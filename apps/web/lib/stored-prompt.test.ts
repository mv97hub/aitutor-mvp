import assert from "node:assert/strict";
import test from "node:test";

import { requestForCall } from "./stored-prompt.ts";

test("a model call keeps the system prompt and the messages sent", () => {
  const stored = requestForCall(
    {
      prompt: [
        { role: "system", content: "You are the knowledge-component tutor." },
        { role: "user", content: "Say this step to the student now." },
      ],
      temperature: 0.2,
    },
    "You are the knowledge-component tutor.",
  );
  assert.equal(stored.system_prompt, "You are the knowledge-component tutor.");
  assert.deepEqual(stored.messages, [
    { role: "user", content: "Say this step to the student now." },
    { role: "request", content: { temperature: 0.2 } },
  ]);
});

test("the fallback system prompt is kept when the call has no system message", () => {
  const stored = requestForCall(
    { prompt: [{ role: "user", content: "Say this step to the student now." }] },
    "Layer 1",
  );
  assert.equal(stored.system_prompt, "Layer 1");
  assert.deepEqual(stored.messages, [{ role: "user", content: "Say this step to the student now." }]);
});
