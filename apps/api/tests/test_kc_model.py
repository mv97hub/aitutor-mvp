"""The KC chats ask the model to plan, then to write the component."""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

from app.kc_model import (
    COURSE_RULES,
    CREATOR_RULES,
    DEFAULT_KC_CHAT_MODEL,
    DESCRIPTION_SLICE,
    KC_CHAT_MODELS,
    MAX_COMPONENTS,
    assemble_course,
    checked_discussion,
    checked_model,
    course_bundle,
    creator_bundle,
    description_plan,
    titles_are_sliced,
)

GEOMETRY = (
    "Tell congruent triangles apart, find a missing angle, and explain why "
    "two sides and a non-included angle do not prove congruence."
)


def _row(title: str) -> dict:
    return {
        "title": title,
        "description": f"A short look at {title}.",
        "outline": f"How {title} works.",
        "topics": [
            {"topic": title, "goal": f"Explain {title}"},
            {"topic": "a worked case", "goal": f"Use {title}"},
        ],
    }


def test_a_three_line_description_splits_once_and_a_summary_stays() -> None:
    from app.kc_model import split_brief

    split = split_brief("Outline: The river is blue.\nTopics: color; banks\nGoals: Recall the color; Name a bank")
    assert split == {
        "description": "The river is blue.",
        "outline": "The river is blue.",
        "topics": [
            {"topic": "color", "goal": "Recall the color"},
            {"topic": "banks", "goal": "Name a bank"},
        ],
    }
    assert split_brief("The river is blue.") is None
    uneven = split_brief("Outline: Setup.\nTopics: color; banks\nGoals: Recall the color")
    assert uneven is not None
    assert uneven["topics"] == [{"topic": "color", "goal": "Recall the color"}]
    four = split_brief(
        "Outline: The river.\n"
        "Topics: color; banks; current; source\n"
        "Goals: Recall the color; Name a bank; Say the flow; Name the source"
    )
    assert four is not None
    assert four["topics"] == [
        {"topic": "color", "goal": "Recall the color"},
        {"topic": "banks", "goal": "Name a bank"},
        {"topic": "current", "goal": "Say the flow"},
        {"topic": "source", "goal": "Name the source"},
    ]
    from app.kc_model import clean_pairs

    assert clean_pairs(four["topics"]) == four["topics"]


def test_menu_keeps_the_original_models_and_names_a_stronger_default() -> None:
    assert KC_CHAT_MODELS[:3] == ("gpt-4o-mini", "gpt-4o", "gpt-4.1-mini")
    assert DEFAULT_KC_CHAT_MODEL == "gpt-4.1"
    assert "gpt-6.1-sol" in KC_CHAT_MODELS
    assert KC_CHAT_MODELS[-1] == "~deepseek/deepseek-flash-latest"
    assert checked_model("~deepseek/deepseek-flash-latest") == "~deepseek/deepseek-flash-latest"
    assert checked_model("deepseek/deepseek-flash-latest") == "~deepseek/deepseek-flash-latest"
    assert checked_model("gpt-4o-mini") == "gpt-4o-mini"
    assert checked_model("gpt-4o") == "gpt-4o"
    assert checked_model("gpt-4.1-mini") == "gpt-4.1-mini"
    assert checked_model("gpt-4.1") == "gpt-4.1"
    assert checked_model("gpt-6.1-sol") == "gpt-6.1-sol"
    assert checked_model("") == "gpt-4.1"
    with pytest.raises(ValueError, match="not allowed"):
        checked_model("gpt-3.5-turbo")
    saved = course_bundle(
        title="Euclidean geometry",
        description=GEOMETRY,
        audience="12-14",
        kind="mastery",
        minutes=None,
        message="Draft the list",
        model="deepseek/deepseek-flash-latest",
    )
    assert saved["model"] == "~deepseek/deepseek-flash-latest"
    kept = course_bundle(
        title="Euclidean geometry",
        description=GEOMETRY,
        audience="12-14",
        kind="mastery",
        minutes=None,
        message="Draft the list",
        model="gpt-4.1",
    )
    assert kept["model"] == "gpt-4.1"


def test_course_prompt_plans_before_the_list() -> None:
    bundle = course_bundle(
        title="Euclidean geometry",
        description=GEOMETRY,
        audience="12-14",
        kind="mastery",
        minutes=None,
        message="Minimum of 10 components",
        model="gpt-6.1-sol",
    )
    prompt = bundle["system_prompt"]
    assert bundle["model"] == "gpt-6.1-sol"
    for sentence in (
        "Name the subject from the course name and the course description",
        "major ideas a strong course on that subject has to cover",
        "Do not slice the description sentence into titles",
        "Mastery is the fuller rigorous breakdown",
        "Time boxed fits the minutes",
        "Curiosity is a path through the subject",
        "minimum of 10",
        "10 distinct components",
        "A pasted title list is used as written",
        "Only after the subject and the major ideas, return the component list",
        "short outline",
        "key topics",
        "key goals",
    ):
        assert sentence in prompt
    assert COURSE_RULES.split(".")[0] in prompt
    assert "Triangle angle sum" in prompt


def test_pasted_titles_stay_and_gain_descriptions() -> None:
    titles = ["Angle sum", "Missing angle", "SAS versus SSA", "Congruence"]
    drafted = assemble_course(
        title="Euclidean geometry",
        description=GEOMETRY,
        kind="mastery",
        minutes=30,
        message="\n".join(titles),
        proposal={
            "subject": "triangle congruence",
            "major_ideas": ["angle measure", "congruence tests"],
            "components": [_row("Renamed")] * 4,
        },
    )
    assert [item["title"] for item in drafted["components"]] == titles
    assert drafted["reply"].startswith("Subject: triangle congruence.")
    assert "Major ideas a strong course" in drafted["reply"]
    assert "from the titles you listed" in drafted["reply"]
    for item in drafted["components"]:
        assert item["description"].startswith("A short look at ")
        assert item["outline"].startswith("How ")
        assert item["topics"][0]["goal"].startswith("Explain ")
        assert "Topics:" not in item["description"]


def test_sliced_description_titles_are_rejected() -> None:
    clauses = [
        "Tell congruent triangles apart",
        "find a missing angle",
        "explain why two sides and a non-included angle do not prove congruence",
    ]
    assert titles_are_sliced(GEOMETRY, clauses)
    with pytest.raises(ValueError, match="Do not slice"):
        assemble_course(
            title="Euclidean geometry",
            description=GEOMETRY,
            kind="mastery",
            minutes=None,
            message="Draft the components",
            proposal={
                "subject": "Euclidean geometry",
                "major_ideas": ["congruence", "angle sum"],
                "components": [_row(title) for title in clauses],
            },
        )


def _course_kwargs(message: str) -> dict:
    return {
        "title": "Euclidean geometry",
        "description": GEOMETRY,
        "audience": "12-14",
        "kind": "mastery",
        "minutes": None,
        "message": message,
        "model": "gpt-4.1",
    }


def test_a_requested_count_is_not_clamped_to_16() -> None:
    bundle = course_bundle(**_course_kwargs("40 components"))
    prompt = bundle["system_prompt"]
    assert MAX_COMPONENTS == 250
    assert "Return 40 distinct components" in prompt
    assert "Return 16" not in prompt
    assert bundle["pass"] == "titles"
    assert "titles" in bundle["schema"]["properties"]
    assert "Do not write outlines" in prompt
    minimum = course_bundle(**_course_kwargs("minimum of 40"))
    assert minimum["pass"] == "titles"
    assert "at least 40" in minimum["system_prompt"]
    assert "at least 16" not in minimum["system_prompt"]


def test_a_list_under_one_slice_stays_a_single_call() -> None:
    bundle = course_bundle(**_course_kwargs("17 components"))
    assert DESCRIPTION_SLICE == 25
    assert bundle["pass"] == "full"
    assert "Return 17 distinct components" in bundle["system_prompt"]
    assert "outline" in bundle["schema"]["properties"]["components"]["items"]["properties"]


def test_descriptions_are_sliced_and_the_full_list_is_checked() -> None:
    titles = [f"Topic {index:02d}" for index in range(1, 31)]
    plan = description_plan(**_course_kwargs("30 components"), titles=titles)
    assert plan["slice_size"] == DESCRIPTION_SLICE
    assert [len(item["titles"]) for item in plan["slices"]] == [25, 5]
    first = plan["slices"][0]["system_prompt"]
    assert COURSE_RULES.split(".")[0] in first
    assert "short outline" in first
    assert "Topic 01" in first
    assert "Topic 26" not in first
    assert "Topic 26" in plan["slices"][1]["system_prompt"]
    drafted = assemble_course(
        title="Euclidean geometry",
        description=GEOMETRY,
        kind="mastery",
        minutes=None,
        message="30 components",
        proposal={
            "subject": "Euclidean geometry",
            "major_ideas": ["congruence", "proof"],
            "components": [_row(title) for title in titles],
        },
    )
    assert [item["title"] for item in drafted["components"]] == titles
    assert 17 <= len(drafted["components"]) <= MAX_COMPONENTS


def test_the_full_cap_is_ten_slices_and_one_past_it_is_rejected() -> None:
    titles = [f"Topic {index:03d}" for index in range(1, 251)]
    bundle = course_bundle(**_course_kwargs("250 components"))
    assert bundle["pass"] == "titles"
    assert "Return 250 distinct components" in bundle["system_prompt"]
    plan = description_plan(**_course_kwargs("250 components"), titles=titles)
    assert [len(item["titles"]) for item in plan["slices"]] == [DESCRIPTION_SLICE] * 10
    with pytest.raises(ValueError, match="at most 250"):
        assemble_course(
            title="Euclidean geometry",
            description=GEOMETRY,
            kind="mastery",
            minutes=None,
            message="Draft the components",
            proposal={
                "subject": "Euclidean geometry",
                "major_ideas": ["congruence"],
                "components": [_row(f"Topic {index:03d}") for index in range(1, 252)],
            },
        )


def test_a_minimum_count_is_enforced() -> None:
    with pytest.raises(ValueError, match="at least 10"):
        assemble_course(
            title="Euclidean geometry",
            description=GEOMETRY,
            kind="mastery",
            minutes=None,
            message="Minimum of 10 components",
            proposal={
                "subject": "Euclidean geometry",
                "major_ideas": ["congruence"],
                "components": [_row(f"Part {index}") for index in range(4)],
            },
        )


def test_creator_prompt_goes_deep_before_the_fields() -> None:
    bundle = creator_bundle(
        course_title="Euclidean geometry",
        course_description=GEOMETRY,
        audience="12-14",
        kind="mastery",
        minutes=None,
        node_title="Triangle angle sum",
        node_code="angle-sum",
        node_description="Outline: The interior angles.\nTopics: 180 degrees\nGoals: State the sum",
        other_codes=["missing-angle"],
        previous=None,
        message="Draft this component.",
        model="gpt-4.1",
    )
    prompt = bundle["system_prompt"]
    assert "You are an expert curriculum maker for this knowledge component and the course kind." in prompt
    assert "Recommend every field that can be entered" in prompt
    assert "description, title, outline, core_truth, an ordered blocks[] sequence" in prompt
    assert "Mastery is the fuller rigorous breakdown" in prompt
    assert "description" in bundle["schema"]["required"]
    assert "Outline: The interior angles." in prompt
    assert "outline" in bundle["schema"]["required"]
    assert "blocks" in bundle["schema"]["required"]
    blocks = bundle["schema"]["properties"]["blocks"]
    assert blocks["type"] == "array"
    assert "topics" not in bundle["schema"]["properties"]
    assert "Go into the topic before you fill the outline, the core truth, the blocks, and the links." in prompt
    assert "Do not change how an answer is scored" in prompt
    assert CREATOR_RULES.split(".")[0] in prompt
    with pytest.raises(ValueError, match="before you fill"):
        checked_discussion("Here is the draft.", "Triangle angle sum")
    kept = checked_discussion(
        "Triangle angle sum is the fact that the three interior angles make a straight line, "
        "which is why a missing angle is the rest of 180 degrees.",
        "Triangle angle sum",
    )
    assert kept.startswith("Triangle angle sum")


def test_creator_schema_limits_broken_kc_to_the_other_codes() -> None:
    bundle = creator_bundle(
        course_title="Euclidean geometry",
        course_description=GEOMETRY,
        audience="12-14",
        kind="mastery",
        minutes=None,
        node_title="Triangle angle sum",
        node_code="angle-sum",
        node_description="Outline: The interior angles.\nTopics: 180 degrees\nGoals: State the sum",
        other_codes=["missing-angle", "congruence"],
        previous=None,
        message="Draft this component.",
        model="gpt-4.1",
    )
    broken = bundle["schema"]["properties"]["misconceptions"]["items"]["properties"]["broken_kc"]
    assert broken["enum"] == ["missing-angle", "congruence"]
    assert "angle-sum" not in broken["enum"]
    prompt = bundle["system_prompt"]
    assert "Copy one code from the other component codes into broken_kc." in prompt
    assert "It is not a description and not this component's code." in prompt
    assert "Use an empty list when none of those links fit." not in prompt
    assert "empty misconception" not in prompt.lower()
    for sentence in prompt.replace("\n", " ").split("."):
        if "empty" in sentence.lower() and "list" in sentence.lower():
            assert "misconception" not in sentence.lower()
    assert "history" not in bundle["schema"]["properties"]


def test_creator_schema_asks_for_no_broken_kc_without_a_sibling() -> None:
    bundle = creator_bundle(
        course_title="Euclidean geometry",
        course_description=GEOMETRY,
        audience="12-14",
        kind="mastery",
        minutes=None,
        node_title="Triangle angle sum",
        node_code="angle-sum",
        node_description="Outline: The interior angles.\nTopics: 180 degrees\nGoals: State the sum",
        other_codes=[],
        previous=None,
        message="Draft this component.",
        model="gpt-4.1",
    )
    misconceptions = bundle["schema"]["properties"]["misconceptions"]
    assert misconceptions["maxItems"] == 0
    assert "broken_kc" not in misconceptions["items"].get("properties", {})
    prompt = bundle["system_prompt"]
    assert "Return an empty misconceptions array." in prompt
    assert "Do not ask for a broken_kc." in prompt
    assert "Copy one code from the other component codes" not in prompt
    assert "history" not in bundle["schema"]["properties"]


def test_an_unrepaired_broken_kc_names_the_rejected_code_and_the_allowed_codes() -> None:
    from app.kc import _require_recommendation

    draft = {
        "description": "The river is blue.",
        "outline": "The river.",
        "core_truth": "The river is blue.",
        "blocks": [{"id": "blk_1", "type": "topic_goal", "data": {"topic": "color", "goal": "Recall it"}}],
        "prerequisite_codes": ["zz-ok"],
        "encompasses_codes": [],
        "misconceptions": [{"wrong_move": "It is red", "broken_kc": "not-a-code"}],
    }
    with pytest.raises(HTTPException) as caught:
        _require_recommendation(draft, ["zz-ok", "zz-other"])
    assert caught.value.status_code == 422
    detail = str(caught.value.detail)
    assert "not-a-code" in detail
    assert "zz-ok" in detail
    assert "zz-other" in detail


def _creator(other_codes: list[str]):
    return creator_bundle(
        course_title="Euclidean geometry",
        course_description=GEOMETRY,
        audience="12-14",
        kind="mastery",
        minutes=None,
        node_title="Triangle angle sum",
        node_code="angle-sum",
        node_description="Outline: The interior angles.\nTopics: 180 degrees\nGoals: State the sum",
        other_codes=other_codes,
        previous=None,
        message="Draft this component.",
        model="gpt-4.1",
    )


def test_creator_schema_limits_each_mix_to_a_different_other_code() -> None:
    bundle = _creator(["missing-angle", "congruence"])
    props = bundle["schema"]["properties"]
    assert "mix_a" not in props
    assert "mix_b" not in props
    assert props["blocks"]["type"] == "array"
    assert "topic_goal" in props["blocks"]["items"]["properties"]["type"]["enum"]
    assert "allOf" not in bundle["schema"]
    prompt = bundle["system_prompt"]
    assert "ordered blocks[] array" in prompt
    assert "Do not ask for two mixes." not in prompt
    assert "history" not in props


def test_creator_schema_does_not_ask_for_two_mixes_without_two_siblings() -> None:
    one = _creator(["missing-angle"])
    assert "mix_a" not in one["schema"]["properties"]
    assert "mix_b" not in one["schema"]["properties"]
    assert one["schema"]["properties"]["misconceptions"]["items"]["properties"]["broken_kc"]["enum"] == [
        "missing-angle"
    ]
    none = _creator([])
    assert "mix_a" not in none["schema"]["properties"]
    assert none["schema"]["properties"]["misconceptions"]["maxItems"] == 0
    assert "This course has no other component." in none["system_prompt"]
    assert "Copy one code from the other component codes" not in none["system_prompt"]
    assert "history" not in none["schema"]["properties"]


def test_a_repeated_mix_is_cleared_without_inventing_a_sibling() -> None:
    from app.kc import _mix_repair_line, _repair_mixes

    kept, repair = _repair_mixes("angles", "angles", ["angles", "lines"])
    assert kept == []
    assert repair is not None
    assert repair.kept == ()
    line = _mix_repair_line(repair, "2026-11-08 01:40:00 ET")
    assert line.startswith("2026-11-08 01:40:00 ET Warning:")
    assert 'mix_a "angles" and mix_b "angles"' in line
    assert "Allowed codes: angles, lines." in line
    assert 'Changed mixes from "angles" and "angles" to cleared (kept nothing)' in line
    assert "so creation could continue." in line
    assert "lines" not in kept

    kept, repair = _repair_mixes("angles", "Angle sum", ["angles", "lines"])
    assert kept == []
    assert repair is not None and repair.kept == ()

    kept, repair = _repair_mixes("angle-sum", "lines", ["angles", "lines"])
    assert kept == []
    assert repair is not None and repair.kept == ()

    kept, repair = _repair_mixes("angles", "", ["angles", "lines"])
    assert kept == []
    assert repair is not None and repair.kept == ()

    kept, repair = _repair_mixes("lines", "angles", ["angles", "lines"])
    assert kept == ["lines", "angles"]
    assert repair is None

    kept, repair = _repair_mixes("", "", ["angles", "lines"])
    assert kept == []
    assert repair is None


def test_fewer_than_two_other_codes_keep_a_named_code_and_drop_a_title() -> None:
    from app.kc import _repair_mixes

    kept, repair = _repair_mixes("", "", ["angles"])
    assert kept == []
    assert repair is None
    kept, repair = _repair_mixes("angles", "Angle sum", ["angles"])
    assert kept == ["angles"]
    assert repair is not None
    assert repair.kept == ("angles",)
    kept, repair = _repair_mixes("Angle sum", "", [])
    assert kept == []
    assert repair is not None
    assert repair.kept == ()
    assert repair.allowed == ()


def test_an_unrepaired_mix_names_the_rejected_strings_and_the_allowed_codes(caplog) -> None:
    from app.kc import _log_mix, _mix_rejection_detail

    caplog.set_level("WARNING", logger="app.kc")
    detail = _mix_rejection_detail("angles", "angles", ["angles", "lines"])
    assert 'Rejected: "angles" and "angles".' in detail
    assert "Allowed codes: angles, lines." in detail
    _log_mix(
        "rejected",
        "15370df9-8e61-4e84-89d8-2d1af8651463",
        "angles",
        "angles",
        ["angles", "lines"],
    )
    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "kc mix rejected" in message
        and "node_id=15370df9-8e61-4e84-89d8-2d1af8651463" in message
        and "mix_a='angles'" in message
        and "mix_b='angles'" in message
        and "allowed=angles, lines" in message
        for message in messages
    )
    assert all("The rookie swaps them." not in message for message in messages)


def test_finish_route_keeps_pasted_titles_and_does_not_write() -> None:
    created = client.post(
        "/kc/courses",
        json={
            "code": "zz-model-finish",
            "title": "Euclidean geometry",
            "description": GEOMETRY,
            "audience": "12-14",
            "kind": "mastery",
        },
    )
    assert created.status_code == 200, created.text
    course_id = created.json()["id"]
    try:
        before = client.get(f"/kc/courses/{course_id}").json()["components"]
        finished = client.post(
            f"/kc/courses/{course_id}/draft-finish",
            json={
                "message": "Angle sum\nMissing angle",
                "proposal": {
                    "subject": "Euclidean geometry",
                    "major_ideas": ["angle measure", "congruence"],
                    "components": [_row("Angle sum"), _row("Missing angle")],
                },
            },
        )
        assert finished.status_code == 200, finished.text
        assert [item["title"] for item in finished.json()["draft"]["components"]] == ["Angle sum", "Missing angle"]
        assert finished.json()["reply"].startswith("Subject:")
        assert client.get(f"/kc/courses/{course_id}").json()["components"] == before
        refused = client.post(
            f"/kc/courses/{course_id}/draft-prompt",
            json={"message": "Draft the list", "model": "gpt-3.5-turbo"},
        )
        assert refused.status_code == 422
        assert "not allowed" in refused.text
    finally:
        from tests.test_kc import _wipe_zz

        _wipe_zz()


def test_slice_route_rejects_a_short_list_before_the_description_calls() -> None:
    from app.kc import description_prompts_for
    from app.routes.kc import router as kc_router

    paths = [getattr(route, "path", "") for route in kc_router.routes]
    assert "/kc/courses/{course_id}/draft-slices" in paths

    class Goal:
        title = "Euclidean geometry"
        description = GEOMETRY
        audience = "12-14"
        kind = "mastery"
        minutes = None

    titles = [f"Topic {index:02d}" for index in range(1, 31)]
    with pytest.raises(HTTPException) as caught:
        description_prompts_for(Goal(), "30 components", "gpt-4.1", titles[:4])
    assert caught.value.status_code == 422
    assert "30" in str(caught.value.detail)


def test_prompt_route_rejects_an_unknown_model() -> None:
    from app.kc import course_prompt_for

    class Goal:
        title = "Euclidean geometry"
        description = GEOMETRY
        audience = "12-14"
        kind = "mastery"
        minutes = None

    with pytest.raises(HTTPException) as caught:
        course_prompt_for(Goal(), "Draft the list", "not-a-model")
    assert caught.value.status_code == 422
    assert "not allowed" in str(caught.value.detail)
