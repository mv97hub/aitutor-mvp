import type { KcPipeline, KcPipelineStage } from "./kc.ts";

/** Output ceiling for one stage call. A unit is a handful of descriptions, the blueprint is the largest plan. */
export const STAGE_TOKEN_LIMITS: Record<KcPipelineStage, number> = {
  brief: 3000,
  blueprint: 16000,
  unit: 10000,
  review: 16000,
};

/** A stage that the API rejects, or that the model fails to answer, is tried once more with the reason. */
export const STAGE_ATTEMPTS = 2;

export type StageCall = {
  label?: string;
  system_prompt: string;
  user_prompt: string;
  schema: Record<string, unknown>;
};

export type StageBundle = {
  model: string;
  system_prompt: string;
  user_prompt: string;
  schema: Record<string, unknown>;
  /** More than one call means the stage is planned one unit at a time, then combined. */
  calls?: StageCall[];
  combine?: "blueprint" | "review";
};

export type StageRequest = { stage: KcPipelineStage; unit: number | null };

export type StageEvent =
  | { type: "prompt"; label: string; instructions: string; prompt: string }
  | { type: "progress"; label: string; items: number }
  | { type: "retry"; label: string; message: string }
  | { type: "done"; pipeline: KcPipeline }
  | { type: "error"; message: string };

export type GenerateInput = {
  instructions: string;
  prompt: string;
  schema: Record<string, unknown>;
  maxOutputTokens: number;
  onPartial: (partial: unknown) => void;
};

export type StageDeps = {
  bundle: () => Promise<StageBundle>;
  generate: (input: GenerateInput) => Promise<unknown>;
  store: (result: unknown) => Promise<KcPipeline>;
};

const STAGES: readonly string[] = ["brief", "blueprint", "unit", "review"];

export function isStage(value: unknown): value is KcPipelineStage {
  return typeof value === "string" && STAGES.includes(value);
}

export function stageLabel(stage: KcPipelineStage, unit: number | null, total = 0): string {
  if (stage === "brief") return "Brief";
  if (stage === "blueprint") return "Blueprint";
  if (stage === "review") return "Review";
  const number = (unit ?? 0) + 1;
  return total > 0 ? `Unit ${number} of ${total}` : `Unit ${number}`;
}

export function stageTitle(stage: KcPipelineStage, unit: number | null, total = 0): string {
  if (stage === "brief") return "Writing the course brief";
  if (stage === "blueprint") return "Planning the course blueprint";
  if (stage === "review") return "Reviewing the whole course";
  return `Writing ${stageLabel(stage, unit, total).toLowerCase()}`;
}

export class StageError extends Error {
  readonly stage: KcPipelineStage;
  readonly unit: number | null;

  constructor(message: string, request: StageRequest) {
    super(message);
    this.name = "StageError";
    this.stage = request.stage;
    this.unit = request.unit;
  }
}

/** How many components the model has written so far. Shown as streaming progress. */
export function partialItems(partial: unknown): number {
  if (!partial || typeof partial !== "object") return 0;
  const record = partial as Record<string, unknown>;
  if ("units" in record || "unit" in record) {
    const grouped = record.units ?? record.unit;
    const rows = Array.isArray(grouped) ? grouped : grouped && typeof grouped === "object" ? [grouped] : [];
    let items = 0;
    for (const row of rows) {
      if (!row || typeof row !== "object") continue;
      const inner = (row as Record<string, unknown>).components;
      if (Array.isArray(inner)) items += inner.length;
    }
    return items;
  }
  let items = 0;
  for (const value of Object.values(record)) {
    if (Array.isArray(value)) items += value.length;
  }
  return items;
}

/** The streaming line. A blueprint counts components, and a retry says so. */
export function progressLine(label: string, items: number): string {
  if (label.startsWith("Blueprint")) {
    const noun = items === 1 ? "component" : "components";
    return `${label}: ${items} ${noun} so far`;
  }
  return `${label}: ${items} so far`;
}

function noted(prompt: string, note: string): string {
  return note ? `${prompt}\n${note}` : prompt;
}

const REVIEW_CHECKS = ["gaps", "overlap", "jumps", "capstone", "outcomes", "reading_level"];
const REVIEW_RANK: Record<string, number> = { ok: 0, fixed: 1, issue: 2 };

function callsOf(bundle: StageBundle): StageCall[] {
  if (bundle.calls && bundle.calls.length > 1) return bundle.calls;
  return [{ system_prompt: bundle.system_prompt, user_prompt: bundle.user_prompt, schema: bundle.schema }];
}

/** Unit plans from separate calls become one blueprint the store already accepts. */
export function combineBlueprint(parts: unknown[]): { outcomes: string[]; units: unknown[] } {
  const units: unknown[] = [];
  let outcomes: string[] = [];
  for (const part of parts) {
    if (!part || typeof part !== "object") throw new Error("The model reply could not be read.");
    const row = part as Record<string, unknown>;
    if (!outcomes.length && Array.isArray(row.outcomes)) outcomes = row.outcomes.map((item) => String(item));
    if (!row.unit || typeof row.unit !== "object") throw new Error("Each unit needs a title and components.");
    units.push(row.unit);
  }
  if (!units.length) throw new Error("Return at least one unit.");
  return { outcomes, units };
}

/** Per-unit reviews become the one check record the course stores. */
export function combineReview(parts: unknown[]): {
  checks: { name: string; result: string; note: string }[];
  outcomes: unknown;
  revisions: unknown[];
  additions: unknown[];
} {
  const found = new Map<string, { name: string; result: string; note: string }>();
  const revisions: unknown[] = [];
  const additions: unknown[] = [];
  let outcomes: unknown = null;
  for (const part of parts) {
    if (!part || typeof part !== "object") throw new Error("The model reply could not be read.");
    const row = part as Record<string, unknown>;
    if (!Array.isArray(row.checks)) throw new Error("Return every check.");
    for (const item of row.checks) {
      if (!item || typeof item !== "object") continue;
      const check = item as Record<string, unknown>;
      const name = String(check.name || "");
      const result = String(check.result || "");
      if (!REVIEW_CHECKS.includes(name) || !(result in REVIEW_RANK)) continue;
      const note = String(check.note || "").trim();
      const previous = found.get(name);
      if (!previous) {
        found.set(name, { name, result, note });
        continue;
      }
      const winner = REVIEW_RANK[result] > REVIEW_RANK[previous.result] ? result : previous.result;
      found.set(name, { name, result: winner, note: [previous.note, note].filter(Boolean).join(" ") });
    }
    if (Array.isArray(row.revisions)) revisions.push(...row.revisions);
    if (Array.isArray(row.additions)) additions.push(...row.additions);
    if (outcomes == null && Array.isArray(row.outcomes)) outcomes = row.outcomes;
  }
  const missing = REVIEW_CHECKS.filter((name) => !found.has(name));
  if (missing.length) throw new Error(`Return every check. Missing: ${missing.join(", ")}.`);
  return {
    checks: REVIEW_CHECKS.map((name) => found.get(name) as { name: string; result: string; note: string }),
    outcomes,
    revisions,
    additions,
  };
}

function messageOf(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

export function encodeEvent(event: StageEvent): string {
  return `${JSON.stringify(event)}\n`;
}

/**
 * Run one stage: get its prompt, call the model, store the result.
 * A rejected result is tried once more. Nothing outside this stage runs again.
 */
export async function runStage(
  request: StageRequest,
  deps: StageDeps,
  emit: (event: StageEvent) => void,
  total = 0,
): Promise<KcPipeline> {
  const label = stageLabel(request.stage, request.unit, total);
  let bundle: StageBundle;
  try {
    bundle = await deps.bundle();
  } catch (error) {
    throw new StageError(messageOf(error, "The stage could not start."), request);
  }
  let note = "";
  let last = "The model reply could not be read.";
  for (let attempt = 0; attempt < STAGE_ATTEMPTS; attempt += 1) {
    if (attempt > 0) {
      try {
        bundle = await deps.bundle();
      } catch {
        /* Keep the prompt already fetched and attach the corrected rejection below. */
      }
    }
    const calls = callsOf(bundle);
    const split = calls.length > 1;
    try {
      if (!split) {
        const call = calls[0];
        const instructions = noted(call.system_prompt, note);
        emit({ type: "prompt", label: attempt ? `${label} (retry)` : label, instructions, prompt: call.user_prompt });
        const progressLabel = attempt ? `${label} (retry)` : label;
        let seen = 0;
        const result = await deps.generate({
          instructions,
          prompt: call.user_prompt,
          schema: call.schema,
          maxOutputTokens: STAGE_TOKEN_LIMITS[request.stage],
          onPartial: (partial) => {
            const items = partialItems(partial);
            if (items === seen) return;
            seen = items;
            emit({ type: "progress", label: progressLabel, items });
          },
        });
        if (!result || typeof result !== "object") throw new Error("The model reply could not be read.");
        return await deps.store(result);
      }
      const parts: unknown[] = [];
      for (const call of calls) {
        const callLabel = call.label || label;
        const instructions = noted(call.system_prompt, note);
        const progressLabel = attempt ? `${callLabel} (retry)` : callLabel;
        emit({
          type: "prompt",
          label: progressLabel,
          instructions,
          prompt: call.user_prompt,
        });
        let seen = 0;
        const result = await deps.generate({
          instructions,
          prompt: call.user_prompt,
          schema: call.schema,
          maxOutputTokens: STAGE_TOKEN_LIMITS.unit,
          onPartial: (partial) => {
            const items = partialItems(partial);
            if (items === seen) return;
            seen = items;
            emit({ type: "progress", label: progressLabel, items });
          },
        });
        if (!result || typeof result !== "object") throw new Error("The model reply could not be read.");
        parts.push(result);
      }
      const combined = bundle.combine === "review" ? combineReview(parts) : combineBlueprint(parts);
      return await deps.store(combined);
    } catch (error) {
      last = messageOf(error, last);
      if (attempt + 1 < STAGE_ATTEMPTS) {
        emit({ type: "retry", label, message: last });
        note = `The previous reply was rejected. ${last}`;
      }
    }
  }
  throw new StageError(last, request);
}
