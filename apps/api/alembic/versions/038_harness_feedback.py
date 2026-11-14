"""Saved suites, recommendation cards, and trial tutor profiles.

Trial profiles are flagged is_test so they stay out of the tutor pickers.
Accepted cards are not applied to the live profile.

Revision ID: 038_harness_feedback
Revises: 037_harness_reviews
Create Date: 2026-11-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "038_harness_feedback"
down_revision: Union[str, None] = "037_harness_reviews"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tutor_profiles",
        sa.Column("is_test", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "harness_suites",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("plan", sa.JSON(), nullable=False),
        sa.Column("baseline_run_id", sa.Uuid(), sa.ForeignKey("harness_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_foreign_key(
        "fk_harness_runs_suite_id",
        "harness_runs",
        "harness_suites",
        ["suite_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "harness_recommendations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("harness_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("suite_id", sa.Uuid(), sa.ForeignKey("harness_suites.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("cause_class", sa.String(40), nullable=False, server_default=""),
        sa.Column("place", sa.Text(), nullable=False, server_default=""),
        sa.Column("proposed", sa.JSON(), nullable=False),
        sa.Column("prompt_direction", sa.String(16), nullable=False, server_default="same"),
        sa.Column("kind", sa.String(16), nullable=False, server_default="reword"),
        sa.Column("risk", sa.Text(), nullable=False, server_default=""),
        sa.Column("confidence", sa.String(16), nullable=False, server_default="low"),
        sa.Column("status", sa.String(16), nullable=False, server_default="new"),
        sa.Column("trial_profile_id", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "kind IN ('setting', 'reword', 'remove', 'add')",
            name="ck_harness_recommendations_kind",
        ),
        sa.CheckConstraint(
            "status IN ('new', 'accepted', 'rejected', 'on_trial', 'shipped', 'verified', 'regressed')",
            name="ck_harness_recommendations_status",
        ),
        sa.CheckConstraint(
            "prompt_direction IN ('shorter', 'longer', 'same')",
            name="ck_harness_recommendations_direction",
        ),
    )


def downgrade() -> None:
    op.drop_table("harness_recommendations")
    op.drop_constraint("fk_harness_runs_suite_id", "harness_runs", type_="foreignkey")
    op.drop_table("harness_suites")
    op.drop_column("tutor_profiles", "is_test")
