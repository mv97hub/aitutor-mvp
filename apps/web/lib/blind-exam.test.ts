import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  computeHakeGainClient,
  examModelForCall,
  formatExamPercent,
  formatHakeGain,
  learnExamPath,
  normalizeExamPhase,
} from "./blind-exam.ts";

test("examModelForCall prefers BLIND_EXAM_MODEL override, then tutor model, then default", () => {
  assert.equal(examModelForCall("gpt-4.1", "gpt-4.1-mini"), "gpt-4.1-mini");
  assert.equal(examModelForCall("gpt-4.1", "deepseek/deepseek-flash-latest"), "~deepseek/deepseek-flash-latest");
  assert.equal(examModelForCall("gpt-4o", ""), "gpt-4o");
  assert.equal(examModelForCall("", ""), "gpt-4.1");
});

test("Hake gain and percentage formatting match the F2 contract", () => {
  assert.equal(computeHakeGainClient(0.4, 0.7), 0.5);
  assert.equal(computeHakeGainClient(1.0, 1.0), 0);
  assert.equal(formatExamPercent(0.754), "75%");
  assert.equal(formatExamPercent(null), "—");
  assert.equal(formatHakeGain(0.5), "+0.50");
  assert.equal(formatHakeGain(-0.1), "-0.10");
  assert.equal(formatHakeGain(null), "—");
  assert.equal(normalizeExamPhase("POST"), "post");
  assert.equal(normalizeExamPhase("anything"), "pre");
  assert.equal(learnExamPath("s1", "c1", "pre"), "/learn/s1/course/c1/exam?phase=pre");
});

test("quiet blind exam UI stays isolated from the live tutor and parent view stays read-only", () => {
  const examUi = readFileSync(new URL("../components/learn/BlindExamClient.tsx", import.meta.url), "utf8");
  assert.equal(examUi.includes("/api/kc/tutor/answer"), false);
  assert.equal(examUi.includes("/api/kc/tutor/speak"), false);
  assert.equal(examUi.includes("KcLesson"), false);

  const progressUi = readFileSync(new URL("../components/KcCourseProgress.tsx", import.meta.url), "utf8");
  assert.equal(progressUi.includes("!area && courseId"), true);
});


test("epistemic API route supports both single-chat and multi-component course run rollups", () => {
  const route = readFileSync(new URL("../app/api/kc/exam/epistemic/route.ts", import.meta.url), "utf8");
  assert.equal(route.includes("/kc/harness/runs/"), true);
  assert.equal(route.includes("/kc/harness/chats/"), true);
  assert.equal(route.includes("epistemic-context"), true);
});
