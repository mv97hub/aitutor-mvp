/**
 * Models for the KC chats and the KC Tutor settings menu.
 *
 * The first three are the original CreateCourse models. gpt-4.1 is the capable default.
 * gpt-6.1-sol is the strongest chat model id openai() accepts in
 * @ai-sdk/openai 4.0.106. gpt-6-luna is shown as GPT-6 Luna and sent as that
 * id on the same OpenAI path. ~deepseek/deepseek-flash-latest is the OpenRouter
 * alias for DeepSeek Flash. It does not replace any OpenAI model.
 * A saved deepseek/deepseek-flash-latest id is sent as that alias.
 */
export const DEEPSEEK_FLASH_MODEL = "~deepseek/deepseek-flash-latest";

/** OpenRouter rejected this id. Saved rows may still store it. */
export const LEGACY_DEEPSEEK_FLASH_MODEL = "deepseek/deepseek-flash-latest";

export const GPT6_LUNA_MODEL = "gpt-6-luna";
export const GPT6_LUNA_LABEL = "GPT-6 Luna";

export const KC_MODELS = [
  "gpt-4o-mini",
  "gpt-4o",
  "gpt-4.1-mini",
  "gpt-4.1",
  "gpt-6.1-sol",
  GPT6_LUNA_MODEL,
  DEEPSEEK_FLASH_MODEL,
] as const;

export type KcModel = (typeof KC_MODELS)[number];

export const DEFAULT_KC_MODEL: KcModel = "gpt-4.1";

/** CreateCourse menu. It is shorter than KC_MODELS and still includes GPT-6 Luna. */
export const STUDIO_MODELS = [
  "gpt-4o-mini",
  "gpt-4o",
  "gpt-4.1-mini",
  GPT6_LUNA_MODEL,
  DEEPSEEK_FLASH_MODEL,
] as const;

const MODEL_LABELS: Readonly<Record<string, string>> = {
  [GPT6_LUNA_MODEL]: GPT6_LUNA_LABEL,
};

/** Visible menu text. Other models keep their id as the label. */
export function kcModelLabel(id: string): string {
  return MODEL_LABELS[id] ?? id;
}

export const KC_MODEL_OPTIONS: readonly (readonly [KcModel, string])[] = KC_MODELS.map(
  (id) => [id, kcModelLabel(id)] as const,
);

export const MISSING_OPENAI_KEY =
  "OPENAI_API_KEY is not set. Copy .env.example to apps/web/.env.local, set OPENAI_API_KEY to your real key, and restart the Next.js server.";

export const MISSING_OPENROUTER_KEY =
  "OPENROUTER_API_KEY is not set. Copy .env.example to apps/web/.env.local, set OPENROUTER_API_KEY to your real key, and restart the Next.js server.";

/** The id OpenRouter accepts. A saved row may still hold the id without the tilde. */
export function modelForCall(model: string): string {
  const cleaned = model.trim();
  if (cleaned === LEGACY_DEEPSEEK_FLASH_MODEL) return DEEPSEEK_FLASH_MODEL;
  return cleaned;
}

export function kcModel(value: string | undefined | null): KcModel {
  const cleaned = modelForCall(value || "");
  return (KC_MODELS as readonly string[]).includes(cleaned) ? (cleaned as KcModel) : DEFAULT_KC_MODEL;
}

export function isKcModel(value: string): value is KcModel {
  return (KC_MODELS as readonly string[]).includes(value);
}

/** A query or request model, or "" when the caller did not choose one. */
export function explicitKcModel(value: string | undefined | null): KcModel | "" {
  const cleaned = modelForCall(value || "");
  if (!cleaned || !isKcModel(cleaned)) return "";
  return cleaned;
}

export function usesOpenRouter(model: string): boolean {
  return modelForCall(model) === DEEPSEEK_FLASH_MODEL;
}

/** The missing-key error for this model, or null when its own key is set. */
export function missingKeyMessage(model: string): string | null {
  if (usesOpenRouter(model)) {
    return process.env.OPENROUTER_API_KEY?.trim() ? null : MISSING_OPENROUTER_KEY;
  }
  return process.env.OPENAI_API_KEY?.trim() ? null : MISSING_OPENAI_KEY;
}
