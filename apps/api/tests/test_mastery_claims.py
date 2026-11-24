"""Mastery claims and block recipes. No database and no model call.

An empty spec keeps today's block list. A new or regenerated component
with a spec drafts the recipe and tags each block with claim ids.
"""

from types import SimpleNamespace

from app.block_catalog import ARCHETYPE_RECIPES, ARCHETYPES, SKILL_KEYS, recipe_block_types
from app.kc import clean_model_component
from app.kc_course_io import _clean_component, _export_component, normalize_blocks
from app.kc_model import creator_bundle
from app.kc_pipeline import (
    PLAN_RULES,
    UNIT_MASTERY_RULES,
    apply_unit_mastery,
    assemble_blueprint,
    blueprint_bundle,
    clean_unit,
    unit_bundle,
    unit_schema,
)
from app.mastery import (
    assign_mastery_spec,
    blocks_for_draft,
    draft_recipe_blocks,
    parse_mastery_spec,
)
from app.models import default_allowed_block_types
from tests.test_kc_pipeline import _course, _model_blueprint, _sentences, _slug

ALLOWED = default_allowed_block_types()


def _spec(**overrides: object) -> dict:
    body = {
        "archetype": "causal_systems",
        "claims": [
            {"id": "cause", "statement": "Explain why the system changes."},
            {"id": "use", "statement": "Use the cause on a new case."},
        ],
        "target_level": 0,
        "skills": ["causes", "explaining"],
    }
    body.update(overrides)
    return body


def _component(title: str, description: str, *, spec: dict | None = None, archetype: str = ""):
    node = SimpleNamespace(id="n1", code="idea", title=title, description=description, archetype=archetype)
    draft = {
        "title": title,
        "description": "A short summary of the component.",
        "outline": "Teach the idea, then check it.",
        "core_truth": "The idea holds.",
        "blocks": [
            {
                "id": "blk_goal",
                "type": "topic_goal",
                "data": {"topic": title, "goal": "Say the idea in your own words."},
            }
        ],
        "misconceptions": [],
        "prerequisite_codes": [],
        "encompasses_codes": [],
    }
    if spec is not None:
        draft["mastery_spec"] = spec
    shaped, _repairs, _mix = clean_model_component(
        node,
        draft,
        [],
        ALLOWED,
        audience="12-14",
        course_title=title,
        course_description=description,
        archetype=archetype,
    )
    return shaped


def test_the_five_recipes_keep_order_and_the_allowed_filter() -> None:
    assert list(ARCHETYPE_RECIPES) == list(ARCHETYPES)
    assert ARCHETYPE_RECIPES["procedural_conceptual"] == (
        "curiosity",
        "explanation",
        "worked_example",
        "spot_the_flaw",
        "mcq",
    )
    assert ARCHETYPE_RECIPES["causal_systems"] == (
        "curiosity",
        "explanation",
        "case_study",
        "spot_the_flaw",
        "teach_back",
    )
    assert ARCHETYPE_RECIPES["textual_interpretive"] == (
        "curiosity",
        "passage_ela",
        "case_study",
        "socratic",
        "teach_back",
    )
    assert ARCHETYPE_RECIPES["factual_terminological"] == (
        "curiosity",
        "explanation",
        "mcq",
        "retrieval_check",
    )
    assert ARCHETYPE_RECIPES["normative_synthesis"] == ("case_study", "socratic", "teach_back")
    assert recipe_block_types("causal_systems", ["passage_ela", "explanation", "curiosity"]) == [
        "curiosity",
        "explanation",
    ]
    assert SKILL_KEYS == (
        "evidence",
        "perspectives",
        "causes",
        "inquiry",
        "errors",
        "transfer",
        "explaining",
        "calibration",
    )


def test_blueprint_assigns_claims_before_any_block_list() -> None:
    for title, summary, expected in (
        ("How AI works", "How a model turns a prompt into a reply.", "causal_systems"),
        ("Psychology", "How memory and attention work in the mind.", "causal_systems"),
        ("Reading comprehension", "Cite evidence from an informational text.", "textual_interpretive"),
        ("Solve a linear equation", "Calculate the unknown.", "procedural_conceptual"),
        ("Define scarcity", "The vocabulary of a limited resource.", "factual_terminological"),
    ):
        spec = assign_mastery_spec(None, title=title, summary=summary)
        assert spec["archetype"] == expected
        assert 2 <= len(spec["claims"]) <= 3
        assert all(isinstance(item["statement"], str) and item["statement"] for item in spec["claims"])
        assert spec["target_level"] in (0, 1, 2, 3)
        assert set(spec["skills"]) <= set(SKILL_KEYS)
        assert "icap" not in spec and "min_icap" not in spec
        assert "blocks" not in spec

    ela = assign_mastery_spec(None, title="Idea", summary="A step.", course_text="Grade 6 ELA")
    assert ela["archetype"] == "textual_interpretive"

    blueprint = assemble_blueprint(_model_blueprint(5), bounds=(4, 6), taken=set(), make_code=_slug)
    rows = [item for unit in blueprint["units"] for item in unit["components"]]
    assert all("blocks" not in item and "_mastery_raw" not in item for item in rows)
    assert [item["mastery_spec"]["archetype"] for item in rows] == [
        "causal_systems",
        "causal_systems",
        "causal_systems",
        "causal_systems",
        "normative_synthesis",
    ]

    supplied = _model_blueprint(5)
    supplied["units"][1]["components"][-1]["mastery_spec"] = _spec(archetype="procedural_conceptual")
    kept = assemble_blueprint(supplied, bounds=(4, 6), taken=set(), make_code=_slug)
    last = [item for unit in kept["units"] for item in unit["components"]][-1]
    assert last["mastery_spec"]["archetype"] == "procedural_conceptual"
    assert last["mastery_spec"]["target_level"] == 0
    assert [item["id"] for item in last["mastery_spec"]["claims"]] == ["cause", "use"]
    assert last["mastery_spec"]["skills"] == ["causes", "explaining"]
    assert "icap" not in last["mastery_spec"]

    bundle = blueprint_bundle(course=_course(), brief="A brief about triangles.", model="gpt-4.1")
    prompt = bundle["system_prompt"].lower()
    assert PLAN_RULES in bundle["system_prompt"]
    assert "before any block" in prompt
    assert "that is the only level" in prompt
    assert "icap" not in prompt
    required = bundle["schema"]["properties"]["units"]["items"]["properties"]["components"]["items"]
    assert required["required"] == ["ref", "title", "summary", "mastery_spec", "prerequisites"]
    assert "blocks" not in required["properties"]
    assert "icap" not in str(required).lower()
    assert required["properties"]["mastery_spec"]["properties"]["target_level"]["maximum"] == 3

    unit = unit_schema(["idea-4", "idea-5"])
    item = unit["properties"]["components"]["items"]
    assert list(item["properties"]) == ["code", "mastery_spec", "description"]
    assert item["required"] == ["code", "mastery_spec", "description"]
    written = unit_bundle(
        course=_course(),
        brief="A brief about triangles.",
        blueprint=blueprint,
        descriptions={row["code"]: _sentences(row["title"]) for row in blueprint["units"][0]["components"]},
        unit_index=1,
        model="gpt-4.1",
    )
    assert UNIT_MASTERY_RULES in written["system_prompt"]
    assert "before any block" in written["system_prompt"].lower()


def test_a_model_spec_round_trips_and_a_second_scale_is_dropped() -> None:
    raw = _spec(target_level=0, skills=["inquiry", "evidence"])
    raw["icap"] = 5
    parsed = parse_mastery_spec(raw)
    assert parsed == {
        "archetype": "causal_systems",
        "claims": raw["claims"],
        "target_level": 0,
        "skills": ["inquiry", "evidence"],
    }
    assert assign_mastery_spec(raw, title="How AI works") == parsed
    assert assign_mastery_spec({**raw, "target_level": 5}, title="How AI works")["target_level"] == 2
    try:
        parse_mastery_spec({**raw, "target_level": 5})
    except ValueError as exc:
        assert "target_level" in str(exc)
    else:
        raise AssertionError("target_level 5 was stored")
    try:
        parse_mastery_spec({**raw, "target_level": True})
    except ValueError as exc:
        assert "target_level" in str(exc)
    else:
        raise AssertionError("a boolean level was stored")


def test_an_empty_spec_keeps_todays_blocks_and_a_recipe_tags_claims() -> None:
    stored = [
        {"id": "m", "type": "mcq", "data": {"question_stem": "Which one?"}},
        {"id": "c", "type": "curiosity", "data": {"phenomenon_hook": "Watch this."}},
        {"id": "g", "type": "topic_goal", "data": {"topic": "Memory", "goal": "Name it."}},
        {"id": "p", "type": "passage_ela", "data": {"passage_title": "Already stored"}},
    ]
    assert blocks_for_draft(_spec(), stored, regenerate=False) == stored
    assert blocks_for_draft({}, stored, regenerate=False) == stored
    assert "claim_ids" not in blocks_for_draft({}, stored, regenerate=True, course_title="Psychology")[0]

    for title, description in (
        ("Psychology", "How memory and attention work in the mind."),
        ("How AI works", "How a model turns a prompt into a reply."),
    ):
        shaped = _component(title, description, spec=_spec())
        assert [block["type"] for block in shaped["blocks"]] == list(ARCHETYPE_RECIPES["causal_systems"])
        assert "passage_ela" not in {block["type"] for block in shaped["blocks"]}
        assert "brass key" not in str(shaped).lower()
        ids = [item["id"] for item in _spec()["claims"]]
        seen: set[str] = set()
        for block in shaped["blocks"]:
            assert block["claim_ids"]
            assert set(block["claim_ids"]) <= set(ids)
            seen.update(block["claim_ids"])
        assert seen == set(ids)

    textual = _component(
        "Psychology",
        "How memory and attention work in the mind.",
        spec=_spec(archetype="textual_interpretive", skills=["evidence", "inquiry"]),
    )
    assert [block["type"] for block in textual["blocks"]] == list(ARCHETYPE_RECIPES["textual_interpretive"])
    assert "brass key" in str(textual).lower()

    ela_factual = _component(
        "Grade 7 ELA",
        "Reading comprehension of informational text.",
        spec=_spec(archetype="factual_terminological", skills=["explaining", "calibration"]),
    )
    assert "passage_ela" not in {block["type"] for block in ela_factual["blocks"]}

    empty_ela = _component("Grade 7 ELA", "Reading comprehension of informational text.")
    assert any(block["type"] == "passage_ela" for block in empty_ela["blocks"])

    fallback = blocks_for_draft(
        _spec(),
        stored[:3],
        regenerate=True,
        allowed=["topic_goal"],
        course_title="Psychology",
        course_description="How memory and attention work.",
    )
    assert [block["type"] for block in fallback] == ["mcq", "curiosity", "topic_goal"]
    assert "claim_ids" not in fallback[0]


def test_import_and_export_keep_the_spec_and_the_stored_block_order() -> None:
    order = [
        {"id": "m", "type": "mcq", "claim_ids": ["use"], "data": {"question_stem": "Which one?", "nope": 1}},
        {"id": "c", "type": "curiosity", "claim_ids": ["cause"], "data": {"phenomenon_hook": "Watch this."}},
        {"id": "g", "type": "topic_goal", "data": {"topic": "Memory", "goal": "Name it."}},
    ]
    cleaned = _clean_component(
        {"title": "Memory", "description": "How attention works.", "mastery_spec": _spec(), "blocks": order},
        [],
    )
    assert [block["type"] for block in cleaned["blocks"]] == ["mcq", "curiosity", "topic_goal"]
    assert cleaned["blocks"][0]["claim_ids"] == ["use"]
    assert cleaned["blocks"][0]["data"] == {"question_stem": "Which one?"}
    assert cleaned["mastery_spec"] == parse_mastery_spec(_spec())
    assert _clean_component(cleaned, [])["blocks"] == cleaned["blocks"]
    assert _clean_component(cleaned, [])["mastery_spec"] == cleaned["mastery_spec"]

    bare = _clean_component({"title": "Memory", "blocks": order}, [])
    assert bare["mastery_spec"] == {}
    assert [block["type"] for block in bare["blocks"]] == ["mcq", "curiosity", "topic_goal"]

    node = SimpleNamespace(
        code="memory",
        title="Memory",
        description="How attention works.",
        outline="",
        core_truth="",
        rubric=[],
        misconceptions=[],
        standards=[],
        prerequisite_codes=[],
        encompasses_codes=[],
        mastery_spec=cleaned["mastery_spec"],
        blocks=cleaned["blocks"],
    )
    exported = _export_component({"summary": "How attention works."}, node, "")
    assert exported["mastery_spec"] == cleaned["mastery_spec"]
    assert exported["blocks"] == cleaned["blocks"]
    again = _clean_component(exported, [])
    assert again["mastery_spec"] == cleaned["mastery_spec"]
    assert again["blocks"] == cleaned["blocks"]

    plain = SimpleNamespace(
        code="memory",
        title="Memory",
        description="",
        outline="",
        core_truth="",
        rubric=[],
        misconceptions=[],
        standards=[],
        prerequisite_codes=[],
        encompasses_codes=[],
        blocks=[{"id": "g", "type": "topic_goal", "data": {"topic": "Memory", "goal": "Name it."}}],
    )
    plain_export = _export_component({}, plain, "")
    assert plain_export["mastery_spec"] == {}
    assert [block["type"] for block in plain_export["blocks"]] == ["topic_goal"]
    assert "claim_ids" not in plain_export["blocks"][0]
    assert normalize_blocks(plain_export["blocks"]) == plain_export["blocks"]


def test_a_unit_reply_can_revise_claims_without_writing_blocks() -> None:
    blueprint = assemble_blueprint(_model_blueprint(5), bounds=(4, 6), taken=set(), make_code=_slug)
    codes = [item["code"] for item in blueprint["units"][1]["components"]]
    result = {
        "components": [
            {"code": code, "description": _sentences(code), "mastery_spec": _spec(archetype="factual_terminological")}
            for code in codes
        ]
    }
    assert set(clean_unit(result, codes)) == set(codes)
    updated = apply_unit_mastery(blueprint, result)
    revised = updated["units"][1]["components"][0]
    assert "blocks" not in revised
    assert revised["mastery_spec"]["archetype"] == "factual_terminological"
    assert updated["units"][0]["components"][0]["mastery_spec"] == blueprint["units"][0]["components"][0]["mastery_spec"]
    assert apply_unit_mastery(blueprint, {"components": [{"code": codes[0], "description": _sentences(codes[0])}]}) == blueprint


def test_a_creator_prompt_names_the_recipe_only_when_a_spec_exists() -> None:
    empty = creator_bundle(
        course_title="Psychology",
        course_description="How memory and attention work.",
        audience="12-14",
        kind="mastery",
        minutes=None,
        node_title="Psychology",
        node_code="idea",
        node_description="How memory and attention work.",
        siblings=[],
        previous=None,
        message="Create Draft",
        model="gpt-4.1",
    )
    assert "Mastery claims are already assigned" not in empty["system_prompt"]
    filled = creator_bundle(
        course_title="Psychology",
        course_description="How memory and attention work.",
        audience="12-14",
        kind="mastery",
        minutes=None,
        node_title="Psychology",
        node_code="idea",
        node_description="How memory and attention work.",
        siblings=[],
        previous=None,
        message="Create Draft",
        model="gpt-4.1",
        mastery_spec=_spec(),
    )
    assert "Mastery claims are already assigned" in filled["system_prompt"]
    assert "curiosity, explanation, case_study, spot_the_flaw, teach_back" in filled["system_prompt"]
    assert "icap" not in filled["system_prompt"].lower()
    assert draft_recipe_blocks(_spec(), allowed=["curiosity"], course_title="Psychology")[0]["claim_ids"] == [
        "cause",
        "use",
    ]
