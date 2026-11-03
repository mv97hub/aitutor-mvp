"""Store the minimum time before a studio course's closing quiz.

The kid tutor does not read this column. This adds one column and records
the same number in the course preferences JSON. It does not drop tables,
delete rows, or reseed chats or courses.

Revision ID: 011_studio_quiz_minutes
Revises: 010_studio_ready
Create Date: 2026-11-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011_studio_quiz_minutes"
down_revision: Union[str, None] = "010_studio_ready"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "studio_courses",
        sa.Column("quiz_minutes", sa.Integer(), nullable=False, server_default="5"),
    )
    op.create_check_constraint(
        "ck_studio_courses_quiz_minutes",
        "studio_courses",
        "quiz_minutes IN (2, 5, 10)",
    )
    op.execute(
        """
        UPDATE studio_courses
        SET preferences = (
            COALESCE(preferences, '{}'::json)::jsonb
            || jsonb_build_object('quiz_minutes', quiz_minutes)
        )::json
        WHERE NOT (COALESCE(preferences, '{}'::json)::jsonb ? 'quiz_minutes')
        """
    )


def downgrade() -> None:
    op.drop_constraint("ck_studio_courses_quiz_minutes", "studio_courses", type_="check")
    op.drop_column("studio_courses", "quiz_minutes")
