from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

AGE_BANDS = ("6-8", "9-11", "12-14", "15-17")


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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sessions: Mapped[list[Session]] = relationship(back_populates="student")


class TutorProfile(Base):
    """One default tutor profile, applied to every student."""

    __tablename__ = "tutor_profiles"
    __table_args__ = (
        CheckConstraint("id = 'default'", name="ck_tutor_profiles_singleton"),
        CheckConstraint(
            "instructive >= 1 AND instructive <= 5",
            name="ck_tutor_profiles_instructive",
        ),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
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
            "model IN ('gpt-4o-mini', 'gpt-4o', 'gpt-4.1-mini')",
            name="ck_studio_settings_model",
        ),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    model: Mapped[str] = mapped_column(String(64), nullable=False, default="gpt-4o-mini")
