"""Lift studio quests onto the course and drop the unit tier.

Every studio quest, close, and move stays. Quest positions are renumbered in
unit order, then the unit table goes away. Extra goals live in a new table.
Goal 1 stays on the quest columns. Kid course tables and kid chat are not
touched.

Revision ID: 012_quests_on_course
Revises: 011_studio_quiz_minutes
Create Date: 2026-11-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012_quests_on_course"
down_revision: Union[str, None] = "011_studio_quiz_minutes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "studio_quest_goals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("quest_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("learning_goal", sa.Text(), nullable=False, server_default=""),
        sa.Column("success_criterion", sa.Text(), nullable=False, server_default=""),
        sa.CheckConstraint("position >= 2", name="ck_studio_quest_goals_position"),
        sa.ForeignKeyConstraint(["quest_id"], ["studio_quests.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("quest_id", "position", name="uq_studio_quest_goals_position"),
    )
    op.create_index("ix_studio_quest_goals_quest_id", "studio_quest_goals", ["quest_id"])
    op.execute(
        """
        WITH ordered AS (
            SELECT q.id AS id,
                   row_number() OVER (
                       PARTITION BY q.course_id
                       ORDER BY u.position, q.position, q.code
                   ) AS pos
            FROM studio_quests AS q
            JOIN studio_units AS u ON u.id = q.unit_id
        )
        UPDATE studio_quests AS q
        SET position = ordered.pos
        FROM ordered
        WHERE q.id = ordered.id
        """
    )
    op.drop_constraint("studio_quests_unit_id_fkey", "studio_quests", type_="foreignkey")
    op.drop_index("ix_studio_quests_unit_id", table_name="studio_quests")
    op.drop_column("studio_quests", "unit_id")
    op.drop_index("ix_studio_units_course_id", table_name="studio_units")
    op.drop_table("studio_units")


def downgrade() -> None:
    op.create_table(
        "studio_units",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("learning_goal", sa.Text(), nullable=False, server_default=""),
        sa.Column("success_criterion", sa.Text(), nullable=False, server_default=""),
        sa.CheckConstraint("position >= 1", name="ck_studio_units_position"),
        sa.ForeignKeyConstraint(["course_id"], ["studio_courses.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("course_id", "code", name="uq_studio_units_course_code"),
    )
    op.create_index("ix_studio_units_course_id", "studio_units", ["course_id"])
    op.add_column("studio_quests", sa.Column("unit_id", sa.Uuid(), nullable=True))
    op.execute(
        """
        INSERT INTO studio_units (id, course_id, code, position, title, learning_goal, success_criterion)
        SELECT gen_random_uuid(), c.id, c.code || '-U1', 1, c.title, '', ''
        FROM studio_courses AS c
        """
    )
    op.execute(
        """
        UPDATE studio_quests AS q
        SET unit_id = u.id
        FROM studio_units AS u
        WHERE u.course_id = q.course_id
        """
    )
    op.alter_column("studio_quests", "unit_id", nullable=False)
    op.create_index("ix_studio_quests_unit_id", "studio_quests", ["unit_id"])
    op.create_foreign_key(
        "studio_quests_unit_id_fkey",
        "studio_quests",
        "studio_units",
        ["unit_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_index("ix_studio_quest_goals_quest_id", table_name="studio_quest_goals")
    op.drop_table("studio_quest_goals")
