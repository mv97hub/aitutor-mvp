from __future__ import annotations

import uuid
from datetime import datetime

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
QUEST_TYPES = ("core", "branch", "capstone")
BEAT_ROLES = (
    "engage",
    "try",
    "name",
    "show",
    "teach_back",
)


class Student(Base):
    """Layer 2 lives here. Layers 3 and 4 are tutor-agent settings stored on the
    student until a tutor profile exists. Those columns are named tutor_* so
    the later move is a relocation, not a redesign.
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


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (
        CheckConstraint(
            "age_band IN ('6-8', '9-11', '12-14', '15-17')",
            name="ck_courses_age_band",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    age_band: Mapped[str] = mapped_column(String(8), nullable=False)
    standards_alignment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    competency_dictionary: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    units: Mapped[list[Unit]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="Unit.number",
    )


class Unit(Base):
    __tablename__ = "units"
    __table_args__ = (
        UniqueConstraint("course_id", "number", name="uq_units_course_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    enduring_understanding: Mapped[str] = mapped_column(Text, nullable=False, default="")
    continuity_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_diagnostic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_capstone: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    course: Mapped[Course] = relationship(back_populates="units")
    quests: Mapped[list[Quest]] = relationship(
        back_populates="unit",
        cascade="all, delete-orphan",
        order_by="Quest.position",
    )


class Quest(Base):
    __tablename__ = "quests"
    __table_args__ = (
        UniqueConstraint("unit_id", "position", name="uq_quests_unit_position"),
        CheckConstraint(
            "quest_type IN ('core', 'branch', 'capstone')",
            name="ck_quests_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    unit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("units.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    quest_type: Mapped[str] = mapped_column(String(16), nullable=False, default="core")
    prerequisite_codes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    competency_tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    dinner_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    learning_goal: Mapped[str] = mapped_column(Text, nullable=False, default="")
    success_criterion: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    requires_teach_back: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    unit: Mapped[Unit] = relationship(back_populates="quests")
    beats: Mapped[list[Beat]] = relationship(
        back_populates="quest",
        cascade="all, delete-orphan",
        order_by="Beat.position",
    )
    sessions: Mapped[list[Session]] = relationship(back_populates="quest")


class Beat(Base):
    __tablename__ = "beats"
    __table_args__ = (
        UniqueConstraint("quest_id", "position", name="uq_beats_quest_position"),
        CheckConstraint(
            "role IN ('engage', 'try', 'name', 'show', 'teach_back')",
            name="ck_beats_role",
        ),
        CheckConstraint("position >= 1", name="ck_beats_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    quest_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    bloom_level: Mapped[str] = mapped_column(String(32), nullable=False, default="understand")
    cognitive_load: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rubric: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    misconception_map: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    hint_ladder: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    widget: Mapped[dict | None] = mapped_column(JSON)

    quest: Mapped[Quest] = relationship(back_populates="beats")
    results: Mapped[list[BeatResult]] = relationship(back_populates="beat")


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
    current_beat_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("beats.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="in_progress")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    student: Mapped[Student] = relationship(back_populates="sessions")
    quest: Mapped[Quest] = relationship(back_populates="sessions")
    messages: Mapped[list[Message]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.seq",
    )
    results: Mapped[list[BeatResult]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="BeatResult.seq",
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


class BeatResult(Base):
    __tablename__ = "beat_results"
    __table_args__ = (
        UniqueConstraint("session_id", "seq", name="uq_beat_results_session_seq"),
        CheckConstraint("score >= 0 AND score <= 100", name="ck_beat_results_score"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    beat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("beats.id", ondelete="RESTRICT"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    feedback: Mapped[str] = mapped_column(Text, nullable=False)
    rubric_met: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    misconception: Mapped[str | None] = mapped_column(Text)
    hint_tier: Mapped[str | None] = mapped_column(String(16))
    choice: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[Session] = relationship(back_populates="results")
    beat: Mapped[Beat] = relationship(back_populates="results")


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
