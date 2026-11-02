"""Grade a choice widget. The model never scores these taps."""

from __future__ import annotations

HINT_TIERS = ("nudge", "analogy", "scaffold")


def hint_tier_for(failed_attempts: int) -> str:
    if failed_attempts <= 0:
        return "nudge"
    if failed_attempts == 1:
        return "analogy"
    return "scaffold"


def hint_text(ladder: dict | None, tier: str) -> str:
    if not isinstance(ladder, dict):
        return ""
    return str(ladder.get(tier) or "").strip()


def choice_ids(choice: str | list[str]) -> list[str]:
    if isinstance(choice, str):
        text = choice.strip()
        return [text] if text else []
    return [str(item).strip() for item in choice if str(item).strip()]


def grade_choice(quiz: dict, choice: str | list[str]) -> dict:
    """Return correct, score, misconception. Score is 100 or 0."""
    qtype = quiz.get("type")
    expected = quiz.get("answer")
    picked = choice_ids(choice)
    by_id = {
        str(item.get("id")): item
        for item in (quiz.get("choices") or [])
        if isinstance(item, dict)
    }
    known = set(by_id)
    if not picked or any(item not in known for item in picked):
        return {
            "correct": False,
            "score": 0,
            "misconception": str(quiz.get("misconception") or "").strip() or None,
        }
    if qtype in {"single", "flaw"}:
        correct = len(picked) == 1 and picked[0] == expected
        if correct:
            return {"correct": True, "score": 100, "misconception": None}
        item = by_id.get(picked[0], {})
        note = str(item.get("misconception") or quiz.get("misconception") or "").strip()
        return {"correct": False, "score": 0, "misconception": note or None}
    if qtype == "multi":
        expected_ids = set(expected if isinstance(expected, list) else [expected])
        correct = set(picked) == expected_ids
    elif qtype == "order":
        expected_ids = list(expected if isinstance(expected, list) else [expected])
        correct = picked == expected_ids
    else:
        correct = False
    if correct:
        return {"correct": True, "score": 100, "misconception": None}
    note = str(quiz.get("misconception") or "").strip()
    return {"correct": False, "score": 0, "misconception": note or None}


def public_quiz(quiz: dict | None) -> dict | None:
    """Kid-facing widget. Answers and stored misconceptions stay on the server."""
    if not isinstance(quiz, dict) or quiz.get("type") not in {"single", "multi", "flaw", "order"}:
        return None
    choices = []
    for item in quiz.get("choices") or []:
        if not isinstance(item, dict):
            continue
        choices.append({"id": str(item.get("id")), "text": str(item.get("text") or "")})
    if len(choices) < 2:
        return None
    return {
        "type": quiz["type"],
        "prompt": str(quiz.get("prompt") or ""),
        "choices": choices,
        "explain": bool(quiz.get("explain")),
    }
