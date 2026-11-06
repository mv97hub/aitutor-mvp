"""Add knowledge-component tables.

This revision creates only kc_ tables. It does not drop tutor tables,
studio tables, chats, or messages, and it does not reseed courses.

Revision ID: 016_kc_tables
Revises: 015_close_question_index
Create Date: 2026-11-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "016_kc_tables"
down_revision: Union[str, None] = "015_close_question_index"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kc_nodes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("kc_type", sa.String(32), nullable=True),
        sa.Column("core_truth", sa.Text(), nullable=False, server_default=""),
        sa.Column("type_fields", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("rubric", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("misconceptions", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("prerequisite_codes", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("encompasses_codes", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
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
            "kc_type IS NULL OR kc_type IN "
            "('factual', 'procedural', 'conceptual', 'causal', 'synthesis')",
            name="ck_kc_nodes_type",
        ),
        sa.UniqueConstraint("code", name="uq_kc_nodes_code"),
    )
    op.create_table(
        "kc_edges",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("from_kc", sa.Uuid(), nullable=False),
        sa.Column("to_kc", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('prerequisite_of', 'encompasses')",
            name="ck_kc_edges_kind",
        ),
        sa.CheckConstraint("from_kc <> to_kc", name="ck_kc_edges_distinct"),
        sa.ForeignKeyConstraint(["from_kc"], ["kc_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_kc"], ["kc_nodes.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("from_kc", "to_kc", "kind", name="uq_kc_edges_ends_kind"),
    )
    op.create_index("ix_kc_edges_from_kc", "kc_edges", ["from_kc"])
    op.create_index("ix_kc_edges_to_kc", "kc_edges", ["to_kc"])
    op.create_table(
        "kc_goals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("audience", sa.String(8), nullable=False, server_default="9-11"),
        sa.Column("kind", sa.String(16), nullable=False, server_default="mastery"),
        sa.Column("minutes", sa.Integer(), nullable=True),
        sa.Column("target_kc_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("ready", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
            "audience IN ('6-8', '9-11', '12-14', '15-17')",
            name="ck_kc_goals_audience",
        ),
        sa.CheckConstraint(
            "kind IN ('mastery', 'time_boxed', 'curiosity')",
            name="ck_kc_goals_kind",
        ),
        sa.CheckConstraint("minutes IS NULL OR minutes > 0", name="ck_kc_goals_minutes"),
        sa.UniqueConstraint("code", name="uq_kc_goals_code"),
    )
    op.create_table(
        "kc_states",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("kc_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("stability", sa.Float(), nullable=False, server_default="0"),
        sa.Column("last_practiced", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('unknown', 'fragile', 'known')",
            name="ck_kc_states_status",
        ),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["kc_id"], ["kc_nodes.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("student_id", "kc_id", name="uq_kc_states_student_kc"),
    )
    op.create_index("ix_kc_states_student_id", "kc_states", ["student_id"])
    op.create_index("ix_kc_states_kc_id", "kc_states", ["kc_id"])
    op.create_table(
        "kc_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("goal_id", sa.Uuid(), nullable=False),
        sa.Column("kc_id", sa.Uuid(), nullable=False),
        sa.Column("recipe", sa.String(40), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="in_progress"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("redirect_kc_id", sa.Uuid(), nullable=True),
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
            "status IN ('in_progress', 'completed')",
            name="ck_kc_sessions_status",
        ),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["goal_id"], ["kc_goals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["kc_id"], ["kc_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["redirect_kc_id"], ["kc_nodes.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_kc_sessions_student_id", "kc_sessions", ["student_id"])
    op.create_index("ix_kc_sessions_goal_id", "kc_sessions", ["goal_id"])
    op.create_index("ix_kc_sessions_kc_id", "kc_sessions", ["kc_id"])
    op.create_table(
        "kc_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_kc_messages_role"),
        sa.ForeignKeyConstraint(["session_id"], ["kc_sessions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("session_id", "seq", name="uq_kc_messages_session_seq"),
    )
    op.create_index("ix_kc_messages_session_id", "kc_messages", ["session_id"])


def downgrade() -> None:
    op.drop_table("kc_messages")
    op.drop_table("kc_sessions")
    op.drop_table("kc_states")
    op.drop_table("kc_goals")
    op.drop_table("kc_edges")
    op.drop_table("kc_nodes")
