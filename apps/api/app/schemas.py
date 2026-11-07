from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.engine.choices import METAPHORS, PERSONAS, SIDEKICKS, STRUGGLE_WINDOWS, VOICES, ids


AgeBand = Literal["6-8", "9-11", "12-14", "15-17"]
QuestType = Literal["core", "branch", "capstone"]
BeatRole = Literal["engage", "try", "name", "show", "teach_back"]
Bloom = Literal["remember", "understand", "apply", "analyze", "evaluate", "create"]
Load = Literal["low", "medium", "high"]


class StudentOut(BaseModel):
    id: UUID
    slug: str
    display_name: str
    age: int | None = None
    age_band: str
    reading_level: str = ""
    modality: str = ""
    interests: list[str] = Field(default_factory=list)
    tutor_persona: str = ""
    tutor_lexicon: str = ""
    tutor_metaphors: str = ""
    tutor_sidekick: str = ""
    tutor_socratic_strictness: str = "balanced"
    tutor_struggle_window: str = "minimum"
    tutor_anti_spoiler: bool = True
    tutor_pacing: str = "short-turns-one-question"


class StudentCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    age: int = Field(ge=4, le=18)
    reading_level: str | None = None
    modality: str | None = None
    interests: list[str] | None = None
    tutor_persona: str | None = None
    tutor_lexicon: str | None = None
    tutor_metaphors: str | None = None
    tutor_sidekick: str | None = None
    tutor_socratic_strictness: str | None = None
    tutor_struggle_window: str | None = None
    tutor_anti_spoiler: bool | None = None
    tutor_pacing: str | None = None


class StudentPatch(BaseModel):
    reading_level: str | None = None
    modality: str | None = None
    interests: list[str] | None = None
    tutor_persona: str | None = None
    tutor_lexicon: str | None = None
    tutor_metaphors: str | None = None
    tutor_sidekick: str | None = None
    tutor_socratic_strictness: str | None = None
    tutor_struggle_window: str | None = None
    tutor_anti_spoiler: bool | None = None
    tutor_pacing: str | None = None


def _closed(value: str, options: tuple[tuple[str, str], ...], field: str) -> None:
    allowed = ids(options)
    if value not in allowed:
        raise ValueError(f"{field} must be one of: {', '.join(sorted(allowed))}")


class TutorProfileIn(BaseModel):
    instructive: int = Field(ge=1, le=5)
    persona: str
    lexicon: str
    voice_override: bool = False
    metaphors: str
    sidekick: str
    struggle_window: str
    anti_spoiler: bool = True
    one_question: bool = True
    use_interests: bool = True
    stay_on_course: bool = True
    growth_praise: bool = True

    @model_validator(mode="after")
    def closed_choices(self) -> "TutorProfileIn":
        _closed(self.persona, PERSONAS, "persona")
        _closed(self.lexicon, VOICES, "lexicon")
        _closed(self.metaphors, METAPHORS, "metaphors")
        _closed(self.sidekick, SIDEKICKS, "sidekick")
        _closed(self.struggle_window, STRUGGLE_WINDOWS, "struggle_window")
        return self


class TutorProfileOut(TutorProfileIn):
    updated_at: datetime


class ProfileDefaults(BaseModel):
    age_band: str
    reading_level: str
    modality: str
    interests: list[str] = Field(default_factory=list)
    tutor_persona: str
    tutor_lexicon: str
    tutor_metaphors: str
    tutor_sidekick: str
    tutor_socratic_strictness: str
    tutor_struggle_window: str
    tutor_anti_spoiler: bool
    tutor_pacing: str


class Competency(BaseModel):
    code: str
    description: str


class StudioImportIn(BaseModel):
    studio_course_id: UUID


class CourseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    code: str | None = None
    description: str = ""
    audience: AgeBand = "9-11"
    quest_count: int = 1
    goals_per_quest: int = 1
    quiz_minutes: int = 5


class CoursePatch(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    code: str = Field(min_length=1, max_length=40)
    description: str = ""
    audience: AgeBand
    quest_count: int = 1
    goals_per_quest: int = 1
    quiz_minutes: int = 5


class UnitCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    number: int | None = Field(default=None, ge=1)
    enduring_understanding: str = ""
    continuity_summary: str = "This unit connects to the quest before it. The next quest carries that idea forward."
    is_diagnostic: bool = False
    is_capstone: bool = False


class UnitPatch(UnitCreate):
    number: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=240)


class QuestCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    code: str = Field(min_length=1, max_length=40)
    quest_type: QuestType = "core"
    prerequisite_codes: list[str] = Field(default_factory=list)
    competency_tags: list[str] = Field(default_factory=list)
    dinner_prompt: str = ""
    learning_goal: str = "State the idea this quest is building."
    success_criterion: list = Field(default_factory=list)
    requires_teach_back: bool = False


class QuestPatch(QuestCreate):
    pass


class RubricRowIn(BaseModel):
    id: str = ""
    text: str = ""
    weight: int = Field(default=0, ge=0, le=100)


class HintLadderIn(BaseModel):
    nudge: str = ""
    analogy: str = ""
    scaffold: str = ""


class TrapIn(BaseModel):
    id: str = ""
    trap: str = ""
    note: str = ""


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


class BeatIn(BaseModel):
    role: BeatRole
    bloom_level: Bloom = "understand"
    cognitive_load: Load = "medium"
    prompt: str = ""
    rubric: list[RubricRowIn] = Field(default_factory=list)
    misconception_map: list[TrapIn] = Field(default_factory=list)
    hint_ladder: HintLadderIn = Field(default_factory=HintLadderIn)
    widget: QuizIn | None = None


class BeatWrite(BaseModel):
    beats: list[BeatIn]


class CourseSummary(BaseModel):
    id: UUID
    code: str
    title: str
    description: str = ""
    audience: str = ""
    quest_count: int
    goals_per_quest: int = 1
    quiz_minutes: int = 5


class QuestNode(BaseModel):
    id: UUID
    code: str
    title: str
    position: int


class GoalOut(BaseModel):
    position: int
    learning_goal: str = ""
    success_criterion: str = ""


class CloseOut(BaseModel):
    close_style: str
    answer_style: str
    choice_mode: str | None = None
    items: list[dict] = Field(default_factory=list)
    questions: list[dict] = Field(default_factory=list)
    intent: str = ""
    selection: str | None = None


class CatalogQuest(BaseModel):
    id: UUID
    code: str
    title: str
    position: int
    goals: list[GoalOut] = Field(default_factory=list)
    close: CloseOut | None = None


class CourseTree(BaseModel):
    id: UUID
    code: str
    title: str
    description: str = ""
    audience: str = ""
    quest_count: int = 1
    goals_per_quest: int = 1
    quiz_minutes: int = 5
    quests: list[CatalogQuest]


class QuestListItem(BaseModel):
    id: UUID
    code: str
    title: str
    position: int


class BeatOut(BaseModel):
    id: UUID
    position: int
    role: str
    bloom_level: str
    cognitive_load: str
    prompt: str
    rubric: list[dict]
    misconception_map: list[dict]
    hint_ladder: dict
    widget: dict | None = None


class QuestDetail(QuestNode):
    course_id: UUID
    goals: list[GoalOut] = Field(default_factory=list)
    close: CloseOut | None = None


class MessageOut(BaseModel):
    id: UUID
    role: str
    content: str
    client_id: str | None
    created_at: datetime


class BoardResult(BaseModel):
    id: UUID
    score: int
    passed: bool
    feedback: str
    created_at: datetime


class BoardBeat(BaseModel):
    id: UUID
    position: int
    role: str
    latest_result: BoardResult | None


class RubricRowOut(BaseModel):
    id: str
    text: str
    weight: int
    met: bool


class QuizChoiceOut(BaseModel):
    id: str
    text: str


class QuizOut(BaseModel):
    type: Literal["single", "flaw", "order", "multi"]
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
    course_code: str
    course_title: str
    quest_id: UUID
    quest_code: str
    quest_title: str
    enduring_understanding: str
    current_goal_id: UUID | None
    close_started: bool = False
    messages: list[MessageOut]
    steps: list[BlockStep]
    current_block: CurrentBlock | None = None


class ResultOut(BaseModel):
    id: UUID
    goal_id: UUID | None = None
    role: str
    position: int
    quest_title: str
    criterion: str = ""
    answer: str = ""
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
    quest_id: UUID
    quest_code: str
    quest_title: str
    course_title: str
    status: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    result_count: int


class ModelPromptOut(BaseModel):
    id: UUID
    session_id: UUID
    message_id: UUID | None = None
    seq: int
    system_prompt: str
    messages: list[Any]
    model: str
    created_at: datetime


class SessionQuest(BaseModel):
    id: UUID
    code: str
    title: str
    course_code: str
    course_title: str


class SessionBeat(BaseModel):
    id: UUID
    position: int
    role: str


class SessionAdminOut(BaseModel):
    id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    student: StudentOut
    quest: SessionQuest
    current_goal_id: UUID | None
    close_started: bool = False
    messages: list[MessageOut]
    results: list[ResultOut]
    prompts: list[ModelPromptOut] = Field(default_factory=list)


class PromptBundleOut(BaseModel):
    system_prompt: str
    response_schema: dict
    temperature: float


class SessionOpen(BaseModel):
    student_id: UUID
    quest_id: UUID
    fresh: bool = False


class MessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20000)
    client_id: str | None = Field(default=None, max_length=200)


class WidgetIn(BaseModel):
    choice: str | list[str]
    explanation: str = Field(default="", max_length=2000)


class DiagramCheckIn(BaseModel):
    diagram: Any = None


class TurnScoreIn(BaseModel):
    rubric_met: list[str] = Field(default_factory=list)
    misconception: str | None = None
    hint_tier: Literal["nudge", "analogy", "scaffold"] = "nudge"
    advance: bool = False


class ModelPromptIn(BaseModel):
    system_prompt: str = Field(min_length=1)
    messages: list[Any] = Field(default_factory=list)
    model: str = Field(default="", max_length=120)
    message_id: UUID | None = None


class KcChatSummary(BaseModel):
    id: UUID
    student_id: UUID
    student_display_name: str
    course_id: UUID
    course_code: str
    course_title: str
    kc_id: UUID
    kc_code: str
    kc_title: str
    kc_type: str | None = None
    recipe: str
    step: int
    step_label: str
    status: str
    score: int | None = None
    created_at: datetime
    updated_at: datetime
    message_count: int


class KcChatCourse(BaseModel):
    id: UUID
    code: str
    title: str


class KcChatComponent(BaseModel):
    id: UUID
    code: str
    title: str
    kc_type: str | None = None


class KcChatMessage(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    content: str
    seq: int
    created_at: datetime


class KcChatDetail(BaseModel):
    id: UUID
    status: str
    recipe: str
    step: int
    step_label: str
    score: int | None = None
    attempts: int
    created_at: datetime
    updated_at: datetime
    student: StudentOut
    course: KcChatCourse
    component: KcChatComponent
    messages: list[KcChatMessage]
    prompts: list[ModelPromptOut] = Field(default_factory=list)


StudioDepth = Literal["survey", "standard", "go_deep"]
StudioCloseStyle = Literal["one", "several"]
StudioAnswerStyle = Literal["multiple_choice", "essay", "mixed"]
StudioChoiceMode = Literal["predefined", "dynamic"]


class StudioChoiceOut(BaseModel):
    text: str
    correct: bool = False


class StudioQuestionOut(BaseModel):
    text: str
    kind: Literal["single", "multiple"] = "single"
    choices: list[StudioChoiceOut] = Field(default_factory=list)


class StudioCloseOut(BaseModel):
    close_style: StudioCloseStyle
    answer_style: StudioAnswerStyle
    choice_mode: StudioChoiceMode | None = None
    items: list[StudioChoiceOut] = Field(default_factory=list)
    questions: list[StudioQuestionOut] = Field(default_factory=list)
    intent: str = ""
    selection: Literal["single", "multi"] | None = None


class StudioGoalOut(BaseModel):
    position: int
    learning_goal: str
    success_criterion: str


class StudioMoveOut(BaseModel):
    id: UUID
    code: str
    position: int
    title: str
    learning_goal: str
    success_criterion: str


class StudioQuestOut(BaseModel):
    id: UUID
    code: str
    position: int
    title: str
    learning_goal: str
    success_criterion: str
    goals: list[StudioGoalOut] = Field(default_factory=list)
    close: StudioCloseOut | None = None
    moves: list[StudioMoveOut]


class StudioPhaseOut(BaseModel):
    name: Literal["quests", "goals", "close", "ready"]
    label: Literal["Quests", "Goals/Success Criteria", "Close", "Ready"]
    open_codes: list[str]


class StudioStripOut(BaseModel):
    name: Literal["quests", "goals", "close", "ready"]
    label: Literal["Quests", "Goals/Success Criteria", "Close", "Ready"]
    filled: bool
    active: bool


class StudioViewOut(BaseModel):
    name: Literal["quests", "goals", "close", "ready"]
    label: Literal["Quests", "Goals/Success Criteria", "Close", "Ready"]
    codes: list[str]


class StudioPhaseIn(BaseModel):
    name: Literal["quests", "goals", "close", "ready", "structure"]


class StudioCourseOut(BaseModel):
    id: UUID
    code: str
    title: str
    audience: str
    focus: str
    theme: str
    depth: StudioDepth
    quiz_minutes: Literal[2, 5, 10]
    sources: str
    schema_version: int
    close_default: StudioCloseOut
    ready: bool
    gaps: list[str]
    phase: StudioPhaseOut
    strip: list[StudioStripOut]
    view: StudioViewOut
    quests: list[StudioQuestOut]
    quest_count: int = 10
    goals_per_quest: int = 3
    undo: bool = False
    stage: StudioPhaseOut | None = None
    stage_strip: list[StudioStripOut] = Field(default_factory=list)
    stage_view: StudioViewOut | None = None
    stage_gaps: list[str] = Field(default_factory=list)
    can_advance: bool = False
    can_push: bool = False
    updated_at: datetime


class StudioCourseSummary(BaseModel):
    id: UUID
    code: str
    title: str
    updated_at: datetime


class StudioCourseCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=240)


class StudioDeleteIn(BaseModel):
    password: str = Field(default="", max_length=200)


class StudioCopyIn(BaseModel):
    title: str = Field(min_length=1, max_length=240)


class StudioPreferencesIn(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    audience: str = ""
    focus: str = ""
    theme: str = ""
    description: str = ""
    depth: StudioDepth = "standard"
    quiz_minutes: int = 5
    sources: str = ""
    quest_count: int = 10
    goals_per_quest: int = 3
    close_default: dict


class StudioMessageOut(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    content: str
    seq: int
    proposal: dict | None = None
    applied: bool
    created_at: datetime


class StudioMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20000)
    proposal: dict | None = None


class StudioSettingsOut(BaseModel):
    model: str
    options: list[str]


class StudioSettingsIn(BaseModel):
    model: str = Field(min_length=1, max_length=64)


class StudioPromptOut(BaseModel):
    model: str
    system_prompt: str
    response_schema: dict
    temperature: float


class StudioIndexesIn(BaseModel):
    indexes: list[int] | None = None


class StudioEditIn(BaseModel):
    kind: Literal["quest", "move"]
    code: str = Field(min_length=1, max_length=40)
    title: str | None = None
    learning_goal: str | None = None
    success_criterion: str | None = None


class StudioAcceptOut(BaseModel):
    course: StudioCourseOut
    message: StudioMessageOut


class StudioOpeningOut(BaseModel):
    course: StudioCourseOut
    messages: list[StudioMessageOut]


class StudioTurnIn(BaseModel):
    content: str = Field(min_length=1, max_length=20000)


class StudioTurnOut(BaseModel):
    wrote: bool
    handled: bool = False
    awaiting_draft: bool = False
    user: StudioMessageOut | None = None
    assistant: StudioMessageOut | None = None
    course: StudioCourseOut | None = None


class StudioDraftIn(BaseModel):
    content: str = Field(min_length=1, max_length=20000)
    operations: list[dict[str, Any]] | None = None
    reply: str = ""
    fallback: bool = False


class StudioFallbackIn(BaseModel):
    content: str = Field(default="", max_length=20000)


class StudioTreeEditIn(BaseModel):
    action: Literal[
        "add_quest",
        "update_quest",
        "delete_quest",
        "add_goal",
        "update_goal",
        "delete_goal",
        "set_close",
    ]
    code: str | None = None
    title: str | None = None
    position: int | None = None
    learning_goal: str | None = None
    success_criterion: str | None = None
    close: dict[str, Any] | None = None
    question_index: int | None = None
