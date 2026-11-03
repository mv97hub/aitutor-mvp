"""Add the studio course draft flag.

A course is a draft until the creator marks it ready. This adds one column.
It does not drop tutor or studio tables, and it does not reseed chats or courses.

Revision ID: 010_studio_ready
Revises: 009_studio
Create Date: 2026-11-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010_studio_ready"
down_revision: Union[str, None] = "009_studio"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "studio_courses",
        sa.Column("ready", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("studio_courses", "ready")
