import assert from "node:assert/strict";
import test from "node:test";

import { blankBlock, blockSummary, orderScope, scopeFromCourse, toggleScope } from "./kc-blocks.ts";

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
