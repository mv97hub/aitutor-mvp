export type Student = {
  id: string;
  slug: string;
  display_name: string;
  age: number | null;
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

export type TutorProfile = {
  instructive: number;
  persona: string;
  lexicon: string;
  voice_override: boolean;
  metaphors: string;
  sidekick: string;
  struggle_window: string;
  anti_spoiler: boolean;
  one_question: boolean;
  use_interests: boolean;
  stay_on_course: boolean;
  growth_praise: boolean;
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
  age_band: string;
  standards_alignment: string;
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
  quest_type: string;
  prerequisite_codes: string[];
  competency_tags: string[];
  unit_number: number;
  unit_title: string;
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
  quest_type: string;
  prerequisite_codes: string[];
  competency_tags: string[];
  dinner_prompt: string;
  position: number;
};

export type CourseGoal = {
  position: number;
  learning_goal: string;
  success_criterion: string;
};

export type CourseClose = {
  kind: "essay" | "single" | "multi" | "none";
  question: string;
  items: { text: string; correct?: boolean }[];
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
  age_band: string;
  standards_alignment: string;
  description: string;
  audience: string;
  quest_count: number;
  goals_per_quest: number;
  quiz_minutes: number;
  competency_dictionary: Competency[];
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
  learning_goal: string;
  success_criterion: RubricRowInput[];
  requires_teach_back: boolean;
  beats: BeatOut[];
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
  current_beat_id: string | null;
  beats: BoardBeat[];
  messages: StoredMessage[];
  steps: BlockStep[];
  current_block: CurrentBlock | null;
};

export type ResultRow = {
  id: string;
  beat_id: string;
  beat_role: string;
  beat_position: number;
  quest_title: string;
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
  current_beat_id: string | null;
  beats: SessionBeat[];
  messages: StoredMessage[];
  results: ResultRow[];
  prompts: ModelPrompt[];
};

export type PromptBundle = {
  system_prompt: string;
  response_schema: Record<string, unknown>;
  temperature: number;
};
