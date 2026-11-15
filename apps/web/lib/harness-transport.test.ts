import assert from "node:assert/strict";
import test from "node:test";

import type { SessionSnap } from "./harness-runner.ts";
import { serverTransport, type RoutePost } from "./harness-transport.ts";

function ok(body: unknown): RoutePost {
  return async () => Response.json(body);
}

test("a tutor turn calls the speak or answer route once", async () => {
  let speaks = 0;
  let answers = 0;
  let children = 0;
  const snap = async (): Promise<SessionSnap> => ({
    id: "session-1",
    status: "in_progress",
    needs_speech: false,
    messages: [],
  });
  const speak: RoutePost = async () => {
    speaks += 1;
    return Response.json({ ok: true });
  };
  const answer: RoutePost = async () => {
    answers += 1;
    return Response.json({ ok: true });
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
  await transport.speak("session-1", "gpt-4.1");
  await transport.answer("session-1", "blue", "gpt-4.1");
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
