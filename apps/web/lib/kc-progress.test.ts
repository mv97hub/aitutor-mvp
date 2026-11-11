import assert from "node:assert/strict";
import test from "node:test";

import { readFileSync } from "node:fs";

import {
  blockRows,
  blockScore,
  childComponentLabel,
  componentLine,
  componentRecommendations,
  courseRecommendations,
  courseScore,
  courseTotals,
  coursesStartedFirst,
  finishedComponents,
  finishedSentence,
  masteryByCode,
  networkStatusClass,
  passedCourseRubric,
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

test("a selected course lists finished components, and a passed course adds the stored rubric", () => {
  const known = {
    ...unit("halves", "completed"),
    mastery: "known" as const,
    finished_blocks: 3,
    total_blocks: 3,
    what_was_strong: "You split the pizza.",
    result: { strong: "You split the pizza.", work_on: "Use this on the next piece." },
  };
  const fragile = {
    ...unit("thirds", "completed"),
    mastery: "fragile" as const,
    finished_blocks: 3,
    total_blocks: 3,
    what_was_strong: "The last try failed.",
    what_to_work_on: "Practice the rule in your own words.",
    result: { strong: "The last try failed.", work_on: "Practice the rule in your own words." },
  };
  const open = unit("quarters", "in_progress");
  assert.deepEqual(
    finishedComponents([known, open, fragile]).map((item) => item.code),
    ["halves", "thirds"],
  );
  assert.equal(blockScore(known), "3 of 3");
  assert.equal(
    finishedSentence(known, [{ component_code: "halves", summary: "You split the pizza into equal parts." }]),
    "You split the pizza into equal parts.",
  );
  assert.equal(finishedSentence(fragile, []), "You finished this topic.");
  assert.equal(finishedComponents([open]).length, 0);
  assert.deepEqual(passedCourseRubric({ course_complete: true, units: [known, fragile, open] }), {
    completed: "You split the pizza.",
    struggled: "Practice the rule in your own words.",
  });
  assert.deepEqual(passedCourseRubric({ course_complete: false, units: [known, fragile] }), {
    completed: "",
    struggled: "",
  });
  assert.deepEqual(
    passedCourseRubric({
      course_complete: true,
      units: [{ ...known, result: { strong: "The finished blocks held.", work_on: "" }, what_was_strong: "" }],
    }),
    { completed: "", struggled: "" },
  );
});

test("course totals, block rows, and recommendations come from stored progress", () => {
  const known = {
    ...unit("halves", "completed"),
    title: "Halves",
    mastery: "known" as const,
    total_blocks: 2,
    block_details: [
      {
        index: 1,
        block_id: "a",
        block_type: "topic_goal",
        label: "Goal",
        prompt_preview: "Split the pizza",
        rubric_line: "",
        counts_toward_mastery: true,
        status: "passed" as const,
        outcome: "passed" as const,
        attempts: 1,
        max_retries: 2,
        passed_on_first_try: true,
        eliminated_choices: [],
      },
      {
        index: 2,
        block_id: "b",
        block_type: "mcq",
        label: "Check",
        prompt_preview: "Which piece is half?",
        rubric_line: "",
        counts_toward_mastery: true,
        status: "passed" as const,
        outcome: "passed" as const,
        attempts: 2,
        max_retries: 2,
        passed_on_first_try: false,
        eliminated_choices: [],
      },
    ],
  };
  const fragile = {
    ...unit("thirds", "completed"),
    title: "Thirds",
    mastery: "fragile" as const,
    total_blocks: 2,
    what_to_work_on: "Practice the rule in your own words.",
    student_misconceptions: ["A third is bigger than a half."],
    block_details: [
      {
        index: 1,
        block_id: "c",
        block_type: "topic_goal",
        label: "Goal",
        prompt_preview: "Name a third",
        rubric_line: "",
        counts_toward_mastery: true,
        status: "revealed" as const,
        outcome: "revealed" as const,
        attempts: 3,
        max_retries: 2,
        passed_on_first_try: false,
        eliminated_choices: [],
      },
      {
        index: 2,
        block_id: "d",
        block_type: "mcq",
        label: "Check",
        prompt_preview: "",
        rubric_line: "",
        counts_toward_mastery: true,
        status: "upcoming" as const,
        outcome: null,
        attempts: 0,
        max_retries: null,
        passed_on_first_try: false,
        eliminated_choices: [],
      },
    ],
  };
  const open = {
    ...unit("quarters", "in_progress"),
    title: "Quarters",
    total_blocks: 1,
    passed_blocks_count: 0,
    revealed_blocks_count: 0,
  };
  const patch = { ...unit("extra", "completed", true), mastery: "fragile" as const, title: "Extra" };
  assert.deepEqual(courseTotals([known, fragile, open, patch]), {
    mastered: 1,
    completed: 1,
    inProgress: 1,
    notStarted: 0,
    blocksPassed: 2,
    blocksRevealed: 1,
    blocksNotYet: 2,
  });
  assert.equal(componentLine(known), "Mastered · 2 passed · 0 revealed · 2 of 2");
  assert.equal(componentLine(fragile), "Completed · 0 passed · 1 revealed · 1 of 2");
  assert.equal(componentLine(open), "In Progress · 0 passed · 0 revealed · 0 of 1");
  const rows = blockRows(fragile);
  assert.equal(rows.length, 2);
  assert.deepEqual(
    rows.map((row) => [row.name, row.type, row.state, row.attempts, row.firstTry]),
    [
      ["Name a third", "Goal", "Revealed", 3, false],
      ["Check", "mcq", "Not yet", 0, false],
    ],
  );
  assert.equal(blockRows(known)[0]?.firstTry, true);
  assert.equal(blockRows(known)[1]?.firstTry, false);
  assert.deepEqual(
    courseRecommendations([known, fragile, open, patch]).map((item) => item.title),
    ["Thirds"],
  );
  assert.deepEqual(
    componentRecommendations(fragile, [
      { component_code: "thirds", summary: "Block 1 (Goal) was revealed after 3 attempts." },
      { component_code: "halves", summary: "Leave this one." },
      { component_code: "thirds", summary: "Practice the rule in your own words." },
      { component_code: "thirds", summary: "Use this on the next piece." },
    ]),
    {
      workOn: "Practice the rule in your own words.",
      misconceptions: ["A third is bigger than a half."],
      opportunities: ["Block 1 (Goal) was revealed after 3 attempts."],
    },
  );
  assert.equal(
    componentRecommendations({ ...fragile, what_to_work_on: "The last try failed." }).workOn,
    "The last try failed.",
  );
});

test("detailed progress is the child page and a visit with no child goes home", () => {
  const page = readFileSync(new URL("../app/kc-progress/page.tsx", import.meta.url), "utf8");
  const view = readFileSync(new URL("../components/KcCourseProgress.tsx", import.meta.url), "utf8");
  assert.match(page, /if \(!studentId\) redirect\("\/learn"\)/);
  assert.match(page, /Detailed Progress/);
  assert.doesNotMatch(page, /ParentFrame/);
  assert.match(view, /Detailed Progress/);
  assert.match(view, /learnCoursePath/);
  assert.match(view, /courseTotals/);
  assert.match(view, /componentLine/);
  assert.match(view, /blockRows/);
  assert.match(view, /courseRecommendations/);
  assert.match(view, /componentRecommendations/);
  assert.match(view, /Blocks revealed/);
  assert.match(view, /Blocks not yet/);
  const helpers = readFileSync(new URL("./kc-progress.ts", import.meta.url), "utf8");
  assert.match(helpers, /"Passed" \| "Revealed" \| "Not yet"/);
  assert.doesNotMatch(view, /KcBanner|Fragile|Failed|Key Learning/);
});
