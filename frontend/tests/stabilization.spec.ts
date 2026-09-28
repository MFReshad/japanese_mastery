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
  await page.getByRole("button", {name: "Retry"}).click();
  await expect(page.getByRole("alert").filter({hasText: "need review"})).toHaveCount(0);
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

test("management dashboard opens books and creates a book", async ({ page }) => {
  await page.goto("/manage");
  await page.getByRole("link", {name: /Books/}).click();
  const title = `Created in browser ${Date.now()}`;
  await page.getByRole("button", {name: "Add book"}).click();
  await page.getByLabel("Title", {exact: true}).fill(title);
  await page.getByLabel("Short name").fill(`B${Date.now()}`);
  await page.getByRole("button", {name: "Save book"}).click();
  const row = page.getByRole("article").filter({has: page.getByRole("heading", {name: title})});
  await expect(row).toBeVisible();
  await row.getByRole("button", {name: "Mark inactive"}).click();
  await expect(row.getByText("Inactive", {exact: true})).toBeVisible();
  await page.goto("/study");
  await expect(page.getByRole("combobox", {name: "Book"}).locator("option", {hasText: title})).toHaveCount(0);
  await page.goto("/manage/books");
  await page.getByRole("article").filter({has: page.getByRole("heading", {name: title})}).getByRole("button", {name: "Mark active"}).click();
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
  await page.goto(`/manage/kanji?book=${book.id}&chapter=${chapters[1].id}`);
  await page.getByRole("button", {name: "Add kanji"}).click();
  const addDialog = page.getByRole("dialog", {name: "Add kanji"});
  await addDialog.getByRole("textbox", {name: "Kanji", exact: true}).fill("語");
  await addDialog.getByRole("textbox", {name: "Meaning", exact: true}).fill("language");
  await addDialog.getByRole("button", {name: "Save kanji"}).click();
  await page.getByRole("button", {name: "Edit"}).click();
  const editDialog = page.getByRole("dialog", {name: "Edit 語"});
  await editDialog.getByRole("textbox", {name: "Meaning", exact: true}).fill("speech / language");
  await editDialog.getByRole("button", {name: "Save kanji"}).click();
  await expect(page.getByRole("status")).toContainText("saved");
  const sources = await (await request.get(`${backend}/kanji-sources?book_id=${book.id}&chapter_id=${chapters[1].id}`)).json();
  expect(sources[0].meaning_as_printed).toBe("speech / language");
});

test("vocabulary management preserves context through edit add and reorder", async ({ page, request }) => {
  const {book, chapters} = await seed(request);
  await page.goto("/manage");
  await page.getByRole("link", {name: /Vocabulary/}).click();
  await page.getByLabel("Book", {exact: true}).selectOption(String(book.id));
  await page.getByLabel("Chapter", {exact: true}).selectOption(String(chapters[1].id));
  await expect(page.getByText("2 entries in study order")).toBeVisible();
  await page.getByRole("button", {name: "Edit", exact: true}).first().click();
  await page.getByLabel("Meaning").fill("early morning");
  await page.getByRole("button", {name: "Save entry"}).click();
  await page.getByRole("button", {name: "Add vocabulary"}).click();
  await page.getByLabel("Expression").fill("夜");
  await page.getByLabel("Reading").fill("よる");
  await page.getByLabel("Meaning").fill("night");
  await page.getByRole("dialog", {name: "Add vocabulary"}).getByRole("button", {name: "Add vocabulary", exact: true}).click();
  await page.getByRole("button", {name: /Move 夜 up/}).click();
  await page.getByRole("button", {name: "Save order"}).click();
  await page.goto("/manage");
  await page.getByRole("link", {name: /Vocabulary/}).click();
  await expect(page.getByLabel("Book", {exact: true})).toHaveValue(String(book.id));
  await expect(page.getByLabel("Chapter", {exact: true})).toHaveValue(String(chapters[1].id));
  await expect(page.getByText("3 entries in study order")).toBeVisible();
});
