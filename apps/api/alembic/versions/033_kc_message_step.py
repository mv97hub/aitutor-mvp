"""Store the block index on each tutor message.

Revision ID: 033_kc_message_step
Revises: 032_merge_parent_portal
Create Date: 2026-11-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "033_kc_message_step"
down_revision: Union[str, None] = "032_merge_parent_portal"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "kc_messages",
        sa.Column("step", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("kc_messages", "step")
