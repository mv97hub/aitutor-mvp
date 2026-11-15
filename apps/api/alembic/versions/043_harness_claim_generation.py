"""Remember which claim owns a harness chat.

A second claim keeps the tutor session and bumps this number. The browser
loop that stored the old number stops.

Revision ID: 043_harness_claim_generation
Revises: 042_harness_hand_scores
Create Date: 2026-11-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "043_harness_claim_generation"
down_revision: Union[str, None] = "042_harness_hand_scores"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "harness_chats",
        sa.Column("claim_generation", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("harness_chats", "claim_generation")
