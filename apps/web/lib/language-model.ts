import { createOpenAI, openai } from "@ai-sdk/openai";

import { usesOpenRouter } from "@/lib/kc-models";

/** OpenAI models stay on OPENAI_API_KEY. DeepSeek Flash uses OpenRouter chat completions. */
export function languageModel(model: string) {
  if (usesOpenRouter(model)) {
    const openrouter = createOpenAI({
      apiKey: process.env.OPENROUTER_API_KEY,
      baseURL: "https://openrouter.ai/api/v1",
      name: "openrouter",
    });
    return openrouter.chat(model);
  }
  return openai(model);
}
