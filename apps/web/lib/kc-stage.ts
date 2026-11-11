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

export type StageBundle = {
  model: string;
  system_prompt: string;
  user_prompt: string;
  schema: Record<string, unknown>;
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

/** How many rows of the main list the model has written so far. Shown as streaming progress. */
export function partialItems(partial: unknown): number {
  if (!partial || typeof partial !== "object") return 0;
  let items = 0;
  for (const value of Object.values(partial as Record<string, unknown>)) {
    if (!Array.isArray(value)) continue;
    for (const row of value) {
      items += 1;
      if (row && typeof row === "object") {
        const inner = (row as Record<string, unknown>).components;
        if (Array.isArray(inner)) items += inner.length;
      }
    }
  }
  return items;
}

function noted(prompt: string, note: string): string {
  return note ? `${prompt}\n${note}` : prompt;
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
    const instructions = noted(bundle.system_prompt, note);
    emit({ type: "prompt", label: attempt ? `${label} (retry)` : label, instructions, prompt: bundle.user_prompt });
    let seen = 0;
    try {
      const result = await deps.generate({
        instructions,
        prompt: bundle.user_prompt,
        schema: bundle.schema,
        maxOutputTokens: STAGE_TOKEN_LIMITS[request.stage],
        onPartial: (partial) => {
          const items = partialItems(partial);
          if (items === seen) return;
          seen = items;
          emit({ type: "progress", label, items });
        },
      });
      if (!result || typeof result !== "object") throw new Error("The model reply could not be read.");
      return await deps.store(result);
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
