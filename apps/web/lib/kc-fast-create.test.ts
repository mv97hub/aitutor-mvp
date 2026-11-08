import assert from "node:assert/strict";
import test from "node:test";

import {
  CREATE_DRAFT_MESSAGE,
  beginFastCreate,
  emptyComponentIds,
  gapLabel,
  stepFastCreate,
  type FastRecord,
  type FastView,
} from "./kc-fast-create.ts";

const view = (patch: Partial<FastView> = {}): FastView => ({
  courseId: "course",
  componentId: "a",
  messageCount: 0,
  hasDraft: false,
  missing: ["no blocks"],
  markedComplete: false,
  error: null,
  ...patch,
});

test("empty components are the ones with no blocks, in list order", () => {
  assert.equal(CREATE_DRAFT_MESSAGE, "Create Draft");
  assert.deepEqual(
    emptyComponentIds([
      { id: "typed", blocks: [] },
      { id: "filled", blocks: [{ id: "b", type: "topic_goal" }] },
      { id: "first" },
      { id: "bare", blocks: [] },
      { id: "second" },
    ]),
    ["typed", "first", "bare", "second"],
  );
});

test("the gap line is the structure row's missing text", () => {
  assert.equal(gapLabel(["no truth", "no rubric check"]), "no truth, no rubric check");
  assert.equal(gapLabel([]), "");
});

test("a course with nothing empty finishes at 0 / 0", () => {
  const record = beginFastCreate("course", [], "gpt-4.1", 1);
  assert.equal(record.active, false);
  assert.equal(record.done, 0);
  assert.equal(record.ids.length, 0);
});

test("the cycle drafts, pushes, marks complete, then opens the next empty component", () => {
  let record = beginFastCreate("course", ["a", "b"], "gpt-4o", 1);
  let step = stepFastCreate(record, view());
  assert.equal(step.action.type, "draft");
  record = step.record;
  assert.equal(record.phase, "draft-sent");
  assert.equal(record.baseline, 0);

  step = stepFastCreate(record, view());
  assert.equal(step.action.type, "none");
  assert.equal(step.record, record);

  step = stepFastCreate(record, view({ messageCount: 2, hasDraft: true }));
  assert.equal(step.action.type, "push");
  record = step.record;

  step = stepFastCreate(record, view({ messageCount: 2, hasDraft: true }));
  assert.equal(step.action.type, "none");

  step = stepFastCreate(record, view({ messageCount: 3, hasDraft: false, missing: [] }));
  assert.equal(step.action.type, "complete");
  record = step.record;

  step = stepFastCreate(record, view({ messageCount: 3, hasDraft: false, missing: [] }));
  assert.equal(step.action.type, "none");

  step = stepFastCreate(record, view({ messageCount: 3, hasDraft: false, missing: [], markedComplete: true }));
  assert.equal(step.record.done, 1);
  assert.equal(step.record.index, 1);
  assert.deepEqual(step.action, { type: "open", courseId: "course", componentId: "b", model: "gpt-4o" });
});

test("a push that leaves a gap stops on that component and does not mark it complete", () => {
  const drafted: FastRecord = {
    ...beginFastCreate("course", ["a", "b"], "gpt-4.1", 1),
    phase: "push-sent",
    baseline: 0,
  };
  const waiting = stepFastCreate(drafted, view({ messageCount: 2, hasDraft: true, missing: ["no blocks"] }));
  assert.equal(waiting.action.type, "none");
  assert.equal(waiting.record.active, true);

  const stopped = stepFastCreate(drafted, view({ messageCount: 3, hasDraft: false, missing: ["no truth", "no rubric check"] }));
  assert.equal(stopped.action.type, "none");
  assert.equal(stopped.record.active, false);
  assert.equal(stopped.record.done, 0);
  assert.equal(stopped.record.gapId, "a");
  assert.equal(gapLabel(["no truth", "no rubric check"]), "no truth, no rubric check");
});

test("a missing key, or any error after the draft is sent, stops the cycle", () => {
  const sent: FastRecord = { ...beginFastCreate("course", ["a"], "gpt-4.1", 1), phase: "draft-sent", baseline: 0 };
  const stopped = stepFastCreate(sent, view({ error: "OPENAI_API_KEY is not set." }));
  assert.equal(stopped.record.active, false);
  assert.equal(stopped.record.done, 0);
  assert.equal(stopped.action.type, "none");
});

test("an error already on the page is cleared before the first draft", () => {
  const record = beginFastCreate("course", ["a"], "gpt-4.1", 1);
  const step = stepFastCreate(record, view({ error: "OPENAI_API_KEY is not set." }));
  assert.equal(step.record.active, true);
  assert.equal(step.action.type, "open");
});

test("the last component leaves the count at total", () => {
  const ready: FastRecord = {
    ...beginFastCreate("course", ["a"], "gpt-4.1", 1),
    phase: "complete-sent",
  };
  const step = stepFastCreate(ready, view({ hasDraft: false, missing: [], markedComplete: true }));
  assert.equal(step.record.active, false);
  assert.equal(step.record.done, 1);
  assert.equal(step.record.ids.length, 1);
  assert.equal(step.action.type, "none");
});

test("the run opens a component that is not on screen before it drafts", () => {
  const record = beginFastCreate("course", ["b"], "gpt-4.1", 1);
  const step = stepFastCreate(record, view({ componentId: "a" }));
  assert.deepEqual(step.action, { type: "open", courseId: "course", componentId: "b", model: "gpt-4.1" });
  assert.equal(step.record.phase, "draft");
});
