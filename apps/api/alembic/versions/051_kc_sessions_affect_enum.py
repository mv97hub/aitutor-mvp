"""Extend kc_sessions.ck_kc_sessions_affect to allow F4 'bored' and 'curious_stretch'.

Revision ID: 051_kc_sessions_affect_enum
Revises: 050_f5_placement_state
Create Date: 2026-11-27
"""

from typing import Sequence, Union

from alembic import op


revision: str = "051_kc_sessions_affect_enum"
down_revision: Union[str, Sequence[str], None] = "050_f5_placement_state"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_kc_sessions_affect", "kc_sessions", type_="check")
    op.create_check_constraint(
        "ck_kc_sessions_affect",
        "kc_sessions",
        "affect IN ('', 'engaged', 'stuck', 'guessing', 'frustrated', 'bored', 'curious_stretch')",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE kc_sessions SET affect = 'engaged' WHERE affect IN ('bored', 'curious_stretch')"
    )
    op.drop_constraint("ck_kc_sessions_affect", "kc_sessions", type_="check")
    op.create_check_constraint(
        "ck_kc_sessions_affect",
        "kc_sessions",
        "affect IN ('', 'engaged', 'stuck', 'guessing', 'frustrated')",
    )
