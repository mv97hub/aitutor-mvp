import { Output, jsonSchema, streamText, type JSONSchema7 } from "ai";

import { api } from "@/lib/api";
import { languageModel } from "@/lib/language-model";
import { isKcModel, missingKeyMessage, modelForCall, usesOpenRouter, type KcModel } from "@/lib/kc-models";
import { KcDraftError, releaseRecord, type SentPrompt } from "@/lib/kc-prompt-log";

type PromptBundle = {
  model: string;
  system_prompt: string;
  user_prompt: string;
  schema: JSONSchema7;
};

function requireKey(model: string) {
  const missing = missingKeyMessage(model);
  if (missing) throw new Error(missing);
}

function requireModel(model: string): KcModel {
  const called = modelForCall(model);
  if (!isKcModel(called)) {
    throw new Error("That model is not allowed.");
  }
  return called;
}

async function completeObject(
  model: KcModel,
  instructions: string,
  prompt: string,
  schema: JSONSchema7,
  sent: SentPrompt[],
  label: string,
) {
  sent.push({ label, instructions, prompt });
  const output = await streamText({
    model: languageModel(model),
    output: Output.object({
      schema: jsonSchema(schema),
      name: "kc_draft",
      description: "A curriculum draft. No web search.",
    }),
    instructions,
    prompt,
    ...(model.startsWith("gpt-4") || usesOpenRouter(model) ? { temperature: 0.3 } : {}),
  }).output;
  if (!output || typeof output !== "object") {
    throw new Error("The model reply could not be read.");
  }
  return output as Record<string, unknown>;
}

async function withModel<T>(
  model: KcModel,
  bundle: PromptBundle,
  finish: (proposal: Record<string, unknown>) => Promise<T>,
  sent: SentPrompt[],
  label: string,
): Promise<T> {
  let note = "";
  let last = "The model reply could not be read.";
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      const proposal = await completeObject(
        model,
        noted(bundle.system_prompt, note),
        bundle.user_prompt,
        bundle.schema,
        sent,
        label,
      );
      try {
        return await finish(proposal);
      } finally {
        releaseRecord(proposal);
      }
    } catch (error) {
      last = error instanceof Error ? error.message : last;
      note = `The previous reply was rejected. ${last}`;
    }
  }
  throw new KcDraftError(last, sent);
}

function noted(prompt: string, note: string) {
  return note ? `${prompt}\n${note}` : prompt;
}

function scopeBody(allowedBlockTypes?: string[]) {
  return allowedBlockTypes && allowedBlockTypes.length ? { allowed_block_types: allowedBlockTypes } : {};
}

export async function draftKcComponent(input: {
  nodeId: string;
  message: string;
  model: string;
  allowedBlockTypes?: string[];
}): Promise<SentPrompt[]> {
  const model = requireModel(input.model);
  requireKey(model);
  const message = input.message.trim();
  if (!message) throw new Error("Write a message first.");
  const sent: SentPrompt[] = [];
  const bundle = await api<PromptBundle>(`/kc/nodes/${input.nodeId}/creator-prompt`, {
    method: "POST",
    body: JSON.stringify({ message, model, ...scopeBody(input.allowedBlockTypes) }),
  });
  await withModel(
    model,
    bundle,
    async (proposal) => {
      const discussion = typeof proposal.discussion === "string" ? proposal.discussion : "";
      await api(`/kc/nodes/${input.nodeId}/model-turn`, {
        method: "POST",
        body: JSON.stringify({ message, discussion, draft: proposal, ...scopeBody(input.allowedBlockTypes) }),
      });
    },
    sent,
    "Draft",
  );
  return sent;
}
