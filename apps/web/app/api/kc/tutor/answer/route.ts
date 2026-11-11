import { generateText, jsonSchema, Output, wrapLanguageModel, type LanguageModelMiddleware } from "ai";

import { api } from "@/lib/api";
import type { KcTutorSession } from "@/lib/kc";
import { languageModel } from "@/lib/language-model";
import { DEFAULT_KC_MODEL, isKcModel, missingKeyMessage } from "@/lib/kc-models";
import { requestForCall, type ModelCall } from "@/lib/stored-prompt";

export const runtime = "nodejs";
export const maxDuration = 60;

const ANSWER_PROMPT =
  "The child's latest message is their answer. Return the decision object. The reply is the only text the child sees. Follow the system instructions. Do not set the type, the edges, or the score.";

type TurnBundle = KcTutorSession & {
  system_prompt: string;
  response_schema: Record<string, unknown>;
  temperature: number;
};

type Decision = {
  reply: string;
  decision: string;
  substep_passed: boolean;
  block_complete: boolean;
  generated_mcq: Record<string, unknown> | null;
  rubric_met: string[];
  misconception: string | null;
  hint_tier: string;
  help_requested: boolean;
  off_course: boolean;
  affect: string;
  confidence: string;
  score_justification: string;
  what_was_strong: string;
  what_to_work_on: string;
  safety_flag: string;
};

type StoredCall = {
  system_prompt: string;
  messages: unknown;
  model: string;
};

function asDecision(value: unknown): Decision | null {
  if (!value || typeof value !== "object") return null;
  const row = value as Partial<Decision>;
  if (typeof row.reply !== "string" || typeof row.decision !== "string") return null;
  const generated = row.generated_mcq;
  return {
    reply: row.reply,
    decision: row.decision,
    substep_passed: Boolean(row.substep_passed),
    block_complete: Boolean(row.block_complete),
    generated_mcq:
      generated && typeof generated === "object" && !Array.isArray(generated)
        ? (generated as Record<string, unknown>)
        : null,
    rubric_met: Array.isArray(row.rubric_met) ? row.rubric_met.map(String) : [],
    misconception: typeof row.misconception === "string" ? row.misconception : null,
    hint_tier: typeof row.hint_tier === "string" ? row.hint_tier : "nudge",
    help_requested: Boolean(row.help_requested),
    off_course: Boolean(row.off_course),
    affect: typeof row.affect === "string" ? row.affect : "engaged",
    confidence: typeof row.confidence === "string" ? row.confidence : "ok",
    score_justification: typeof row.score_justification === "string" ? row.score_justification : "",
    what_was_strong: typeof row.what_was_strong === "string" ? row.what_was_strong : "",
    what_to_work_on: typeof row.what_to_work_on === "string" ? row.what_to_work_on : "",
    safety_flag: typeof row.safety_flag === "string" && row.safety_flag ? row.safety_flag : "none",
  };
}

export async function POST(req: Request) {
  let body: { sessionId?: string; answer?: string; model?: string };
  try {
    body = (await req.json()) as { sessionId?: string; answer?: string; model?: string };
  } catch {
    return new Response("Expected JSON with sessionId and answer.", { status: 400 });
  }
  const sessionId = body.sessionId;
  const answer = typeof body.answer === "string" ? body.answer.trim() : "";
  if (!sessionId) return new Response("sessionId is required.", { status: 400 });
  if (!answer) return new Response("Write an answer first.", { status: 400 });

  const requested = typeof body.model === "string" ? body.model.trim() : "";
  if (requested && !isKcModel(requested)) {
    return new Response("That model is not allowed.", { status: 422 });
  }
  const modelName = requested && isKcModel(requested) ? requested : DEFAULT_KC_MODEL;
  const missingKey = missingKeyMessage(modelName);
  if (missingKey) {
    return new Response(missingKey, {
      status: 503,
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  }

  let bundle: TurnBundle;
  try {
    bundle = await api<TurnBundle>(`/kc/tutor/sessions/${sessionId}/turn`, {
      method: "POST",
      body: JSON.stringify({ answer }),
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not store the answer.";
    return new Response(message, { status: 502 });
  }

  let captured: StoredCall | null = null;
  const captureRequest: LanguageModelMiddleware = {
    specificationVersion: "v4",
    wrapGenerate: async ({ doGenerate, params, model }) => {
      const request = requestForCall(params as ModelCall, bundle.system_prompt);
      captured = {
        system_prompt: request.system_prompt,
        messages: Array.isArray(request.messages) ? request.messages : [],
        model: model.modelId || modelName,
      };
      return doGenerate();
    },
  };

  let decision: Decision | null = null;
  try {
    const result = await generateText({
      model: wrapLanguageModel({ model: languageModel(modelName), middleware: captureRequest }),
      instructions: bundle.system_prompt,
      prompt: ANSWER_PROMPT,
      temperature: bundle.temperature,
      output: Output.object({ schema: jsonSchema(bundle.response_schema) }),
    });
    decision = asDecision(result.output);
    if (!decision && result.text) {
      try {
        decision = asDecision(JSON.parse(result.text));
      } catch {
        decision = null;
      }
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : "The tutor could not answer.";
    return new Response(message, { status: 502 });
  }
  if (!decision || !decision.reply.trim()) {
    return new Response("The tutor did not write a reply.", { status: 502 });
  }

  let session: KcTutorSession;
  try {
    session = await api<KcTutorSession>(`/kc/tutor/sessions/${sessionId}/decision`, {
      method: "POST",
      body: JSON.stringify(decision),
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not apply that decision.";
    return new Response(message, { status: 502 });
  }

  const added = [...session.messages].reverse().find((message) => message.role === "assistant");
  const stored = captured ?? {
    system_prompt: bundle.system_prompt,
    messages: [{ role: "user", content: ANSWER_PROMPT }],
    model: modelName,
  };
  try {
    await api(`/kc/sessions/${sessionId}/model-prompts`, {
      method: "POST",
      body: JSON.stringify({
        system_prompt: stored.system_prompt,
        messages: stored.messages,
        model: stored.model,
        message_id: added?.id ?? null,
        rubric_met: decision.rubric_met,
        misconception: decision.misconception,
      }),
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not store the prompt.";
    return new Response(message, { status: 502 });
  }
  return Response.json(session);
}
