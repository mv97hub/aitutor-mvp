import { Output, jsonSchema, streamText, type JSONSchema7 } from "ai";

import { api } from "@/lib/api";
import type { KcDraft } from "@/lib/kc";
import { languageModel } from "@/lib/language-model";
import { isKcModel, missingKeyMessage, usesOpenRouter, type KcModel } from "@/lib/kc-models";

type PromptBundle = {
  model: string;
  system_prompt: string;
  user_prompt: string;
  schema: JSONSchema7;
};

type CourseResult = {
  reply: string;
  draft: Extract<KcDraft, { kind: "course" }>;
};

const cache = new Map<string, CourseResult>();

function requireKey(model: string) {
  const missing = missingKeyMessage(model);
  if (missing) throw new Error(missing);
}

function requireModel(model: string): KcModel {
  if (!isKcModel(model)) {
    throw new Error("That model is not allowed.");
  }
  return model;
}

async function completeObject(model: KcModel, instructions: string, prompt: string, schema: JSONSchema7) {
  const result = streamText({
    model: languageModel(model),
    output: Output.object({
      schema: jsonSchema(schema),
      name: "kc_draft",
      description: "A curriculum draft. No web search.",
    }),
    instructions,
    prompt,
    ...(model.startsWith("gpt-4") || usesOpenRouter(model) ? { temperature: 0.3 } : {}),
  });
  const output = await result.output;
  if (!output || typeof output !== "object") {
    throw new Error("The model reply could not be read.");
  }
  return output as Record<string, unknown>;
}

async function withModel<T>(
  model: KcModel,
  bundle: PromptBundle,
  finish: (proposal: Record<string, unknown>) => Promise<T>,
): Promise<T> {
  let note = "";
  let last = "The model reply could not be read.";
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      const proposal = await completeObject(
        model,
        note ? `${bundle.system_prompt}\n${note}` : bundle.system_prompt,
        bundle.user_prompt,
        bundle.schema,
      );
      return await finish(proposal);
    } catch (error) {
      last = error instanceof Error ? error.message : last;
      note = `The previous reply was rejected. ${last}`;
    }
  }
  throw new Error(last);
}

export async function draftKcCourse(input: {
  courseId: string;
  message: string;
  model: string;
}): Promise<CourseResult> {
  const model = requireModel(input.model);
  requireKey(model);
  const message = input.message.trim();
  if (!message) throw new Error("Write a message first.");
  const key = `${input.courseId}\n${model}\n${message}`;
  const cached = cache.get(key);
  if (cached) return cached;
  const bundle = await api<PromptBundle>(`/kc/courses/${input.courseId}/draft-prompt`, {
    method: "POST",
    body: JSON.stringify({ message, model }),
  });
  const finished = await withModel(model, bundle, (proposal) =>
    api<CourseResult>(`/kc/courses/${input.courseId}/draft-finish`, {
      method: "POST",
      body: JSON.stringify({ message, proposal }),
    }),
  );
  cache.set(key, finished);
  return finished;
}

export async function draftKcComponent(input: {
  nodeId: string;
  message: string;
  model: string;
}): Promise<void> {
  const model = requireModel(input.model);
  requireKey(model);
  const message = input.message.trim();
  if (!message) throw new Error("Write a message first.");
  const bundle = await api<PromptBundle>(`/kc/nodes/${input.nodeId}/creator-prompt`, {
    method: "POST",
    body: JSON.stringify({ message, model }),
  });
  await withModel(model, bundle, async (proposal) => {
    const discussion = typeof proposal.discussion === "string" ? proposal.discussion : "";
    await api(`/kc/nodes/${input.nodeId}/model-turn`, {
      method: "POST",
      body: JSON.stringify({ message, discussion, draft: proposal }),
    });
  });
}
