import {
  CHALLENGE_APPETITE_OPTIONS,
  COMMUNICATION_TONE_OPTIONS,
  EXPLANATION_STYLE_OPTIONS,
  GRADE_BAND_OPTIONS,
  INTEREST_TAG_OPTIONS,
  gradeBandForAge,
} from "./kc-layer-fields.ts";
import type { KcTutorCourse } from "./kc.ts";
import { DEFAULT_KC_MODEL, kcModel } from "./kc-models.ts";
import type { Student } from "./types.ts";

/** Keep these thresholds aligned with apps/api/app/learn_stars.py. */
export const EXPLORER_RANKS = [
  { level: 1, rank: "Curious Spark", floor: 0 },
  { level: 2, rank: "Concept Builder", floor: 75 },
  { level: 3, rank: "Discovery Navigator", floor: 250 },
  { level: 4, rank: "Grand Scholar", floor: 600 },
] as const;

export const GRADE_SHORT: Record<string, string> = {
  early_elementary: "Grades K–2",
  upper_elementary: "Grades 3–5",
  middle_school: "Grades 6–8",
  high_school: "Grades 9–12",
};

export const EXPLANATION_SHORT: Record<string, string> = {
  concrete_examples: "Concrete examples",
  story_and_analogy: "Stories & analogies",
  step_by_step: "Step-by-step",
  visual_spatial: "Visual pictures",
  pattern_and_rule: "Patterns & rules",
};

export const CHALLENGE_SHORT: Record<string, string> = {
  needs_reassurance: "Needs reassurance",
  steady: "Steady",
  loves_a_challenge: "Loves a challenge",
};

export const TONE_SHORT: Record<string, string> = {
  warm_and_encouraging: "Warm & encouraging",
  playful_and_curious: "Playful & curious",
  calm_and_gentle: "Calm & gentle",
  direct_and_matter_of_fact: "Direct",
};

export const CHILD_STATUSES = ["Mastered", "Completed", "In Progress", "Up Next", "Locked"] as const;

export type ChildDraft = {
  name: string;
  age: string;
  grade_band: string;
  reading_level: string;
  response_length: string;
  expression_style: string;
  explanation_style: string;
  challenge_appetite: string;
  communication_tone: string;
  learning_support: string;
  interest_tags: string[];
  interests: string;
  avatar_preset: string;
  avatar_url: string;
  tutor_model: string;
};

export type LearnerCard = {
  student: Student;
  in_progress_course_count: number;
  stars: number;
  explorer_level: number;
  explorer_rank: string;
  explorer_floor: number;
  explorer_next: number | null;
  explorer_percent: number;
};

export function explorerFor(stars: number): {
  explorer_level: number;
  explorer_rank: string;
  explorer_floor: number;
  explorer_next: number | null;
  explorer_percent: number;
} {
  const safe = Math.max(0, Math.floor(stars || 0));
  let level: number = EXPLORER_RANKS[0].level;
  let rank: string = EXPLORER_RANKS[0].rank;
  let floor: number = EXPLORER_RANKS[0].floor;
  let next: number | null = EXPLORER_RANKS[1].floor;
  EXPLORER_RANKS.forEach((item, index) => {
    if (safe >= item.floor) {
      level = item.level;
      rank = item.rank;
      floor = item.floor;
      next = index + 1 < EXPLORER_RANKS.length ? EXPLORER_RANKS[index + 1].floor : null;
    }
  });
  const percent = next == null ? 100 : Math.min(100, Math.floor(((safe - floor) * 100) / Math.max(next - floor, 1)));
  return {
    explorer_level: level,
    explorer_rank: rank,
    explorer_floor: floor,
    explorer_next: next,
    explorer_percent: percent,
  };
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0] ?? ""}${parts[1][0] ?? ""}`.toUpperCase();
}

export function interestLabel(id: string): string {
  return INTEREST_TAG_OPTIONS.find(([key]) => key === id)?.[1] ?? id;
}

export function gradeLabel(band: string | undefined): string {
  return GRADE_BAND_OPTIONS.find(([id]) => id === band)?.[1] ?? GRADE_SHORT[band || ""] ?? "Grade band";
}

export function gradePill(age: number | null | undefined, band: string | undefined): string {
  const short = GRADE_SHORT[band || ""] ?? "Grade band";
  if (age == null) return short;
  return `Age ${age} · ${short}`;
}

/** Never surface the technical mastery word on a child screen. */
export function displayChildStatus(label: string | undefined, status?: string, mastery?: string): string {
  if (label && CHILD_STATUSES.includes(label as (typeof CHILD_STATUSES)[number]) && !/fragile/i.test(label)) {
    return label;
  }
  if (status === "completed" && mastery === "known") return "Mastered";
  if (status === "completed" || mastery === "fragile" || status === "fragile") return "Completed";
  if (status === "in_progress") return "In Progress";
  if (status === "locked") return "Locked";
  return "Up Next";
}

export function blankChildDraft(): ChildDraft {
  return {
    name: "",
    age: "10",
    grade_band: gradeBandForAge(10),
    reading_level: "on_grade",
    response_length: "balanced",
    expression_style: "short_phrases",
    explanation_style: "concrete_examples",
    challenge_appetite: "steady",
    communication_tone: "warm_and_encouraging",
    learning_support: "none",
    interest_tags: [],
    interests: "",
    avatar_preset: "",
    avatar_url: "",
    tutor_model: DEFAULT_KC_MODEL,
  };
}

export function draftFromStudent(student: Student): ChildDraft {
  const cp = student.child_profile;
  const age = student.age ?? 10;
  return {
    name: student.display_name,
    age: String(age),
    grade_band: cp?.grade_band || student.grade_band || gradeBandForAge(age),
    reading_level: cp?.reading_level || student.reading_level || "on_grade",
    response_length: cp?.response_length || student.response_length || "balanced",
    expression_style: cp?.expression_style || student.expression_style || "short_phrases",
    explanation_style: cp?.explanation_style || student.explanation_style || student.modality || "concrete_examples",
    challenge_appetite: cp?.challenge_appetite || student.challenge_appetite || "steady",
    communication_tone: cp?.communication_tone || student.communication_tone || "warm_and_encouraging",
    learning_support: cp?.learning_support || student.learning_support || "none",
    interest_tags: [...(cp?.interest_tags || student.interest_tags || [])].slice(0, 4),
    interests: cp?.interests || (student.interests || []).join(", "),
    avatar_preset: cp?.avatar_preset || "",
    avatar_url: cp?.avatar_url || "",
    tutor_model: kcModel(student.tutor_model || cp?.tutor_model),
  };
}

export function childDraftError(draft: ChildDraft): string | null {
  if (!draft.name.trim()) return "Name is required.";
  const age = Number(draft.age);
  if (!Number.isInteger(age) || age < 4 || age > 18) return "Age must be from 4 to 18.";
  return null;
}

/** Gray circle is stored blank so a child who never picks an icon still shows initials. */
export function withChildAvatarPreset(draft: ChildDraft, preset: string): ChildDraft {
  const trimmed = preset.trim();
  return {
    ...draft,
    avatar_preset: !trimmed || trimmed === "default_circle" ? "" : trimmed,
    avatar_url: "",
  };
}

export function withChildAvatarUrl(draft: ChildDraft, url: string | null): ChildDraft {
  return { ...draft, avatar_url: url ?? "" };
}

/**
 * An icon click emits a preset change and then a URL clear. Each step has to
 * see the draft from the step before it, or the URL clear puts the old preset back.
 */
export function childAvatarAfterIconClick(draft: ChildDraft, preset: string): ChildDraft {
  return withChildAvatarUrl(withChildAvatarPreset(draft, preset), null);
}

export function childWriteBody(draft: ChildDraft, opts: { includeName: boolean }) {
  const age = Number(draft.age);
  const favorites = draft.interests.trim().slice(0, 120);
  const tags = draft.interest_tags.slice(0, 4);
  const tutorModel = kcModel(draft.tutor_model);
  const profile = {
    grade_band: draft.grade_band || gradeBandForAge(age),
    reading_level: draft.reading_level || "on_grade",
    response_length: draft.response_length || "balanced",
    expression_style: draft.expression_style || "short_phrases",
    explanation_style: draft.explanation_style || "concrete_examples",
    challenge_appetite: draft.challenge_appetite || "steady",
    communication_tone: draft.communication_tone || "warm_and_encouraging",
    learning_support: draft.learning_support || "none",
    interest_tags: tags,
    interests: favorites,
    avatar_preset: draft.avatar_preset,
    avatar_url: draft.avatar_url.trim(),
    tutor_model: tutorModel,
  };
  const interests = favorites
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  const body: Record<string, unknown> = {
    age,
    grade_band: profile.grade_band,
    reading_level: profile.reading_level,
    response_length: profile.response_length,
    expression_style: profile.expression_style,
    explanation_style: profile.explanation_style,
    modality: profile.explanation_style,
    challenge_appetite: profile.challenge_appetite,
    communication_tone: profile.communication_tone,
    learning_support: profile.learning_support,
    interest_tags: tags,
    interests,
    tutor_model: tutorModel,
    child_profile: profile,
  };
  if (opts.includeName) body.display_name = draft.name.trim();
  return body;
}

export function courseMinutes(course: { minutes?: number | null; component_count?: number }): number {
  if (course.minutes && course.minutes > 0) return course.minutes;
  return Math.max(course.component_count ?? 1, 1) * 4;
}

export function sumStars(courses: KcTutorCourse[]): number {
  return courses.reduce((total, course) => total + (course.stars ?? 0), 0);
}

export function explanationChoices(): [string, string][] {
  return EXPLANATION_STYLE_OPTIONS.map(([id]) => [id, EXPLANATION_SHORT[id] ?? id]);
}

export function challengeChoices(): [string, string][] {
  return CHALLENGE_APPETITE_OPTIONS.map(([id]) => [id, CHALLENGE_SHORT[id] ?? id]);
}

export function toneChoices(): [string, string][] {
  return COMMUNICATION_TONE_OPTIONS.map(([id]) => [id, TONE_SHORT[id] ?? id]);
}

export function learnCoursePath(
  studentId: string,
  courseId: string,
  extra?: { session?: string; kc?: string },
): string {
  const params = new URLSearchParams();
  if (extra?.session) params.set("session", extra.session);
  if (extra?.kc && !extra.session) params.set("kc", extra.kc);
  const query = params.toString();
  const path = `/learn/${studentId}/course/${courseId}`;
  return query ? `${path}?${query}` : path;
}

export function topicStars(unit: {
  completed_blocks?: number;
  first_try_blocks_count?: number;
  status?: string;
  mastery?: string;
  revealed_blocks_count?: number;
}): number {
  const blocks = unit.completed_blocks ?? 0;
  const first = unit.first_try_blocks_count ?? 0;
  const finished = unit.status === "completed" ? 1 : 0;
  const crown = finished && unit.mastery === "known" && (unit.revealed_blocks_count ?? 0) === 0 ? 1 : 0;
  return blocks * 10 + first * 5 + finished * 25 + crown * 15;
}

export function starBurst(
  knownIds: string[],
  blocks: { id: string; status: string; outcome?: string | null; attempts?: number }[],
): { award: number; firstTry: boolean; revealed: boolean; seen: string[] } {
  const seen = [...knownIds];
  let award = 0;
  let firstTry = false;
  for (const block of blocks) {
    if (block.status !== "completed" || seen.includes(block.id)) continue;
    seen.push(block.id);
    award += 10;
    if (block.outcome === "passed" && (block.attempts ?? 0) <= 1) {
      award += 5;
      firstTry = true;
    }
  }
  return { award, firstTry, revealed: blocks.some((block) => !knownIds.includes(block.id) && block.status === "completed" && block.outcome === "revealed"), seen };
}

export function friendlyStrength(text: string | undefined): string {
  const value = (text || "").trim();
  if (!value || /fragile|reveal|fail/i.test(value)) return "You finished this topic.";
  return value;
}

export const STAR_TOOLTIP =
  "10 stars for each finished block, 5 extra for a first-try pass, 25 for a finished topic, and 15 more when a topic is mastered with no reveals.";

function stepHeading(
  step: number,
  counted: number,
  block: { type_label?: string; short_title?: string } | undefined,
): string {
  const label = (block?.type_label || "").trim();
  const short = (block?.short_title || "").trim();
  const named = label ? `Step ${step + 1} of ${counted} — ${label}` : `Step ${step + 1} of ${counted}`;
  return short ? `${named} — ${short}` : named;
}

export function blockStepDivider(
  previousStep: number | undefined,
  step: number | undefined,
  blocks?: { index: number; type_label?: string; short_title?: string }[],
  totalBlocks?: number,
): string | null {
  if (step === undefined) return null;
  const counted = totalBlocks && totalBlocks > 0 ? totalBlocks : Math.max(step + 1, blocks?.length ?? 0);
  const heading = stepHeading(step, counted, blocks?.find((block) => block.index === step));
  if (previousStep === undefined) return step === 0 ? heading : null;
  if (step <= previousStep) return null;
  return `Step ${previousStep + 1} complete · Up next: ${heading}`;
}
