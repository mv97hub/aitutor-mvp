"""Quest goal, success criterion, and a variable move cycle.

Local test sessions are cleared. Beats from the four-role script are removed
so the new role check can apply. The seed rewrites Rome, Geometry, and AP Macro.

Revision ID: 006_quest_cycle
Revises: 005_syllabus_quests
Create Date: 2026-11-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006_quest_cycle"
down_revision: Union[str, None] = "005_syllabus_quests"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM model_prompts")
    op.execute("DELETE FROM messages")
    op.execute("DELETE FROM beat_results")
    op.execute("DELETE FROM sessions")

    op.add_column("quests", sa.Column("learning_goal", sa.Text(), nullable=False, server_default=""))
    op.add_column(
        "quests",
        sa.Column("success_criterion", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "quests",
        sa.Column("requires_teach_back", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.drop_constraint("ck_beats_role", "beats", type_="check")
    op.drop_constraint("ck_beats_position", "beats", type_="check")
    op.execute("DELETE FROM beats")
    op.create_check_constraint(
        "ck_beats_role",
        "beats",
        "role IN ('engage', 'try', 'name', 'show', 'teach_back')",
    )
    op.create_check_constraint("ck_beats_position", "beats", "position >= 1")


def downgrade() -> None:
    op.execute("DELETE FROM model_prompts")
    op.execute("DELETE FROM messages")
    op.execute("DELETE FROM beat_results")
    op.execute("DELETE FROM sessions")
    op.execute("DELETE FROM beats")
    op.drop_constraint("ck_beats_position", "beats", type_="check")
    op.drop_constraint("ck_beats_role", "beats", type_="check")
    op.create_check_constraint(
        "ck_beats_role",
        "beats",
        "role IN ('mystery_hook', 'interactive_toy', 'diagnostic_gate', 'feynman_flip')",
    )
    op.create_check_constraint("ck_beats_position", "beats", "position >= 1 AND position <= 4")
    op.drop_column("quests", "requires_teach_back")
    op.drop_column("quests", "success_criterion")
    op.drop_column("quests", "learning_goal")
