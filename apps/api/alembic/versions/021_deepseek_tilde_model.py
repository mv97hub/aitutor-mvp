"""Allow the OpenRouter alias for DeepSeek Flash.

OpenRouter rejects deepseek/deepseek-flash-latest. The alias is
~deepseek/deepseek-flash-latest. This revision widens the studio settings
check so a new save of that alias is allowed. A row that still stores the
old id stays as it is. The app sends the alias for that row.

Revision ID: 021_deepseek_tilde_model
Revises: 020_deepseek_studio_model
Create Date: 2026-11-07
"""

from typing import Sequence, Union

from alembic import op

revision: str = "021_deepseek_tilde_model"
down_revision: Union[str, None] = "020_deepseek_studio_model"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_WITH_ALIAS = (
    "model IN ('gpt-4o-mini', 'gpt-4o', 'gpt-4.1-mini', "
    "'deepseek/deepseek-flash-latest', '~deepseek/deepseek-flash-latest')"
)
_PREVIOUS = (
    "model IN ('gpt-4o-mini', 'gpt-4o', 'gpt-4.1-mini', 'deepseek/deepseek-flash-latest')"
)


def upgrade() -> None:
    op.drop_constraint("ck_studio_settings_model", "studio_settings", type_="check")
    op.create_check_constraint("ck_studio_settings_model", "studio_settings", _WITH_ALIAS)


def downgrade() -> None:
    op.execute(
        "UPDATE studio_settings SET model = 'deepseek/deepseek-flash-latest' "
        "WHERE model = '~deepseek/deepseek-flash-latest'"
    )
    op.drop_constraint("ck_studio_settings_model", "studio_settings", type_="check")
    op.create_check_constraint("ck_studio_settings_model", "studio_settings", _PREVIOUS)
