import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import type { KcComponent, KcCourse } from "./kc.ts";
import { applyUnit, emptyTesterValues, testerPayload } from "./kc-prompt-tester.ts";

function component(history: string): KcComponent {
  return {
    id: "unit-1",
    code: "angles",
    title: "Angle sum",
    description: "Why a triangle's angles add up.",
    kc_type: "conceptual",
    target: true,
    core_truth: "The angles add to 180.",
    rubric: ["States 180."],
    misconceptions: [{ wrong_move: "They add to 90.", broken_kc: "right-angle" }],
    prerequisite_codes: ["lines"],
    encompasses_codes: [],
    type_fields: { case_a: "thin", case_b: "wide", prediction: "Which one?", rule: "180" },
    marked_complete: false,
    missing: [],
    history,
  };
}

test("history on a component or course is left out of the tutor tester payload", () => {
  const course: KcCourse = {
    id: "course-1",
    code: "geometry",
    title: "Triangles",
    description: "See why the angles add up.",
    audience: "12-14",
    kind: "mastery",
    minutes: null,
    ready: false,
    history: "2026-11-07 16:42:00 ET Warning: course-history-marker",
    components: [component("2026-11-07 16:42:00 ET Warning: component-history-marker")],
    patches: [],
  };
  const unit = course.components[0];
  assert.ok(unit);
  const values = applyUnit(emptyTesterValues(), course, unit);
  const body = testerPayload(values);
  const blob = JSON.stringify({ values, body });
  assert.equal(blob.includes("course-history-marker"), false);
  assert.equal(blob.includes("component-history-marker"), false);
  assert.equal(Object.hasOwn(body, "history"), false);
});

test("KC Course Creator shows course and component history read-only", () => {
  const studio = readFileSync(new URL("../components/KcStudio.tsx", import.meta.url), "utf8");
  const creator = readFileSync(new URL("../components/KcCreator.tsx", import.meta.url), "utf8");
  for (const source of [studio, creator]) {
    assert.match(source, /<pre aria-label=\{label\}>/);
    assert.match(source, /Course history/);
    assert.doesNotMatch(source, /name="history"/);
    assert.doesNotMatch(source, /contentEditable/);
  }
  assert.match(creator, /Component history/);
});
