"""Store the outline, topics, and goals on a knowledge component.

This revision adds one column on kc_nodes. It does not drop tutor tables,
studio tables, chats, or kid messages.

Revision ID: 018_kc_description
Revises: 017_kc_creator
Create Date: 2026-11-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "018_kc_description"
down_revision: Union[str, None] = "017_kc_creator"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "kc_nodes",
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("kc_nodes", "description")
