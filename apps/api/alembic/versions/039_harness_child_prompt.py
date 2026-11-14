"""Store the child prompt sent to the model on each harness turn.

Revision ID: 039_harness_child_prompt
Revises: 038_harness_feedback
Create Date: 2026-11-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "039_harness_child_prompt"
down_revision: Union[str, None] = "038_harness_feedback"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "harness_turns",
        sa.Column("child_prompt", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("harness_turns", "child_prompt")
