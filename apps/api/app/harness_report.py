"""Roll-ups, findings, and before-versus-after for harness runs."""

from __future__ import annotations

import re
from collections import defaultdict

from app.harness_checks import SIDE_INTENTS, WRONG_INTENTS, graded_step, line_matches_key, loop_accepted, turn_place

RUBRIC_VERSION = "2"
CLEAR_DELTA = 0.3
JUDGE_DIMENSIONS = (
    "teaching_quality",
    "correctness",
    "engagement",
    "side_remarks",
    "age_fit",
    "pacing",
    "feedback",
    "scoring_fairness",
    "emotional_attunement",
    "safety",
    "getting_stuck",
    "natural_conversation",
    "closing",
    "child_realism",
)
JUDGE_TAGS = (
    "ignored_question",
    "too_long",
    "vocabulary_too_hard",
    "repeated_itself",
    "gave_away_answer",
    "generic_praise",
    "missed_boredom",
    "missed_frustration",
    "abrupt_return",
    "talked_down",
    "factual_error",
)

BLOCK_LABELS = {
    "topic_goal": "Topic / Goal",
    "mcq": "Multiple Choice Question",
    "case_study": "Case Study / Contrasting Cases",
    "socratic": "Socratic Discussion",
    "curiosity": "Curiosity / Wonder Hook",
    "worked_example": "Worked Example + Faded Step",
    "spot_the_flaw": "Spot the Flaw / Buggy Rule",
    "teach_back": "Teach-Back / Feynman",
    "retrieval_check": "Retrieval & Elaborative Interrogation",
    "explanation": "Explanatory Walkthrough",
    "passage_ela": "ELA Reading Passage",
}


def stuck_nudge_rows(turns: list[dict]) -> list[dict]:
    """Closing nudges that stayed on the same block and substep."""
    if not turns:
        return []
    last = turns[-1]
    last_place = (str(last.get("block_id") or ""), str(last.get("substep") or ""))
    chosen: list[dict] = []
    for turn in reversed(turns):
        if not isinstance(turn, dict):
            break
        place = (str(turn.get("block_id") or ""), str(turn.get("substep") or ""))
        if str(turn.get("intent") or "") != "nudge" or place != last_place:
            break
        chosen.append(turn)
    rows = []
    for turn in reversed(chosen):
        rows.append(
            {
                "turn": int(turn.get("turn") or turn.get("seq") or 0),
                "asked": str(turn.get("child_text") or turn.get("asked") or ""),
                "answered": str(turn.get("tutor_reply") or turn.get("answered") or ""),
                "block_type": str(turn.get("block_type") or ""),
                "block_id": str(turn.get("block_id") or ""),
                "substep": str(turn.get("substep") or ""),
            }
        )
    return rows


def block_label(value: object) -> str:
    key = str(value or "").strip()
    if not key:
        return ""
    return BLOCK_LABELS.get(key, key.replace("_", " "))


def join_labels(labels: object) -> str:
    clean: list[str] = []
    rows = labels if isinstance(labels, list) else []
    for label in rows:
        text = str(label or "").strip()
        if text and text not in clean:
            clean.append(text)
    if not clean:
        return "an unknown block"
    return ", ".join(clean)


CAUSE_BY_TAG = {
    "too_long": ("setting", "Who you are talking to, response length; explanation_depth"),
    "ignored_question": ("loop", "unanswered_side_turn in kc_loop.py; Stay on course"),
    "gave_away_answer": ("prompt", "What to return; goal_evaluation_strictness"),
    "repeated_itself": ("setting", "Hint ladder in This turn; max_retries_before_reveal"),
    "generic_praise": ("setting", "encouragement_style; How to teach"),
    "missed_boredom": ("prompt", "The mood list has no bored. How to teach."),
    "vocabulary_too_hard": ("setting", "Who you are talking to, reading level"),
    "false_pass": ("loop", "model_accepts_substep; What to return"),
    "stuck": ("prompt", "This turn and How to teach; elaboration is uncapped"),
}


def _num(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


# The cutoff stays at 3. The next judged run should be checked before trusting it.
# One judged child scored 2, and that single score is not a reason to move the bar.
REALISM_BAR = 3
STUCK_SPAN = 8


def _judged(chat: dict) -> bool:
    """A chat the judge scored. A failed call and a missing call are not judged."""
    if str(chat.get("judge_error") or "").strip():
        return False
    if chat.get("child_realism") is None:
        return False
    return bool(chat.get("scores"))


def _usable(chat: dict) -> bool:
    """In the roll-up only when the chat was judged and cleared the realism bar."""
    if not _judged(chat):
        return False
    return int(chat.get("child_realism")) >= REALISM_BAR


def _span_turns(turns: list[dict]) -> list[dict]:
    """The longest run of 8 or more turns in one place. Empty when there is none."""
    last = ""
    run: list[dict] = []
    best: list[dict] = []

    def consider(group: list[dict]) -> None:
        nonlocal best
        if len(group) >= STUCK_SPAN and len(group) > len(best):
            best = list(group)

    for turn in turns:
        if not isinstance(turn, dict):
            continue
        place = turn_place(turn)
        if place == last and run:
            run.append(turn)
        else:
            consider(run)
            run = [turn]
            last = place
    consider(run)
    return best


def chat_is_stuck(chat: dict) -> bool:
    """One definition: 8 or more turns in one place, topic included.

    Stored turns win. A chat with no turns falls back to the stored span count,
    then to the end reason, which uses the same place key.
    """
    turns = _chat_turns(chat)
    if turns:
        return bool(_span_turns(turns))
    checks = chat.get("checks") if isinstance(chat.get("checks"), dict) else {}
    try:
        spans = int(checks.get("stuck_spans") or 0)
    except (TypeError, ValueError):
        spans = 0
    if spans > 0:
        return True
    return str(chat.get("ended_how") or "") == "stuck"


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _group(chats: list[dict], key) -> list[dict]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for chat in chats:
        buckets[str(key(chat) or "—")].append(chat)
    rows = []
    for name, items in sorted(buckets.items(), key=lambda item: item[0]):
        scores = []
        for chat in items:
            for score in chat.get("scores") or []:
                if isinstance(score, dict) and score.get("dimension") != "child_realism":
                    scores.append(_num(score.get("score")))
        completed = sum(1 for chat in items if chat.get("ended_how") == "completed")
        false_passes = sum(len((chat.get("checks") or {}).get("false_passes") or []) for chat in items)
        stuck = sum(1 for chat in items if chat_is_stuck(chat))
        costs = [chat["cost_usd"] for chat in items if chat.get("cost_usd")]
        rows.append(
            {
                "name": name,
                "chats": len(items),
                "completed": completed,
                "completion_rate": round(completed / len(items), 2) if items else 0,
                "mean_score": _mean(scores),
                "false_passes": false_passes,
                "stuck": stuck,
                "priced_chats": len(costs),
            }
        )
    return rows


def rollup(chats: list[dict]) -> dict:
    usable = [chat for chat in chats if _usable(chat)]
    not_judged = sum(1 for chat in chats if not _judged(chat))
    dropped = sum(1 for chat in chats if _judged(chat) and not _usable(chat))
    tags: dict[str, list[dict]] = defaultdict(list)
    for chat in usable:
        for tag in chat.get("tags") or []:
            if not isinstance(tag, dict):
                continue
            name = str(tag.get("tag") or "")
            if not name:
                continue
            named = (chat.get("tag_blocks") or {}).get(name) if isinstance(chat.get("tag_blocks"), dict) else ""
            if not named:
                named = ((chat.get("turn_blocks") or [None])[0]) or ((chat.get("block_types") or [""])[0])
            tags[name].append(
                {
                    "chat_id": chat.get("id"),
                    "turn": tag.get("turn"),
                    "child": chat.get("persona_name"),
                    "block": block_label(named) or "an unknown block",
                }
            )
    top = []
    for name, examples in sorted(tags.items(), key=lambda item: (-len(item[1]), item[0])):
        top.append({"tag": name, "count": len(examples), "examples": examples[:3]})
    by_block: dict[str, list[dict]] = defaultdict(list)
    for chat in usable:
        for block in chat.get("block_types") or ["—"]:
            by_block[str(block)].append(chat)
    instructions: dict[str, dict] = defaultdict(lambda: {"present": 0, "obeyed": 0})
    for chat in usable:
        for key, row in ((chat.get("checks") or {}).get("instructions") or {}).items():
            instructions[key]["present"] += int(row.get("present") or 0)
            instructions[key]["obeyed"] += int(row.get("obeyed") or 0)
    instruction_rows = []
    for key, row in sorted(instructions.items()):
        present = row["present"]
        instruction_rows.append(
            {
                "id": key,
                "present": present,
                "obeyed": row["obeyed"],
                "rate": round(row["obeyed"] / present, 2) if present else None,
            }
        )
    false_blocks: dict[str, list[str]] = defaultdict(list)
    stuck_blocks: dict[str, list[str]] = defaultdict(list)
    instruction_blocks: dict[str, list[str]] = defaultdict(list)
    for chat in usable:
        child = str(chat.get("persona_name") or "")
        for label in chat.get("false_pass_blocks") or []:
            if label not in false_blocks[child]:
                false_blocks[child].append(str(label))
        for label in chat.get("stuck_blocks") or []:
            if label not in stuck_blocks[child]:
                stuck_blocks[child].append(str(label))
        visited = [str(label) for label in (chat.get("turn_blocks") or []) if label]
        for key, row in ((chat.get("checks") or {}).get("instructions") or {}).items():
            if not isinstance(row, dict):
                continue
            present = int(row.get("present") or 0)
            obeyed = int(row.get("obeyed") or 0)
            if present and obeyed < present:
                for label in visited:
                    if label not in instruction_blocks[str(key)]:
                        instruction_blocks[str(key)].append(label)
    return {
        "chats": len(chats),
        "usable_chats": len(usable),
        "not_judged": not_judged,
        "low_realism_left_out": dropped,
        "by_child": _group(usable, lambda chat: chat.get("persona_name")),
        "by_course": _group(usable, lambda chat: chat.get("course_title")),
        "by_component": _group(usable, lambda chat: chat.get("component_title")),
        "by_model": _group(usable, lambda chat: chat.get("tutor_model")),
        "by_profile": _group(usable, lambda chat: chat.get("profile_name")),
        "by_block_type": _group(
            [dict(chat, persona_name=block) for chat in usable for block in (chat.get("block_types") or ["—"])],
            lambda chat: chat.get("persona_name"),
        ),
        "by_intent": _intent_rows(usable),
        "instructions": instruction_rows,
        "top_problems": top,
        "stuck_nudges": _stuck_nudges(usable),
        "issue_blocks": {
            "false_pass": dict(false_blocks),
            "stuck": dict(stuck_blocks),
            "instructions": dict(instruction_blocks),
        },
        "grid": _grid(usable),
        "worst": sorted(usable, key=_worst_key)[:8],
    }


def _stuck_nudges(chats: list[dict]) -> list[dict]:
    rows = []
    for chat in chats:
        if str(chat.get("ended_how") or "") != "stuck":
            continue
        for nudge in chat.get("stuck_nudges") or []:
            if not isinstance(nudge, dict):
                continue
            rows.append(
                {
                    **nudge,
                    "child": str(chat.get("persona_name") or ""),
                    "chat_id": str(chat.get("id") or ""),
                }
            )
    return rows


def _with_stuck_nudges(found: list[dict], report: dict) -> list[dict]:
    nudges = report.get("stuck_nudges") if isinstance(report.get("stuck_nudges"), list) else []
    if not nudges:
        return found
    attached = []
    for item in found:
        if str(item.get("tag") or "") != "stuck":
            attached.append(item)
            continue
        who = str(item.get("who") or "")
        chosen = [
            row
            for row in nudges
            if isinstance(row, dict) and (not who or str(row.get("child") or "") == who)
        ]
        if not chosen:
            chosen = [row for row in nudges if isinstance(row, dict)]
        attached.append({**item, "nudges": chosen})
    return attached


def _intent_rows(chats: list[dict]) -> list[dict]:
    counts: dict[str, int] = defaultdict(int)
    misses: dict[str, int] = defaultdict(int)
    for chat in chats:
        for turn in chat.get("turn_intents") or []:
            intent = str(turn or "")
            if not intent:
                continue
            counts[intent] += 1
        for index in (chat.get("checks") or {}).get("false_passes") or []:
            intents = chat.get("turn_intents") or []
            if 0 <= int(index) < len(intents):
                misses[str(intents[int(index)])] += 1
    return [
        {"intent": name, "turns": count, "false_passes": misses.get(name, 0)}
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _grid(chats: list[dict]) -> list[dict]:
    cells: dict[tuple[str, str], list[float]] = defaultdict(list)
    for chat in chats:
        child = str(chat.get("persona_name") or "—")
        score = _mean([_num(item.get("score")) for item in chat.get("scores") or [] if isinstance(item, dict)])
        if score is None:
            continue
        for block in chat.get("block_types") or ["—"]:
            cells[(child, str(block))].append(score)
    return [
        {"child": child, "block": block, "score": _mean(values)}
        for (child, block), values in sorted(cells.items())
    ]


def _worst_key(chat: dict) -> tuple:
    checks = chat.get("checks") or {}
    score = _mean([_num(item.get("score")) for item in chat.get("scores") or [] if isinstance(item, dict)]) or 5
    problems = len(checks.get("false_passes") or []) + len(checks.get("errors") or []) + int(checks.get("stuck_spans") or 0)
    return (-problems, score)


def _finding(title: str, labels: object, **rest: object) -> dict:
    named = join_labels(labels)
    return {"title": f"{title} on {named}", "block_label": named, **rest}


def findings(report: dict) -> list[dict]:
    """Numbers first. Each finding names a cause class, the block type, and a place to change."""
    found = []
    issues = report.get("issue_blocks") if isinstance(report.get("issue_blocks"), dict) else {}
    false_map = issues.get("false_pass") if isinstance(issues.get("false_pass"), dict) else {}
    stuck_map = issues.get("stuck") if isinstance(issues.get("stuck"), dict) else {}
    instruction_map = issues.get("instructions") if isinstance(issues.get("instructions"), dict) else {}
    for row in report.get("by_child") or []:
        if row["chats"] and row["false_passes"]:
            found.append(
                _finding(
                    f"False passes for {row['name']}",
                    false_map.get(row["name"]),
                    tag="false_pass",
                    count=row["false_passes"],
                    who=row["name"],
                    cause_class="loop",
                    place=CAUSE_BY_TAG["false_pass"][1],
                )
            )
        if row["stuck"]:
            found.append(
                _finding(
                    f"{row['name']} got stuck",
                    stuck_map.get(row["name"]),
                    tag="stuck",
                    count=row["stuck"],
                    who=row["name"],
                    cause_class="prompt",
                    place=CAUSE_BY_TAG["stuck"][1],
                )
            )
    for row in report.get("instructions") or []:
        if row["present"] and row["rate"] is not None and row["rate"] < 0.8:
            found.append(
                _finding(
                    f"The model ignored {row['id'].replace('_', ' ')}",
                    instruction_map.get(row["id"]),
                    tag=row["id"],
                    count=row["present"] - row["obeyed"],
                    who="",
                    cause_class="prompt",
                    place=f"The stored prompt already contains {row['id']}. Shorten or move that line before adding another.",
                )
            )
        if row["present"] == 0 and row["id"] in {"stay_on_course", "one_question"}:
            found.append(
                _finding(
                    f"{row['id'].replace('_', ' ')} was not in the prompt",
                    instruction_map.get(row["id"]),
                    tag=row["id"],
                    count=0,
                    who="",
                    cause_class="prompt",
                    place="The section builder in kc_prompt.py never wrote this instruction.",
                )
            )
    for problem in report.get("top_problems") or []:
        tag = problem["tag"]
        if tag not in CAUSE_BY_TAG:
            continue
        cause, place = CAUSE_BY_TAG[tag]
        labels = [example.get("block") for example in (problem.get("examples") or []) if isinstance(example, dict)]
        found.append(
            _finding(
                tag.replace("_", " "),
                labels,
                tag=tag,
                count=problem["count"],
                who="",
                cause_class=cause,
                place=place,
                examples=problem.get("examples") or [],
            )
        )
    return _with_stuck_nudges(found, report)


def _match_key(chat: dict) -> tuple:
    return (
        str(chat.get("persona_name") or ""),
        str(chat.get("component_id") or chat.get("component_title") or ""),
        str(chat.get("tutor_model") or ""),
        int(chat.get("seed") or 0),
        int(chat.get("iteration") or 1),
    )


def _chat_score(chat: dict) -> float | None:
    return _mean(
        [
            _num(item.get("score"))
            for item in chat.get("scores") or []
            if isinstance(item, dict) and item.get("dimension") != "child_realism"
        ]
    )


def _dimension_scores(chat: dict) -> dict[str, float]:
    """Tutor dimensions for one usable chat. Low child realism stays out of the roll-up."""
    if not _usable(chat):
        return {}
    found: dict[str, float] = {}
    for item in chat.get("scores") or []:
        if not isinstance(item, dict):
            continue
        dimension = str(item.get("dimension") or "")
        if not dimension or dimension == "child_realism":
            continue
        found[dimension] = _num(item.get("score"))
    return found


def _check_count(chat: dict, key: str) -> int:
    checks = chat.get("checks") if isinstance(chat.get("checks"), dict) else {}
    rows = checks.get(key) or []
    return len(rows) if isinstance(rows, list) else 0


def compare_runs(left: list[dict], right: list[dict]) -> dict:
    """Match chats. A small gap on a few chats is no clear difference.

    A new stuck chat, false pass, or empty reply is a failure even when the mean rises.
    """
    right_by = {_match_key(chat): chat for chat in right}
    matched = []
    flips_good = []
    flips_bad = []
    new_hard = []
    new_false = []
    new_empty = []
    dim_pairs: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for chat in left:
        other = right_by.get(_match_key(chat))
        if other is None:
            continue
        before = _chat_score(chat)
        after = _chat_score(other)
        left_checks = chat.get("checks") or {}
        right_checks = other.get("checks") or {}
        row = {
            "child": chat.get("persona_name"),
            "component": chat.get("component_title"),
            "model": chat.get("tutor_model"),
            "seed": chat.get("seed"),
            "score_before": before,
            "score_after": after,
            "false_passes_before": len(left_checks.get("false_passes") or []),
            "false_passes_after": len(right_checks.get("false_passes") or []),
            "cost_before": chat.get("cost_usd"),
            "cost_after": other.get("cost_usd"),
        }
        matched.append(row)
        ended_before = chat.get("ended_how")
        ended_after = other.get("ended_how")
        if ended_before != "completed" and ended_after == "completed":
            flips_good.append(row)
        if ended_before == "completed" and ended_after != "completed":
            flips_bad.append(row)
        for kind in ("safety", "stuck", "route_error"):
            before_hit = _hard(chat, kind)
            after_hit = _hard(other, kind)
            if after_hit and not before_hit:
                new_hard.append({"kind": kind, "child": chat.get("persona_name"), "chat_id": other.get("id")})
        if _check_count(other, "false_passes") > _check_count(chat, "false_passes"):
            new_false.append({"child": chat.get("persona_name"), "chat_id": other.get("id")})
        if _check_count(other, "empty_replies") > _check_count(chat, "empty_replies"):
            new_empty.append({"child": chat.get("persona_name"), "chat_id": other.get("id")})
        left_dims = _dimension_scores(chat)
        right_dims = _dimension_scores(other)
        for dimension in JUDGE_DIMENSIONS:
            if dimension == "child_realism":
                continue
            if dimension in left_dims and dimension in right_dims:
                dim_pairs[dimension].append((left_dims[dimension], right_dims[dimension]))
    deltas = [
        (row["score_after"] - row["score_before"])
        for row in matched
        if row["score_before"] is not None and row["score_after"] is not None
    ]
    mean_delta = _mean(deltas)
    dimension_deltas = []
    for dimension in JUDGE_DIMENSIONS:
        if dimension == "child_realism" or dimension not in dim_pairs:
            continue
        pairs = dim_pairs[dimension]
        before_mean = _mean([item[0] for item in pairs])
        after_mean = _mean([item[1] for item in pairs])
        delta = None if before_mean is None or after_mean is None else round(after_mean - before_mean, 2)
        dimension_deltas.append(
            {
                "dimension": dimension,
                "before": before_mean,
                "after": after_mean,
                "delta": delta,
                "clear": delta is not None and abs(delta) >= CLEAR_DELTA,
            }
        )
    verdict = "no clear difference"
    if new_hard or new_false or new_empty:
        verdict = "worse"
    elif mean_delta is None or len(matched) < 3 or abs(mean_delta) < CLEAR_DELTA:
        verdict = "no clear difference"
    elif mean_delta > 0 and len(flips_bad) <= len(flips_good):
        verdict = "better"
    elif mean_delta < 0:
        verdict = "worse"
    return {
        "matched": len(matched),
        "mean_score_delta": mean_delta,
        "dimension_deltas": dimension_deltas,
        "flipped_to_completed": flips_good,
        "flipped_to_incomplete": flips_bad,
        "new_hard_stops": new_hard,
        "new_false_passes": new_false,
        "new_empty_replies": new_empty,
        "rows": matched,
        "verdict": verdict,
    }


def _hard(chat: dict, kind: str) -> bool:
    checks = chat.get("checks") or {}
    if kind == "safety":
        return bool(checks.get("safety_flags"))
    if kind == "stuck":
        return chat.get("ended_how") == "stuck" or bool(checks.get("stuck_spans"))
    if kind == "route_error":
        return chat.get("ended_how") == "route_error" or bool(checks.get("errors"))
    return False


def kept_run_ids(suites: list[dict]) -> set[str]:
    """Prompts stay for the baseline and the newest run of each suite."""
    kept: set[str] = set()
    for suite in suites:
        baseline = str(suite.get("baseline_run_id") or "")
        if baseline:
            kept.add(baseline)
        run_ids = [str(item) for item in suite.get("run_ids") or [] if item]
        if run_ids:
            kept.add(run_ids[-1])
    return kept


def regression_band(comparison: dict) -> str:
    if comparison.get("new_hard_stops") or comparison.get("new_false_passes") or comparison.get("new_empty_replies"):
        return "red"
    verdict = comparison.get("verdict")
    if verdict == "worse":
        return "red"
    if verdict == "better":
        return "green"
    return "amber"


TONE_DIMENSIONS = (
    ("natural_conversation", "Natural conversation"),
    ("engagement", "Engagement"),
    ("age_fit", "Age fit"),
    ("pacing", "Pacing"),
    ("feedback", "Feedback"),
)

GROUP_LABELS = {
    "wrong_line": "Answered the wrong line",
    "praised_again": "Praised a complete answer and asked again",
    "unchanged_reply": "Stored a reply that did not change",
    "false_pass": "False pass",
    "false_fail": "False fail",
    "stuck": "Stuck",
}
GROUP_ORDER = (
    "wrong_line",
    "praised_again",
    "unchanged_reply",
    "false_pass",
    "false_fail",
    "stuck",
)

_WHATS_NEXT = {
    "what's next",
    "whats next",
    "what is next",
    "what should we do next",
    "what next",
}
_PRAISE = re.compile(
    r"\b(yes|great|nice|good|awesome|excellent|well done|that's right|that is right|that's the chain|that is the chain)\b",
    re.I,
)
_STOPS = {
    "that",
    "this",
    "with",
    "from",
    "have",
    "they",
    "them",
    "what",
    "when",
    "where",
    "your",
    "about",
    "just",
    "like",
    "then",
    "does",
    "did",
    "was",
    "were",
    "been",
    "into",
    "over",
    "more",
    "some",
    "than",
    "their",
    "there",
    "would",
    "could",
    "should",
    "because",
    "while",
    "which",
    "these",
    "those",
    "being",
    "know",
    "dont",
    "don't",
}
_SKIP_PRAISE = SIDE_INTENTS | WRONG_INTENTS | {
    "nudge",
    "quit",
    "move_on",
    "tell_me_more",
    "idk",
    "guess",
    "echo",
    "say_yes",
}


def _chat_turns(chat: dict) -> list[dict]:
    rows = chat.get("report_turns")
    if not isinstance(rows, list) or not rows:
        rows = chat.get("turns")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _turn_block(turn: dict) -> str:
    label = str(turn.get("block_label") or "").strip()
    if label:
        return label
    named = block_label(turn.get("block_type"))
    return named or "an unknown block"


def _ask(text: object) -> str:
    cleaned = re.sub(r"[^a-z'\s]", "", str(text or "").lower())
    return " ".join(cleaned.split())


def leave_out_turn(turn: dict) -> bool:
    """What's next? is not a failure while the goal question is still the open ask."""
    if _ask(turn.get("child_text")) not in _WHATS_NEXT:
        return False
    substep = str(turn.get("substep") or turn.get("substep_before") or "").strip()
    if substep != "main":
        return False
    kind = str(turn.get("block_type") or turn.get("block_label") or "").strip().lower()
    kind = " ".join(re.sub(r"[/_]+", " ", kind).split())
    if not kind:
        return True
    return kind == "topic goal"


def _content_words(text: object) -> set[str]:
    found = set()
    for word in re.findall(r"[a-z']+", str(text or "").lower()):
        if len(word) >= 4 and word not in _STOPS:
            found.add(word)
    return found


def _same_reply(left: object, right: object) -> bool:
    a = " ".join(str(left or "").split())
    b = " ".join(str(right or "").split())
    return bool(a) and a == b


def _stayed(turn: dict) -> bool:
    before_block = str(turn.get("block_before") or "")
    before_sub = str(turn.get("substep_before") or "")
    if before_block and before_block != str(turn.get("block_id") or ""):
        return False
    if before_sub and before_sub != str(turn.get("substep") or ""):
        return False
    return True


def _wrong_line(turn: dict, previous: dict | None) -> bool:
    if previous is None or leave_out_turn(turn):
        return False
    reply_words = _content_words(turn.get("tutor_reply"))
    previous_words = _content_words(previous.get("child_text"))
    current_words = _content_words(turn.get("child_text"))
    if len(current_words) < 2 or not previous_words or not reply_words:
        return False
    if current_words == previous_words:
        return False
    return bool(previous_words & reply_words) and not (current_words & reply_words)


def _praised_again(turn: dict) -> bool:
    if leave_out_turn(turn):
        return False
    intent = str(turn.get("intent") or "")
    if intent in _SKIP_PRAISE:
        return False
    child = str(turn.get("child_text") or "").strip()
    if "?" in child:
        return False
    if intent != "answer_right" and len(child.split()) < 8:
        return False
    reply = str(turn.get("tutor_reply") or "")
    if "?" not in reply or not _PRAISE.search(reply):
        return False
    return _stayed(turn)


def _unchanged_reply(turn: dict, previous: dict | None) -> bool:
    if previous is None or leave_out_turn(turn):
        return False
    reply = str(turn.get("tutor_reply") or "")
    previous_reply = str(previous.get("tutor_reply") or "")
    if _same_reply(reply, previous_reply):
        return True
    return not reply.strip() and bool(previous_reply.strip()) and bool(str(turn.get("error") or "").strip())


def chat_failures(chat: dict) -> dict[str, list[dict]]:
    turns = _chat_turns(chat)
    checks = chat.get("checks") if isinstance(chat.get("checks"), dict) else {}
    found = {key: [] for key in GROUP_ORDER}
    for index, turn in enumerate(turns):
        previous = turns[index - 1] if index else None
        if _wrong_line(turn, previous):
            found["wrong_line"].append(turn)
        if _praised_again(turn):
            found["praised_again"].append(turn)
        if _unchanged_reply(turn, previous):
            found["unchanged_reply"].append(turn)
    if "false_passes" in checks or "false_fails" in checks:
        for index in checks.get("false_passes") or []:
            if isinstance(index, int) and 0 <= index < len(turns) and not leave_out_turn(turns[index]):
                found["false_pass"].append(turns[index])
        for index in checks.get("false_fails") or []:
            if isinstance(index, int) and 0 <= index < len(turns) and not leave_out_turn(turns[index]):
                found["false_fail"].append(turns[index])
    else:
        for turn in turns:
            if leave_out_turn(turn) or not graded_step(turn):
                continue
            matched = line_matches_key(str(turn.get("child_text") or ""), str(turn.get("expected") or ""))
            accepted = loop_accepted(turn)
            if not matched and accepted:
                found["false_pass"].append(turn)
            if matched and not accepted:
                found["false_fail"].append(turn)
    span = _span_turns(turns)
    if span:
        example = next((turn for turn in span if not leave_out_turn(turn)), span[0])
        found["stuck"].append(example)
    return found


def failure_groups(chats: list[dict]) -> list[dict]:
    buckets: dict[tuple[str, str], dict] = {}
    for chat in chats:
        for key, turns in chat_failures(chat).items():
            seen: set[str] = set()
            for turn in turns:
                block = _stuck_block(turn) if key == "stuck" else _turn_block(turn)
                if block in seen:
                    continue
                seen.add(block)
                slot = buckets.setdefault((key, block), {"count": 0, "turn": turn})
                slot["count"] += 1
    rows = []
    for (key, block), slot in buckets.items():
        turn = slot["turn"]
        rows.append(
            {
                "id": key,
                "label": GROUP_LABELS[key],
                "count": slot["count"],
                "block_type": block,
                "child": str(turn.get("child_text") or ""),
                "tutor": str(turn.get("tutor_reply") or ""),
            }
        )
    order = {name: index for index, name in enumerate(GROUP_ORDER)}
    rows.sort(key=lambda row: (order[row["id"]], row["block_type"]))
    return rows


def tone_rows(chats: list[dict]) -> list[dict]:
    usable = [chat for chat in chats if _usable(chat)]
    rows = []
    for key, label in TONE_DIMENSIONS:
        scored = []
        for chat in usable:
            for item in chat.get("scores") or []:
                if isinstance(item, dict) and str(item.get("dimension") or "") == key:
                    scored.append((chat, _num(item.get("score"))))
                    break
        lowest = sorted(
            scored,
            key=lambda pair: (pair[1], str(pair[0].get("persona_name") or ""), str(pair[0].get("id") or "")),
        )[:3]
        rows.append(
            {
                "dimension": key,
                "label": label,
                "mean": _mean([score for _, score in scored]),
                "lowest": [
                    {"chat_id": chat.get("id"), "child": str(chat.get("persona_name") or ""), "score": score}
                    for chat, score in lowest
                ],
            }
        )
    return rows


def _stuck_block(turn: dict) -> str:
    block = _turn_block(turn)
    if str(turn.get("substep") or "") != "explain_topic" or "topic_index" not in turn:
        return block
    topic = turn.get("topic_index")
    if topic is None or topic == "":
        return block
    try:
        number = int(topic) + 1
    except (TypeError, ValueError):
        return block
    return f"{block}, topic {number}"


def _tone_value(row: dict, chats: list[dict]) -> str:
    """A number when the roll-up has scores. Otherwise not judged, or withheld.

    A blank mean is not a withheld score. Withheld is only when every chat was
    judged and none of them cleared the realism bar.
    """
    if row.get("mean") is not None:
        return str(row["mean"])
    judged = [chat for chat in chats if _judged(chat)]
    if judged and len(judged) == len(chats):
        return "withheld"
    return "not judged"


def _outcome_bits(outcomes: object) -> str:
    bits = []
    for item in outcomes if isinstance(outcomes, list) else []:
        if isinstance(item, dict):
            title = str(item.get("title") or "block").strip() or "block"
            outcome = str(item.get("outcome") or "").strip()
            bits.append(f"{title} ({outcome})" if outcome else title)
        elif str(item).strip():
            bits.append(str(item).strip())
    return ", ".join(bits)


def _score_lines(chats: list[dict]) -> list[str]:
    lines = []
    for chat in chats:
        outcomes = chat.get("block_outcomes") or []
        if "component_score" not in chat and not outcomes:
            continue
        score = chat.get("component_score") if "component_score" in chat else None
        shown = "not finished" if score is None else str(score)
        beside = _outcome_bits(outcomes) or "no block outcomes"
        name = str(chat.get("persona_name") or "Chat")
        lines.append(f"{name}: {shown}. {beside}.")
    return lines


def _shown_score(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return str(value)


def _summary_text(
    chats: int,
    completed: int,
    stuck: int,
    ended_stuck: int,
    models: list[str],
    groups: list[dict],
    tone: list[dict],
    source: list[dict],
) -> str:
    tutors = ", ".join(models) if models else "none"
    lines = [
        f"Run: {chats} chats, {completed} completed, {stuck} stuck (8 or more turns in one place). Tutors: {tutors}.",
        "",
    ]
    if ended_stuck != stuck:
        lines.insert(1, f"{ended_stuck} ended as stuck.")
    if not groups:
        lines.append("Automatic checks: none of these failures.")
        lines.append("")
    for group in groups:
        noun = "chat" if group["count"] == 1 else "chats"
        lines.append(f"{group['label']} — {group['count']} {noun} — {group['block_type']}")
        lines.append(f"Child: {group['child']}")
        lines.append(f"Tutor: {group['tutor']}")
        lines.append("")
    lines.append("Tone")
    for row in tone:
        mean = _tone_value(row, source)
        lowest = ", ".join(f"{item['child']} {_shown_score(item['score'])}" for item in row["lowest"]) or "none"
        lines.append(f"{row['label']}: mean {mean}. Lowest: {lowest}.")
    scores = _score_lines(source)
    if scores:
        lines.append("")
        lines.append("Scores")
        lines.extend(scores)
    return "\n".join(lines).strip()


def run_summary(chats: list[dict]) -> dict:
    """A short, copyable account of how the run ended and which checks failed."""
    models = sorted({str(chat.get("tutor_model") or "") for chat in chats if str(chat.get("tutor_model") or "").strip()})
    completed = sum(1 for chat in chats if chat.get("ended_how") == "completed")
    stuck = sum(1 for chat in chats if chat_is_stuck(chat))
    ended_stuck = sum(1 for chat in chats if str(chat.get("ended_how") or "") == "stuck")
    groups = failure_groups(chats)
    tone = tone_rows(chats)
    block_scores = []
    for chat in chats:
        outcomes = chat.get("block_outcomes") or []
        if "component_score" not in chat and not outcomes:
            continue
        block_scores.append(
            {
                "chat_id": chat.get("id"),
                "child": str(chat.get("persona_name") or ""),
                "score": chat.get("component_score") if "component_score" in chat else None,
                "outcomes": _outcome_bits(outcomes),
            }
        )
    return {
        "chats": len(chats),
        "completed": completed,
        "stuck": stuck,
        "ended_stuck": ended_stuck,
        "tutor_models": models,
        "groups": groups,
        "tone": tone,
        "block_scores": block_scores,
        "text": _summary_text(len(chats), completed, stuck, ended_stuck, models, groups, tone, chats),
    }
