"""Tie each stored model prompt to the message that started that turn.

Revision ID: 004_prompt_message
Revises: 003_model_prompts
Create Date: 2026-11-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_prompt_message"
down_revision: Union[str, None] = "003_model_prompts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("model_prompts", sa.Column("message_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_model_prompts_message_id",
        "model_prompts",
        "messages",
        ["message_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_model_prompts_message_id", "model_prompts", ["message_id"])
    op.execute(
        """
        WITH numbered_prompts AS (
            SELECT id,
                   session_id,
                   row_number() OVER (PARTITION BY session_id ORDER BY seq) AS turn_no
            FROM model_prompts
        ),
        numbered_messages AS (
            SELECT id,
                   session_id,
                   row_number() OVER (PARTITION BY session_id ORDER BY seq) AS turn_no
            FROM messages
            WHERE role = 'user'
        )
        UPDATE model_prompts
        SET message_id = numbered_messages.id
        FROM numbered_prompts
        JOIN numbered_messages
          ON numbered_messages.session_id = numbered_prompts.session_id
         AND numbered_messages.turn_no = numbered_prompts.turn_no
        WHERE model_prompts.id = numbered_prompts.id
        """
    )


def downgrade() -> None:
    op.drop_index("ix_model_prompts_message_id", table_name="model_prompts")
    op.drop_constraint("fk_model_prompts_message_id", "model_prompts", type_="foreignkey")
    op.drop_column("model_prompts", "message_id")
