"""Initial tutor tables.

Revision ID: 001_initial
Revises:
Create Date: 2026-11-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "students",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("slug", name="uq_students_slug"),
    )
    op.create_table(
        "lesson_plans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("preamble", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("slug", name="uq_lesson_plans_slug"),
    )
    op.create_index(
        "uq_lesson_plans_one_active",
        "lesson_plans",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_table(
        "topics",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("lesson_plan_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("learning_goal", sa.Text(), nullable=False),
        sa.Column("tutor_instructions", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["lesson_plan_id"], ["lesson_plans.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "lesson_plan_id", "position", name="uq_topics_plan_position"
        ),
    )
    op.create_table(
        "checkpoints",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("tutor_prompt", sa.Text(), nullable=False),
        sa.Column("rubric", sa.Text()),
        sa.Column("pass_criteria", sa.Text()),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('teach', 'practice', 'quiz')", name="ck_checkpoints_kind"
        ),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "topic_id", "position", name="uq_checkpoints_topic_position"
        ),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("lesson_plan_id", sa.Uuid(), nullable=False),
        sa.Column("current_topic_id", sa.Uuid()),
        sa.Column("current_checkpoint_id", sa.Uuid()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('in_progress', 'completed')", name="ck_sessions_status"
        ),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["lesson_plan_id"], ["lesson_plans.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["current_topic_id"], ["topics.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["current_checkpoint_id"], ["checkpoints.id"], ondelete="RESTRICT"
        ),
    )
    op.create_index("ix_sessions_student_id", "sessions", ["student_id"])
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("client_id", sa.String(200)),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_messages_role"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("session_id", "seq", name="uq_messages_session_seq"),
        sa.UniqueConstraint("client_id", name="uq_messages_client_id"),
    )
    op.create_index("ix_messages_session_id", "messages", ["session_id"])
    op.create_table(
        "checkpoint_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("checkpoint_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_results_score"),
        sa.UniqueConstraint("session_id", "seq", name="uq_results_session_seq"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["checkpoint_id"], ["checkpoints.id"], ondelete="RESTRICT"
        ),
    )
    op.create_index(
        "ix_checkpoint_results_session_id", "checkpoint_results", ["session_id"]
    )


def downgrade() -> None:
    op.drop_table("checkpoint_results")
    op.drop_table("messages")
    op.drop_table("sessions")
    op.drop_table("checkpoints")
    op.drop_table("topics")
    op.drop_index("uq_lesson_plans_one_active", table_name="lesson_plans")
    op.drop_table("lesson_plans")
    op.drop_table("students")
