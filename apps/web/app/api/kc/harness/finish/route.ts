import { api, ApiError } from "@/lib/api";
import { judgeFinishedChat } from "@/lib/harness-judge-run";

export const runtime = "nodejs";
export const maxDuration = 60;

/** Finish a harness chat on the server, then judge it. Not the live tutor path. */
export async function POST(req: Request) {
  let body: { chatId?: string; reason?: string; claim_generation?: number };
  try {
    body = (await req.json()) as { chatId?: string; reason?: string; claim_generation?: number };
  } catch {
    return new Response("Expected JSON.", { status: 400 });
  }
  const chatId = body.chatId || "";
  if (!chatId) return new Response("chatId is required.", { status: 400 });
  try {
    const finished = await api<{ ended_how: string }>(`/kc/harness/chats/${chatId}/finish`, {
      method: "POST",
      body: JSON.stringify({ reason: body.reason || "completed", claim_generation: body.claim_generation }),
    });
    if (finished.ended_how === "scenario_not_reached") return Response.json({ ok: true });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not finish the chat.";
    return new Response(message, { status: error instanceof ApiError ? error.status : 502 });
  }
  try {
    await judgeFinishedChat(chatId);
  } catch {
    // Finish already succeeded. The report shows not judged when no score was stored.
  }
  return Response.json({ ok: true });
}
