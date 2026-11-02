export type Student = {
  id: string;
  slug: string;
  display_name: string;
  age: number | null;
};

export type BoardResult = {
  id: string;
  score: number;
  passed: boolean;
  feedback: string;
  created_at: string;
};

export type BoardCheckpoint = {
  id: string;
  kind: string;
  position: number;
  latest_result: BoardResult | null;
};

export type BoardTopic = {
  id: string;
  title: string;
  position: number;
  learning_goal: string;
  checkpoints: BoardCheckpoint[];
};

export type StoredMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  client_id: string | null;
  created_at: string;
};

export type Board = {
  id: string;
  status: string;
  created_at: string;
  updated_at: string;
  student: Student;
  lesson_title: string;
  lesson_plan_id: string;
  current_topic_id: string | null;
  current_checkpoint_id: string | null;
  topics: BoardTopic[];
  messages: StoredMessage[];
  steps: BlockStep[];
  current_block: CurrentBlock | null;
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

export type LessonPlanSummary = {
  id: string;
  slug: string;
  title: string;
  is_active: boolean;
  updated_at: string;
  topic_count: number;
  age_min: number | null;
  age_max: number | null;
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

export type AdminCheckpoint = {
  id: string;
  kind: string;
  position: number;
  tutor_prompt: string;
  rubric: string | null;
  pass_criteria: string | null;
  objective: string | null;
  rubric_rows: RubricRowInput[];
  hint_ladder: HintLadder;
  pass_score: number;
  quiz: QuizInput | null;
};

export type AdminTopic = {
  id: string;
  title: string;
  position: number;
  learning_goal: string;
  tutor_instructions: string;
  checkpoints: AdminCheckpoint[];
};

export type LessonPlan = {
  id: string;
  slug: string;
  title: string;
  preamble: string;
  is_active: boolean;
  age_min: number | null;
  age_max: number | null;
  created_at: string;
  updated_at: string;
  topics: AdminTopic[];
};

export type ResultRow = {
  id: string;
  checkpoint_id: string;
  topic_title: string;
  checkpoint_kind: string;
  checkpoint_position: number;
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
  lesson_plan_id: string;
  lesson_title: string;
  status: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  result_count: number;
};

export type ModelPrompt = {
  id: string;
  session_id: string;
  seq: number;
  system_prompt: string;
  messages: unknown[];
  model: string;
  created_at: string;
};

export type SessionDetail = {
  id: string;
  status: string;
  created_at: string;
  updated_at: string;
  student: Student;
  lesson_plan: LessonPlan;
  current_topic_id: string | null;
  current_checkpoint_id: string | null;
  messages: StoredMessage[];
  results: ResultRow[];
};

export type OutlineCheckpoint = {
  kind: string;
  position: number;
  state: string;
};

export type OutlineTopic = {
  title: string;
  position: number;
  checkpoints: OutlineCheckpoint[];
};

export type LessonContext = {
  session_id: string;
  status: string;
  student_display_name: string;
  lesson_title: string;
  preamble: string;
  topic_count: number;
  outline: OutlineTopic[];
  current_topic: {
    title: string;
    position: number;
    learning_goal: string;
    tutor_instructions: string;
  } | null;
  current_checkpoint: {
    kind: string;
    position: number;
    checkpoints_in_topic: number;
    tutor_prompt: string;
    rubric: string | null;
    pass_criteria: string | null;
    objective: string | null;
    rubric_rows: { id: string; text: string; weight: number }[];
    hint_tier: string | null;
    hint_text: string;
    pass_score: number;
    quiz: (QuizInput & { choices: { id: string; text: string; misconception?: string }[] }) | null;
    widget_grade: {
      correct: boolean;
      score: number;
      passed: boolean;
      misconception: string | null;
      choice_ids: string[];
      explanation: string;
    } | null;
  } | null;
};
