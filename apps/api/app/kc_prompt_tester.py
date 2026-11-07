"""Read-only preview of the knowledge-component prompt.

The form is turned into in-memory rows. build_kc_prompt is the same
function the tutor calls. Nothing is added to the database.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.engine.choices import METAPHORS, PERSONAS, SIDEKICKS, STRUGGLE_WINDOWS, VOICES, ids
from app.kc import AUDIENCES, KC_TYPES, KINDS
from app.kc_prompt import (
    AFFECTS,
    HINTS,
    Move,
    asks_why,
    build_kc_prompt,
    effective_enrichment,
    effective_window_name,
    is_fragment,
    moves_for,
    struggle_tries,
)
from app.models import KcGoal, KcNode, Student, TutorProfile

SUPPORT_BANDS = ("ready", "stretch", "hold")
ENRICHMENTS = ("direct", "on_request", "offer")
COMPONENT_STATUSES = ("unknown", "fragile", "known")
YES_NO = ("yes", "no")


class MisconceptionIn(BaseModel):
    wrong_move: str = ""
    broken_kc: str = ""


class PromptTesterIn(BaseModel):
    course_title: str = ""
    course_description: str = ""
    audience: str = "9-11"
    kind: str = "mastery"
    minutes: int | None = None
    component_title: str = ""
    component_code: str = ""
    component_description: str = ""
    kc_type: str = ""
    core_truth: str = ""
    rubric: list[str] = Field(default_factory=list)
    misconceptions: list[MisconceptionIn] = Field(default_factory=list)
    prerequisite_codes: list[str] = Field(default_factory=list)
    encompasses_codes: list[str] = Field(default_factory=list)
    transfer_case: str = ""
    counterfactual: str = ""
    type_fields: dict = Field(default_factory=dict)
    move_index: int = Field(default=1, ge=1)
    choice_on_screen: str = "no"
    prerequisite_status: str = ""
    course_position: str = ""
    display_name: str = ""
    age: int | None = None
    reading_level: str = ""
    modality: str = ""
    interests: list[str] = Field(default_factory=list)
    attempts: int = Field(default=0, ge=0)
    hint_tier: str = "nudge"
    component_status: str = "unknown"
    stability: str = "0"
    last_answer: str = ""
    last_misconception: str = ""
    minutes_used: int = Field(default=0, ge=0)
    support_band: str = "ready"
    persona: str = "curious-co-explorer"
    lexicon: str = "middle-grade-vivid"
    metaphors: str = "playground-sports"
    sidekick: str = "bumbling-partner"
    use_interests: str = "yes"
    instructive: int = Field(default=3, ge=1, le=5)
    struggle_window: str = "standard"
    stay_on_course: str = "yes"
    anti_spoiler: str = "yes"
    one_question: str = "yes"
    misconception_policy: str = "retry_once"
    enrichment: str = "on_request"
    growth_praise: str = "yes"
    self_explanation: str = "yes"
    reveals: int = Field(default=0, ge=0)
    off_course_count: int = Field(default=0, ge=0)
    rubric_met: list[str] = Field(default_factory=list)
    last_messages: str = ""
    affect: str = ""
    help_requested: str = "no"
    last_practiced: str = ""
    redirect_pending: str = "no"
    enrichment_turns: int = Field(default=0, ge=0)
    unit_close: str = "no"
    course_outro: str = "no"

    @model_validator(mode="after")
    def closed_sets(self) -> "PromptTesterIn":
        _one(self.audience, AUDIENCES, "Audience")
        _one(self.kind, KINDS, "Kind")
        _one(self.kc_type, ("", *KC_TYPES), "Type")
        _one(self.choice_on_screen, YES_NO, "Choice widget")
        _one(self.hint_tier, HINTS, "Hint tier")
        _one(self.component_status, COMPONENT_STATUSES, "Component status")
        _one(self.support_band, SUPPORT_BANDS, "Support band")
        _one(self.persona, ids(PERSONAS), "Persona")
        _one(self.lexicon, ids(VOICES), "Lexicon")
        _one(self.metaphors, ids(METAPHORS), "Metaphors")
        _one(self.sidekick, ids(SIDEKICKS), "Sidekick")
        _one(self.use_interests, YES_NO, "Use interests")
        _one(self.struggle_window, ids(STRUGGLE_WINDOWS), "Struggle window")
        _one(self.stay_on_course, YES_NO, "Stay on course")
        _one(self.anti_spoiler, YES_NO, "Anti-spoiler")
        _one(self.one_question, YES_NO, "One question")
        _one(self.misconception_policy, ("retry_once",), "Misconception policy")
        _one(self.enrichment, ENRICHMENTS, "Enrichment")
        _one(self.growth_praise, YES_NO, "Growth-mindset praise")
        _one(self.self_explanation, YES_NO, "Self-explanation")
        _one(self.affect, ("", *AFFECTS), "Affect")
        _one(self.help_requested, YES_NO, "Help requested")
        _one(self.redirect_pending, YES_NO, "Redirect pending")
        _one(self.unit_close, YES_NO, "Unit close")
        _one(self.course_outro, YES_NO, "Course outro")
        return self


def _one(value: str, allowed: tuple[str, ...] | set[str], label: str) -> None:
    if value in allowed:
        return
    shown = ", ".join(sorted(item for item in allowed if item))
    raise ValueError(f"{label} must be one of: {shown}")


def _yes(value: str) -> bool:
    return value == "yes"


def _opening(last_messages: str) -> bool:
    """True until an assistant turn is in the recent transcript."""
    for part in (last_messages or "").split(" | "):
        if part.strip().lower().startswith("assistant:"):
            return False
    return True


def _fragment(node: KcNode, last_answer: str) -> bool:
    if node.kc_type != "factual":
        return False
    fact = str((node.type_fields or {}).get("fact") or node.core_truth or "")
    return is_fragment(last_answer, fact)


def _rows(body: PromptTesterIn) -> tuple[Student, TutorProfile, KcNode, KcGoal]:
    fields = dict(body.type_fields or {})
    fields["transfer_case"] = body.transfer_case
    fields["counterfactual"] = body.counterfactual
    student = Student(
        slug="prompt-tester",
        display_name=body.display_name,
        age=body.age,
        reading_level=body.reading_level,
        modality=body.modality,
        interests=list(body.interests),
    )
    profile = TutorProfile(
        id="prompt-tester",
        instructive=body.instructive,
        persona=body.persona,
        lexicon=body.lexicon,
        voice_override=False,
        metaphors=body.metaphors,
        sidekick=body.sidekick,
        struggle_window=body.struggle_window,
        anti_spoiler=_yes(body.anti_spoiler),
        one_question=_yes(body.one_question),
        use_interests=_yes(body.use_interests),
        stay_on_course=_yes(body.stay_on_course),
        growth_praise=_yes(body.growth_praise),
        misconception_policy=body.misconception_policy,
        self_explanation=_yes(body.self_explanation),
        enrichment=body.enrichment,
    )
    node = KcNode(
        code=body.component_code,
        title=body.component_title,
        description=body.component_description,
        kc_type=body.kc_type or None,
        core_truth=body.core_truth,
        type_fields=fields,
        rubric=list(body.rubric),
        misconceptions=[
            {"wrong_move": item.wrong_move, "broken_kc": item.broken_kc} for item in body.misconceptions
        ],
        prerequisite_codes=list(body.prerequisite_codes),
        encompasses_codes=list(body.encompasses_codes),
    )
    goal = KcGoal(
        code="prompt-tester",
        title=body.course_title,
        description=body.course_description,
        audience=body.audience,
        kind=body.kind,
        minutes=body.minutes,
        target_kc_ids=[],
        ready=False,
    )
    return student, profile, node, goal


def preview_kc_prompt(body: PromptTesterIn) -> dict:
    """The system prompt and the values the generator computes itself."""
    student, profile, node, goal = _rows(body)
    fragment = _fragment(node, body.last_answer)
    moves = moves_for(node, profile, goal, fragment=fragment) or [Move("this", "This step", (), False)]
    bundle = build_kc_prompt(
        student=student,
        profile=profile,
        node=node,
        goal=goal,
        step=body.move_index - 1,
        moves=moves,
        opening=_opening(body.last_messages),
        choice_on_screen=_yes(body.choice_on_screen),
        prerequisite_status=body.prerequisite_status,
        support_band=body.support_band,
        course_position=body.course_position,
        unit_complete=_yes(body.unit_close),
        course_complete=_yes(body.course_outro),
        attempts=body.attempts,
        hint_tier=body.hint_tier,
        reveals=body.reveals,
        off_course_count=body.off_course_count,
        affect=body.affect,
        enrichment_turns=body.enrichment_turns,
        help_requested=_yes(body.help_requested),
        minutes_used=body.minutes_used,
        component_status=body.component_status,
        stability=body.stability,
        last_answer=body.last_answer,
        last_misconception=body.last_misconception,
        last_messages=body.last_messages,
        rubric_met=list(body.rubric_met),
        redirect_pending=_yes(body.redirect_pending),
        fragment=fragment,
        others_known=False,
    )
    index = min(max(body.move_index - 1, 0), len(moves) - 1)
    move = moves[index]
    window_name = effective_window_name(profile, goal)
    return {
        "system_prompt": bundle["system_prompt"],
        "move_name": move.name,
        "evidence": ", ".join(move.evidence),
        "effective_struggle_window": f"{window_name} ({struggle_tries(window_name)} tries)",
        "effective_enrichment": effective_enrichment(profile, goal),
        "asks_why": "yes" if asks_why(profile, move) else "no",
    }
