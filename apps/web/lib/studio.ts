export type StudioClose = {
  close_style: "one" | "several";
  answer_style: "multiple_choice" | "essay" | "mixed";
  choice_mode: "predefined" | "dynamic" | null;
  items: { text: string; correct?: boolean }[];
  questions: { text: string; kind?: "single" | "multiple"; choices?: { text: string; correct?: boolean }[] }[];
  intent: string;
  selection?: "single" | "multi" | null;
};

export type StudioGoal = {
  position: number;
  learning_goal: string;
  success_criterion: string;
};

export type StudioMove = {
  id: string;
  code: string;
  position: number;
  title: string;
  learning_goal: string;
  success_criterion: string;
};

export type StudioQuest = {
  id: string;
  code: string;
  position: number;
  title: string;
  learning_goal: string;
  success_criterion: string;
  goals: StudioGoal[];
  close: StudioClose | null;
  moves: StudioMove[];
};

export type StudioPhaseName = "quests" | "goals" | "close" | "ready";

export type StudioPhase = {
  name: StudioPhaseName;
  label: "Quests" | "Goals/Success Criteria" | "Close" | "Ready";
  open_codes: string[];
};

export type StudioStripPhase = {
  name: StudioPhaseName;
  label: "Quests" | "Goals/Success Criteria" | "Close" | "Ready";
  filled: boolean;
  active: boolean;
};

export type StudioView = {
  name: StudioPhaseName;
  label: "Quests" | "Goals/Success Criteria" | "Close" | "Ready";
  codes: string[];
};

export type StudioCourse = {
  id: string;
  code: string;
  title: string;
  audience: string;
  focus: string;
  theme: string;
  depth: "survey" | "standard" | "go_deep";
  quiz_minutes: 2 | 5 | 10;
  sources: string;
  schema_version: number;
  close_default: StudioClose;
  ready: boolean;
  gaps: string[];
  phase: StudioPhase;
  strip: StudioStripPhase[];
  view: StudioView;
  quests: StudioQuest[];
  quest_count: number;
  goals_per_quest: number;
  undo: boolean;
  stage: StudioPhase;
  stage_strip: StudioStripPhase[];
  stage_view: StudioView;
  stage_gaps: string[];
  can_advance: boolean;
  can_push: boolean;
  updated_at: string;
};

export type StudioSummary = {
  id: string;
  code: string;
  title: string;
  updated_at: string;
};

export type StudioOperation = {
  op: "add" | "update" | "remove";
  kind: "course" | "quest" | "move";
  code: string;
  parent?: string | null;
  title?: string | null;
  learning_goal?: string | null;
  success_criterion?: string | null;
  position?: number | null;
};

export type StudioMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  seq: number;
  proposal: { operations: StudioOperation[]; phase?: StudioPhaseName } | null;
  applied: boolean;
  created_at: string;
};

export type StudioSettings = {
  model: string;
  options: string[];
};

export const DEPTHS = [
  { value: "survey", label: "Survey" },
  { value: "standard", label: "Standard" },
  { value: "go_deep", label: "Go deep" },
] as const;

export const AGE_BANDS = ["6-8", "9-11", "12-14", "15-17"] as const;

export const QUIZ_MINUTES = [2, 5, 10] as const;

export function describeOperation(op: StudioOperation): string {
  const title = op.title ? `: ${op.title}` : "";
  if (op.op === "remove") return `Remove ${op.code}`;
  if (op.op === "add") return `Add ${op.kind} ${op.code}${title}`;
  return `Update ${op.code}${title}`;
}

export function closeSummary(close: StudioClose): string {
  const count = close.questions?.length ?? 0;
  const question = count === 0 ? "No questions" : count === 1 ? "One question" : "Several questions";
  if (count === 0) return "No questions";
  const kinds = new Set((close.questions ?? []).map((item) => (item.kind === "multiple" ? "multiple" : "single")));
  if (kinds.size > 1) return `${question} · Mixed`;
  if (kinds.has("multiple")) return `${question} · Multiple choice`;
  return `${question} · Single choice`;
}
