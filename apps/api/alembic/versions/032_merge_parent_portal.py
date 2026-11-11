"""Join the parent portal revision with the course pipeline head.

030_parent_portal and 030_course_pipeline both follow 029_ai_safety.
031_course_standards continues only the course branch, so
`alembic upgrade head` stopped with two heads and never created
the parents tables. This revision does not change the schema. It
gives `alembic upgrade head` one head so the parent tables apply.

Revision ID: 032_merge_parent_portal
Revises: 030_parent_portal, 031_course_standards
Create Date: 2026-11-11
"""

from typing import Sequence, Union

revision: str = "032_merge_parent_portal"
down_revision: Union[str, Sequence[str], None] = (
    "030_parent_portal",
    "031_course_standards",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
