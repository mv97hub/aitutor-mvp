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
    KC_CHAT_MODELS,
    assemble_course,
    checked_discussion,
    checked_model,
    course_bundle,
    creator_bundle,
    titles_are_sliced,
)

GEOMETRY = (
    "Tell congruent triangles apart, find a missing angle, and explain why "
    "two sides and a non-included angle do not prove congruence."
)


def _row(title: str) -> dict:
    return {
        "title": title,
        "outline": f"How {title} works.",
        "topics": [title, "a worked case"],
        "goals": [f"Explain {title}", f"Use {title}"],
    }


def test_menu_keeps_the_original_models_and_names_a_stronger_default() -> None:
    assert KC_CHAT_MODELS[:3] == ("gpt-4o-mini", "gpt-4o", "gpt-4.1-mini")
    assert DEFAULT_KC_CHAT_MODEL == "gpt-4.1"
    assert KC_CHAT_MODELS[-1] == "gpt-6.1-sol"
    assert checked_model("") == "gpt-4.1"
    with pytest.raises(ValueError, match="not allowed"):
        checked_model("gpt-3.5-turbo")


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
        assert item["description"].startswith("Outline:")
        assert "Topics:" in item["description"]
        assert "Goals:" in item["description"]


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
    assert "You are an expert on this knowledge component" in prompt
    assert "Mastery is the fuller rigorous breakdown" in prompt
    assert "Outline: The interior angles." in prompt
    assert "Go into the topic before you fill the type" in prompt
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
