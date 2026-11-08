"""Store a person-readable history log on a KC component and its course.

This adds one text column on kc_nodes and one on kc_goals. It does not
drop tables, delete rows, or send the log to a model.

Revision ID: 023_kc_history
Revises: 022_merge_heads
Create Date: 2026-11-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "023_kc_history"
down_revision: Union[str, None] = "022_merge_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "kc_nodes",
        sa.Column("history", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "kc_goals",
        sa.Column("history", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("kc_goals", "history")
    op.drop_column("kc_nodes", "history")
