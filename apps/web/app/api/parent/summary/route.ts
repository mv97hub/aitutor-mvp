import { generateText, jsonSchema, Output } from "ai";

import { api } from "@/lib/api";
import { DEFAULT_KC_MODEL, missingKeyMessage } from "@/lib/kc-models";
import { languageModel } from "@/lib/language-model";
import { knownId, type ParentChatDetail } from "@/lib/parent";
import {
  PARENT_SUMMARY_INSTRUCTIONS,
  PARENT_SUMMARY_PROMPT,
  PARENT_SUMMARY_SCHEMA,
  parseParentSummary,
  transcriptText,
} from "@/lib/parent-summary";

export const runtime = "nodejs";
export const maxDuration = 60;

/** Generated on click and returned to the page. Nothing here is stored. */
export async function POST(req: Request) {
  let body: { parentId?: string; studentId?: string; sessionId?: string };
  try {
    body = (await req.json()) as { parentId?: string; studentId?: string; sessionId?: string };
  } catch {
    return new Response("Expected JSON with parentId, studentId, and sessionId.", { status: 400 });
  }
  const parentId = knownId(body.parentId);
  const studentId = knownId(body.studentId);
  const sessionId = knownId(body.sessionId);
  if (!parentId || !studentId || !sessionId) {
    return new Response("parentId, studentId, and sessionId are required.", { status: 400 });
  }

  const missingKey = missingKeyMessage(DEFAULT_KC_MODEL);
  if (missingKey) {
    return new Response(missingKey, {
      status: 503,
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  }

  let chat: ParentChatDetail;
  try {
    chat = await api<ParentChatDetail>(`/parents/${parentId}/children/${studentId}/sessions/${sessionId}`);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not load that chat.";
    return new Response(message, { status: 502 });
  }
  if (chat.messages.length === 0) {
    return new Response("This chat has no messages yet, so there is nothing to summarize.", { status: 422 });
  }

  try {
    const result = await generateText({
      model: languageModel(DEFAULT_KC_MODEL),
      instructions: `${PARENT_SUMMARY_INSTRUCTIONS}\n\n${transcriptText(chat)}`,
      prompt: PARENT_SUMMARY_PROMPT,
      temperature: 0.4,
      output: Output.object({ schema: jsonSchema(PARENT_SUMMARY_SCHEMA) }),
    });
    let summary = parseParentSummary(result.output);
    if (!summary && result.text) {
      try {
        summary = parseParentSummary(JSON.parse(result.text));
      } catch {
        summary = null;
      }
    }
    if (!summary) return new Response("The summary could not be read. Try again.", { status: 502 });
    return Response.json(summary);
  } catch (error) {
    const message = error instanceof Error ? error.message : "The summary could not be written.";
    return new Response(message, { status: 502 });
  }
}
