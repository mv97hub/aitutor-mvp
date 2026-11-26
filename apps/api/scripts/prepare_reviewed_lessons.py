"""Prepare one reviewed November 2026 correction from its original KC course export.

This offline command writes a unit file for the existing course import screen.
"""

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path

BALCONY = "a-scene-in-romeo-and-juliet-that-only-se"
CPI = "price-indices-and-inflation"
WEIMAR = "weimar-recovery-and-its-limits-1924-29"
# Scope the correction to the authored component Myuran reviewed. Other components
# and course settings can have changed without affecting the correction.
PACKS = {
    BALCONY: "romeo-and-juliet.json",
    CPI: "price-indices.json",
    WEIMAR: "weimar-recovery.json",
}
DIRECTORY = Path(__file__).resolve().parents[3] / "docs" / "course-corrections"



def cpi_check(previous: int, current: int) -> dict:
    """Create the printed example and assessable options from the same pair of indices."""
    if previous <= 0 or current <= 0:
        raise ValueError("Both price indices must be positive.")
    points = current - previous
    rate = Decimal(100 * points) / Decimal(previous)
    percent = format(rate.quantize(Decimal("0.01")), "f")
    explanation = (
        f"The index change is {current} − {previous} = {points} index points. "
        f"The inflation rate is 100 × ({current} − {previous}) / {previous} = {percent}% to two decimal places."
    )
    return {
        "id": "checked-cpi-rate", "type": "mcq", "data": {
            "mode": "static",
            "question_stem": (
                f"The same CPI series goes from {previous} to {current} in one year. "
                "Which answer gives the inflation rate, with the correct unit?"
            ),
            "choices": [
                {"id": "a", "text": f"{points} index points", "is_correct": False,
                 "distractor_rationale": "That describes the difference between the index readings. Divide the change by the starting index to get the rate."},
                {"id": "b", "text": f"{percent}%", "is_correct": True},
                {"id": "c", "text": f"{points} dollars", "is_correct": False,
                 "distractor_rationale": "An index reading measures relative prices. Its change does not give a dollar amount."},
            ],
            "correct_explanation": explanation,
        },
    }


def prepare(document: dict) -> dict:
    matches = [(unit, item) for unit in document["units"] for item in unit["components"] if item["code"] in PACKS]
    if len(matches) != 1:
        raise ValueError("Expected one reviewed component in a full export of an affected course.")
    unit, original = matches[0]
    code = original["code"]
    pack = json.loads((DIRECTORY / PACKS[code]).read_text())
    canonical = json.dumps(original, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if hashlib.sha256(canonical.encode()).hexdigest() != pack["review"]["original_component_sha256"]:
        raise ValueError(f"{code} differs from the reviewed component. Compare its edits before preparing a new correction.")
    blocks = pack["unit"]["components"][0]["blocks"]
    if code == CPI:
        inputs = pack["review"]["cpi"]
        checked = cpi_check(inputs["previous"], inputs["current"])
        for index, block in enumerate(blocks):
            if block["id"] == checked["id"]:
                blocks[index] = checked
            elif block["id"] == "topic-goal-1":
                block["data"]["teaching_notes"] = checked["data"]["correct_explanation"]
            elif block["id"] == "explanation-1":
                topic = next(t for t in block["data"]["topics"] if t["id"] == "calculating-inflation")
                topic["examples_or_analogies"] = checked["data"]["correct_explanation"]
    component = {**original, "blocks": blocks}
    return {**pack, "unit": {**unit, "components": [component]}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.export.resolve() == args.output.resolve():
        parser.error("Choose a different path for the prepared lesson.")
    try:
        prepared = prepare(json.loads(args.export.read_text()))
    except (KeyError, TypeError, ValueError) as error:
        parser.error(str(error))
    args.output.write_text(json.dumps(prepared, indent=2, ensure_ascii=False) + "\n")
