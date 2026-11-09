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

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  const body = text ? (JSON.parse(text) as unknown) : null;
  if (!response.ok) {
    throw new Error(detailFrom(body, text || `Request failed (${response.status})`));
  }
  return body as T;
}
