/** Cheapest small chat model that can run a short tutor turn. */
export const DEFAULT_OPENAI_MODEL = "gpt-4o-mini";

/** OPENAI_MODEL overrides the default. The same OPENAI_API_KEY is used either way. */
export function openaiModelName(): string {
  const configured = process.env.OPENAI_MODEL?.trim();
  return configured || DEFAULT_OPENAI_MODEL;
}
