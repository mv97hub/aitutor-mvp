"""Store the system prompt and messages sent to the model.

Revision ID: 003_model_prompts
Revises: 002_syllabus_blocks
Create Date: 2026-11-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_model_prompts"
down_revision: Union[str, None] = "002_syllabus_blocks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "model_prompts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("messages", sa.JSON(), nullable=False),
        sa.Column("model", sa.String(120), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["sessions.id"], ondelete="CASCADE", name="fk_model_prompts_session_id"
        ),
        sa.UniqueConstraint("session_id", "seq", name="uq_model_prompts_session_seq"),
    )
    op.create_index("ix_model_prompts_session_id", "model_prompts", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_model_prompts_session_id", table_name="model_prompts")
    op.drop_table("model_prompts")
