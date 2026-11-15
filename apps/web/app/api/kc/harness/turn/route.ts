import { api } from "@/lib/api";
import { judgeFinishedChat } from "@/lib/harness-judge-run";

export const runtime = "nodejs";
export const maxDuration = 60;

/** Store one harness turn. When that turn finishes the chat, judge it here. */
export async function POST(req: Request) {
  let body: { chatId?: string; turn?: Record<string, unknown> };
  try {
    body = (await req.json()) as { chatId?: string; turn?: Record<string, unknown> };
  } catch {
    return new Response("Expected JSON.", { status: 400 });
  }
  const chatId = body.chatId || "";
  if (!chatId || !body.turn) return new Response("chatId and turn are required.", { status: 400 });
  let recorded: { stop?: string };
  try {
    recorded = await api(`/kc/harness/chats/${chatId}/turns`, {
      method: "POST",
      body: JSON.stringify(body.turn),
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not store the turn.";
    return new Response(message, { status: 502 });
  }
  if (recorded.stop) {
    try {
      await judgeFinishedChat(chatId);
    } catch {
      // The turn is already stored. A judge failure is recorded inside judgeFinishedChat when the model call fails.
    }
  }
  return Response.json(recorded);
}
