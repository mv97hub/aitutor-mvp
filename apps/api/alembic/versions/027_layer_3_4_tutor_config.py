"""Expand tutor_profiles check constraints for revamped Layer 3 and Layer 4 settings.

Revision ID: 027_layer_3_4_tutor_config
Revises: 026_student_child_profile
Create Date: 2026-11-10
"""

from typing import Sequence, Union

from alembic import op

revision: str = "027_layer_3_4_tutor_config"
down_revision: Union[str, None] = "026_student_child_profile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_tutor_profiles_persona", "tutor_profiles", type_="check")
    op.drop_constraint("ck_tutor_profiles_lexicon", "tutor_profiles", type_="check")
    op.drop_constraint("ck_tutor_profiles_metaphors", "tutor_profiles", type_="check")
    op.drop_constraint("ck_tutor_profiles_sidekick", "tutor_profiles", type_="check")
    op.drop_constraint("ck_tutor_profiles_misconception_policy", "tutor_profiles", type_="check")

    op.create_check_constraint(
        "ck_tutor_profiles_persona",
        "tutor_profiles",
        "persona IN ('socratic_mentor', 'coach', 'detective', 'explorer', 'storyteller', 'sibling', 'wizard', "
        "'curious-co-explorer', 'tactical-coach', 'debate-moderator', 'patient-explainer')",
    )
    op.create_check_constraint(
        "ck_tutor_profiles_lexicon",
        "tutor_profiles",
        "lexicon IN ('adaptive_to_child', 'everyday_conversational', 'academic_precision', 'story_rich_expressive', "
        "'early-concrete', 'middle-grade-vivid', 'precise-visual', 'analytical-high-school')",
    )
    op.create_check_constraint(
        "ck_tutor_profiles_metaphors",
        "tutor_profiles",
        "metaphors IN ('everyday', 'games', 'nature', 'sports', 'cooking', 'scifi', "
        "'playground-sports', 'buildings-machines', 'policy-cause', 'none')",
    )
    op.create_check_constraint(
        "ck_tutor_profiles_sidekick",
        "tutor_profiles",
        "sidekick IN ('none', 'barnaby', 'pixel', 'spark', "
        "'bumbling-partner', 'rookie-picture', 'pundit', 'off')",
    )
    op.create_check_constraint(
        "ck_tutor_profiles_misconception_policy",
        "tutor_profiles",
        "misconception_policy IN ('retry_once', 'nudge_without_naming', 'explain_and_retry_once', 'immediate_redirect')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_tutor_profiles_misconception_policy", "tutor_profiles", type_="check")
    op.drop_constraint("ck_tutor_profiles_sidekick", "tutor_profiles", type_="check")
    op.drop_constraint("ck_tutor_profiles_metaphors", "tutor_profiles", type_="check")
    op.drop_constraint("ck_tutor_profiles_lexicon", "tutor_profiles", type_="check")
    op.drop_constraint("ck_tutor_profiles_persona", "tutor_profiles", type_="check")

    op.create_check_constraint(
        "ck_tutor_profiles_persona",
        "tutor_profiles",
        "persona IN ('curious-co-explorer', 'tactical-coach', 'debate-moderator', 'patient-explainer')",
    )
    op.create_check_constraint(
        "ck_tutor_profiles_lexicon",
        "tutor_profiles",
        "lexicon IN ('early-concrete', 'middle-grade-vivid', 'precise-visual', 'analytical-high-school')",
    )
    op.create_check_constraint(
        "ck_tutor_profiles_metaphors",
        "tutor_profiles",
        "metaphors IN ('playground-sports', 'buildings-machines', 'policy-cause', 'none')",
    )
    op.create_check_constraint(
        "ck_tutor_profiles_sidekick",
        "tutor_profiles",
        "sidekick IN ('bumbling-partner', 'rookie-picture', 'pundit', 'off')",
    )
    op.create_check_constraint(
        "ck_tutor_profiles_misconception_policy",
        "tutor_profiles",
        "misconception_policy IN ('retry_once')",
    )
