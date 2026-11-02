from app.course_io import validate_course
from app.curriculum import COURSES
from app.models import BEAT_ROLES


def _quests(course):
    return [quest for unit in course["units"] for quest in unit["quests"]]


def test_seed_courses_match_the_cycle() -> None:
    by_code = {course["code"]: validate_course(course) for course in COURSES}
    assert set(by_code) == {"rome", "geometry", "macro"}
    assert by_code["rome"]["age_band"] == "9-11"
    assert by_code["geometry"]["age_band"] == "12-14"
    assert by_code["macro"]["age_band"] == "15-17"
    assert "NCSS C3" in by_code["rome"]["standards_alignment"]
    assert "HSG" in by_code["geometry"]["standards_alignment"]
    assert "AP Macro" in by_code["macro"]["standards_alignment"]
    assert len(by_code["macro"]["units"]) == 6

    rome = _quests(by_code["rome"])
    geometry = _quests(by_code["geometry"])
    macro = _quests(by_code["macro"])
    assert len(rome) == 16
    assert len(geometry) == 16
    assert len(macro) == 18
    assert {quest["quest_type"] for quest in rome if quest["code"] in {"ROM-U4-Q2A", "ROM-U4-Q2B"}} == {"branch"}
    boss = next(quest for quest in rome if quest["code"] == "ROM-U4-BOSS")
    assert boss["prerequisite_codes"] == ["ROM-U4-Q2A", "ROM-U4-Q2B"]

    consuls = next(quest for quest in rome if quest["code"] == "ROM-U2-Q1")
    roles = [beat["role"] for beat in consuls["beats"]]
    assert roles[0] == "engage"
    assert "try" in roles
    assert "show" in roles
    assert roles[-1] == "teach_back"
    assert set(roles) <= set(BEAT_ROLES)
    assert consuls["requires_teach_back"] is True
    assert "VETO" in consuls["beats"][0]["prompt"]
    assert not consuls["beats"][0]["prompt"].rstrip().endswith("?")
    name = next(beat for beat in consuls["beats"] if beat["role"] == "name")
    assert "veto stops one consul" in name["prompt"]
    assert not name["prompt"].rstrip().endswith("?")
    try_move = next(beat for beat in consuls["beats"] if beat["role"] == "try")
    assert try_move["widget"]["answer"] == "deadlock"
    assert "walkout" not in try_move["widget"]["answer"]
    show = next(beat for beat in consuls["beats"] if beat["role"] == "show")
    assert show["rubric"] == consuls["success_criterion"]
    assert sum(row["weight"] for row in consuls["success_criterion"]) == 100
    assert 2 <= len(consuls["success_criterion"]) <= 3

    truss = next(quest for quest in geometry if quest["code"] == "GEO-U2-Q2")
    assert truss["requires_teach_back"] is True
    assert [beat["role"] for beat in truss["beats"]].count("try") == 2
    show = next(beat for beat in truss["beats"] if beat["role"] == "show")
    assert show["widget"]["type"] == "order"
    assert show["widget"]["answer"] == ["given", "bisector", "reflexive", "sas"]
    assert show["rubric"] == truss["success_criterion"]
    named = next(beat for beat in truss["beats"] if beat["role"] == "name")
    assert "AAA keeps the angles" in named["prompt"]
    assert not named["prompt"].rstrip().endswith("?")
    teach = next(beat for beat in truss["beats"] if beat["role"] == "teach_back")
    assert "Rookie Architect Bot" in teach["prompt"]
    bosses = [quest for quest in geometry if quest["quest_type"] == "capstone" or quest["code"].endswith("BOSS")]
    assert all(quest["requires_teach_back"] for quest in bosses)
    plain = next(quest for quest in geometry if quest["code"] == "GEO-U1-Q1")
    assert plain["requires_teach_back"] is False

    banker = next(quest for quest in macro if quest["code"] == "MAC-U5-Q1")
    assert "POL-1.D" in banker["competency_tags"]
    assert [row["weight"] for row in banker["success_criterion"]] == [35, 35, 30]
    try_move = next(beat for beat in banker["beats"] if beat["role"] == "try")
    assert "6.5" in try_move["prompt"]
    assert try_move["widget"]["answer"] == "shift"
    show = next(beat for beat in banker["beats"] if beat["role"] == "show")
    assert show["widget"]["type"] == "flaw"
    assert show["widget"]["answer"] == "s3"
    named = next(beat for beat in banker["beats"] if beat["role"] == "name")
    assert "rate rise makes loans more expensive" in named["prompt"]
    assert not named["prompt"].rstrip().endswith("?")
    teach = next(beat for beat in banker["beats"] if beat["role"] == "teach_back")
    assert "Cable Pundit Bot" in teach["prompt"]
    assert "8 percent" in teach["prompt"]
