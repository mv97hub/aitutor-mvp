"""One course shape: goals then a close, and no seeded courses.

Rome, Geometry, and AP Macro go away with their chats. Every other session
and message stays, and that session restarts at the quest's first goal.
Every studio goal, including the first, is a row. Published closes use the
same columns as the studio close.

Revision ID: 014_one_course_model
Revises: 013_tutor_quests_on_course
Create Date: 2026-11-06
"""

from typing import Sequence, Union
import json
import uuid

import sqlalchemy as sa
from alembic import op

revision: str = "014_one_course_model"
down_revision: Union[str, None] = "013_tutor_quests_on_course"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEEDED = ("rome", "geometry", "macro")


def _json(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return []
    return value


def _pref_count(raw, key: str, default: int) -> int:
    if isinstance(raw, str):
        raw = _json(raw)
    if not isinstance(raw, dict):
        return default
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > 200:
        return default
    return value


def _packed_close(kind: str, question: str, items) -> tuple[str, str, str | None, object, str]:
    question = (question or "").strip()
    choices = items if isinstance(items, list) else []
    questions = [{"text": question}] if question else []
    if kind == "single":
        return (
            "one",
            "multiple_choice",
            "predefined",
            {"choices": choices, "questions": questions, "selection": "single"},
            "",
        )
    if kind == "multi":
        return (
            "one",
            "multiple_choice",
            "predefined",
            {"choices": choices, "questions": questions, "selection": "multi"},
            "",
        )
    if kind == "essay" and questions:
        return "one", "essay", None, {"choices": [], "questions": questions}, ""
    return "one", "essay", None, [], ""


def _delete_seeded_courses() -> None:
    """Remove the three seeded courses and only their chats."""
    bind = op.get_bind()
    codes = ", ".join(f"'{code}'" for code in SEEDED)
    session_ids = f"""
        SELECT s.id
        FROM sessions AS s
        JOIN quests AS q ON q.id = s.quest_id
        JOIN courses AS c ON c.id = q.course_id
        WHERE c.code IN ({codes})
    """
    bind.execute(sa.text(f"DELETE FROM model_prompts WHERE session_id IN ({session_ids})"))
    bind.execute(sa.text(f"DELETE FROM messages WHERE session_id IN ({session_ids})"))
    bind.execute(sa.text(f"DELETE FROM beat_results WHERE session_id IN ({session_ids})"))
    bind.execute(sa.text(f"DELETE FROM sessions WHERE id IN ({session_ids})"))
    bind.execute(sa.text(f"DELETE FROM courses WHERE code IN ({codes})"))


def _studio_goals_and_preferences() -> None:
    bind = op.get_bind()
    op.drop_constraint("ck_studio_quest_goals_position", "studio_quest_goals", type_="check")
    op.create_check_constraint(
        "ck_studio_quest_goals_position",
        "studio_quest_goals",
        "position >= 1",
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO studio_quest_goals (id, quest_id, position, learning_goal, success_criterion)
            SELECT gen_random_uuid(), q.id, 1, q.learning_goal, q.success_criterion
            FROM studio_quests AS q
            WHERE (
                btrim(COALESCE(q.learning_goal, '')) <> ''
                OR btrim(COALESCE(q.success_criterion, '')) <> ''
            )
            AND NOT EXISTS (
                SELECT 1 FROM studio_quest_goals AS g
                WHERE g.quest_id = q.id AND g.position = 1
            )
            """
        )
    )
    op.drop_column("studio_quests", "learning_goal")
    op.drop_column("studio_quests", "success_criterion")
    op.drop_index("ix_studio_moves_quest_id", table_name="studio_moves")
    op.drop_index("ix_studio_moves_course_id", table_name="studio_moves")
    op.drop_table("studio_moves")
    op.add_column("studio_courses", sa.Column("description", sa.Text(), nullable=False, server_default=""))
    op.add_column("studio_courses", sa.Column("quest_count", sa.Integer(), nullable=False, server_default="10"))
    op.add_column("studio_courses", sa.Column("goals_per_quest", sa.Integer(), nullable=False, server_default="3"))
    rows = bind.execute(sa.text("SELECT id, theme, preferences FROM studio_courses")).mappings()
    for row in rows:
        bind.execute(
            sa.text(
                """
                UPDATE studio_courses
                SET description = :description,
                    quest_count = :quest_count,
                    goals_per_quest = :goals_per_quest
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "description": row["theme"] or "",
                "quest_count": _pref_count(row["preferences"], "quest_count", 10),
                "goals_per_quest": _pref_count(row["preferences"], "goals_per_quest", 3),
            },
        )


def _reshape_published_closes() -> None:
    bind = op.get_bind()
    op.add_column("quest_closes", sa.Column("close_style", sa.String(16), nullable=True))
    op.add_column("quest_closes", sa.Column("answer_style", sa.String(32), nullable=True))
    op.add_column("quest_closes", sa.Column("choice_mode", sa.String(16), nullable=True))
    op.add_column("quest_closes", sa.Column("intent", sa.Text(), nullable=False, server_default=""))
    rows = bind.execute(sa.text("SELECT id, kind, question, items FROM quest_closes")).mappings()
    for row in rows:
        style, answer, mode, packed, intent = _packed_close(row["kind"], row["question"], _json(row["items"]))
        bind.execute(
            sa.text(
                """
                UPDATE quest_closes
                SET close_style = :close_style,
                    answer_style = :answer_style,
                    choice_mode = :choice_mode,
                    items = CAST(:items AS json),
                    intent = :intent
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "close_style": style,
                "answer_style": answer,
                "choice_mode": mode,
                "items": json.dumps(packed),
                "intent": intent,
            },
        )
    op.alter_column("quest_closes", "close_style", nullable=False)
    op.alter_column("quest_closes", "answer_style", nullable=False)
    op.drop_constraint("ck_quest_closes_kind", "quest_closes", type_="check")
    op.drop_column("quest_closes", "kind")
    op.drop_column("quest_closes", "question")
    op.create_check_constraint(
        "ck_quest_closes_style",
        "quest_closes",
        "close_style IN ('one', 'several')",
    )
    op.create_check_constraint(
        "ck_quest_closes_answer",
        "quest_closes",
        "answer_style IN ('multiple_choice', 'essay', 'mixed')",
    )
    op.create_check_constraint(
        "ck_quest_closes_choice",
        "quest_closes",
        "choice_mode IS NULL OR choice_mode IN ('predefined', 'dynamic')",
    )


def _restart_sessions_on_first_goal() -> None:
    bind = op.get_bind()
    op.add_column("sessions", sa.Column("current_goal_id", sa.Uuid(), nullable=True))
    op.add_column(
        "sessions",
        sa.Column("close_started", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_foreign_key(
        "fk_sessions_current_goal_id",
        "sessions",
        "quest_goals",
        ["current_goal_id"],
        ["id"],
        ondelete="SET NULL",
    )
    bind.execute(
        sa.text(
            """
            UPDATE sessions AS s
            SET current_goal_id = first_goal.id,
                close_started = false
            FROM (
                SELECT DISTINCT ON (quest_id) id, quest_id
                FROM quest_goals
                ORDER BY quest_id, position
            ) AS first_goal
            WHERE first_goal.quest_id = s.quest_id
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE sessions AS s
            SET close_started = true,
                current_goal_id = NULL
            WHERE current_goal_id IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM quest_goals AS g WHERE g.quest_id = s.quest_id
              )
            """
        )
    )


def upgrade() -> None:
    _delete_seeded_courses()
    op.drop_constraint("fk_sessions_current_beat_id", "sessions", type_="foreignkey")
    op.drop_column("sessions", "current_beat_id")
    op.drop_index("ix_beat_results_session_id", table_name="beat_results")
    op.drop_table("beat_results")
    op.drop_index("ix_beats_quest_id", table_name="beats")
    op.drop_table("beats")
    _restart_sessions_on_first_goal()
    op.create_table(
        "goal_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("goal_id", sa.Uuid(), nullable=True),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("criterion", sa.Text(), nullable=False, server_default=""),
        sa.Column("answer", sa.Text(), nullable=False, server_default=""),
        sa.Column("misconception", sa.Text(), nullable=True),
        sa.Column("hint_tier", sa.String(16), nullable=True),
        sa.Column("choice", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_goal_results_score"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["goal_id"], ["quest_goals.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("session_id", "seq", name="uq_goal_results_session_seq"),
    )
    op.create_index("ix_goal_results_session_id", "goal_results", ["session_id"])
    _studio_goals_and_preferences()
    _reshape_published_closes()
    op.drop_constraint("ck_quests_type", "quests", type_="check")
    for column in (
        "quest_type",
        "prerequisite_codes",
        "competency_tags",
        "dinner_prompt",
        "learning_goal",
        "success_criterion",
        "requires_teach_back",
    ):
        op.drop_column("quests", column)
    op.drop_constraint("ck_courses_age_band", "courses", type_="check")
    op.drop_column("courses", "age_band")
    op.drop_column("courses", "standards_alignment")
    op.drop_column("courses", "competency_dictionary")


def downgrade() -> None:
    op.add_column("courses", sa.Column("age_band", sa.String(8), nullable=False, server_default="9-11"))
    op.add_column("courses", sa.Column("standards_alignment", sa.Text(), nullable=False, server_default=""))
    op.add_column(
        "courses",
        sa.Column("competency_dictionary", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.create_check_constraint(
        "ck_courses_age_band",
        "courses",
        "age_band IN ('6-8', '9-11', '12-14', '15-17')",
    )
    op.execute("UPDATE courses SET age_band = audience, standards_alignment = description")
    for column, typedef in (
        ("quest_type", sa.String(16)),
        ("prerequisite_codes", sa.JSON()),
        ("competency_tags", sa.JSON()),
        ("dinner_prompt", sa.Text()),
        ("learning_goal", sa.Text()),
        ("success_criterion", sa.JSON()),
        ("requires_teach_back", sa.Boolean()),
    ):
        op.add_column("quests", sa.Column(column, typedef, nullable=True))
    op.execute(
        """
        UPDATE quests
        SET quest_type = 'core',
            prerequisite_codes = '[]'::json,
            competency_tags = '[]'::json,
            dinner_prompt = '',
            learning_goal = '',
            success_criterion = '[]'::json,
            requires_teach_back = false
        """
    )
    op.alter_column("quests", "quest_type", nullable=False)
    op.alter_column("quests", "prerequisite_codes", nullable=False)
    op.alter_column("quests", "competency_tags", nullable=False)
    op.alter_column("quests", "dinner_prompt", nullable=False)
    op.alter_column("quests", "learning_goal", nullable=False)
    op.alter_column("quests", "success_criterion", nullable=False)
    op.alter_column("quests", "requires_teach_back", nullable=False)
    op.create_check_constraint(
        "ck_quests_type",
        "quests",
        "quest_type IN ('core', 'branch', 'capstone')",
    )
    op.drop_constraint("ck_quest_closes_choice", "quest_closes", type_="check")
    op.drop_constraint("ck_quest_closes_answer", "quest_closes", type_="check")
    op.drop_constraint("ck_quest_closes_style", "quest_closes", type_="check")
    op.add_column("quest_closes", sa.Column("kind", sa.String(16), nullable=True))
    op.add_column("quest_closes", sa.Column("question", sa.Text(), nullable=True))
    op.execute("UPDATE quest_closes SET kind = 'none', question = ''")
    op.alter_column("quest_closes", "kind", nullable=False)
    op.alter_column("quest_closes", "question", nullable=False)
    op.drop_column("quest_closes", "intent")
    op.drop_column("quest_closes", "choice_mode")
    op.drop_column("quest_closes", "answer_style")
    op.drop_column("quest_closes", "close_style")
    op.create_check_constraint(
        "ck_quest_closes_kind",
        "quest_closes",
        "kind IN ('essay', 'single', 'multi', 'none')",
    )
    op.drop_column("studio_courses", "goals_per_quest")
    op.drop_column("studio_courses", "quest_count")
    op.drop_column("studio_courses", "description")
    op.add_column("studio_quests", sa.Column("learning_goal", sa.Text(), nullable=False, server_default=""))
    op.add_column("studio_quests", sa.Column("success_criterion", sa.Text(), nullable=False, server_default=""))
    op.execute(
        """
        UPDATE studio_quests AS q
        SET learning_goal = g.learning_goal,
            success_criterion = g.success_criterion
        FROM studio_quest_goals AS g
        WHERE g.quest_id = q.id AND g.position = 1
        """
    )
    op.execute("DELETE FROM studio_quest_goals WHERE position = 1")
    op.drop_constraint("ck_studio_quest_goals_position", "studio_quest_goals", type_="check")
    op.create_check_constraint(
        "ck_studio_quest_goals_position",
        "studio_quest_goals",
        "position >= 2",
    )
    op.create_table(
        "studio_moves",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("quest_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("learning_goal", sa.Text(), nullable=False, server_default=""),
        sa.Column("success_criterion", sa.Text(), nullable=False, server_default=""),
        sa.CheckConstraint("position >= 1", name="ck_studio_moves_position"),
        sa.ForeignKeyConstraint(["course_id"], ["studio_courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["quest_id"], ["studio_quests.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("course_id", "code", name="uq_studio_moves_course_code"),
    )
    op.create_index("ix_studio_moves_course_id", "studio_moves", ["course_id"])
    op.create_index("ix_studio_moves_quest_id", "studio_moves", ["quest_id"])
    op.drop_index("ix_goal_results_session_id", table_name="goal_results")
    op.drop_table("goal_results")
    op.drop_constraint("fk_sessions_current_goal_id", "sessions", type_="foreignkey")
    op.drop_column("sessions", "close_started")
    op.drop_column("sessions", "current_goal_id")
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
            "role IN ('engage', 'try', 'name', 'show', 'teach_back')",
            name="ck_beats_role",
        ),
        sa.CheckConstraint("position >= 1", name="ck_beats_position"),
        sa.ForeignKeyConstraint(["quest_id"], ["quests.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("quest_id", "position", name="uq_beats_quest_position"),
    )
    op.create_index("ix_beats_quest_id", "beats", ["quest_id"])
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
    op.add_column("sessions", sa.Column("current_beat_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_sessions_current_beat_id",
        "sessions",
        "beats",
        ["current_beat_id"],
        ["id"],
        ondelete="RESTRICT",
    )
