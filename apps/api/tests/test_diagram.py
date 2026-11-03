import math

from app.widgets import guard_reply

REPLY = "The angles inside a triangle add to a straight line."


def _triangle() -> dict:
    return {
        "kind": "triangle",
        "sides": [
            {"label": "a", "length": 5},
            {"label": "b", "length": 4},
            {"label": "c", "length": 3},
        ],
        "angles": [
            {"label": "A", "degrees": 90},
            {"label": "B", "degrees": math.degrees(math.asin(4 / 5))},
            {"label": "C", "degrees": math.degrees(math.asin(3 / 5))},
        ],
        "right_angle": True,
    }


def test_valid_triangle_is_kept() -> None:
    turn = guard_reply({"reply": REPLY, "diagram": _triangle()}, "geometry")
    assert turn["reply"] == REPLY
    diagram = turn["diagram"]
    assert diagram["kind"] == "triangle"
    assert diagram["right_angle"] is True
    assert [side["label"] for side in diagram["sides"]] == ["a", "b", "c"]
    assert [angle["label"] for angle in diagram["angles"]] == ["A", "B", "C"]
    assert set(diagram) == {"kind", "sides", "angles", "right_angle"}


def test_bad_angles_are_dropped_and_the_reply_stays() -> None:
    diagram = _triangle()
    diagram["angles"] = [
        {"label": "A", "degrees": 90},
        {"label": "B", "degrees": 50},
        {"label": "C", "degrees": 50},
    ]
    turn = guard_reply({"reply": REPLY, "diagram": diagram}, "geometry")
    assert turn["reply"] == REPLY
    assert "diagram" not in turn


def test_wrong_course_drops_the_diagram_and_keeps_the_reply() -> None:
    turn = guard_reply({"reply": REPLY, "diagram": _triangle()}, "rome")
    assert turn["reply"] == REPLY
    assert "diagram" not in turn


def test_unknown_kind_is_dropped_and_the_reply_stays() -> None:
    diagram = _triangle()
    diagram["kind"] = "bitmap"
    turn = guard_reply({"reply": REPLY, "diagram": diagram}, "geometry")
    assert turn["reply"] == REPLY
    assert "diagram" not in turn

    graph = guard_reply({"reply": REPLY, "diagram": {"kind": "graph"}}, "geometry")
    assert graph["reply"] == REPLY
    assert "diagram" not in graph

    markup = _triangle()
    markup["sides"][0]["label"] = "<img src=x>"
    marked = guard_reply({"reply": REPLY, "diagram": markup}, "geometry")
    assert marked["reply"] == REPLY
    assert "diagram" not in marked
