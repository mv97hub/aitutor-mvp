"""Allow a person's scores on a harness chat.

The judge row stays kind 'judged'. A hand score is a separate row so an empty
form does not invent numbers.

Revision ID: 042_harness_hand_scores
Revises: 041_harness_stuck_answers
Create Date: 2026-11-15
"""

from typing import Sequence, Union

from alembic import op

revision: str = "042_harness_hand_scores"
down_revision: Union[str, None] = "041_harness_stuck_answers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_harness_evaluations_kind", "harness_evaluations", type_="check")
    op.create_check_constraint(
        "ck_harness_evaluations_kind",
        "harness_evaluations",
        "kind IN ('automatic', 'judged', 'hand')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_harness_evaluations_kind", "harness_evaluations", type_="check")
    op.create_check_constraint(
        "ck_harness_evaluations_kind",
        "harness_evaluations",
        "kind IN ('automatic', 'judged')",
    )
