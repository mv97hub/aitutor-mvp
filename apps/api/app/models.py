from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

AGE_BANDS = ("6-8", "9-11", "12-14", "15-17")

GRADE_BANDS = (
    "early_elementary",
    "upper_elementary",
    "middle_school",
    "high_school",
)
READING_LEVELS = (
    "emerging",
    "early_fluent",
    "on_grade",
    "advanced",
)
RESPONSE_LENGTHS = (
    "bite_sized",
    "balanced",
    "detailed",
)
EXPRESSION_STYLES = (
    "one_word_or_taps",
    "short_phrases",
    "conversational",
    "analytical",
)
EXPLANATION_STYLES = (
    "concrete_examples",
    "step_by_step",
    "visual_spatial",
    "story_and_analogy",
    "pattern_and_rule",
)
CHALLENGE_APPETITES = (
    "needs_reassurance",
    "steady",
    "loves_a_challenge",
)
COMMUNICATION_TONES = (
    "calm_and_gentle",
    "warm_and_encouraging",
    "playful_and_curious",
    "direct_and_matter_of_fact",
)
LEARNING_SUPPORTS = (
    "none",
    "adhd_focus_friendly",
    "dyslexia_reading_friendly",
    "ell_language_support",
    "math_or_test_anxiety",
)
INTEREST_TAGS = (
    "sports_and_games",
    "video_games",
    "animals_and_nature",
    "space_and_science",
    "art_and_design",
    "music_and_dance",
    "building_and_coding",
    "cooking_and_food",
    "cars_and_trains",
    "stories_and_comics",
)

INTEREST_TAG_LABELS: dict[str, str] = {
    "sports_and_games": "Sports & games",
    "video_games": "Video games",
    "animals_and_nature": "Animals & nature",
    "space_and_science": "Space & science",
    "art_and_design": "Art & design",
    "music_and_dance": "Music & dance",
    "building_and_coding": "Building & coding",
    "cooking_and_food": "Cooking & food",
    "cars_and_trains": "Cars & trains",
    "stories_and_comics": "Stories & comics",
}


def grade_band_for_age(age: int | None) -> str:
    if age is None:
        return "upper_elementary"
    if age <= 7:
        return "early_elementary"
    if age <= 10:
        return "upper_elementary"
    if age <= 13:
        return "middle_school"
    return "high_school"


def normalize_reading_level(raw: str | None) -> str:
    val = (raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    if val in READING_LEVELS:
        return val
    if val in {"early_reader", "early", "beginner", "k_2", "emerging_reader"}:
        return "emerging"
    if val in {"middle_grade", "early_fluent_reader", "elementary"}:
        return "early_fluent"
    if val in {"grade_level", "on_grade_level", "standard"}:
        return "on_grade"
    if val in {"high_school", "above_grade", "advanced_reader", "college"}:
        return "advanced"
    if any(token in val for token in ("early", "emerg", "begin", "simple", "short")):
        return "emerging"
    if any(token in val for token in ("high", "advanc", "above")):
        return "advanced"
    return "on_grade"


def normalize_explanation_style(raw: str | None) -> str:
    val = (raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    if val in EXPLANATION_STYLES:
        return val
    if val in {"visual", "picture", "diagram", "spatial"} or "visual" in val:
        return "visual_spatial"
    if val in {"story", "narrative", "analogy", "metaphor"} or "story" in val:
        return "story_and_analogy"
    if val in {"steps", "procedural", "sequential"} or "step" in val:
        return "step_by_step"
    if val in {"verbal", "rule", "pattern", "abstract", "logic"} or "rule" in val:
        return "pattern_and_rule"
    return "concrete_examples"


def normalize_interest_tags(raw: object) -> list[str]:
    if isinstance(raw, str):
        items = [part.strip() for part in raw.split(",") if part.strip()]
    elif isinstance(raw, (list, tuple)):
        items = [str(part).strip() for part in raw if str(part).strip()]
    else:
        items = []
    out: list[str] = []
    for item in items:
        key = item.lower().replace("-", "_").replace(" ", "_")
        if key in INTEREST_TAGS and key not in out:
            out.append(key)
        if len(out) >= 4:
            break
    return out


def default_child_profile(age: int | None = 10) -> dict:
    return {
        "grade_band": grade_band_for_age(age),
        "reading_level": "on_grade",
        "response_length": "balanced",
        "expression_style": "short_phrases",
        "explanation_style": "concrete_examples",
        "challenge_appetite": "steady",
        "communication_tone": "warm_and_encouraging",
        "learning_support": "none",
        "interest_tags": [],
        "interests": "",
        "avatar_preset": "",
        "avatar_url": "",
    }


def child_avatar_preset(raw: object) -> str:
    """A blank preset means the child card shows initials. Unknown ids are dropped."""
    val = str(raw or "").strip()
    if not val:
        return ""
    from app.tutor_profile import AVATAR_PRESET_SET

    return val if val in AVATAR_PRESET_SET else ""


def normalize_child_profile(
    raw: dict | None,
    *,
    age: int | None = None,
    reading_level: str | None = None,
    modality: str | None = None,
    interests: list[str] | str | None = None,
) -> dict:
    src = raw if isinstance(raw, dict) else {}
    base = default_child_profile(age)

    gb = str(src.get("grade_band") or "").strip()
    base["grade_band"] = gb if gb in GRADE_BANDS else grade_band_for_age(age)

    rl_raw = src.get("reading_level") or reading_level
    base["reading_level"] = normalize_reading_level(str(rl_raw) if rl_raw else None)

    resp_len = str(src.get("response_length") or "").strip()
    if resp_len in RESPONSE_LENGTHS:
        base["response_length"] = resp_len

    expr = str(src.get("expression_style") or "").strip()
    if expr in EXPRESSION_STYLES:
        base["expression_style"] = expr

    expl_raw = src.get("explanation_style") or modality
    base["explanation_style"] = normalize_explanation_style(str(expl_raw) if expl_raw else None)

    chal = str(src.get("challenge_appetite") or "").strip()
    if chal in CHALLENGE_APPETITES:
        base["challenge_appetite"] = chal

    tone = str(src.get("communication_tone") or "").strip()
    if tone in COMMUNICATION_TONES:
        base["communication_tone"] = tone

    supp = str(src.get("learning_support") or src.get("learning_accommodation") or "").strip()
    if supp in LEARNING_SUPPORTS:
        base["learning_support"] = supp

    base["interest_tags"] = normalize_interest_tags(src.get("interest_tags"))

    fav_raw = src.get("interests")
    if fav_raw is None and interests is not None:
        if isinstance(interests, str):
            fav_raw = interests
        elif isinstance(interests, (list, tuple)):
            fav_raw = ", ".join(str(x).strip() for x in interests if str(x).strip())
    base["interests"] = str(fav_raw or "").strip()[:120]
    base["avatar_preset"] = child_avatar_preset(src.get("avatar_preset"))
    base["avatar_url"] = str(src.get("avatar_url") or "").strip()[:200_000]
    return base


def effective_child_profile(student: "Student | None") -> dict:
    if student is None:
        return default_child_profile(None)
    raw = getattr(student, "child_profile", None)
    return normalize_child_profile(
        raw if isinstance(raw, dict) else {},
        age=student.age,
        reading_level=student.reading_level,
        modality=student.modality,
        interests=student.interests,
    )


class Student(Base):
    """Layer 2 lives here. Older tutor_* columns are not what kid chat reads.

    Kid chat reads the single tutor_profiles row. These columns stay so a
    saved student row is not rewritten by a migration.
    """

    __tablename__ = "students"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    age: Mapped[int | None] = mapped_column(Integer)
    reading_level: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    modality: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    interests: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    child_profile: Mapped[dict] = mapped_column(JSON, nullable=False, default=default_child_profile)
    tutor_persona: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    tutor_lexicon: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tutor_metaphors: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tutor_sidekick: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    tutor_socratic_strictness: Mapped[str] = mapped_column(
        String(40), nullable=False, default="balanced"
    )
    tutor_struggle_window: Mapped[str] = mapped_column(
        String(40), nullable=False, default="minimum"
    )
    tutor_anti_spoiler: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    tutor_pacing: Mapped[str] = mapped_column(
        String(80), nullable=False, default="short-turns-one-question"
    )
    preferred_tutor_profile_id: Mapped[str | None] = mapped_column(
        String(120),
        ForeignKey("tutor_profiles.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sessions: Mapped[list[Session]] = relationship(back_populates="student")


ALL_BLOCK_TYPES = (
    "topic_goal",
    "mcq",
    "case_study",
    "socratic",
    "curiosity",
    "worked_example",
    "spot_the_flaw",
    "teach_back",
    "retrieval_check",
    "explanation",
)


def default_allowed_block_types() -> list[str]:
    return list(ALL_BLOCK_TYPES)


def default_kc_tutor_config() -> dict:
    return {
        "overarching": {
            "orient_framing": "elaborate_outline",
            "instructional_stance": "guided_discovery",
            "scaffolding_escalation": "progressive_nudge_then_scaffold",
            "stay_on_course": "brief_answer_then_return",
            "misconception_policy": "explain_and_retry_once",
            "prerequisite_support_policy": "inline_micro_recap",
            "encouragement_style": "process_praise",
            "close_summary_depth": "diagnostic_strengths_and_gaps",
        },
        "voice": {
            "persona": "coach",
            "vocabulary_register": "adaptive_to_child",
            "interest_weaving": "subtle_natural",
            "metaphors": "everyday",
            "humor_and_wit": "light_warm",
            "sidekick": "none",
        },
        "blocks": {
            "topic_goal": {
                "explanation_depth": 3,
                "max_retries_before_reveal": 3,
                "hint_ladder_style": "progressive_nudge_analogy_scaffold",
                "goal_evaluation_strictness": "conceptual_gist",
                "fragment_self_explanation": True,
                "enrichment_mode": "on_request",
            },
            "mcq": {
                "max_retry_attempts": 2,
                "wrong_answer_explanation_depth": 2,
                "disable_eliminated_choices": True,
                "confirm_why_on_correct": "on_retry_only",
                "correct_pass_explanation_depth": "reinforce_why",
            },
            "case_study": {
                "case_presentation": "sequential_predict_then_contrast",
                "explanation_depth": 3,
                "max_retries_before_reveal": 3,
                "require_transfer_application": True,
            },
            "socratic": {
                "dialogue_depth_turns": 2,
                "challenge_intensity": "counterexample_entrapment",
                "max_retries_before_reveal": 3,
                "hint_when_stuck": "highlight_contradiction",
            },
            "curiosity": {
                "max_wonder_turns": 2,
                "require_initial_prediction": True,
                "counts_toward_mastery_score": False,
                "hook_framing_style": "mystery_paradox",
            },
            "worked_example": {
                "fading_level": "single_blanked_step",
                "require_step_self_explanation": True,
                "max_retries_before_reveal": 2,
                "wrong_step_explanation_depth": 2,
            },
            "spot_the_flaw": {
                "critique_depth": "identify_and_correct",
                "wrong_answer_explanation_depth": 2,
                "max_retries_before_reveal": 2,
                "show_misconception_why": True,
            },
            "teach_back": {
                "peer_confusion_level": "curious_beginner",
                "follow_up_questions_count": 1,
                "max_retries_before_reveal": 2,
                "evaluation_strictness": "plain_language_clarity",
            },
            "retrieval_check": {
                "cue_scaffolding": "cued_hint_on_first_miss",
                "require_elaborative_why": True,
                "max_retries_before_reveal": 2,
                "accept_paraphrase": True,
            },
            "explanation": {
                "explanation_depth": 4,
                "allow_depth_override_student_length": True,
                "elaboration_style_on_question": "fresh_analogy_and_example",
                "check_in_prompt_style": "questions_or_elaborate",
                "end_of_block_summary_style": "bulleted_recap_with_takeaway",
                "counts_toward_mastery_score": False,
            },
        },
    }


DEFAULT_TUTOR_DESCRIPTION = (
    "Standard balanced AI Tutor profile using research-backed guided discovery "
    "and adaptive child vocabulary."
)


class TutorProfile(Base):
    """A configurable AI Tutor profile (Default + custom profiles)."""

    __tablename__ = "tutor_profiles"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_tutor_profiles_slug"),
        CheckConstraint(
            "instructive >= 1 AND instructive <= 5",
            name="ck_tutor_profiles_instructive",
        ),
    )

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    name: Mapped[str] = mapped_column(
        String(120), nullable=False, default="Default", server_default="Default"
    )
    slug: Mapped[str] = mapped_column(
        String(120), nullable=False, default="default", server_default="default"
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=DEFAULT_TUTOR_DESCRIPTION,
        server_default=DEFAULT_TUTOR_DESCRIPTION,
    )
    avatar_preset: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="default_circle",
        server_default="default_circle",
    )
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    instructive: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    persona: Mapped[str] = mapped_column(String(40), nullable=False)
    lexicon: Mapped[str] = mapped_column(String(40), nullable=False)
    voice_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metaphors: Mapped[str] = mapped_column(String(40), nullable=False)
    sidekick: Mapped[str] = mapped_column(String(40), nullable=False)
    struggle_window: Mapped[str] = mapped_column(String(16), nullable=False, default="standard")
    anti_spoiler: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    one_question: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    use_interests: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    stay_on_course: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    growth_praise: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    misconception_policy: Mapped[str] = mapped_column(
        String(32), nullable=False, default="retry_once", server_default="retry_once"
    )
    self_explanation: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    enrichment: Mapped[str] = mapped_column(
        String(16), nullable=False, default="on_request", server_default="on_request"
    )
    kc_tutor_config: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=default_kc_tutor_config, server_default="{}"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Course(Base):
    """A published course. Columns match the studio draft that import copies."""

    __tablename__ = "courses"
    __table_args__ = (
        CheckConstraint(
            "audience IN ('6-8', '9-11', '12-14', '15-17')",
            name="ck_courses_audience",
        ),
        CheckConstraint(
            "quiz_minutes IN (2, 5, 10)",
            name="ck_courses_quiz_minutes",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    audience: Mapped[str] = mapped_column(String(8), nullable=False, default="9-11")
    quest_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    goals_per_quest: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    quiz_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    in_catalog: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    quests: Mapped[list[Quest]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="Quest.position",
    )


class Quest(Base):
    __tablename__ = "quests"
    __table_args__ = (
        UniqueConstraint("course_id", "position", name="uq_quests_course_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    course: Mapped[Course] = relationship(back_populates="quests")
    goals: Mapped[list[QuestGoal]] = relationship(
        back_populates="quest",
        cascade="all, delete-orphan",
        order_by="QuestGoal.position",
    )
    close: Mapped[QuestClose | None] = relationship(
        back_populates="quest",
        cascade="all, delete-orphan",
        uselist=False,
    )
    sessions: Mapped[list[Session]] = relationship(back_populates="quest")


class QuestGoal(Base):
    """One learning goal and the single criterion that finishes it."""

    __tablename__ = "quest_goals"
    __table_args__ = (
        UniqueConstraint("quest_id", "position", name="uq_quest_goals_position"),
        CheckConstraint("position >= 1", name="ck_quest_goals_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    quest_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    learning_goal: Mapped[str] = mapped_column(Text, nullable=False, default="")
    success_criterion: Mapped[str] = mapped_column(Text, nullable=False, default="")

    quest: Mapped[Quest] = relationship(back_populates="goals")


class QuestClose(Base):
    """How a quest ends. Same columns as the studio close."""

    __tablename__ = "quest_closes"
    __table_args__ = (
        CheckConstraint(
            "close_style IN ('one', 'several')",
            name="ck_quest_closes_style",
        ),
        CheckConstraint(
            "answer_style IN ('multiple_choice', 'essay', 'mixed')",
            name="ck_quest_closes_answer",
        ),
        CheckConstraint(
            "choice_mode IS NULL OR choice_mode IN ('predefined', 'dynamic')",
            name="ck_quest_closes_choice",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    quest_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quests.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    close_style: Mapped[str] = mapped_column(String(16), nullable=False)
    answer_style: Mapped[str] = mapped_column(String(32), nullable=False)
    choice_mode: Mapped[str | None] = mapped_column(String(16))
    items: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    intent: Mapped[str] = mapped_column(Text, nullable=False, default="")

    quest: Mapped[Quest] = relationship(back_populates="close")


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('in_progress', 'completed')", name="ck_sessions_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quest_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quests.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    current_goal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("quest_goals.id", ondelete="SET NULL")
    )
    close_started: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    close_question_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="in_progress")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    student: Mapped[Student] = relationship(back_populates="sessions")
    quest: Mapped[Quest] = relationship(back_populates="sessions")
    current_goal: Mapped[QuestGoal | None] = relationship()
    messages: Mapped[list[Message]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.seq",
    )
    results: Mapped[list[GoalResult]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="GoalResult.seq",
    )
    prompts: Mapped[list[ModelPrompt]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ModelPrompt.seq",
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("session_id", "seq", name="uq_messages_session_seq"),
        CheckConstraint("role IN ('user', 'assistant')", name="ck_messages_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    client_id: Mapped[str | None] = mapped_column(String(200), unique=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[Session] = relationship(back_populates="messages")


class GoalResult(Base):
    """A goal's criterion, or the close answer, for one turn."""

    __tablename__ = "goal_results"
    __table_args__ = (
        UniqueConstraint("session_id", "seq", name="uq_goal_results_session_seq"),
        CheckConstraint("score >= 0 AND score <= 100", name="ck_goal_results_score"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    goal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("quest_goals.id", ondelete="SET NULL")
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    feedback: Mapped[str] = mapped_column(Text, nullable=False)
    criterion: Mapped[str] = mapped_column(Text, nullable=False, default="")
    answer: Mapped[str] = mapped_column(Text, nullable=False, default="")
    misconception: Mapped[str | None] = mapped_column(Text)
    hint_tier: Mapped[str | None] = mapped_column(String(16))
    choice: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[Session] = relationship(back_populates="results")
    goal: Mapped[QuestGoal | None] = relationship()


class ModelPrompt(Base):
    """One model call: the system prompt plus the messages sent to the model."""

    __tablename__ = "model_prompts"
    __table_args__ = (
        UniqueConstraint("session_id", "seq", name="uq_model_prompts_session_seq"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    messages: Mapped[list] = mapped_column(JSON, nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[Session] = relationship(back_populates="prompts")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StudioCourse(Base):
    """A course built in CreateCourse. Separate from the tutor courses table."""

    __tablename__ = "studio_courses"
    __table_args__ = (
        CheckConstraint(
            "depth IN ('survey', 'standard', 'go_deep')",
            name="ck_studio_courses_depth",
        ),
        CheckConstraint(
            "quiz_minutes IN (2, 5, 10)",
            name="ck_studio_courses_quiz_minutes",
        ),
        CheckConstraint("schema_version >= 1", name="ck_studio_courses_schema_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    audience: Mapped[str] = mapped_column(Text, nullable=False, default="")
    quest_count: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    goals_per_quest: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    focus: Mapped[str] = mapped_column(Text, nullable=False, default="")
    theme: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    depth: Mapped[str] = mapped_column(String(16), nullable=False, default="standard")
    quiz_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=5, server_default="5")
    sources: Mapped[str] = mapped_column(Text, nullable=False, default="")
    preferences: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )

    quests: Mapped[list["StudioQuest"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="StudioQuest.position",
    )
    messages: Mapped[list["StudioMessage"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="StudioMessage.seq",
    )


class StudioQuest(Base):
    """A quest on the course. Every goal, including the first, is its own row."""

    __tablename__ = "studio_quests"
    __table_args__ = (
        UniqueConstraint("course_id", "code", name="uq_studio_quests_course_code"),
        CheckConstraint("position >= 1", name="ck_studio_quests_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("studio_courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)

    course: Mapped[StudioCourse] = relationship(back_populates="quests")
    close: Mapped["StudioQuestClose | None"] = relationship(
        back_populates="quest",
        cascade="all, delete-orphan",
        uselist=False,
    )
    goals: Mapped[list["StudioQuestGoal"]] = relationship(
        back_populates="quest",
        cascade="all, delete-orphan",
        order_by="StudioQuestGoal.position",
    )


class StudioQuestGoal(Base):
    """One goal on a quest, including the first."""

    __tablename__ = "studio_quest_goals"
    __table_args__ = (
        UniqueConstraint("quest_id", "position", name="uq_studio_quest_goals_position"),
        CheckConstraint("position >= 1", name="ck_studio_quest_goals_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    quest_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("studio_quests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    learning_goal: Mapped[str] = mapped_column(Text, nullable=False, default="")
    success_criterion: Mapped[str] = mapped_column(Text, nullable=False, default="")

    quest: Mapped[StudioQuest] = relationship(back_populates="goals")


class StudioQuestClose(Base):
    """How a quest ends. One row per quest. Dynamic choices store intent only."""

    __tablename__ = "studio_quest_close"
    __table_args__ = (
        CheckConstraint(
            "close_style IN ('one', 'several')",
            name="ck_studio_quest_close_style",
        ),
        CheckConstraint(
            "answer_style IN ('multiple_choice', 'essay', 'mixed')",
            name="ck_studio_quest_close_answer",
        ),
        CheckConstraint(
            "choice_mode IS NULL OR choice_mode IN ('predefined', 'dynamic')",
            name="ck_studio_quest_close_choice",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    quest_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("studio_quests.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    close_style: Mapped[str] = mapped_column(String(16), nullable=False)
    answer_style: Mapped[str] = mapped_column(String(32), nullable=False)
    choice_mode: Mapped[str | None] = mapped_column(String(16))
    items: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    intent: Mapped[str] = mapped_column(Text, nullable=False, default="")

    quest: Mapped[StudioQuest] = relationship(back_populates="close")


class StudioMessage(Base):
    """Creation chat for one studio course. Not a kid session."""

    __tablename__ = "studio_messages"
    __table_args__ = (
        UniqueConstraint("course_id", "seq", name="uq_studio_messages_course_seq"),
        CheckConstraint("role IN ('user', 'assistant')", name="ck_studio_messages_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("studio_courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    proposal: Mapped[dict | None] = mapped_column(JSON)
    applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )

    course: Mapped[StudioCourse] = relationship(back_populates="messages")


class StudioSettings(Base):
    """The CreateCourse model. The kid tutor does not read this row."""

    __tablename__ = "studio_settings"
    __table_args__ = (
        CheckConstraint("id = 'default'", name="ck_studio_settings_singleton"),
        CheckConstraint(
            "model IN ('gpt-4o-mini', 'gpt-4o', 'gpt-4.1-mini', "
            "'deepseek/deepseek-flash-latest', '~deepseek/deepseek-flash-latest')",
            name="ck_studio_settings_model",
        ),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    model: Mapped[str] = mapped_column(String(64), nullable=False, default="gpt-4o-mini")


def without_legacy_blocks(value: object) -> list:
    """Drop the retired type blob so it cannot appear as a block."""
    if not isinstance(value, list):
        return []
    return [
        item
        for item in value
        if not (isinstance(item, dict) and str(item.get("type") or "") == "_legacy")
    ]


class BlockList(TypeDecorator):
    """JSON block list. A retired `_legacy` blob is removed on read and on write."""

    impl = JSON
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return []
        return without_legacy_blocks(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return []
        return without_legacy_blocks(value)


class KcNode(Base):
    """One knowledge component. The kid chat and the course catalog do not read this table."""

    __tablename__ = "kc_nodes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    outline: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    topics: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    blocks: Mapped[list] = mapped_column(BlockList, nullable=False, default=list, server_default="[]")
    core_truth: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rubric: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    misconceptions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    standards: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    prerequisite_codes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    encompasses_codes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    marked_complete: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    history: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )

    def __init__(self, **kwargs):
        # In-memory only. These are not columns and are not written into blocks.
        self._kc_type_memory = kwargs.pop("kc_type", None)
        fields = kwargs.pop("type_fields", None)
        self._type_fields_memory = fields if isinstance(fields, dict) else {}
        super().__init__(**kwargs)

    @property
    def kc_type(self) -> str | None:
        value = getattr(self, "_kc_type_memory", None)
        text = str(value).strip() if value else ""
        return text or None

    @property
    def type_fields(self) -> dict:
        raw = getattr(self, "_type_fields_memory", None)
        return raw if isinstance(raw, dict) else {}


class KcEdge(Base):
    """A prerequisite or an encompasses link. Both ends are knowledge components."""

    __tablename__ = "kc_edges"
    __table_args__ = (
        UniqueConstraint("from_kc", "to_kc", "kind", name="uq_kc_edges_ends_kind"),
        CheckConstraint(
            "kind IN ('prerequisite_of', 'encompasses')",
            name="ck_kc_edges_kind",
        ),
        CheckConstraint("from_kc <> to_kc", name="ck_kc_edges_distinct"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    from_kc: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("kc_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    to_kc: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("kc_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1)


class KcGoal(Base):
    """A Plane 2 course: a goal made of knowledge components. Not a quest course."""

    __tablename__ = "kc_goals"
    __table_args__ = (
        CheckConstraint(
            "audience IN ('6-8', '9-11', '12-14', '15-17')",
            name="ck_kc_goals_audience",
        ),
        CheckConstraint(
            "kind IN ('mastery', 'time_boxed', 'curiosity')",
            name="ck_kc_goals_kind",
        ),
        CheckConstraint(
            "minutes IS NULL OR minutes > 0",
            name="ck_kc_goals_minutes",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    audience: Mapped[str] = mapped_column(String(8), nullable=False, default="9-11")
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="mastery")
    minutes: Mapped[int | None] = mapped_column(Integer)
    target_kc_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    allowed_block_types: Mapped[list] = mapped_column(
        JSON, nullable=False, default=default_allowed_block_types, server_default="[]"
    )
    intake: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    brief: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    blueprint: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    drafting: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    standards: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    history: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )


class KcState(Base):
    """What one student knows about one component."""

    __tablename__ = "kc_states"
    __table_args__ = (
        UniqueConstraint("student_id", "kc_id", name="uq_kc_states_student_kc"),
        CheckConstraint(
            "status IN ('unknown', 'fragile', 'known')",
            name="ck_kc_states_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    kc_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("kc_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    stability: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    last_practiced: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict | None] = mapped_column(JSON)


class KcSession(Base):
    """One session is one component. Tutor settings are not copied onto this row."""

    __tablename__ = "kc_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('in_progress', 'completed')",
            name="ck_kc_sessions_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    goal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("kc_goals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kc_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("kc_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tutor_profile_id: Mapped[str | None] = mapped_column(
        String(120),
        ForeignKey("tutor_profiles.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )
    recipe: Mapped[str] = mapped_column(String(40), nullable=False, default="block_walk", server_default="block_walk")
    step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active_block_id: Mapped[str | None] = mapped_column(String(80))
    active_block_state: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    block_results: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    score: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="in_progress")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    redirect_kc_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("kc_nodes.id", ondelete="SET NULL")
    )
    hint_tier: Mapped[str] = mapped_column(String(16), nullable=False, default="nudge", server_default="nudge")
    move_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    reveals: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    off_course_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    affect: Mapped[str] = mapped_column(String(16), nullable=False, default="", server_default="")
    enrichment_turns: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    help_requested: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    rubric_met: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    last_misconception: Mapped[str] = mapped_column(String(240), nullable=False, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )

    student: Mapped[Student] = relationship()
    goal: Mapped[KcGoal] = relationship()
    component: Mapped[KcNode] = relationship(foreign_keys=[kc_id])
    messages: Mapped[list["KcMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="KcMessage.seq",
    )
    prompts: Mapped[list["KcModelPrompt"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="KcModelPrompt.seq",
    )


class KcMessage(Base):
    """A turn inside one component session. Not a kid-chat message."""

    __tablename__ = "kc_messages"
    __table_args__ = (
        UniqueConstraint("session_id", "seq", name="uq_kc_messages_session_seq"),
        CheckConstraint("role IN ('user', 'assistant')", name="ck_kc_messages_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("kc_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )

    session: Mapped[KcSession] = relationship(back_populates="messages")


class KcModelPrompt(Base):
    """One model call for a component session: the system prompt and the messages sent."""

    __tablename__ = "kc_model_prompts"
    __table_args__ = (
        UniqueConstraint("session_id", "seq", name="uq_kc_model_prompts_session_seq"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("kc_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("kc_messages.id", ondelete="SET NULL"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    messages: Mapped[list] = mapped_column(JSON, nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    rubric_met: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    misconception: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[KcSession] = relationship(back_populates="prompts")


class KcCreatorMessage(Base):
    """One turn of the KC Creator chat for a component. Not a kid-tutor kc_messages row."""

    __tablename__ = "kc_creator_messages"
    __table_args__ = (
        UniqueConstraint("node_id", "seq", name="uq_kc_creator_messages_node_seq"),
        CheckConstraint("role IN ('user', 'assistant')", name="ck_kc_creator_messages_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("kc_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    draft: Mapped[dict | None] = mapped_column(JSON)
    applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )


class AiSafetySettings(Base):
    """The one global safety row. It is not stored on a tutor profile."""

    __tablename__ = "ai_safety_settings"
    __table_args__ = (
        CheckConstraint("id = 'global'", name="ck_ai_safety_settings_singleton"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    settings: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )


class AiSafetyEvent(Base):
    """One flagged tutor turn, kept apart from the chat transcript."""

    __tablename__ = "ai_safety_events"
    __table_args__ = (
        CheckConstraint(
            "category IN ('distress', 'inappropriate_content', 'personal_info', 'manipulation', 'other')",
            name="ck_ai_safety_events_category",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kc_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("kc_sessions.id", ondelete="CASCADE"), nullable=True, index=True
    )
    kc_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("kc_messages.id", ondelete="SET NULL"), nullable=True
    )
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("kc_goals.id", ondelete="CASCADE"), nullable=True
    )
    node_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("kc_nodes.id", ondelete="CASCADE"), nullable=True
    )
    tutor_profile_id: Mapped[str | None] = mapped_column(
        String(120),
        ForeignKey("tutor_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    strictness: Mapped[str] = mapped_column(String(40), nullable=False)
    child_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tutor_reply: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
