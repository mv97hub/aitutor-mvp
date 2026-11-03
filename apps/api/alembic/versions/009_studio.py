"""Add CreateCourse studio tables.

This revision creates only studio_ tables. It does not drop tutor tables,
and it does not reseed courses, chats, or studio rows.

Revision ID: 009_studio
Revises: 008_stay_on_course
Create Date: 2026-11-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009_studio"
down_revision: Union[str, None] = "008_stay_on_course"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "studio_courses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("audience", sa.Text(), nullable=False, server_default=""),
        sa.Column("focus", sa.Text(), nullable=False, server_default=""),
        sa.Column("theme", sa.String(240), nullable=False, server_default=""),
        sa.Column("depth", sa.String(16), nullable=False, server_default="standard"),
        sa.Column("sources", sa.Text(), nullable=False, server_default=""),
        sa.Column("preferences", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "depth IN ('survey', 'standard', 'go_deep')",
            name="ck_studio_courses_depth",
        ),
        sa.CheckConstraint("schema_version >= 1", name="ck_studio_courses_schema_version"),
        sa.UniqueConstraint("code", name="uq_studio_courses_code"),
    )
    op.create_table(
        "studio_settings",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("model", sa.String(64), nullable=False, server_default="gpt-4o-mini"),
        sa.CheckConstraint("id = 'default'", name="ck_studio_settings_singleton"),
        sa.CheckConstraint(
            "model IN ('gpt-4o-mini', 'gpt-4o', 'gpt-4.1-mini')",
            name="ck_studio_settings_model",
        ),
    )
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
    op.create_table(
        "studio_quests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("learning_goal", sa.Text(), nullable=False, server_default=""),
        sa.Column("success_criterion", sa.Text(), nullable=False, server_default=""),
        sa.CheckConstraint("position >= 1", name="ck_studio_quests_position"),
        sa.ForeignKeyConstraint(["course_id"], ["studio_courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["unit_id"], ["studio_units.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("course_id", "code", name="uq_studio_quests_course_code"),
    )
    op.create_index("ix_studio_quests_course_id", "studio_quests", ["course_id"])
    op.create_index("ix_studio_quests_unit_id", "studio_quests", ["unit_id"])
    op.create_table(
        "studio_moves",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("quest_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("learning_goal", sa.Text(), nullable=False, server_default=""),
        sa.Column("success_criterion", sa.Text(), nullable=False, server_default=""),
        sa.CheckConstraint("position >= 1", name="ck_studio_moves_position"),
        sa.ForeignKeyConstraint(["course_id"], ["studio_courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["quest_id"], ["studio_quests.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("course_id", "code", name="uq_studio_moves_course_code"),
    )
    op.create_index("ix_studio_moves_course_id", "studio_moves", ["course_id"])
    op.create_index("ix_studio_moves_quest_id", "studio_moves", ["quest_id"])
    op.create_table(
        "studio_quest_close",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("quest_id", sa.Uuid(), nullable=False),
        sa.Column("close_style", sa.String(16), nullable=False),
        sa.Column("answer_style", sa.String(32), nullable=False),
        sa.Column("choice_mode", sa.String(16), nullable=True),
        sa.Column("items", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("intent", sa.Text(), nullable=False, server_default=""),
        sa.CheckConstraint(
            "close_style IN ('one', 'several')",
            name="ck_studio_quest_close_style",
        ),
        sa.CheckConstraint(
            "answer_style IN ('multiple_choice', 'essay', 'mixed')",
            name="ck_studio_quest_close_answer",
        ),
        sa.CheckConstraint(
            "choice_mode IS NULL OR choice_mode IN ('predefined', 'dynamic')",
            name="ck_studio_quest_close_choice",
        ),
        sa.ForeignKeyConstraint(["quest_id"], ["studio_quests.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("quest_id", name="uq_studio_quest_close_quest"),
    )
    op.create_table(
        "studio_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("proposal", sa.JSON(), nullable=True),
        sa.Column("applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_studio_messages_role"),
        sa.ForeignKeyConstraint(["course_id"], ["studio_courses.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("course_id", "seq", name="uq_studio_messages_course_seq"),
    )
    op.create_index("ix_studio_messages_course_id", "studio_messages", ["course_id"])


def downgrade() -> None:
    op.drop_index("ix_studio_messages_course_id", table_name="studio_messages")
    op.drop_table("studio_messages")
    op.drop_table("studio_quest_close")
    op.drop_index("ix_studio_moves_quest_id", table_name="studio_moves")
    op.drop_index("ix_studio_moves_course_id", table_name="studio_moves")
    op.drop_table("studio_moves")
    op.drop_index("ix_studio_quests_unit_id", table_name="studio_quests")
    op.drop_index("ix_studio_quests_course_id", table_name="studio_quests")
    op.drop_table("studio_quests")
    op.drop_index("ix_studio_units_course_id", table_name="studio_units")
    op.drop_table("studio_units")
    op.drop_table("studio_settings")
    op.drop_table("studio_courses")
