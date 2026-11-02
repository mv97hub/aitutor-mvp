from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


AgeBand = Literal["6-8", "9-11", "12-14", "15-17"]
QuestType = Literal["core", "branch", "capstone"]
BeatRole = Literal["mystery_hook", "interactive_toy", "diagnostic_gate", "feynman_flip"]
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


class CourseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    code: str | None = None
    age_band: AgeBand = "9-11"
    standards_alignment: str = ""


class CoursePatch(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    code: str = Field(min_length=1, max_length=40)
    age_band: AgeBand
    standards_alignment: str = ""
    competency_dictionary: list[Competency] = Field(default_factory=list)


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
    type: Literal["single", "flaw", "order"]
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
    age_band: str
    standards_alignment: str
    unit_count: int
    quest_count: int


class QuestNode(BaseModel):
    id: UUID
    code: str
    title: str
    quest_type: str
    prerequisite_codes: list[str]
    competency_tags: list[str]
    dinner_prompt: str
    position: int


class UnitNode(BaseModel):
    id: UUID
    number: int
    title: str
    enduring_understanding: str
    continuity_summary: str
    is_diagnostic: bool
    is_capstone: bool
    quests: list[QuestNode]


class CourseTree(BaseModel):
    id: UUID
    code: str
    title: str
    age_band: str
    standards_alignment: str
    competency_dictionary: list[dict]
    units: list[UnitNode]


class QuestListItem(BaseModel):
    id: UUID
    code: str
    title: str
    quest_type: str
    prerequisite_codes: list[str]
    competency_tags: list[str]
    unit_number: int
    unit_title: str
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
    unit_id: UUID
    course_id: UUID
    beats: list[BeatOut]


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
    current_beat_id: UUID | None
    beats: list[BoardBeat]
    messages: list[MessageOut]
    steps: list[BlockStep]
    current_block: CurrentBlock | None = None


class ResultOut(BaseModel):
    id: UUID
    beat_id: UUID
    beat_role: str
    beat_position: int
    quest_title: str
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
    current_beat_id: UUID | None
    beats: list[SessionBeat]
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
