import assert from "node:assert/strict";
import test from "node:test";

import type { ClaimedChat, HarnessTransport, SessionSnap } from "./harness-runner.ts";
import { playChat } from "./harness-runner.ts";

function session(overrides: Partial<SessionSnap> = {}): SessionSnap {
  return {
    id: "session-1",
    status: "in_progress",
    needs_speech: false,
    active_block_type: "topic_goal",
    active_substep: "main",
    messages: [{ role: "assistant", content: "What color is the river?" }],
    ...overrides,
  };
}

function chat(): ClaimedChat {
  return {
    id: "chat-1",
    session_id: "session-1",
    tutor_model: "gpt-4.1-mini",
    child_model: "gpt-4.1-mini",
    behavior: "script",
    seed: 1,
    script: ["the river is blue"],
    child: { description: "Steady", traits: { quit: 5, boundary: 1, echoing: 1, compliance: 3, writing: 3 } },
  };
}

test("a chat stops when the server reports the spending cap", async () => {
  const calls: string[] = [];
  const transport: HarnessTransport = {
    runStatus: async () => ({ status: "running" }),
    session: async () => session(),
    speak: async () => session(),
    answer: async () => session({ status: "in_progress", messages: [{ role: "assistant", content: "Say a bit more." }] }),
    answerKey: async () => ({ expected: "blue", block_id: "blk", move_attempts: 0 }),
    childText: async () => {
      throw new Error("script mode should not call the child model");
    },
    recordTurn: async (_id, body) => {
      calls.push(String(body.child_text));
      return { stop: "cap", cost_usd: "0.4", luna_tokens: 0 };
    },
    finish: async () => {
      calls.push("finish");
    },
  };
  const result = await playChat(chat(), transport);
  assert.equal(result, "done");
  assert.deepEqual(calls, ["the river is blue"]);
});

test("two tutor failures in a row close the chat", async () => {
  let finished = "";
  const transport: HarnessTransport = {
    runStatus: async () => ({ status: "running" }),
    session: async () => session({ needs_speech: true, messages: [] }),
    speak: async () => {
      throw new Error("down");
    },
    answer: async () => session(),
    answerKey: async () => ({}),
    childText: async () => ({ text: "ok", input_tokens: 0, output_tokens: 0, model: "gpt-4.1-mini" }),
    recordTurn: async () => ({ stop: "", cost_usd: "0", luna_tokens: 0 }),
    finish: async (_id, reason) => {
      finished = reason;
    },
  };
  const result = await playChat(chat(), transport);
  assert.equal(result, "done");
  assert.equal(finished, "route_error");
});

test("a model turn stores the child prompt, and a scripted line does not", async () => {
  const recorded: { child_prompt?: string; child_text?: string }[] = [];
  const transport: HarnessTransport = {
    runStatus: async () => ({ status: "running" }),
    session: async () => session(),
    speak: async () => session(),
    answer: async () => session({ status: "completed" }),
    answerKey: async () => ({ expected: "blue" }),
    childText: async () => ({
      text: "the river is blue",
      prompt: "You are the test child.",
      input_tokens: 20,
      output_tokens: 5,
      model: "gpt-4.1-mini",
    }),
    recordTurn: async (_id, body) => {
      recorded.push({ child_prompt: String(body.child_prompt || ""), child_text: String(body.child_text || "") });
      return { stop: "completed", cost_usd: "0", luna_tokens: 0 };
    },
    finish: async () => undefined,
  };
  const free = chat();
  free.behavior = "free";
  await playChat(free, transport);
  assert.equal(recorded[0]?.child_prompt, "You are the test child.");
  recorded.length = 0;
  await playChat(chat(), transport);
  assert.equal(recorded[0]?.child_text, "the river is blue");
  assert.equal(recorded[0]?.child_prompt, "");
});

test("a paused run leaves the chat for resume", async () => {
  const transport: HarnessTransport = {
    runStatus: async () => ({ status: "paused" }),
    session: async () => session(),
    speak: async () => session(),
    answer: async () => session(),
    answerKey: async () => ({}),
    childText: async () => ({ text: "ok", input_tokens: 0, output_tokens: 0, model: "gpt-4.1-mini" }),
    recordTurn: async () => ({ stop: "", cost_usd: "0", luna_tokens: 0 }),
    finish: async () => {
      throw new Error("should not finish");
    },
  };
  assert.equal(await playChat(chat(), transport), "paused");
});

test("eight same-place turns are followed by two nudges, then stuck", async () => {
  const childLines: string[] = [];
  const intents: string[] = [];
  const live: string[] = [];
  const answered: string[] = [];
  let pending = 0;
  const transport: HarnessTransport = {
    runStatus: async () => ({ status: "running" }),
    session: async () => session({ block_id: "b1", active_substep: "explain", active_block_type: "topic_goal" }),
    speak: async () => session(),
    answer: async (_id, text) => {
      answered.push(text);
      return session({
        block_id: "b1",
        active_substep: "explain",
        active_block_type: "topic_goal",
        messages: [
          { role: "user", content: text },
          { role: "assistant", content: `Still on explain after ${text}` },
        ],
      });
    },
    answerKey: async () => ({ block_id: "b1", block_type: "topic_goal", move_attempts: 0 }),
    childText: async () => {
      throw new Error("a nudge does not call the child model");
    },
    recordTurn: async (_id, body) => {
      childLines.push(String(body.child_text));
      intents.push(String(body.intent));
      const after = body.session_after as { block_id?: string; block_type?: string; substep?: string; tutor_reply?: string };
      assert.equal(after.block_id, "b1");
      assert.equal(after.block_type, "topic_goal");
      assert.equal(after.substep, "explain");
      assert.match(String(after.tutor_reply), /Still on explain/);
      if (childLines.length === 1) pending = 2;
      else if (pending > 0) pending -= 1;
      return { stop: pending === 0 && childLines.length > 1 ? "stuck" : "", pending_nudges: pending, cost_usd: "0", luna_tokens: 0 };
    },
    finish: async () => undefined,
  };
  const result = await playChat(chat(), transport, undefined, (line) => {
    if (line.role === "child") live.push(line.text);
  });
  assert.equal(result, "done");
  assert.deepEqual(childLines, ["the river is blue", "What's next?", "What should we do next?"]);
  assert.deepEqual(intents.slice(1), ["nudge", "nudge"]);
  assert.deepEqual(answered.slice(1), ["What's next?", "What should we do next?"]);
  assert.ok(live.includes("What's next?"));
  assert.ok(live.includes("What should we do next?"));
});

test("a nudge that moves the block does not send the second nudge", async () => {
  const childLines: string[] = [];
  let calls = 0;
  const moving = chat();
  moving.script = ["one", "two", "three"];
  const transport: HarnessTransport = {
    runStatus: async () => ({ status: "running" }),
    session: async () => session(),
    speak: async () => session(),
    answer: async (_id, text) =>
      session({
        status: calls >= 2 ? "completed" : "in_progress",
        block_id: text === "What's next?" ? "b2" : "b1",
        active_substep: text === "What's next?" ? "ask" : "explain",
        messages: [{ role: "assistant", content: "Next step." }],
      }),
    answerKey: async () => ({ block_id: "b1", block_type: "topic_goal" }),
    childText: async () => ({ text: "unused", input_tokens: 0, output_tokens: 0, model: "gpt-4.1-mini" }),
    recordTurn: async (_id, body) => {
      calls += 1;
      childLines.push(String(body.child_text));
      if (calls === 1) return { stop: "", pending_nudges: 2, cost_usd: "0", luna_tokens: 0 };
      return { stop: "", pending_nudges: 0, cost_usd: "0", luna_tokens: 0 };
    },
    finish: async () => undefined,
  };
  await playChat(moving, transport);
  assert.equal(childLines[0], "one");
  assert.equal(childLines[1], "What's next?");
  assert.notEqual(childLines[2], "What should we do next?");
});

test("a refresh resumes the remaining nudge instead of repeating the first", async () => {
  const childLines: string[] = [];
  const resumed = chat();
  resumed.pending_nudges = 1;
  const transport: HarnessTransport = {
    runStatus: async () => ({ status: "running" }),
    session: async () => session(),
    speak: async () => session(),
    answer: async () => session({ status: "completed", messages: [{ role: "assistant", content: "Still here." }] }),
    answerKey: async () => ({ block_id: "b1", block_type: "topic_goal" }),
    childText: async () => {
      throw new Error("a resumed nudge does not call the child model");
    },
    recordTurn: async (_id, body) => {
      childLines.push(String(body.child_text));
      assert.equal(body.intent, "nudge");
      return { stop: "stuck", pending_nudges: 0, cost_usd: "0", luna_tokens: 0 };
    },
    finish: async () => undefined,
  };
  await playChat(resumed, transport);
  assert.deepEqual(childLines, ["What should we do next?"]);
});
