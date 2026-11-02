from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    age: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sessions: Mapped[list[Session]] = relationship(back_populates="student")


class LessonPlan(Base):
    __tablename__ = "lesson_plans"
    __table_args__ = (
        Index(
            "uq_lesson_plans_one_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    preamble: Mapped[str] = mapped_column(Text, nullable=False, default="")
    age_min: Mapped[int | None] = mapped_column(Integer)
    age_max: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    topics: Mapped[list[Topic]] = relationship(
        back_populates="lesson_plan",
        cascade="all, delete-orphan",
        order_by="Topic.position",
    )
    sessions: Mapped[list[Session]] = relationship(back_populates="lesson_plan")


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (
        UniqueConstraint("lesson_plan_id", "position", name="uq_topics_plan_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    lesson_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lesson_plans.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    learning_goal: Mapped[str] = mapped_column(Text, nullable=False)
    tutor_instructions: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    lesson_plan: Mapped[LessonPlan] = relationship(back_populates="topics")
    checkpoints: Mapped[list[Checkpoint]] = relationship(
        back_populates="topic",
        cascade="all, delete-orphan",
        order_by="Checkpoint.position",
    )


class Checkpoint(Base):
    __tablename__ = "checkpoints"
    __table_args__ = (
        UniqueConstraint("topic_id", "position", name="uq_checkpoints_topic_position"),
        CheckConstraint(
            "kind IN ('teach', 'practice', 'quiz', 'discovery', 'teach_back')",
            name="ck_checkpoints_kind",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    tutor_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    rubric: Mapped[str | None] = mapped_column(Text)
    pass_criteria: Mapped[str | None] = mapped_column(Text)
    objective: Mapped[str | None] = mapped_column(Text)
    rubric_rows: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    hint_ladder: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    pass_score: Mapped[int] = mapped_column(Integer, nullable=False, default=70)
    quiz: Mapped[dict | None] = mapped_column(JSON)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    topic: Mapped[Topic] = relationship(back_populates="checkpoints")
    results: Mapped[list[CheckpointResult]] = relationship(back_populates="checkpoint")


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
    lesson_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lesson_plans.id", ondelete="RESTRICT"), nullable=False
    )
    current_topic_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("topics.id", ondelete="RESTRICT")
    )
    current_checkpoint_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("checkpoints.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="in_progress")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    student: Mapped[Student] = relationship(back_populates="sessions")
    lesson_plan: Mapped[LessonPlan] = relationship(back_populates="sessions")
    messages: Mapped[list[Message]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.seq",
    )
    results: Mapped[list[CheckpointResult]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="CheckpointResult.seq",
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


class CheckpointResult(Base):
    __tablename__ = "checkpoint_results"
    __table_args__ = (
        UniqueConstraint("session_id", "seq", name="uq_results_session_seq"),
        CheckConstraint("score >= 0 AND score <= 100", name="ck_results_score"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    checkpoint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("checkpoints.id", ondelete="RESTRICT"), nullable=False
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
    checkpoint: Mapped[Checkpoint] = relationship(back_populates="results")


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
