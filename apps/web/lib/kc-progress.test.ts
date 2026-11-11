import assert from "node:assert/strict";
import test from "node:test";

import { readFileSync } from "node:fs";

import {
  childComponentLabel,
  courseScore,
  coursesStartedFirst,
  masteryByCode,
  networkStatusClass,
  portfolioCourseStatus,
  portfolioCount,
  statusByCode,
  unitLine,
  unitsByStatus,
  type KcProgressUnit,
} from "./kc-progress.ts";

function unit(code: string, status: KcProgressUnit["status"], patch = false): KcProgressUnit {
  return { id: code, code, title: code, kc_type: "factual", patch, status };
}

test("the three lists keep course order and the map joins on component code", () => {
  const units = [
    unit("known", "completed"),
    unit("open", "in_progress"),
    unit("untouched", "not_started"),
    unit("also-known", "completed"),
    unit("patch", "not_started", true),
  ];
  const groups = unitsByStatus(units);
  assert.deepEqual(
    groups.completed.map((item) => item.code),
    ["known", "also-known"],
  );
  assert.deepEqual(
    groups.in_progress.map((item) => item.code),
    ["open"],
  );
  assert.deepEqual(
    groups.not_started.map((item) => item.code),
    ["untouched", "patch"],
  );
  assert.deepEqual(statusByCode(units), {
    known: "completed",
    open: "in_progress",
    untouched: "not_started",
    "also-known": "completed",
    patch: "not_started",
  });
  assert.equal(networkStatusClass("completed"), "is-completed");
  assert.equal(networkStatusClass("in_progress"), "is-in-progress");
  assert.equal(networkStatusClass("not_started"), "is-not-started");
  assert.equal(networkStatusClass(undefined), "");
  assert.equal(unitLine({ ...unit("known", "completed"), mastery: "known" }), "known");
  assert.equal(unitLine({ ...unit("gap", "completed", true), mastery: "fragile" }), "fragile patch");
  assert.equal(
    unitLine({ ...unit("open", "in_progress"), finished_blocks: 1, total_blocks: 3, summary: "Topic" }),
    "1 of 3 blocks",
  );
  assert.equal(unitLine({ ...unit("later", "not_started"), summary: "Topic, MCQ" }), "Topic, MCQ");
  assert.deepEqual(
    masteryByCode([
      { ...unit("known", "completed"), mastery: "known" },
      { ...unit("gap", "completed"), mastery: "fragile" },
      { ...unit("open", "in_progress"), mastery: "known" },
    ]),
    { known: "known", gap: "fragile" },
  );
});

test("the course percent counts known and fragile, and keeps the known count", () => {
  assert.deepEqual(
    courseScore(
      [
        { ...unit("known", "completed"), mastery: "known" },
        { ...unit("gap", "completed"), mastery: "fragile" },
        unit("later", "not_started"),
        unit("patch", "not_started", true),
      ],
      1,
    ),
    { percent: 67, finished: 2, total: 3, known: 1 },
  );
});

test("a finished fragile component counts as Completed", () => {
  assert.equal(childComponentLabel({ status: "completed", mastery: "known" }), "Mastered");
  assert.equal(childComponentLabel({ status: "completed", mastery: "fragile" }), "Completed");
  assert.equal(childComponentLabel({ status: "completed" }), "Completed");
  assert.equal(childComponentLabel({ status: "fragile" }), "Completed");
  assert.equal(childComponentLabel({ status: "in_progress" }), "In Progress");
  assert.equal(childComponentLabel({ status: "not_started" }), "");
  assert.equal(
    portfolioCourseStatus({
      started: true,
      course_complete: true,
      component_count: 2,
      completed_count: 2,
      known_count: 1,
      fragile_count: 1,
    }),
    "Completed",
  );
  assert.equal(
    portfolioCourseStatus({
      started: true,
      course_complete: true,
      component_count: 2,
      completed_count: 2,
      known_count: 2,
      fragile_count: 0,
    }),
    "Mastered",
  );
  assert.equal(
    portfolioCourseStatus({
      started: true,
      component_count: 3,
      completed_count: 1,
      in_progress_count: 1,
    }),
    "In Progress",
  );
  assert.equal(portfolioCourseStatus({ component_count: 4 }), "");
  assert.equal(
    portfolioCount({ component_count: 4, completed_count: 2, fragile_count: 1 }),
    "2 of 4",
  );
  assert.deepEqual(
    coursesStartedFirst([
      { id: "later" },
      { id: "now", started: true, last_active_at: "2026-11-01" },
      { id: "earlier", started: true, last_active_at: "2026-10-01" },
      { id: "quiet" },
    ]).map((course) => course.id),
    ["now", "earlier", "later", "quiet"],
  );
});

test("detailed progress is the child page and a visit with no child goes home", () => {
  const page = readFileSync(new URL("../app/kc-progress/page.tsx", import.meta.url), "utf8");
  const view = readFileSync(new URL("../components/KcCourseProgress.tsx", import.meta.url), "utf8");
  assert.match(page, /if \(!studentId\) redirect\("\/learn"\)/);
  assert.match(page, /Detailed Progress/);
  assert.match(view, /Detailed Progress/);
  assert.match(view, /learnCoursePath/);
  assert.doesNotMatch(view, /KcBanner|Fragile|Failed|Key Learning/);
});
