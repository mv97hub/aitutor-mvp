"""Read-only preview of the knowledge-component modular block prompt.

The form is turned into in-memory rows. build_kc_prompt is the same
function the tutor calls. Nothing is added to the database.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.engine.choices import (
    HUMOR_MODES,
    INTEREST_WEAVING_MODES,
    METAPHORS,
    PERSONAS,
    SIDEKICKS,
    VOCABULARY_REGISTERS,
    VOICES,
    ids,
)
from app.kc import AUDIENCES, KINDS
from app.kc_model import BLOCK_LABELS, derive_rubric_from_blocks
from app.kc_prompt import (
    AFFECTS,
    HINTS,
    SUBSTEP_LABELS,
    block_evidence_id,
    block_step_label,
    block_uses_choice_widget,
    build_kc_prompt,
    default_substep_for_block,
    format_active_substep_label,
    is_fragment,
    max_retries_for_block,
    stored_blocks,
    substeps_for_block,
)
from app.models import (
    ALL_BLOCK_TYPES,
    KcGoal,
    KcNode,
    Student,
    TutorProfile,
    default_kc_tutor_config,
    normalize_child_profile,
)
from app.tutor_profile import (
    OVERARCHING_ENUMS,
    map_legacy_lexicon,
    map_legacy_use_interests,
    normalize_kc_tutor_config,
)

SUPPORT_BANDS = ("ready", "stretch", "hold")
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
    component_outline: str = ""
    core_truth: str = ""
    blocks: list[dict] = Field(default_factory=list)
    active_block_type: str = "topic_goal"
    active_block_data: dict = Field(default_factory=dict)
    active_substep: str = ""
    block_index: int = Field(default=1, ge=1)
    move_index: int | None = Field(default=None, ge=1)
    dialogue_turns: int = Field(default=0, ge=0)
    eliminated_indices: list[int] = Field(default_factory=list)
    rubric: list[str] = Field(default_factory=list)
    misconceptions: list[MisconceptionIn] = Field(default_factory=list)
    prerequisite_codes: list[str] = Field(default_factory=list)
    encompasses_codes: list[str] = Field(default_factory=list)
    choice_on_screen: str = "no"
    prerequisite_status: str = ""
    course_position: str = ""
    display_name: str = ""
    age: int | None = None
    grade_band: str = ""
    reading_level: str = ""
    response_length: str = ""
    expression_style: str = ""
    explanation_style: str = ""
    challenge_appetite: str = ""
    communication_tone: str = ""
    learning_support: str = ""
    interest_tags: list[str] = Field(default_factory=list)
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
    persona: str = "coach"
    lexicon: str = "adaptive_to_child"
    vocabulary_register: str = ""
    interest_weaving: str = ""
    metaphors: str = "everyday"
    humor_and_wit: str = "light_warm"
    sidekick: str = "none"
    use_interests: str = "yes"
    orient_framing: str = "elaborate_outline"
    instructional_stance: str = "guided_discovery"
    scaffolding_escalation: str = "progressive_nudge_then_scaffold"
    stay_on_course: str = "brief_answer_then_return"
    misconception_policy: str = "explain_and_retry_once"
    prerequisite_support_policy: str = "inline_micro_recap"
    encouragement_style: str = "process_praise"
    close_summary_depth: str = "diagnostic_strengths_and_gaps"
    instructive: int | None = Field(default=None, ge=1, le=5)
    kc_tutor_config: dict | None = None
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
        _one(self.active_block_type, ("", *ALL_BLOCK_TYPES), "Active block type")
        _one(self.choice_on_screen, YES_NO, "Choice widget")
        _one(self.hint_tier, HINTS, "Hint tier")
        _one(self.component_status, COMPONENT_STATUSES, "Component status")
        _one(self.support_band, SUPPORT_BANDS, "Support band")
        _one(self.persona, ids(PERSONAS), "Persona")
        if self.vocabulary_register:
            if self.vocabulary_register in {"1", "2", "3", "4", "5", "match_child"}:
                self.vocabulary_register = map_legacy_lexicon(self.vocabulary_register)
            _one(self.vocabulary_register, ids(VOCABULARY_REGISTERS), "Vocabulary register")
            self.lexicon = self.vocabulary_register
        else:
            if self.lexicon in {"1", "2", "3", "4", "5", "match_child"}:
                self.lexicon = map_legacy_lexicon(self.lexicon)
            _one(self.lexicon, ids(VOICES), "Lexicon")
            self.vocabulary_register = map_legacy_lexicon(self.lexicon)
        if self.interest_weaving:
            _one(self.interest_weaving, ids(INTEREST_WEAVING_MODES), "Interest weaving")
            self.use_interests = "no" if self.interest_weaving == "off" else "yes"
        else:
            _one(self.use_interests, YES_NO, "Use interests")
            self.interest_weaving = map_legacy_use_interests(self.use_interests == "yes")
        _one(self.metaphors, ids(METAPHORS), "Metaphors")
        _one(self.humor_and_wit, ids(HUMOR_MODES), "Humor and wit")
        _one(self.sidekick, ids(SIDEKICKS), "Sidekick")
        _one(self.orient_framing, OVERARCHING_ENUMS["orient_framing"], "Orient framing")
        _one(self.instructional_stance, OVERARCHING_ENUMS["instructional_stance"], "Instructional stance")
        _one(self.scaffolding_escalation, OVERARCHING_ENUMS["scaffolding_escalation"], "Scaffolding escalation")
        if self.stay_on_course in {"yes", "no"}:
            self.stay_on_course = "brief_answer_then_return" if self.stay_on_course == "yes" else "exploratory"
        _one(self.stay_on_course, OVERARCHING_ENUMS["stay_on_course"], "Stay on course")
        if self.misconception_policy == "retry_once":
            self.misconception_policy = "explain_and_retry_once"
        _one(self.misconception_policy, OVERARCHING_ENUMS["misconception_policy"], "Misconception policy")
        _one(
            self.prerequisite_support_policy,
            OVERARCHING_ENUMS["prerequisite_support_policy"],
            "Prerequisite support policy",
        )
        if self.encouragement_style == "brief_confirm":
            self.encouragement_style = "matter_of_fact_confirm"
        _one(self.encouragement_style, OVERARCHING_ENUMS["encouragement_style"], "Encouragement style")
        if self.close_summary_depth == "elaborate_strengths_and_weaknesses":
            self.close_summary_depth = "diagnostic_strengths_and_gaps"
        _one(self.close_summary_depth, OVERARCHING_ENUMS["close_summary_depth"], "Close summary depth")
        _one(self.affect, ("", *AFFECTS), "Affect")
        _one(self.help_requested, YES_NO, "Help requested")
        _one(self.redirect_pending, YES_NO, "Redirect pending")
        _one(self.unit_close, YES_NO, "Unit close")
        _one(self.course_outro, YES_NO, "Course outro")
        if self.active_substep and self.active_substep not in SUBSTEP_LABELS:
            raise ValueError(f"Active substep must be one of: {', '.join(sorted(k for k in SUBSTEP_LABELS if k))}")
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


def _effective_blocks(body: PromptTesterIn) -> list[dict]:
    blocks: list[dict] = []
    for idx, raw in enumerate(body.blocks or [], start=1):
        if not isinstance(raw, dict):
            continue
        btype = str(raw.get("type") or "topic_goal").strip()
        if btype not in ALL_BLOCK_TYPES:
            btype = "topic_goal"
        bid = str(raw.get("id") or f"blk_{idx}").strip() or f"blk_{idx}"
        data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
        blocks.append({"id": bid, "type": btype, "data": dict(data)})
    if not blocks:
        btype = body.active_block_type or "topic_goal"
        data = dict(body.active_block_data or {})
        if btype == "topic_goal" and not data:
            data = {
                "topic": body.component_title or "Concept",
                "goal": body.core_truth or f"Explain {body.component_title or 'this idea'}.",
            }
        blocks = [{"id": "blk_1", "type": btype, "data": data}]
    elif body.active_block_data:
        idx = min(max((body.move_index or body.block_index) - 1, 0), len(blocks) - 1)
        btype = body.active_block_type or blocks[idx]["type"]
        blocks[idx] = {
            "id": blocks[idx]["id"],
            "type": btype if btype in ALL_BLOCK_TYPES else blocks[idx]["type"],
            "data": dict(body.active_block_data),
        }
    return blocks


def _effective_config(body: PromptTesterIn) -> dict:
    raw = dict(body.kc_tutor_config or default_kc_tutor_config())
    over = dict(raw.get("overarching") or {})
    if body.kc_tutor_config is None or "overarching" not in body.kc_tutor_config:
        over.update(
            {
                "orient_framing": body.orient_framing,
                "instructional_stance": body.instructional_stance,
                "scaffolding_escalation": body.scaffolding_escalation,
                "stay_on_course": body.stay_on_course,
                "misconception_policy": body.misconception_policy,
                "prerequisite_support_policy": body.prerequisite_support_policy,
                "encouragement_style": body.encouragement_style,
                "close_summary_depth": body.close_summary_depth,
            }
        )
    else:
        for k, v in (
            ("orient_framing", body.orient_framing),
            ("instructional_stance", body.instructional_stance),
            ("scaffolding_escalation", body.scaffolding_escalation),
            ("stay_on_course", body.stay_on_course),
            ("misconception_policy", body.misconception_policy),
            ("prerequisite_support_policy", body.prerequisite_support_policy),
            ("encouragement_style", body.encouragement_style),
            ("close_summary_depth", body.close_summary_depth),
        ):
            over.setdefault(k, v)
    raw["overarching"] = over
    raw["voice"] = {
        "persona": body.persona,
        "vocabulary_register": body.vocabulary_register or map_legacy_lexicon(body.lexicon),
        "interest_weaving": body.interest_weaving or map_legacy_use_interests(body.use_interests == "yes"),
        "metaphors": body.metaphors,
        "humor_and_wit": body.humor_and_wit or "light_warm",
        "sidekick": body.sidekick,
    }
    if body.instructive is not None:
        blocks_cfg = {key: dict(value) for key, value in (raw.get("blocks") or {}).items() if isinstance(value, dict)}
        topic = dict(blocks_cfg.get("topic_goal") or {})
        topic["explanation_depth"] = int(body.instructive)
        blocks_cfg["topic_goal"] = topic
        raw["blocks"] = blocks_cfg
    return normalize_kc_tutor_config(raw, strict=True)


def _rows(body: PromptTesterIn) -> tuple[Student, TutorProfile, KcNode, KcGoal, dict]:
    cfg = _effective_config(body)
    blocks = _effective_blocks(body)
    rubric = list(body.rubric) or derive_rubric_from_blocks(blocks)
    child_raw: dict = {}
    for k in (
        "grade_band",
        "reading_level",
        "response_length",
        "expression_style",
        "explanation_style",
        "challenge_appetite",
        "communication_tone",
        "learning_support",
    ):
        v = str(getattr(body, k, "") or "").strip()
        if v:
            child_raw[k] = v
    if body.interest_tags:
        child_raw["interest_tags"] = list(body.interest_tags)
    if body.interests:
        child_raw["interests"] = ", ".join(str(x).strip() for x in body.interests if str(x).strip())
    cp = normalize_child_profile(
        child_raw,
        age=body.age,
        reading_level=body.reading_level,
        modality=body.explanation_style or body.modality,
        interests=list(body.interests),
    )
    student = Student(
        slug="prompt-tester",
        display_name=body.display_name,
        age=body.age,
        reading_level=body.reading_level,
        modality=body.modality or body.explanation_style,
        interests=list(body.interests),
        child_profile=cp if (child_raw or body.age is not None or body.reading_level or body.modality) else {},
    )
    profile = TutorProfile(
        id="prompt-tester",
        instructive=3,
        persona=body.persona,
        lexicon=body.lexicon,
        voice_override=False,
        metaphors=body.metaphors,
        sidekick=body.sidekick,
        struggle_window="standard",
        anti_spoiler=True,
        one_question=True,
        use_interests=_yes(body.use_interests),
        stay_on_course=cfg["overarching"]["stay_on_course"] != "exploratory",
        growth_praise=cfg["overarching"]["encouragement_style"] == "process_praise",
        misconception_policy=cfg["overarching"]["misconception_policy"],
        self_explanation=True,
        enrichment="on_request",
        kc_tutor_config=cfg,
    )
    node = KcNode(
        code=body.component_code,
        title=body.component_title,
        description=body.component_description,
        outline=body.component_outline or body.component_description,
        blocks=blocks,
        core_truth=body.core_truth,
        rubric=rubric,
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
        allowed_block_types=list(ALL_BLOCK_TYPES),
        ready=False,
    )
    return student, profile, node, goal, cfg


def preview_kc_prompt(body: PromptTesterIn) -> dict:
    """The system prompt and the active block/substep metadata computed by the generator."""
    student, profile, node, goal, cfg = _rows(body)
    blocks = stored_blocks(node)
    chosen_index = (body.move_index if body.move_index is not None else body.block_index) - 1
    index = min(max(chosen_index, 0), len(blocks) - 1)
    active_block = blocks[index]
    btype = str(active_block.get("type") or "topic_goal")
    data = active_block.get("data") if isinstance(active_block.get("data"), dict) else {}
    substeps = substeps_for_block(active_block, cfg)
    substep = body.active_substep.strip() or default_substep_for_block(active_block, cfg)
    target_text = str(data.get("goal") or data.get("expected_fact") or node.core_truth or "")
    fragment = bool(btype == "topic_goal" and is_fragment(body.last_answer, target_text))
    active_state = {
        "substep": substep,
        "dialogue_turns": body.dialogue_turns,
        "mcq": {"eliminated_indices": list(body.eliminated_indices)} if body.eliminated_indices else {},
    }
    widget_on = _yes(body.choice_on_screen) or block_uses_choice_widget(active_block, substep)
    bundle = build_kc_prompt(
        student=student,
        profile=profile,
        node=node,
        goal=goal,
        step=index,
        opening=_opening(body.last_messages),
        choice_on_screen=widget_on,
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
        active_block_state=active_state,
    )
    ev_id = block_evidence_id(active_block, index, substep)
    step_label = block_step_label(active_block, index, len(blocks), substep)
    substep_label = format_active_substep_label(active_block, substep, cfg)
    max_retries = max_retries_for_block(active_block, cfg, goal)
    return {
        "system_prompt": bundle["system_prompt"],
        "move_name": step_label,
        "active_block_label": step_label,
        "active_block_type": btype,
        "active_block_type_label": BLOCK_LABELS.get(btype, btype),
        "active_substep": substep,
        "active_substep_label": substep_label,
        "substeps": substeps,
        "evidence": ev_id,
        "max_retries": max_retries,
        "uses_choice_widget": "yes" if widget_on else "no",
    }
