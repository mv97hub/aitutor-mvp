"""One default tutor profile for layers 3 and 4.

Student tutor_* columns stay. This does not clear classes or rewrite courses.

Revision ID: 007_tutor_profile
Revises: 006_quest_cycle
Create Date: 2026-11-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007_tutor_profile"
down_revision: Union[str, None] = "006_quest_cycle"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tutor_profiles",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("instructive", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("persona", sa.String(40), nullable=False),
        sa.Column("lexicon", sa.String(40), nullable=False),
        sa.Column("voice_override", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("metaphors", sa.String(40), nullable=False),
        sa.Column("sidekick", sa.String(40), nullable=False),
        sa.Column("struggle_window", sa.String(16), nullable=False, server_default="standard"),
        sa.Column("anti_spoiler", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("one_question", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("use_interests", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("growth_praise", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("id = 'default'", name="ck_tutor_profiles_singleton"),
        sa.CheckConstraint(
            "instructive >= 1 AND instructive <= 5",
            name="ck_tutor_profiles_instructive",
        ),
        sa.CheckConstraint(
            "persona IN ('curious-co-explorer', 'tactical-coach', 'debate-moderator', 'patient-explainer')",
            name="ck_tutor_profiles_persona",
        ),
        sa.CheckConstraint(
            "lexicon IN ('early-concrete', 'middle-grade-vivid', 'precise-visual', 'analytical-high-school')",
            name="ck_tutor_profiles_lexicon",
        ),
        sa.CheckConstraint(
            "metaphors IN ('playground-sports', 'buildings-machines', 'policy-cause', 'none')",
            name="ck_tutor_profiles_metaphors",
        ),
        sa.CheckConstraint(
            "sidekick IN ('bumbling-partner', 'rookie-picture', 'pundit', 'off')",
            name="ck_tutor_profiles_sidekick",
        ),
        sa.CheckConstraint(
            "struggle_window IN ('short', 'standard', 'long')",
            name="ck_tutor_profiles_struggle",
        ),
    )
    op.execute(
        """
        INSERT INTO tutor_profiles (
            id, instructive, persona, lexicon, voice_override, metaphors, sidekick,
            struggle_window, anti_spoiler, one_question, use_interests, growth_praise
        ) VALUES (
            'default', 3, 'curious-co-explorer', 'middle-grade-vivid', false,
            'playground-sports', 'bumbling-partner', 'standard', true, true, true, true
        )
        """
    )


def downgrade() -> None:
    op.drop_table("tutor_profiles")
