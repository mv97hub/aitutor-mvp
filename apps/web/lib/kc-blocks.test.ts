import assert from "node:assert/strict";
import test from "node:test";

import { blankBlock, blankData, blockSummary, orderScope, recommendedChips, scopeFromCourse, toggleScope } from "./kc-blocks.ts";

test("an empty scope falls back to topic and goal, in canvas order", () => {
  assert.deepEqual(orderScope([]), ["topic_goal"]);
  assert.deepEqual(orderScope(["retrieval_check", "curiosity", "nope"]), ["curiosity", "retrieval_check"]);
  assert.deepEqual(scopeFromCourse(undefined).length, 9);
  assert.deepEqual(scopeFromCourse([]), ["topic_goal"]);
});

test("unchecking the last type keeps topic and goal", () => {
  assert.deepEqual(toggleScope(["mcq"], "mcq"), ["topic_goal"]);
  assert.deepEqual(toggleScope(["topic_goal", "mcq"], "topic_goal"), ["mcq"]);
});

test("recommended chips follow the description sequence", () => {
  assert.deepEqual(
    recommendedChips(
      "Explains free fall. Recommended blocks: 1. Curiosity Hook (hammer vs. feather) -> 2. Topic / Goal (force-to-mass ratio).",
    ),
    [
      { label: "Curiosity Hook", focus: "hammer vs. feather" },
      { label: "Topic / Goal", focus: "force-to-mass ratio" },
    ],
  );
  assert.deepEqual(recommendedChips("", [{ type: "mcq", focus: "check" }]), [
    { label: "Multiple choice", focus: "check" },
  ]);
});

test("blank blocks use the field catalog keys", () => {
  const topic = blankData("topic_goal");
  assert.deepEqual(Object.keys(topic), ["topic", "goal", "acceptance_criteria", "teaching_notes"]);
  const mcq = blankData("mcq");
  assert.equal(mcq.mode, "static");
  assert.equal("question" in mcq, false);
  assert.equal("options" in mcq, false);
  const choices = mcq.choices as { id: string; text: string; is_correct: boolean }[];
  assert.equal(choices[0]?.is_correct, true);
  assert.equal("scenario" in blankData("case_study"), false);
  assert.equal("case_a" in blankData("case_study"), true);
  assert.equal("hook_question" in blankData("curiosity"), false);
  assert.equal("phenomenon_hook" in blankData("curiosity"), true);
  const worked = blankData("worked_example");
  const steps = worked.steps as { step_text: string; rationale: string }[];
  assert.equal(steps[0] && "step_text" in steps[0], true);
  assert.equal("solo_problem" in worked, true);
  assert.equal("solo_check" in worked, false);
  assert.deepEqual(Object.keys(blankBlock("retrieval_check", "r").data), [
    "recall_prompt",
    "expected_fact",
    "elaborative_why_prompt",
    "expected_why_rationale",
  ]);
});

test("the block summary groups a run of the same type", () => {
  assert.equal(
    blockSummary([
      blankBlock("curiosity", "a"),
      blankBlock("topic_goal", "b"),
      blankBlock("topic_goal", "c"),
    ]),
    "1 Curiosity · 2 Topics",
  );
});
