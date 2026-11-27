import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  MAX_END_CARD_SKILLS,
  NOT_ENOUGH_YET,
  SKILL_ORDER,
  judgeModelForCall,
  normalizeEndCard,
  orderedRadarSpokes,
  radarGeometry,
  type SkillRadarPayload,
} from "./graph2.ts";

function source(path: string): string {
  return readFileSync(new URL(path, import.meta.url), "utf8");
}

test("judgeModelForCall honors GRAPH2_JUDGE_MODEL override and falls back to tutor model", () => {
  assert.equal(judgeModelForCall("gpt-6-luna", "gpt-4.1-mini"), "gpt-4.1-mini");
  assert.equal(judgeModelForCall("gpt-6-luna", "deepseek/deepseek-flash-latest"), "~deepseek/deepseek-flash-latest");
  assert.equal(judgeModelForCall("gpt-6-luna", ""), "gpt-6-luna");
  assert.equal(judgeModelForCall("gpt-6-luna", "unknown-model"), "gpt-6-luna");
  assert.equal(judgeModelForCall(undefined, undefined), "gpt-4.1");
});

test("normalizeEndCard caps at 3 evidenced skills with sentence and quote", () => {
  const card = normalizeEndCard({
    items: [
      { skill: "evidence", label: "Evidence", sentence: "Grounded in text.", quote: "Paragraph 2 says..." },
      { skill: "causes", label: "Causes", sentence: "Traced cause.", quote: "Supply fell so prices rose." },
      { skill: "errors", label: "Errors", sentence: "Spotted break.", quote: "Step 2 doubled the bottom." },
      { skill: "transfer", label: "Transfer", sentence: "New case.", quote: "Works on buses too." },
    ],
  });
  assert.ok(card !== null);
  assert.equal(card.items.length, MAX_END_CARD_SKILLS);
  assert.deepEqual(
    card.items.map((item) => item.skill),
    ["evidence", "causes", "errors"],
  );
  // Missing quote or sentence drops the entry.
  assert.equal(
    normalizeEndCard({ items: [{ skill: "evidence", label: "Evidence", sentence: "Ok", quote: "" }] }),
    null,
  );
});

test("radar keeps hollow spokes under 3 observations and never draws a 0.50 octagon", () => {
  const emptyRadar: SkillRadarPayload = {
    student_id: "s1",
    min_observations: 3,
    spokes: SKILL_ORDER.map((skill) => ({
      skill,
      label: skill[0].toUpperCase() + skill.slice(1),
      count: 1,
      ready: false,
      hollow: true,
      score: 0.5, // Even if a caller accidentally supplied 0.50, orderedRadarSpokes strips it!
      status_label: NOT_ENOUGH_YET,
      last_quote: null,
      last_observed_at: null,
    })),
  };

  const ordered = orderedRadarSpokes(emptyRadar);
  assert.deepEqual(
    ordered.map((s) => s.skill),
    [...SKILL_ORDER],
  );
  assert.ok(ordered.every((s) => s.hollow && s.score === null && s.status_label === NOT_ENOUGH_YET));

  const geom = radarGeometry(emptyRadar);
  assert.equal(geom.readyVertices.length, 0);
  assert.equal(geom.filledPolygonPoints, null);
  assert.equal(geom.confirmedSegments.length, 0);
  assert.ok(geom.spokes.every((pt) => pt.hollow && pt.pointX === null && pt.pointY === null));

  // With 3 ready spokes, ONLY those 3 are plotted; the remaining 5 stay hollow.
  const partial: SkillRadarPayload = {
    student_id: "s1",
    min_observations: 3,
    spokes: [
      { skill: "evidence", label: "Evidence", count: 4, ready: true, hollow: false, score: 0.85, status_label: null, last_quote: "Line 2", last_observed_at: null },
      { skill: "perspectives", label: "Perspectives", count: 3, ready: true, hollow: false, score: 0.7, status_label: null, last_quote: "Both sides", last_observed_at: null },
      { skill: "causes", label: "Causes", count: 3, ready: true, hollow: false, score: 0.6, status_label: null, last_quote: "Because", last_observed_at: null },
    ],
  };
  const partialGeom = radarGeometry(partial);
  assert.equal(partialGeom.readyVertices.length, 3);
  assert.ok(partialGeom.filledPolygonPoints !== null);
  assert.equal(partialGeom.filledPolygonPoints.split(" ").length, 3);
  assert.equal(partialGeom.spokes.filter((pt) => pt.hollow).length, 5);
});

test("radar is shared across child progress and parent views and never appears in live chat", () => {
  const progress = source("../components/KcCourseProgress.tsx");
  const parentDash = source("../components/parent/ParentDashboard.tsx");
  const childProgressPage = source("../app/kc-progress/page.tsx");
  const parentProgressPage = source("../app/parent/[parentId]/child/[studentId]/progress/page.tsx");
  const parentDashPage = source("../app/parent/[parentId]/page.tsx");
  const lesson = source("../components/learn/KcLesson.tsx");
  const tutor = source("../components/KcTutor.tsx");
  const mobile = source("../components/learn/LearnMobileTutor.tsx");
  const answerRoute = source("../app/api/kc/tutor/answer/route.ts");

  assert.match(progress, /<SkillRadar/);
  assert.match(parentDash, /<SkillRadar/);
  assert.match(childProgressPage, /\/kc\/students\/.*\/radar/);
  assert.match(parentProgressPage, /\/radar/);
  assert.match(parentDashPage, /\/radar/);

  // Live chat never imports or renders SkillRadar; KcLesson renders SkillEndCardView on completion only.
  assert.doesNotMatch(lesson, /SkillRadar/);
  assert.doesNotMatch(tutor, /SkillRadar/);
  assert.doesNotMatch(mobile, /SkillRadar/);
  assert.match(lesson, /<SkillEndCardView endCard=\{session\.end_card\}/);

  // Post-close batch judge runs asynchronously after the reply is sent, never blocking the reply.
  assert.match(answerRoute, /schedulePostCloseTask/);
  assert.match(answerRoute, /import\("next\/server"\)/);
  assert.match(answerRoute, /mod\.after\(task\)/);
  assert.match(answerRoute, /graph2\/judge-prompt/);
  assert.match(answerRoute, /graph2\/judge-result/);
  assert.match(answerRoute, /graph2\/judge-failed/);
});
