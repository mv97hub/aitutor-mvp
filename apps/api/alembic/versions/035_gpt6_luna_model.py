"""Allow GPT-6 Luna on the CreateCourse model menu.

The stored id is gpt-6-luna. A row that already uses another model stays
as it is. Downgrade moves a saved Luna row back to the CreateCourse default
before the check narrows.

Revision ID: 035_gpt6_luna_model
Revises: 034_tutor_token_usage
Create Date: 2026-11-12
"""

from typing import Sequence, Union

from alembic import op

revision: str = "035_gpt6_luna_model"
down_revision: Union[str, None] = "034_tutor_token_usage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_WITH_LUNA = (
    "model IN ('gpt-4o-mini', 'gpt-4o', 'gpt-4.1-mini', 'gpt-6-luna', "
    "'deepseek/deepseek-flash-latest', '~deepseek/deepseek-flash-latest')"
)
_PREVIOUS = (
    "model IN ('gpt-4o-mini', 'gpt-4o', 'gpt-4.1-mini', "
    "'deepseek/deepseek-flash-latest', '~deepseek/deepseek-flash-latest')"
)


def upgrade() -> None:
    op.drop_constraint("ck_studio_settings_model", "studio_settings", type_="check")
    op.create_check_constraint("ck_studio_settings_model", "studio_settings", _WITH_LUNA)


def downgrade() -> None:
    op.execute("UPDATE studio_settings SET model = 'gpt-4o-mini' WHERE model = 'gpt-6-luna'")
    op.drop_constraint("ck_studio_settings_model", "studio_settings", type_="check")
    op.create_check_constraint("ck_studio_settings_model", "studio_settings", _PREVIOUS)
