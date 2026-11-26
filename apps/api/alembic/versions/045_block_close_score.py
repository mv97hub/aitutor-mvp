"""Pin a scoring version and store visits, requirements, and turn receipts.

Existing sessions stay on scoring version 1. The new columns default there,
and this migration does not invent a requirement score for a session that
is already running. A course run is stored so a restart can tell an old
completion from the current run. Nothing here rewrites a stored score.

Revision ID: 045_block_close_score
Revises: 044_kc_mastery_spec
Create Date: 2026-11-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "045_block_close_score"
down_revision: Union[str, None] = "044_kc_mastery_spec"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kc_course_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("student_id", sa.Uuid(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("goal_id", sa.Uuid(), sa.ForeignKey("kc_goals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(
        "ix_kc_course_runs_student_goal",
        "kc_course_runs",
        ["student_id", "goal_id", "created_at"],
    )
    op.add_column(
        "kc_sessions",
        sa.Column("scoring_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "kc_sessions",
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "kc_sessions",
        sa.Column("course_run_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "kc_sessions",
        sa.Column("verdict", sa.String(length=16), nullable=True),
    )
    op.create_foreign_key(
        "fk_kc_sessions_course_run_id",
        "kc_sessions",
        "kc_course_runs",
        ["course_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_kc_sessions_scoring_version",
        "kc_sessions",
        "scoring_version IN (1, 2)",
    )
    op.create_check_constraint(
        "ck_kc_sessions_verdict",
        "kc_sessions",
        "verdict IS NULL OR verdict IN ('known', 'fragile', 'unassessed')",
    )
    op.create_table(
        "kc_visits",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("kc_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_run_id", sa.Uuid(), sa.ForeignKey("kc_course_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("block_id", sa.String(length=80), nullable=False),
        sa.Column("block_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('open', 'finished')", name="ck_kc_visits_status"),
    )
    op.create_index("ix_kc_visits_session_id", "kc_visits", ["session_id"])
    op.create_table(
        "kc_requirements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("visit_id", sa.Uuid(), sa.ForeignKey("kc_visits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("kc_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requirement_key", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("observation", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gave_up", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("ordinal", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("role IN ('assessed', 'participation')", name="ck_kc_requirements_role"),
        sa.CheckConstraint(
            "observation IN ('open', 'insufficient', 'assisted', 'independent', 'participated')",
            name="ck_kc_requirements_observation",
        ),
    )
    op.create_index("ix_kc_requirements_visit_id", "kc_requirements", ["visit_id"])
    op.create_index("ix_kc_requirements_session_id", "kc_requirements", ["session_id"])
    op.create_table(
        "kc_turn_receipts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("kc_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_turn_id", sa.String(length=80), nullable=False),
        sa.Column("route", sa.String(length=16), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("payload", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="claimed"),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("opening_key", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("route IN ('answer', 'speech')", name="ck_kc_turn_receipts_route"),
        sa.CheckConstraint("status IN ('claimed', 'committed')", name="ck_kc_turn_receipts_status"),
        sa.UniqueConstraint("session_id", "client_turn_id", name="uq_kc_turn_receipts_session_turn"),
    )
    op.create_index("ix_kc_turn_receipts_session_id", "kc_turn_receipts", ["session_id"])
    op.create_index(
        "uq_kc_turn_receipts_speech_opening",
        "kc_turn_receipts",
        ["session_id", "revision"],
        unique=True,
        postgresql_where=sa.text("route = 'speech'"),
    )


def downgrade() -> None:
    op.drop_index("uq_kc_turn_receipts_speech_opening", table_name="kc_turn_receipts")
    op.drop_index("ix_kc_turn_receipts_session_id", table_name="kc_turn_receipts")
    op.drop_table("kc_turn_receipts")
    op.drop_index("ix_kc_requirements_session_id", table_name="kc_requirements")
    op.drop_index("ix_kc_requirements_visit_id", table_name="kc_requirements")
    op.drop_table("kc_requirements")
    op.drop_index("ix_kc_visits_session_id", table_name="kc_visits")
    op.drop_table("kc_visits")
    op.drop_constraint("ck_kc_sessions_verdict", "kc_sessions", type_="check")
    op.drop_constraint("ck_kc_sessions_scoring_version", "kc_sessions", type_="check")
    op.drop_constraint("fk_kc_sessions_course_run_id", "kc_sessions", type_="foreignkey")
    op.drop_column("kc_sessions", "verdict")
    op.drop_column("kc_sessions", "course_run_id")
    op.drop_column("kc_sessions", "revision")
    op.drop_column("kc_sessions", "scoring_version")
    op.drop_index("ix_kc_course_runs_student_goal", table_name="kc_course_runs")
    op.drop_table("kc_course_runs")
