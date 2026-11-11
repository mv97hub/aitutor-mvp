"""Full course import and export, including blocks and a unit-by-unit file."""

from fastapi.testclient import TestClient

from app.kc_course_io import SCHEMA, external_course_prompt, normalize_blocks
from app.main import app
from tests.test_kc_pipeline import OUTCOME, _wipe_zz

client = TestClient(app)


def _file(code: str = "zz-macro") -> dict:
    return {
        "schema": SCHEMA,
        "course": {
            "title": "AP Macroeconomics",
            "code": code,
            "description": OUTCOME,
            "subject": "Economics",
            "grade_band": "15-17",
            "kind": "mastery",
            "estimated_minutes": 120,
            "outcomes": ["Explain scarcity.", "Use a supply curve."],
            "brief": "A course on macroeconomics for older students who can read a graph. " * 2,
            "standards": [{"code": "s1", "text": "Scarcity."}, {"code": "s2", "text": "Supply."}],
        },
        "units": [
            {
                "title": "Basic concepts",
                "summary": "The first ideas.",
                "components": [
                    {
                        "code": "zz-scarcity",
                        "title": "Scarcity",
                        "description": "The learner can explain scarcity. Resources are limited. A mix-up is treating price as the only cost.",
                        "summary": "Limited resources.",
                        "outline": "Define scarcity.",
                        "core_truth": "Resources are limited.",
                        "rubric": ["Names scarcity."],
                        "misconceptions": [{"wrong_move": "Price is the only cost.", "broken_kc": ""}],
                        "standards": ["s1"],
                        "prerequisite_codes": [],
                        "encompasses_codes": [],
                        "blocks": [
                            {
                                "id": "blk_1",
                                "type": "topic_goal",
                                "data": {"topic": "Scarcity", "goal": "Define it", "extra": "drop me"},
                            }
                        ],
                    },
                    {
                        "code": "zz-supply",
                        "title": "Supply",
                        "description": "The learner can read a supply curve. Quantity rises with price. A mix-up is swapping it with demand.",
                        "summary": "The supply curve.",
                        "standards": ["s2"],
                        "prerequisite_codes": ["zz-scarcity"],
                        "blocks": [
                            {
                                "id": "blk_2",
                                "type": "mcq",
                                "data": {
                                    "mode": "static",
                                    "question_stem": "Which way does supply slope?",
                                    "choices": [
                                        {"id": "a", "text": "Up", "is_correct": True},
                                        {"id": "b", "text": "Down", "is_correct": False},
                                    ],
                                },
                            }
                        ],
                    },
                ],
            }
        ],
    }


def test_blocks_keep_catalog_fields_and_reject_unknown_types() -> None:
    cleaned = normalize_blocks([{"type": "topic_goal", "data": {"topic": "A", "goal": "B", "nope": 1}}])
    assert cleaned[0]["data"] == {"topic": "A", "goal": "B"}
    try:
        normalize_blocks([{"type": "quiz", "data": {}}])
    except ValueError as exc:
        assert "unknown type" in str(exc)
    else:
        raise AssertionError("unknown block type was accepted")


def test_import_export_round_trip_merge_and_the_external_prompt() -> None:
    _wipe_zz()
    try:
        created = client.post("/kc/courses/import", json={"document": _file()})
        assert created.status_code == 200, created.text
        course_id = created.json()["id"]
        nodes = {item["code"]: item for item in created.json()["components"]}
        assert nodes["zz-supply"]["prerequisite_codes"] == ["zz-scarcity"]
        assert nodes["zz-scarcity"]["standards"] == ["s1"]
        assert nodes["zz-scarcity"]["core_truth"] == "Resources are limited."
        assert nodes["zz-scarcity"]["blocks"][0]["data"] == {"topic": "Scarcity", "goal": "Define it"}
        assert nodes["zz-supply"]["blocks"][0]["type"] == "mcq"
        exported = client.get(f"/kc/courses/{course_id}/export").json()
        assert exported["schema"] == SCHEMA
        assert exported["course"]["subject"] == "Economics"
        assert exported["course"]["grade_band"] == "15-17"
        assert exported["course"]["standards"][0]["code"] == "s1"
        assert exported["units"][0]["components"][1]["prerequisite_codes"] == ["zz-scarcity"]
        assert exported["units"][0]["components"][0]["blocks"][0]["type"] == "topic_goal"

        unit_file = {
            "unit": {
                "title": "Policy",
                "summary": "Fiscal policy.",
                "components": [
                    {
                        "code": "zz-fiscal",
                        "title": "Fiscal policy",
                        "description": "The learner can name a fiscal tool. Spending is one tool. A mix-up is calling a tax cut monetary policy.",
                        "standards": ["s1"],
                        "prerequisite_codes": ["zz-supply"],
                        "blocks": [],
                    }
                ],
            }
        }
        preview = client.post("/kc/courses/import-preview", json={"document": unit_file})
        assert preview.status_code == 200, preview.text
        assert preview.json()["partial"] is True
        assert preview.json()["component_count"] == 1
        merged = client.post(
            f"/kc/courses/{course_id}/import", json={"document": unit_file, "mode": "merge"}
        )
        assert merged.status_code == 200, merged.text
        titles = [unit["title"] for unit in client.get(f"/kc/courses/{course_id}/pipeline").json()["blueprint"]["units"]]
        assert titles == ["Basic concepts", "Policy"]
        codes = [item["code"] for item in merged.json()["components"]]
        assert "zz-scarcity" in codes and "zz-fiscal" in codes

        replaced = client.post(
            f"/kc/courses/{course_id}/import",
            json={"document": _file(), "mode": "replace"},
        )
        # code in the file is ignored on replace of an existing course; components come from the file.
        assert replaced.status_code == 200, replaced.text
        replaced_codes = [item["code"] for item in replaced.json()["components"]]
        assert replaced_codes == ["zz-scarcity", "zz-supply"]

        rejected = client.post(
            f"/kc/courses/{course_id}/import",
            json={"document": {"units": [{"title": "Bad", "components": [{"title": "Bad", "blocks": [{"type": "quiz", "data": {}}]}]}]}, "mode": "merge"},
        )
        assert rejected.status_code == 422
        assert "unknown type" in rejected.json()["detail"]

        prompt = client.post(
            "/kc/courses/external-prompt",
            json={
                "title": "AP Macroeconomics",
                "grade": "12",
                "audience": "15-17",
                "curriculum": "1. Scarcity\n2. Supply",
                "block_notes": "Every component includes an explanation and one mcq.",
            },
        )
        assert prompt.status_code == 200, prompt.text
        text = prompt.json()["prompt"]
        assert SCHEMA in text
        assert "unit_index" in text
        assert "1. Scarcity" in text
        assert "topic_goal" in text and "mcq" in text
        built = external_course_prompt(title="AP", grade="12", audience="15-17", curriculum="Unit 1: Ideas", block_notes="")
        assert "one unit per reply" in built
    finally:
        _wipe_zz()
