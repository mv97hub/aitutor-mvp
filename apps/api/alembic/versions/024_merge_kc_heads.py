"""Join the two revisions that both follow 022_merge_heads.

023_kc_component_result and 023_kc_history were added on separate
branches. This revision does not change the schema. It gives
`alembic upgrade head` a single head so both branches apply.

Revision ID: 024_merge_kc_heads
Revises: 023_kc_component_result, 023_kc_history
Create Date: 2026-11-08
"""

from typing import Sequence, Union

revision: str = "024_merge_kc_heads"
down_revision: Union[str, Sequence[str], None] = (
    "023_kc_component_result",
    "023_kc_history",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
