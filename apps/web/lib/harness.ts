/** Shared types, prices, and recommendation rules for AI Test Children. */

import { GPT6_LUNA_MODEL, KC_MODELS, type KcModel } from "./kc-models.ts";

export const DEFAULT_CHILD_MODEL: KcModel = "gpt-4.1-mini";
export const DEFAULT_JUDGE_MODEL: KcModel = "gpt-6.1-sol";
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

export const ESTIMATE_TUTOR_CALLS = 32;
export const ESTIMATE_TUTOR_INPUT = 2700;
export const ESTIMATE_TUTOR_OUTPUT = 180;
export const ESTIMATE_CHILD_CALLS = 12;
export const ESTIMATE_CHILD_INPUT = 400;
export const ESTIMATE_CHILD_OUTPUT = 40;
export const ESTIMATE_JUDGE_INPUT = 4000;
export const ESTIMATE_JUDGE_OUTPUT = 600;

export function estimateChatUsd(tutorModel: string, childModel: string, judgeModel: string): {
  usd: string | null;
  unpriced: string[];
} {
  const parts = [
    { model: tutorModel, calls: ESTIMATE_TUTOR_CALLS, input: ESTIMATE_TUTOR_INPUT, output: ESTIMATE_TUTOR_OUTPUT },
    { model: childModel, calls: ESTIMATE_CHILD_CALLS, input: ESTIMATE_CHILD_INPUT, output: ESTIMATE_CHILD_OUTPUT },
    { model: judgeModel, calls: 1, input: ESTIMATE_JUDGE_INPUT, output: ESTIMATE_JUDGE_OUTPUT },
  ];
  let total = 0;
  let priced = false;
  const unpriced: string[] = [];
  for (const part of parts) {
    const one = costUsd(part.model, part.input, 0, part.output);
    if (one == null) {
      if (!unpriced.includes(part.model)) unpriced.push(part.model);
      continue;
    }
    priced = true;
    total += Number(one) * part.calls;
  }
  return { usd: priced ? trimMoney(total) : null, unpriced };
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

export type RecommendationCard = {
  title: string;
  evidence?: { summary?: string; count?: number; block_type?: string };
  block_type?: string;
  cause_class?: string;
  place?: string;
  proposed?: Record<string, unknown>;
  prompt_direction: "shorter" | "longer" | "same";
  kind: "setting" | "reword" | "remove" | "add";
  risk?: string;
  confidence?: string;
};

export function ensureSimplification(cards: RecommendationCard[]): RecommendationCard[] {
  if (cards.some((card) => card.kind === "remove" || (card.kind === "reword" && card.prompt_direction === "shorter"))) {
    return cards;
  }
  return [
    ...cards,
    {
      title: "Shorten a rule instead of adding one",
      kind: "remove",
      prompt_direction: "shorter",
      cause_class: "prompt",
      place: "Drop or shorten the line that already covers this finding before adding another.",
      proposed: { text: "Remove the overlapping sentence from the stored prompt." },
      risk: "A shorter prompt can drop a reminder the model was using.",
      confidence: "medium",
      evidence: { summary: "The drafter only proposed additions. A cut is required before the batch is complete." },
    },
  ];
}

export function keptRunIds(suites: { baseline_run_id?: string | null; run_ids: string[] }[]): string[] {
  const kept = new Set<string>();
  for (const suite of suites) {
    if (suite.baseline_run_id) kept.add(suite.baseline_run_id);
    const latest = suite.run_ids[suite.run_ids.length - 1];
    if (latest) kept.add(latest);
  }
  return [...kept];
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
