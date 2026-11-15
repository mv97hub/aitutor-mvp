import assert from "node:assert/strict";
import test from "node:test";

import { transcriptForChat } from "./harness-live.ts";

test("a running session is the transcript, and a pending child line is added once", () => {
  const lines = transcriptForChat(
    "chat-1",
    [
      { role: "assistant", content: "What color is the river?" },
      { role: "user", content: "blue" },
    ],
    [
      { chatId: "chat-1", role: "child", text: "blue" },
      { chatId: "chat-1", role: "child", text: "and cold" },
      { chatId: "other", role: "tutor", text: "Ignore me" },
    ],
  );
  assert.deepEqual(lines, [
    { role: "tutor", text: "What color is the river?" },
    { role: "child", text: "blue" },
    { role: "child", text: "and cold" },
  ]);
});

test("line numbers stay the session turn sequence", () => {
  const lines = transcriptForChat(
    "chat-1",
    [
      { role: "assistant", content: "Hello", seq: 4 },
      { role: "user", content: "blue", seq: 5 },
      { role: "assistant", content: "Hello", seq: 6 },
    ],
    [],
  );
  assert.deepEqual(lines, [
    { role: "tutor", text: "Hello", seq: 4 },
    { role: "child", text: "blue", seq: 5 },
    { role: "tutor", text: "Hello", seq: 6 },
  ]);
});

test("an empty session stays empty until a line arrives", () => {
  assert.deepEqual(transcriptForChat("chat-1", [], []), []);
  assert.deepEqual(transcriptForChat("chat-1", undefined, [{ chatId: "chat-1", role: "tutor", text: "Hello" }]), [
    { role: "tutor", text: "Hello" },
  ]);
});
