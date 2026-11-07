import { generateText, wrapLanguageModel, type LanguageModelMiddleware } from "ai";

import { api } from "@/lib/api";
import type { KcTutorSession } from "@/lib/kc";
import { languageModel } from "@/lib/language-model";
import { DEFAULT_KC_MODEL, isKcModel, missingKeyMessage } from "@/lib/kc-models";
import { requestForCall, type ModelCall } from "@/lib/stored-prompt";

export const runtime = "nodejs";
export const maxDuration = 60;

const SPEAK_PROMPT =
  "Say this step to the student now. Follow the system instructions. Do not set the type, the edges, or the score.";

type PromptBundle = {
  system_prompt: string;
  recipe: string;
  step: number;
  step_label: string;
};

type StoredCall = {
  system_prompt: string;
  messages: unknown;
  model: string;
};

export async function POST(req: Request) {
  let body: { sessionId?: string; model?: string };
  try {
    body = (await req.json()) as { sessionId?: string; model?: string };
  } catch {
    return new Response("Expected JSON with sessionId.", { status: 400 });
  }
  const sessionId = body.sessionId;
  if (!sessionId) return new Response("sessionId is required.", { status: 400 });

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
  try {
    const result = await generateText({
      model: wrapLanguageModel({ model: languageModel(modelName), middleware: captureRequest }),
      instructions: bundle.system_prompt,
      prompt: SPEAK_PROMPT,
    });
    spoken = result.text.trim();
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
      body: JSON.stringify({ content: spoken }),
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not store that step.";
    return new Response(message, { status: 502 });
  }

  const added =
    session.messages.length > prior.messages.length ? session.messages[session.messages.length - 1] : undefined;
  const messageId = added && added.role === "assistant" ? added.id : null;
  const stored = captured ?? {
    system_prompt: bundle.system_prompt,
    messages: [{ role: "user", content: SPEAK_PROMPT }],
    model: modelName,
  };
  try {
    await api(`/kc/sessions/${sessionId}/model-prompts`, {
      method: "POST",
      body: JSON.stringify({
        system_prompt: stored.system_prompt,
        messages: stored.messages,
        model: stored.model,
        message_id: messageId,
      }),
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not store the prompt.";
    return new Response(message, { status: 502 });
  }
  return Response.json(session);
}
