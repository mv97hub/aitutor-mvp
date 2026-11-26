import assert from "node:assert/strict";
import test from "node:test";

import type { SessionSnap } from "./harness-runner.ts";
import { readSnap, serverTransport, type RoutePost } from "./harness-transport.ts";

function ok(body: unknown): RoutePost {
  return async () => Response.json(body);
}

test("a tutor turn calls the speak or answer route once", async () => {
  let speaks = 0;
  let answers = 0;
  let children = 0;
  const snap = async (_id: string, committed?: SessionSnap): Promise<SessionSnap> => committed ?? ({
    id: "session-1",
    status: "in_progress",
    needs_speech: false,
    messages: [],
  });
  const speak: RoutePost = async () => {
    speaks += 1;
    return Response.json({ ...await snap("session-1"), messages: [{ id: "spoken", role: "assistant", content: "Hi." }] });
  };
  const answer: RoutePost = async () => {
    answers += 1;
    return Response.json({ ...await snap("session-1"), messages: [{ id: "answered", role: "assistant", content: "Yes." }] });
  };
  const child: RoutePost = async () => {
    children += 1;
    return Response.json({ text: "blue", input_tokens: 3, output_tokens: 1, model: "gpt-4.1-mini", prompt: "be a child" });
  };
  const transport = serverTransport(
    "run-1",
    { speak, answer, child, turn: ok({ stop: "", cost_usd: "0", luna_tokens: 0 }), finish: ok({ ok: true }) },
    { runStatus: async () => ({ status: "running" }), session: snap, answerKey: async () => ({}) },
  );
  const opening = await transport.speak("session-1", "gpt-4.1");
  assert.equal(opening.response_message_id, "spoken");
  assert.equal(opening.tutor_call_kind, "speak");
  const reply = await transport.answer("session-1", "blue", "gpt-4.1");
  assert.equal(reply.response_message_id, "answered");
  assert.equal(reply.tutor_call_kind, "answer");
  const written = await transport.childText({
    model: "gpt-4.1-mini",
    intent: "answer_part",
    description: "Steady",
    traits: {},
    lastTutor: "What color?",
  });
  assert.equal(speaks, 1);
  assert.equal(answers, 1);
  assert.equal(children, 1);
  assert.equal(written.text, "blue");
  assert.equal(written.prompt, "be a child");
});

test("a failed tutor route is returned as the error and is not called again", async () => {
  let speaks = 0;
  const speak: RoutePost = async () => {
    speaks += 1;
    return new Response("The tutor did not say this step.", { status: 502 });
  };
  const transport = serverTransport(
    "run-1",
    { speak, answer: ok({}), child: ok({}), turn: ok({}), finish: ok({}) },
    {
      runStatus: async () => ({ status: "running" }),
      session: async () => ({ id: "session-1", status: "in_progress", needs_speech: false, messages: [] }),
      answerKey: async () => ({}),
    },
  );
  await assert.rejects(() => transport.speak("session-1", "gpt-4.1"), /did not say this step/);
  assert.equal(speaks, 1);
});

test("late or duplicate prompt records cannot supply a different message's evidence", async (t) => {
  const committed: SessionSnap = {
    id: "session-1", status: "in_progress", needs_speech: false, loop_decision: "advance",
    loop_result: { advanced: true }, messages: [{ id: "actual", role: "assistant", content: "Yes" }],
  };
  const matching = { message_id: "actual", system_prompt: "exact", decision: { loop_decision: "stay", safety_flag: "none" } };
  const other = { message_id: "late", system_prompt: "different", decision: { loop_decision: "redirect", safety_flag: "flag" } };
  let prompts = [matching, other];
  t.mock.method(globalThis, "fetch", async () => Response.json({ prompts }));
  const snapshot = await readSnap(committed.id, committed);
  assert.equal(snapshot.prompt, "exact");
  assert.equal(snapshot.loop_decision, "advance");
  assert.equal(snapshot.passed, true);
  assert.equal(snapshot.safety_flag, "none");
  for (const logs of [[other], [matching, matching, other]]) {
    prompts = logs;
    const missing = await readSnap(committed.id, { ...committed, loop_result: null, loop_decision: "" });
    assert.equal(missing.prompt, "");
    assert.equal(missing.loop_decision, "");
    assert.equal(missing.safety_flag, "none");
    assert.equal(missing.loop_result, null);
  }
});
