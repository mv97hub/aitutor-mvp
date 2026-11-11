import assert from "node:assert/strict";
import test from "node:test";

import { api } from "./api.ts";

test("a stuck server fetch becomes the tutor error", async () => {
  const original = globalThis.fetch;
  let sawSignal = false;
  globalThis.fetch = (async (_input: unknown, init?: RequestInit) => {
    sawSignal = Boolean(init?.signal);
    const err = new Error("timed out");
    err.name = "TimeoutError";
    throw err;
  }) as typeof fetch;
  try {
    await assert.rejects(api("/kc/tutor/learners"), /The tutor service is not reachable\./);
    assert.equal(sawSignal, true);
  } finally {
    globalThis.fetch = original;
  }
});

test("a browser fetch does not add a timeout", async () => {
  const original = globalThis.fetch;
  const globalRecord = globalThis as { window?: unknown };
  const hadWindow = Object.prototype.hasOwnProperty.call(globalRecord, "window");
  const previous = globalRecord.window;
  globalRecord.window = {};
  let signal: AbortSignal | null | undefined;
  globalThis.fetch = (async (_input: unknown, init?: RequestInit) => {
    signal = init?.signal;
    return new Response("[]", { status: 200 });
  }) as typeof fetch;
  try {
    assert.deepEqual(await api<unknown[]>("/kc/tutor/learners"), []);
    assert.equal(signal, undefined);
  } finally {
    globalThis.fetch = original;
    if (hadWindow) globalRecord.window = previous;
    else delete globalRecord.window;
  }
});
