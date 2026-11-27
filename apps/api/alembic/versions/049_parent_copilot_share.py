"""F6: Active Parent Co-Pilot digests, course policy locks, catalog metadata, and revocable teacher shares.

Revision ID: 049_parent_copilot_share
Revises: 048_blind_evaluator_tables
Create Date: 2026-11-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "049_parent_copilot_share"
down_revision: Union[str, Sequence[str], None] = "048_blind_evaluator_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Course catalog metadata on kc_goals
    op.add_column(
        "kc_goals",
        sa.Column("catalog_tier", sa.String(length=24), server_default="core", nullable=False),
    )
    op.add_column(
        "kc_goals",
        sa.Column("upvotes_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "kc_goals",
        sa.Column("default_archetype", sa.String(length=64), nullable=True),
    )
    op.create_check_constraint(
        "ck_kc_goals_catalog_tier",
        "kc_goals",
        "catalog_tier IN ('core', 'enrichment', 'custom')",
    )
    op.create_check_constraint(
        "ck_kc_goals_upvotes_non_negative",
        "kc_goals",
        "upvotes_count >= 0",
    )

    # 2. Reuse F3's learner_course_state for course mode & parent policy locks (single (student_id, goal_id) table)
    op.add_column(
        "learner_course_state",
        sa.Column("course_mode", sa.String(length=24), server_default="mastery", nullable=False),
    )
    op.add_column(
        "learner_course_state",
        sa.Column("parent_policy_locks", sa.JSON(), server_default="{}", nullable=False),
    )
    op.create_check_constraint(
        "ck_learner_course_state_course_mode",
        "learner_course_state",
        "course_mode IN ('explore', 'mastery', 'exam_prep')",
    )

    # 3. Auto-persisted Parent Co-Pilot session digests
    op.create_table(
        "parent_session_digests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("goal_id", sa.Uuid(), nullable=True),
        sa.Column("kc_id", sa.Uuid(), nullable=False),
        sa.Column("trajectory_state", sa.String(length=32), server_default="steady_progress", nullable=False),
        sa.Column("summary", sa.Text(), server_default="", nullable=False),
        sa.Column("talking_points", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("biomarkers_snapshot", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("recommended_interventions", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "trajectory_state IN ('flourishing', 'steady_progress', 'needs_reinforcement', 'struggling', 'returning')",
            name="ck_parent_session_digests_trajectory",
        ),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["kc_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["goal_id"], ["kc_goals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["kc_id"], ["kc_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", name="uq_parent_session_digests_session_id"),
    )
    op.create_index(
        "ix_parent_session_digests_student_created",
        "parent_session_digests",
        ["student_id", "created_at"],
    )

    # 4. Revocable SHA-256 Teacher Share tokens
    op.create_table(
        "teacher_share_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_prefix", sa.String(length=16), server_default="", nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("goal_id", sa.Uuid(), nullable=True),
        sa.Column("label", sa.String(length=120), server_default="", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["parents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["goal_id"], ["kc_goals.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_teacher_share_tokens_hash"),
    )
    op.create_index(
        "ix_teacher_share_tokens_parent_student",
        "teacher_share_tokens",
        ["parent_id", "student_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_teacher_share_tokens_parent_student", table_name="teacher_share_tokens")
    op.drop_table("teacher_share_tokens")

    op.drop_index("ix_parent_session_digests_student_created", table_name="parent_session_digests")
    op.drop_table("parent_session_digests")

    op.drop_constraint("ck_learner_course_state_course_mode", "learner_course_state", type_="check")
    op.drop_column("learner_course_state", "parent_policy_locks")
    op.drop_column("learner_course_state", "course_mode")

    op.drop_constraint("ck_kc_goals_upvotes_non_negative", "kc_goals", type_="check")
    op.drop_constraint("ck_kc_goals_catalog_tier", "kc_goals", type_="check")
    op.drop_column("kc_goals", "default_archetype")
    op.drop_column("kc_goals", "upvotes_count")
    op.drop_column("kc_goals", "catalog_tier")
