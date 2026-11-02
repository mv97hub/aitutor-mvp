export type Student = {
  id: string;
  slug: string;
  display_name: string;
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
};

export type LessonPlanSummary = {
  id: string;
  slug: string;
  title: string;
  is_active: boolean;
  updated_at: string;
  topic_count: number;
};

export type AdminCheckpoint = {
  id: string;
  kind: string;
  position: number;
  tutor_prompt: string;
  rubric: string | null;
  pass_criteria: string | null;
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
  } | null;
};
