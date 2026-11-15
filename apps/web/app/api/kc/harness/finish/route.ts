import { api } from "@/lib/api";
import { judgeFinishedChat } from "@/lib/harness-judge-run";

export const runtime = "nodejs";
export const maxDuration = 60;

/** Finish a harness chat on the server, then judge it. Not the live tutor path. */
export async function POST(req: Request) {
  let body: { chatId?: string; reason?: string };
  try {
    body = (await req.json()) as { chatId?: string; reason?: string };
  } catch {
    return new Response("Expected JSON.", { status: 400 });
  }
  const chatId = body.chatId || "";
  if (!chatId) return new Response("chatId is required.", { status: 400 });
  try {
    await api(`/kc/harness/chats/${chatId}/finish`, {
      method: "POST",
      body: JSON.stringify({ reason: body.reason || "completed" }),
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not finish the chat.";
    return new Response(message, { status: 502 });
  }
  try {
    await judgeFinishedChat(chatId);
  } catch {
    // Finish already succeeded. The report shows not judged when no score was stored.
  }
  return Response.json({ ok: true });
}
