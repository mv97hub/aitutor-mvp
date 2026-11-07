import assert from "node:assert/strict";
import test from "node:test";

import { promptsOnTranscript } from "./kc-chat-prompts.ts";

const prompt = (id: string, messageId: string | null, seq: number) => ({ id, message_id: messageId, seq });

test("a stored KC call sits on the tutor line it wrote", () => {
  const messages = [
    { id: "u1", role: "user" },
    { id: "a1", role: "assistant" },
  ];
  const { placed, leftover } = promptsOnTranscript(messages, [prompt("p1", "a1", 1)]);
  assert.equal(placed.get("a1")?.id, "p1");
  assert.equal(leftover.length, 0);
});

test("a call linked to the learner line opens on the following tutor line", () => {
  const messages = [
    { id: "u1", role: "user" },
    { id: "a1", role: "assistant" },
  ];
  const { placed } = promptsOnTranscript(messages, [prompt("p1", "u1", 1)]);
  assert.equal(placed.get("a1")?.id, "p1");
  assert.equal(placed.has("u1"), false);
});

test("an unlinked call fills the first tutor line that has none", () => {
  const messages = [{ id: "a1", role: "assistant" }];
  const { placed, leftover } = promptsOnTranscript(messages, [
    prompt("p1", null, 1),
    prompt("p2", null, 2),
  ]);
  assert.equal(placed.get("a1")?.id, "p1");
  assert.equal(leftover[0]?.id, "p2");
});
