"""Validate, import, and export one Tier 1 course file."""

from __future__ import annotations

import copy
import re
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, object_session, selectinload

from app.blocks import normalize_hints, normalize_quiz, normalize_rows
from app.models import (
    AGE_BANDS,
    BEAT_ROLES,
    QUEST_TYPES,
    Beat,
    BeatResult,
    Course,
    Quest,
    QuestClose,
    QuestGoal,
    Session as TutorSession,
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


def _validate_legacy(payload) -> dict:
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


CLOSE_KINDS = ("essay", "single", "multi", "none")
QUIZ_MINUTES = (2, 5, 10)


def goals_from_points(learning_goal: str, criterion: list) -> list[dict]:
    """One goal per criterion point. The quest sentence stays on the first goal."""
    texts = []
    for row in criterion or []:
        if isinstance(row, dict) and str(row.get("text") or "").strip():
            texts.append(str(row["text"]).strip())
    goal = (learning_goal or "").strip()
    if not texts:
        text = goal or "States the idea."
        return [{"position": 1, "learning_goal": goal or text, "success_criterion": text}]
    goals = [{"position": 1, "learning_goal": goal or texts[0], "success_criterion": texts[0]}]
    for index, text in enumerate(texts[1:], start=2):
        goals.append({"position": index, "learning_goal": text, "success_criterion": text})
    return goals


def close_from_beats(beats: list[dict]) -> dict:
    """The show move becomes an essay, a single choice, a multi-choice, or no questions."""
    show = next((beat for beat in beats if beat.get("role") == "show"), None)
    widget = show.get("widget") if isinstance(show, dict) else None
    prompt = str((show or {}).get("prompt") or "").strip()
    if not isinstance(widget, dict):
        if "?" in prompt:
            return {"kind": "essay", "question": prompt, "items": []}
        return {"kind": "none", "question": "", "items": []}
    question = str(widget.get("prompt") or prompt).strip()
    choices = widget.get("choices") if isinstance(widget.get("choices"), list) else []
    answer = widget.get("answer")
    kind = widget.get("type")
    if kind in {"single", "flaw", "multi"}:
        answers = set(answer if isinstance(answer, list) else [answer])
        items = []
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            text = str(choice.get("text") or "").strip()
            if not text:
                continue
            items.append({"text": text, "correct": choice.get("id") in answers})
        return {"kind": "multi" if kind == "multi" else "single", "question": question, "items": items}
    if question:
        return {"kind": "essay", "question": question, "items": []}
    return {"kind": "none", "question": "", "items": []}


def _preferred_goal_count(quests: list[dict]) -> int:
    counts = [max(1, len(quest.get("goals") or [])) for quest in quests]
    if not counts:
        return 1
    tally: dict[int, int] = {}
    for count in counts:
        tally[count] = tally.get(count, 0) + 1
    return max(tally, key=lambda count: (tally[count], count))


def _flatten(normalized: dict) -> dict:
    quests = []
    for unit in normalized["units"]:
        for quest in unit["quests"]:
            body = dict(quest)
            body["goals"] = goals_from_points(quest["learning_goal"], quest["success_criterion"])
            body["close"] = close_from_beats(quest["beats"])
            quests.append(body)
    for index, quest in enumerate(quests, start=1):
        quest["position"] = index
    audience = normalized["age_band"]
    return {
        "code": normalized["code"],
        "title": normalized["title"],
        "age_band": audience,
        "standards_alignment": normalized["standards_alignment"],
        "competency_dictionary": normalized["competency_dictionary"],
        "description": normalized["standards_alignment"],
        "audience": audience,
        "quest_count": len(quests) or 1,
        "goals_per_quest": _preferred_goal_count(quests),
        "quiz_minutes": 5,
        "quests": quests,
    }


def _header(payload: dict) -> dict:
    code = _text(payload.get("code"), "code")
    if not CODE_RE.match(code):
        raise CourseFileError("code", "must be letters, numbers, hyphens, and dots")
    title = _text(payload.get("title"), "title")
    age_band = _text(payload.get("age_band"), "age_band")
    if age_band not in AGE_BANDS:
        raise CourseFileError("age_band", "must be 6-8, 9-11, 12-14, or 15-17")
    audience = payload.get("audience") or age_band
    if audience not in AGE_BANDS:
        raise CourseFileError("audience", "must be 6-8, 9-11, 12-14, or 15-17")
    standards = payload.get("standards_alignment")
    if not isinstance(standards, str) or not standards.strip():
        standards = title
    else:
        standards = standards.strip()
    description = payload.get("description")
    if not isinstance(description, str):
        description = ""
    quiz_minutes = payload.get("quiz_minutes", 5)
    if quiz_minutes not in QUIZ_MINUTES:
        raise CourseFileError("quiz_minutes", "must be 2, 5, or 10")
    quest_count = payload.get("quest_count")
    if isinstance(quest_count, bool) or not isinstance(quest_count, int) or quest_count < 1:
        quest_count = None
    goals_per_quest = payload.get("goals_per_quest")
    if isinstance(goals_per_quest, bool) or not isinstance(goals_per_quest, int) or goals_per_quest < 1:
        goals_per_quest = None
    dictionary = _as_list(payload.get("competency_dictionary") or [], "competency_dictionary")
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
    return {
        "code": code,
        "title": title,
        "age_band": age_band,
        "audience": audience,
        "standards_alignment": standards,
        "description": description.strip(),
        "quiz_minutes": quiz_minutes,
        "quest_count": quest_count,
        "goals_per_quest": goals_per_quest,
        "competency_dictionary": competencies,
        "tags": tags,
    }


def _validate_goals(raw, field: str) -> list[dict]:
    rows = _as_list(raw, field)
    if not rows:
        raise CourseFileError(field, "needs at least one goal")
    goals = []
    for index, item in enumerate(rows, start=1):
        path = f"{field}[{index - 1}]"
        if not isinstance(item, dict):
            raise CourseFileError(path, "must be an object")
        learning_goal = _text(item.get("learning_goal"), f"{path}.learning_goal")
        criterion = _text(item.get("success_criterion"), f"{path}.success_criterion")
        goals.append({"position": index, "learning_goal": learning_goal, "success_criterion": criterion})
    return goals


def _validate_close(raw, field: str) -> dict:
    if not isinstance(raw, dict):
        raise CourseFileError(field, "must say how the quest closes")
    kind = raw.get("kind")
    if kind not in CLOSE_KINDS:
        raise CourseFileError(f"{field}.kind", "must be essay, single, multi, or none")
    question = raw.get("question") or ""
    if not isinstance(question, str):
        raise CourseFileError(f"{field}.question", "must be text")
    items_raw = raw.get("items") or []
    if not isinstance(items_raw, list):
        raise CourseFileError(f"{field}.items", "must be a list")
    items = []
    for index, item in enumerate(items_raw):
        if isinstance(item, str) and item.strip():
            items.append({"text": item.strip(), "correct": False})
            continue
        if not isinstance(item, dict) or not str(item.get("text") or "").strip():
            raise CourseFileError(f"{field}.items[{index}]", "each choice needs text")
        items.append({"text": str(item["text"]).strip(), "correct": item.get("correct") is True})
    if kind in {"single", "multi"} and len(items) < 2:
        raise CourseFileError(f"{field}.items", "needs two choices")
    if kind in {"essay", "none"}:
        items = []
    if kind == "none":
        question = ""
    return {"kind": kind, "question": question.strip(), "items": items}


def _validate_catalog(payload: dict) -> dict:
    header = _header(payload)
    tags = header.pop("tags")
    quests_raw = _as_list(payload.get("quests"), "quests")
    quests = []
    quest_codes: list[str] = []
    for index, raw in enumerate(quests_raw):
        path = f"quests[{index}]"
        if not isinstance(raw, dict):
            raise CourseFileError(path, "must be an object")
        quest_code = _text(raw.get("code"), f"{path}.code")
        if not CODE_RE.match(quest_code):
            raise CourseFileError(f"{path}.code", "must be letters, numbers, and hyphens")
        if quest_code in quest_codes:
            raise CourseFileError(f"{path}.code", "is duplicated")
        quest_codes.append(quest_code)
        quest_type = _text(raw.get("quest_type") or "core", f"{path}.quest_type")
        if quest_type not in QUEST_TYPES:
            raise CourseFileError(f"{path}.quest_type", "must be core, branch, or capstone")
        prereqs_raw = _as_list(raw.get("prerequisite_codes") or [], f"{path}.prerequisite_codes")
        prereqs = []
        for pre_index, prereq in enumerate(prereqs_raw):
            pre = _text(prereq, f"{path}.prerequisite_codes[{pre_index}]")
            if pre == quest_code:
                raise CourseFileError(f"{path}.prerequisite_codes[{pre_index}]", "cannot be the quest itself")
            prereqs.append(pre)
        tag_raw = _as_list(raw.get("competency_tags") or [], f"{path}.competency_tags")
        quest_tags = []
        for tag_index, tag in enumerate(tag_raw):
            cleaned = _text(tag, f"{path}.competency_tags[{tag_index}]")
            if tags and cleaned not in tags:
                raise CourseFileError(
                    f"{path}.competency_tags[{tag_index}]",
                    "is not in the competency dictionary",
                )
            if not tags:
                raise CourseFileError(f"{path}.competency_tags[{tag_index}]", "is not in the competency dictionary")
            quest_tags.append(cleaned)
        goal = _text(raw.get("learning_goal"), f"{path}.learning_goal")
        criterion = normalize_rows(raw.get("success_criterion") or [])
        if not criterion:
            raise CourseFileError(f"{path}.success_criterion", "needs at least one row")
        if sum(row["weight"] for row in criterion) != 100:
            raise CourseFileError(f"{path}.success_criterion", "weights must sum to 100")
        teach_back = raw.get("requires_teach_back")
        if not isinstance(teach_back, bool):
            teach_back = False
        beats_raw = _as_list(raw.get("beats"), f"{path}.beats")
        beats = [validate_move(beat, f"{path}.beats[{beat_index}]") for beat_index, beat in enumerate(beats_raw)]
        check_moves(beats, teach_back=teach_back, criterion=criterion, field=f"{path}.beats")
        goals = _validate_goals(raw.get("goals"), f"{path}.goals")
        close = _validate_close(raw.get("close"), f"{path}.close")
        dinner = raw.get("dinner_prompt") or raw.get("title") or quest_code
        quests.append(
            {
                "code": quest_code,
                "title": _text(raw.get("title"), f"{path}.title"),
                "quest_type": quest_type,
                "prerequisite_codes": prereqs,
                "competency_tags": quest_tags,
                "dinner_prompt": _text(dinner, f"{path}.dinner_prompt"),
                "learning_goal": goal,
                "success_criterion": criterion,
                "requires_teach_back": teach_back,
                "beats": beats,
                "goals": goals,
                "close": close,
                "position": index + 1,
            }
        )
    known = set(quest_codes)
    for index, quest in enumerate(quests):
        for pre_index, prereq in enumerate(quest["prerequisite_codes"]):
            if prereq not in known:
                raise CourseFileError(
                    f"quests[{index}].prerequisite_codes[{pre_index}]",
                    "does not match a quest in this course",
                )
    header["quest_count"] = header["quest_count"] or len(quests) or 1
    header["goals_per_quest"] = header["goals_per_quest"] or _preferred_goal_count(quests)
    header["quests"] = quests
    return header


def validate_course(payload) -> dict:
    if not isinstance(payload, dict):
        raise CourseFileError("course", "must be an object")
    if "units" in payload and "quests" not in payload:
        return _flatten(_validate_legacy(payload))
    return _validate_catalog(payload)


def _quest_fields(quest: Quest) -> dict:
    return {
        "code": quest.code,
        "title": quest.title,
        "quest_type": quest.quest_type,
        "prerequisite_codes": list(quest.prerequisite_codes or []),
        "competency_tags": list(quest.competency_tags or []),
        "dinner_prompt": quest.dinner_prompt,
        "learning_goal": quest.learning_goal,
        "success_criterion": copy.deepcopy(quest.success_criterion or []),
        "requires_teach_back": bool(quest.requires_teach_back),
        "goals": [
            {
                "position": goal.position,
                "learning_goal": goal.learning_goal,
                "success_criterion": goal.success_criterion,
            }
            for goal in sorted(quest.goals, key=lambda item: item.position)
        ],
        "close": {
            "kind": quest.close.kind,
            "question": quest.close.question,
            "items": copy.deepcopy(quest.close.items or []),
        }
        if quest.close is not None
        else {"kind": "none", "question": "", "items": []},
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


def export_course(course: Course) -> dict:
    return {
        "code": course.code,
        "title": course.title,
        "age_band": course.age_band,
        "standards_alignment": course.standards_alignment,
        "competency_dictionary": copy.deepcopy(course.competency_dictionary or []),
        "description": course.description or "",
        "audience": course.audience or course.age_band,
        "quest_count": course.quest_count,
        "goals_per_quest": course.goals_per_quest,
        "quiz_minutes": course.quiz_minutes,
        "quests": [
            _quest_fields(quest)
            for quest in sorted(course.quests, key=lambda item: item.position)
        ],
    }


def _apply_course_fields(course: Course, payload: dict) -> None:
    course.code = payload["code"]
    course.title = payload["title"]
    course.age_band = payload["age_band"]
    course.standards_alignment = payload["standards_alignment"]
    course.competency_dictionary = payload["competency_dictionary"]
    course.description = payload.get("description") or ""
    course.audience = payload.get("audience") or payload["age_band"]
    course.quest_count = int(payload.get("quest_count") or len(payload["quests"]) or 1)
    course.goals_per_quest = int(payload.get("goals_per_quest") or 1)
    course.quiz_minutes = int(payload.get("quiz_minutes") or 5)
    course.updated_at = datetime.now(timezone.utc)


def _append_quest(course: Course, body: dict, position: int) -> Quest:
    quest = Quest(
        code=body["code"],
        title=body["title"],
        quest_type=body["quest_type"],
        prerequisite_codes=body["prerequisite_codes"],
        competency_tags=body["competency_tags"],
        dinner_prompt=body["dinner_prompt"],
        learning_goal=body["learning_goal"],
        success_criterion=body["success_criterion"],
        requires_teach_back=body["requires_teach_back"],
        position=position,
    )
    course.quests.append(quest)
    for beat_position, beat_body in enumerate(body["beats"], start=1):
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
    for goal in body["goals"]:
        quest.goals.append(
            QuestGoal(
                position=goal["position"],
                learning_goal=goal["learning_goal"],
                success_criterion=goal["success_criterion"],
            )
        )
    close = body["close"]
    quest.close = QuestClose(kind=close["kind"], question=close["question"], items=close["items"])
    return quest


def replace_course(db: Session, payload: dict) -> Course:
    """Upload replaces the course with this code. Open classes on it are cleared."""
    normalized = validate_course(payload)
    existing = db.scalar(
        select(Course)
        .where(Course.code == normalized["code"])
        .options(selectinload(Course.quests))
    )
    incoming = [quest["code"] for quest in normalized["quests"]]
    if existing is None:
        if incoming:
            taken = db.scalar(select(Quest.id).where(Quest.code.in_(incoming)))
            if taken is not None:
                raise CourseFileError("quests", "a quest code is already used by another course")
        course = Course(
            code=normalized["code"],
            title=normalized["title"],
            age_band=normalized["age_band"],
            audience=normalized["audience"],
        )
        db.add(course)
        db.flush()
        _apply_course_fields(course, normalized)
        for position, quest_body in enumerate(normalized["quests"], start=1):
            _append_quest(course, quest_body, position)
        db.flush()
        return course
    quest_ids = [quest.id for quest in existing.quests]
    if quest_ids:
        db.execute(delete(TutorSession).where(TutorSession.quest_id.in_(quest_ids)))
        db.flush()
    for quest in list(existing.quests):
        db.delete(quest)
    db.flush()
    if incoming:
        clash = db.scalar(select(Quest.id).where(Quest.code.in_(incoming)))
        if clash is not None:
            raise CourseFileError("quests", "a quest code is already used by another course")
    _apply_course_fields(existing, normalized)
    for position, quest_body in enumerate(normalized["quests"], start=1):
        _append_quest(existing, quest_body, position)
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


def _sync_goals(quest: Quest, goals: list[dict]) -> None:
    session = object_session(quest)
    for goal in list(quest.goals):
        quest.goals.remove(goal)
    if session is not None:
        session.flush()
    for goal in goals:
        quest.goals.append(
            QuestGoal(
                position=goal["position"],
                learning_goal=goal["learning_goal"],
                success_criterion=goal["success_criterion"],
            )
        )


def _sync_close(quest: Quest, close: dict) -> None:
    row = quest.close
    if row is None:
        quest.close = QuestClose(kind=close["kind"], question=close["question"], items=close["items"])
        return
    row.kind = close["kind"]
    row.question = close["question"]
    row.items = list(close["items"])


def update_course_in_place(db: Session, payload: dict) -> Course:
    """Refresh one course without deleting classes.

    Quests match by code and moves match by position. Columns, goals, and the
    close are updated on those rows. A quest that still has a class is not dropped.
    """
    normalized = validate_course(payload)
    course = db.scalar(
        select(Course)
        .where(Course.code == normalized["code"])
        .options(
            selectinload(Course.quests).selectinload(Quest.beats),
            selectinload(Course.quests).selectinload(Quest.goals),
            selectinload(Course.quests).selectinload(Quest.close),
        )
    )
    if course is None:
        raise CourseFileError("code", "is not in the database")

    incoming_codes = [quest["code"] for quest in normalized["quests"]]
    incoming_code_set = set(incoming_codes)
    quests_by_code = {quest.code: quest for quest in course.quests}
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

    for quest_body in normalized["quests"]:
        quest = quests_by_code.get(quest_body["code"])
        if quest is None:
            continue
        incoming_positions = set(range(1, len(quest_body["beats"]) + 1))
        extra_ids = [beat.id for beat in quest.beats if beat.position not in incoming_positions]
        if _beats_held(db, extra_ids):
            raise CourseFileError("beats", "a move still has classes, so it cannot be removed")

    _apply_course_fields(course, normalized)
    for quest in list(course.quests):
        if quest.code not in incoming_code_set:
            course.quests.remove(quest)
    db.flush()

    live = [quests_by_code[code] for code in incoming_codes if code in quests_by_code]
    for offset, quest in enumerate(live, start=1):
        quest.position = 10_000 + offset
    db.flush()

    for position, quest_body in enumerate(normalized["quests"], start=1):
        quest = quests_by_code.get(quest_body["code"])
        if quest is None:
            clash = db.scalar(select(Quest.id).where(Quest.code == quest_body["code"]))
            if clash is not None:
                raise CourseFileError("quests", "a quest code is already used by another course")
            quest = _append_quest(course, quest_body, position)
            quests_by_code[quest.code] = quest
            continue
        quest.position = position
        _fill_quest(quest, quest_body)
        _sync_beats(quest, quest_body["beats"])
        _sync_goals(quest, quest_body["goals"])
        _sync_close(quest, quest_body["close"])
    db.flush()
    return course


def _rubric_from_goals(goals: list[dict]) -> list[dict]:
    count = len(goals)
    if count <= 1:
        text = goals[0]["success_criterion"] if goals else "States the idea."
        return [{"id": "goal-1", "text": text, "weight": 100}]
    base = 100 // count
    leftover = 100 - base * count
    rows = []
    for index, goal in enumerate(goals, start=1):
        rows.append(
            {
                "id": f"goal-{index}",
                "text": goal["success_criterion"],
                "weight": base + (leftover if index == 1 else 0),
            }
        )
    return rows


def _widget_from_close(close: dict) -> dict | None:
    if close["kind"] not in {"single", "multi"}:
        return None
    choices = []
    answers = []
    for index, item in enumerate(close["items"], start=1):
        choice_id = f"c{index}"
        choices.append(
            {
                "id": choice_id,
                "text": item["text"],
                "misconception": "" if item.get("correct") else "That choice answers a different question.",
            }
        )
        if item.get("correct"):
            answers.append(choice_id)
    if len(choices) < 2:
        return None
    if not answers:
        answers = [choices[0]["id"]]
    kind = "multi" if close["kind"] == "multi" else "single"
    return {
        "type": kind,
        "prompt": close["question"] or "Choose the best answer.",
        "choices": choices,
        "answer": answers if kind == "multi" else answers[0],
        "explain": False,
        "misconception": "Stay on the question this quest asked.",
    }


def _beats_for_close(goals: list[dict], close: dict) -> list[dict]:
    from app.flow import blank_beats

    beats = blank_beats(_rubric_from_goals(goals))
    widget = _widget_from_close(close)
    for beat in beats:
        if beat["role"] != "show":
            continue
        if close["kind"] == "essay" and close["question"]:
            beat["prompt"] = close["question"]
        elif close["kind"] == "none":
            beat["prompt"] = "There is no closing question. The quest ends when the goals are met."
            beat["widget"] = None
        elif widget is not None:
            beat["widget"] = widget
            beat["prompt"] = close["question"] or beat["prompt"]
    return beats


def _close_from_studio_row(row) -> dict:
    if row is None:
        return {"kind": "none", "question": "", "items": []}
    stored = row.items
    choices: list = []
    questions: list = []
    selection = None
    if isinstance(stored, dict):
        choices = stored.get("choices") if isinstance(stored.get("choices"), list) else []
        questions = stored.get("questions") if isinstance(stored.get("questions"), list) else []
        if stored.get("selection") in {"single", "multi"}:
            selection = stored["selection"]
    elif isinstance(stored, list):
        choices = stored
    question = ""
    if questions and isinstance(questions[0], dict):
        question = str(questions[0].get("text") or "").strip()
    answer = row.answer_style
    if answer == "essay" and not question:
        return {"kind": "none", "question": "", "items": []}
    if answer == "essay":
        return {"kind": "essay", "question": question, "items": []}
    items = []
    for choice in choices:
        if isinstance(choice, str) and choice.strip():
            items.append({"text": choice.strip(), "correct": False})
        elif isinstance(choice, dict) and str(choice.get("text") or "").strip():
            items.append({"text": str(choice["text"]).strip(), "correct": choice.get("correct") is True})
    if len(items) < 2:
        if question:
            return {"kind": "essay", "question": question, "items": []}
        return {"kind": "none", "question": "", "items": []}
    return {
        "kind": "multi" if selection == "multi" else "single",
        "question": question or "Choose the best answer.",
        "items": items,
    }


def catalog_from_studio(studio) -> dict:
    """Copy a Create course draft into the kid-catalog shape. The draft stays put."""
    from app.studio import goal_rows, goals_per_quest_of, quest_count_of

    audience = studio.audience if studio.audience in AGE_BANDS else "9-11"
    description = (studio.theme or studio.focus or "").strip()
    standards = (studio.focus or description or studio.title or "").strip() or studio.title
    quests = []
    for source in sorted(studio.quests, key=lambda item: (item.position, item.code)):
        rows = goal_rows(source)
        if not rows:
            rows = [{"learning_goal": source.title, "success_criterion": source.title}]
        goals = []
        for index, row in enumerate(rows, start=1):
            learning_goal = str(row.get("learning_goal") or "").strip() or source.title
            criterion = str(row.get("success_criterion") or "").strip() or learning_goal
            goals.append(
                {"position": index, "learning_goal": learning_goal, "success_criterion": criterion}
            )
        close = _close_from_studio_row(source.close)
        rubric = _rubric_from_goals(goals)
        quests.append(
            {
                "code": source.code,
                "title": source.title,
                "quest_type": "core",
                "prerequisite_codes": [],
                "competency_tags": [],
                "dinner_prompt": source.title,
                "learning_goal": goals[0]["learning_goal"],
                "success_criterion": rubric,
                "requires_teach_back": False,
                "beats": _beats_for_close(goals, close),
                "goals": goals,
                "close": close,
            }
        )
    return {
        "code": studio.code,
        "title": studio.title,
        "age_band": audience,
        "standards_alignment": standards,
        "competency_dictionary": [],
        "description": description,
        "audience": audience,
        "quest_count": quest_count_of(studio),
        "goals_per_quest": goals_per_quest_of(studio),
        "quiz_minutes": studio.quiz_minutes if studio.quiz_minutes in QUIZ_MINUTES else 5,
        "quests": quests,
    }


def copy_studio_into_catalog(db: Session, studio_id) -> Course:
    from app.studio import load_course as load_studio

    studio = load_studio(db, studio_id)
    if studio is None:
        raise CourseFileError("studio_course_id", "is not a Create course draft")
    payload = catalog_from_studio(studio)
    existing = db.scalar(select(Course.id).where(Course.code == payload["code"]))
    if existing is None:
        course = replace_course(db, payload)
    else:
        course = update_course_in_place(db, payload)
    course.in_catalog = True
    course.updated_at = datetime.now(timezone.utc)
    db.flush()
    return course
