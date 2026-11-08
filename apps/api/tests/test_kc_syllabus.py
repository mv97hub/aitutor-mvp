"""The KC Course Creator draft is a syllabus, not a chopped description."""

from types import SimpleNamespace

import pytest

from app.kc import KC_TYPES, draft_course
from app.kc_syllabus import MAX_COMPONENTS, plan_component_titles

GEOMETRY = (
    "Tell congruent triangles apart, find a missing angle, and explain why "
    "two sides and a non-included angle do not prove congruence."
)
CLAUSES = (
    "Tell congruent triangles apart",
    "find a missing angle",
    "explain why two sides and a non-included angle do not prove congruence",
)
TIME_BOXED_30 = (
    "Triangle angle sum",
    "Find the missing angle",
    "What congruence means",
    "SAS versus SSA",
    "Why SSA fails",
    "Fix a faulty congruence plan",
)


def _titles(**kwargs) -> list[str]:
    titles, _reply = plan_component_titles(**kwargs)
    return titles


def _reply(**kwargs) -> str:
    _titles, reply = plan_component_titles(**kwargs)
    return reply


def _geometry(**overrides):
    body = {
        "title": "Euclidean geometry",
        "description": GEOMETRY,
        "kind": "mastery",
        "minutes": None,
        "message": "Draft the component list",
    }
    body.update(overrides)
    return body


def test_pasted_titles_stay_a_list_and_do_not_write_fields() -> None:
    goal = SimpleNamespace(
        title="Euclidean geometry",
        description=GEOMETRY,
        kind="mastery",
        minutes=30,
    )
    drafted = draft_course(goal, "Angle sum\nMissing angle\nSAS versus SSA\nCongruence")
    assert drafted["draft"]["kind"] == "course"
    assert [item["title"] for item in drafted["draft"]["components"]] == [
        "Angle sum",
        "Missing angle",
        "SAS versus SSA",
        "Congruence",
    ]
    assert [item["code"] for item in drafted["draft"]["components"]] == [
        "angle-sum",
        "missing-angle",
        "sas-versus-ssa",
        "congruence",
    ]
    for item in drafted["draft"]["components"]:
        assert set(item) == {"code", "title", "description", "outline", "topics"}
        assert item["description"] == item["outline"]
        assert "Outline:" not in item["description"]
        assert item["topics"][0]["topic"] == item["title"]
        assert item["topics"][0]["goal"] == f"Explain {item['title']}"
    assert drafted["reply"].startswith("Subject:")
    assert "Major ideas a strong course" in drafted["reply"]
    assert "Nothing is saved" in drafted["reply"]
    assert KC_TYPES == ("factual", "procedural", "conceptual", "causal", "synthesis")


def test_mastery_is_the_subject_not_the_description() -> None:
    titles = _titles(**_geometry(message="Be a master of this.\nMinimum of 10 components."))
    reply = _reply(**_geometry(message="Be a master of this.\nMinimum of 10 components."))
    assert len(titles) >= 10
    assert len(titles) == len({title.lower() for title in titles})
    for clause in CLAUSES:
        assert clause not in titles
    for anchor in ("Triangle angle sum", "SAS versus SSA", "Why SSA fails", "Fix a faulty congruence plan"):
        assert anchor in titles
    assert "Points, lines, and angles" in titles
    assert "fuller breakdown" in reply
    assert "mastery" in reply
    assert "at least 10" in reply
    assert "Nothing is saved" in reply


def test_a_thin_title_still_uses_the_subject_in_the_description() -> None:
    titles = _titles(
        title="ZZ course",
        description=GEOMETRY,
        kind="mastery",
        minutes=None,
        message="Be a master. Minimum of 10.",
    )
    assert "Triangle angle sum" in titles
    assert "Tell congruent triangles apart" not in titles
    assert all(not title.lower().startswith("zz course") for title in titles)


def test_kind_changes_the_depth() -> None:
    mastery = _titles(**_geometry())
    boxed = _titles(**_geometry(kind="time_boxed", minutes=30, message="Draft the components"))
    curiosity = _titles(**_geometry(kind="curiosity", message="Draft a path"))
    assert boxed == list(TIME_BOXED_30)
    assert len(mastery) > len(boxed)
    assert len(curiosity) < len(mastery)
    assert curiosity[0] != mastery[0]
    assert "Two triangles that look the same" in curiosity
    assert "path through" in _reply(**_geometry(kind="curiosity", message="Draft a path"))
    boxed_reply = _reply(**_geometry(kind="time_boxed", minutes=30, message="Draft the components"))
    assert "time-boxed course of 30 minutes" in boxed_reply
    assert "sized to the minutes" in boxed_reply


def test_time_boxed_fits_the_minutes() -> None:
    quarter = _titles(**_geometry(kind="time_boxed", minutes=15, message="Draft the list"))
    three_quarters = _titles(**_geometry(kind="time_boxed", minutes=45, message="Draft the list"))
    blank = _titles(**_geometry(kind="time_boxed", minutes=None, message="Draft the list"))
    assert quarter == list(TIME_BOXED_30[:3])
    assert len(three_quarters) == 9
    assert three_quarters[0] == "Points, lines, and angles"
    assert len(blank) == 4
    assert "minutes" not in _reply(**_geometry(kind="time_boxed", minutes=None, message="Draft the list"))


def test_minimum_of_ten_does_not_pad_with_sentence_pieces() -> None:
    titles = _titles(**_geometry(kind="time_boxed", minutes=15, message="I want a minimum of 10 components"))
    assert len(titles) >= 10
    assert len(titles) == len({title.lower() for title in titles})
    for clause in CLAUSES:
        assert clause not in titles
    assert not any(title[-1].isdigit() for title in titles)
    reply = _reply(**_geometry(kind="time_boxed", minutes=15, message="a minimum of ten components"))
    assert "at least 10" in reply
    assert len(_titles(**_geometry(kind="curiosity", message="minimum of 10"))) >= 10


def test_an_exact_count_is_that_many_real_components() -> None:
    titles = _titles(**_geometry(message="10 components"))
    assert len(titles) == 10
    assert titles[-1] == "Why SSA fails"
    assert len(_titles(**_geometry(message="twelve"))) == 12
    assert "You asked for 10." in _reply(**_geometry(message="10 components"))


def test_the_message_can_choose_the_kind() -> None:
    mastered = _titles(
        **_geometry(kind="curiosity", message="Be a master of this. Minimum of 10.")
    )
    assert len(mastered) >= 10
    assert "Triangle angle sum" in mastered
    assert "mastery" in _reply(**_geometry(kind="curiosity", message="Be a master of this."))
    timed = _titles(**_geometry(kind="mastery", minutes=None, message="Fit this in 20 minutes"))
    assert len(timed) == 4
    assert "20 minutes" in _reply(**_geometry(kind="mastery", minutes=None, message="Fit this in 20 minutes"))
    stayed = _titles(**_geometry(minutes=30, message="Be a master in 30 minutes"))
    assert len(stayed) > 6
    assert "mastery" in _reply(**_geometry(minutes=30, message="Be a master in 30 minutes"))


def test_a_mastery_course_does_not_shrink_because_minutes_are_saved() -> None:
    full = _titles(**_geometry(minutes=30, message="Draft the syllabus"))
    assert len(full) > 6
    assert "Triangle angle sum" in full


def test_an_age_band_is_not_a_component_count() -> None:
    titles = _titles(**_geometry(kind="time_boxed", minutes=30, message="For ages 12-14, draft the list"))
    assert titles == list(TIME_BOXED_30)


def test_an_unknown_subject_is_not_chopped_clauses() -> None:
    description = "Include the materials, the first coil, and how to finish the rim."
    titles = _titles(
        title="Basket weaving",
        description=description,
        kind="mastery",
        minutes=None,
        message="Be a master. Minimum of 10 components.",
    )
    reply = _reply(
        title="Basket weaving",
        description=description,
        kind="mastery",
        minutes=None,
        message="Be a master. Minimum of 10 components.",
    )
    assert len(titles) >= 10
    assert all("Basket weaving" in title for title in titles)
    for fragment in ("the materials", "the first coil", "how to finish the rim"):
        assert fragment not in [title.lower() for title in titles]
        assert fragment not in " ".join(titles).lower()
    assert "fuller breakdown" in reply
    path = _titles(
        title="Basket weaving",
        description=description,
        kind="curiosity",
        minutes=None,
        message="Draft a curiosity path",
    )
    assert len(path) < len(titles)
    assert path[0] != titles[0]
    assert all("Basket weaving" in title for title in path)


def test_a_history_course_keeps_the_subject_and_drops_the_include_list() -> None:
    description = (
        "Create a course about the history of Imperial College. "
        "Include the founding, the move to South Kensington, and the later mergers."
    )
    titles = _titles(
        title="Imperial College",
        description=description,
        kind="mastery",
        minutes=None,
        message="Draft the syllabus",
    )
    assert len(titles) >= 10
    assert all("Imperial College" in title for title in titles)
    blob = " ".join(titles).lower()
    assert "south kensington" not in blob
    assert "later mergers" not in blob
    assert "include the founding" not in blob


def test_a_known_science_topic_uses_its_own_structure() -> None:
    titles = _titles(
        title="Photosynthesis",
        description="Explain how a plant gets its mass, including the air, the light, and the soil.",
        kind="mastery",
        minutes=None,
        message="Minimum of 10",
    )
    assert "The Calvin cycle" in titles
    assert "Chlorophyll" in titles
    assert "including the air, the light, and the soil" not in titles
    assert "the soil" not in titles


def test_a_requested_count_above_the_real_structure_does_not_invent_fillers() -> None:
    titles = _titles(**_geometry(message="40 components"))
    reply = _reply(**_geometry(message="40 components"))
    assert MAX_COMPONENTS == 250
    assert len(titles) == 16
    assert len(titles) < MAX_COMPONENTS
    assert len(titles) == len({title.lower() for title in titles})
    assert "earn a place" in reply
    assert "40" in reply
    assert not any(title.lower().startswith("euclidean geometry ") for title in titles)


def test_a_pasted_list_between_17_and_250_is_kept() -> None:
    titles = [f"Topic {index:02d}" for index in range(1, 31)]
    kept = _titles(**_geometry(message="\n".join(titles)))
    assert kept == titles
    assert 17 <= len(kept) <= MAX_COMPONENTS


def test_a_pasted_list_above_the_cap_is_rejected() -> None:
    titles = [f"Topic {index:03d}" for index in range(1, 252)]
    with pytest.raises(ValueError, match="at most 250"):
        _titles(**_geometry(message="\n".join(titles)))
