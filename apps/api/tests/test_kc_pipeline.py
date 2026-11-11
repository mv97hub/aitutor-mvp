"""The KC Course Creator pipeline: brief, blueprint, unit descriptions, review."""

import json

import pytest
from fastapi.testclient import TestClient

from app import block_catalog, kc, kc_model
from app.kc_standards import MAX_STATEMENTS, coverage_matrix, parse_standard_text, statements_from_intake
from app.kc_pipeline import (
    CHECKS,
    INSTRUCTION_RULES,
    MAX_COMPONENTS,
    MAX_FOLLOW_UPS,
    apply_review,
    assemble_blueprint,
    blueprint_bundle,
    brief_bundle,
    chat_bundle,
    clean_blueprint_edit,
    clean_brief,
    clean_description,
    clean_intake,
    clean_unit,
    component_range,
    interpret_chat,
    missing_intake,
    review_bundle,
    unit_bundle,
)
from app.main import app
from app.models import ALL_BLOCK_TYPES
from tests.test_kc import _model_fields, _wipe_zz

client = TestClient(app)

OUTCOME = "Find a missing angle in a triangle and explain why two sides and a non-included angle do not prove congruence."


def _course(**overrides) -> dict:
    base = {
        "title": "Triangle congruence",
        "description": OUTCOME,
        "audience": "12-14",
        "kind": "mastery",
        "minutes": None,
        "intake": clean_intake({"depth": "intro", "must_cover": "angle sum", "interests": "skateboards"}),
    }
    base.update(overrides)
    return base


def _slug(title: str, taken: set[str]) -> str:
    base = title.lower().replace(" ", "-")
    code, number = base, 2
    while code in taken:
        code = f"{base}-{number}"
        number += 1
    return code


def _sentences(topic: str) -> str:
    return (
        f"The child can explain {topic} in their own words. "
        f"The one core idea is {topic}. "
        f"A common confusion is mixing {topic} up with a nearby idea."
    )


def _model_blueprint(count: int = 5, *, title_prefix: str = "Idea") -> dict:
    components = [
        {
            "ref": f"c{index}",
            "title": f"{title_prefix} {index}",
            "summary": f"Teaches idea {index}.",
            "prerequisites": [f"c{index - 1}"] if index > 1 else [],
        }
        for index in range(1, count + 1)
    ]
    return {
        "outcomes": ["Name the angle sum.", "Explain why SSA fails."],
        "units": [
            {"title": "Angles", "summary": "Angle facts.", "components": components[:3]},
            {"title": "Congruence", "summary": "Proof ideas.", "components": components[3:]},
        ],
    }


def _walk_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            keys.add(str(key))
            keys |= _walk_keys(item)
    elif isinstance(value, list):
        for item in value:
            keys |= _walk_keys(item)
    return keys


def test_intake_defaults_caps_and_required_fields() -> None:
    intake = clean_intake({})
    assert intake["reading_level"] == "age"
    assert intake["depth"] == "standard"
    assert intake["component_count"] is None
    assert intake["standard"] == ""
    assert intake["standard_grade"] == ""
    assert intake["standard_text"] == ""
    assert len(clean_intake({"source_text": "x" * 30000})["source_text"]) == 20000
    with pytest.raises(ValueError, match="Depth"):
        clean_intake({"depth": "huge"})
    with pytest.raises(ValueError, match="Component count"):
        clean_intake({"component_count": 1})
    assert missing_intake(title="Fractions", description="", audience="9-11", intake=intake) == [
        'what the child can do by the end ("by the end the child can...")'
    ]
    assert missing_intake(title="Fractions", description=OUTCOME, audience="9-11", intake=intake) == []
    named = clean_intake({"standard": "ngss", "standard_grade": ""})
    assert "the grade or year" in missing_intake(title="Fractions", description=OUTCOME, audience="9-11", intake=named)
    other = clean_intake({"standard": "other", "standard_grade": "4", "standard_name": ""})
    assert "the name of the standard" in missing_intake(
        title="Fractions", description=OUTCOME, audience="9-11", intake=other
    )
    with pytest.raises(ValueError, match="Standard"):
        clean_intake({"standard": "nope"})


def test_depth_kind_and_an_explicit_count_set_the_component_range() -> None:
    assert component_range(kind="mastery", minutes=None, intake=clean_intake({"depth": "intro"})) == (4, 6)
    assert component_range(kind="mastery", minutes=None, intake=clean_intake({"depth": "deep"})) == (15, 25)
    assert component_range(kind="time_boxed", minutes=60, intake=clean_intake({})) == (4, 6)
    assert component_range(kind="mastery", minutes=None, intake=clean_intake({"component_count": 9})) == (9, 9)


def test_brief_prompt_uses_the_intake_and_caps_follow_ups() -> None:
    course = _course()
    bundle = brief_bundle(course=course, answers=[], model="gpt-4.1")
    prompt = bundle["system_prompt"]
    assert "one paragraph" in prompt
    assert f"at most {MAX_FOLLOW_UPS} short follow-up questions" in prompt
    assert OUTCOME in prompt
    assert "Must cover: angle sum" in prompt
    assert "Interests for real-world hooks: skateboards" in prompt
    assert "Age band: 12-14" in prompt
    assert bundle["schema"]["properties"]["questions"]["maxItems"] == 2
    assert bundle["schema"]["required"] == ["brief", "questions"]
    answered = brief_bundle(course=course, answers=[{"question": "Which grade?", "answer": "Grade 7"}], model="gpt-4.1")
    assert "- Which grade? Grade 7" in answered["system_prompt"]
    assert "Return no questions" in answered["system_prompt"]


def test_brief_check_is_one_paragraph_and_drops_questions_once_answered() -> None:
    text = "A course on triangle congruence for twelve to fourteen year olds. " * 2
    brief, questions = clean_brief({"brief": text.replace(". ", ".\n"), "questions": ["A?", "a?", "B?", "C?"]}, answered=False)
    assert "\n" not in brief
    assert questions == ["A?", "B?"]
    assert clean_brief({"brief": text, "questions": ["A?"]}, answered=True)[1] == []
    with pytest.raises(ValueError, match="one paragraph"):
        clean_brief({"brief": "Too short.", "questions": []}, answered=False)


def test_blueprint_prompt_carries_the_count_the_rules_and_the_schema() -> None:
    bundle = blueprint_bundle(course=_course(), brief="A brief about triangles.", model="gpt-4.1")
    prompt = bundle["system_prompt"]
    assert "Return between 4 and 6 components." in prompt
    assert INSTRUCTION_RULES in prompt
    assert "One teachable idea per component, about 10 to 15 minutes." in prompt
    assert "Order from concrete to abstract." in prompt
    assert "worked example, then guided practice, then independent practice" in prompt
    assert "capstone" in prompt
    assert "observable verbs" in prompt
    assert "A brief about triangles." in prompt
    unit = bundle["schema"]["properties"]["units"]["items"]["properties"]["components"]["items"]
    assert unit["required"] == ["ref", "title", "summary", "prerequisites"]
    exact = blueprint_bundle(course=_course(intake=clean_intake({"component_count": 7})), brief="B" * 50, model="gpt-4.1")
    assert "Return exactly 7 components." in exact["system_prompt"]


def test_blueprint_refs_become_codes_and_bad_plans_are_rejected() -> None:
    blueprint = assemble_blueprint(_model_blueprint(5), bounds=(4, 6), taken={"idea-1"}, make_code=_slug)
    rows = [item for unit in blueprint["units"] for item in unit["components"]]
    assert [item["code"] for item in rows] == ["idea-1-2", "idea-2", "idea-3", "idea-4", "idea-5"]
    assert rows[1]["prerequisites"] == ["idea-1-2"]
    assert rows[0]["prerequisites"] == []
    assert blueprint["outcomes"] == ["Name the angle sum.", "Explain why SSA fails."]

    with pytest.raises(ValueError, match="Return between 4 and 6"):
        assemble_blueprint(_model_blueprint(8), bounds=(4, 6), taken=set(), make_code=_slug)
    forward = _model_blueprint(5)
    forward["units"][0]["components"][0]["prerequisites"] = ["c3"]
    with pytest.raises(ValueError, match="comes earlier"):
        assemble_blueprint(forward, bounds=(4, 6), taken=set(), make_code=_slug)
    twice = _model_blueprint(5)
    twice["units"][1]["components"][0]["title"] = "Idea 1"
    with pytest.raises(ValueError, match="distinct"):
        assemble_blueprint(twice, bounds=(4, 6), taken=set(), make_code=_slug)
    thin = _model_blueprint(5)
    thin["outcomes"] = ["Only one."]
    with pytest.raises(ValueError, match="at least two course outcomes"):
        assemble_blueprint(thin, bounds=(4, 6), taken=set(), make_code=_slug)


def test_an_edited_blueprint_keeps_codes_names_new_rows_and_checks_order() -> None:
    stored = assemble_blueprint(_model_blueprint(5), bounds=(4, 6), taken=set(), make_code=_slug)
    edited = json.loads(json.dumps(stored))
    edited["units"][0]["components"][0]["title"] = "A better first idea"
    edited["units"][0]["components"].append(
        {"code": "", "title": "Brand new", "summary": "New.", "prerequisites": "idea-1, idea-2"}
    )
    cleaned = clean_blueprint_edit(edited, taken=set(), make_code=_slug)
    first = cleaned["units"][0]["components"]
    assert first[0]["code"] == "idea-1"
    assert first[0]["title"] == "A better first idea"
    assert first[-1]["code"] == "brand-new"
    assert first[-1]["prerequisites"] == ["idea-1", "idea-2"]
    cycle = json.loads(json.dumps(stored))
    cycle["units"][0]["components"][0]["prerequisites"] = ["idea-2"]
    with pytest.raises(ValueError, match="comes earlier"):
        clean_blueprint_edit(cycle, taken=set(), make_code=_slug)
    gone = json.loads(json.dumps(stored))
    gone["units"] = []
    with pytest.raises(ValueError, match="at least one unit"):
        clean_blueprint_edit(gone, taken=set(), make_code=_slug)


def test_descriptions_are_plain_text_with_no_block_line() -> None:
    good = clean_description(_sentences("angle sum"))
    assert good.count(".") == 3
    for bad, message in (
        ("One. Two.", "3 to 4 sentences"),
        (_sentences("angle sum") + " Recommended blocks: 1. MCQ (angle sum) -> 2. Case Study (SSA).", "does not list blocks"),
        ("- Know the sum\n- Use the sum\n- Check the sum", "not a list"),
        ("", "empty"),
    ):
        with pytest.raises(ValueError, match=message):
            clean_description(bad)
    assert "\n" not in clean_description("The child can state it.\nThe idea is simple.\nA mix-up is common.")


def test_unit_prompt_sees_the_brief_the_blueprint_and_earlier_descriptions() -> None:
    blueprint = assemble_blueprint(_model_blueprint(5), bounds=(4, 6), taken=set(), make_code=_slug)
    written = {item["code"]: _sentences(item["title"]) for item in blueprint["units"][0]["components"]}
    bundle = unit_bundle(
        course=_course(),
        brief="A brief about triangles.",
        blueprint=blueprint,
        descriptions=written,
        unit_index=1,
        model="gpt-4.1",
    )
    prompt = bundle["system_prompt"]
    assert "A brief about triangles." in prompt
    assert "- Name the angle sum." in prompt
    assert "Unit 2 of 2: Congruence" in prompt
    assert "- idea-4: Idea 4 (needs: idea-3) - Teaches idea 4." in prompt
    assert "Descriptions already written:" in prompt
    assert f"- idea-1: {written['idea-1']}" in prompt
    assert "Write now: unit 2 of 2, Congruence." in prompt
    assert INSTRUCTION_RULES in prompt
    assert "3 to 4 sentences" in prompt
    assert "Do not repeat or contradict the descriptions already written." in prompt
    codes = bundle["schema"]["properties"]["components"]["items"]["properties"]["code"]["enum"]
    assert codes == ["idea-4", "idea-5"]


def test_a_unit_result_must_describe_exactly_its_components() -> None:
    codes = ["idea-4", "idea-5"]
    result = {"components": [{"code": code, "description": _sentences(code)} for code in codes]}
    assert set(clean_unit(result, codes)) == set(codes)
    with pytest.raises(ValueError, match="Missing: idea-5"):
        clean_unit({"components": result["components"][:1]}, codes)
    with pytest.raises(ValueError, match="not a component in this unit"):
        clean_unit({"components": [{"code": "idea-1", "description": _sentences("x")}]}, codes)
    with pytest.raises(ValueError, match="3 to 4 sentences"):
        clean_unit({"components": [{"code": "idea-4", "description": "Short."}]}, codes)


def _drafted() -> tuple[dict, dict]:
    blueprint = assemble_blueprint(_model_blueprint(5), bounds=(4, 6), taken=set(), make_code=_slug)
    return blueprint, {
        item["code"]: _sentences(item["title"]) for unit in blueprint["units"] for item in unit["components"]
    }


def _ok_checks() -> list[dict]:
    return [{"name": name, "result": "ok", "note": ""} for name in CHECKS]


def test_review_prompt_names_every_check_and_the_drafted_course() -> None:
    blueprint, descriptions = _drafted()
    bundle = review_bundle(
        course=_course(), brief="A brief about triangles.", blueprint=blueprint, descriptions=descriptions, model="gpt-4.1"
    )
    prompt = bundle["system_prompt"]
    for name in CHECKS:
        assert name in prompt
    for phrase in ("steps that jump too far", "overlap", "capstone", "observable verb", "reading level"):
        assert phrase in prompt or phrase.replace("steps that jump too far", "leaps too far") in prompt
    assert INSTRUCTION_RULES in prompt
    assert "- idea-2: Idea 2 (unit 1, needs: idea-1)" in prompt
    names = bundle["schema"]["properties"]["checks"]["items"]["properties"]["name"]["enum"]
    assert names == list(CHECKS)


def test_review_applies_fixes_before_the_draft_is_shown() -> None:
    blueprint, descriptions = _drafted()
    result = {
        "checks": [
            {"name": "gaps", "result": "ok", "note": ""},
            {"name": "overlap", "result": "ok", "note": ""},
            {"name": "jumps", "result": "fixed", "note": "Idea 4 now needs idea 3 and idea 2."},
            {"name": "capstone", "result": "fixed", "note": "Added a capstone."},
            {"name": "outcomes", "result": "fixed", "note": "Sharper verbs."},
            {"name": "reading_level", "result": "ok", "note": ""},
        ],
        "outcomes": ["Name the angle sum.", "Prove two triangles congruent with SAS."],
        "revisions": [
            {
                "code": "idea-4",
                "title": None,
                "summary": None,
                "description": _sentences("a sharper idea four"),
                "prerequisites": ["idea-3", "idea-2"],
            }
        ],
        "additions": [
            {
                "after_code": "idea-5",
                "title": "Capstone proof",
                "summary": "Combine every idea in one proof.",
                "description": _sentences("a full proof"),
                "prerequisites": ["idea-5", "idea-1"],
            }
        ],
    }
    fixed, notes, review = apply_review(
        result, blueprint=blueprint, descriptions=descriptions, taken=set(), make_code=_slug
    )
    codes = [item["code"] for unit in fixed["units"] for item in unit["components"]]
    assert codes[-1] == "capstone-proof"
    assert "a sharper idea four" in notes["idea-4"]
    assert fixed["units"][1]["components"][0]["prerequisites"] == ["idea-3", "idea-2"]
    assert review["revised"] == ["idea-4"]
    assert review["added"] == ["capstone-proof"]
    assert review["outcomes_changed"] is True
    assert [item["name"] for item in review["checks"]] == list(CHECKS)
    assert "Recommended blocks" not in " ".join(notes.values())

    quiet = {"checks": _ok_checks(), "outcomes": None, "revisions": [], "additions": []}
    same, same_notes, same_review = apply_review(
        quiet, blueprint=blueprint, descriptions=descriptions, taken=set(), make_code=_slug
    )
    assert same == blueprint and same_notes == descriptions
    assert same_review["revised"] == [] and same_review["added"] == []

    with pytest.raises(ValueError, match="Missing: reading_level"):
        apply_review(
            {**quiet, "checks": _ok_checks()[:-1]},
            blueprint=blueprint,
            descriptions=descriptions,
            taken=set(),
            make_code=_slug,
        )
    with pytest.raises(ValueError, match="not a component"):
        apply_review(
            {**quiet, "revisions": [{"code": "nope", "title": None, "summary": None, "description": None, "prerequisites": None}]},
            blueprint=blueprint,
            descriptions=descriptions,
            taken=set(),
            make_code=_slug,
        )


def test_the_course_creator_has_no_blocks_outline_or_topic_goals() -> None:
    blueprint, descriptions = _drafted()
    bundles = [
        brief_bundle(course=_course(), answers=[], model="gpt-4.1"),
        blueprint_bundle(course=_course(), brief="B" * 50, model="gpt-4.1"),
        unit_bundle(
            course=_course(), brief="B" * 50, blueprint=blueprint, descriptions={}, unit_index=0, model="gpt-4.1"
        ),
        review_bundle(course=_course(), brief="B" * 50, blueprint=blueprint, descriptions=descriptions, model="gpt-4.1"),
    ]
    for bundle in bundles:
        keys = _walk_keys(bundle["schema"])
        assert not keys & {"recommended_blocks", "outline", "topics", "goal"}
        text = bundle["system_prompt"].lower()
        assert "apollo" not in text
        assert "recommended blocks" not in text.replace("do not write a block list", "")
        assert "syllabus titles" not in text


def test_dead_course_creator_code_is_gone() -> None:
    for name in (
        "STUDIO_RULES",
        "_STUDIO_SCHEMA",
        "COURSE_SCHEMA",
        "SLICE_SCHEMA",
        "_RECOMMENDED_BLOCK",
        "studio_bundle",
        "seed_skeleton_blocks_from_recommendations",
        "course_bundle",
        "description_plan",
        "assemble_course",
        "clean_recommended_blocks",
        "format_recommended_blocks_summary",
        "ensure_description_with_recommended_blocks",
    ):
        assert not hasattr(kc_model, name), name
    for name in ("draft_course", "draft_component", "_revise_draft", "post_creator_turn", "finish_model_course"):
        assert not hasattr(kc, name), name
    with pytest.raises(ImportError):
        __import__("app.kc_syllabus")


def test_there_is_one_block_catalog() -> None:
    types = set(ALL_BLOCK_TYPES)
    assert set(block_catalog.BLOCK_LABELS) == types
    assert set(block_catalog.BLOCK_BANNER_LABELS) == types
    assert set(block_catalog.BLOCK_SHORT_LABELS) == types
    assert set(block_catalog.BLOCK_FIELDS) == types
    assert set(block_catalog.BLOCK_AUTHORING_RULES) == types
    assert set(block_catalog.BLOCK_DATA_SCHEMAS) == types
    assert kc_model.BLOCK_LABELS is block_catalog.BLOCK_LABELS
    assert kc.BLOCK_LABELS is block_catalog.BLOCK_LABELS
    assert kc.BLOCK_FIELDS is block_catalog.BLOCK_FIELDS
    assert kc.BLOCK_BANNER_LABELS is block_catalog.BLOCK_BANNER_LABELS


def _stage(course_id: str, stage: str, result: dict | None = None, **extra):
    if result is None:
        return client.post(f"/kc/courses/{course_id}/pipeline/{stage}/prompt", json={"model": "gpt-4.1", **extra})
    return client.post(f"/kc/courses/{course_id}/pipeline/{stage}", json={"result": result, **extra})


def test_the_staged_pipeline_runs_end_to_end_and_the_creator_gets_sibling_context() -> None:
    _wipe_zz()
    created = client.post(
        "/kc/courses",
        json={
            "code": "zz-pipe",
            "title": "Triangle congruence",
            "description": "",
            "audience": "12-14",
            "kind": "mastery",
            "intake": {"depth": "intro", "must_cover": "angle sum"},
        },
    )
    assert created.status_code == 200, created.text
    course_id = created.json()["id"]
    try:
        assert created.json()["intake"]["depth"] == "intro"
        state = client.get(f"/kc/courses/{course_id}/pipeline").json()
        assert state["stage"] == "brief"
        assert state["missing"] and "by the end the child can" in state["missing"][0]
        refused = _stage(course_id, "brief")
        assert refused.status_code == 422
        assert "before drafting" in refused.json()["detail"]

        patched = client.patch(f"/kc/courses/{course_id}", json={"description": OUTCOME})
        assert patched.status_code == 200, patched.text
        prompt = _stage(course_id, "brief")
        assert prompt.status_code == 200, prompt.text
        assert OUTCOME in prompt.json()["system_prompt"]
        assert _stage(course_id, "blueprint").status_code == 409

        asked = _stage(
            course_id,
            "brief",
            {"brief": "A course on triangle congruence for twelve to fourteen year olds. " * 2, "questions": ["Which grade?"]},
        )
        assert asked.status_code == 200, asked.text
        assert asked.json()["stage"] == "questions"
        assert asked.json()["next"] is None
        assert _stage(course_id, "blueprint").status_code == 409
        answered = client.post(
            f"/kc/courses/{course_id}/pipeline/answers",
            json={"answers": [{"question": "Which grade?", "answer": "Grade 7"}]},
        )
        assert answered.status_code == 200, answered.text
        redo = _stage(course_id, "brief")
        assert "- Which grade? Grade 7" in redo.json()["system_prompt"]
        briefed = _stage(
            course_id,
            "brief",
            {"brief": "A course on triangle congruence for grade seven learners. " * 2, "questions": ["Again?"]},
        )
        assert briefed.json()["stage"] == "blueprint"
        assert briefed.json()["questions"] == []
        assert briefed.json()["next"] == {"stage": "blueprint", "unit": None}

        planned = _stage(course_id, "blueprint")
        assert planned.status_code == 200
        assert "Return between 4 and 6 components." in planned.json()["system_prompt"]
        short = _stage(course_id, "blueprint", _model_blueprint(8))
        assert short.status_code == 422
        stored = _stage(course_id, "blueprint", _model_blueprint(5))
        assert stored.status_code == 200, stored.text
        body = stored.json()
        assert body["stage"] == "edit_blueprint"
        assert body["next"] is None
        assert _stage(course_id, "unit", unit=0).status_code == 409

        blueprint = body["blueprint"]
        blueprint["units"][0]["components"][0]["title"] = "Why angles add up"
        approved = client.put(
            f"/kc/courses/{course_id}/pipeline/blueprint", json={"blueprint": blueprint, "approve": True}
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["next"] == {"stage": "unit", "unit": 0}
        rows = [item for unit in approved.json()["blueprint"]["units"] for item in unit["components"]]
        codes = [item["code"] for item in rows]
        assert rows[0]["title"] == "Why angles add up"

        first_codes = [item["code"] for item in approved.json()["blueprint"]["units"][0]["components"]]
        unit_one = {"components": [{"code": code, "description": _sentences(code)} for code in first_codes]}
        too_early = _stage(course_id, "unit", unit_one, unit=1)
        assert too_early.status_code == 409
        broken = _stage(course_id, "unit", {"components": [{"code": first_codes[0], "description": "Too short."}]}, unit=0)
        assert broken.status_code == 422
        still = client.get(f"/kc/courses/{course_id}/pipeline").json()
        assert still["units_done"] == 0 and still["next"] == {"stage": "unit", "unit": 0}
        written = _stage(course_id, "unit", unit_one, unit=0)
        assert written.status_code == 200, written.text
        assert written.json()["units_done"] == 1
        assert written.json()["next"] == {"stage": "unit", "unit": 1}

        second = _stage(course_id, "unit", unit=1)
        assert second.status_code == 200
        assert f"- {first_codes[0]}: {_sentences(first_codes[0])}" in second.json()["system_prompt"]
        rest = [item["code"] for item in approved.json()["blueprint"]["units"][1]["components"]]
        unit_two = {"components": [{"code": code, "description": _sentences(code)} for code in rest]}
        done = _stage(course_id, "unit", unit_two, unit=1)
        assert done.json()["next"] == {"stage": "review", "unit": None}

        review = {"checks": _ok_checks(), "outcomes": None, "revisions": [], "additions": []}
        reviewed = _stage(course_id, "review", review)
        assert reviewed.status_code == 200, reviewed.text
        final = reviewed.json()
        assert final["stage"] == "draft"
        draft = final["draft"]["components"]
        assert [item["code"] for item in draft] == codes
        assert all("Recommended blocks" not in item["description"] for item in draft)
        assert draft[1]["prerequisite_codes"] == [codes[0]]
        assert all("outline" not in item and "topics" not in item for item in draft)

        pushed = client.post(f"/kc/courses/{course_id}/push", json={"components": draft})
        assert pushed.status_code == 200, pushed.text
        nodes = pushed.json()["components"]
        assert [item["code"] for item in nodes] == codes
        assert nodes[1]["prerequisite_codes"] == [codes[0]]
        assert nodes[0]["description"] == draft[0]["description"]
        assert client.get(f"/kc/courses/{course_id}/pipeline").json()["pushed"] is True

        creator = client.post(
            f"/kc/nodes/{nodes[1]['id']}/creator-prompt",
            json={"message": "Create Draft", "model": "gpt-4.1"},
        )
        assert creator.status_code == 200, creator.text
        system = creator.json()["system_prompt"]
        assert "Course brief:" in system and "grade seven learners" in system
        assert "Course outcomes:" in system and "- Explain why SSA fails." in system
        assert "Position: component 2 of 5, unit 1 of 2 (Angles)" in system
        assert f"Builds on: {codes[0]} (Why angles add up)" in system
        assert f"Leads to: {codes[2]} (Idea 3)" in system
        assert f"- {codes[0]}: Why angles add up - Teaches idea 1." in system
        assert f"- {codes[4]}: Idea 5 - Teaches idea 5." in system
        enum = creator.json()["schema"]["properties"]["misconceptions"]["items"]["properties"]["broken_kc"]["enum"]
        assert enum == [code for code in codes if code != codes[1]]

        reset = client.delete(f"/kc/courses/{course_id}/pipeline")
        assert reset.status_code == 200
        assert reset.json()["stage"] == "brief"
        assert client.get(f"/kc/courses/{course_id}").json()["brief"] == ""
    finally:
        _wipe_zz()


def test_changing_the_outcome_clears_the_brief() -> None:
    _wipe_zz()
    created = client.post(
        "/kc/courses",
        json={"code": "zz-pipe", "title": "Triangle congruence", "description": OUTCOME, "audience": "12-14", "kind": "mastery"},
    )
    course_id = created.json()["id"]
    try:
        brief = "A course on triangle congruence for twelve to fourteen year olds. " * 2
        stored = _stage(course_id, "brief", {"brief": brief, "questions": []})
        assert stored.status_code == 200, stored.text
        assert stored.json()["stage"] == "blueprint"
        kept = client.patch(f"/kc/courses/{course_id}", json={"allowed_block_types": ["topic_goal", "mcq"]})
        assert kept.json()["brief"].startswith("A course on triangle congruence")
        changed = client.patch(f"/kc/courses/{course_id}", json={"description": OUTCOME + " And name the rule."})
        assert changed.status_code == 200, changed.text
        assert changed.json()["brief"] == ""
        assert client.get(f"/kc/courses/{course_id}/pipeline").json()["stage"] == "brief"
    finally:
        _wipe_zz()


FIVE = [
    ("3.NF.A.1", "Understand a fraction 1/b as the quantity formed by 1 part when a whole is partitioned into b equal parts."),
    ("3.NF.A.2", "Understand a fraction as a number on the number line."),
    ("3.NF.A.3", "Explain equivalence of fractions and compare fractions by reasoning about their size."),
    ("3.NF.A.4", "Understand a fraction a/b as a multiple of 1/b."),
    ("3.NF.A.5", "Express whole numbers as fractions, and recognize fractions that are equivalent to whole numbers."),
]


def _five_text() -> str:
    return "\n".join(f"{code} {text}" for code, text in FIVE)


def _five_plan() -> dict:
    plan = _model_blueprint(5)
    codes = [code for code, _text in FIVE]
    rows = [item for unit in plan["units"] for item in unit["components"]]
    rows[0]["standards"] = [codes[0], codes[1]]
    rows[1]["standards"] = [codes[2]]
    rows[2]["standards"] = [codes[3]]
    rows[3]["standards"] = [codes[3]]
    rows[4]["standards"] = []
    return plan


def test_a_pasted_standard_is_the_authority_and_a_gap_is_marked() -> None:
    sample = (
        "3.NF.A.1 Understand a fraction 1/b as the quantity formed by 1 part when a whole is partitioned into b equal parts.\n"
        "3.NF.A.2 Understand a fraction as a number on the number line.\n"
        "3.NF.A.3 Explain equivalence of fractions and compare fractions by reasoning about their size."
    )
    parsed = parse_standard_text(sample)
    assert [item["code"] for item in parsed] == ["3.NF.A.1", "3.NF.A.2", "3.NF.A.3"]
    assert len(parse_standard_text("\n".join(f"{index}. Topic {index}." for index in range(1, 43)))) == 42
    with pytest.raises(ValueError, match="120"):
        parse_standard_text("\n".join(f"s{index} Statement {index}." for index in range(121)))

    intake = clean_intake({"standard": "common_core_math", "standard_grade": "3", "standard_text": _five_text()})
    statements = statements_from_intake(intake)
    assert [item["code"] for item in statements] == [code for code, _text in FIVE]
    course = _course(intake=intake, statements=statements)
    brief = brief_bundle(course=course, answers=[], model="gpt-4.1")
    assert "Do not add, drop, or rewrite" in brief["system_prompt"]
    assert "3.NF.A.1" in brief["system_prompt"]
    assert brief["schema"]["required"] == ["brief", "questions"]
    recalled = brief_bundle(
        course=_course(intake=clean_intake({"standard": "ngss", "standard_grade": "5"})),
        answers=[],
        model="gpt-4.1",
    )
    assert "recall the statements" in recalled["system_prompt"]
    assert "should be checked" in recalled["system_prompt"]
    assert recalled["schema"]["required"] == ["brief", "questions", "statements"]
    plain = brief_bundle(course=_course(), answers=[], model="gpt-4.1")
    assert "Do not invent a curriculum standard." in plain["system_prompt"]

    planned = blueprint_bundle(course=course, brief="B" * 50, model="gpt-4.1")
    assert "3.NF.A.5" in planned["system_prompt"]
    required = planned["schema"]["properties"]["units"]["items"]["properties"]["components"]["items"]["required"]
    assert required == ["ref", "title", "summary", "prerequisites", "standards"]
    built = assemble_blueprint(_five_plan(), bounds=(4, 6), taken=set(), make_code=_slug, statements=statements)
    matrix = coverage_matrix(statements, built)
    assert matrix["gaps"] == ["3.NF.A.5"]
    assert matrix["extensions"]
    assert any(row["once_without_review"] for row in matrix["rows"])
    extension = next(
        item["code"] for unit in built["units"] for item in unit["components"] if item["extension"]
    )
    assert extension in matrix["extensions"]
    review = review_bundle(
        course=course,
        brief="B" * 50,
        blueprint=built,
        descriptions={item["code"]: _sentences(item["title"]) for unit in built["units"] for item in unit["components"]},
        model="gpt-4.1",
    )
    assert "touched lightly" in review["system_prompt"]
    assert "standards" in review["schema"]["properties"]["additions"]["items"]["required"]


def test_a_pasted_standard_pauses_for_a_check_and_a_gapped_draft_can_be_pushed() -> None:
    _wipe_zz()
    created = client.post(
        "/kc/courses",
        json={
            "code": "zz-std",
            "title": "Fractions",
            "description": OUTCOME,
            "audience": "9-11",
            "kind": "mastery",
            "intake": {
                "depth": "intro",
                "standard": "common_core_math",
                "standard_grade": "3",
                "standard_text": _five_text(),
            },
        },
    )
    assert created.status_code == 200, created.text
    course_id = created.json()["id"]
    try:
        assert [item["code"] for item in created.json()["standards"]] == [code for code, _text in FIVE]
        stored = _stage(
            course_id,
            "brief",
            {"brief": "A grade three course on fractions as numbers on the line. " * 2, "questions": []},
        )
        assert stored.status_code == 200, stored.text
        assert stored.json()["stage"] == "standards"
        assert stored.json()["next"] is None
        assert "Common Core (math), 3." in stored.json()["brief"]
        assert _stage(course_id, "blueprint").status_code == 409

        edited = client.put(
            f"/kc/courses/{course_id}/pipeline/standards",
            json={
                "confirm": True,
                "statements": [
                    {"code": code, "text": text if code != "3.NF.A.2" else "Understand a fraction as a number on the number line, in grade three."}
                    for code, text in FIVE
                ],
            },
        )
        assert edited.status_code == 200, edited.text
        assert edited.json()["stage"] == "blueprint"
        assert "grade three" in edited.json()["standards"][1]["text"]
        prompt = _stage(course_id, "blueprint")
        assert prompt.status_code == 200, prompt.text
        assert "3.NF.A.5" in prompt.json()["system_prompt"]

        planned = _stage(course_id, "blueprint", _five_plan())
        assert planned.status_code == 200, planned.text
        body = planned.json()
        assert "3.NF.A.5" in body["coverage"]["gaps"]
        assert body["coverage"]["extensions"]
        approved = client.put(
            f"/kc/courses/{course_id}/pipeline/blueprint",
            json={"blueprint": body["blueprint"], "approve": True},
        )
        assert approved.status_code == 200, approved.text
        for index, unit in enumerate(approved.json()["blueprint"]["units"]):
            unit_codes = [item["code"] for item in unit["components"]]
            written = _stage(
                course_id,
                "unit",
                {"components": [{"code": code, "description": _sentences(code)} for code in unit_codes]},
                unit=index,
            )
            assert written.status_code == 200, written.text
        reviewed = _stage(course_id, "review", {"checks": _ok_checks(), "outcomes": None, "revisions": [], "additions": []})
        assert reviewed.status_code == 200, reviewed.text
        final = reviewed.json()
        assert final["stage"] == "draft"
        assert "3.NF.A.5" in final["coverage"]["gaps"]
        draft = final["draft"]["components"]
        extension = next(item for item in draft if item["extension"])
        assert extension["standards"] == []
        pushed = client.post(f"/kc/courses/{course_id}/push", json={"components": draft})
        assert pushed.status_code == 200, pushed.text
        nodes = pushed.json()["components"]
        by_code = {item["code"]: item for item in nodes}
        assert by_code[extension["code"]]["standards"] == []
        covered = next(item for item in draft if "3.NF.A.1" in item["standards"])
        assert by_code[covered["code"]]["standards"] == covered["standards"]
        creator = client.post(
            f"/kc/nodes/{by_code[extension['code']]['id']}/creator-prompt",
            json={"message": "Create Draft", "model": "gpt-4.1"},
        )
        assert "This component is an extension." in creator.json()["system_prompt"]
        covering = client.post(
            f"/kc/nodes/{by_code[covered['code']]['id']}/creator-prompt",
            json={"message": "Create Draft", "model": "gpt-4.1"},
        )
        assert "Standard codes this component covers: 3.NF.A.1, 3.NF.A.2." in covering.json()["system_prompt"]

        intake = created.json()["intake"]
        intake["standard_text"] = "3.NF.A.1 Understand a fraction 1/b as one part of a whole."
        changed = client.patch(f"/kc/courses/{course_id}", json={"intake": intake})
        assert changed.status_code == 200, changed.text
        assert changed.json()["brief"] == ""
        assert [item["code"] for item in changed.json()["standards"]] == ["3.NF.A.1"]
    finally:
        _wipe_zz()


def test_a_named_standard_with_no_paste_is_recalled_and_then_checked() -> None:
    _wipe_zz()
    created = client.post(
        "/kc/courses",
        json={
            "code": "zz-recall",
            "title": "Forces",
            "description": OUTCOME,
            "audience": "9-11",
            "kind": "mastery",
            "intake": {"depth": "intro", "standard": "ngss", "standard_grade": "5"},
        },
    )
    assert created.status_code == 200, created.text
    course_id = created.json()["id"]
    try:
        assert created.json()["standards"] == []
        prompt = _stage(course_id, "brief")
        assert prompt.status_code == 200, prompt.text
        assert "recall the statements" in prompt.json()["system_prompt"]
        assert prompt.json()["schema"]["required"] == ["brief", "questions", "statements"]
        missing = _stage(
            course_id,
            "brief",
            {"brief": "A grade five course on forces and motion for nine to eleven year olds. " * 2, "questions": []},
        )
        assert missing.status_code == 422
        assert "Recall the statements" in missing.json()["detail"]
        stored = _stage(
            course_id,
            "brief",
            {
                "brief": "A grade five course on forces and motion for nine to eleven year olds. " * 2,
                "questions": [],
                "statements": [
                    {"code": "5-PS2-1", "text": "Support an argument that the gravitational force exerted by Earth on objects is directed down."},
                    {"code": "3-PS2-1", "text": "Plan and conduct an investigation to compare the effects of different strengths of pushes and pulls."},
                ],
            },
        )
        assert stored.status_code == 200, stored.text
        body = stored.json()
        assert body["stage"] == "standards"
        assert body["standards_source"] == "recalled"
        assert "recalled and should be checked" in body["brief"]
        assert [item["code"] for item in body["standards"]] == ["5-PS2-1", "3-PS2-1"]
        confirmed = client.put(
            f"/kc/courses/{course_id}/pipeline/standards",
            json={
                "confirm": True,
                "statements": [
                    "5-PS2-1 Support an argument that the gravitational force exerted by Earth on objects is directed down.",
                    "3-PS2-1 Plan and conduct an investigation to compare the effects of different strengths of pushes and pulls.",
                ],
            },
        )
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["stage"] == "blueprint"
        assert confirmed.json()["standards"][0]["code"] == "5-PS2-1"
    finally:
        _wipe_zz()


def test_model_fields_helper_still_matches_the_creator_schema() -> None:
    assert set(_model_fields()) == set(kc_model.CREATOR_SCHEMA["required"])


def test_a_pasted_syllabus_is_one_component_per_topic_and_not_clamped() -> None:
    topics = [f"{index}. Topic {index} about scarcity and choice." for index in range(1, 43)]
    text = "Unit 1: Basic concepts\n" + "\n".join(topics[:10]) + "\nUnit 2: Markets\n" + "\n".join(topics[10:])
    intake = clean_intake({"depth": "curriculum", "align_syllabus": True, "source_text": text})
    statements = statements_from_intake(intake)
    assert len(statements) == 42
    assert all(not item["text"].lower().startswith("unit ") for item in statements)
    assert component_range(kind="mastery", minutes=None, intake=intake, statements=statements) == (42, 42)
    assert MAX_COMPONENTS == 100
    prompt = blueprint_bundle(
        course=_course(intake=intake, statements=statements), brief="B" * 50, model="gpt-4.1"
    )["system_prompt"]
    assert "Return exactly 42 components." in prompt
    assert "One component per statement" in prompt
    assert "Unit 1: Basic concepts" in prompt
    assert "Unit 2: Markets" in prompt
    wide = clean_intake(
        {
            "depth": "standard",
            "standard": "other",
            "standard_grade": "12",
            "standard_name": "AP Macroeconomics",
            "standard_text": "\n".join(topics),
        }
    )
    assert component_range(kind="mastery", minutes=None, intake=wide, statements=statements_from_intake(wide)) == (42, 42)
    with pytest.raises(ValueError, match="100"):
        clean_intake({"component_count": 101})


def test_a_42_unit_syllabus_is_stored_as_tracked_statements_and_a_matching_blueprint() -> None:
    """No model call. A 42-unit paste is accepted, tracked, and planned one component per topic."""
    lines = []
    for index in range(1, 43):
        lines.append(f"Unit {index}: Topic {index}")
        lines.append(f"{index}. Topic {index} about scarcity and choice.")
    text = "\n".join(lines)
    assert MAX_STATEMENTS == 120
    intake = clean_intake({"depth": "curriculum", "source_text": text})
    statements = statements_from_intake(intake)
    assert len(statements) == 42
    assert len(statements) > 40
    assert component_range(kind="mastery", minutes=None, intake=intake, statements=statements) == (42, 42)
    _wipe_zz()
    created = client.post(
        "/kc/courses",
        json={
            "code": "zz-scale",
            "title": "AP Macroeconomics",
            "description": OUTCOME,
            "audience": "15-17",
            "kind": "mastery",
            "intake": {"depth": "curriculum", "source_text": text},
        },
    )
    assert created.status_code == 200, created.text
    course_id = created.json()["id"]
    try:
        brief = _stage(
            course_id,
            "brief",
            {"brief": "A course that follows the pasted macroeconomics syllabus, one topic at a time. " * 2, "questions": []},
        )
        assert brief.status_code == 200, brief.text
        stored = brief.json()["standards"]
        assert len(stored) == 42
        assert stored[0]["text"].startswith("Topic 1 about scarcity")
        assert all(not item["text"].lower().startswith("unit ") for item in stored)
        confirmed = client.put(
            f"/kc/courses/{course_id}/pipeline/standards",
            json={"confirm": True, "statements": stored},
        )
        assert confirmed.status_code == 200, confirmed.text
        plan = {
            "outcomes": ["Explain scarcity.", "Use a supply curve."],
            "units": [
                {
                    "title": f"Unit {index}",
                    "summary": f"Topic {index}.",
                    "components": [
                        {
                            "ref": f"c{index}",
                            "title": f"Zz Topic {index}",
                            "summary": f"Teaches topic {index}.",
                            "prerequisites": [f"c{index - 1}"] if index > 1 else [],
                            "standards": [stored[index - 1]["code"]],
                        }
                    ],
                }
                for index in range(1, 43)
            ],
        }
        saved = _stage(course_id, "blueprint", plan)
        assert saved.status_code == 200, saved.text
        units = saved.json()["blueprint"]["units"]
        assert len(units) == 42
        assert sum(len(unit["components"]) for unit in units) == 42
        assert units[0]["components"][0]["standards"] == [stored[0]["code"]]
        assert units[41]["title"] == "Unit 42"
    finally:
        _wipe_zz()


def test_an_empty_unit_is_dropped_and_chat_keeps_untouched_descriptions() -> None:
    stored = assemble_blueprint(_model_blueprint(5), bounds=(4, 6), taken=set(), make_code=_slug)
    edited = json.loads(json.dumps(stored))
    edited["units"][1]["components"] = []
    cleaned = clean_blueprint_edit(edited, taken=set(), make_code=_slug)
    assert [unit["title"] for unit in cleaned["units"]] == ["Angles"]
    notes = {item["code"]: _sentences(item["title"]) for unit in stored["units"] for item in unit["components"]}
    kept = stored["units"][0]
    proposal = {
        "reply": "Removed unit 2.",
        "changed_codes": [],
        "outcomes": stored["outcomes"],
        "units": [
            {
                "title": kept["title"],
                "summary": kept["summary"],
                "components": [
                    {
                        "code": item["code"],
                        "title": item["title"],
                        "summary": item["summary"],
                        "prerequisites": item["prerequisites"],
                        "standards": [],
                        "description": None,
                    }
                    for item in kept["components"]
                ],
            }
        ],
    }
    interpreted = interpret_chat(proposal, blueprint=stored, descriptions=notes, statements=[], taken=set(), make_code=_slug)
    assert interpreted["changes"]
    assert any(line.startswith("Removed") for line in interpreted["changes"])
    kept_codes = [item["code"] for item in kept["components"]]
    assert all(interpreted["descriptions"][code] == notes[code] for code in kept_codes)
    assert "idea-4" not in interpreted["descriptions"] or interpreted["descriptions"].get("idea-4") != notes.get("idea-4")
    bundle = chat_bundle(
        course=_course(statements=[]),
        brief="A brief about triangles that is long enough.",
        blueprint=stored,
        descriptions=notes,
        statements=[],
        components=[],
        messages=[{"role": "user", "content": "Delete unit 2."}],
        model="gpt-4.1",
    )
    assert "Delete unit 2." in bundle["user_prompt"]
    assert "Course schema:" in bundle["system_prompt"]
    assert INSTRUCTION_RULES not in bundle["system_prompt"]
    assert "Group components into units of 3 to 8" not in bundle["system_prompt"]


def test_delete_unit_and_start_over_can_clear_pushed_components() -> None:
    _wipe_zz()
    created = client.post(
        "/kc/courses",
        json={
            "code": "zz-units",
            "title": "Triangle congruence",
            "description": OUTCOME,
            "audience": "12-14",
            "kind": "mastery",
            "intake": {"depth": "intro"},
        },
    )
    assert created.status_code == 200, created.text
    course_id = created.json()["id"]
    try:
        brief = "A course on triangle congruence for twelve to fourteen year olds. " * 2
        assert _stage(course_id, "brief", {"brief": brief, "questions": []}).status_code == 200
        planned = _stage(course_id, "blueprint", _model_blueprint(5, title_prefix="Zz Idea"))
        assert planned.status_code == 200, planned.text
        blueprint = planned.json()["blueprint"]
        pushed = client.post(
            f"/kc/courses/{course_id}/push",
            json={
                "components": [
                    {
                        "code": item["code"],
                        "title": item["title"],
                        "description": _sentences(item["title"]),
                        "prerequisite_codes": item["prerequisites"],
                    }
                    for unit in blueprint["units"]
                    for item in unit["components"]
                ]
            },
        )
        assert pushed.status_code == 200, pushed.text
        before = client.get(f"/kc/courses/{course_id}/structure").json()
        assert [group["title"] for group in before["groups"]] == ["Angles", "Congruence"]
        removed_codes = [item["code"] for item in blueprint["units"][0]["components"]]
        deleted = client.delete(f"/kc/courses/{course_id}/units/0")
        assert deleted.status_code == 200, deleted.text
        assert [unit["title"] for unit in deleted.json()["blueprint"]["units"]] == ["Congruence"]
        structure = client.get(f"/kc/courses/{course_id}/structure").json()
        assert [group["title"] for group in structure["groups"]] == ["Congruence"]
        assert all(row["code"] not in removed_codes for group in structure["groups"] for row in group["components"])
        kept = client.get(f"/kc/courses/{course_id}").json()["components"]
        assert kept
        draft_only = client.delete(f"/kc/courses/{course_id}/pipeline")
        assert draft_only.status_code == 200
        assert client.get(f"/kc/courses/{course_id}").json()["components"]
        # The blueprint is gone, so put the components back on a fresh draft and clear them.
        assert _stage(course_id, "brief", {"brief": brief, "questions": []}).status_code == 200
        again = _stage(course_id, "blueprint", _model_blueprint(5, title_prefix="Zz Idea"))
        assert again.status_code == 200, again.text
        cleared = client.delete(f"/kc/courses/{course_id}/pipeline?components=true")
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["stage"] == "brief"
        assert client.get(f"/kc/courses/{course_id}").json()["components"] == []
        assert client.get(f"/kc/courses/{course_id}/structure").json()["groups"] == []
    finally:
        _wipe_zz()


def test_chat_apply_changes_the_same_course_and_preview_does_not() -> None:
    _wipe_zz()
    created = client.post(
        "/kc/courses",
        json={
            "code": "zz-chat",
            "title": "Triangle congruence",
            "description": OUTCOME,
            "audience": "12-14",
            "kind": "mastery",
            "intake": {"depth": "intro"},
        },
    )
    course_id = created.json()["id"]
    try:
        brief = "A course on triangle congruence for twelve to fourteen year olds. " * 2
        assert _stage(course_id, "brief", {"brief": brief, "questions": []}).status_code == 200
        planned = _stage(course_id, "blueprint", _model_blueprint(5, title_prefix="Zz Idea"))
        assert planned.status_code == 200, planned.text
        blueprint = planned.json()["blueprint"]
        kept = blueprint["units"][0]
        proposal = {
            "reply": "Removed the congruence unit.",
            "changed_codes": [],
            "outcomes": blueprint["outcomes"],
            "units": [
                {
                    "title": kept["title"],
                    "summary": kept["summary"],
                    "components": [
                        {
                            "code": item["code"],
                            "title": item["title"],
                            "summary": item["summary"],
                            "prerequisites": item["prerequisites"],
                            "standards": [],
                            "description": _sentences(item["title"]),
                        }
                        for item in kept["components"]
                    ],
                }
            ],
        }
        preview = client.post(f"/kc/courses/{course_id}/chat/preview", json={"proposal": proposal})
        assert preview.status_code == 200, preview.text
        assert any("Removed" in line for line in preview.json()["changes"])
        assert len(client.get(f"/kc/courses/{course_id}/pipeline").json()["blueprint"]["units"]) == 2
        prompt = client.post(
            f"/kc/courses/{course_id}/chat/prompt",
            json={"model": "gpt-4.1", "messages": [{"role": "user", "content": "Delete unit 2."}]},
        )
        assert prompt.status_code == 200, prompt.text
        assert "Delete unit 2." in prompt.json()["user_prompt"]
        assert "Angles" in prompt.json()["system_prompt"]
        assert INSTRUCTION_RULES not in prompt.json()["system_prompt"]
        applied = client.post(f"/kc/courses/{course_id}/chat/apply", json={"proposal": proposal})
        assert applied.status_code == 200, applied.text
        assert [unit["title"] for unit in applied.json()["pipeline"]["blueprint"]["units"]] == ["Angles"]
        assert applied.json()["pipeline"]["brief"].startswith("A course on triangle congruence")
    finally:
        _wipe_zz()
