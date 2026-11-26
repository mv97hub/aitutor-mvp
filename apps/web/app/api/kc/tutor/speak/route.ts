import { generateText, jsonSchema, Output, wrapLanguageModel, type LanguageModelMiddleware } from "ai";

import { api } from "@/lib/api";
import type { KcTutorSession } from "@/lib/kc";
import { languageModel } from "@/lib/language-model";
import { isKcModel, kcModel, missingKeyMessage, modelForCall } from "@/lib/kc-models";
import { readModelUsage, type ModelUsageCounts } from "@/lib/model-usage";
import { requestForCall, type ModelCall } from "@/lib/stored-prompt";
import { finishSavedTurn, newTutorMessageId } from "@/lib/tutor-turn";

export const runtime = "nodejs";
export const maxDuration = 60;

const SPEAK_PROMPT =
  "Say the opening now. This is the only message for this change. Ask the new question if this step opens with one. Give no cue. Do not praise what came before. Never say the word block to the learner. Return the decision object.";

type PromptBundle = {
  system_prompt: string;
  response_schema: Record<string, unknown>;
  temperature: number;
  recipe: string;
  step: number;
  step_label: string;
  tutor_model?: string;
  model?: string;
};

type Decision = {
  reply?: string;
  generated_mcq?: Record<string, unknown> | null;
  safety_flag?: string;
};

type StoredCall = {
  system_prompt: string;
  messages: unknown;
  model: string;
};

export async function POST(req: Request) {
  let body: { sessionId?: string; model?: string; turnId?: string; revision?: number };
  try {
    body = (await req.json()) as { sessionId?: string; model?: string; turnId?: string; revision?: number };
  } catch {
    return new Response("Expected JSON with sessionId.", { status: 400 });
  }
  const sessionId = body.sessionId;
  const turnId = typeof body.turnId === "string" ? body.turnId.trim() : "";
  const revision = typeof body.revision === "number" ? body.revision : 0;
  if (!sessionId) return new Response("sessionId is required.", { status: 400 });

  const requested = typeof body.model === "string" ? body.model.trim() : "";
  const called = requested ? modelForCall(requested) : "";
  if (requested && !isKcModel(called)) {
    return new Response("That model is not allowed.", { status: 422 });
  }

  let prior: KcTutorSession;
  try {
    prior = await api<KcTutorSession>(`/kc/tutor/sessions/${sessionId}`);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not load the session.";
    return new Response(message, { status: 502 });
  }

  let bundle: PromptBundle;
  try {
    bundle = await api<PromptBundle>(`/kc/tutor/sessions/${sessionId}/prompt`);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not load the prompt.";
    return new Response(message, { status: 502 });
  }

  if (turnId) {
    try {
      const claim = await api<{
        replayed?: boolean;
        held?: boolean;
        session?: KcTutorSession;
      }>(`/kc/tutor/sessions/${sessionId}/speech`, {
        method: "POST",
        body: JSON.stringify({ phase: "claim", turn_id: turnId, revision, content: "" }),
      });
      if (claim.replayed && claim.session) return Response.json(claim.session);
      if (claim.held) return new Response("The opening is already in progress.", { status: 409 });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not claim this opening.";
      return new Response(message, { status: 502 });
    }
  }

  const modelName =
    called && isKcModel(called) ? called : kcModel(bundle.tutor_model ?? bundle.model ?? prior.tutor_model);
  const missingKey = missingKeyMessage(modelName);
  if (missingKey) {
    return new Response(missingKey, {
      status: 503,
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
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

  let spoken = "";
  let safetyFlag = "none";
  let generatedMcq: Record<string, unknown> | null = null;
  let decision: Decision | null = null;
  let usage: ModelUsageCounts = readModelUsage(undefined);
  try {
    const result = await generateText({
      model: wrapLanguageModel({ model: languageModel(modelName), middleware: captureRequest }),
      instructions: bundle.system_prompt,
      prompt: SPEAK_PROMPT,
      temperature: bundle.temperature,
      output: Output.object({ schema: jsonSchema(bundle.response_schema) }),
    });
    usage = readModelUsage(result.usage);
    decision = (result.output as Decision | undefined) ?? null;
    spoken = (decision?.reply || result.text || "").trim();
    safetyFlag = typeof decision?.safety_flag === "string" && decision.safety_flag ? decision.safety_flag : "none";
    const generated = decision?.generated_mcq;
    if (generated && typeof generated === "object" && !Array.isArray(generated) && generated.choices) {
      generatedMcq = generated;
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : "The tutor could not say this step.";
    return new Response(message, { status: 502 });
  }
  if (!spoken) {
    return new Response("The tutor did not say this step.", { status: 502 });
  }

  let session: KcTutorSession;
  try {
    session = await api<KcTutorSession>(`/kc/tutor/sessions/${sessionId}/speech`, {
      method: "POST",
      body: JSON.stringify(
        turnId
          ? { phase: "commit", turn_id: turnId, revision, content: spoken, generated_mcq: generatedMcq, safety_flag: safetyFlag }
          : { content: spoken, generated_mcq: generatedMcq, safety_flag: safetyFlag },
      ),
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not store that step.";
    return new Response(message, { status: 502 });
  }

  const messageId = newTutorMessageId(prior.messages, session.messages);
  const stored = captured ?? {
    system_prompt: bundle.system_prompt,
    messages: [{ role: "user", content: SPEAK_PROMPT }],
    model: modelName,
  };
  const saved = await finishSavedTurn(session, async () => {
    await api(`/kc/sessions/${sessionId}/model-prompts`, {
      method: "POST",
      body: JSON.stringify({
        system_prompt: stored.system_prompt,
        messages: stored.messages,
        model: stored.model,
        message_id: messageId,
        decision: decision ?? null,
      }),
    });
    await api(`/kc/sessions/${sessionId}/token-usage`, {
      method: "POST",
      body: JSON.stringify({
        kind: "speak",
        model: stored.model,
        message_id: messageId,
        ...usage,
      }),
    });
  });
  return Response.json(saved);
}
