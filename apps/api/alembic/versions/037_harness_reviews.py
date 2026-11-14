"""Judged and automatic reviews, plus the tutor decision on the prompt log.

The decision column stores the object the tutor route already returned.
The prompt text and the tutor flow are unchanged.

Revision ID: 037_harness_reviews
Revises: 036_test_harness
Create Date: 2026-11-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "037_harness_reviews"
down_revision: Union[str, None] = "036_test_harness"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("kc_model_prompts", sa.Column("decision", sa.JSON(), nullable=True))
    op.create_table(
        "harness_evaluations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("chat_id", sa.Uuid(), sa.ForeignKey("harness_chats.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("checks", sa.JSON(), nullable=False),
        sa.Column("scores", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("rubric_version", sa.String(40), nullable=False, server_default=""),
        sa.Column("judge_model", sa.String(120), nullable=False, server_default=""),
        sa.Column("child_realism", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind IN ('automatic', 'judged')", name="ck_harness_evaluations_kind"),
    )
    op.create_index("ix_harness_evaluations_chat_id", "harness_evaluations", ["chat_id"])


def downgrade() -> None:
    op.drop_index("ix_harness_evaluations_chat_id", table_name="harness_evaluations")
    op.drop_table("harness_evaluations")
    op.drop_column("kc_model_prompts", "decision")
