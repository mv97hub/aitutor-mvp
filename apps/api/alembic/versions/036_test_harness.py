"""Test children and the harness run tables.

Adds students.is_test. Existing rows stay real children.
Nothing already stored is rewritten.

Revision ID: 036_test_harness
Revises: 035_gpt6_luna_model
Create Date: 2026-11-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "036_test_harness"
down_revision: Union[str, None] = "035_gpt6_luna_model"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "students",
        sa.Column("is_test", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "harness_personas",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("age", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("child_profile", sa.JSON(), nullable=False),
        sa.Column("traits", sa.JSON(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("number", name="uq_harness_personas_number"),
        sa.UniqueConstraint("name", name="uq_harness_personas_name"),
    )
    op.create_table(
        "harness_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("plan", sa.JSON(), nullable=False),
        sa.Column("totals", sa.JSON(), nullable=False),
        sa.Column("code_version", sa.String(80), nullable=False, server_default=""),
        sa.Column("suite_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'paused', 'completed', 'cancelled')",
            name="ck_harness_runs_status",
        ),
    )
    op.create_table(
        "harness_chats",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("harness_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("persona_id", sa.Uuid(), sa.ForeignKey("harness_personas.id", ondelete="SET NULL"), nullable=True),
        sa.Column("child_snapshot", sa.JSON(), nullable=False),
        sa.Column("student_id", sa.Uuid(), sa.ForeignKey("students.id", ondelete="SET NULL"), nullable=True),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("kc_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("course_id", sa.Uuid(), nullable=True),
        sa.Column("component_id", sa.Uuid(), nullable=True),
        sa.Column("tutor_model", sa.String(120), nullable=False, server_default=""),
        sa.Column("child_model", sa.String(120), nullable=False, server_default=""),
        sa.Column("judge_model", sa.String(120), nullable=False, server_default=""),
        sa.Column("tutor_profile_id", sa.String(120), nullable=True),
        sa.Column("settings_copy", sa.JSON(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("iteration", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("behavior", sa.String(16), nullable=False, server_default="rule"),
        sa.Column("script", sa.JSON(), nullable=False),
        sa.Column("ended_how", sa.String(32), nullable=False, server_default=""),
        sa.Column("tokens", sa.JSON(), nullable=False),
        sa.Column("cost_usd", sa.String(32), nullable=True),
        sa.Column("luna_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("turn_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'paused', 'completed', 'cancelled', 'failed')",
            name="ck_harness_chats_status",
        ),
    )
    op.create_index("ix_harness_chats_run_id", "harness_chats", ["run_id"])
    op.create_table(
        "harness_turns",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("chat_id", sa.Uuid(), sa.ForeignKey("harness_chats.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("intent", sa.String(40), nullable=False, server_default=""),
        sa.Column("child_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("inner_state", sa.JSON(), nullable=False),
        sa.Column("session_before", sa.JSON(), nullable=False),
        sa.Column("session_after", sa.JSON(), nullable=False),
        sa.Column("child_tokens", sa.JSON(), nullable=False),
        sa.Column("elapsed_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("chat_id", "seq", name="uq_harness_turns_chat_seq"),
    )
    op.create_index("ix_harness_turns_chat_id", "harness_turns", ["chat_id"])


def downgrade() -> None:
    op.drop_index("ix_harness_turns_chat_id", table_name="harness_turns")
    op.drop_table("harness_turns")
    op.drop_index("ix_harness_chats_run_id", table_name="harness_chats")
    op.drop_table("harness_chats")
    op.drop_table("harness_runs")
    op.drop_table("harness_personas")
    op.drop_column("students", "is_test")
