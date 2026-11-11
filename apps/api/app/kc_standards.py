"""Curriculum standards for a KC course: the picker, the statement list, and coverage.

Pasted statements are the authority. A named standard with no paste is recalled
by the model and then checked by the author. A component with no statement code
is an extension.
"""

from __future__ import annotations

import re
from typing import Any

MAX_STATEMENTS = 120

STANDARDS: dict[str, dict[str, str]] = {
    "": {"label": "None", "site": "", "host": ""},
    "common_core_math": {
        "label": "Common Core (math)",
        "site": "https://www.corestandards.org/Math/",
        "host": "corestandards.org",
    },
    "common_core_ela": {
        "label": "Common Core (ELA)",
        "site": "https://www.corestandards.org/ELA-Literacy/",
        "host": "corestandards.org",
    },
    "ngss": {
        "label": "NGSS",
        "site": "https://www.nextgenscience.org/",
        "host": "nextgenscience.org",
    },
    "uk": {
        "label": "UK National Curriculum",
        "site": "https://www.gov.uk/national-curriculum",
        "host": "gov.uk",
    },
    "australian": {
        "label": "Australian Curriculum",
        "site": "https://www.australiancurriculum.edu.au/",
        "host": "australiancurriculum.edu.au",
    },
    "ontario": {
        "label": "Ontario",
        "site": "https://www.dcp.edu.gov.on.ca/en/curriculum",
        "host": "dcp.edu.gov.on.ca",
    },
    "ib_pyp": {
        "label": "International Baccalaureate PYP",
        "site": "https://www.ibo.org/programmes/primary-years-programme/",
        "host": "ibo.org",
    },
    "other": {"label": "Other", "site": "", "host": ""},
}

_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9./-]{0,24}$")
_BULLET = re.compile(r"^(?:[-*•]|\d+[.)])\s+")
_LIST_ITEM = re.compile(r"^(?:[-*•]\s+|\d+(?:\.\d+)*[.)]?\s+)\S")
# Unit words, or a markdown heading. A dotted topic such as "1.2 Demand" is not a header.
_UNIT_HEADER = re.compile(
    r"^(?:(?:unit|chapter|module|week|part|section|topic|lesson)\s+\d+\b"
    r"(?:\s*[:–—-]\s*(.+)|\s*\.\s+(?!\d)(.+)|\s+(?!\d)(.+))"
    r"|#+\s*(.+))$",
    re.IGNORECASE,
)
_SPACE = re.compile(r"\s+")


def standard_label(key: str, name: str = "") -> str:
    if key == "other":
        return (name or "").strip() or "Other"
    return STANDARDS.get(key, STANDARDS[""])["label"]


def _clean(value: object) -> str:
    return _SPACE.sub(" ", str(value or "")).strip()


def _looks_like_code(token: str) -> bool:
    return bool(_CODE.match(token) and (any(ch.isdigit() for ch in token) or "." in token or "-" in token))


def _too_many(count: int) -> ValueError:
    return ValueError(f"Keep the statements to at most {MAX_STATEMENTS} lines. This list has {count}.")


def _unit_title(line: str) -> str | None:
    """The title of a unit header, or None when the line is a topic."""
    match = _UNIT_HEADER.match(line)
    if not match:
        return None
    title = next((part.strip() for part in match.groups() if part and part.strip()), "")
    return title or None


def _statement_row(line: str) -> dict[str, str]:
    parts = line.split(None, 1)
    if len(parts) == 2 and _looks_like_code(parts[0]):
        return {"code": parts[0], "text": _clean(parts[1])}
    return {"code": "", "text": _clean(line)}


def parse_standard_text(text: str) -> list[dict[str, str]]:
    """One statement per line. A leading code is kept when the line has one."""
    rows: list[dict[str, str]] = []
    for raw in str(text or "").splitlines():
        line = _BULLET.sub("", raw.strip())
        if not line:
            continue
        rows.append(_statement_row(line))
    return _finish(rows)


def parse_syllabus(text: str) -> dict[str, Any]:
    """A pasted syllabus. Unit headers group topics. They are not statements."""
    buckets: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    loose: list[str] = []
    for raw in str(text or "").splitlines():
        raw_line = raw.strip()
        if not raw_line:
            continue
        title = _unit_title(raw_line)
        if title:
            current = {"title": _clean(title), "lines": []}
            buckets.append(current)
            continue
        line = _BULLET.sub("", raw_line)
        if not line:
            continue
        if current is None:
            loose.append(line)
        else:
            current["lines"].append(line)
    if not buckets:
        return {"units": [], "statements": parse_standard_text(text)}
    topic_lines = loose + [line for bucket in buckets for line in bucket["lines"]]
    statements = parse_standard_text("\n".join(topic_lines))
    index = len(loose)
    units: list[dict[str, Any]] = []
    for bucket in buckets:
        count = len(bucket["lines"])
        topics = statements[index : index + count]
        index += count
        if topics and bucket["title"]:
            units.append({"title": bucket["title"], "statements": topics})
    return {"units": units, "statements": statements}


def paste_count(text: str, *, syllabus: bool = False, flat: bool = False) -> int:
    """Units or statements in pasted text. A long list is counted, not rejected.

    syllabus=True counts unit headers, and also a bulleted or numbered topic
    list of at least two lines when there is no unit header. A prose paragraph
    does not set the course size. flat=True also counts a single bulleted or
    numbered line. The count is the larger of the unit headers and the topic
    lines: one component per pasted topic, not one per header plus one per topic.
    """
    units = 0
    statements = 0
    listed = 0
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if _unit_title(line):
            units += 1
            continue
        body = _BULLET.sub("", line)
        if not body:
            continue
        statements += 1
        if _LIST_ITEM.match(line):
            listed += 1
    if syllabus and units == 0:
        if listed >= 2:
            return listed
        return listed if flat else 0
    if units:
        return max(units, statements)
    return statements


def syllabus_statements(text: str) -> list[dict[str, str]]:
    """Topics from a pasted syllabus. A paragraph or a single line is an empty list."""
    if paste_count(text, syllabus=True) < 2:
        return []
    try:
        return list(parse_syllabus(text)["statements"])
    except ValueError:
        return []


def syllabus_outcome(text: str) -> str:
    """A short outcome sentence for a pasted syllabus of more than one topic."""
    try:
        parsed = parse_syllabus(text)
    except ValueError:
        parsed = {"units": [], "statements": []}
    units = [unit for unit in parsed.get("units") or [] if str(unit.get("title") or "").strip()]
    if len(units) >= 2:
        return f"Work through {units[0]['title']} through {units[-1]['title']}."
    if len(units) == 1:
        return f"Work through {units[0]['title']}."
    count = paste_count(text, syllabus=True)
    if count > 1:
        return f"Work through {count} pasted topics, one at a time."
    return "Work through the pasted syllabus, one topic at a time."


def clean_statements(raw: object) -> list[dict[str, str]]:
    """The statement list from the model or the editor."""
    if not isinstance(raw, list):
        raise ValueError("The standard statements are a list.")
    rows: list[dict[str, str]] = []
    for item in raw:
        if isinstance(item, str):
            rows.extend(parse_standard_text(item))
            continue
        if not isinstance(item, dict):
            raise ValueError("Each statement needs a code and its text.")
        rows.append({"code": _clean(item.get("code")), "text": _clean(item.get("text"))})
    return _finish(rows)


def _finish(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    if len(rows) > MAX_STATEMENTS:
        raise _too_many(len(rows))
    used: set[str] = set()
    number = 1
    finished: list[dict[str, str]] = []
    for row in rows:
        text = row["text"]
        if not text:
            raise ValueError("Each statement needs its text.")
        code = row["code"]
        if not code:
            while f"s{number}" in used:
                number += 1
            code = f"s{number}"
            number += 1
        if code in used:
            raise ValueError(f"The statement code {code} is used twice.")
        used.add(code)
        finished.append({"code": code, "text": text})
    return finished


def syllabus_requested(intake: dict) -> bool:
    """The author asked for one component per pasted topic."""
    return bool(intake.get("align_syllabus") or intake.get("depth") == "curriculum")


def syllabus_source(intake: dict) -> str:
    """Curriculum statements win. Source text counts when the syllabus should be tracked."""
    pasted = str(intake.get("standard_text") or "").strip()
    if pasted and (intake.get("standard") or syllabus_requested(intake)):
        return pasted
    if syllabus_requested(intake):
        return str(intake.get("source_text") or "").strip()
    return ""


def statements_from_intake(intake: dict) -> list[dict[str, str]]:
    """Pasted text wins. A syllabus paste becomes tracked statements. A named standard with no paste is recalled later."""
    text = syllabus_source(intake)
    if not text:
        return []
    if syllabus_requested(intake):
        return list(parse_syllabus(text)["statements"])
    return parse_standard_text(text)


def syllabus_units(intake: dict) -> list[dict[str, Any]]:
    """Unit titles from a pasted syllabus, each with the statements under it."""
    if not syllabus_requested(intake):
        return []
    text = syllabus_source(intake)
    if not text:
        return []
    return list(parse_syllabus(text)["units"])


def read_statements(raw: object) -> list[dict[str, str]]:
    """Stored rows. A damaged row is dropped rather than failing a page load."""
    if not isinstance(raw, list):
        return []
    try:
        return clean_statements(raw)
    except ValueError:
        return []


def component_standards(raw: object, statements: list[dict[str, str]] | None, label: str) -> tuple[list[str], bool]:
    """Codes this component covers, and whether it is an extension.

    An empty course list means the course has no standard, so a component is
    never marked as an extension. A non-empty list with no codes is an extension.
    """
    codes: list[str] = []
    if isinstance(raw, str):
        raw = re.split(r"[,\s]+", raw)
    for item in raw or []:
        key = _clean(item)
        if key and key not in codes:
            codes.append(key)
    if not statements:
        if codes:
            raise ValueError(f"{label} lists standard codes, and this course has no standard statements.")
        return [], False
    known = {item["code"] for item in statements}
    unknown = [code for code in codes if code not in known]
    if unknown:
        raise ValueError(
            f"{label} names {unknown[0]!r}, which is not one of the standard statements. "
            f"Use only {', '.join(known)}."
        )
    return codes, not codes


def coverage_matrix(statements: list[dict[str, str]], blueprint: dict) -> dict[str, Any]:
    """Statements down the side. Missing, light, and extension come from the codes."""
    rows = []
    for unit in (blueprint or {}).get("units") or []:
        rows.extend(unit.get("components") or [])
    covered: dict[str, list[str]] = {item["code"]: [] for item in statements}
    extensions: list[str] = []
    for row in rows:
        codes = [code for code in (row.get("standards") or []) if code in covered]
        if statements and not codes:
            extensions.append(row.get("code") or "")
        for code in codes:
            covered[code].append(row.get("code") or "")
    matrix: list[dict[str, Any]] = []
    gaps: list[str] = []
    light: list[str] = []
    for item in statements:
        comps = [code for code in covered[item["code"]] if code]
        if not comps:
            status = "missing"
            gaps.append(item["code"])
            once = False
        elif len(comps) == 1:
            status = "light"
            light.append(item["code"])
            once = True
        else:
            status = "covered"
            once = False
        matrix.append(
            {
                "code": item["code"],
                "text": item["text"],
                "components": comps,
                "status": status,
                "once_without_review": once,
            }
        )
    return {
        "rows": matrix,
        "gaps": gaps,
        "light": light,
        "once_without_review": light,
        "extensions": [code for code in extensions if code],
    }


def statement_lines(statements: list[dict[str, str]]) -> str:
    return "\n".join(f"- {item['code']}: {item['text']}" for item in statements)


def standard_brief_lines(intake: dict, statements: list[dict[str, str]]) -> list[str]:
    """What the brief prompt says about the chosen standard."""
    key = intake.get("standard") or ""
    if not key:
        return ["Do not invent a curriculum standard."]
    label = standard_label(key, intake.get("standard_name") or "")
    grade = intake.get("standard_grade") or "the grade the author named"
    lines = [
        f"Curriculum standard: {label}.",
        f"Grade or year: {grade}.",
        "Name this standard and the grade in the brief.",
    ]
    if statements:
        lines.extend(
            [
                "The author pasted these statements. They are the authority. "
                "Do not add, drop, or rewrite them, and do not recall a different list.",
                "Standard statements:",
                statement_lines(statements),
            ]
        )
    else:
        host = STANDARDS.get(key, {}).get("host") or "the official site for this curriculum"
        lines.extend(
            [
                "No statements were pasted, so recall the statements for this grade and this topic. "
                "Return them in statements, one object per statement, with its code when the standard has one. "
                f"Keep it to the statements this course should cover, at most {MAX_STATEMENTS}, not a different subject on {host}. "
                "The author will check this list before the blueprint. "
                "Say in the brief that the list is recalled and should be checked.",
            ]
        )
    return lines
