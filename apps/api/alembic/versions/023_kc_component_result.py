"""Store the component result on the child's progress for that component.

Revision ID: 023_kc_component_result
Revises: 022_merge_heads
Create Date: 2026-11-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "023_kc_component_result"
down_revision: Union[str, None] = "022_merge_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("kc_states", sa.Column("result", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("kc_states", "result")
