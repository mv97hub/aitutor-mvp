"""Add the global AI safety settings row and the safety events table.

Revision ID: 029_ai_safety
Revises: 028_multi_tutor_profiles
Create Date: 2026-11-11
"""

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "029_ai_safety"
down_revision: Union[str, None] = "028_multi_tutor_profiles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_safety_settings",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("id = 'global'", name="ck_ai_safety_settings_singleton"),
    )
    op.create_table(
        "ai_safety_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("student_id", sa.Uuid(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "kc_session_id",
            sa.Uuid(),
            sa.ForeignKey("kc_sessions.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "kc_message_id",
            sa.Uuid(),
            sa.ForeignKey("kc_messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("course_id", sa.Uuid(), sa.ForeignKey("kc_goals.id", ondelete="CASCADE"), nullable=True),
        sa.Column("node_id", sa.Uuid(), sa.ForeignKey("kc_nodes.id", ondelete="CASCADE"), nullable=True),
        sa.Column(
            "tutor_profile_id",
            sa.String(120),
            sa.ForeignKey("tutor_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("strictness", sa.String(40), nullable=False),
        sa.Column("child_message", sa.Text(), nullable=False, server_default=""),
        sa.Column("tutor_reply", sa.Text(), nullable=False, server_default=""),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.String(120), nullable=True),
        sa.CheckConstraint(
            "category IN ('distress', 'inappropriate_content', 'personal_info', 'manipulation', 'other')",
            name="ck_ai_safety_events_category",
        ),
    )
    op.create_index("ix_ai_safety_events_student_id", "ai_safety_events", ["student_id"])
    op.create_index("ix_ai_safety_events_kc_session_id", "ai_safety_events", ["kc_session_id"])

    from app.ai_safety import default_ai_safety

    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO ai_safety_settings (id, settings) VALUES ('global', CAST(:settings AS JSON))"
        ),
        {"settings": json.dumps(default_ai_safety())},
    )


def downgrade() -> None:
    op.drop_index("ix_ai_safety_events_kc_session_id", table_name="ai_safety_events")
    op.drop_index("ix_ai_safety_events_student_id", table_name="ai_safety_events")
    op.drop_table("ai_safety_events")
    op.drop_table("ai_safety_settings")
