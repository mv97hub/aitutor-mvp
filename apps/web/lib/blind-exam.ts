/** Pure helpers and shared types for F2 Blind Pre/Post Exams. */

import { DEFAULT_KC_MODEL, isKcModel, modelForCall } from "./kc-models.ts";

export type ExamPhase = "pre" | "post";

export type BlindExamChoice = {
  id: string;
  text: string;
};

export type BlindExamItem = {
  id: string;
  kind: "scenario_mcq" | "misconception_trap" | "short_transfer";
  kc_id: string;
  skill: string;
  prompt: string;
  choices: BlindExamChoice[];
  max_points: number;
};

export type BlindExamPublic = {
  id: string;
  goal_id: string;
  course_title: string;
  phase: ExamPhase;
  version: number;
  spec_fingerprint: string;
  model: string | null;
  item_count: number;
  items: BlindExamItem[];
  created_at: string | null;
};

export type BlindExamItemGrade = {
  item_id: string;
  kind: string;
  skill: string;
  earned: number;
  possible: number;
  correct: boolean;
  feedback: string;
  graded_by: string;
};

export type BlindExamAttemptSummary = {
  id: string;
  exam_id: string;
  goal_id: string;
  student_id: string | null;
  harness_chat_id: string | null;
  phase: ExamPhase;
  mode: "human" | "epistemic_sandbox";
  status: string;
  raw_score: number | null;
  mcq_score: number | null;
  transfer_score: number | null;
  paired_pre_attempt_id: string | null;
  paired_pre_score: number | null;
  hake_g: number | null;
  item_grades: BlindExamItemGrade[];
  submitted_at: string | null;
};

export type CourseExamSummary = {
  goal_id: string;
  course_title: string;
  spec_fingerprint: string;
  has_pre_exam: boolean;
  has_post_exam: boolean;
  exam: BlindExamPublic | null;
  pre_attempt: BlindExamAttemptSummary | null;
  post_attempt: BlindExamAttemptSummary | null;
  pre_score: number | null;
  post_score: number | null;
  hake_g: number | null;
};

export function examModelForCall(
  tutorModel: string | undefined | null,
  envOverride: string | undefined = typeof process !== "undefined" ? process.env.BLIND_EXAM_MODEL : undefined,
): string {
  const override = (envOverride || "").trim();
  if (override) {
    const normalized = modelForCall(override);
    if (isKcModel(normalized)) return normalized;
  }
  const fallback = (tutorModel || "").trim();
  if (fallback) {
    const normalized = modelForCall(fallback);
    if (isKcModel(normalized)) return normalized;
  }
  return DEFAULT_KC_MODEL;
}

export function normalizeExamPhase(raw: string | undefined | null): ExamPhase {
  return (raw || "").trim().toLowerCase() === "post" ? "post" : "pre";
}

export function learnExamPath(studentId: string, courseId: string, phase: ExamPhase): string {
  return `/learn/${encodeURIComponent(studentId)}/course/${encodeURIComponent(courseId)}/exam?phase=${phase}`;
}

export function formatExamPercent(score: number | null | undefined): string {
  if (typeof score !== "number" || !Number.isFinite(score)) return "—";
  return `${Math.round(Math.max(0, Math.min(1, score)) * 100)}%`;
}

export function formatHakeGain(g: number | null | undefined): string {
  if (typeof g !== "number" || !Number.isFinite(g)) return "—";
  const sign = g > 0 ? "+" : "";
  return `${sign}${g.toFixed(2)}`;
}

export function computeHakeGainClient(pre: number, post: number): number {
  const p0 = Math.max(0, Math.min(1, pre));
  const p1 = Math.max(0, Math.min(1, post));
  const denom = Math.max(1 - p0, 0.05);
  return Math.round(((p1 - p0) / denom) * 10000) / 10000;
}
