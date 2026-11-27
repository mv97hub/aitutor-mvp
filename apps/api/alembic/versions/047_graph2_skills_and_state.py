"""Add Graph-2 eight-skill tables, frozen tutor note, end card, and judge token kind.

Creates:
- student_educational_state (1:1 per real student)
- learner_course_state (per student + course)
- skill_observation (append-only 0-3 observation log, idempotent per session+skill)

Adds additive columns on kc_sessions:
- frozen_tutor_note (copied at component open, immutable during the session)
- close_end_card (synchronous child end card snapshot)
- graph2_judge_status (async post-close batch judge lifecycle)

Widens tutor_token_usage.kind check constraint to include 'judge'.

Revision ID: 047_graph2_skills_and_state
Revises: 046_harness_pending_turn
Create Date: 2026-11-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "047_graph2_skills_and_state"
down_revision: Union[str, None] = "046_harness_pending_turn"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SKILL_CHECK = (
    "skill IN ('evidence', 'perspectives', 'causes', 'inquiry', "
    "'errors', 'transfer', 'explaining', 'calibration')"
)


def upgrade() -> None:
    op.create_table(
        "student_educational_state",
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("students.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("skills", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("hint_uptake", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("block_affinity", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("expression_stats", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("biomarkers", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("tutor_note", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "tutor_note_component_id",
            sa.Uuid(),
            sa.ForeignKey("kc_nodes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "tutor_note_course_id",
            sa.Uuid(),
            sa.ForeignKey("kc_goals.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "learner_course_state",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("students.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "goal_id",
            sa.Uuid(),
            sa.ForeignKey("kc_goals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("misconceptions", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("unlock_notes", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("analogies_worked", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("student_id", "goal_id", name="uq_learner_course_state_student_goal"),
    )
    op.create_index("ix_learner_course_state_student_id", "learner_course_state", ["student_id"])
    op.create_index("ix_learner_course_state_goal_id", "learner_course_state", ["goal_id"])

    op.create_table(
        "skill_observation",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("students.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("kc_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "goal_id",
            sa.Uuid(),
            sa.ForeignKey("kc_goals.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "kc_id",
            sa.Uuid(),
            sa.ForeignKey("kc_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("block_id", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("block_type", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("claim_id", sa.String(length=80), nullable=True),
        sa.Column("skill", sa.String(length=32), nullable=False),
        sa.Column("rubric_grade", sa.Integer(), nullable=False),
        sa.Column("raw_y", sa.Float(), nullable=False),
        sa.Column("cap_applied", sa.String(length=24), nullable=True),
        sa.Column("capped_y", sa.Float(), nullable=False),
        sa.Column("score_before", sa.Float(), nullable=False),
        sa.Column("score_after", sa.Float(), nullable=False),
        sa.Column("obs_index", sa.Integer(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(_SKILL_CHECK, name="ck_skill_observation_skill"),
        sa.CheckConstraint("rubric_grade >= 0 AND rubric_grade <= 3", name="ck_skill_observation_grade"),
        sa.CheckConstraint(
            "cap_applied IS NULL OR cap_applied IN ('revealed', 'giveaway', 'overlap')",
            name="ck_skill_observation_cap",
        ),
        sa.CheckConstraint("capped_y >= 0.0 AND capped_y <= 1.0", name="ck_skill_observation_capped_y"),
        sa.UniqueConstraint("session_id", "skill", name="uq_skill_observation_session_skill"),
    )
    op.create_index(
        "ix_skill_observation_student_skill",
        "skill_observation",
        ["student_id", "skill", "created_at"],
    )
    op.create_index("ix_skill_observation_session_id", "skill_observation", ["session_id"])
    op.create_index("ix_skill_observation_kc_id", "skill_observation", ["kc_id"])

    op.add_column(
        "kc_sessions",
        sa.Column("frozen_tutor_note", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "kc_sessions",
        sa.Column("close_end_card", sa.JSON(), nullable=True),
    )
    op.add_column(
        "kc_sessions",
        sa.Column("graph2_judge_status", sa.String(length=16), nullable=False, server_default="none"),
    )
    op.create_check_constraint(
        "ck_kc_sessions_graph2_judge_status",
        "kc_sessions",
        "graph2_judge_status IN ('none', 'pending', 'completed', 'failed', 'skipped')",
    )

    op.drop_constraint("ck_tutor_token_usage_kind", "tutor_token_usage", type_="check")
    op.create_check_constraint(
        "ck_tutor_token_usage_kind",
        "tutor_token_usage",
        "kind IN ('speak', 'answer', 'judge')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_tutor_token_usage_kind", "tutor_token_usage", type_="check")
    op.create_check_constraint(
        "ck_tutor_token_usage_kind",
        "tutor_token_usage",
        "kind IN ('speak', 'answer')",
    )
    op.drop_constraint("ck_kc_sessions_graph2_judge_status", "kc_sessions", type_="check")
    op.drop_column("kc_sessions", "graph2_judge_status")
    op.drop_column("kc_sessions", "close_end_card")
    op.drop_column("kc_sessions", "frozen_tutor_note")
    op.drop_index("ix_skill_observation_kc_id", table_name="skill_observation")
    op.drop_index("ix_skill_observation_session_id", table_name="skill_observation")
    op.drop_index("ix_skill_observation_student_skill", table_name="skill_observation")
    op.drop_table("skill_observation")
    op.drop_index("ix_learner_course_state_goal_id", table_name="learner_course_state")
    op.drop_index("ix_learner_course_state_student_id", table_name="learner_course_state")
    op.drop_table("learner_course_state")
    op.drop_table("student_educational_state")
