import assert from "node:assert/strict";
import test from "node:test";

import { blockMarks } from "./harness-blocks.ts";

test("a block marks its start and its end, with the title when it was stored", () => {
  const marks = blockMarks([
    { seq: 1, session_after: { block_id: "b1", block_type: "explanation", block_title: "How Apple began" } },
    { seq: 2, session_after: { block_id: "b1", block_type: "explanation", block_title: "How Apple began" } },
    { seq: 3, session_after: { block_id: "b2", block_type: "topic_goal" } },
  ]);
  assert.deepEqual(marks, [
    { seq: 1, edge: "start", label: "Explanatory Walkthrough — How Apple began" },
    { seq: 2, edge: "end", label: "Explanatory Walkthrough — How Apple began" },
    { seq: 3, edge: "start", label: "Topic / Goal" },
  ]);
  assert.equal(marks.some((mark) => mark.edge === "end" && mark.label.includes("—")), true);
  assert.equal(marks.some((mark) => mark.label === "Topic / Goal"), true);
});

test("an older turn with no stored title shows the type only", () => {
  const marks = blockMarks([
    { seq: 4, session_after: { block_id: "old", block_type: "mcq" } },
    { seq: 5, session_after: { block_id: "next", block_type: "socratic", block_title: "Two cases" } },
  ]);
  assert.equal(marks[0].label, "Multiple Choice Question");
  assert.equal(marks[0].label.includes("—"), false);
  assert.equal(marks[1].edge, "end");
  assert.equal(marks[2].label, "Socratic Discussion — Two cases");
});

test("a move belongs to the block the learner answered before advancing", () => {
  const first = { block_id: "1", block_type: "mcq" };
  const next = { block_id: "2", block_type: "teach_back" };
  const marks = blockMarks([
    { seq: 1, session_before: first, session_after: next },
    { seq: 2, session_before: next, session_after: next },
  ]);
  assert.deepEqual(marks.map(({ seq, edge, label }) => [seq, edge, label]), [
    [1, "start", "Multiple Choice Question"], [1, "end", "Multiple Choice Question"],
    [2, "start", "Teach-Back / Feynman"],
  ]);
});
