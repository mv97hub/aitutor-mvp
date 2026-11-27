"""F2: Quarantined blind pre/post exam tables (blind_exams, blind_exam_attempts).

Revision ID: 048_blind_evaluator_tables
Revises: 047_graph2_skills_and_state
Create Date: 2026-11-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "048_blind_evaluator_tables"
down_revision: Union[str, Sequence[str], None] = "047_graph2_skills_and_state"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "blind_exams",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("goal_id", sa.Uuid(), nullable=False),
        sa.Column("phase", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("spec_fingerprint", sa.String(length=64), server_default="", nullable=False),
        sa.Column("items", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("rubric_key", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("phase IN ('pre', 'post')", name="ck_blind_exams_phase"),
        sa.CheckConstraint("version >= 1", name="ck_blind_exams_version"),
        sa.ForeignKeyConstraint(["goal_id"], ["kc_goals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("goal_id", "phase", "version", name="uq_blind_exams_goal_phase_version"),
    )
    op.create_index("ix_blind_exams_goal_phase", "blind_exams", ["goal_id", "phase", "spec_fingerprint"])

    op.create_table(
        "blind_exam_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("exam_id", sa.Uuid(), nullable=False),
        sa.Column("goal_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=True),
        sa.Column("harness_chat_id", sa.Uuid(), nullable=True),
        sa.Column("phase", sa.String(length=16), nullable=False),
        sa.Column("mode", sa.String(length=24), server_default="human", nullable=False),
        sa.Column("status", sa.String(length=24), server_default="graded", nullable=False),
        sa.Column("answers", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("item_grades", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("raw_score", sa.Float(), nullable=True),
        sa.Column("mcq_score", sa.Float(), nullable=True),
        sa.Column("transfer_score", sa.Float(), nullable=True),
        sa.Column("paired_pre_attempt_id", sa.Uuid(), nullable=True),
        sa.Column("paired_pre_score", sa.Float(), nullable=True),
        sa.Column("hake_g", sa.Float(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("phase IN ('pre', 'post')", name="ck_blind_exam_attempts_phase"),
        sa.CheckConstraint("mode IN ('human', 'epistemic_sandbox')", name="ck_blind_exam_attempts_mode"),
        sa.CheckConstraint("status IN ('in_progress', 'graded')", name="ck_blind_exam_attempts_status"),
        sa.CheckConstraint(
            "raw_score IS NULL OR (raw_score >= 0.0 AND raw_score <= 1.0)",
            name="ck_blind_exam_attempts_raw_score",
        ),
        sa.ForeignKeyConstraint(["exam_id"], ["blind_exams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["goal_id"], ["kc_goals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_blind_exam_attempts_student_goal_phase",
        "blind_exam_attempts",
        ["student_id", "goal_id", "phase", "submitted_at"],
    )
    op.create_index("ix_blind_exam_attempts_exam_id", "blind_exam_attempts", ["exam_id"])
    op.create_index("ix_blind_exam_attempts_harness_chat_id", "blind_exam_attempts", ["harness_chat_id"])


def downgrade() -> None:
    op.drop_index("ix_blind_exam_attempts_harness_chat_id", table_name="blind_exam_attempts")
    op.drop_index("ix_blind_exam_attempts_exam_id", table_name="blind_exam_attempts")
    op.drop_index("ix_blind_exam_attempts_student_goal_phase", table_name="blind_exam_attempts")
    op.drop_table("blind_exam_attempts")
    op.drop_index("ix_blind_exams_goal_phase", table_name="blind_exams")
    op.drop_table("blind_exams")
