export type KcType = "factual" | "procedural" | "conceptual" | "causal" | "synthesis";

export type KcBlockType =
  | "topic_goal"
  | "mcq"
  | "case_study"
  | "socratic"
  | "curiosity"
  | "worked_example"
  | "spot_the_flaw"
  | "teach_back"
  | "retrieval_check";

export type KcBlock = {
  id: string;
  type: KcBlockType;
  data: Record<string, unknown>;
};

export type KcRecommendedBlock = {
  type: KcBlockType;
  reason?: string;
  focus?: string;
};

export type KcBlockProgress = {
  id: string;
  index: number;
  type: string;
  type_label: string;
  title: string;
  status: "completed" | "active" | "upcoming";
  outcome?: string | null;
  attempts?: number;
};

export type KcMisconception = { wrong_move: string; broken_kc: string };

export type KcTopicPair = { topic: string; goal: string };

export type KcComponent = {
  id: string;
  code: string;
  title: string;
  description: string;
  outline: string;
  topics: KcTopicPair[];
  kc_type: KcType | null;
  target: boolean;
  core_truth: string;
  rubric: string[];
  misconceptions: KcMisconception[];
  prerequisite_codes: string[];
  encompasses_codes: string[];
  type_fields: Record<string, unknown>;
  blocks?: KcBlock[];
  recommended_blocks?: KcRecommendedBlock[];
  marked_complete: boolean;
  missing: string[];
  history: string;
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
  allowed_block_types?: KcBlockType[];
  history: string;
  components: KcComponent[];
  patches: KcComponent[];
};

export type KcStructure = {
  groups: {
    components: {
      id: string;
      code: string;
      title: string;
      description: string;
      recommended_blocks?: KcRecommendedBlock[];
      blocks?: { type: string }[];
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
  outline?: string;
  topics?: KcTopicPair[];
  kc_type?: KcType | null;
  core_truth: string;
  rubric?: string[];
  misconceptions: KcMisconception[];
  prerequisite_codes: string[];
  encompasses_codes: string[];
  type_fields?: Record<string, unknown>;
  blocks?: KcBlock[];
  recommended_blocks?: KcRecommendedBlock[];
};

export type KcDraft =
  | {
      kind: "course";
      components: {
        code: string;
        title: string;
        description?: string;
        outline?: string;
        topics?: KcTopicPair[];
        recommended_blocks?: KcRecommendedBlock[];
      }[];
    }
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

export type KcProgressBlock = {
  id: string;
  type: string;
  type_label: string;
  status: "completed" | "active";
  outcome?: "passed" | "revealed";
  attempts?: number;
  rubric?: string;
};

export type KcProgress = {
  course_id: string;
  title: string;
  kind: string;
  minutes: number | null;
  known: number;
  total: number;
  percent: number;
  count_label: string;
  course_complete?: boolean;
  next_course?: { id: string; code: string; title: string } | null;
  units: {
    id: string;
    code: string;
    title: string;
    kc_type: string | null;
    summary?: string;
    patch: boolean;
    status: "completed" | "in_progress" | "not_started";
    mastery?: "" | "known" | "fragile";
    finished_blocks?: number;
    total_blocks?: number;
    blocks?: KcProgressBlock[];
    rubric?: string[];
    result?: {
      status: "known" | "fragile";
      rubric_met: string[];
      justification: string;
      strong: string;
      work_on: string;
    } | null;
  }[];
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

export type KcChatSummary = {
  id: string;
  student_id: string;
  student_display_name: string;
  course_id: string;
  course_code: string;
  course_title: string;
  kc_id: string;
  kc_code: string;
  kc_title: string;
  kc_type: string | null;
  recipe: string;
  step: number;
  step_label: string;
  status: string;
  score: number | null;
  created_at: string;
  updated_at: string;
  message_count: number;
};

export type KcChatDetail = {
  id: string;
  status: string;
  recipe: string;
  step: number;
  step_label: string;
  score: number | null;
  attempts: number;
  created_at: string;
  updated_at: string;
  student: { id: string; display_name: string };
  course: { id: string; code: string; title: string };
  component: { id: string; code: string; title: string; kc_type: string | null };
  messages: { id: string; role: "user" | "assistant"; content: string; seq: number; created_at: string }[];
  prompts: {
    id: string;
    session_id: string;
    message_id: string | null;
    seq: number;
    system_prompt: string;
    messages: unknown[];
    model: string;
    rubric_met?: string[];
    misconception?: string | null;
    created_at: string;
  }[];
};

export type KcDebugVariable = {
  name: string;
  value: string;
  layer?: string;
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
  total_blocks?: number;
  completed_blocks?: number;
  completion_pct?: number;
  active_block_index?: number;
  active_substep_label?: string;
  block_progress?: KcBlockProgress[];
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
