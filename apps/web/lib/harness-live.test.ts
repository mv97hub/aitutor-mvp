import assert from "node:assert/strict";
import test from "node:test";

import { recentLines, transcriptForChat } from "./harness-live.ts";

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
    { role: "tutor", text: "What color is the river?", seq: 1 },
    { role: "child", text: "blue", seq: 2 },
    { role: "child", text: "and cold", seq: 3 },
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
    { role: "tutor", text: "Hello", seq: 1 },
  ]);
});

test("a live line keeps the session sequence, so the last number climbs past 40", () => {
  const messages = Array.from({ length: 41 }, (_, index) => ({
    role: index % 2 === 0 ? "assistant" : "user",
    content: `line ${index + 1}`,
    seq: index + 1,
  }));
  const lines = transcriptForChat("chat-1", messages, [{ chatId: "chat-1", role: "child", text: "line 42" }]);
  assert.equal(lines.at(-1)?.seq, 42);
  const shown = recentLines(lines);
  assert.equal(shown.length, 40);
  assert.equal(shown[0]?.seq, 3);
  assert.equal(shown.at(-1)?.seq, 42);
});
