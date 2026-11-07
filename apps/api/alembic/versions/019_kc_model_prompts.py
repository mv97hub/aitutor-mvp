"""Store the system prompt and messages sent for a KC Tutor turn.

This revision adds kc_model_prompts. It does not drop tutor tables,
studio tables, kid chats, or knowledge-component rows.

Revision ID: 019_kc_model_prompts
Revises: 018_kc_description
Create Date: 2026-11-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "019_kc_model_prompts"
down_revision: Union[str, None] = "018_kc_description"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kc_model_prompts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=True),
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
            ["session_id"],
            ["kc_sessions.id"],
            ondelete="CASCADE",
            name="fk_kc_model_prompts_session_id",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["kc_messages.id"],
            ondelete="SET NULL",
            name="fk_kc_model_prompts_message_id",
        ),
        sa.UniqueConstraint("session_id", "seq", name="uq_kc_model_prompts_session_seq"),
    )
    op.create_index("ix_kc_model_prompts_session_id", "kc_model_prompts", ["session_id"])
    op.create_index("ix_kc_model_prompts_message_id", "kc_model_prompts", ["message_id"])


def downgrade() -> None:
    op.drop_index("ix_kc_model_prompts_message_id", table_name="kc_model_prompts")
    op.drop_index("ix_kc_model_prompts_session_id", table_name="kc_model_prompts")
    op.drop_table("kc_model_prompts")
