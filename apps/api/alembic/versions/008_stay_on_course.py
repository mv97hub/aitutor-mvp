"""Add stay_on_course to the default tutor profile.

Existing rows get true from the server default. This adds one column.
It does not clear classes, chats, courses, or the profile row.

Revision ID: 008_stay_on_course
Revises: 007_tutor_profile
Create Date: 2026-11-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008_stay_on_course"
down_revision: Union[str, None] = "007_tutor_profile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tutor_profiles",
        sa.Column(
            "stay_on_course",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("tutor_profiles", "stay_on_course")
