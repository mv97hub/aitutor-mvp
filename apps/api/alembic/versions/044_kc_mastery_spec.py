"""Store mastery claims on a knowledge component.

The column defaults to an empty object. Existing rows keep that empty spec,
and this migration does not read or rewrite their blocks.

Revision ID: 044_kc_mastery_spec
Revises: 043_harness_claim_generation
Create Date: 2026-11-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "044_kc_mastery_spec"
down_revision: Union[str, None] = "043_harness_claim_generation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "kc_nodes",
        sa.Column("mastery_spec", sa.JSON(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("kc_nodes", "mastery_spec")
