import type {
  KcBlockDetail,
  KcMisconception,
} from "./kc.ts";

export type KcUnitStatus = "completed" | "in_progress" | "not_started";

export type KcProgressBlock = {
  id: string;
  type: string;
  type_label: string;
  status: "completed" | "active";
  outcome?: "passed" | "revealed";
  attempts?: number;
  rubric?: string;
};

export type KcProgressUnit = {
  id: string;
  code: string;
  title: string;
  description?: string;
  outline?: string;
  core_truth?: string;
  kc_type: string | null;
  summary?: string;
  patch: boolean;
  status: KcUnitStatus;
  mastery?: "" | "known" | "fragile";
  p_known?: number;
  finished_blocks?: number;
  completed_blocks?: number;
  total_blocks?: number;
  passed_blocks_count?: number;
  revealed_blocks_count?: number;
  first_try_blocks_count?: number;
  total_attempts?: number;
  started_at?: string | null;
  completed_at?: string | null;
  updated_at?: string | null;
  strengths?: string;
  what_was_strong?: string;
  weaknesses?: string;
  what_to_work_on?: string;
  close_text?: string;
  score_justification?: string;
  prerequisite_codes?: string[];
  dependent_codes?: string[];
  misconceptions?: KcMisconception[];
  student_misconceptions?: string[];
  blocks?: KcProgressBlock[];
  block_details?: KcBlockDetail[];
  rubric?: string[];
  result?: {
    status: "known" | "fragile";
    rubric_met: string[];
    justification: string;
    strong: string;
    work_on: string;
  } | null;
};

/** Finished means known or fragile. The known count stays separate. */
export function courseScore(units: KcProgressUnit[], known: number) {
  const targets = units.filter((unit) => !unit.patch);
  const total = targets.length;
  const finished = targets.filter((unit) => unit.status === "completed").length;
  const percent = total <= 0 ? 0 : Math.floor((finished * 100 + Math.floor(total / 2)) / total);
  return { percent, finished, total, known };
}

export function unitLine(unit: KcProgressUnit): string {
  const patch = unit.patch ? " patch" : "";
  if (unit.status === "completed" && (unit.mastery === "known" || unit.mastery === "fragile")) {
    return `${unit.mastery}${patch}`;
  }
  if (unit.status === "in_progress") {
    return `${unit.finished_blocks ?? 0} of ${unit.total_blocks ?? 0} blocks${patch}`;
  }
  const name = unit.summary || "No blocks yet";
  return unit.patch ? `${name} patch` : name;
}

export function unitsByStatus(units: KcProgressUnit[]) {
  return {
    completed: units.filter((unit) => unit.status === "completed"),
    in_progress: units.filter((unit) => unit.status === "in_progress"),
    not_started: units.filter((unit) => unit.status === "not_started"),
  };
}

/** Join course units onto network nodes by component code. */
export function statusByCode(units: KcProgressUnit[]): Record<string, KcUnitStatus> {
  return Object.fromEntries(units.map((unit) => [unit.code, unit.status]));
}

export function masteryByCode(units: KcProgressUnit[]): Record<string, string> {
  return Object.fromEntries(
    units
      .filter((unit) => unit.status === "completed" && (unit.mastery === "known" || unit.mastery === "fragile"))
      .map((unit) => [unit.code, unit.mastery as string]),
  );
}

export function networkStatusClass(
  status: KcUnitStatus | undefined,
  mastery?: string,
): string {
  if (status === "completed") {
    if (mastery === "fragile") return "is-completed is-fragile";
    return "is-completed";
  }
  if (status === "in_progress") return "is-in-progress";
  if (status === "not_started") return "is-not-started";
  return "";
}

export type ChildProgressLabel = "Mastered" | "Completed" | "In Progress";

/** Child-facing label. A finished component that is still fragile counts as Completed. */
export function childComponentLabel(unit: {
  status?: string;
  mastery?: string;
}): ChildProgressLabel | "" {
  if (unit.status === "completed" && unit.mastery === "known") return "Mastered";
  if (unit.status === "completed" || unit.mastery === "fragile" || unit.status === "fragile") {
    return "Completed";
  }
  if (unit.status === "in_progress") return "In Progress";
  return "";
}

export function childNoteByCode(units: KcProgressUnit[]): Record<string, string> {
  return Object.fromEntries(
    units
      .map((unit) => [unit.code, childComponentLabel(unit)] as const)
      .filter((entry) => entry[1] !== ""),
  );
}

type PortfolioCourse = {
  started?: boolean;
  course_complete?: boolean;
  component_count?: number;
  completed_count?: number;
  known_count?: number;
  fragile_count?: number;
  in_progress_count?: number;
  last_active_at?: string | null;
};

function courseHasStarted(course: PortfolioCourse): boolean {
  const done = course.completed_count ?? (course.known_count ?? 0) + (course.fragile_count ?? 0);
  return Boolean(course.started) || done > 0 || (course.in_progress_count ?? 0) > 0;
}

export function portfolioCourseStatus(course: PortfolioCourse): ChildProgressLabel | "" {
  if (!courseHasStarted(course)) return "";
  const total = course.component_count ?? 0;
  const done = course.completed_count ?? (course.known_count ?? 0) + (course.fragile_count ?? 0);
  const finished = Boolean(course.course_complete) || (total > 0 && done >= total);
  if (!finished) return "In Progress";
  if ((course.fragile_count ?? 0) > 0) return "Completed";
  return "Mastered";
}

export function portfolioCount(course: PortfolioCourse): string {
  const total = course.component_count ?? 0;
  const done = course.completed_count ?? (course.known_count ?? 0) + (course.fragile_count ?? 0);
  return `${done} of ${total}`;
}

/** Started courses first. Relative order is kept when activity matches. */
export function coursesStartedFirst<T extends PortfolioCourse>(courses: T[]): T[] {
  return courses
    .map((course, index) => ({ course, index }))
    .sort((a, b) => {
      const byStart = Number(courseHasStarted(b.course)) - Number(courseHasStarted(a.course));
      if (byStart !== 0) return byStart;
      const byTime = (b.course.last_active_at || "").localeCompare(a.course.last_active_at || "");
      if (byTime !== 0) return byTime;
      return a.index - b.index;
    })
    .map((item) => item.course);
}
