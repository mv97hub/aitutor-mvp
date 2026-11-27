import type { SkillRadarPayload } from "./graph2.ts";

export type TrajectoryState =
  | "flourishing"
  | "steady_progress"
  | "needs_reinforcement"
  | "struggling"
  | "returning";

export type CourseMode = "explore" | "mastery" | "exam_prep";

export type ParentPolicyLocks = {
  more_guided_examples?: boolean;
  gentler_socratic?: boolean;
  stretch_challenge?: boolean;
  anchor_in_interest?: string;
};

export type RecommendedIntervention = {
  key: string;
  label: string;
  reason: string;
  payload: ParentPolicyLocks;
};

export type ParentSessionDigestItem = {
  id: string;
  session_id: string;
  course_id: string | null;
  course_title: string;
  kc_id: string;
  kc_title: string;
  trajectory_state: TrajectoryState;
  summary: string;
  talking_points: string[];
  biomarkers_snapshot: Record<string, number>;
  recommended_interventions: RecommendedIntervention[];
  created_at: string | null;
};

export type CopilotCourseRow = {
  course_id: string;
  code: string;
  title: string;
  audience: string;
  catalog_tier: string;
  default_archetype: string | null;
  standards: string[];
  total_components: number;
  known_count: number;
  fragile_count: number;
  in_progress_count: number;
  known_topics: string[];
  fragile_topics: string[];
  active_misconceptions: string[];
  blind_exam: {
    latest_pre_score: number | null;
    latest_post_score: number | null;
    hake_g: number | null;
  };
  course_mode?: CourseMode;
  parent_policy_locks?: ParentPolicyLocks;
};

export type TeacherShareMeta = {
  id: string;
  token_prefix: string;
  label: string;
  goal_id: string | null;
  course_title: string | null;
  status: "active" | "revoked" | "expired";
  expires_at: string | null;
  revoked_at: string | null;
  created_at: string | null;
  share_token?: string;
  share_path?: string;
};

export type ParentCopilotSummary = {
  student_id: string;
  display_name: string;
  interests: string[];
  trajectory_state: TrajectoryState;
  trajectory_meta: { label: string; description: string };
  biomarkers: {
    own_words_pass: number;
    hard_recovery_pass: number;
    on_topic_inquiry_before_known: number;
    multi_perspective_synthesis: number;
  };
  radar: SkillRadarPayload;
  digests: ParentSessionDigestItem[];
  courses: CopilotCourseRow[];
  teacher_shares: TeacherShareMeta[];
};

export type TeacherSnapshot = {
  share_label: string;
  scoped_course_id: string | null;
  expires_at: string | null;
  generated_at: string;
  learner: {
    first_name: string;
    grade_band: string;
  };
  trajectory_state: TrajectoryState;
  trajectory_meta: { label: string; description: string };
  biomarkers: {
    own_words_pass: number;
    hard_recovery_pass: number;
    on_topic_inquiry_before_known: number;
    multi_perspective_synthesis: number;
  };
  radar: SkillRadarPayload;
  courses: CopilotCourseRow[];
};

export const COURSE_MODE_OPTIONS: ReadonlyArray<{ id: CourseMode; label: string; hint: string }> = [
  { id: "explore", label: "Explore", hint: "Curiosity and intuition first" },
  { id: "mastery", label: "Mastery", hint: "Balanced understanding and checks" },
  { id: "exam_prep", label: "Exam Prep", hint: "Precision and transfer readiness" },
];

export const BIOMARKER_LABELS: ReadonlyArray<{ key: keyof ParentCopilotSummary["biomarkers"]; label: string }> = [
  { key: "own_words_pass", label: "Own-words passes" },
  { key: "hard_recovery_pass", label: "Unaided recoveries" },
  { key: "on_topic_inquiry_before_known", label: "Curious why/what-if asks" },
  { key: "multi_perspective_synthesis", label: "Multi-perspective syntheses" },
];

export function trajectoryTone(state: string): "good" | "calm" | "warn" | "alert" {
  if (state === "flourishing") return "good";
  if (state === "struggling") return "alert";
  if (state === "needs_reinforcement" || state === "returning") return "warn";
  return "calm";
}

export function formatPercent(score: number | null | undefined): string {
  if (typeof score !== "number" || Number.isNaN(score)) return "—";
  return `${Math.round(score * 100)}%`;
}

export function formatHakeGain(g: number | null | undefined): string {
  if (typeof g !== "number" || Number.isNaN(g)) return "—";
  const pct = Math.round(g * 100);
  return `${pct >= 0 ? "+" : ""}${pct}%`;
}

export function activeLockLabels(locks: ParentPolicyLocks | undefined | null): string[] {
  if (!locks) return [];
  const out: string[] = [];
  if (locks.more_guided_examples) out.push("More guided examples");
  if (locks.gentler_socratic) out.push("Gentler Socratic challenge");
  if (locks.stretch_challenge) out.push("Stretch challenge");
  if (locks.anchor_in_interest) out.push(`Anchor in ${locks.anchor_in_interest}`);
  return out;
}

export function absoluteShareUrl(sharePath: string, origin: string): string {
  const cleanOrigin = origin.replace(/\/+$/, "");
  const cleanPath = sharePath.startsWith("/") ? sharePath : `/${sharePath}`;
  return cleanOrigin ? `${cleanOrigin}${cleanPath}` : cleanPath;
}
