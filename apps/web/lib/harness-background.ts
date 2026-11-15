/** Chats in flight for one run. The loop stays in this process after the page returns. */

import { driveRun, type ClaimedChat, type HarnessTransport } from "./harness-runner.ts";

type Active = { aborted: boolean };

const active = new Map<string, Active>();

export function backgroundRunActive(runId: string): boolean {
  return active.has(runId);
}

/** Reserve the run before any await, so a second start does not open another loop. */
export function beginBackgroundRun(runId: string): Active | null {
  if (active.has(runId)) return null;
  const signal: Active = { aborted: false };
  active.set(runId, signal);
  return signal;
}

export function finishBackgroundRun(runId: string, signal: Active): void {
  if (active.get(runId) === signal) active.delete(runId);
}

export function stopBackgroundRun(runId: string): void {
  const signal = active.get(runId);
  if (signal) signal.aborted = true;
}

export function clampConcurrency(value: unknown): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return 1;
  return Math.max(1, Math.min(8, Math.floor(parsed)));
}

export type StatusChat = { status?: string; ended_how?: string };

/** Counts the page can show from the stored run, with the tab closed. */
export function runStatusLine(chats: StatusChat[]): string {
  let queued = 0;
  let running = 0;
  let finished = 0;
  let stuck = 0;
  let turnLimit = 0;
  for (const chat of chats) {
    if (chat.status === "queued") queued += 1;
    else if (chat.status === "running") running += 1;
    else if (chat.status === "completed" || chat.status === "failed" || chat.status === "cancelled") finished += 1;
    if (chat.ended_how === "stuck") stuck += 1;
    if (chat.ended_how === "turn_limit") turnLimit += 1;
  }
  return `Queued ${queued} · Running ${running} · Finished ${finished} · Stuck ${stuck} · Turn limit ${turnLimit}`;
}

export function launchBackgroundRun(input: {
  runId: string;
  signal: Active;
  concurrency: number;
  claim: () => Promise<ClaimedChat | null>;
  transport: HarnessTransport;
}): void {
  const concurrency = clampConcurrency(input.concurrency);
  void driveRun(input.runId, input.claim, input.transport, concurrency, input.signal)
    .catch(() => undefined)
    .finally(() => finishBackgroundRun(input.runId, input.signal));
}
