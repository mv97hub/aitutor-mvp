/** Server renders fail closed so a stuck API cannot hold the document open. */
const SERVER_FETCH_TIMEOUT_MS = 20_000;

export function apiBase(): string {
  const configured =
    typeof window === "undefined"
      ? process.env.API_URL || process.env.NEXT_PUBLIC_API_URL
      : process.env.NEXT_PUBLIC_API_URL;
  return (configured || "http://localhost:8000").replace(/\/$/, "");
}

export function detailFrom(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object" || !("detail" in body)) return fallback;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (typeof item === "string") return item.trim();
        if (item && typeof item === "object" && "msg" in item) {
          return String((item as { msg: unknown }).msg).trim();
        }
        return JSON.stringify(item);
      })
      .filter(Boolean);
    if (parts.length === 0) return fallback;
    const gaps = detail.every((item) => typeof item === "string");
    return parts.join(gaps ? " · " : " ");
  }
  return fallback;
}

function fetchTimedOut(err: unknown): boolean {
  return err instanceof Error && (err.name === "TimeoutError" || err.name === "AbortError");
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const server = typeof window === "undefined";
  let response: Response;
  try {
    response = await fetch(`${apiBase()}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
      signal: init?.signal ?? (server ? AbortSignal.timeout(SERVER_FETCH_TIMEOUT_MS) : undefined),
    });
  } catch (err) {
    if (server && fetchTimedOut(err)) {
      throw new Error("The tutor service is not reachable.");
    }
    throw err;
  }
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text) as unknown;
    } catch {
      if (!response.ok) throw new Error(text.trim() || `Request failed (${response.status})`);
      throw new Error("The tutor service sent a response that could not be read.");
    }
  }
  if (!response.ok) {
    throw new Error(detailFrom(body, text || `Request failed (${response.status})`));
  }
  return body as T;
}
