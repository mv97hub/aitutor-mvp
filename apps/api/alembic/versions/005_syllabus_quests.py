"""Replace lesson plans with a 4-tier syllabus and retarget sessions at a quest.

Local test transcripts are cleared. This is not a production data migration.

Revision ID: 005_syllabus_quests
Revises: 004_prompt_message
Create Date: 2026-11-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_syllabus_quests"
down_revision: Union[str, None] = "004_prompt_message"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM model_prompts")
    op.execute("DELETE FROM messages")
    op.execute("DELETE FROM checkpoint_results")
    op.execute("DELETE FROM sessions")

    op.drop_table("checkpoint_results")
    op.drop_column("sessions", "current_checkpoint_id")
    op.drop_column("sessions", "current_topic_id")
    op.drop_column("sessions", "lesson_plan_id")
    op.drop_table("checkpoints")
    op.drop_table("topics")
    op.drop_index("uq_lesson_plans_one_active", table_name="lesson_plans")
    op.drop_table("lesson_plans")

    op.add_column("students", sa.Column("reading_level", sa.String(80), nullable=False, server_default=""))
    op.add_column("students", sa.Column("modality", sa.String(80), nullable=False, server_default=""))
    op.add_column(
        "students",
        sa.Column("interests", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column("students", sa.Column("tutor_persona", sa.String(160), nullable=False, server_default=""))
    op.add_column("students", sa.Column("tutor_lexicon", sa.Text(), nullable=False, server_default=""))
    op.add_column("students", sa.Column("tutor_metaphors", sa.Text(), nullable=False, server_default=""))
    op.add_column("students", sa.Column("tutor_sidekick", sa.String(200), nullable=False, server_default=""))
    op.add_column(
        "students",
        sa.Column("tutor_socratic_strictness", sa.String(40), nullable=False, server_default="balanced"),
    )
    op.add_column(
        "students",
        sa.Column("tutor_struggle_window", sa.String(40), nullable=False, server_default="minimum"),
    )
    op.add_column(
        "students",
        sa.Column("tutor_anti_spoiler", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "students",
        sa.Column(
            "tutor_pacing",
            sa.String(80),
            nullable=False,
            server_default="short-turns-one-question",
        ),
    )

    op.create_table(
        "courses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("age_band", sa.String(8), nullable=False),
        sa.Column("standards_alignment", sa.Text(), nullable=False, server_default=""),
        sa.Column("competency_dictionary", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "age_band IN ('6-8', '9-11', '12-14', '15-17')",
            name="ck_courses_age_band",
        ),
        sa.UniqueConstraint("code", name="uq_courses_code"),
    )
    op.create_table(
        "units",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("enduring_understanding", sa.Text(), nullable=False, server_default=""),
        sa.Column("continuity_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_diagnostic", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_capstone", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("course_id", "number", name="uq_units_course_number"),
    )
    op.create_index("ix_units_course_id", "units", ["course_id"])
    op.create_table(
        "quests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("quest_type", sa.String(16), nullable=False, server_default="core"),
        sa.Column("prerequisite_codes", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("competency_tags", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("dinner_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "quest_type IN ('core', 'branch', 'capstone')",
            name="ck_quests_type",
        ),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("code", name="uq_quests_code"),
        sa.UniqueConstraint("unit_id", "position", name="uq_quests_unit_position"),
    )
    op.create_index("ix_quests_unit_id", "quests", ["unit_id"])
    op.create_table(
        "beats",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("quest_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("bloom_level", sa.String(32), nullable=False, server_default="understand"),
        sa.Column("cognitive_load", sa.String(16), nullable=False, server_default="medium"),
        sa.Column("prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("rubric", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("misconception_map", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("hint_ladder", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("widget", sa.JSON(), nullable=True),
        sa.CheckConstraint(
            "role IN ('mystery_hook', 'interactive_toy', 'diagnostic_gate', 'feynman_flip')",
            name="ck_beats_role",
        ),
        sa.CheckConstraint("position >= 1 AND position <= 4", name="ck_beats_position"),
        sa.ForeignKeyConstraint(["quest_id"], ["quests.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("quest_id", "position", name="uq_beats_quest_position"),
    )
    op.create_index("ix_beats_quest_id", "beats", ["quest_id"])

    op.add_column("sessions", sa.Column("quest_id", sa.Uuid(), nullable=False))
    op.add_column("sessions", sa.Column("current_beat_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_sessions_quest_id", "sessions", "quests", ["quest_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_foreign_key(
        "fk_sessions_current_beat_id",
        "sessions",
        "beats",
        ["current_beat_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_sessions_quest_id", "sessions", ["quest_id"])

    op.create_table(
        "beat_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("beat_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("rubric_met", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("misconception", sa.Text(), nullable=True),
        sa.Column("hint_tier", sa.String(16), nullable=True),
        sa.Column("choice", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_beat_results_score"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["beat_id"], ["beats.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("session_id", "seq", name="uq_beat_results_session_seq"),
    )
    op.create_index("ix_beat_results_session_id", "beat_results", ["session_id"])


def downgrade() -> None:
    op.execute("DELETE FROM model_prompts")
    op.execute("DELETE FROM messages")
    op.execute("DELETE FROM beat_results")
    op.execute("DELETE FROM sessions")
    op.drop_index("ix_beat_results_session_id", table_name="beat_results")
    op.drop_table("beat_results")
    op.drop_index("ix_sessions_quest_id", table_name="sessions")
    op.drop_constraint("fk_sessions_current_beat_id", "sessions", type_="foreignkey")
    op.drop_constraint("fk_sessions_quest_id", "sessions", type_="foreignkey")
    op.drop_column("sessions", "current_beat_id")
    op.drop_column("sessions", "quest_id")
    op.drop_index("ix_beats_quest_id", table_name="beats")
    op.drop_table("beats")
    op.drop_index("ix_quests_unit_id", table_name="quests")
    op.drop_table("quests")
    op.drop_index("ix_units_course_id", table_name="units")
    op.drop_table("units")
    op.drop_table("courses")
    for column in (
        "tutor_pacing",
        "tutor_anti_spoiler",
        "tutor_struggle_window",
        "tutor_socratic_strictness",
        "tutor_sidekick",
        "tutor_metaphors",
        "tutor_lexicon",
        "tutor_persona",
        "interests",
        "modality",
        "reading_level",
    ):
        op.drop_column("students", column)

    op.create_table(
        "lesson_plans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("preamble", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("age_min", sa.Integer(), nullable=True),
        sa.Column("age_max", sa.Integer(), nullable=True),
        sa.UniqueConstraint("slug", name="uq_lesson_plans_slug"),
    )
    op.create_index(
        "uq_lesson_plans_one_active",
        "lesson_plans",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_table(
        "topics",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("lesson_plan_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("learning_goal", sa.Text(), nullable=False),
        sa.Column("tutor_instructions", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["lesson_plan_id"], ["lesson_plans.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("lesson_plan_id", "position", name="uq_topics_plan_position"),
    )
    op.create_table(
        "checkpoints",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("tutor_prompt", sa.Text(), nullable=False),
        sa.Column("rubric", sa.Text()),
        sa.Column("pass_criteria", sa.Text()),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("objective", sa.Text()),
        sa.Column("rubric_rows", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("hint_ladder", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("pass_score", sa.Integer(), nullable=False, server_default="70"),
        sa.Column("quiz", sa.JSON()),
        sa.CheckConstraint(
            "kind IN ('teach', 'practice', 'quiz', 'discovery', 'teach_back')",
            name="ck_checkpoints_kind",
        ),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("topic_id", "position", name="uq_checkpoints_topic_position"),
    )
    op.add_column("sessions", sa.Column("lesson_plan_id", sa.Uuid(), nullable=False))
    op.add_column("sessions", sa.Column("current_topic_id", sa.Uuid(), nullable=True))
    op.add_column("sessions", sa.Column("current_checkpoint_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "sessions_lesson_plan_id_fkey",
        "sessions",
        "lesson_plans",
        ["lesson_plan_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "sessions_current_topic_id_fkey",
        "sessions",
        "topics",
        ["current_topic_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "sessions_current_checkpoint_id_fkey",
        "sessions",
        "checkpoints",
        ["current_checkpoint_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_table(
        "checkpoint_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("checkpoint_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("rubric_met", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("misconception", sa.Text()),
        sa.Column("hint_tier", sa.String(16)),
        sa.Column("choice", sa.JSON()),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_results_score"),
        sa.UniqueConstraint("session_id", "seq", name="uq_results_session_seq"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["checkpoint_id"], ["checkpoints.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_checkpoint_results_session_id", "checkpoint_results", ["session_id"])
