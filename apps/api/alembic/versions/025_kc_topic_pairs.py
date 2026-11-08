"""Store an outline and topic-goal pairs on a knowledge component.

A description that already uses the three-line form is split once.
Outline goes to outline. Each topic is stored with its goal.
That description becomes the outline sentence, which is the summary
we can recover. A description that does not match stays the summary,
and its topic list stays empty.

This revision adds columns. It does not drop tables or delete rows.

Revision ID: 025_kc_topic_pairs
Revises: 024_merge_kc_heads
Create Date: 2026-11-08
"""

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "025_kc_topic_pairs"
down_revision: Union[str, None] = "024_merge_kc_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "kc_nodes",
        sa.Column("outline", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "kc_nodes",
        sa.Column("topics", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    from app.kc_model import split_brief

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, description FROM kc_nodes")).mappings()
    for row in rows:
        split = split_brief(row["description"] or "")
        if split is None:
            continue
        bind.execute(
            sa.text(
                "UPDATE kc_nodes SET description = :description, outline = :outline, "
                "topics = CAST(:topics AS JSON) WHERE id = :id"
            ),
            {
                "description": split["description"],
                "outline": split["outline"],
                "topics": json.dumps(split["topics"]),
                "id": row["id"],
            },
        )


def downgrade() -> None:
    op.drop_column("kc_nodes", "topics")
    op.drop_column("kc_nodes", "outline")
