import assert from "node:assert/strict";
import test from "node:test";

import {
  beginBackgroundRun,
  clampConcurrency,
  finishBackgroundRun,
  launchBackgroundRun,
  runStatusLine,
  stopBackgroundRun,
} from "./harness-background.ts";
import type { ClaimedChat, HarnessTransport, SessionSnap } from "./harness-runner.ts";

function session(overrides: Partial<SessionSnap> = {}): SessionSnap {
  return {
    id: "session-1",
    status: "in_progress",
    needs_speech: false,
    messages: [{ role: "assistant", content: "What color is the river?", seq: 1 } as SessionSnap["messages"][number]],
    ...overrides,
  };
}

function chat(id: string): ClaimedChat {
  return {
    id,
    session_id: "session-1",
    tutor_model: "gpt-4.1-mini",
    child_model: "gpt-4.1-mini",
    behavior: "script",
    seed: 1,
    script: ["blue", "again"],
    child: { description: "Steady", traits: {} },
  };
}

test("status counts queued, running, finished, stuck, and the turn limit", () => {
  const line = runStatusLine([
    { status: "queued" },
    { status: "running" },
    { status: "completed", ended_how: "completed" },
    { status: "completed", ended_how: "stuck" },
    { status: "completed", ended_how: "turn_limit" },
    { status: "cancelled", ended_how: "cancelled" },
  ]);
  assert.equal(line, "Queued 1 · Running 1 · Finished 4 · Stuck 1 · Turn limit 1");
});

test("concurrency stays inside 1 to 8", () => {
  assert.equal(clampConcurrency(undefined), 1);
  assert.equal(clampConcurrency(0), 1);
  assert.equal(clampConcurrency(3.8), 3);
  assert.equal(clampConcurrency(20), 8);
});

test("a second start does not open another loop", () => {
  const first = beginBackgroundRun("run-once");
  const second = beginBackgroundRun("run-once");
  assert.ok(first);
  assert.equal(second, null);
  finishBackgroundRun("run-once", first!);
});

test("chats run side by side, and one chat takes its turns one at a time", async () => {
  const runId = "run-flight";
  const signal = beginBackgroundRun(runId);
  assert.ok(signal);
  const busy = new Set<string>();
  const turns: Record<string, number> = {};
  let answers = 0;
  let speaks = 0;
  let childCalls = 0;
  let inFlight = 0;
  let peak = 0;
  const transport: HarnessTransport = {
    runStatus: async () => ({ status: "running" }),
    session: async () => session(),
    speak: async () => {
      speaks += 1;
      return session();
    },
    answer: async () => {
      answers += 1;
      return session({ messages: [{ role: "assistant", content: "Next.", seq: 3 }] });
    },
    answerKey: async () => ({ block_id: "b1", block_type: "topic_goal" }),
    childText: async () => {
      childCalls += 1;
      return { text: "no", input_tokens: 0, output_tokens: 0, model: "gpt-4.1-mini" };
    },
    recordTurn: async (id) => {
      assert.equal(busy.has(id), false);
      busy.add(id);
      inFlight += 1;
      peak = Math.max(peak, inFlight);
      await new Promise((resolve) => setTimeout(resolve, 30));
      inFlight -= 1;
      busy.delete(id);
      turns[id] = (turns[id] || 0) + 1;
      return { stop: turns[id] >= 2 ? "completed" : "", cost_usd: "0", luna_tokens: 0 };
    },
    finish: async () => undefined,
  };
  const queue = [chat("chat-a"), chat("chat-b")];
  launchBackgroundRun({
    runId,
    signal: signal!,
    concurrency: 2,
    claim: async () => queue.shift() ?? null,
    transport,
  });
  await new Promise((resolve) => setTimeout(resolve, 400));
  assert.equal(speaks, 0);
  assert.equal(childCalls, 0);
  assert.equal(answers, 4);
  assert.equal(peak, 2);
  assert.deepEqual(turns, { "chat-a": 2, "chat-b": 2 });
});

test("stop ends the loop before another chat is claimed", async () => {
  const runId = "run-stop";
  const signal = beginBackgroundRun(runId);
  assert.ok(signal);
  let claims = 0;
  let answers = 0;
  const transport: HarnessTransport = {
    runStatus: async () => ({ status: "running" }),
    session: async () => session({ status: "completed", messages: [] }),
    speak: async () => session(),
    answer: async () => {
      answers += 1;
      return session();
    },
    answerKey: async () => ({}),
    childText: async () => ({ text: "no", input_tokens: 0, output_tokens: 0, model: "" }),
    recordTurn: async () => ({ stop: "", cost_usd: null, luna_tokens: 0 }),
    finish: async () => undefined,
  };
  launchBackgroundRun({
    runId,
    signal: signal!,
    concurrency: 1,
    claim: async () => {
      claims += 1;
      stopBackgroundRun(runId);
      return chat("chat-stopped");
    },
    transport,
  });
  await new Promise((resolve) => setTimeout(resolve, 50));
  assert.equal(claims, 1);
  assert.equal(answers, 0);
});
