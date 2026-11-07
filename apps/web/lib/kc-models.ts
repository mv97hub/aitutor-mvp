/**
 * Models for the KC chats and the KC Tutor settings menu.
 *
 * The first three are the CreateCourse menu. gpt-4.1 is the capable default.
 * gpt-6.1-sol is the strongest chat model id openai() accepts in
 * @ai-sdk/openai 4.0.106. deepseek/deepseek-flash-latest is called through
 * OpenRouter and does not replace any OpenAI model.
 */
export const DEEPSEEK_FLASH_MODEL = "deepseek/deepseek-flash-latest";

export const KC_MODELS = [
  "gpt-4o-mini",
  "gpt-4o",
  "gpt-4.1-mini",
  "gpt-4.1",
  "gpt-6.1-sol",
  DEEPSEEK_FLASH_MODEL,
] as const;

export type KcModel = (typeof KC_MODELS)[number];

export const DEFAULT_KC_MODEL: KcModel = "gpt-4.1";

export const MISSING_OPENAI_KEY =
  "OPENAI_API_KEY is not set. Copy .env.example to apps/web/.env.local, set OPENAI_API_KEY to your real key, and restart the Next.js server.";

export const MISSING_OPENROUTER_KEY =
  "OPENROUTER_API_KEY is not set. Copy .env.example to apps/web/.env.local, set OPENROUTER_API_KEY to your real key, and restart the Next.js server.";

export function kcModel(value: string | undefined | null): KcModel {
  const cleaned = (value || "").trim();
  return (KC_MODELS as readonly string[]).includes(cleaned) ? (cleaned as KcModel) : DEFAULT_KC_MODEL;
}

export function isKcModel(value: string): value is KcModel {
  return (KC_MODELS as readonly string[]).includes(value);
}

export function usesOpenRouter(model: string): boolean {
  return model === DEEPSEEK_FLASH_MODEL;
}

/** The missing-key error for this model, or null when its own key is set. */
export function missingKeyMessage(model: string): string | null {
  if (usesOpenRouter(model)) {
    return process.env.OPENROUTER_API_KEY?.trim() ? null : MISSING_OPENROUTER_KEY;
  }
  return process.env.OPENAI_API_KEY?.trim() ? null : MISSING_OPENAI_KEY;
}
