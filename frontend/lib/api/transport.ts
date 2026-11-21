const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
  get retryable() { return this.status === 408 || this.status === 429 || this.status >= 500; }
}

export function retryable(error: unknown) { return !(error instanceof ApiError) || error.retryable; }

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(`${API_BASE}${path}`, { ...init, signal: controller.signal, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) }, cache: "no-store" });
    if (!response.ok) {
      const body = await response.text();
      let message = body;
      try {
        const parsed = JSON.parse(body) as {detail?: unknown};
        if (typeof parsed.detail === "string") message = parsed.detail;
      } catch { /* Keep a non-JSON server response as-is. */ }
      throw new ApiError(response.status, message);
    }
    if (response.status === 204) return undefined as T;
    return await response.json() as T;
  } finally { clearTimeout(timeout); }
}
