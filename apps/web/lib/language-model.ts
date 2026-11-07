import { createOpenAI, openai } from "@ai-sdk/openai";

import { modelForCall, usesOpenRouter } from "@/lib/kc-models";

/** OpenAI models stay on OPENAI_API_KEY. DeepSeek Flash uses OpenRouter chat completions. */
export function languageModel(model: string) {
  const called = modelForCall(model);
  if (usesOpenRouter(called)) {
    const openrouter = createOpenAI({
      apiKey: process.env.OPENROUTER_API_KEY,
      baseURL: "https://openrouter.ai/api/v1",
      name: "openrouter",
    });
    return openrouter.chat(called);
  }
  return openai(called);
}
