"""Lift tutor quests onto the course and store goals and a close.

Quests leave the unit tier. Each quest keeps its id, so sessions and messages
stay attached. Goal rows and one close are filled from the lesson that was
already there. Chat rows are not deleted.

Revision ID: 013_tutor_quests_on_course
Revises: 012_quests_on_course
Create Date: 2026-11-05
"""

from typing import Sequence, Union
import json
import uuid

import sqlalchemy as sa
from alembic import op

revision: str = "013_tutor_quests_on_course"
down_revision: Union[str, None] = "012_quests_on_course"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _points(raw) -> list[str]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []
    texts = []
    for row in raw:
        if isinstance(row, dict) and str(row.get("text") or "").strip():
            texts.append(str(row["text"]).strip())
    return texts


def _close_from_widget(prompt: str | None, widget) -> tuple[str, str, list]:
    if isinstance(widget, str):
        try:
            widget = json.loads(widget)
        except json.JSONDecodeError:
            widget = None
    question = (prompt or "").strip()
    if not isinstance(widget, dict):
        if "?" in question:
            return "essay", question, []
        return "none", "", []
    stem = str(widget.get("prompt") or question).strip()
    choices = widget.get("choices") if isinstance(widget.get("choices"), list) else []
    answer = widget.get("answer")
    kind = widget.get("type")
    items = []
    if kind in {"single", "flaw", "multi"}:
        answers = set(answer if isinstance(answer, list) else [answer])
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            text = str(choice.get("text") or "").strip()
            if not text:
                continue
            items.append({"text": text, "correct": choice.get("id") in answers})
        return ("multi" if kind == "multi" else "single"), stem, items
    if stem:
        return "essay", stem, []
    return "none", "", []


def _backfill_goals_and_closes() -> None:
    bind = op.get_bind()
    quests = bind.execute(
        sa.text("SELECT id, learning_goal, success_criterion FROM quests")
    ).mappings()
    for quest in quests:
        texts = _points(quest["success_criterion"])
        goal = str(quest["learning_goal"] or "").strip()
        rows = [{"learning_goal": goal or texts[0], "success_criterion": texts[0]}] if texts else [
            {"learning_goal": goal or "States the idea.", "success_criterion": goal or "States the idea."}
        ]
        for index, text in enumerate(texts[1:], start=2):
            rows.append({"learning_goal": text, "success_criterion": text})
        if texts:
            rows[0] = {"learning_goal": goal or texts[0], "success_criterion": texts[0]}
        for position, row in enumerate(rows, start=1):
            bind.execute(
                sa.text(
                    """
                    INSERT INTO quest_goals (id, quest_id, position, learning_goal, success_criterion)
                    VALUES (:id, :quest_id, :position, :learning_goal, :success_criterion)
                    """
                ),
                {
                    "id": uuid.uuid4(),
                    "quest_id": quest["id"],
                    "position": position,
                    "learning_goal": row["learning_goal"],
                    "success_criterion": row["success_criterion"],
                },
            )
    shows = bind.execute(
        sa.text(
            """
            SELECT DISTINCT ON (quest_id) quest_id, prompt, widget
            FROM beats
            WHERE role = 'show'
            ORDER BY quest_id, position
            """
        )
    ).mappings()
    seen: set = set()
    for show in shows:
        seen.add(show["quest_id"])
        kind, question, items = _close_from_widget(show["prompt"], show["widget"])
        bind.execute(
            sa.text(
                """
                INSERT INTO quest_closes (id, quest_id, kind, question, items)
                VALUES (:id, :quest_id, :kind, :question, CAST(:items AS json))
                """
            ),
            {
                "id": uuid.uuid4(),
                "quest_id": show["quest_id"],
                "kind": kind,
                "question": question,
                "items": json.dumps(items),
            },
        )
    missing = bind.execute(sa.text("SELECT id FROM quests")).scalars()
    for quest_id in missing:
        if quest_id in seen:
            continue
        bind.execute(
            sa.text(
                """
                INSERT INTO quest_closes (id, quest_id, kind, question, items)
                VALUES (:id, :quest_id, 'none', '', CAST('[]' AS json))
                """
            ),
            {"id": uuid.uuid4(), "quest_id": quest_id},
        )


def upgrade() -> None:
    op.add_column("courses", sa.Column("description", sa.Text(), nullable=False, server_default=""))
    op.add_column("courses", sa.Column("audience", sa.String(8), nullable=False, server_default="9-11"))
    op.add_column("courses", sa.Column("quest_count", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("courses", sa.Column("goals_per_quest", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("courses", sa.Column("quiz_minutes", sa.Integer(), nullable=False, server_default="5"))
    op.add_column("courses", sa.Column("in_catalog", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.execute(
        """
        UPDATE courses
        SET description = standards_alignment,
            audience = age_band
        """
    )
    op.create_check_constraint(
        "ck_courses_audience",
        "courses",
        "audience IN ('6-8', '9-11', '12-14', '15-17')",
    )
    op.create_check_constraint(
        "ck_courses_quiz_minutes",
        "courses",
        "quiz_minutes IN (2, 5, 10)",
    )
    op.add_column("quests", sa.Column("course_id", sa.Uuid(), nullable=True))
    op.execute(
        """
        UPDATE quests AS q
        SET course_id = u.course_id
        FROM units AS u
        WHERE u.id = q.unit_id
        """
    )
    op.execute(
        """
        WITH ordered AS (
            SELECT q.id AS id,
                   row_number() OVER (
                       PARTITION BY u.course_id
                       ORDER BY u.number, q.position, q.code
                   ) AS pos
            FROM quests AS q
            JOIN units AS u ON u.id = q.unit_id
        )
        UPDATE quests AS q
        SET position = ordered.pos + 10000
        FROM ordered
        WHERE q.id = ordered.id
        """
    )
    op.execute("UPDATE quests SET position = position - 10000 WHERE position > 10000")
    op.drop_constraint("uq_quests_unit_position", "quests", type_="unique")
    op.drop_constraint("quests_unit_id_fkey", "quests", type_="foreignkey")
    op.drop_index("ix_quests_unit_id", table_name="quests")
    op.drop_column("quests", "unit_id")
    op.alter_column("quests", "course_id", nullable=False)
    op.create_index("ix_quests_course_id", "quests", ["course_id"])
    op.create_foreign_key(
        "quests_course_id_fkey",
        "quests",
        "courses",
        ["course_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint("uq_quests_course_position", "quests", ["course_id", "position"])
    op.drop_index("ix_units_course_id", table_name="units")
    op.drop_table("units")
    op.create_table(
        "quest_goals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("quest_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("learning_goal", sa.Text(), nullable=False, server_default=""),
        sa.Column("success_criterion", sa.Text(), nullable=False, server_default=""),
        sa.CheckConstraint("position >= 1", name="ck_quest_goals_position"),
        sa.ForeignKeyConstraint(["quest_id"], ["quests.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("quest_id", "position", name="uq_quest_goals_position"),
    )
    op.create_index("ix_quest_goals_quest_id", "quest_goals", ["quest_id"])
    op.create_table(
        "quest_closes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("quest_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("question", sa.Text(), nullable=False, server_default=""),
        sa.Column("items", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.CheckConstraint(
            "kind IN ('essay', 'single', 'multi', 'none')",
            name="ck_quest_closes_kind",
        ),
        sa.ForeignKeyConstraint(["quest_id"], ["quests.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("quest_id", name="uq_quest_closes_quest_id"),
    )
    _backfill_goals_and_closes()
    op.execute(
        """
        UPDATE courses AS c
        SET quest_count = COALESCE((
                SELECT count(*) FROM quests AS q WHERE q.course_id = c.id
            ), 0),
            goals_per_quest = COALESCE((
                SELECT max(counted.n) FROM (
                    SELECT count(*) AS n
                    FROM quest_goals AS g
                    JOIN quests AS q ON q.id = g.quest_id
                    WHERE q.course_id = c.id
                    GROUP BY g.quest_id
                ) AS counted
            ), 1)
        """
    )


def downgrade() -> None:
    op.drop_index("ix_quest_goals_quest_id", table_name="quest_goals")
    op.drop_table("quest_goals")
    op.drop_table("quest_closes")
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
    op.add_column("quests", sa.Column("unit_id", sa.Uuid(), nullable=True))
    op.execute(
        """
        INSERT INTO units (
            id, course_id, number, title, enduring_understanding, continuity_summary,
            is_diagnostic, is_capstone
        )
        SELECT gen_random_uuid(), c.id, 1, c.title, '', c.description, false, false
        FROM courses AS c
        """
    )
    op.execute(
        """
        UPDATE quests AS q
        SET unit_id = u.id
        FROM units AS u
        WHERE u.course_id = q.course_id
        """
    )
    op.alter_column("quests", "unit_id", nullable=False)
    op.create_index("ix_quests_unit_id", "quests", ["unit_id"])
    op.create_foreign_key(
        "quests_unit_id_fkey",
        "quests",
        "units",
        ["unit_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint("uq_quests_unit_position", "quests", ["unit_id", "position"])
    op.drop_constraint("uq_quests_course_position", "quests", type_="unique")
    op.drop_constraint("quests_course_id_fkey", "quests", type_="foreignkey")
    op.drop_index("ix_quests_course_id", table_name="quests")
    op.drop_column("quests", "course_id")
    op.drop_constraint("ck_courses_quiz_minutes", "courses", type_="check")
    op.drop_constraint("ck_courses_audience", "courses", type_="check")
    op.drop_column("courses", "in_catalog")
    op.drop_column("courses", "quiz_minutes")
    op.drop_column("courses", "goals_per_quest")
    op.drop_column("courses", "quest_count")
    op.drop_column("courses", "audience")
    op.drop_column("courses", "description")
