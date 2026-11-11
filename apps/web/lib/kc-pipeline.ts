import type { KcPipeline, KcPipelineNext } from "./kc.ts";
import { stageTitle, type StageEvent, type StageRequest } from "./kc-stage.ts";

export class PipelineStageError extends Error {
  readonly request: StageRequest;

  constructor(message: string, request: StageRequest) {
    super(message);
    this.name = "PipelineStageError";
    this.request = request;
  }
}

export type RunStage = (request: StageRequest, onEvent: (event: StageEvent) => void) => Promise<KcPipeline>;

export function requestOf(next: KcPipelineNext): StageRequest | null {
  return next ? { stage: next.stage, unit: next.unit } : null;
}

/** The line shown while a stage runs, or null when the draft waits for the user. */
export function workingText(state: KcPipeline): string | null {
  const next = requestOf(state.next);
  if (!next) return null;
  return `${stageTitle(next.stage, next.unit, state.units_total)}…`;
}

/**
 * Run stages one after another until the draft needs the user.
 * Every stage is stored on the server, so a failure leaves the last stored state in place:
 * calling this again with that state reruns only the stage that failed.
 */
export async function runPipeline(
  state: KcPipeline,
  run: RunStage,
  onState: (state: KcPipeline) => void,
  onEvent: (event: StageEvent) => void = () => {},
  cancelled: () => boolean = () => false,
): Promise<KcPipeline> {
  let current = state;
  for (;;) {
    const request = requestOf(current.next);
    if (!request || cancelled()) return current;
    current = await run({ ...request }, onEvent);
    onState(current);
  }
}

export async function* readEvents(body: ReadableStream<Uint8Array>): AsyncGenerator<StageEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let newline = buffer.indexOf("\n");
      while (newline >= 0) {
        const line = buffer.slice(0, newline).trim();
        buffer = buffer.slice(newline + 1);
        if (line) yield JSON.parse(line) as StageEvent;
        newline = buffer.indexOf("\n");
      }
      if (done) break;
    }
    const rest = buffer.trim();
    if (rest) yield JSON.parse(rest) as StageEvent;
  } finally {
    reader.releaseLock();
  }
}

const ROUTE = "/api/kc/course-draft";

async function errorText(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { error?: string };
    if (body.error) return body.error;
  } catch {
    /* Not JSON. */
  }
  return `The request failed (${response.status}).`;
}

/** Call the streaming route for one stage and pass its events on. */
export function stageRunner(courseId: string, model: string, unitsTotal: () => number, signal?: AbortSignal): RunStage {
  return async (request, onEvent) => {
    let response: Response;
    try {
      response = await fetch(ROUTE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "stage",
          course_id: courseId,
          stage: request.stage,
          unit: request.unit,
          units_total: unitsTotal(),
          model,
        }),
        signal,
      });
    } catch (error) {
      throw new PipelineStageError(error instanceof Error ? error.message : "The request failed.", request);
    }
    if (!response.ok || !response.body) throw new PipelineStageError(await errorText(response), request);
    let done: KcPipeline | null = null;
    for await (const event of readEvents(response.body)) {
      if (event.type === "error") throw new PipelineStageError(event.message, request);
      if (event.type === "done") done = event.pipeline;
      else onEvent(event);
    }
    if (!done) throw new PipelineStageError("The stream ended before the stage finished.", request);
    return done;
  };
}

export async function pipelineAction(
  courseId: string,
  action: "answers" | "blueprint" | "reset",
  payload: Record<string, unknown> = {},
): Promise<KcPipeline> {
  const response = await fetch(ROUTE, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, course_id: courseId, ...payload }),
  });
  if (!response.ok) throw new Error(await errorText(response));
  return ((await response.json()) as { pipeline: KcPipeline }).pipeline;
}
