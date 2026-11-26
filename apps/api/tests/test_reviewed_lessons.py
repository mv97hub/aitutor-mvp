"""Read the import files and exercise the same scorer and tutor prompt as the course."""

import json
from pathlib import Path

import pytest

from app.block_score import score_supported_turn
from app.kc_course_io import parse_course_document
from app.models import default_kc_tutor_config
from scripts.prepare_reviewed_lessons import cpi_check
from tests.test_kc_course_io import _file, _wipe_zz, client
from tests.test_kc_prompt import _node, _text

FILES = Path(__file__).resolve().parents[3] / "docs" / "course-corrections"


def _component(lesson):
    partial = json.loads((FILES / f"{lesson}.json").read_text())
    assert "course" not in partial
    return parse_course_document(partial)["units"][0]["components"][0]


def _score(block, step, line, passed, mode="quote_or_close_paraphrase"):
    cfg = default_kc_tutor_config()
    cfg["blocks"]["passage_ela"]["passage_ela_evidence_mode"] = mode
    return score_supported_turn(
        blocks=[block], step=0, active_block_state={"substep": step}, block_results=[],
        answer=line, cfg=cfg, goal=None, stored_rubric=[], move_attempts=0, hint_tier="nudge",
        reveals=0, enrichment_turns=0, prior_tutor="", decision="advance" if passed else "stay",
        substep_passed=passed, block_complete=False, rubric_met=[], matched_wrong="", last_misconception="",
    )


def test_contextual_citation_uses_source_and_current_reading_judgment():
    balcony, _, cell, _ = _component("romeo-and-juliet")["blocks"]
    data = cell["data"]
    assert data["evidence_context"] in _text(node=_node(blocks=[cell]), active_block_state={"substep": "cite_evidence"})
    assert data["passage_text"] in _text(node=_node(blocks=[cell]), opening=True)
    for block, line, passed, step in [
        (balcony, 'Juliet says “My only love sprung from my only hate!” so their families oppose their love.', True, "cite_evidence"),
        (cell, 'Paris tells Juliet “I will confess to you that I love him.”', False, "cite_evidence"),
        (cell, "Juliet tells Paris she loves someone but avoids naming him, because she loves Romeo.", True, "craft_or_inference"),
        (cell, "Can I see the passage again?", True, "cite_evidence"),
    ]:
        result = _score(block, "cite_evidence", line, passed)
        assert result.next_block_state["substep"] == step, line
        evidence = next(r for r in result.next_block_state["requirements"] if r["key"] == "cite_evidence")
        if "again?" in line:
            assert evidence["attempts"] == 0
        else:
            assert evidence["observation"] == ("independent" if step == "craft_or_inference" else "insufficient")
    strict = _score(cell, "cite_evidence", "Juliet avoids naming her husband while answering Paris.", True, "exact_quote_required")
    assert strict.next_block_state["substep"] == "cite_evidence"


@pytest.mark.parametrize(("old", "new", "rate"), [(100, 115, "15.00%"), (108, 115, "6.48%"), (108, 108, "0.00%"), (115, 108, "-6.09%")])
def test_cpi_question_and_choice_grade_use_the_same_two_readings(old, new, rate):
    check = cpi_check(old, new)
    if (old, new) == (108, 115):
        assert check in _component("price-indices")["blocks"]
    assert f"from {old} to {new}" in check["data"]["question_stem"]
    assert [c["text"] for c in check["data"]["choices"] if c["is_correct"]] == [rate]
    right = _score(check, "choice", f"b. {rate}", False)
    assert next(r for r in right.next_block_state["requirements"] if r["key"] == "choice")["observation"] == "independent"
    wrong = _score(check, "choice", f"a. {new-old} index points", True)
    assert wrong.next_block_state["substep"] == "choice"


def test_rentenmark_year_question_survives_course_import_and_export():
    check = next(b for b in _component("weimar-recovery")["blocks"] if b["id"] == "rentenmark-issue")
    source = _file()
    source["units"][0]["components"][0]["blocks"] = [check]
    _wipe_zz()
    try:
        imported = client.post("/kc/courses/import", json={"document": source})
        assert imported.status_code == 200, imported.text
        stored = client.get(f"/kc/courses/{imported.json()['id']}/export").json()
        loaded = stored["units"][0]["components"][0]["blocks"][0]
        assert "15 November 1923" in loaded["data"]["correct_explanation"]
        assert _score(loaded, "choice", "a. 1924", True).next_block_state["substep"] == "choice"
        assert _score(loaded, "choice", "b. 1923", False).next_block_state["substep"] != "choice"
    finally:
        _wipe_zz()
