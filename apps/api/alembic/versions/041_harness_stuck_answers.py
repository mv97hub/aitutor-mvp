"""Remember answers given before stuck nudges.

Revision ID: 041_harness_stuck_answers
Revises: 040_harness_stuck_nudges
Create Date: 2026-11-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "041_harness_stuck_answers"
down_revision: Union[str, None] = "040_harness_stuck_nudges"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "harness_chats",
        sa.Column("stuck_answers", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("harness_chats", "stuck_answers")
