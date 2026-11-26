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

for (const failsBeforeCommit of [true, false]) {
  test(failsBeforeCommit
    ? "provider failure keeps the claimed submission available for retry"
    : "overlapping calls retain actual usage without claiming the winning reply", async (t) => {
    const oldKey = process.env.OPENROUTER_API_KEY;
    t.after(() => {
      if (oldKey === undefined) delete process.env.OPENROUTER_API_KEY;
      else process.env.OPENROUTER_API_KEY = oldKey;
    });
    process.env.OPENROUTER_API_KEY = "offline-fixture";
    const model = "~deepseek/deepseek-flash-latest";
    const session = { id: "lesson", revision: 1, tutor_model: model, messages: [] };
    const winner = { ...session, revision: 2, replayed: true, reply: "Saved.", loop_decision: "advance" };
    const writes: Record<string, Record<string, unknown>> = {};
    t.mock.method(globalThis, "fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(input instanceof Request ? input.url : String(input));
      if (url.hostname === "openrouter.ai") {
        if (failsBeforeCommit) return Response.json({ error: { message: "provider unavailable", type: "provider_error" } }, { status: 400 });
        return Response.json({
          id: "offline", model, created: 1, choices: [{ index: 0, finish_reason: "stop",
            message: { role: "assistant", content: JSON.stringify({ reply: "Losing reply.", decision: "stay" }) } }],
          usage: { prompt_tokens: 21, completion_tokens: 6, total_tokens: 27 },
        });
      }
      if (url.pathname.endsWith("/turn")) {
        return Response.json({ ...session, system_prompt: "Test rubric", response_schema: { type: "object" }, temperature: 0 });
      }
      if (url.pathname.endsWith("/lesson")) return Response.json(session);
      const operation = url.pathname.split("/").at(-1) || "";
      writes[operation] = JSON.parse(String(init?.body));
      return Response.json(operation === "decision" ? winner : {});
    });
    const response = await POST(new Request("http://harness.local/api/kc/tutor/answer", {
      method: "POST", body: JSON.stringify({ sessionId: "lesson", model, turnId: "pending-id", revision: 1, answer: "yes" }),
    }));
    if (failsBeforeCommit) {
      assert.equal(response.status, 502);
      assert.deepEqual(writes, {});
    } else {
      assert.equal(response.status, 200);
      assert.deepEqual(await response.json(), winner);
      assert.equal(writes["token-usage"]?.message_id, null);
      assert.equal(writes["token-usage"]?.input_tokens, 21);
      assert.equal(writes["model-prompts"]?.message_id, null);
    }
  });
}
