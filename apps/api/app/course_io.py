"""Validate, import, and export one Tier 1 course file."""

from __future__ import annotations

import copy
import re
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.blocks import normalize_hints, normalize_quiz, normalize_rows
from app.models import (
    AGE_BANDS,
    BEAT_ROLES,
    QUEST_TYPES,
    Beat,
    BeatResult,
    Course,
    Quest,
    Session as TutorSession,
    Unit,
)

BLOOM_LEVELS = {"remember", "understand", "apply", "analyze", "evaluate", "create"}
LOADS = {"low", "medium", "high"}
WIDGET_TYPES = {"single", "multi", "flaw", "order"}
TYPED_ROLES = {"engage", "name", "teach_back"}
ROLE_ORDER = {role: index for index, role in enumerate(BEAT_ROLES)}
CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,39}$")


class CourseFileError(Exception):
    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


def _text(value, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CourseFileError(field, "is required")
    return value.strip()


def _sentence_count(text: str) -> int:
    return len(re.findall(r"[.!?]", text))


def _as_list(value, field: str) -> list:
    if not isinstance(value, list):
        raise CourseFileError(field, "must be a list")
    return value


def normalize_goal(value, field: str) -> str:
    goal = _text(value, field)
    if _sentence_count(goal) != 1:
        raise CourseFileError(field, "must be one sentence")
    return goal


def normalize_criterion(raw, field: str) -> list[dict]:
    if not isinstance(raw, list):
        raise CourseFileError(field, "must be a list")
    rows = normalize_rows(raw)
    if not 2 <= len(rows) <= 3:
        raise CourseFileError(field, "needs two or three rows")
    if sum(row["weight"] for row in rows) != 100:
        raise CourseFileError(field, "weights must sum to 100")
    return rows


def check_moves(moves: list[dict], *, teach_back: bool, criterion: list[dict], field: str = "beats") -> None:
    if not moves:
        raise CourseFileError(field, "needs at least one move")
    if len(moves) > 6:
        raise CourseFileError(field, "needs at most six moves")
    ranks = [ROLE_ORDER[move["role"]] for move in moves]
    if ranks != sorted(ranks):
        raise CourseFileError(field, "must stay in cycle order")
    teach_indexes = [index for index, move in enumerate(moves) if move["role"] == "teach_back"]
    if teach_back and not teach_indexes:
        raise CourseFileError("requires_teach_back", "needs a teach-back move")
    if teach_indexes and not teach_back:
        raise CourseFileError(
            f"{field}[{teach_indexes[0]}].role",
            "teach-back is only for a quest that must explain",
        )
    if len(teach_indexes) > 1 or (teach_indexes and teach_indexes != [len(moves) - 1]):
        raise CourseFileError(f"{field}[{teach_indexes[0]}].role", "teach-back must be the last move")
    show_indexes = [index for index, move in enumerate(moves) if move["role"] == "show"]
    if not show_indexes:
        raise CourseFileError(field, "needs a show move for the success criterion")
    criterion_key = [(row["id"], row["text"], row["weight"]) for row in criterion]
    for index in show_indexes:
        move_key = [(row["id"], row["text"], row["weight"]) for row in moves[index]["rubric"]]
        if move_key != criterion_key:
            raise CourseFileError(f"{field}[{index}].rubric", "must match the success criterion")


def validate_move(raw, field: str) -> dict:
    if not isinstance(raw, dict):
        raise CourseFileError(field, "must be an object")
    role = _text(raw.get("role"), f"{field}.role")
    if role not in BEAT_ROLES:
        raise CourseFileError(f"{field}.role", "must be engage, try, name, show, or teach_back")
    bloom = _text(raw.get("bloom_level"), f"{field}.bloom_level").lower()
    if bloom not in BLOOM_LEVELS:
        raise CourseFileError(f"{field}.bloom_level", "must be a Bloom level")
    load = _text(raw.get("cognitive_load"), f"{field}.cognitive_load").lower()
    if load not in LOADS:
        raise CourseFileError(f"{field}.cognitive_load", "must be low, medium, or high")
    prompt = _text(raw.get("prompt"), f"{field}.prompt")
    rows = normalize_rows(raw.get("rubric") or [])
    if not rows:
        raise CourseFileError(f"{field}.rubric", "needs at least one row")
    if sum(row["weight"] for row in rows) != 100:
        raise CourseFileError(f"{field}.rubric", "weights must sum to 100")
    hints = normalize_hints(raw.get("hint_ladder") or {})
    for key in ("nudge", "analogy", "scaffold"):
        if not hints[key]:
            raise CourseFileError(f"{field}.hint_ladder.{key}", "is required")
    traps_raw = _as_list(raw.get("misconception_map"), f"{field}.misconception_map")
    traps: list[dict] = []
    seen: set[str] = set()
    for index, trap in enumerate(traps_raw):
        path = f"{field}.misconception_map[{index}]"
        if not isinstance(trap, dict):
            raise CourseFileError(path, "must be an object")
        trap_id = re.sub(r"[^a-z0-9-]", "", str(trap.get("id") or f"t{index + 1}").lower())[:40] or f"t{index + 1}"
        while trap_id in seen:
            trap_id = f"{trap_id}-{index + 1}"
        seen.add(trap_id)
        text = _text(trap.get("trap"), f"{path}.trap")
        note = _text(trap.get("note"), f"{path}.note")
        traps.append({"id": trap_id, "trap": text, "note": note})
    if not traps:
        raise CourseFileError(f"{field}.misconception_map", "needs at least one trap")
    widget = raw.get("widget")
    if role in TYPED_ROLES:
        if widget not in (None, {}):
            raise CourseFileError(f"{field}.widget", "must be empty on this move")
        widget = None
    if widget:
        try:
            widget = normalize_quiz(widget)
        except HTTPException as exc:
            raise CourseFileError(f"{field}.widget", str(exc.detail)) from exc
        if widget["type"] not in WIDGET_TYPES:
            raise CourseFileError(f"{field}.widget.type", "must be single, multi, flaw, or order")
    return {
        "role": role,
        "bloom_level": bloom,
        "cognitive_load": load,
        "prompt": prompt,
        "rubric": rows,
        "misconception_map": traps,
        "hint_ladder": hints,
        "widget": widget,
    }


def validate_course(payload) -> dict:
    if not isinstance(payload, dict):
        raise CourseFileError("course", "must be an object")
    code = _text(payload.get("code"), "code")
    if not CODE_RE.match(code):
        raise CourseFileError("code", "must be letters, numbers, hyphens, and dots")
    title = _text(payload.get("title"), "title")
    age_band = _text(payload.get("age_band"), "age_band")
    if age_band not in AGE_BANDS:
        raise CourseFileError("age_band", "must be 6-8, 9-11, 12-14, or 15-17")
    standards = _text(payload.get("standards_alignment"), "standards_alignment")
    dictionary = _as_list(payload.get("competency_dictionary"), "competency_dictionary")
    competencies: list[dict] = []
    tags: set[str] = set()
    for index, item in enumerate(dictionary):
        path = f"competency_dictionary[{index}]"
        if not isinstance(item, dict):
            raise CourseFileError(path, "must be an object")
        tag = _text(item.get("code"), f"{path}.code")
        if not CODE_RE.match(tag):
            raise CourseFileError(f"{path}.code", "must be letters, numbers, hyphens, and dots")
        if tag in tags:
            raise CourseFileError(f"{path}.code", "is duplicated")
        tags.add(tag)
        competencies.append({"code": tag, "description": _text(item.get("description"), f"{path}.description")})
    units_raw = _as_list(payload.get("units"), "units")
    if not units_raw:
        raise CourseFileError("units", "needs at least one unit")
    units: list[dict] = []
    numbers: set[int] = set()
    quest_codes: list[str] = []
    for unit_index, raw_unit in enumerate(units_raw):
        path = f"units[{unit_index}]"
        if not isinstance(raw_unit, dict):
            raise CourseFileError(path, "must be an object")
        number = raw_unit.get("number")
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            raise CourseFileError(f"{path}.number", "must be a positive integer")
        if number in numbers:
            raise CourseFileError(f"{path}.number", "is duplicated")
        numbers.add(number)
        continuity = _text(raw_unit.get("continuity_summary"), f"{path}.continuity_summary")
        if _sentence_count(continuity) < 2:
            raise CourseFileError(f"{path}.continuity_summary", "must be two sentences")
        quests_raw = _as_list(raw_unit.get("quests"), f"{path}.quests")
        if not quests_raw:
            raise CourseFileError(f"{path}.quests", "needs at least one quest")
        quests: list[dict] = []
        for quest_index, raw_quest in enumerate(quests_raw):
            qpath = f"{path}.quests[{quest_index}]"
            if not isinstance(raw_quest, dict):
                raise CourseFileError(qpath, "must be an object")
            quest_code = _text(raw_quest.get("code"), f"{qpath}.code")
            if not CODE_RE.match(quest_code):
                raise CourseFileError(f"{qpath}.code", "must be letters, numbers, and hyphens")
            if quest_code in quest_codes:
                raise CourseFileError(f"{qpath}.code", "is duplicated")
            quest_codes.append(quest_code)
            quest_type = _text(raw_quest.get("quest_type"), f"{qpath}.quest_type")
            if quest_type not in QUEST_TYPES:
                raise CourseFileError(f"{qpath}.quest_type", "must be core, branch, or capstone")
            prereqs_raw = _as_list(raw_quest.get("prerequisite_codes"), f"{qpath}.prerequisite_codes")
            prereqs = []
            for pre_index, prereq in enumerate(prereqs_raw):
                pre = _text(prereq, f"{qpath}.prerequisite_codes[{pre_index}]")
                if pre == quest_code:
                    raise CourseFileError(f"{qpath}.prerequisite_codes[{pre_index}]", "cannot be the quest itself")
                prereqs.append(pre)
            tag_raw = _as_list(raw_quest.get("competency_tags"), f"{qpath}.competency_tags")
            if not 1 <= len(tag_raw) <= 2:
                raise CourseFileError(f"{qpath}.competency_tags", "needs one or two tags")
            quest_tags = []
            for tag_index, tag in enumerate(tag_raw):
                cleaned = _text(tag, f"{qpath}.competency_tags[{tag_index}]")
                if cleaned not in tags:
                    raise CourseFileError(
                        f"{qpath}.competency_tags[{tag_index}]",
                        "is not in the competency dictionary",
                    )
                quest_tags.append(cleaned)
            goal = normalize_goal(raw_quest.get("learning_goal"), f"{qpath}.learning_goal")
            criterion = normalize_criterion(raw_quest.get("success_criterion"), f"{qpath}.success_criterion")
            teach_back = raw_quest.get("requires_teach_back")
            if not isinstance(teach_back, bool):
                raise CourseFileError(f"{qpath}.requires_teach_back", "must be true or false")
            beats_raw = _as_list(raw_quest.get("beats"), f"{qpath}.beats")
            beats = [
                validate_move(beat, f"{qpath}.beats[{index}]")
                for index, beat in enumerate(beats_raw)
            ]
            check_moves(
                beats,
                teach_back=teach_back,
                criterion=criterion,
                field=f"{qpath}.beats",
            )
            quests.append(
                {
                    "code": quest_code,
                    "title": _text(raw_quest.get("title"), f"{qpath}.title"),
                    "quest_type": quest_type,
                    "prerequisite_codes": prereqs,
                    "competency_tags": quest_tags,
                    "dinner_prompt": _text(raw_quest.get("dinner_prompt"), f"{qpath}.dinner_prompt"),
                    "learning_goal": goal,
                    "success_criterion": criterion,
                    "requires_teach_back": teach_back,
                    "beats": beats,
                }
            )
        units.append(
            {
                "number": number,
                "title": _text(raw_unit.get("title"), f"{path}.title"),
                "enduring_understanding": _text(
                    raw_unit.get("enduring_understanding"), f"{path}.enduring_understanding"
                ),
                "continuity_summary": continuity,
                "is_diagnostic": bool(raw_unit.get("is_diagnostic")),
                "is_capstone": bool(raw_unit.get("is_capstone")),
                "quests": quests,
            }
        )
    known = set(quest_codes)
    for unit_index, unit_body in enumerate(units):
        for quest_index, quest_body in enumerate(unit_body["quests"]):
            for pre_index, prereq in enumerate(quest_body["prerequisite_codes"]):
                if prereq not in known:
                    raise CourseFileError(
                        f"units[{unit_index}].quests[{quest_index}].prerequisite_codes[{pre_index}]",
                        "does not match a quest in this course",
                    )
    return {
        "code": code,
        "title": title,
        "age_band": age_band,
        "standards_alignment": standards,
        "competency_dictionary": competencies,
        "units": units,
    }


def export_course(course: Course) -> dict:
    return {
        "code": course.code,
        "title": course.title,
        "age_band": course.age_band,
        "standards_alignment": course.standards_alignment,
        "competency_dictionary": copy.deepcopy(course.competency_dictionary or []),
        "units": [
            {
                "number": unit.number,
                "title": unit.title,
                "enduring_understanding": unit.enduring_understanding,
                "continuity_summary": unit.continuity_summary,
                "is_diagnostic": unit.is_diagnostic,
                "is_capstone": unit.is_capstone,
                "quests": [
                    {
                        "code": quest.code,
                        "title": quest.title,
                        "quest_type": quest.quest_type,
                        "prerequisite_codes": list(quest.prerequisite_codes or []),
                        "competency_tags": list(quest.competency_tags or []),
                        "dinner_prompt": quest.dinner_prompt,
                        "learning_goal": quest.learning_goal,
                        "success_criterion": copy.deepcopy(quest.success_criterion or []),
                        "requires_teach_back": bool(quest.requires_teach_back),
                        "beats": [
                            {
                                "role": beat.role,
                                "bloom_level": beat.bloom_level,
                                "cognitive_load": beat.cognitive_load,
                                "prompt": beat.prompt,
                                "rubric": copy.deepcopy(beat.rubric or []),
                                "misconception_map": copy.deepcopy(beat.misconception_map or []),
                                "hint_ladder": copy.deepcopy(beat.hint_ladder or {}),
                                "widget": copy.deepcopy(beat.widget) if beat.widget else None,
                            }
                            for beat in sorted(quest.beats, key=lambda item: item.position)
                        ],
                    }
                    for quest in sorted(unit.quests, key=lambda item: item.position)
                ],
            }
            for unit in sorted(course.units, key=lambda item: item.number)
        ],
    }


def _write_tree(course: Course, payload: dict) -> None:
    course.code = payload["code"]
    course.title = payload["title"]
    course.age_band = payload["age_band"]
    course.standards_alignment = payload["standards_alignment"]
    course.competency_dictionary = payload["competency_dictionary"]
    for unit_body in payload["units"]:
        unit = Unit(
            course_id=course.id,
            number=unit_body["number"],
            title=unit_body["title"],
            enduring_understanding=unit_body["enduring_understanding"],
            continuity_summary=unit_body["continuity_summary"],
            is_diagnostic=unit_body["is_diagnostic"],
            is_capstone=unit_body["is_capstone"],
        )
        course.units.append(unit)
        for position, quest_body in enumerate(unit_body["quests"], start=1):
            quest = Quest(
                code=quest_body["code"],
                title=quest_body["title"],
                quest_type=quest_body["quest_type"],
                prerequisite_codes=quest_body["prerequisite_codes"],
                competency_tags=quest_body["competency_tags"],
                dinner_prompt=quest_body["dinner_prompt"],
                learning_goal=quest_body["learning_goal"],
                success_criterion=quest_body["success_criterion"],
                requires_teach_back=quest_body["requires_teach_back"],
                position=position,
            )
            unit.quests.append(quest)
            for beat_position, beat_body in enumerate(quest_body["beats"], start=1):
                quest.beats.append(
                    Beat(
                        position=beat_position,
                        role=beat_body["role"],
                        bloom_level=beat_body["bloom_level"],
                        cognitive_load=beat_body["cognitive_load"],
                        prompt=beat_body["prompt"],
                        rubric=beat_body["rubric"],
                        misconception_map=beat_body["misconception_map"],
                        hint_ladder=beat_body["hint_ladder"],
                        widget=beat_body["widget"],
                    )
                )


def replace_course(db: Session, payload: dict) -> Course:
    """Upload replaces the course with this code. Open classes on it are cleared."""
    normalized = validate_course(payload)
    existing = db.scalar(
        select(Course)
        .where(Course.code == normalized["code"])
        .options(selectinload(Course.units).selectinload(Unit.quests))
    )
    if existing is None:
        taken = db.scalar(select(Quest.id).where(Quest.code.in_([
            quest["code"] for unit in normalized["units"] for quest in unit["quests"]
        ])))
        if taken is not None:
            raise CourseFileError("quests", "a quest code is already used by another course")
        course = Course(code=normalized["code"], title=normalized["title"], age_band=normalized["age_band"])
        db.add(course)
        db.flush()
        _write_tree(course, normalized)
        db.flush()
        return course
    quest_ids = [quest.id for unit in existing.units for quest in unit.quests]
    if quest_ids:
        db.execute(delete(TutorSession).where(TutorSession.quest_id.in_(quest_ids)))
        db.flush()
    for unit in list(existing.units):
        db.delete(unit)
    db.flush()
    incoming = [
        quest["code"] for unit in normalized["units"] for quest in unit["quests"]
    ]
    clash = db.scalar(select(Quest.id).where(Quest.code.in_(incoming)))
    if clash is not None:
        raise CourseFileError("quests", "a quest code is already used by another course")
    _write_tree(existing, normalized)
    db.flush()
    return existing


def _beats_held(db: Session, beat_ids: list) -> bool:
    if not beat_ids:
        return False
    if db.scalar(select(TutorSession.id).where(TutorSession.current_beat_id.in_(beat_ids))) is not None:
        return True
    return db.scalar(select(BeatResult.id).where(BeatResult.beat_id.in_(beat_ids))) is not None


def _fill_beat(beat: Beat, body: dict) -> None:
    beat.role = body["role"]
    beat.bloom_level = body["bloom_level"]
    beat.cognitive_load = body["cognitive_load"]
    beat.prompt = body["prompt"]
    beat.rubric = body["rubric"]
    beat.misconception_map = body["misconception_map"]
    beat.hint_ladder = body["hint_ladder"]
    beat.widget = body["widget"]


def _sync_beats(quest: Quest, beats: list[dict]) -> None:
    by_position = {beat.position: beat for beat in quest.beats}
    incoming = set(range(1, len(beats) + 1))
    for position, body in enumerate(beats, start=1):
        beat = by_position.get(position)
        if beat is None:
            beat = Beat(position=position, role=body["role"])
            quest.beats.append(beat)
        _fill_beat(beat, body)
    for beat in list(quest.beats):
        if beat.position not in incoming:
            quest.beats.remove(beat)


def _fill_quest(quest: Quest, body: dict) -> None:
    quest.title = body["title"]
    quest.quest_type = body["quest_type"]
    quest.prerequisite_codes = body["prerequisite_codes"]
    quest.competency_tags = body["competency_tags"]
    quest.dinner_prompt = body["dinner_prompt"]
    quest.learning_goal = body["learning_goal"]
    quest.success_criterion = body["success_criterion"]
    quest.requires_teach_back = body["requires_teach_back"]


def update_course_in_place(db: Session, payload: dict) -> Course:
    """Refresh one course without deleting classes.

    Units match by number, quests by code, and moves by position. Columns are
    updated on those rows. A quest that still has a class is not dropped.
    """
    normalized = validate_course(payload)
    course = db.scalar(
        select(Course)
        .where(Course.code == normalized["code"])
        .options(selectinload(Course.units).selectinload(Unit.quests).selectinload(Quest.beats))
    )
    if course is None:
        raise CourseFileError("code", "is not in the database")

    incoming_codes = [
        quest["code"] for unit in normalized["units"] for quest in unit["quests"]
    ]
    incoming_code_set = set(incoming_codes)
    quests_by_code = {quest.code: quest for unit in course.units for quest in unit.quests}
    dropped = [quest for quest in quests_by_code.values() if quest.code not in incoming_code_set]
    if dropped:
        dropped_ids = [quest.id for quest in dropped]
        held_id = db.scalar(
            select(TutorSession.quest_id).where(TutorSession.quest_id.in_(dropped_ids))
        )
        if held_id is not None:
            code = next(quest.code for quest in dropped if quest.id == held_id)
            raise CourseFileError("quests", f"{code} still has classes, so it cannot be removed")
        dropped_beats = [beat.id for quest in dropped for beat in quest.beats]
        if _beats_held(db, dropped_beats):
            raise CourseFileError("beats", "a move still has classes, so it cannot be removed")

    for unit_body in normalized["units"]:
        for quest_body in unit_body["quests"]:
            quest = quests_by_code.get(quest_body["code"])
            if quest is None:
                continue
            incoming_positions = set(range(1, len(quest_body["beats"]) + 1))
            extra_ids = [beat.id for beat in quest.beats if beat.position not in incoming_positions]
            if _beats_held(db, extra_ids):
                raise CourseFileError("beats", "a move still has classes, so it cannot be removed")

    course.title = normalized["title"]
    course.age_band = normalized["age_band"]
    course.standards_alignment = normalized["standards_alignment"]
    course.competency_dictionary = normalized["competency_dictionary"]
    course.updated_at = datetime.now(timezone.utc)

    units_by_number = {unit.number: unit for unit in course.units}
    for unit_body in normalized["units"]:
        unit = units_by_number.get(unit_body["number"])
        if unit is None:
            unit = Unit(
                course_id=course.id,
                number=unit_body["number"],
                title=unit_body["title"],
                enduring_understanding=unit_body["enduring_understanding"],
                continuity_summary=unit_body["continuity_summary"],
                is_diagnostic=unit_body["is_diagnostic"],
                is_capstone=unit_body["is_capstone"],
            )
            course.units.append(unit)
            units_by_number[unit.number] = unit
        else:
            unit.title = unit_body["title"]
            unit.enduring_understanding = unit_body["enduring_understanding"]
            unit.continuity_summary = unit_body["continuity_summary"]
            unit.is_diagnostic = unit_body["is_diagnostic"]
            unit.is_capstone = unit_body["is_capstone"]
    db.flush()

    for unit in list(course.units):
        for quest in list(unit.quests):
            if quest.code not in incoming_code_set:
                unit.quests.remove(quest)
    db.flush()

    live = [quests_by_code[code] for code in incoming_codes if code in quests_by_code]
    for offset, quest in enumerate(live, start=1):
        quest.position = 10_000 + offset
    db.flush()

    for unit_body in normalized["units"]:
        unit = units_by_number[unit_body["number"]]
        for position, quest_body in enumerate(unit_body["quests"], start=1):
            quest = quests_by_code.get(quest_body["code"])
            if quest is None:
                clash = db.scalar(select(Quest.id).where(Quest.code == quest_body["code"]))
                if clash is not None:
                    raise CourseFileError("quests", "a quest code is already used by another course")
                quest = Quest(code=quest_body["code"], position=position)
                unit.quests.append(quest)
                quests_by_code[quest.code] = quest
            else:
                quest.unit = unit
                quest.position = position
            _fill_quest(quest, quest_body)
            _sync_beats(quest, quest_body["beats"])
    db.flush()

    incoming_numbers = [unit_body["number"] for unit_body in normalized["units"]]
    stale_units = db.scalars(
        select(Unit).where(Unit.course_id == course.id, Unit.number.not_in(incoming_numbers))
    ).all()
    for unit in stale_units:
        if db.scalar(select(Quest.id).where(Quest.unit_id == unit.id)) is not None:
            raise CourseFileError("units", "a unit still has quests, so it cannot be removed")
        db.delete(unit)
    db.flush()
    return course
