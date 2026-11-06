export type KcType = "factual" | "procedural" | "conceptual" | "causal" | "synthesis";

export type KcMisconception = { wrong_move: string; broken_kc: string };

export type KcComponent = {
  id: string;
  code: string;
  title: string;
  description: string;
  kc_type: KcType | null;
  target: boolean;
  core_truth: string;
  rubric: string[];
  misconceptions: KcMisconception[];
  prerequisite_codes: string[];
  encompasses_codes: string[];
  type_fields: Record<string, unknown>;
  marked_complete: boolean;
  missing: string[];
};

export type KcCourse = {
  id: string;
  code: string;
  title: string;
  description: string;
  audience: string;
  kind: "mastery" | "time_boxed" | "curiosity";
  minutes: number | null;
  ready: boolean;
  components: KcComponent[];
  patches: KcComponent[];
};

export type KcStructure = {
  groups: {
    kc_type: string;
    components: {
      id: string;
      code: string;
      title: string;
      description: string;
      kc_type: string | null;
      missing: string[];
      marked_complete: boolean;
    }[];
  }[];
};

export type KcNetwork = {
  nodes: { id: string; code: string; title: string; kc_type: string | null; target: boolean; patch: boolean }[];
  edges: { from_code: string; to_code: string; kind: "prerequisite_of" | "encompasses" }[];
};

export type KcComponentDraft = {
  kind: "component";
  code: string;
  title: string;
  description?: string;
  kc_type: KcType;
  core_truth: string;
  rubric: string[];
  misconceptions: KcMisconception[];
  prerequisite_codes: string[];
  encompasses_codes: string[];
  type_fields: Record<string, unknown>;
};

export type KcDraft =
  | { kind: "course"; components: { code: string; title: string; description?: string }[] }
  | KcComponentDraft;

export type KcCard = {
  role: "fastest" | "patch" | "stretch";
  label: string;
  id: string;
  code: string;
  title: string;
  kc_type: string | null;
  reason: string;
};

export type KcProgress = {
  course_id: string;
  title: string;
  kind: string;
  minutes: number | null;
  known: number;
  total: number;
  count_label: string;
  ring: { id: string; code: string; title: string; kc_type: string | null; status: "known" | "fragile" | "not_started" }[];
  cards: KcCard[];
};

export type KcTutorCourse = {
  id: string;
  code: string;
  title: string;
  description: string;
  audience: string;
  kind: string;
  minutes: number | null;
};

export type KcTutorSession = {
  id: string;
  course_id: string;
  kc_id: string;
  code: string;
  title: string;
  kc_type: string | null;
  recipe: string;
  step: number;
  step_label: string;
  status: string;
  score: number | null;
  needs_speech: boolean;
  choice: { prompt: string; choices: { id: string; text: string }[] } | null;
  reply?: string;
  passed?: boolean;
  redirect: { id: string; code: string; title: string } | null;
  messages: { id: string; role: "user" | "assistant"; content: string; seq: number }[];
};

export const AUDIENCES = ["6-8", "9-11", "12-14", "15-17"] as const;
export const KINDS = [
  { id: "mastery", label: "Mastery" },
  { id: "time_boxed", label: "Time boxed" },
  { id: "curiosity", label: "Curiosity" },
] as const;
export type KcCreatorMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  seq: number;
  draft: KcComponentDraft | null;
  applied: boolean;
};

export type KcCreatorThread = {
  node_id: string;
  mirror: string;
  messages: KcCreatorMessage[];
  draft: KcComponentDraft | null;
};

export const TYPE_LABELS: Record<string, string> = {
  factual: "Factual",
  procedural: "Procedural",
  conceptual: "Conceptual principle",
  causal: "Causal or historical",
  synthesis: "Synthesis",
  unset: "No type yet",
};
