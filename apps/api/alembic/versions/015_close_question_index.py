"""Remember which close question a session is asking.

Adds close_question_index. Chats, messages, and results stay.

Revision ID: 015_close_question_index
Revises: 014_one_course_model
Create Date: 2026-11-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "015_close_question_index"
down_revision: Union[str, None] = "014_one_course_model"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("close_question_index", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("sessions", "close_question_index")
