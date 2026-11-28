"""F5: Cold-start DAG placement status & state on learner_course_state.

Revision ID: 050_f5_placement_state
Revises: 049_parent_copilot_share
Create Date: 2026-11-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "050_f5_placement_state"
down_revision: Union[str, Sequence[str], None] = "049_parent_copilot_share"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "learner_course_state",
        sa.Column(
            "placement_status",
            sa.String(length=24),
            server_default="not_started",
            nullable=False,
        ),
    )
    op.add_column(
        "learner_course_state",
        sa.Column(
            "placement_state",
            sa.JSON(),
            server_default="{}",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_learner_course_state_placement_status",
        "learner_course_state",
        "placement_status IN ('not_started', 'in_progress', 'completed', 'skipped')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_learner_course_state_placement_status",
        "learner_course_state",
        type_="check",
    )
    op.drop_column("learner_course_state", "placement_state")
    op.drop_column("learner_course_state", "placement_status")
