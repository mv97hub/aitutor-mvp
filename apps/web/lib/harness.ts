/** Shared types and prices for AI Test Children. */

import { GPT6_LUNA_MODEL, KC_MODELS, type KcModel } from "./kc-models.ts";

export const DEFAULT_CHILD_MODEL: KcModel = "gpt-4.1-mini";

export type HarnessPersona = {
  id: string;
  number: number;
  name: string;
  description: string;
  age: number;
  child_profile: Record<string, string | string[]>;
  traits: Record<string, number>;
  archived?: boolean;
};
export const DEFAULT_CHAT_CAP_CENTS = 40;
export const DEFAULT_TURN_LIMIT = 40;
export const DEFAULT_STUCK_LIMIT = 8;
export const DEFAULT_CONCURRENCY = 3;
export const DEFAULT_LUNA_TOKEN_CEILING = 100_000;

/** Mirrors apps/api/app/token_usage.py. gpt-6-luna is absent on purpose. */
export const MODEL_TOKEN_PRICES: Record<string, { input: number; cached: number; output: number }> = {
  "gpt-4o-mini": { input: 0.15, cached: 0.075, output: 0.6 },
  "gpt-4o": { input: 2.5, cached: 1.25, output: 10 },
  "gpt-4.1-mini": { input: 0.4, cached: 0.1, output: 1.6 },
  "gpt-4.1": { input: 2, cached: 0.5, output: 8 },
  "gpt-6.1-sol": { input: 2, cached: 0.1, output: 10 },
  "~deepseek/deepseek-flash-latest": { input: 0.022, cached: 0.004, output: 0.4 },
  "deepseek/deepseek-flash-latest": { input: 0.022, cached: 0.004, output: 0.4 },
};

export const HARNESS_MODELS: readonly KcModel[] = KC_MODELS;

export function costUsd(model: string, inputTokens: number, cachedTokens: number, outputTokens: number): string | null {
  const rates = MODEL_TOKEN_PRICES[model];
  if (!rates) return null;
  const cached = Math.min(Math.max(0, cachedTokens), Math.max(0, inputTokens));
  const amount =
    ((inputTokens - cached) * rates.input + cached * rates.cached + outputTokens * rates.output) / 1_000_000;
  return trimMoney(amount);
}

function trimMoney(amount: number): string {
  const text = amount.toFixed(8).replace(/0+$/, "").replace(/\.$/, "");
  return text || "0";
}

/** Children and New run show this list. Archived children stay off it. */
export function listedTestChildren<T extends { archived?: boolean }>(personas: T[]): T[] {
  return personas.filter((persona) => !persona.archived);
}

export function chatCount(input: {
  children: number;
  components: number;
  models: number;
  profiles: number;
  iterations: number;
}): number {
  return input.children * input.components * Math.max(1, input.models) * Math.max(1, input.profiles) * input.iterations;
}

export function sameModelWarning(childModel: string, tutorModels: string[]): boolean {
  return tutorModels.includes(childModel);
}

export function lunaNote(model: string): string | null {
  if (model !== GPT6_LUNA_MODEL) return null;
  return "GPT-6 Luna has no published price. Its calls show a blank cost. The spending cap does not cover them. They stop at the token ceiling.";
}

export const TRAIT_FIELDS: { key: string; label: string; low: string; high: string }[] = [
  { key: "maturity", label: "Maturity", low: "Little patience for their age.", high: "Patient and polite for their age." },
  { key: "attention", label: "Attention span", low: "Drifts after a short tutor message.", high: "Stays with a long explanation." },
  { key: "curiosity", label: "Curiosity", low: "Rarely asks anything.", high: "Often asks why, or presses Tell me more." },
  { key: "boredom", label: "Propensity for boredom", low: "Boredom builds slowly.", high: "Gets bored fast and goes short, off topic, or quits." },
  { key: "prior_knowledge", label: "Prior knowledge", low: "Often wrong on the first try.", high: "Often right on the first try." },
  { key: "learning_rate", label: "Learning rate", low: "A hint barely helps.", high: "A hint or explanation raises the chance of a right answer." },
  { key: "reading", label: "Actual reading ability", low: "Long or wordy messages cause what? and misreads.", high: "Reads the tutor's message as written." },
  { key: "writing", label: "Writing style", low: "Very short, with spelling slips.", high: "A clear sentence with normal punctuation." },
  { key: "compliance", label: "Compliance", low: "Resists and negotiates.", high: "Does what is asked." },
  { key: "tangent", label: "Tangent rate", low: "Stays on the question.", high: "Side stories and unrelated remarks." },
  { key: "when_unsure", label: "When unsure", low: "Guesses.", high: "Asks for the answer." },
  { key: "wrong_pattern", label: "Wrong-answer pattern", low: "Uses a stored misconception.", high: "Right idea, imperfect words." },
  { key: "frustration", label: "Frustration tolerance", low: "Mistakes land hard.", high: "Shrugs a mistake off." },
  { key: "buttons", label: "Buttons versus typing", low: "Types when both are offered.", high: "Presses the button." },
  { key: "echoing", label: "Agreeing and echoing", low: "Answers in their own words.", high: "Says yes or repeats the tutor." },
  { key: "boundary", label: "Boundary testing", low: "Stays in the lesson.", high: "Silly, personal, or tries to pull the tutor off its role." },
  { key: "quit", label: "Quit point", low: "Leaves when boredom or frustration is still low.", high: "Stays until boredom or frustration is high." },
];

export function traitSentence(field: { low: string; high: string }, value: number): string {
  if (value <= 2) return field.low;
  if (value >= 4) return field.high;
  return "Around the middle of this scale.";
}
