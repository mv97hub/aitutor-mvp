import type { KcTutorConfig } from "./kc-tutor-config";

export type ChildProfile = {
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
};

export type Student = {
  id: string;
  slug: string;
  display_name: string;
  age: number | null;
  age_band: string;
  reading_level: string;
  modality: string;
  interests: string[];
  grade_band?: string;
  response_length?: string;
  expression_style?: string;
  explanation_style?: string;
  challenge_appetite?: string;
  communication_tone?: string;
  learning_support?: string;
  interest_tags?: string[];
  child_profile?: ChildProfile;
  tutor_persona: string;
  tutor_lexicon: string;
  tutor_metaphors: string;
  tutor_sidekick: string;
  tutor_socratic_strictness: string;
  tutor_struggle_window: string;
  tutor_anti_spoiler: boolean;
  tutor_pacing: string;
  preferred_tutor_profile_id?: string | null;
};

export type TutorProfile = {
  id?: string;
  name?: string;
  slug?: string;
  description?: string;
  avatar_preset?: string;
  avatar_url?: string | null;
  is_default?: boolean;
  instructive: number;
  persona: string;
  lexicon: string;
  vocabulary_register?: string;
  interest_weaving?: string;
  humor_and_wit?: string;
  voice_override: boolean;
  metaphors: string;
  sidekick: string;
  struggle_window: string;
  anti_spoiler: boolean;
  one_question: boolean;
  use_interests: boolean;
  stay_on_course: boolean;
  growth_praise: boolean;
  misconception_policy: string;
  self_explanation: boolean;
  enrichment: string;
  kc_tutor_config?: KcTutorConfig;
  updated_at?: string;
};

export type ProfileDefaults = {
  age_band: string;
  reading_level: string;
  modality: string;
  interests: string[];
  tutor_persona: string;
  tutor_lexicon: string;
  tutor_metaphors: string;
  tutor_sidekick: string;
  tutor_socratic_strictness: string;
  tutor_struggle_window: string;
  tutor_anti_spoiler: boolean;
  tutor_pacing: string;
};

export type CourseSummary = {
  id: string;
  code: string;
  title: string;
  description: string;
  audience: string;
  quest_count: number;
  goals_per_quest: number;
  quiz_minutes: number;
};

export type QuestListItem = {
  id: string;
  code: string;
  title: string;
  position: number;
};

export type Competency = {
  code: string;
  description: string;
};

export type QuestNode = {
  id: string;
  code: string;
  title: string;
  position: number;
};

export type CourseGoal = {
  position: number;
  learning_goal: string;
  success_criterion: string;
};

export type CourseClose = {
  close_style: string;
  answer_style: string;
  choice_mode: string | null;
  items: { text: string; correct?: boolean }[];
  questions: { text: string; kind?: "single" | "multiple"; choices?: { text: string; correct?: boolean }[] }[];
  intent: string;
  selection: string | null;
};

export type CatalogQuest = {
  id: string;
  code: string;
  title: string;
  position: number;
  goals: CourseGoal[];
  close: CourseClose | null;
};

export type CourseTree = {
  id: string;
  code: string;
  title: string;
  description: string;
  audience: string;
  quest_count: number;
  goals_per_quest: number;
  quiz_minutes: number;
  quests: CatalogQuest[];
};

export type RubricRowInput = {
  id: string;
  text: string;
  weight: number;
};

export type HintLadder = {
  nudge: string;
  analogy: string;
  scaffold: string;
};

export type TrapInput = {
  id: string;
  trap: string;
  note: string;
};

export type QuizChoiceInput = {
  id: string;
  text: string;
  misconception: string;
};

export type QuizInput = {
  type: "single" | "multi" | "flaw" | "order";
  prompt: string;
  choices: QuizChoiceInput[];
  answer: string | string[];
  explain: boolean;
  misconception: string;
};

export type BeatOut = {
  id: string;
  position: number;
  role: string;
  bloom_level: string;
  cognitive_load: string;
  prompt: string;
  rubric: RubricRowInput[];
  misconception_map: TrapInput[];
  hint_ladder: HintLadder;
  widget: QuizInput | null;
};

export type QuestDetail = QuestNode & {
  course_id: string;
  goals: CourseGoal[];
  close: CourseClose | null;
};

export type BoardResult = {
  id: string;
  score: number;
  passed: boolean;
  feedback: string;
  created_at: string;
};

export type BoardBeat = {
  id: string;
  position: number;
  role: string;
  latest_result: BoardResult | null;
};

export type StoredMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  client_id: string | null;
  created_at: string;
};

export type RubricRow = {
  id: string;
  text: string;
  weight: number;
  met: boolean;
};

export type QuizChoice = {
  id: string;
  text: string;
};

export type KidQuiz = {
  type: "single" | "multi" | "flaw" | "order";
  prompt: string;
  choices: QuizChoice[];
  explain: boolean;
};

export type TriangleSide = {
  label: string;
  length: number;
};

export type TriangleAngle = {
  label: string;
  degrees: number;
};

export type TriangleDiagram = {
  kind: "triangle";
  sides: TriangleSide[];
  angles: TriangleAngle[];
  right_angle: boolean;
};

export type BlockStep = {
  id: string;
  position: number;
  kind: string;
  title: string;
  state: string;
};

export type CurrentBlock = {
  id: string;
  kind: string;
  title: string;
  objective: string;
  tutor_prompt: string;
  rubric: RubricRow[];
  hint_tier: "nudge" | "analogy" | "scaffold";
  hint_text: string;
  quiz: KidQuiz | null;
};

export type Board = {
  id: string;
  status: string;
  created_at: string;
  updated_at: string;
  student: Student;
  course_code: string;
  course_title: string;
  quest_id: string;
  quest_code: string;
  quest_title: string;
  enduring_understanding: string;
  current_goal_id: string | null;
  close_started: boolean;
  messages: StoredMessage[];
  steps: BlockStep[];
  current_block: CurrentBlock | null;
};

export type ResultRow = {
  id: string;
  goal_id: string | null;
  role: string;
  position: number;
  quest_title: string;
  criterion: string;
  answer: string;
  score: number;
  passed: boolean;
  feedback: string;
  misconception: string | null;
  hint_tier: string | null;
  created_at: string;
};

export type SessionSummary = {
  id: string;
  student_id: string;
  student_display_name: string;
  quest_id: string;
  quest_code: string;
  quest_title: string;
  course_title: string;
  status: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  result_count: number;
};

export type ModelPrompt = {
  id: string;
  session_id: string;
  message_id: string | null;
  seq: number;
  system_prompt: string;
  messages: unknown[];
  model: string;
  created_at: string;
};

export type SessionQuest = {
  id: string;
  code: string;
  title: string;
  course_code: string;
  course_title: string;
};

export type SessionBeat = {
  id: string;
  position: number;
  role: string;
};

export type SessionDetail = {
  id: string;
  status: string;
  created_at: string;
  updated_at: string;
  student: Student;
  quest: SessionQuest;
  current_goal_id: string | null;
  close_started: boolean;
  messages: StoredMessage[];
  results: ResultRow[];
  prompts: ModelPrompt[];
};

export type PromptBundle = {
  system_prompt: string;
  response_schema: Record<string, unknown>;
  temperature: number;
};
