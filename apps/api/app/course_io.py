"""Validate, import, and export one Tier 1 course file."""

from __future__ import annotations

import copy
import re

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.blocks import normalize_hints, normalize_quiz, normalize_rows
from app.models import (
    AGE_BANDS,
    BEAT_ROLES,
    QUEST_TYPES,
    Beat,
    Course,
    Quest,
    Session as TutorSession,
    Unit,
)

BLOOM_LEVELS = {"remember", "understand", "apply", "analyze", "evaluate", "create"}
LOADS = {"low", "medium", "high"}
WIDGET_TYPES = {"single", "flaw", "order"}
CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,39}$")


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


def validate_beat(raw, field: str, *, role: str) -> dict:
    if not isinstance(raw, dict):
        raise CourseFileError(field, "must be an object")
    found = raw.get("role", role)
    if found != role:
        raise CourseFileError(f"{field}.role", f"must be {role}")
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
    if role in {"mystery_hook", "feynman_flip"}:
        if widget not in (None, {}):
            raise CourseFileError(f"{field}.widget", "must be empty on a typed beat")
        widget = None
    elif role == "interactive_toy" and not widget:
        raise CourseFileError(f"{field}.widget", "is required on the interactive toy")
    if widget:
        try:
            widget = normalize_quiz(widget)
        except HTTPException as exc:
            raise CourseFileError(f"{field}.widget", str(exc.detail)) from exc
        if widget["type"] not in WIDGET_TYPES:
            raise CourseFileError(f"{field}.widget.type", "must be single, flaw, or order")
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
        raise CourseFileError("code", "must be letters, numbers, and hyphens")
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
            raise CourseFileError(f"{path}.code", "must be letters, numbers, and hyphens")
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
            beats_raw = _as_list(raw_quest.get("beats"), f"{qpath}.beats")
            if len(beats_raw) != 4:
                raise CourseFileError(f"{qpath}.beats", "must contain exactly four beats")
            beats = [
                validate_beat(beats_raw[index], f"{qpath}.beats[{index}]", role=role)
                for index, role in enumerate(BEAT_ROLES)
            ]
            quests.append(
                {
                    "code": quest_code,
                    "title": _text(raw_quest.get("title"), f"{qpath}.title"),
                    "quest_type": quest_type,
                    "prerequisite_codes": prereqs,
                    "competency_tags": quest_tags,
                    "dinner_prompt": _text(raw_quest.get("dinner_prompt"), f"{qpath}.dinner_prompt"),
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
