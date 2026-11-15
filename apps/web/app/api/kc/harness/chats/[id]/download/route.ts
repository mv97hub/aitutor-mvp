import { apiBase } from "@/lib/api";

export const runtime = "nodejs";

export async function GET(_req: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const response = await fetch(`${apiBase()}/kc/harness/chats/${id}/download`, { cache: "no-store" });
  const text = await response.text();
  if (!response.ok) return new Response(text || "Could not download that chat.", { status: response.status });
  const disposition = response.headers.get("content-disposition") || `attachment; filename="harness-chat-${id}.md"`;
  return new Response(text, {
    headers: {
      "content-type": "text/markdown; charset=utf-8",
      "content-disposition": disposition,
    },
  });
}
