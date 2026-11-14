"""Remember how many stuck nudges a harness chat still owes.

Revision ID: 040_harness_stuck_nudges
Revises: 039_harness_child_prompt
Create Date: 2026-11-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "040_harness_stuck_nudges"
down_revision: Union[str, None] = "039_harness_child_prompt"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "harness_chats",
        sa.Column("pending_nudges", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("harness_chats", "pending_nudges")
