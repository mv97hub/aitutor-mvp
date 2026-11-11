"""Store curriculum statements on a KC course and the codes on each component.

Revision ID: 031_course_standards
Revises: 030_course_pipeline
Create Date: 2026-11-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "031_course_standards"
down_revision: Union[str, None] = "030_course_pipeline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("kc_goals", sa.Column("standards", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("kc_nodes", sa.Column("standards", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    op.drop_column("kc_nodes", "standards")
    op.drop_column("kc_goals", "standards")
