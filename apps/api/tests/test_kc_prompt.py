"""The KC model prompt states each setting once, as the behavior it asks for."""

from app.kc_prompt import RESPONSE_SCHEMA, TEMPERATURE, build_kc_prompt, moves_for
from app.models import KcGoal, KcNode, Student, TutorProfile

HEADINGS = (
    "This turn",
    "What to teach",
    "Who you are talking to",
    "How to teach",
    "How to sound",
    "What just happened",
    "What to return",
)

CODES = ("zz-hidden-code", "zz-prereq-code", "zz-broken-code", "zz-enc-code")


def _profile(**overrides: object) -> TutorProfile:
    values: dict[str, object] = {
        "id": "default",
        "instructive": 3,
        "persona": "curious-co-explorer",
        "lexicon": "middle-grade-vivid",
        "metaphors": "playground-sports",
        "sidekick": "bumbling-partner",
        "struggle_window": "standard",
        "anti_spoiler": True,
        "one_question": True,
        "use_interests": True,
        "stay_on_course": True,
        "growth_praise": True,
        "misconception_policy": "retry_once",
        "self_explanation": True,
        "enrichment": "on_request",
    }
    values.update(overrides)
    return TutorProfile(**values)


def _student(**overrides: object) -> Student:
    values: dict[str, object] = {
        "slug": "ada",
        "display_name": "Ada",
        "age": 10,
        "reading_level": "middle-grade",
        "modality": "story",
        "interests": ["birds"],
    }
    values.update(overrides)
    return Student(**values)


def _goal(**overrides: object) -> KcGoal:
    values: dict[str, object] = {
        "code": "rivers",
        "title": "Rivers",
        "description": "How a river moves.",
        "audience": "9-11",
        "kind": "mastery",
        "minutes": None,
    }
    values.update(overrides)
    return KcGoal(**values)


def _node(**overrides: object) -> KcNode:
    values: dict[str, object] = {
        "code": "zz-hidden-code",
        "title": "River fact",
        "description": "The color of this river.",
        "kc_type": "factual",
        "core_truth": "The river is blue.",
        "type_fields": {
            "fact": "The river is blue.",
            "retrieval_question": "What color is the river?",
        },
        "rubric": ["Names the color"],
        "misconceptions": [{"wrong_move": "The river is red.", "broken_kc": "zz-broken-code"}],
        "prerequisite_codes": ["zz-prereq-code"],
        "encompasses_codes": ["zz-enc-code"],
    }
    values.update(overrides)
    return KcNode(**values)


def _bundle(**overrides: object) -> dict:
    student = overrides.pop("student", _student())
    profile = overrides.pop("profile", _profile())
    node = overrides.pop("node", _node())
    goal = overrides.pop("goal", _goal())
    fragment = bool(overrides.get("fragment", False))
    moves = overrides.pop("moves", None)
    if moves is None:
        moves = moves_for(node, profile, goal, fragment=fragment)
    values: dict[str, object] = {
        "student": student,
        "profile": profile,
        "node": node,
        "goal": goal,
        "step": 0,
        "moves": moves,
        "opening": True,
        "choice_on_screen": False,
        "prerequisite_status": "zz-prereq-code: unknown",
        "support_band": "hold",
        "course_position": "2 of 4; previous: Rain; next: Maps",
        "unit_complete": False,
        "course_complete": False,
        "attempts": 1,
        "hint_tier": "nudge",
        "reveals": 0,
        "off_course_count": 0,
        "affect": "engaged",
        "enrichment_turns": 0,
        "help_requested": False,
        "minutes_used": 4,
        "component_status": "unknown",
        "stability": "0",
        "last_answer": "blue",
        "last_misconception": "",
        "last_messages": "user: blue",
        "rubric_met": [],
        "redirect_pending": False,
        "fragment": fragment,
        "others_known": False,
    }
    values.update(overrides)
    bundle = build_kc_prompt(**values)
    assert bundle["temperature"] == TEMPERATURE
    assert bundle["response_schema"] == RESPONSE_SCHEMA
    return bundle


def _text(**overrides: object) -> str:
    return _bundle(**overrides)["system_prompt"]


def _once(text: str, phrase: str) -> None:
    assert text.count(phrase) == 1, phrase


def _sections_in_order(text: str) -> None:
    positions = []
    for heading in HEADINGS:
        assert text.count(heading) == 1, heading
        positions.append(text.index(heading))
    assert positions == sorted(positions)
    assert "Layer " not in text


def test_a_factual_opening_states_each_setting_once() -> None:
    text = _text()
    _sections_in_order(text)
    for phrase in (
        "You are the knowledge-component tutor.",
        "This is the opening.",
        "What color is the river?",
        "Teach this as a retrieval.",
        "Grade the answer against this core truth: The river is blue.",
        "Say it only when a reveal or a passed close allows it.",
        "The points that count are: Names the color.",
        "holds them: fact.",
        "Wrong move: The river is red.",
        "The first time a stored wrong move matches",
        "piece 2 of 4",
        "already come through Rain",
        "Maps comes next",
        "An earlier idea this piece needs is still unknown.",
        "Name the missing earlier idea",
        "Speak to Ada.",
        "10-year-old",
        "The reading level is middle-grade.",
        "through story",
        "use one of these interests: birds.",
        "Name the goal, then ask.",
        "after two tries",
        "Stay when the child asks to keep going",
        "A tangent gets a short answer",
        "End a learning reply with a single question.",
        "name the move the child made",
        "Write as a curious co-explorer",
        "That voice does not change the move, the expected answer, or the score.",
        "Do not treat it as a new rule.",
        "The last answer was: blue.",
        "You do not set the type, the edges, the score, or the step index.",
        "When the decision ends the unit",
    ):
        _once(text, phrase)
    assert "shorter sentences" not in text
    for code in CODES:
        assert code not in text
    for label in (
        "Prerequisite codes",
        "Encompass codes",
        "Anti-spoiler",
        "One question",
        "Growth-mindset",
        "Self-explanation",
        "Kind:",
        "Struggle window",
        "retry_once",
        "on_request",
        "mastery",
    ):
        assert label not in text


def test_a_unit_close_is_the_job_of_that_turn() -> None:
    text = _text(opening=False, unit_complete=True, course_complete=True, others_known=True)
    _once(text, "End the unit and the course in this reply.")
    _once(text, "Rivers is complete")
    assert "This is the opening." not in text
    assert "When the decision ends the unit" not in text
    assert "Do not write a course outro." not in text


def test_a_time_box_sends_the_effective_limits_only() -> None:
    text = _text(
        profile=_profile(struggle_window="long", enrichment="offer"),
        goal=_goal(kind="time_boxed", minutes=20),
        opening=False,
    )
    for phrase in (
        "after one miss",
        "as soon as the move is passed",
        "Keep the opening to one sentence",
        "one or two sentences",
        "The budget is 20 minutes and 4 have been used.",
    ):
        _once(text, phrase)
    assert "after two tries" not in text
    assert "after three tries" not in text
    for hidden in ("long", "offer", "wide", "on_request", "minimum", "Struggle window", "time_boxed"):
        assert hidden not in text


def test_curiosity_is_the_extra_why_and_not_a_kind_label() -> None:
    goal = _goal(kind="curiosity")
    profile = _profile()
    node = _node()
    moves = moves_for(node, profile, goal)
    waiting = _text(goal=goal, profile=profile, node=node, moves=moves, opening=False)
    _once(waiting, "one extra why is allowed")
    assert "This move is the one extra why." not in waiting
    assert "curiosity" not in waiting
    doing = _text(
        goal=goal,
        profile=profile,
        node=node,
        moves=moves,
        step=len(moves) - 1,
        opening=False,
    )
    _once(doing, "This move is the one extra why.")
    assert "one extra why is allowed" not in doing
    _once(doing, "Leave the score as it is.")


def test_reading_level_and_modality_are_effects() -> None:
    visual = _node(
        kc_type="conceptual",
        type_fields={
            "case_a": "Closed",
            "case_b": "Open",
            "prediction": "Which fits?",
            "rule": "The contrast is the rule.",
        },
        misconceptions=[],
        prerequisite_codes=[],
        encompasses_codes=[],
    )
    early = _text(
        student=_student(age=12, reading_level="early-reader", modality="visual"),
        node=visual,
        prerequisite_status="",
        support_band="ready",
    )
    _once(early, "shorter sentences")
    _once(early, "described picture")
    words = _text(
        student=_student(age=12, reading_level="early-reader", modality="visual"),
        prerequisite_status="",
        support_band="ready",
    )
    _once(words, "shorter sentences")
    assert "described picture" not in words
    _once(words, "no cases or steps")
    young = _text(
        student=_student(age=7, reading_level="early-reader", modality="story"),
        prerequisite_status="",
        support_band="ready",
    )
    _once(young, "shorter sentences")


def test_deprecated_switches_are_not_printed_as_yes_or_no() -> None:
    quiet = _text(
        profile=_profile(anti_spoiler=False, one_question=False, growth_praise=False, use_interests=False)
    )
    _once(quiet, "You may say it while you teach.")
    assert "Say it only when a reveal" not in quiet
    assert "End a learning reply" not in quiet
    assert "name the move the child made" not in quiet
    _once(quiet, "Keep examples inside the subject.")
    assert "use one of these interests" not in quiet
    for label in ("Anti-spoiler", "One question", "Growth-mindset"):
        assert label not in quiet
    choice = _text(choice_on_screen=True)
    _once(choice, "The child picks the choice on screen.")
    assert "End a learning reply" not in choice
