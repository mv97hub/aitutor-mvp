import assert from "node:assert/strict";
import test from "node:test";

import type { ClaimedChat, HarnessTransport, SessionSnap } from "./harness-runner.ts";
import { claimStillOwns, placeKey, playChat } from "./harness-runner.ts";

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
    prepareTurn: async (_id, _gen, prepared) => prepared,
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
    prepareTurn: async (_id, _gen, prepared) => prepared,
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
    prepareTurn: async (_id, _gen, prepared) => prepared,
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

test("a loop stops when the claim generation is no longer its own", async () => {
  let answers = 0;
  let finished = false;
  const owned = chat();
  owned.claim_generation = 1;
  owned.script = ["one", "two"];
  const transport: HarnessTransport = {
    prepareTurn: async (_id, _gen, prepared) => prepared,
    runStatus: async () => ({
      status: "running",
      chat_rows: [{ id: "chat-1", claim_generation: answers === 0 ? 1 : 2 }],
    }),
    session: async () => session(),
    speak: async () => session(),
    answer: async () => {
      answers += 1;
      return session({
        messages: [
          { role: "assistant", content: "What color is the river?" },
          { role: "user", content: "one" },
          { role: "assistant", content: "Say the next part." },
        ],
      });
    },
    answerKey: async () => ({ expected: "blue", block_id: "blk" }),
    childText: async () => {
      throw new Error("script mode should not call the child model");
    },
    recordTurn: async () => ({ stop: "", cost_usd: "0", luna_tokens: 0 }),
    finish: async () => {
      finished = true;
    },
  };
  assert.equal(await playChat(owned, transport), "paused");
  assert.equal(answers, 1);
  assert.equal(finished, false);
  assert.equal(claimStillOwns({ status: "running", chat_rows: [{ id: "chat-1", claim_generation: 1 }] }, "chat-1", 1), true);
  assert.equal(claimStillOwns({ status: "running", chat_rows: [{ id: "chat-1", claim_generation: 2 }] }, "chat-1", 1), false);
});

test("a paused run leaves the chat for resume", async () => {
  const transport: HarnessTransport = {
    prepareTurn: async (_id, _gen, prepared) => prepared,
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

test("the place key includes the topic, so three explanation topics are not one place", () => {
  assert.equal(placeKey("e", "explain_topic", undefined), "e:explain_topic");
  assert.equal(placeKey("e", "explain_topic", null), "e:explain_topic");
  assert.notEqual(placeKey("e", "explain_topic", 0), placeKey("e", "explain_topic", 1));
  assert.notEqual(placeKey("e", "explain_topic", 1), placeKey("e", "explain_topic", 2));
});

test("eight same-place turns are followed by two nudges, then stuck", async () => {
  const childLines: string[] = [];
  const intents: string[] = [];
  const live: string[] = [];
  const answered: string[] = [];
  let pending = 0;
  const transport: HarnessTransport = {
    prepareTurn: async (_id, _gen, prepared) => prepared,
    runStatus: async () => ({ status: "running" }),
    session: async () => session({ block_id: "b1", active_substep: "explain", active_block_type: "topic_goal" }),
    speak: async () => session(),
    answer: async (_id, { child_text: text }) => {
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
    prepareTurn: async (_id, _gen, prepared) => prepared,
    runStatus: async () => ({ status: "running" }),
    session: async () => session(),
    speak: async () => session(),
    answer: async (_id, { child_text: text }) =>
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
    prepareTurn: async (_id, _gen, prepared) => prepared,
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

test("an empty tutor reply is not stored as the previous reply", async () => {
  const prior = "What color is the river?";
  const recorded: { tutor_reply?: string; error?: string; child_text?: string }[] = [];
  const transport: HarnessTransport = {
    prepareTurn: async (_id, _gen, prepared) => prepared,
    runStatus: async () => ({ status: "running" }),
    session: async () => session({ messages: [{ role: "assistant", content: prior }] }),
    speak: async () => session(),
    answer: async () => session({ messages: [{ role: "assistant", content: prior }] }),
    answerKey: async () => ({ expected: "blue", block_id: "blk" }),
    childText: async () => {
      throw new Error("script mode should not call the child model");
    },
    recordTurn: async (_id, body) => {
      const after = body.session_after as { tutor_reply?: string; error?: string };
      recorded.push({
        child_text: String(body.child_text || ""),
        tutor_reply: after.tutor_reply,
        error: String(after.error || ""),
      });
      return { stop: "completed", cost_usd: "0", luna_tokens: 0 };
    },
    finish: async () => undefined,
  };
  await playChat(chat(), transport);
  assert.equal(recorded.length, 1);
  assert.equal(recorded[0]?.child_text, "the river is blue");
  assert.equal(recorded[0]?.tutor_reply, "");
  assert.notEqual(recorded[0]?.tutor_reply, prior);
  assert.match(recorded[0]?.error || "", /new reply/);
});

test("a thrown tutor call does not copy the previous reply forward", async () => {
  const prior = "What color is the river?";
  const recorded: { tutor_reply?: string; error?: string }[] = [];
  const transport: HarnessTransport = {
    prepareTurn: async (_id, _gen, prepared) => prepared,
    runStatus: async () => ({ status: "running" }),
    session: async () => session({ messages: [{ id: "old", role: "assistant", content: prior }],
      prompt: "old prompt", loop_decision: "advance", loop_result: { advanced: true } }),
    speak: async () => session(),
    answer: async () => {
      throw new Error("The tutor did not write a reply.");
    },
    answerKey: async () => ({}),
    childText: async () => {
      throw new Error("script mode should not call the child model");
    },
    recordTurn: async (_id, body) => {
      const after = body.session_after as { tutor_reply?: string; error?: string };
      assert.equal((body.session_before as Record<string, unknown>).tutor_message_id, "old");
      const evidence = body.session_after as Record<string, unknown>;
      assert.ok(!evidence.tutor_message_id);
      assert.ok(!evidence.prompt);
      assert.ok(!evidence.loop_decision);
      assert.equal(evidence.loop_result, null);
      assert.equal(evidence.passed, false);
      recorded.push({ tutor_reply: after.tutor_reply, error: String(after.error || "") });
      return { stop: "completed", cost_usd: "0", luna_tokens: 0 };
    },
    finish: async () => undefined,
  };
  await playChat(chat(), transport);
  assert.equal(recorded.length, 1);
  assert.equal(recorded[0]?.tutor_reply, "");
  assert.match(recorded[0]?.error || "", /did not write a reply/);
});

test("a Cuba recall and a next-move explanation are answered before either nudge", async () => {
  const cuba = "What do you remember about why Cuba ended up in the middle?";
  const origins = "The next move is your own short explanation of the origins.";
  const tutors = [cuba, origins, origins, "Still on this step."];
  let step = 0;
  const childLines: string[] = [];
  const intents: string[] = [];
  const asked = chat();
  asked.pending_nudges = 2;
  asked.stuck_answers = 0;
  asked.script = ["Spain lost the island", "sugar and empire pulled it into the fight", "ok"];
  const transport: HarnessTransport = {
    prepareTurn: async (_id, _gen, prepared) => prepared,
    runStatus: async () => ({ status: "running" }),
    session: async () => session({ messages: [{ role: "assistant", content: cuba }] }),
    speak: async () => session(),
    answer: async () => {
      step += 1;
      return session({
        block_id: "b1",
        active_substep: "explain",
        active_block_type: "topic_goal",
        messages: [{ role: "assistant", content: tutors[Math.min(step, tutors.length - 1)] }],
      });
    },
    answerKey: async () => ({ block_id: "b1", block_type: "topic_goal", move_attempts: 0 }),
    childText: async () => {
      throw new Error("these answers are scripted");
    },
    recordTurn: async (_id, body) => {
      childLines.push(String(body.child_text));
      intents.push(String(body.intent));
      const turn = childLines.length;
      if (turn === 1) return { stop: "", pending_nudges: 2, stuck_answers: 1, cost_usd: "0", luna_tokens: 0 };
      if (turn === 2) return { stop: "", pending_nudges: 2, stuck_answers: 2, cost_usd: "0", luna_tokens: 0 };
      if (turn === 3) return { stop: "", pending_nudges: 1, stuck_answers: 2, cost_usd: "0", luna_tokens: 0 };
      return { stop: "stuck", pending_nudges: 0, stuck_answers: 0, cost_usd: "0", luna_tokens: 0 };
    },
    finish: async () => undefined,
  };
  await playChat(asked, transport);
  assert.deepEqual(childLines, [
    "Spain lost the island",
    "sugar and empire pulled it into the fight",
    "What's next?",
    "What should we do next?",
  ]);
  assert.deepEqual(intents, ["script", "script", "nudge", "nudge"]);
});

function retryTestTransport(): HarnessTransport {
  return {
    prepareTurn: async (_id, _gen, prepared) => prepared,
    runStatus: async () => ({ status: "running" }),
    session: async () => session({ revision: 4, messages: [{ role: "assistant", id: "old", content: "Ready?" }] }),
    speak: async () => { throw new Error("unexpected opening"); },
    answerKey: async () => ({ block_id: "b1", expected: "yes" }),
    childText: async () => ({ text: "yes", input_tokens: 5, output_tokens: 1, model: "test-child" }),
    answer: async () => session({ status: "completed", messages: [{ id: "fresh", role: "assistant", content: "Done." }] }),
    recordTurn: async () => ({ stop: "completed", cost_usd: null, luna_tokens: 0 }),
    finish: async () => { throw new Error("pending turn was bypassed"); },
  };
}

test("a lost tutor reply and a lost recording response retry the original submission once", async () => {
  const transport = retryTestTransport();
  let childCalls = 0;
  let preparations = 0;
  let writes = 0;
  const ids: string[] = [];
  const bodies: unknown[] = [];
  transport.childText = async () => ({ text: `answer ${++childCalls}`, input_tokens: 5, output_tokens: 1, model: "child" });
  transport.prepareTurn = async (_id, generation, prepared) => {
    assert.equal(generation, 7);
    assert.equal(prepared.seq, 3);
    assert.equal(prepared.revision, 4);
    assert.equal(prepared.session_before.tutor_message_id, "old");
    preparations++;
    return prepared;
  };
  transport.answer = async (_id, prepared) => {
    assert.equal(preparations, 1);
    assert.equal(prepared.child_text, "answer 1");
    ids.push(prepared.turn_id);
    if (ids.length === 1) throw new Error("lost after tutor commit");
    return session({ status: "completed", response_message_id: "new", messages: [{ id: "new", role: "assistant", content: "Ready?" }] });
  };
  transport.recordTurn = async (_id, body) => {
    bodies.push(body);
    if (++writes === 1) throw new Error("lost after harness commit");
    assert.deepEqual(body, bodies[0]);
    assert.equal(body.turn_id, ids[0]);
    assert.equal(body.seq, 3);
    assert.equal(body.claim_generation, 7);
    assert.equal((body.session_after as Record<string,unknown>).delivery_status, "recovered");
    return { replayed: true, stop: "completed", cost_usd: null, luna_tokens: 0 };
  };
  const owned = { ...chat(), behavior: "free" as const, claim_generation: 7, turn_count: 2 };
  assert.equal(await playChat(owned, transport), "done");
  assert.equal(ids.length, 2);
  assert.equal(new Set(ids).size, 1);
  assert.equal(childCalls, 1);
  assert.equal(writes, 2);
});

test("a reclaimed completed session reconciles the pending answer before opening, finishing or generating another", async () => {
  const transport = retryTestTransport();
  const saved = {
    turn_id: crypto.randomUUID(), revision: 3, seq: 4, child_text: "B", intent: "choice", child_prompt: "",
    child_tokens: { model: "test-child", input_tokens: 0, output_tokens: 0 },
    session_before: { tutor_message_id: "q", tutor_reply: "Which option?", block_id: "original", message_count: 1, last_message_id: "q" },
    move_intent: "choice", move_inner: { boredom: 3, frustration: 0, confusion: 0, hints: 2 },
  };
  const owned = { ...chat(), pending_turn: saved, claim_generation: 19, turn_count: 3, last_place: "original:choice" };
  const completed = session({ revision: 4, status: "completed", needs_speech: true, block_id: "saved-block",
    messages: [{ id: "q", role: "assistant", content: "Which option?" }, { id: "r", role: "assistant", content: "Well done." }],
    loop_result: { ended_unit: true, attempt_counted: true },
  });
  transport.session = async () => completed;
  transport.childText = async () => { throw new Error("pending child regenerated"); };
  transport.prepareTurn = async () => { throw new Error("pending move regenerated"); };
  transport.answerKey = async () => ({ revision: 6, block_id: "from-another-revision" });
  const events: string[] = [];
  transport.answer = async (_id, turn) => {
    events.push("replay");
    assert.deepEqual(turn, saved);
    assert.equal(turn.child_text, "B");
    return { ...completed, response_message_id: "r" };
  };
  transport.recordTurn = async (_id, body) => {
    events.push("record");
    assert.equal(body.claim_generation, 19);
    assert.equal(body.turn_id, saved.turn_id);
    assert.equal(body.seq, 4);
    assert.deepEqual(body.session_before, saved.session_before);
    assert.equal((body.inner_state as { hints: number }).hints, 2);
    const after = body.session_after as Record<string, unknown>;
    assert.equal(after.tutor_message_id, "r");
    assert.equal(after.block_id, "saved-block");
    assert.equal(after.delivery_status, "recovered");
    assert.deepEqual(after.loop_result, completed.loop_result);
    return { stop: "completed", cost_usd: "0", luna_tokens: 0 };
  };
  assert.equal(await playChat(owned, transport), "done");
  assert.deepEqual(events, ["replay", "record"]);
});

test("exhausted delivery preserves a single pending submission and defers after a committed receipt is found", async () => {
  const transport = retryTestTransport();
  const ids: string[] = [];
  const writes: unknown[] = [];
  transport.answer = async (_id, pending) => {
    ids.push(pending.turn_id);
    throw new Error("no response");
  };
  transport.recordTurn = async (_id, body) => {
    const after = body.session_after as Record<string, unknown>;
    assert.equal(after.delivery_status, "unknown");
    assert.equal(after.tutor_reply, "");
    assert.equal(after.loop_result, null);
    assert.equal(body.seq, 1);
    writes.push(body.defer);
    return { stop: body.defer ? "awaiting_retry" : "", recover: !body.defer, pending: true, cost_usd: null, luna_tokens: 0 };
  };
  assert.equal(await playChat(chat(), transport), "paused");
  assert.equal(ids.length, 3);
  assert.equal(new Set(ids).size, 1);
  assert.deepEqual(writes, [false, true]);
});

test("repeated child text on separate logical turns has separate submission IDs and sequence numbers", async () => {
  const transport = retryTestTransport();
  const owned = { ...chat(), script: ["yes", "yes"] };
  const turns: { text: string; seq: number; id: string }[] = [];
  transport.answer = async (_id, pending) => {
    turns.push({ text: pending.child_text, seq: pending.seq, id: pending.turn_id });
    return session({ revision: pending.seq, messages: [{ role: "assistant", id: `r${pending.seq}`, content: "Again?" }] });
  };
  transport.recordTurn = async () => ({ stop: turns.length === 2 ? "cap" : "", cost_usd: null, luna_tokens: 0 });
  assert.equal(await playChat(owned, transport), "done");
  assert.deepEqual(turns.map(({ text, seq }) => [text, seq]), [["yes", 1], ["yes", 2]]);
  assert.notEqual(turns[0].id, turns[1].id);
});

test("an unconfirmed submission survives Pause and Resume without drawing another child response", async () => {
  const transport = retryTestTransport();
  let saved: ClaimedChat["pending_turn"] = null;
  let accepted = false;
  let commits = 0;
  let answers = 0;
  let childCalls = 0;
  transport.childText = async () => ({ text: `chosen answer ${++childCalls}`, input_tokens: 2, output_tokens: 1, model: "child" });
  transport.prepareTurn = async (_id, _generation, turn) => {
    assert.equal(saved, null);
    saved = turn;
    return saved;
  };
  transport.answer = async (_id, turn) => {
    answers++;
    assert.deepEqual(turn, saved);
    if (!accepted) throw new Error("network unavailable before commit");
    return session({ status: "completed", messages: [{ role: "assistant", id: "fresh", content: "Correct." }] });
  };
  transport.recordTurn = async (_id, body) => {
    assert.equal(body.turn_id, saved?.turn_id);
    if (!accepted) {
      assert.equal((body.session_after as Record<string, unknown>).delivery_status, "unknown");
      return { pending: true, stop: "awaiting_retry", cost_usd: null, luna_tokens: 0 };
    }
    assert.equal(body.claim_generation, 6);
    assert.equal((body.session_after as Record<string, unknown>).delivery_status, "recovered");
    commits++;
    return { stop: "completed", cost_usd: null, luna_tokens: 0 };
  };
  const first = { ...chat(), behavior: "free" as const, claim_generation: 5 };
  assert.equal(await playChat(first, transport), "paused");
  assert.equal(answers, 2);
  assert.equal(commits, 0);
  accepted = true;
  assert.equal(await playChat({ ...first, claim_generation: 6, pending_turn: saved }, transport), "done");
  assert.equal(answers, 3);
  assert.equal(commits, 1);
  assert.equal(childCalls, 1);
});

test("a replaced worker with a lost response yields its pending submission to the new claim", async () => {
  const transport = retryTestTransport();
  let attempts = 0;
  transport.runStatus = async () => ({ status: "running", chat_rows: [{ id: "chat-1", claim_generation: attempts ? 4 : 3 }] });
  transport.answer = async () => { attempts++; throw new Error("lost"); };
  transport.recordTurn = async () => { throw new Error("a stale worker must not record or generate the next turn"); };
  assert.equal(await playChat({ ...chat(), claim_generation: 3 }, transport), "paused");
  assert.equal(attempts, 1);
});
