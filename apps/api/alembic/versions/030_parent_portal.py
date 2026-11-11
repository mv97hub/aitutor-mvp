"""Add parents and the parent-to-child link table.

Revision ID: 030_parent_portal
Revises: 029_ai_safety
Create Date: 2026-11-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "030_parent_portal"
down_revision: Union[str, None] = "029_ai_safety"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "parents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_table(
        "parent_students",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "parent_id",
            sa.Uuid(),
            sa.ForeignKey("parents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("students.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("parent_id", "student_id", name="uq_parent_students_pair"),
    )
    op.create_index("ix_parent_students_parent_id", "parent_students", ["parent_id"])
    op.create_index("ix_parent_students_student_id", "parent_students", ["student_id"])


def downgrade() -> None:
    op.drop_index("ix_parent_students_student_id", table_name="parent_students")
    op.drop_index("ix_parent_students_parent_id", table_name="parent_students")
    op.drop_table("parent_students")
    op.drop_table("parents")
