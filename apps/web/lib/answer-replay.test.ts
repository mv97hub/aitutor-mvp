import assert from "node:assert/strict";
import { registerHooks } from "node:module";
import test from "node:test";

// Load the actual Next route in Node, resolving the same project alias as Next.
const hooks = registerHooks({
  resolve(specifier, context, next) {
    return specifier.startsWith("@/lib/")
      ? next(new URL("./" + specifier.slice("@/lib/".length) + ".ts", import.meta.url).href, context)
      : next(specifier, context);
  },
});
const { POST } = await import("../app/api/kc/tutor/answer/route.ts");
hooks.deregister();

for (const haveKey of [true, false]) {
  test(`lost answer returns its committed session without a model call (key present: ${haveKey})`, async (t) => {
    const key = process.env.OPENAI_API_KEY;
    t.after(() => {
      if (key === undefined) delete process.env.OPENAI_API_KEY;
      else process.env.OPENAI_API_KEY = key;
    });
    if (haveKey) process.env.OPENAI_API_KEY = "local-replay-test";
    else delete process.env.OPENAI_API_KEY;

    const saved = { id: "lesson", revision: 2, status: "completed", tutor_model: "gpt-4.1",
      messages: [{ id: "reply", role: "assistant", content: "Well done." }], reply: "Well done.", replayed: true };
    const submission = { answer: "yes", turn_id: "one-answer", revision: 1 };
    const requests: string[] = [];
    t.mock.method(globalThis, "fetch", async (url: string, init: RequestInit) => {
      const path = new URL(url).pathname;
      requests.push(path);
      if (path === "/kc/tutor/sessions/lesson") return Response.json(saved);
      assert.equal(path, "/kc/tutor/sessions/lesson/turn");
      assert.deepEqual(JSON.parse(String(init.body)), submission);
      return Response.json(saved);
    });

    const response = await POST(new Request("http://harness.local/api/kc/tutor/answer", {
      method: "POST", body: JSON.stringify({ sessionId: "lesson", turnId: "one-answer", revision: 1, answer: "yes" }),
    }));
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), saved);
    assert.equal(requests.filter(path => path.endsWith("/turn")).length, 1);
    assert.ok(requests.every(path => path === "/kc/tutor/sessions/lesson" || path.endsWith("/turn")));
  });
}

test("a conflicting saved submission preserves the API conflict", async (t) => {
  t.mock.method(globalThis, "fetch", async (url: string) => {
    if (new URL(url).pathname.endsWith("/turn")) {
      return Response.json({ detail: "That turn was already sent with a different answer." }, { status: 409 });
    }
    return Response.json({ tutor_model: "gpt-4.1" });
  });
  const response = await POST(new Request("http://harness.local/api/kc/tutor/answer", {
    method: "POST", body: JSON.stringify({ sessionId: "lesson", turnId: "one-answer", revision: 1, answer: "changed" }),
  }));
  assert.equal(response.status, 409);
});
