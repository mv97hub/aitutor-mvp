"""Store the course intake, brief, blueprint, and draft state on a KC course.

Revision ID: 030_course_pipeline
Revises: 029_ai_safety
Create Date: 2026-11-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "030_course_pipeline"
down_revision: Union[str, None] = "029_ai_safety"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("kc_goals", sa.Column("intake", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("kc_goals", sa.Column("brief", sa.Text(), nullable=False, server_default=""))
    op.add_column("kc_goals", sa.Column("blueprint", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("kc_goals", sa.Column("drafting", sa.JSON(), nullable=False, server_default="{}"))


def downgrade() -> None:
    op.drop_column("kc_goals", "drafting")
    op.drop_column("kc_goals", "blueprint")
    op.drop_column("kc_goals", "brief")
    op.drop_column("kc_goals", "intake")
