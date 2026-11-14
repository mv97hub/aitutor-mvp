"""Roll-ups, findings, and before-versus-after for harness runs."""

from __future__ import annotations

from collections import defaultdict

RUBRIC_VERSION = "1"
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


def _usable(chat: dict) -> bool:
    realism = chat.get("child_realism")
    if realism is None:
        return True
    return int(realism) >= 3


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
        stuck = sum(1 for chat in items if chat.get("ended_how") == "stuck" or (chat.get("checks") or {}).get("stuck_spans"))
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
    dropped = len(chats) - len(usable)
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


def compare_runs(left: list[dict], right: list[dict]) -> dict:
    """Match chats. A small gap on a few chats is no clear difference."""
    right_by = {_match_key(chat): chat for chat in right}
    matched = []
    flips_good = []
    flips_bad = []
    new_hard = []
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
    deltas = [
        (row["score_after"] - row["score_before"])
        for row in matched
        if row["score_before"] is not None and row["score_after"] is not None
    ]
    mean_delta = _mean(deltas)
    verdict = "no clear difference"
    if new_hard:
        verdict = "worse"
    elif mean_delta is None or len(matched) < 3 or abs(mean_delta) < 0.3:
        verdict = "no clear difference"
    elif mean_delta > 0 and len(flips_bad) <= len(flips_good):
        verdict = "better"
    elif mean_delta < 0:
        verdict = "worse"
    return {
        "matched": len(matched),
        "mean_score_delta": mean_delta,
        "flipped_to_completed": flips_good,
        "flipped_to_incomplete": flips_bad,
        "new_hard_stops": new_hard,
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
    if comparison.get("new_hard_stops"):
        return "red"
    verdict = comparison.get("verdict")
    if verdict == "worse":
        return "red"
    if verdict == "better":
        return "green"
    return "amber"
