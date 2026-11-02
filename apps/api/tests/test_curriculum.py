from app.course_io import validate_course
from app.curriculum import COURSES
from app.models import BEAT_ROLES


def test_seed_courses_match_the_blueprint_shape() -> None:
    by_code = {course["code"]: validate_course(course) for course in COURSES}
    assert set(by_code) == {"rome", "geometry", "macro"}
    assert by_code["rome"]["age_band"] == "9-11"
    assert by_code["geometry"]["age_band"] == "12-14"
    assert by_code["macro"]["age_band"] == "15-17"
    assert "NCSS C3" in by_code["rome"]["standards_alignment"]
    assert "HSG" in by_code["geometry"]["standards_alignment"]
    assert "AP Macro" in by_code["macro"]["standards_alignment"]

    def quests(course):
        return [quest for unit in course["units"] for quest in unit["quests"]]

    rome = quests(by_code["rome"])
    geometry = quests(by_code["geometry"])
    macro = quests(by_code["macro"])
    assert len(rome) == 16
    assert len(geometry) == 16
    assert len(macro) == 16
    assert {quest["quest_type"] for quest in rome if quest["code"] in {"ROM-U4-Q2A", "ROM-U4-Q2B"}} == {"branch"}
    boss = next(quest for quest in rome if quest["code"] == "ROM-U4-BOSS")
    assert boss["prerequisite_codes"] == ["ROM-U4-Q2A", "ROM-U4-Q2B"]

    consuls = next(quest for quest in rome if quest["code"] == "ROM-U2-Q1")
    assert [beat["role"] for beat in consuls["beats"]] == list(BEAT_ROLES)
    assert "VETO" in consuls["beats"][0]["prompt"]
    assert consuls["beats"][1]["widget"]["answer"] == "walkout"
    assert "Twelve" in consuls["beats"][2]["prompt"]
    assert "Bumbling Centurion Bot" in consuls["beats"][3]["prompt"]

    truss = next(quest for quest in geometry if quest["code"] == "GEO-U2-Q2")
    assert truss["beats"][2]["widget"]["type"] == "order"
    assert truss["beats"][2]["widget"]["answer"] == ["given", "bisector", "reflexive", "sas"]
    assert "Rookie Architect Bot" in truss["beats"][3]["prompt"]
    assert sum(row["weight"] for row in truss["beats"][2]["rubric"]) == 100

    banker = next(quest for quest in macro if quest["code"] == "MAC-U4-Q1")
    assert "6.5" in banker["beats"][0]["prompt"]
    assert [row["weight"] for row in banker["beats"][0]["rubric"]] == [35, 35, 30]
    assert banker["beats"][2]["widget"]["type"] == "flaw"
    assert banker["beats"][2]["widget"]["answer"] == "s3"
    assert "Cable Pundit Bot" in banker["beats"][3]["prompt"]
    assert "8 percent" in banker["beats"][3]["prompt"]
