import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { HARNESS_BUTTONS, availableActions } from "./harness-actions.ts";
import { MOVE_ON_LABEL, TELL_ME_MORE_LABEL } from "./kc-goal-start.ts";

test("harness buttons are the labels the lesson sends", () => {
  const lesson = readFileSync(new URL("../components/learn/KcLesson.tsx", import.meta.url), "utf8");
  for (const label of HARNESS_BUTTONS) {
    assert.equal(lesson.includes(label), true, label);
  }
  assert.equal(HARNESS_BUTTONS.includes(TELL_ME_MORE_LABEL), true);
  assert.equal(HARNESS_BUTTONS.includes(MOVE_ON_LABEL), true);
  assert.ok(lesson.indexOf("Tell me more") < lesson.indexOf("Got it - move on"));
});

test("a choice card hides typing, and an explanation offers its buttons", () => {
  const choosing = availableActions({
    status: "in_progress",
    needs_speech: false,
    active_block_type: "mcq",
    active_substep: "ask",
    choice: {
      prompt: "Which way?",
      choices: [
        { id: "a", text: "Up" },
        { id: "b", text: "Down" },
      ],
    },
  });
  assert.equal(choosing.canType, false);
  assert.equal(choosing.choices.length, 2);
  const explaining = availableActions({
    status: "in_progress",
    needs_speech: false,
    active_block_type: "explanation",
    active_substep: "explain",
    choice: null,
  });
  assert.deepEqual(explaining.buttons, ["Tell me more", "Got it - move on"]);
  assert.equal(explaining.canType, true);
  const summary = availableActions({
    status: "in_progress",
    needs_speech: false,
    active_block_type: "explanation",
    active_substep: "summary_check",
    choice: null,
  });
  assert.deepEqual(summary.buttons, ["No final questions — let's continue!"]);
});
