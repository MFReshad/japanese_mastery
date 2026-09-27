import { test, expect, APIRequestContext } from "@playwright/test";

const backend = "http://127.0.0.1:8100";
const headers = {};
async function seed(request: APIRequestContext) {
  const book = await (await request.post(`${backend}/books`, { headers, data: { title: `Browser ${Date.now()}` } })).json();
  const chapters = [];
  for (const number of [1, 2]) {
    chapters.push(await (await request.post(`${backend}/chapters`, { headers, data: { book_id: book.id, chapter_number: number, title: `Lesson ${number}` } })).json());
  }
  const sources = [];
  for (const order of [1, 2]) {
    sources.push(await (await request.post(`${backend}/vocabulary-sources`, { headers, data: {
      book_id: book.id, chapter_id: chapters[1].id, item_order: order,
      expression: `朝${book.id}`, reading: `あさ${book.id}`, meaning: `morning ${book.id}`,
    } })).json());
  }
  return { book, chapters, sources };
}
test("practice reveal survives page reload and saves exactly once", async ({ page, request }) => {
  const { book, chapters } = await seed(request);
  await page.goto(`/practice?practice_type=vocabulary&book_id=${book.id}&chapter_id=${chapters[1].id}`);
  await page.getByRole("button", {name: "Start", exact: true}).click();
  await page.getByRole("button", {name: "Show answer"}).click();
  await page.reload();
  await expect(page.getByRole("button", {name: "Correct", exact: true})).toBeVisible();
  await page.getByRole("button", {name: "Correct", exact: true}).click();
  await expect(page.getByRole("button", {name: "Show answer"})).toBeVisible();
  await page.getByRole("button", {name: "Show answer"}).click();
  await page.getByRole("button", {name: "Wrong", exact: true}).click();
  await expect(page.getByText("Session complete.")).toBeVisible();
});

test("queued answer recovers after network failure and reload", async ({ page, request }) => {
  const { sources } = await seed(request);
  await page.goto(`/practice?practice_type=vocabulary&source_entry_id=${sources[0].id}`);
  await page.getByRole("button", {name: "Start", exact: true}).click();
  await page.getByRole("button", {name: "Show answer"}).click();
  await page.route("**/practice/answer", route => route.abort());
  await page.getByRole("button", {name: "Correct", exact: true}).click();
  await expect.poll(() => page.evaluate(() => JSON.parse(sessionStorage.getItem("practice-answer-queue-v1") || "{}").items?.length)).toBe(1);
  await page.unroute("**/practice/answer");
  await page.reload();
  await expect(page.getByText("Session complete.")).toBeVisible();
  await expect.poll(() => page.evaluate(() => JSON.parse(sessionStorage.getItem("practice-answer-queue-v1") || "{}").items?.length)).toBe(0);
});

test("permanent rejection does not block a later answer", async ({ page, request }) => {
  const { book, chapters } = await seed(request);
  await page.goto(`/practice?practice_type=vocabulary&book_id=${book.id}&chapter_id=${chapters[1].id}`);
  await page.getByRole("button", {name: "Start", exact: true}).click();
  let rejected = false;
  await page.route("**/practice/answer", async route => {
    if (!rejected) { rejected = true; await route.fulfill({status: 409, contentType: "application/json", body: '{"detail":"conflict"}'}); }
    else await route.continue();
  });
  for (let i = 0; i < 2; i++) {
    await page.getByRole("button", {name: "Show answer"}).click();
    await page.getByRole("button", {name: "Correct", exact: true}).click();
  }
  await expect.poll(() => page.evaluate(() => JSON.parse(sessionStorage.getItem("practice-answer-queue-v1") || "{}").items?.length)).toBe(0);
  await expect(page.getByRole("alert").filter({hasText: "need review"})).toContainText("need review");
});

test("Study deep link survives delayed lookups", async ({ page, request }) => {
  const { book, chapters } = await seed(request);
  await page.route("**/chapters", async route => {
    const response = await route.fetch();
    await new Promise(resolve => setTimeout(resolve, 400));
    await route.fulfill({response});
  });
  await page.goto(`/study?book=${book.id}&chapter=${chapters[1].id}`);
  await expect(page.getByRole("combobox").last()).toHaveValue(String(chapters[1].id));
  await expect(page.getByText("2 words")).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`chapter=${chapters[1].id}`));
});

test("canonical stars update every visible occurrence and book filter scopes chapters", async ({ page, request }) => {
  const { book, chapters } = await seed(request);
  await page.goto("/library");
  await page.getByLabel("Book", {exact: true}).selectOption(String(book.id));
  await page.getByLabel("Chapter", {exact: true}).selectOption(String(chapters[1].id));
  await expect(page.getByRole("button", {name: "Star item", exact: true})).toHaveCount(2);
  await page.getByRole("button", {name: "Star item", exact: true}).first().click();
  await expect(page.getByRole("button", {name: "Unstar item", exact: true})).toHaveCount(2);
  await page.reload();
});

test("management create resets form after await and refreshes counts", async ({ page }) => {
  await page.goto("/manage");
  const title = `Created in browser ${Date.now()}`;
  await page.getByPlaceholder("Title", {exact: true}).first().fill(title);
  await page.getByPlaceholder("Short name").fill(`B${Date.now()}`);
  await page.getByRole("button", {name: "Create book", exact: true}).click();
  await expect(page.getByPlaceholder("Title", {exact: true}).first()).toHaveValue("");
  await expect(page.getByText(`${title} · vocab 0 · kanji 0`)).toBeVisible();
});

test("reveal remains saveable after backend process restart", async ({ page, request }) => {
  test.skip(!process.env.TEST_POSTGRES_URL, "Requires disposable TEST_POSTGRES_URL and E2E_PYTHON");
  const { spawn } = await import("node:child_process");
  const path = await import("node:path");
  const { book, chapters } = await seed(request);
  const startWorker = () => spawn(process.env.E2E_PYTHON || "python3", ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8102"], {
    cwd: path.resolve("../backend"), stdio: "ignore",
    env: {...process.env, DATABASE_URL: process.env.TEST_POSTGRES_URL, CORS_ORIGINS: '["http://localhost:3100"]'},
  });
  let worker = startWorker();
  async function ready() {
    await expect.poll(async () => { try { return (await request.get("http://127.0.0.1:8102/health")).status(); } catch { return 0; } }).toBe(200);
  }
  async function stop() { const current = worker; await new Promise<void>(resolve => { current.once("exit", () => resolve()); current.kill("SIGTERM"); }); }
  try {
    await ready();
    await page.route("**/practice/**", async route => {
      if (!route.request().url().startsWith(backend)) { await route.continue(); return; }
      const response = await route.fetch({url: route.request().url().replace(backend, "http://127.0.0.1:8102")});
      await route.fulfill({response});
    });
    await page.goto(`/practice?practice_type=vocabulary&book_id=${book.id}&chapter_id=${chapters[1].id}`);
    await page.getByRole("button", {name: "Start", exact: true}).click();
    await page.getByRole("button", {name: "Show answer"}).click();
    await stop(); worker = startWorker(); await ready();
    await page.reload();
    await page.getByRole("button", {name: "Correct", exact: true}).click();
    await expect(page.getByRole("button", {name: "Show answer"})).toBeVisible();
    await expect.poll(() => page.evaluate(() => JSON.parse(sessionStorage.getItem("practice-answer-queue-v1") || "{}").items?.length)).toBe(0);
  } finally { await stop(); }
});

test("management creates kanji in the selected book and edits its source", async ({ page, request }) => {
  const {book, chapters} = await seed(request);
  await page.goto("/manage");
  const create = page.locator("form").filter({has: page.getByPlaceholder("character", {exact: true})});
  await create.locator('select[name="book_id"]').selectOption(String(book.id));
  await create.locator('select[name="chapter_id"]').selectOption(String(chapters[1].id));
  await create.getByPlaceholder("Order").fill("3");
  await create.getByPlaceholder("character", {exact: true}).fill("語");
  await create.getByPlaceholder("meaning", {exact: true}).fill("language");
  await create.getByRole("button", {name: "Save", exact: true}).click();
  await expect(create.getByPlaceholder("character", {exact: true})).toHaveValue("");
  const editor = page.locator("section").filter({has: page.getByRole("heading", {name: "Edit source entry"})});
  await editor.getByLabel("Book", {exact: true}).selectOption(String(book.id));
  await editor.getByLabel("Chapter", {exact: true}).selectOption(String(chapters[1].id));
  await expect(editor.getByLabel("Source entry").locator("option")).toHaveCount(2);
  await editor.getByLabel("Source entry").selectOption({index: 1});
  await editor.locator("textarea").first().fill("speech / language");
  await editor.getByRole("button", {name: "Save changes"}).click();
  await expect(editor.getByRole("status")).toContainText("Saved.");
  const sources = await (await request.get(`${backend}/kanji-sources?book_id=${book.id}&chapter_id=${chapters[1].id}`)).json();
  expect(sources[0].meaning_as_printed).toBe("speech / language");
});
