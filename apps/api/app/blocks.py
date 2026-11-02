"""Normalize rubric rows, hint ladders, and choice widgets."""

from __future__ import annotations

from fastapi import HTTPException

QUIZ_TYPES = {"single", "multi", "flaw", "order"}
LIST_ANSWER = {"multi", "order"}


def _clean_id(value: str, fallback: str) -> str:
    cleaned = "".join(ch for ch in value.strip().lower() if ch.isalnum() or ch in "-_")
    return cleaned[:40] or fallback


def normalize_rows(rows: list) -> list[dict]:
    cleaned: list[dict] = []
    seen: set[str] = set()
    for index, row in enumerate(rows, start=1):
        text = (getattr(row, "text", None) or row.get("text", "") if isinstance(row, dict) else row.text).strip()
        if not text:
            continue
        raw_id = getattr(row, "id", None) if not isinstance(row, dict) else row.get("id", "")
        weight = getattr(row, "weight", None) if not isinstance(row, dict) else row.get("weight", 1)
        row_id = _clean_id(str(raw_id or ""), f"r{index}")
        while row_id in seen:
            row_id = f"{row_id}-{index}"
        seen.add(row_id)
        try:
            weight_int = int(weight)
        except (TypeError, ValueError):
            weight_int = 1
        cleaned.append({"id": row_id, "text": text, "weight": max(0, min(weight_int, 100))})
    return cleaned


def normalize_hints(hints) -> dict:
    source = hints if isinstance(hints, dict) else {
        "nudge": getattr(hints, "nudge", ""),
        "analogy": getattr(hints, "analogy", ""),
        "scaffold": getattr(hints, "scaffold", ""),
    }
    return {
        "nudge": str(source.get("nudge") or "").strip(),
        "analogy": str(source.get("analogy") or "").strip(),
        "scaffold": str(source.get("scaffold") or "").strip(),
    }


def normalize_quiz(quiz) -> dict | None:
    if quiz is None:
        return None
    qtype = quiz.type if not isinstance(quiz, dict) else quiz.get("type")
    if qtype not in QUIZ_TYPES:
        raise HTTPException(status_code=400, detail="Quiz type must be single, multi, flaw, or order.")
    raw_choices = quiz.choices if not isinstance(quiz, dict) else quiz.get("choices") or []
    choices: list[dict] = []
    seen: set[str] = set()
    for index, choice in enumerate(raw_choices, start=1):
        text = (choice.text if not isinstance(choice, dict) else choice.get("text") or "").strip()
        if not text:
            continue
        raw_id = choice.id if not isinstance(choice, dict) else choice.get("id") or ""
        misconception = choice.misconception if not isinstance(choice, dict) else choice.get("misconception") or ""
        choice_id = _clean_id(str(raw_id or ""), chr(ord("a") + index - 1))
        while choice_id in seen:
            choice_id = f"{choice_id}{index}"
        seen.add(choice_id)
        choices.append(
            {
                "id": choice_id,
                "text": text,
                "misconception": str(misconception or "").strip(),
            }
        )
    if len(choices) < 2:
        raise HTTPException(status_code=400, detail="A choice widget needs at least two choices.")
    raw_answer = quiz.answer if not isinstance(quiz, dict) else quiz.get("answer")
    if qtype in LIST_ANSWER:
        if isinstance(raw_answer, str):
            answer = [part.strip() for part in raw_answer.split(",") if part.strip()]
        else:
            answer = [str(part).strip() for part in (raw_answer or []) if str(part).strip()]
        unknown = [part for part in answer if part not in seen]
        if unknown or len(answer) != len(set(answer)):
            raise HTTPException(status_code=400, detail="The answer must be ids of the choices.")
        if qtype == "order" and len(answer) != len(choices):
            raise HTTPException(status_code=400, detail="An ordering answer lists every choice once.")
        if qtype == "multi" and not answer:
            raise HTTPException(status_code=400, detail="A multi-select answer needs at least one choice.")
    else:
        answer = str(raw_answer or "").strip()
        if answer not in seen:
            raise HTTPException(status_code=400, detail="The answer must be the id of one choice.")
    prompt = (quiz.prompt if not isinstance(quiz, dict) else quiz.get("prompt") or "").strip()
    explain = bool(quiz.explain if not isinstance(quiz, dict) else quiz.get("explain"))
    level = quiz.misconception if not isinstance(quiz, dict) else quiz.get("misconception") or ""
    return {
        "type": qtype,
        "prompt": prompt,
        "choices": choices,
        "answer": answer,
        "explain": explain,
        "misconception": str(level or "").strip(),
    }


