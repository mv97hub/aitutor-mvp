import assert from "node:assert/strict";
import test from "node:test";

import { harnessRunIdentity, harnessRunWhen } from "./harness-run-identity.ts";

test("a run time is shown in Eastern time", () => {
  assert.equal(harnessRunWhen("2026-11-27T18:40:30Z"), "Nov 27, 2026, 1:40 PM EST");
  assert.equal(harnessRunWhen("2026-07-04T16:00:00Z"), "Jul 4, 2026, 12:00 PM EDT");
  assert.equal(harnessRunWhen(""), "—");
});

test("a stored plan shows the fields the agent create call accepts", () => {
  const identity = harnessRunIdentity(
    {
      id: "run-1",
      created_at: "2026-11-27T18:40:30Z",
      plan: {
        course_ids: ["course-1", "course-3"],
        persona_ids: ["persona-1", "persona-13", "persona-missing"],
        tutor_models: ["~deepseek/deepseek-flash-latest"],
        child_model: "gpt-6-luna",
        concurrency: 4,
        turn_limit: 40,
        run_cap_cents: 400,
        stuck_limit: 8,
      },
    },
    [
      { id: "persona-1", name: "AI_Child1" },
      { id: "persona-13", name: "AI_Child13" },
    ],
  );
  assert.equal(identity.when, "Nov 27, 2026, 1:40 PM EST");
  assert.equal(identity.runId, "run-1");
  assert.equal(identity.courseIds, "course-1, course-3");
  assert.equal(identity.childProfileIds, "AI_Child1 (persona-1), AI_Child13 (persona-13), persona-missing");
  assert.equal(identity.tutorModel, "~deepseek/deepseek-flash-latest");
  assert.equal(identity.childModel, "gpt-6-luna");
  assert.equal(identity.concurrency, "4");
  assert.equal(identity.turnLimit, "40");
  assert.equal(identity.costLimit, "400 cents");
  assert.equal(identity.stuckLimit, "8");
});

test("a run with no cap leaves the cost limit blank", () => {
  const identity = harnessRunIdentity({
    id: "run-2",
    created_at: "2026-11-27T18:40:30Z",
    plan: { run_cap_cents: null, tutor_model: "gpt-4.1" },
  });
  assert.equal(identity.costLimit, "blank");
  assert.equal(identity.tutorModel, "gpt-4.1");
  assert.equal(identity.courseIds, "—");
  assert.equal(identity.childProfileIds, "—");
});
