"""Add child_profile JSON column to students for Layer 2 child persona settings.

Revision ID: 026_student_child_profile
Revises: 025_kc_blocks_and_configs
Create Date: 2026-11-09
"""

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "026_student_child_profile"
down_revision: Union[str, None] = "025_kc_blocks_and_configs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.models import normalize_child_profile

    op.add_column(
        "students",
        sa.Column(
            "child_profile",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )

    bind = op.get_bind()
    rows = list(
        bind.execute(
            sa.text(
                "SELECT id, age, reading_level, modality, interests FROM students"
            )
        ).mappings()
    )
    for row in rows:
        raw_interests = row["interests"] if isinstance(row["interests"], list) else []
        profile = normalize_child_profile(
            {},
            age=row["age"],
            reading_level=row["reading_level"],
            modality=row["modality"],
            interests=raw_interests,
        )
        bind.execute(
            sa.text("UPDATE students SET child_profile = CAST(:profile AS JSON) WHERE id = :id"),
            {"profile": json.dumps(profile), "id": row["id"]},
        )


def downgrade() -> None:
    op.drop_column("students", "child_profile")
