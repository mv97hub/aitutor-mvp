import assert from "node:assert/strict";
import { registerHooks } from "node:module";
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
  const reply = await transport.answer("session-1", {
    turn_id: crypto.randomUUID(), seq: 1, revision: 0, session_before: { message_count: 0 },
    intent: "script", child_text: "blue", child_prompt: "", child_tokens: { model: "", input_tokens: 0, output_tokens: 0 },
    move_intent: "script", move_inner: { boredom: 0, frustration: 0, confusion: 0, hints: 0 },
  }, "gpt-4.1");
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

test("prepared transport uses the original revision and committed transcript even after session completion", async (t) => {
  const prior = { id: "old", role: "assistant", content: "Which?" };
  const final = { id: "new", role: "assistant", content: "Which?" };
  const completed: SessionSnap = { id: "session", status: "completed", revision: 5, needs_speech: false,
    messages: [prior, { id: "child", role: "user", content: "B" }, final] };
  const pending = {
    turn_id: crypto.randomUUID(), seq: 4, revision: 4, child_text: "B", intent: "choice", child_prompt: "",
    child_tokens: { model: "child", input_tokens: 0, output_tokens: 0 },
    session_before: { message_count: 1, last_message_id: prior.id, tutor_message_id: prior.id },
    move_intent: "choice", move_inner: { boredom: 0, frustration: 0, confusion: 0, hints: 0 },
  };
  let preparations = 0;
  let persisted: SessionSnap | null = null;
  t.mock.method(globalThis, "fetch", async (url: string, init: RequestInit) => {
    if (String(url).endsWith(`/pending-turn/${pending.turn_id}`)) {
      assert.equal(init.method ?? "GET", "GET");
      return Response.json({ result: persisted });
    }
    assert.ok(String(url).endsWith("/kc/harness/chats/chat/pending-turn"));
    assert.deepEqual(JSON.parse(String(init.body)), { claim_generation: 6, seq: pending.seq, submission: pending });
    preparations++;
    return Response.json({ submission: pending });
  });
  const bodies: unknown[] = [];
  const answer: RoutePost = async (req) => {
    bodies.push(await req.json());
    if (bodies.length === 1) return new Response("lost", { status: 502 });
    return Response.json(completed);
  };
  const transport = serverTransport("run", { answer, speak: ok({}), child: ok({}), turn: ok({}), finish: ok({}) },
    { session: async (_id, saved) => { assert.deepEqual(saved, completed); return saved!; },
      answerKey: async () => ({}), runStatus: async () => ({ status: "running" }) });
  const saved = await transport.prepareTurn("chat", 6, pending);
  await assert.rejects(transport.answer("session", saved, "model"), /lost/);
  const replay = await transport.answer("session", saved, "model");
  assert.equal(replay.response_message_id, final.id);
  assert.equal(preparations, 1);
  assert.deepEqual(bodies[0], { sessionId: "session", answer: "B", model: "model", turnId: pending.turn_id, revision: 4 });
  assert.deepEqual(bodies[0], bodies[1]);
  await assert.rejects(transport.answer("session", pending, "model", "chat"), /has not committed/);
  persisted = completed;
  const capped = await transport.answer("session", pending, "model", "chat");
  assert.deepEqual(capped, replay);
  assert.equal(bodies.length, 2, "receipt-only recovery never enters the tutor route");
});

test("recording the same final turn twice or pausing for delivery does not start another judge", async (t) => {
  const hooks = registerHooks({
    resolve(specifier, context, next) {
      return specifier.startsWith("@/lib/")
        ? next(new URL("./" + specifier.slice("@/lib/".length) + ".ts", import.meta.url).href, context)
        : next(specifier, context);
    },
  });
  const { POST } = await import("../app/api/kc/harness/turn/route.ts");
  const { judgeFinishedChat } = await import("./harness-judge-run.ts").finally(() => hooks.deregister());
  const stored = [
    { stop: "completed" }, { stop: "completed", replayed: true }, { stop: "awaiting_retry", pending: true },
  ];
  let judgeReads = 0;
  t.mock.method(globalThis, "fetch", async (url: string) => {
    const path = new URL(url).pathname;
    if (path === "/kc/harness/chats/chat/turns") return Response.json(stored.shift());
    if (path === "/kc/harness/chats/capped") return Response.json({ run_cap_reached: true, evaluations: [] });
    assert.equal(path, "/kc/harness/chats/chat");
    judgeReads++;
    return Response.json({ evaluations: [{ kind: "judged", child_realism: 4 }] });
  });
  assert.equal(await judgeFinishedChat("capped"), null, "no judge or evaluation write after hitting the cap");
  for (let index = 0; index < 3; index++) {
    const res = await POST(new Request("http://harness.local/api/kc/harness/turn", {
      method: "POST", body: JSON.stringify({ chatId: "chat", turn: { turn_id: "stable" } }),
    }));
    assert.equal(res.status, 200);
    assert.equal(judgeReads, 1);
  }
});
