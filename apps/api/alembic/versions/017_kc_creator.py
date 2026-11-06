"""Add the component complete flag and the KC Creator thread.

This revision adds a column on kc_nodes and creates kc_creator_messages.
It does not drop tutor tables, studio tables, chats, or kid messages.

Revision ID: 017_kc_creator
Revises: 016_kc_tables
Create Date: 2026-11-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "017_kc_creator"
down_revision: Union[str, None] = "016_kc_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "kc_nodes",
        sa.Column(
            "marked_complete",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_table(
        "kc_creator_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("node_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("draft", sa.JSON(), nullable=True),
        sa.Column(
            "applied",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_kc_creator_messages_role"),
        sa.ForeignKeyConstraint(["node_id"], ["kc_nodes.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("node_id", "seq", name="uq_kc_creator_messages_node_seq"),
    )
    op.create_index("ix_kc_creator_messages_node_id", "kc_creator_messages", ["node_id"])


def downgrade() -> None:
    op.drop_index("ix_kc_creator_messages_node_id", table_name="kc_creator_messages")
    op.drop_table("kc_creator_messages")
    op.drop_column("kc_nodes", "marked_complete")
