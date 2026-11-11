import assert from "node:assert/strict";
import test from "node:test";

import {
  BLOCK_FIELD_LABELS,
  BLOCK_REPLY_LABELS,
  BLOCK_TYPES,
  blankBlock,
  blankData,
  blockSummary,
  orderScope,
  scopeFromCourse,
  toggleScope,
} from "./kc-blocks.ts";

test("an empty scope falls back to topic and goal, in canvas order", () => {
  assert.deepEqual(orderScope([]), ["topic_goal"]);
  assert.deepEqual(orderScope(["retrieval_check", "curiosity", "nope"]), ["curiosity", "retrieval_check"]);
  assert.deepEqual(scopeFromCourse(undefined).length, 10);
  assert.deepEqual(scopeFromCourse([]), ["topic_goal"]);
});

test("unchecking the last type keeps topic and goal", () => {
  assert.deepEqual(toggleScope(["mcq"], "mcq"), ["topic_goal"]);
  assert.deepEqual(toggleScope(["topic_goal", "mcq"], "topic_goal"), ["mcq"]);
});

test("reply labels and field labels cover every block type once", () => {
  assert.deepEqual(Object.keys(BLOCK_REPLY_LABELS).sort(), [...BLOCK_TYPES].sort());
  assert.deepEqual(Object.keys(BLOCK_FIELD_LABELS).sort(), [...BLOCK_TYPES].sort());
  for (const type of BLOCK_TYPES) {
    const keys = BLOCK_FIELD_LABELS[type].map(([key]) => key);
    assert.equal(new Set(keys).size, keys.length, type);
    for (const key of keys) assert.equal(key in blankData(type), true, `${type}.${key}`);
  }
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
  const explanation = blankData("explanation");
  assert.deepEqual(Object.keys(explanation), ["block_title", "topics", "summary_takeaway"]);
  const topics = explanation.topics as { id: string; title: string; explanation: string }[];
  assert.equal(topics[0]?.id, "top_1");
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
