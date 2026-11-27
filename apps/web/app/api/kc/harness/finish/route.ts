import { api, ApiError } from "@/lib/api";

export const runtime = "nodejs";
export const maxDuration = 60;

/** Finish a harness chat on the server. Scoring happens outside the app. */
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
    await api(`/kc/harness/chats/${chatId}/finish`, {
      method: "POST",
      body: JSON.stringify({ reason: body.reason || "completed", claim_generation: body.claim_generation }),
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not finish the chat.";
    return new Response(message, { status: error instanceof ApiError ? error.status : 502 });
  }
  return Response.json({ ok: true });
}
