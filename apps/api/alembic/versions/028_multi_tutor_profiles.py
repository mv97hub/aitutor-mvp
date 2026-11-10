"""Add multi-tutor profile metadata, avatar fields, and student/session foreign keys.

Revision ID: 028_multi_tutor_profiles
Revises: 027_layer_3_4_tutor_config
Create Date: 2026-11-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "028_multi_tutor_profiles"
down_revision: Union[str, None] = "027_layer_3_4_tutor_config"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_TUTOR_DESCRIPTION = (
    "Standard balanced AI Tutor profile using research-backed guided discovery "
    "and adaptive child vocabulary."
)


def upgrade() -> None:
    op.drop_constraint("ck_tutor_profiles_singleton", "tutor_profiles", type_="check")
    op.alter_column(
        "tutor_profiles",
        "id",
        existing_type=sa.String(length=40),
        type_=sa.String(length=120),
        existing_nullable=False,
    )
    op.add_column(
        "tutor_profiles",
        sa.Column("name", sa.String(120), nullable=False, server_default="Default"),
    )
    op.add_column(
        "tutor_profiles",
        sa.Column("slug", sa.String(120), nullable=False, server_default="default"),
    )
    op.add_column(
        "tutor_profiles",
        sa.Column(
            "description",
            sa.Text(),
            nullable=False,
            server_default=DEFAULT_TUTOR_DESCRIPTION,
        ),
    )
    op.add_column(
        "tutor_profiles",
        sa.Column(
            "avatar_preset",
            sa.String(64),
            nullable=False,
            server_default="default_circle",
        ),
    )
    op.add_column(
        "tutor_profiles",
        sa.Column("avatar_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "tutor_profiles",
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.execute(
        sa.text(
            """
            UPDATE tutor_profiles
            SET name = 'Default',
                slug = 'default',
                description = :desc,
                avatar_preset = 'default_circle',
                is_default = TRUE
            WHERE id = 'default'
            """
        ).bindparams(desc=DEFAULT_TUTOR_DESCRIPTION)
    )

    op.create_unique_constraint("uq_tutor_profiles_slug", "tutor_profiles", ["slug"])

    op.add_column(
        "students",
        sa.Column(
            "preferred_tutor_profile_id",
            sa.String(120),
            sa.ForeignKey("tutor_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "kc_sessions",
        sa.Column(
            "tutor_profile_id",
            sa.String(120),
            sa.ForeignKey("tutor_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("kc_sessions", "tutor_profile_id")
    op.drop_column("students", "preferred_tutor_profile_id")
    op.drop_constraint("uq_tutor_profiles_slug", "tutor_profiles", type_="unique")
    op.drop_column("tutor_profiles", "is_default")
    op.drop_column("tutor_profiles", "avatar_url")
    op.drop_column("tutor_profiles", "avatar_preset")
    op.drop_column("tutor_profiles", "description")
    op.drop_column("tutor_profiles", "slug")
    op.drop_column("tutor_profiles", "name")
    op.execute(sa.text("DELETE FROM tutor_profiles WHERE id <> 'default'"))
    op.alter_column(
        "tutor_profiles",
        "id",
        existing_type=sa.String(length=120),
        type_=sa.String(length=40),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "ck_tutor_profiles_singleton",
        "tutor_profiles",
        "id = 'default'",
    )
