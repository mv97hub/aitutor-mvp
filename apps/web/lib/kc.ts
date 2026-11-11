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
  | "retrieval_check"
  | "explanation";

export type KcBlock = {
  id: string;
  type: KcBlockType;
  data: Record<string, unknown>;
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
  intake: KcIntake;
  brief: string;
  history: string;
  components: KcComponent[];
  patches: KcComponent[];
};

export type KcStructure = {
  groups: {
    title?: string;
    unit_index?: number | null;
    components: {
      id: string;
      code: string;
      title: string;
      description: string;
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
};

export type KcCourseDraft = {
  kind: "course";
  components: {
    code: string;
    title: string;
    description: string;
    prerequisite_codes: string[];
    standards?: string[];
    extension?: boolean;
    unit?: string;
    position?: number;
  }[];
};

export type KcDepth = "intro" | "standard" | "deep" | "curriculum";
export type KcReadingLevel = "easier" | "age" | "stronger";
export type KcUse = "" | "enrichment" | "school_support" | "test_prep";

export type KcIntake = {
  reading_level: KcReadingLevel;
  depth: KcDepth;
  component_count: number | null;
  use: KcUse;
  align_syllabus?: boolean;
  subject?: string;
  standard: string;
  standard_grade: string;
  standard_name: string;
  standard_text: string;
  starting_point: string;
  must_cover: string;
  must_avoid: string;
  interests: string;
  misconceptions_seen: string;
  source_text: string;
  source_text_cut?: boolean;
  standard_text_cut?: boolean;
};

export type KcStatement = {
  code: string;
  text: string;
};

export type KcCoverageStatus = "missing" | "light" | "covered";

export type KcCoverage = {
  rows: {
    code: string;
    text: string;
    components: string[];
    status: KcCoverageStatus;
    once_without_review: boolean;
  }[];
  gaps: string[];
  light: string[];
  once_without_review: string[];
  extensions: string[];
};

export type KcBlueprintComponent = {
  code: string;
  title: string;
  summary: string;
  prerequisites: string[];
  standards?: string[];
  extension?: boolean;
};

export type KcBlueprintUnit = {
  title: string;
  summary: string;
  components: KcBlueprintComponent[];
};

export type KcBlueprint = {
  outcomes: string[];
  units: KcBlueprintUnit[];
};

export type KcPipelineStage = "brief" | "blueprint" | "unit" | "review";

export type KcPipelineNext = { stage: KcPipelineStage; unit: number | null } | null;

export type KcReviewCheck = { name: string; result: "ok" | "fixed" | "issue"; note: string };

export type KcPipeline = {
  stage: "brief" | "questions" | "standards" | "blueprint" | "edit_blueprint" | "units" | "review" | "draft";
  next: KcPipelineNext;
  brief: string;
  questions: string[];
  answers: { question: string; answer: string }[];
  standards: KcStatement[];
  standards_source: string;
  coverage: KcCoverage | null;
  blueprint: KcBlueprint | null;
  approved: boolean;
  units_total: number;
  units_done: number;
  descriptions: Record<string, string>;
  review: {
    checks: KcReviewCheck[];
    revised: string[];
    added: string[];
    outcomes_changed: boolean;
  } | null;
  pushed: boolean;
  missing: string[];
  draft: KcCourseDraft | null;
};

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

export type KcBlockDetail = {
  index: number;
  block_id: string;
  block_type: string;
  label: string;
  prompt_preview: string;
  rubric_line: string;
  counts_toward_mastery: boolean;
  status: "passed" | "revealed" | "active" | "upcoming";
  outcome: "passed" | "revealed" | null;
  attempts: number;
  max_retries: number | null;
  passed_on_first_try: boolean;
  eliminated_choices: string[];
};

export type KcAccomplishmentItem = {
  component_id: string | number;
  component_code: string;
  component_title: string;
  kind: "strength" | "mastered" | "first_try_streak";
  summary: string;
  detail: string | null;
};

export type KcOpportunityItem = {
  component_id: string | number;
  component_code: string;
  component_title: string;
  kind: "weakness" | "revealed_block" | "misconception" | "fragile_prerequisite" | "in_progress";
  summary: string;
  detail: string | null;
};

export type KcProgress = {
  course_id: string;
  title: string;
  description?: string;
  audience?: string;
  kind: string;
  minutes: number | null;
  course?: {
    id: string;
    code: string;
    title: string;
    description: string;
    audience: string;
    kind: string;
    minutes: number | null;
  };
  known: number;
  total: number;
  total_count?: number;
  completed_count?: number;
  known_count?: number;
  fragile_count?: number;
  in_progress_count?: number;
  not_started_count?: number;
  percent: number;
  completion_percent?: number;
  count_label: string;
  course_complete?: boolean;
  next_course?: { id: string; code: string; title: string } | null;
  prerequisite_codes?: string[];
  unlocked?: boolean;
  total_blocks_count?: number;
  completed_blocks_count?: number;
  first_try_pass_count?: number;
  stars?: number;
  star_block?: number;
  star_first_try?: number;
  star_topic?: number;
  star_crown?: number;
  finished_topic_count?: number;
  crown_topic_count?: number;
  last_active_at?: string | null;
  accomplishments?: KcAccomplishmentItem[];
  opportunities?: KcOpportunityItem[];
  edges?: { from_code: string; to_code: string; kind: "prerequisite_of" | "encompasses" }[];
  units: {
    id: string;
    code: string;
    title: string;
    description?: string;
    outline?: string;
    core_truth?: string;
    kc_type: string | null;
    summary?: string;
    patch: boolean;
    status: "completed" | "in_progress" | "not_started";
    mastery?: "" | "known" | "fragile";
    child_status?: string;
    practice_bonus?: boolean;
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
  component_count?: number;
  completed_count?: number;
  known_count?: number;
  fragile_count?: number;
  in_progress_count?: number;
  not_started_count?: number;
  percent?: number;
  known_percent?: number;
  prerequisite_codes?: string[];
  unlocked?: boolean;
  total_blocks_count?: number;
  completed_blocks_count?: number;
  first_try_pass_count?: number;
  stars?: number;
  star_block?: number;
  star_first_try?: number;
  star_topic?: number;
  star_crown?: number;
  finished_topic_count?: number;
  crown_topic_count?: number;
  course_complete?: boolean;
  started?: boolean;
  current_topic?: {
    id: string;
    code: string;
    title: string;
    status: string;
    child_status: string;
    completed_blocks: number;
    total_blocks: number;
  } | null;
  tutor?: {
    id: string;
    name: string;
    description: string;
    avatar_preset: string;
    avatar_url?: string | null;
    is_default?: boolean;
    source?: "course" | "preferred" | "default";
  } | null;
  last_active_at?: string | null;
  accomplishments_preview?: KcAccomplishmentItem[];
  opportunities_preview?: KcOpportunityItem[];
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
  safety_event_count?: number;
  unreviewed_safety_count?: number;
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
  token_usage?: KcTokenUsage;
};

export type KcTokenCounts = {
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
  total_tokens: number;
};

export type KcTokenTurn = KcTokenCounts & {
  id: string;
  created_at: string;
  kind: "speak" | "answer" | string;
  model: string;
  message_id?: string | null;
};

export type KcTokenUsage = {
  total: KcTokenCounts;
  turns: KcTokenTurn[];
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
  active_block_type?: string;
  active_substep?: string;
  active_substep_label?: string;
  block_progress?: KcBlockProgress[];
  reply?: string;
  passed?: boolean;
  tutor_profile_id?: string;
  tutor_name?: string;
  tutor_slug?: string;
  tutor_description?: string;
  avatar_preset?: string;
  avatar_url?: string | null;
  redirect: { id: string; code: string; title: string } | null;
  messages: { id: string; role: "user" | "assistant"; content: string; seq: number; step?: number }[];
};

export const AUDIENCES = ["6-8", "9-11", "12-14", "15-17"] as const;
export const KINDS = [
  { id: "mastery", label: "Mastery" },
  { id: "time_boxed", label: "Time boxed" },
  { id: "curiosity", label: "Curiosity" },
] as const;
export const READING_LEVELS = [
  { id: "easier", label: "Easier than the age band" },
  { id: "age", label: "Matches the age band" },
  { id: "stronger", label: "A stronger reader" },
] as const;
export const DEPTHS = [
  { id: "intro", label: "Quick intro" },
  { id: "standard", label: "Standard" },
  { id: "deep", label: "Deep dive" },
  { id: "curriculum", label: "Match curriculum (1 component per topic)" },
] as const;
export const COURSE_USES = [
  { id: "", label: "Not set" },
  { id: "enrichment", label: "Enrichment" },
  { id: "school_support", label: "School support" },
  { id: "test_prep", label: "Test prep" },
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
