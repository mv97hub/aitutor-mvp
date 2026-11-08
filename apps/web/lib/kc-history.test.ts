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
    outline: "",
    topics: [],
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
  const courseHistory = readFileSync(new URL("../components/KcCourseHistory.tsx", import.meta.url), "utf8");
  const creator = readFileSync(new URL("../components/KcCreator.tsx", import.meta.url), "utf8");
  assert.match(studio, /<KcCourseHistory text=\{course\.history \?\? ""\} \/>/);
  assert.doesNotMatch(studio, /function HistoryLog/);
  assert.doesNotMatch(studio, /name="history"/);
  assert.doesNotMatch(studio, /contentEditable/);
  assert.match(courseHistory, /useState\(false\)/);
  assert.match(courseHistory, /Course history/);
  assert.match(courseHistory, /type="button"/);
  assert.match(courseHistory, /aria-expanded=\{open\}/);
  assert.match(courseHistory, /aria-label="Course history"/);
  assert.match(courseHistory, /hidden=\{!open\}/);
  assert.doesNotMatch(courseHistory, /name="history"/);
  assert.doesNotMatch(courseHistory, /contentEditable/);
  assert.doesNotMatch(courseHistory, /<textarea/);
  assert.doesNotMatch(courseHistory, /<input/);
  assert.match(creator, /<pre aria-label=\{label\}>/);
  assert.match(creator, /Course history/);
  assert.match(creator, /Component history/);
  assert.doesNotMatch(creator, /KcCourseHistory/);
  assert.doesNotMatch(creator, /name="history"/);
  assert.doesNotMatch(creator, /contentEditable/);
});
