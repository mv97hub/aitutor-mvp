"""Allow DeepSeek Flash on the CreateCourse model menu.

This revision widens the studio settings check. It does not drop rows,
and it does not change a saved OpenAI model.

Revision ID: 020_deepseek_studio_model
Revises: 019_kc_model_prompts
Create Date: 2026-11-07
"""

from typing import Sequence, Union

from alembic import op

revision: str = "020_deepseek_studio_model"
down_revision: Union[str, None] = "019_kc_model_prompts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_WITH_DEEPSEEK = (
    "model IN ('gpt-4o-mini', 'gpt-4o', 'gpt-4.1-mini', 'deepseek/deepseek-flash-latest')"
)
_OPENAI_ONLY = "model IN ('gpt-4o-mini', 'gpt-4o', 'gpt-4.1-mini')"


def upgrade() -> None:
    op.drop_constraint("ck_studio_settings_model", "studio_settings", type_="check")
    op.create_check_constraint("ck_studio_settings_model", "studio_settings", _WITH_DEEPSEEK)


def downgrade() -> None:
    op.execute(
        "UPDATE studio_settings SET model = 'gpt-4o-mini' "
        "WHERE model = 'deepseek/deepseek-flash-latest'"
    )
    op.drop_constraint("ck_studio_settings_model", "studio_settings", type_="check")
    op.create_check_constraint("ck_studio_settings_model", "studio_settings", _OPENAI_ONLY)
