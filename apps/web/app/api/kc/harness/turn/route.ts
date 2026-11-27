import { api, ApiError } from "@/lib/api";

export const runtime = "nodejs";
export const maxDuration = 60;

/** Store one harness turn. The turn is recorded and returned. */
export async function POST(req: Request) {
  let body: { chatId?: string; turn?: Record<string, unknown> };
  try {
    body = (await req.json()) as { chatId?: string; turn?: Record<string, unknown> };
  } catch {
    return new Response("Expected JSON.", { status: 400 });
  }
  const chatId = body.chatId || "";
  if (!chatId || !body.turn) return new Response("chatId and turn are required.", { status: 400 });
  try {
    const recorded = await api(`/kc/harness/chats/${chatId}/turns`, {
      method: "POST",
      body: JSON.stringify(body.turn),
    });
    return Response.json(recorded);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not store the turn.";
    return new Response(message, { status: error instanceof ApiError ? error.status : 502 });
  }
}
