import { generateText, jsonSchema, Output } from "ai";

import { api } from "@/lib/api";
import { examModelForCall, type BlindExamAttemptSummary } from "@/lib/blind-exam";
import { missingKeyMessage } from "@/lib/kc-models";
import { languageModel } from "@/lib/language-model";

export const runtime = "nodejs";
export const maxDuration = 60;

type EpistemicContext = {
  chat_id: string;
  course_id: string;
  exam_needs_generation: boolean;
  tutor_message_count?: number;
  exam_id?: string;
  system_prompt?: string;
  user_prompt?: string;
  response_schema?: Record<string, unknown>;
  temperature?: number;
};

/** Run a blank-slate epistemic-sandbox Post-Test restricted strictly to a HarnessChat's tutor messages. */
export async function POST(req: Request) {
  let body: { chatId?: string; model?: string };
  try {
    body = (await req.json()) as { chatId?: string; model?: string };
  } catch {
    return Response.json({ detail: "Expected JSON with chatId." }, { status: 400 });
  }
  const chatId = (body.chatId || "").trim();
  if (!chatId) return Response.json({ detail: "chatId is required." }, { status: 400 });

  let ctx: EpistemicContext;
  try {
    ctx = await api<EpistemicContext>(`/kc/harness/chats/${encodeURIComponent(chatId)}/epistemic-context?fallback=true`);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not load epistemic exam context.";
    return Response.json({ detail: message }, { status: 502 });
  }
  if (!ctx.exam_id || !ctx.system_prompt || !ctx.user_prompt || !ctx.response_schema) {
    return Response.json({ detail: "No frozen post-test available for this chat's course." }, { status: 422 });
  }

  const modelName = examModelForCall(body.model);
  const missingKey = missingKeyMessage(modelName);
  if (missingKey) return Response.json({ detail: missingKey }, { status: 503 });

  let agentAnswers: Array<{ item_id: string; answer: string }> = [];
  try {
    const result = await generateText({
      model: languageModel(modelName),
      instructions: ctx.system_prompt,
      prompt: ctx.user_prompt,
      temperature: typeof ctx.temperature === "number" ? ctx.temperature : 0,
      output: Output.object({ schema: jsonSchema(ctx.response_schema) }),
    });
    const parsed = result.output as { answers?: Array<{ item_id: string; answer: string }> } | undefined;
    agentAnswers = Array.isArray(parsed?.answers) ? parsed.answers : [];
  } catch (error) {
    const message = error instanceof Error ? error.message : "Epistemic exam agent call failed.";
    return Response.json({ detail: message }, { status: 502 });
  }

  const answerMap: Record<string, string> = {};
  for (const row of agentAnswers) {
    if (row && typeof row.item_id === "string") answerMap[row.item_id] = String(row.answer ?? "");
  }

  let transferGrades: unknown[] | null = null;
  try {
    const gradeBundle = await api<{
      has_transfer_items: boolean;
      system_prompt?: string;
      user_prompt?: string;
      response_schema?: Record<string, unknown>;
    }>(`/kc/tutor/courses/${encodeURIComponent(ctx.course_id)}/exam/grade-prompt`, {
      method: "POST",
      body: JSON.stringify({ exam_id: ctx.exam_id, answers: answerMap }),
    });
    if (gradeBundle.has_transfer_items && gradeBundle.system_prompt && gradeBundle.user_prompt && gradeBundle.response_schema) {
      const gRes = await generateText({
        model: languageModel(modelName),
        instructions: gradeBundle.system_prompt,
        prompt: gradeBundle.user_prompt,
        temperature: 0,
        output: Output.object({ schema: jsonSchema(gradeBundle.response_schema) }),
      });
      const parsed = gRes.output as { grades?: unknown[] } | undefined;
      if (parsed && Array.isArray(parsed.grades)) transferGrades = parsed.grades;
    }
  } catch {
    transferGrades = null;
  }

  try {
    const saved = await api<BlindExamAttemptSummary>(`/kc/harness/chats/${encodeURIComponent(chatId)}/blind-post-test`, {
      method: "POST",
      body: JSON.stringify({
        exam_id: ctx.exam_id,
        answers: answerMap,
        transfer_grades: transferGrades,
      }),
    });
    return Response.json(saved);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not record epistemic post-test.";
    return Response.json({ detail: message }, { status: 502 });
  }
}
