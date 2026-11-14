"""Prompt-builder excerpts and stored tutor prompts for recommendation drafts.

Reads kc_prompt.py. Does not change it and does not call the tutor.
"""

from __future__ import annotations

import ast
import re
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

PROMPT_FILE = Path(__file__).resolve().parent / "kc_prompt.py"

SECTION_HEADERS = (
    "Safety",
    "Who you are talking to",
    "How to sound",
    "How to teach",
    "What to return",
    "What to teach",
    "This turn",
    "What just happened",
)

# Sentence constants are appended by a section function. The function name is
# what a later edit of kc_prompt.py should change.
_SYMBOLS: tuple[tuple[str, str, str], ...] = (
    ("_GOAL_START_EXPLAIN", "This turn", "_this_turn"),
    ("_GOAL_START_DEEPEN", "This turn", "_this_turn"),
    ("_GOAL_START_CLARIFY", "This turn", "_this_turn"),
    ("_GOAL_START_ASIDE", "This turn", "_this_turn"),
    ("_GOAL_START_ASK", "This turn", "_this_turn"),
    ("_SIDE_STAY", "This turn", "_this_turn"),
    ("_SIDE_FOLLOW", "This turn", "_this_turn"),
    ("_SIDE_EXPLAIN", "This turn", "_this_turn"),
    ("_block_config_rules", "How to teach", "_block_config_rules"),
    ("_this_turn", "This turn", "_this_turn"),
    ("_how_to_teach", "How to teach", "_how_to_teach"),
    ("_what_to_return", "What to return", "_what_to_return"),
    ("build_kc_prompt", "This turn", "build_kc_prompt"),
)

_SOURCE_CAP = 8000


def prompt_sections(prompt: str) -> dict[str, str]:
    """Split a stored tutor prompt on its section headers."""
    current = ""
    buckets: dict[str, list[str]] = {}
    for line in str(prompt or "").splitlines():
        header = line.strip()
        if header in SECTION_HEADERS:
            current = header
            buckets.setdefault(current, [])
            continue
        if current:
            buckets[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in buckets.items() if "\n".join(lines).strip()}


def block_label_from_prompt(prompt: str) -> str:
    match = re.search(r"Block \d+ of \d+: ([^.\n]+)", str(prompt or ""))
    if match is None:
        return ""
    return match.group(1).strip()


def _literals(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        text = " ".join(node.value.split())
        if len(text) < 40 or text in seen:
            continue
        seen.add(text)
        found.append(text)
    found.sort(key=len, reverse=True)
    return found[:40]


def _cap(source: str, limit: int = _SOURCE_CAP) -> str:
    if len(source) <= limit:
        return source
    head = limit // 2
    tail = limit - head
    return f"{source[:head]}\n# ...\n{source[-tail:]}"


def prompt_builder_excerpts(source: str | None = None) -> list[dict]:
    """Return the section, function, source, and sentence literals for each symbol."""
    text = source if source is not None else PROMPT_FILE.read_text()
    tree = ast.parse(text)
    nodes: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nodes[node.name] = node
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    nodes[target.id] = node
    rows = []
    for symbol, section, function in _SYMBOLS:
        node = nodes.get(symbol)
        if node is None:
            continue
        segment = ast.get_source_segment(text, node) or ""
        rows.append(
            {
                "symbol": symbol,
                "section": section,
                "function": function,
                "source": _cap(segment),
                "literals": _literals(segment),
            }
        )
    return rows


def select_turns(turns: list[dict], wanted: set[int]) -> list[dict]:
    """Keep the opening turn, the closing turn, and turns a finding points at."""
    if not turns:
        return []
    indexes = {0, len(turns) - 1}
    for index, turn in enumerate(turns):
        try:
            seq = int(turn.get("seq") or 0)
        except (TypeError, ValueError):
            seq = 0
        if seq in wanted or index in wanted or (seq - 1) in wanted:
            indexes.add(index)
    return [turns[index] for index in sorted(indexes)][:6]


def example_from_turn(chat_id: str, turn: dict) -> dict | None:
    prompt = str(turn.get("tutor_prompt") or "").strip()
    if not prompt:
        return None
    try:
        seq = int(turn.get("seq") or 0)
    except (TypeError, ValueError):
        seq = 0
    return {
        "chat_id": chat_id,
        "turn": seq,
        "intent": str(turn.get("intent") or ""),
        "child_text": str(turn.get("child_text") or "")[:400],
        "block_label": block_label_from_prompt(prompt),
        "tutor_prompt": prompt[:20000],
        "sections": prompt_sections(prompt),
    }


def _wanted_turns(findings: list[dict]) -> dict[str, set[int]]:
    wanted: dict[str, set[int]] = {}
    for finding in findings:
        for example in finding.get("examples") or []:
            if not isinstance(example, dict):
                continue
            chat_id = str(example.get("chat_id") or "")
            if not chat_id:
                continue
            try:
                turn = int(example.get("turn") or 0)
            except (TypeError, ValueError):
                turn = 0
            wanted.setdefault(chat_id, set()).add(turn)
    return wanted


def draft_context(db: Session, run_id: uuid.UUID) -> dict:
    """Findings, the prompt-builder source, and stored prompts for example turns."""
    from sqlalchemy import select

    from app.harness import findings_for_run, get_chat
    from app.models import HarnessChat

    report = findings_for_run(db, run_id)
    findings = report.get("findings") if isinstance(report.get("findings"), list) else []
    wanted = _wanted_turns(findings)
    chat_ids = list(wanted)
    if not chat_ids:
        chat_ids = [
            str(item)
            for item in db.scalars(
                select(HarnessChat.id).where(HarnessChat.run_id == run_id).order_by(HarnessChat.created_at.desc()).limit(2)
            ).all()
        ]
    examples: list[dict] = []
    for chat_id in chat_ids[:3]:
        try:
            detail = get_chat(db, uuid.UUID(chat_id))
        except Exception:
            continue
        turns = detail.get("turns") if isinstance(detail.get("turns"), list) else []
        for turn in select_turns(turns, wanted.get(chat_id, set())):
            if not isinstance(turn, dict):
                continue
            row = example_from_turn(chat_id, turn)
            if row is None:
                continue
            examples.append(row)
            if len(examples) >= 8:
                break
        if len(examples) >= 8:
            break
    return {
        "run_id": str(run_id),
        "findings": findings,
        "examples": examples,
        "builder": prompt_builder_excerpts(),
    }
