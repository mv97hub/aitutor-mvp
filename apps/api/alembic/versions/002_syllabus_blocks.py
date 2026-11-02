"""Block fields on checkpoints: rubric rows, hints, quiz widgets.

Revision ID: 002_syllabus_blocks
Revises: 001_initial
Create Date: 2026-11-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_syllabus_blocks"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

KIND_SQL = "kind IN ('teach', 'practice', 'quiz', 'discovery', 'teach_back')"
OLD_KIND_SQL = "kind IN ('teach', 'practice', 'quiz')"


def upgrade() -> None:
    op.add_column("students", sa.Column("age", sa.Integer(), nullable=True))
    op.add_column("lesson_plans", sa.Column("age_min", sa.Integer(), nullable=True))
    op.add_column("lesson_plans", sa.Column("age_max", sa.Integer(), nullable=True))
    op.drop_constraint("ck_checkpoints_kind", "checkpoints", type_="check")
    op.create_check_constraint("ck_checkpoints_kind", "checkpoints", KIND_SQL)
    op.add_column("checkpoints", sa.Column("objective", sa.Text(), nullable=True))
    op.add_column(
        "checkpoints",
        sa.Column("rubric_rows", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "checkpoints",
        sa.Column(
            "hint_ladder",
            sa.JSON(),
            nullable=False,
            server_default=sa.text('\'{"nudge": "", "analogy": "", "scaffold": ""}\''),
        ),
    )
    op.add_column(
        "checkpoints",
        sa.Column("pass_score", sa.Integer(), nullable=False, server_default="70"),
    )
    op.add_column("checkpoints", sa.Column("quiz", sa.JSON(), nullable=True))
    op.add_column(
        "checkpoint_results",
        sa.Column("rubric_met", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column("checkpoint_results", sa.Column("misconception", sa.Text(), nullable=True))
    op.add_column("checkpoint_results", sa.Column("hint_tier", sa.String(16), nullable=True))
    op.add_column("checkpoint_results", sa.Column("choice", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("checkpoint_results", "choice")
    op.drop_column("checkpoint_results", "hint_tier")
    op.drop_column("checkpoint_results", "misconception")
    op.drop_column("checkpoint_results", "rubric_met")
    op.drop_column("checkpoints", "quiz")
    op.drop_column("checkpoints", "pass_score")
    op.drop_column("checkpoints", "hint_ladder")
    op.drop_column("checkpoints", "rubric_rows")
    op.drop_column("checkpoints", "objective")
    op.drop_constraint("ck_checkpoints_kind", "checkpoints", type_="check")
    op.create_check_constraint("ck_checkpoints_kind", "checkpoints", OLD_KIND_SQL)
    op.drop_column("lesson_plans", "age_max")
    op.drop_column("lesson_plans", "age_min")
    op.drop_column("students", "age")
