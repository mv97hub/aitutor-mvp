export type StudioClose = {
  close_style: "one" | "several";
  answer_style: "multiple_choice" | "essay" | "mixed";
  choice_mode: "predefined" | "dynamic" | null;
  items: { text: string }[];
  intent: string;
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
  close: StudioClose | null;
  moves: StudioMove[];
};

export type StudioUnit = {
  id: string;
  code: string;
  position: number;
  title: string;
  learning_goal: string;
  success_criterion: string;
  quests: StudioQuest[];
};

export type StudioPhaseName = "structure" | "goals" | "close" | "ready";

export type StudioPhase = {
  name: StudioPhaseName;
  label: "Structure" | "Goals" | "Close" | "Ready";
  open_codes: string[];
};

export type StudioStripPhase = {
  name: StudioPhaseName;
  label: "Structure" | "Goals" | "Close" | "Ready";
  filled: boolean;
  active: boolean;
};

export type StudioView = {
  name: StudioPhaseName;
  label: "Structure" | "Goals" | "Close" | "Ready";
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
  units: StudioUnit[];
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
  kind: "course" | "unit" | "quest" | "move";
  code: string;
  parent?: string | null;
  title?: string | null;
  learning_goal?: string | null;
  success_criterion?: string | null;
};

export type StudioMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  seq: number;
  proposal: { operations: StudioOperation[] } | null;
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
  const question = close.close_style === "one" ? "One question" : "Several questions";
  const answer =
    close.answer_style === "multiple_choice"
      ? "Multiple choice"
      : close.answer_style === "essay"
        ? "Essay"
        : "Mixed";
  if (close.answer_style === "essay") return `${question} · ${answer}`;
  const mode = close.choice_mode === "predefined" ? "Predefined choices" : "Dynamic choices";
  return `${question} · ${answer} · ${mode}`;
}
