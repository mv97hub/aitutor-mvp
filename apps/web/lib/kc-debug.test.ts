import assert from "node:assert/strict";
import test from "node:test";

import { debugTurns } from "./kc-debug.ts";

const prompt = (id: string, seq: number, messageId: string | null, system = `system ${id}`) => ({
  id,
  session_id: "session",
  message_id: messageId,
  seq,
  system_prompt: system,
  messages: [{ role: "user", content: `ask ${id}` }],
  model: "gpt-4o-mini",
  created_at: "2026-11-07T00:00:00Z",
});

test("debug turns keep earlier calls and put the newest last", () => {
  const turns = debugTurns({
    messages: [
      { id: "a1", content: "First reply" },
      { id: "a2", content: "Second reply" },
    ],
    prompts: [prompt("p2", 2, "a2"), prompt("p1", 1, "a1")],
  });
  assert.deepEqual(
    turns.map((turn) => turn.id),
    ["p1", "p2"],
  );
  assert.equal(turns[0]?.response, "First reply");
  assert.equal(turns[1]?.response, "Second reply");
  assert.equal(turns[1]?.system_prompt, "system p2");
  assert.equal((turns[1]?.messages[0] as { content: string }).content, "ask p2");
});

test("a stored call with no linked message keeps an empty response", () => {
  const turns = debugTurns({
    messages: [],
    prompts: [prompt("p1", 1, null)],
  });
  assert.equal(turns[0]?.response, "");
  assert.equal(turns[0]?.messages.length, 1);
});
