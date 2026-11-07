"""KC tutor profile controls and the session columns the seven-layer loop writes.

This adds columns. It does not drop tables, delete rows, or change a saved
struggle window. The original tutor still reads short, standard, and long.

Revision ID: 021_kc_seven_layer
Revises: 020_deepseek_studio_model
Create Date: 2026-11-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "021_kc_seven_layer"
down_revision: Union[str, None] = "020_deepseek_studio_model"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tutor_profiles",
        sa.Column(
            "misconception_policy",
            sa.String(32),
            nullable=False,
            server_default="retry_once",
        ),
    )
    op.add_column(
        "tutor_profiles",
        sa.Column("self_explanation", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "tutor_profiles",
        sa.Column("enrichment", sa.String(16), nullable=False, server_default="on_request"),
    )
    op.create_check_constraint(
        "ck_tutor_profiles_misconception_policy",
        "tutor_profiles",
        "misconception_policy IN ('retry_once')",
    )
    op.create_check_constraint(
        "ck_tutor_profiles_enrichment",
        "tutor_profiles",
        "enrichment IN ('direct', 'on_request', 'offer')",
    )

    op.add_column(
        "kc_sessions",
        sa.Column("hint_tier", sa.String(16), nullable=False, server_default="nudge"),
    )
    op.add_column(
        "kc_sessions",
        sa.Column("move_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "kc_sessions",
        sa.Column("reveals", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "kc_sessions",
        sa.Column("off_course_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "kc_sessions",
        sa.Column("affect", sa.String(16), nullable=False, server_default=""),
    )
    op.add_column(
        "kc_sessions",
        sa.Column("enrichment_turns", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "kc_sessions",
        sa.Column("help_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "kc_sessions",
        sa.Column("rubric_met", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "kc_sessions",
        sa.Column("last_misconception", sa.String(240), nullable=False, server_default=""),
    )
    op.create_check_constraint(
        "ck_kc_sessions_hint_tier",
        "kc_sessions",
        "hint_tier IN ('nudge', 'analogy', 'scaffold', 'reveal')",
    )
    op.create_check_constraint(
        "ck_kc_sessions_affect",
        "kc_sessions",
        "affect IN ('', 'engaged', 'stuck', 'guessing', 'frustrated')",
    )

    op.add_column(
        "kc_model_prompts",
        sa.Column("rubric_met", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column("kc_model_prompts", sa.Column("misconception", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("kc_model_prompts", "misconception")
    op.drop_column("kc_model_prompts", "rubric_met")
    op.drop_constraint("ck_kc_sessions_affect", "kc_sessions", type_="check")
    op.drop_constraint("ck_kc_sessions_hint_tier", "kc_sessions", type_="check")
    op.drop_column("kc_sessions", "last_misconception")
    op.drop_column("kc_sessions", "rubric_met")
    op.drop_column("kc_sessions", "help_requested")
    op.drop_column("kc_sessions", "enrichment_turns")
    op.drop_column("kc_sessions", "affect")
    op.drop_column("kc_sessions", "off_course_count")
    op.drop_column("kc_sessions", "reveals")
    op.drop_column("kc_sessions", "move_attempts")
    op.drop_column("kc_sessions", "hint_tier")
    op.drop_constraint("ck_tutor_profiles_enrichment", "tutor_profiles", type_="check")
    op.drop_constraint("ck_tutor_profiles_misconception_policy", "tutor_profiles", type_="check")
    op.drop_column("tutor_profiles", "enrichment")
    op.drop_column("tutor_profiles", "self_explanation")
    op.drop_column("tutor_profiles", "misconception_policy")
