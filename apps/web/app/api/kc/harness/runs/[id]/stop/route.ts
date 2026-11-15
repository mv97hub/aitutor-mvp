import { api } from "@/lib/api";
import { stopBackgroundRun } from "@/lib/harness-background";

export const runtime = "nodejs";

/** Stop the loop. Chats already stored stay; queued and running chats are marked cancelled. */
export async function POST(_req: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  stopBackgroundRun(id);
  try {
    const run = await api<{ status?: string }>(`/kc/harness/runs/${id}/cancel`, { method: "POST" });
    return Response.json({ ok: true, status: run.status || "cancelled" });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not stop the run.";
    return new Response(message, { status: 502 });
  }
}
