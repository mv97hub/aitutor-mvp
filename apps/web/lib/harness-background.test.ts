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
import { driveRun, type ClaimedChat, type HarnessTransport, type SessionSnap } from "./harness-runner.ts";

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
    prepareTurn: async (_id, _gen, prepared) => prepared,
    dispatchTurn: async () => "send",
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
    prepareTurn: async (_id, _gen, prepared) => prepared,
    dispatchTurn: async () => "send",
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

function flightTransport(onTurn: (id: string) => Promise<void>): HarnessTransport {
  return {
    prepareTurn: async (_id, _gen, prepared) => prepared,
    dispatchTurn: async () => "send",
    runStatus: async () => ({ status: "running" }),
    session: async () => session(),
    speak: async () => session(),
    answer: async () => session({ messages: [{ role: "assistant", content: "Next.", seq: 3 }] }),
    answerKey: async () => ({ block_id: "b1", block_type: "topic_goal" }),
    childText: async () => ({ text: "no", input_tokens: 0, output_tokens: 0, model: "gpt-4.1-mini" }),
    recordTurn: async (id) => {
      await onTurn(id);
      return { stop: "completed", cost_usd: "0", luna_tokens: 0 };
    },
    finish: async () => undefined,
  };
}

test("a claim that fails once still fills the requested concurrency", async () => {
  const want = 4;
  let failures = 0;
  let inFlight = 0;
  let peak = 0;
  const played: string[] = [];
  const queue = ["chat-a", "chat-b", "chat-c", "chat-d"].map((id) => chat(id));
  await driveRun(
    "run-retry",
    async () => {
      if (failures < 1) {
        failures += 1;
        throw new Error("The tutor service is not reachable.");
      }
      return queue.shift() ?? null;
    },
    flightTransport(async (id) => {
      inFlight += 1;
      peak = Math.max(peak, inFlight);
      await new Promise((resolve) => setTimeout(resolve, 200));
      inFlight -= 1;
      played.push(id);
    }),
    want,
  );
  assert.equal(failures, 1);
  assert.equal(peak, want);
  assert.deepEqual(played.sort(), ["chat-a", "chat-b", "chat-c", "chat-d"]);
});

test("a dropped worker is replaced and the run still fills the requested concurrency", async () => {
  const want = 4;
  let inFlight = 0;
  let peak = 0;
  let drops = 0;
  const played: string[] = [];
  const queue = ["chat-a", "chat-b", "chat-c", "chat-d", "chat-e"].map((id) => chat(id));
  await driveRun(
    "run-replace",
    async () => queue.shift() ?? null,
    flightTransport(async (id) => {
      if (id === "chat-a") {
        drops++;
        throw new Error("The turn call failed.");
      }
      inFlight += 1;
      peak = Math.max(peak, inFlight);
      await new Promise((resolve) => setTimeout(resolve, 200));
      inFlight -= 1;
      played.push(id);
    }),
    want,
  );
  assert.equal(drops, 2); // Both attempts failed, so a replacement worker was needed.
  assert.equal(queue.length, 0);
  assert.equal(peak, want);
  assert.equal(played.length, want);
});
