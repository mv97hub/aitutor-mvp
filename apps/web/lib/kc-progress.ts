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

const STORED_FILLER = new Set([
  "the finished blocks held.",
  "a required block was revealed.",
  "none stored.",
  "use this on the next piece.",
  "look at this component again.",
  "known.",
  "fragile.",
]);

function storedSentence(text: string | undefined, hiddenAsFinished: boolean): string {
  const value = (text || "").trim();
  if (!value || STORED_FILLER.has(value.toLowerCase())) return "";
  if (/fragile|fail/i.test(value)) return hiddenAsFinished ? "You finished this topic." : "";
  return value;
}

export function finishedComponents<T extends { status?: string; mastery?: string }>(units: T[]): T[] {
  return units.filter((unit) => {
    const label = childComponentLabel(unit);
    return label === "Mastered" || label === "Completed";
  });
}

export function blockScore(unit: {
  finished_blocks?: number;
  completed_blocks?: number;
  total_blocks?: number;
}): string {
  const done = unit.finished_blocks ?? unit.completed_blocks ?? 0;
  const total = unit.total_blocks ?? 0;
  return total > 0 ? `${done} of ${total}` : "";
}

/** Accomplishment summary when there is one, otherwise what they showed. */
export function finishedSentence(
  unit: {
    code: string;
    what_was_strong?: string;
    strengths?: string;
    close_text?: string;
    result?: { strong?: string } | null;
  },
  accomplishments?: { component_code: string; summary?: string }[],
): string {
  const summary = (accomplishments ?? []).find((item) => item.component_code === unit.code)?.summary?.trim() || "";
  const showed = (unit.what_was_strong || unit.result?.strong || unit.strengths || unit.close_text || "").trim();
  return storedSentence(summary || showed, true);
}

export type PassedCourseRubric = { completed: string; struggled: string };

/** Two lines from the stored component result, and only after the course is passed. */
export function passedCourseRubric(course: {
  course_complete?: boolean;
  units?: {
    status?: string;
    mastery?: string;
    what_was_strong?: string;
    what_to_work_on?: string;
    result?: { strong?: string; work_on?: string } | null;
  }[];
}): PassedCourseRubric {
  const empty = { completed: "", struggled: "" };
  if (!course.course_complete) return empty;
  const finished = finishedComponents(course.units ?? []);
  const completed = finished
    .map((unit) => storedSentence(unit.result?.strong || unit.what_was_strong, false))
    .filter(Boolean)
    .join(" ");
  const struggled = finished
    .map((unit) => storedSentence(unit.result?.work_on || unit.what_to_work_on, false))
    .filter(Boolean)
    .join(" ");
  return { completed, struggled };
}

export type CourseTotals = {
  mastered: number;
  completed: number;
  inProgress: number;
  notStarted: number;
  blocksPassed: number;
  blocksRevealed: number;
  blocksNotYet: number;
};

export type BlockState = "Passed" | "Revealed" | "Not yet";

export type BlockRow = {
  id: string;
  name: string;
  type: string;
  state: BlockState;
  attempts: number;
  firstTry: boolean;
};

export type RevisitComponent = { code: string; title: string };

export type ComponentRecommendations = {
  workOn: string;
  misconceptions: string[];
  opportunities: string[];
};

type CountableBlock = {
  status?: string;
  outcome?: "passed" | "revealed" | null;
  attempts?: number;
  passed_on_first_try?: boolean;
};

function blockStateOf(block: CountableBlock): BlockState {
  if (block.status === "revealed" || block.outcome === "revealed") return "Revealed";
  if (block.status === "passed" || block.outcome === "passed" || block.status === "completed") return "Passed";
  return "Not yet";
}

function blockFacts(unit: {
  block_details?: CountableBlock[];
  blocks?: CountableBlock[];
  passed_blocks_count?: number;
  revealed_blocks_count?: number;
  total_blocks?: number;
}): { passed: number; revealed: number; notYet: number } {
  const details = unit.block_details ?? [];
  const blocks = details.length > 0 ? details : (unit.blocks ?? []);
  if (blocks.length > 0) {
    let passed = 0;
    let revealed = 0;
    let notYet = 0;
    for (const block of blocks) {
      const state = blockStateOf(block);
      if (state === "Passed") passed += 1;
      else if (state === "Revealed") revealed += 1;
      else notYet += 1;
    }
    return { passed, revealed, notYet };
  }
  const passed = unit.passed_blocks_count ?? 0;
  const revealed = unit.revealed_blocks_count ?? 0;
  const total = unit.total_blocks ?? 0;
  return { passed, revealed, notYet: Math.max(0, total - passed - revealed) };
}

function passedImmediately(block: CountableBlock, state: BlockState): boolean {
  if (state !== "Passed") return false;
  if (block.passed_on_first_try) return true;
  const attempts = block.attempts ?? 0;
  return attempts <= 1 && (block.outcome === "passed" || block.status === "passed" || block.status === "completed");
}

/** Component counts, then block counts. Patches stay out of both. */
export function courseTotals(units: KcProgressUnit[]): CourseTotals {
  const totals: CourseTotals = {
    mastered: 0,
    completed: 0,
    inProgress: 0,
    notStarted: 0,
    blocksPassed: 0,
    blocksRevealed: 0,
    blocksNotYet: 0,
  };
  for (const unit of units) {
    if (unit.patch) continue;
    const label = childComponentLabel(unit);
    if (label === "Mastered") totals.mastered += 1;
    else if (label === "Completed") totals.completed += 1;
    else if (label === "In Progress") totals.inProgress += 1;
    else totals.notStarted += 1;
    const facts = blockFacts(unit);
    totals.blocksPassed += facts.passed;
    totals.blocksRevealed += facts.revealed;
    totals.blocksNotYet += facts.notYet;
  }
  return totals;
}

/** Status plus passed and revealed counts. The of-total count stays with them. */
export function componentLine(unit: {
  status?: string;
  mastery?: string;
  total_blocks?: number;
  block_details?: KcBlockDetail[];
  blocks?: KcProgressBlock[];
  passed_blocks_count?: number;
  revealed_blocks_count?: number;
}): string {
  const label = childComponentLabel(unit);
  const facts = blockFacts(unit);
  const total = unit.total_blocks ?? (unit.block_details?.length || unit.blocks?.length || 0);
  const parts = [label, `${facts.passed} passed`, `${facts.revealed} revealed`];
  if (total > 0) parts.push(`${facts.passed + facts.revealed} of ${total}`);
  return parts.filter(Boolean).join(" · ");
}

/** One row per block. A revealed block stays revealed. First try only when it passed immediately. */
export function blockRows(unit: KcProgressUnit): BlockRow[] {
  const details = unit.block_details ?? [];
  if (details.length > 0) {
    return details.map((block, index) => {
      const state = blockStateOf(block);
      const preview = (block.prompt_preview || "").trim();
      const label = (block.label || "").trim();
      const name = preview || label || `Block ${block.index || index + 1}`;
      const type = label && label !== name ? label : block.block_type || label;
      return {
        id: block.block_id || String(block.index ?? index),
        name,
        type,
        state,
        attempts: block.attempts ?? 0,
        firstTry: passedImmediately(block, state),
      };
    });
  }
  return (unit.blocks ?? []).map((block, index) => {
    const state = blockStateOf(block);
    const name = block.type_label || block.type || `Block ${index + 1}`;
    return {
      id: block.id || String(index),
      name,
      type: block.type && block.type !== name ? block.type : block.type_label || block.type,
      state,
      attempts: block.attempts ?? 0,
      firstTry: passedImmediately(block, state),
    };
  });
}

/** Components to open again: fragile, or any block was revealed. */
export function courseRecommendations(units: KcProgressUnit[]): RevisitComponent[] {
  const items: RevisitComponent[] = [];
  const seen = new Set<string>();
  for (const unit of units) {
    if (unit.patch || seen.has(unit.code)) continue;
    if (unit.mastery !== "fragile" && blockFacts(unit).revealed === 0) continue;
    seen.add(unit.code);
    items.push({ code: unit.code, title: unit.title });
  }
  return items;
}

function keptText(text: string | null | undefined): string {
  const value = (text || "").trim();
  if (!value || STORED_FILLER.has(value.toLowerCase())) return "";
  return value;
}

/** Stored next steps for one component. No new model call. */
export function componentRecommendations(
  unit: {
    code: string;
    what_to_work_on?: string;
    result?: { work_on?: string } | null;
    student_misconceptions?: string[];
  },
  opportunities?: { component_code: string; summary?: string | null }[],
): ComponentRecommendations {
  const workOn = keptText(unit.what_to_work_on || unit.result?.work_on);
  const misconceptions: string[] = [];
  const seenMisc = new Set<string>();
  for (const item of unit.student_misconceptions ?? []) {
    const text = keptText(item);
    if (!text || seenMisc.has(text)) continue;
    seenMisc.add(text);
    misconceptions.push(text);
  }
  const lines: string[] = [];
  const seen = new Set<string>();
  for (const item of opportunities ?? []) {
    if (item.component_code !== unit.code) continue;
    const summary = keptText(item.summary);
    if (!summary || summary === workOn || seen.has(summary)) continue;
    seen.add(summary);
    lines.push(summary);
  }
  return { workOn, misconceptions, opportunities: lines };
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
