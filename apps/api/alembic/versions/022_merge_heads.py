"""Join the two revisions that both follow 020_deepseek_studio_model.

021_deepseek_tilde_model and 021_kc_seven_layer were added on separate
branches. This revision does not change the schema. It gives
`alembic upgrade head` a single head so both branches apply.

Revision ID: 022_merge_heads
Revises: 021_deepseek_tilde_model, 021_kc_seven_layer
Create Date: 2026-11-07
"""

from typing import Sequence, Union

revision: str = "022_merge_heads"
down_revision: Union[str, Sequence[str], None] = (
    "021_deepseek_tilde_model",
    "021_kc_seven_layer",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
