import { Output, jsonSchema, streamText, type JSONSchema7 } from "ai";

import { languageModel } from "@/lib/language-model";
import { isKcModel, missingKeyMessage, modelForCall, usesOpenRouter, type KcModel } from "@/lib/kc-models";
import type { GenerateInput } from "@/lib/kc-stage";

export function checkedStageModel(value: string): KcModel {
  const called = modelForCall(value);
  if (!isKcModel(called)) throw new Error("That model is not allowed.");
  const missing = missingKeyMessage(called);
  if (missing) throw new Error(missing);
  return called;
}

/** One streamed object call. Partial objects go to `onPartial` while the model writes. */
export async function generateStageObject(
  model: KcModel,
  input: GenerateInput,
  abortSignal?: AbortSignal,
): Promise<unknown> {
  const result = streamText({
    model: languageModel(model),
    output: Output.object({
      schema: jsonSchema(input.schema as JSONSchema7),
      name: "kc_course_stage",
      description: "One stage of a course draft. No web search.",
    }),
    instructions: input.instructions,
    prompt: input.prompt,
    maxOutputTokens: input.maxOutputTokens,
    abortSignal,
    ...(model.startsWith("gpt-4") || usesOpenRouter(model) ? { temperature: 0.3 } : {}),
  });
  for await (const partial of result.partialOutputStream) {
    input.onPartial(partial);
  }
  return await result.output;
}
