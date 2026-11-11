import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { MOVE_ON_LABEL, TELL_ME_MORE_LABEL, goalStartActions } from "./kc-goal-start.ts";

const open = {
  status: "in_progress",
  needsSpeech: false,
  blockType: "topic_goal",
  substep: "explain",
  choosing: false,
};

test("a new topic offers Tell me more, then Got it - move on", () => {
  assert.deepEqual(goalStartActions(open), [TELL_ME_MORE_LABEL, MOVE_ON_LABEL]);
  assert.equal(TELL_ME_MORE_LABEL, "Tell me more");
  assert.equal(MOVE_ON_LABEL, "Got it - move on");
});

test("the buttons hide once the goal question is open", () => {
  assert.deepEqual(goalStartActions({ ...open, substep: "main" }), []);
  assert.deepEqual(goalStartActions({ ...open, substep: "summary_check" }), []);
  assert.deepEqual(goalStartActions({ ...open, blockType: "explanation" }), []);
  assert.deepEqual(goalStartActions({ ...open, needsSpeech: true }), []);
  assert.deepEqual(goalStartActions({ ...open, choosing: true }), []);
  assert.deepEqual(goalStartActions({ ...open, status: "completed" }), []);
});

test("the lesson sends those labels from the buttons, Tell me more first", () => {
  const lesson = readFileSync(new URL("../components/learn/KcLesson.tsx", import.meta.url), "utf8");
  assert.match(lesson, /goalStartActions/);
  assert.match(lesson, /sendAnswer\(label\)/);
  const tell = lesson.indexOf("Tell me more");
  const move = lesson.indexOf("Got it - move on");
  assert.equal(tell, -1);
  assert.equal(move, -1);
  const source = readFileSync(new URL("./kc-goal-start.ts", import.meta.url), "utf8");
  assert.ok(source.indexOf("Tell me more") < source.indexOf("Got it - move on"));
});
