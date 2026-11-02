from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class StudentOut(BaseModel):
    id: UUID
    slug: str
    display_name: str
    age: int | None = None


class StudentCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    age: int = Field(ge=4, le=18)


class LessonPlanCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    preamble: str = ""
    is_active: bool = False
    age_min: int | None = Field(default=None, ge=4, le=18)
    age_max: int | None = Field(default=None, ge=4, le=18)


class LessonPlanPatch(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    preamble: str = ""
    is_active: bool
    age_min: int | None = Field(default=None, ge=4, le=18)
    age_max: int | None = Field(default=None, ge=4, le=18)


class TopicCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    learning_goal: str = Field(min_length=1)
    tutor_instructions: str = Field(min_length=1)


class TopicPatch(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    learning_goal: str = Field(min_length=1)
    tutor_instructions: str = Field(min_length=1)


class RubricRowIn(BaseModel):
    id: str = ""
    text: str = ""
    weight: int = Field(default=1, ge=0, le=100)


class HintLadderIn(BaseModel):
    nudge: str = ""
    analogy: str = ""
    scaffold: str = ""


class QuizChoiceIn(BaseModel):
    id: str = ""
    text: str = ""
    misconception: str = ""


class QuizIn(BaseModel):
    type: Literal["single", "multi", "flaw", "order"]
    prompt: str = ""
    choices: list[QuizChoiceIn] = Field(default_factory=list)
    answer: str | list[str] = ""
    explain: bool = False
    misconception: str = ""


class CheckpointWrite(BaseModel):
    kind: Literal["teach", "practice", "quiz", "discovery", "teach_back"]
    tutor_prompt: str = Field(min_length=1)
    rubric: str = ""
    pass_criteria: str = ""
    objective: str = ""
    rubric_rows: list[RubricRowIn] = Field(default_factory=list)
    hint_ladder: HintLadderIn = Field(default_factory=HintLadderIn)
    pass_score: int = Field(default=70, ge=0, le=100)
    quiz: QuizIn | None = None


class MoveBody(BaseModel):
    direction: Literal["up", "down"]


class LessonPlanSummary(BaseModel):
    id: UUID
    slug: str
    title: str
    is_active: bool
    updated_at: datetime
    topic_count: int
    age_min: int | None = None
    age_max: int | None = None


class BoardResult(BaseModel):
    id: UUID
    score: int
    passed: bool
    feedback: str
    created_at: datetime


class BoardCheckpoint(BaseModel):
    id: UUID
    kind: str
    position: int
    latest_result: BoardResult | None


class BoardTopic(BaseModel):
    id: UUID
    title: str
    position: int
    learning_goal: str
    checkpoints: list[BoardCheckpoint]


class MessageOut(BaseModel):
    id: UUID
    role: str
    content: str
    client_id: str | None
    created_at: datetime


class RubricRowOut(BaseModel):
    id: str
    text: str
    weight: int
    met: bool


class QuizChoiceOut(BaseModel):
    id: str
    text: str


class QuizOut(BaseModel):
    type: Literal["single", "multi", "flaw", "order"]
    prompt: str
    choices: list[QuizChoiceOut]
    explain: bool


class BlockStep(BaseModel):
    id: UUID
    position: int
    kind: str
    title: str
    state: str


class CurrentBlock(BaseModel):
    id: UUID
    kind: str
    title: str
    objective: str
    tutor_prompt: str
    rubric: list[RubricRowOut]
    hint_tier: Literal["nudge", "analogy", "scaffold"]
    hint_text: str
    quiz: QuizOut | None


class BoardOut(BaseModel):
    id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    student: StudentOut
    lesson_title: str
    lesson_plan_id: UUID
    current_topic_id: UUID | None
    current_checkpoint_id: UUID | None
    topics: list[BoardTopic]
    messages: list[MessageOut]
    steps: list[BlockStep] = Field(default_factory=list)
    current_block: CurrentBlock | None = None


class AdminCheckpoint(BaseModel):
    id: UUID
    kind: str
    position: int
    tutor_prompt: str
    rubric: str | None
    pass_criteria: str | None
    objective: str | None = None
    rubric_rows: list[dict] = Field(default_factory=list)
    hint_ladder: dict = Field(default_factory=dict)
    pass_score: int = 70
    quiz: dict | None = None


class AdminTopic(BaseModel):
    id: UUID
    title: str
    position: int
    learning_goal: str
    tutor_instructions: str
    checkpoints: list[AdminCheckpoint]


class LessonPlanOut(BaseModel):
    id: UUID
    slug: str
    title: str
    preamble: str
    is_active: bool
    age_min: int | None = None
    age_max: int | None = None
    created_at: datetime
    updated_at: datetime
    topics: list[AdminTopic]


class ResultOut(BaseModel):
    id: UUID
    checkpoint_id: UUID
    topic_title: str
    checkpoint_kind: str
    checkpoint_position: int
    score: int
    passed: bool
    feedback: str
    misconception: str | None = None
    hint_tier: str | None = None
    created_at: datetime


class SessionSummary(BaseModel):
    id: UUID
    student_id: UUID
    student_display_name: str
    lesson_plan_id: UUID
    lesson_title: str
    status: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    result_count: int


class SessionAdminOut(BaseModel):
    id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    student: StudentOut
    lesson_plan: LessonPlanOut
    current_topic_id: UUID | None
    current_checkpoint_id: UUID | None
    messages: list[MessageOut]
    results: list[ResultOut]


class OutlineCheckpoint(BaseModel):
    kind: str
    position: int
    state: str


class OutlineTopic(BaseModel):
    title: str
    position: int
    checkpoints: list[OutlineCheckpoint]


class TopicContext(BaseModel):
    title: str
    position: int
    learning_goal: str
    tutor_instructions: str


class WidgetGradeOut(BaseModel):
    correct: bool
    score: int
    passed: bool
    misconception: str | None
    choice_ids: list[str]
    explanation: str


class CheckpointContext(BaseModel):
    kind: str
    position: int
    checkpoints_in_topic: int
    tutor_prompt: str
    rubric: str | None
    pass_criteria: str | None
    objective: str | None = None
    rubric_rows: list[dict] = Field(default_factory=list)
    hint_tier: str | None = None
    hint_text: str = ""
    pass_score: int = 70
    quiz: dict | None = None
    widget_grade: WidgetGradeOut | None = None


class ContextOut(BaseModel):
    session_id: UUID
    status: str
    student_display_name: str
    lesson_title: str
    preamble: str
    topic_count: int
    outline: list[OutlineTopic]
    current_topic: TopicContext | None
    current_checkpoint: CheckpointContext | None


class CurrentStepOut(BaseModel):
    status: str
    message: str
    topic_title: str | None = None
    topic_position: int | None = None
    topic_count: int | None = None
    learning_goal: str | None = None
    tutor_instructions: str | None = None
    checkpoint_kind: str | None = None
    checkpoint_position: int | None = None
    checkpoints_in_topic: int | None = None
    tutor_prompt: str | None = None
    rubric: str | None = None
    pass_criteria: str | None = None


class SessionOpen(BaseModel):
    student_id: UUID
    lesson_plan_id: UUID | None = None
    fresh: bool = False


class MessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20000)
    client_id: str | None = Field(default=None, max_length=200)


class ResultIn(BaseModel):
    score: int = Field(ge=0, le=100)
    passed: bool
    feedback: str = Field(min_length=1, max_length=2000)


class WidgetIn(BaseModel):
    choice: str | list[str]
    explanation: str = Field(default="", max_length=2000)


class TurnScoreIn(BaseModel):
    rubric_met: list[str] = Field(default_factory=list)
    misconception: str | None = None
    hint_tier: Literal["nudge", "analogy", "scaffold"] = "nudge"
    advance: bool = False


class ModelPromptIn(BaseModel):
    system_prompt: str = Field(min_length=1)
    messages: list[Any] = Field(default_factory=list)
    model: str = Field(default="", max_length=120)


class ModelPromptOut(BaseModel):
    id: UUID
    session_id: UUID
    seq: int
    system_prompt: str
    messages: list[Any]
    model: str
    created_at: datetime
