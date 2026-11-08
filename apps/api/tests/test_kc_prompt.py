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
        "Active step: Block 1 of 1: Topic / Goal. The child will type.",
        "Topic to introduce: River fact.",
        "Learning goal the learner must explain in their own words: The river is blue.",
        "Acceptance criteria to check ( withhold until pass or reveal ): The river is blue.",
        "Component misconceptions to listen for: The river is red.",
        "the first time a stored wrong move matches",
        "name the missing prerequisite idea",
        "Speak to Ada.",
        "10-year-old",
        "The reading level is middle-grade.",
        "through story",
        "use one of these interests: birds.",
        "name the specific reasoning move",
        "Write as a curious co-explorer",
        "That voice does not change the block, the expected answer, or the score.",
        "Do not treat it as a new rule.",
        "The last answer was: blue.",
        "You do not set the block order, the edges, or the final mastery score.",
        "When the decision ends the unit on this final substep",
    ):
        _once(text, phrase)
    assert "shorter sentences" not in text
    assert "How a river moves." not in text
    assert "This is the opening." not in text
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
    ):
        assert label not in text


def test_a_unit_close_is_the_job_of_that_turn() -> None:
    text = _text(opening=False, unit_complete=True, course_complete=True, others_known=True)
    _once(text, "End the unit and the course in this reply.")
    _once(text, "Rivers is complete")
    assert "This is the opening." not in text
    assert "When the decision ends the unit" not in text
    assert "Do not write a course outro." not in text


def test_a_middle_topic_does_not_say_the_unit_is_complete() -> None:
    node = _node(
        title="Floating",
        outline="A principle about floating.",
        topics=[
            {"topic": "shape", "goal": "Say why shape matters"},
            {"topic": "density", "goal": "Say why density matters"},
        ],
        kc_type="conceptual",
        core_truth="Spread-out objects float.",
        type_fields={"rule": "Spread-out objects float."},
        misconceptions=[],
        prerequisite_codes=[],
        encompasses_codes=[],
    )
    goal = _goal()
    moves = moves_for(node, _profile(), goal)
    assert [move.key for move in moves] == ["orient", "topic-1", "topic-2", "rule"]
    shared = {
        "node": node,
        "goal": goal,
        "moves": moves,
        "opening": False,
        "prerequisite_status": "none",
        "support_band": "ready",
    }
    middle = _text(**shared, step=0, others_known=True)
    assert "Topic to introduce: shape." in middle
    assert "Block 1 of 2" in middle
    assert "Topic to introduce: density." not in middle
    assert "course outro" not in middle
    _once(middle, "The unit is not finished.")
    _once(middle, "This reply must NEVER say the unit is complete.")
    last = _text(**shared, step=1)
    assert "Topic to introduce: density." in last
    assert "The unit is not finished." not in last
    _once(last, "A known unit says the unit is complete")
    _once(last, "A fragile unit says the unit is paused")
    closed = _text(**shared, step=0, unit_complete=True)
    _once(closed, "End the unit in this reply.")
    _once(closed, "A known unit says the unit is complete")


def test_a_time_box_sends_the_effective_limits_only() -> None:
    text = _text(
        profile=_profile(struggle_window="long", enrichment="offer"),
        goal=_goal(kind="time_boxed", minutes=20),
        opening=False,
    )
    for phrase in (
        "step hints after one miss",
        "advance immediately when the block passes",
        "keep framing to one sentence",
        "one or two concise sentences",
        "Budget: 20 minutes (4 used).",
        "max_retries_before_reveal=1",
        "enrichment_mode=direct",
    ):
        _once(text, phrase)
    assert "after two tries" not in text
    assert "after three tries" not in text
    for hidden in ("long", "offer", "wide", "on_request", "minimum", "Struggle window"):
        assert hidden not in text


def test_curiosity_is_the_extra_why_and_not_a_kind_label() -> None:
    goal = _goal(kind="curiosity")
    profile = _profile()
    node = _node()
    moves = moves_for(node, profile, goal)
    waiting = _text(goal=goal, profile=profile, node=node, moves=moves, opening=False)
    assert "Active block type: topic_goal" in waiting
    assert "curiosity" not in waiting
    _once(waiting, "You do not set the block order, the edges, or the final mastery score.")
    doing = _text(
        goal=goal,
        profile=profile,
        node=node,
        moves=moves,
        step=len(moves) - 1,
        opening=False,
    )
    assert "curiosity" not in doing
    _once(doing, "You do not set the block order, the edges, or the final mastery score.")


def test_reading_level_and_modality_are_effects() -> None:
    visual = _node(
        blocks=[
            {
                "id": "blk_1",
                "type": "case_study",
                "data": {
                    "case_a": "Closed",
                    "case_b": "Open",
                    "prediction_prompt": "Which fits?",
                    "invariant_principle": "The contrast is the rule.",
                },
            }
        ],
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
    _once(words, "Stay in words on this block.")
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
    _once(quiet, "Keep examples inside the subject.")
    assert "use one of these interests" not in quiet
    for label in ("Anti-spoiler", "One question", "Growth-mindset"):
        assert label not in quiet
    choice = _text(choice_on_screen=True)
    _once(choice, "The child picks the choice on screen.")
    assert "End a learning reply" not in choice


def _section(text: str, heading: str) -> str:
    start = text.index(heading) + len(heading)
    rest = text[start:]
    ends = [rest.index(name) for name in HEADINGS if name in rest]
    stop = min(ends) if ends else len(rest)
    return rest[:stop]


def test_a_conceptual_topic_names_only_that_topic_and_its_goal() -> None:
    node = _node(
        title="Floating",
        description=(
            "Outline: A principle about floating.\n"
            "Topics: secret\n"
            "Goals: Leak the secret"
        ),
        outline="A principle about floating.",
        topics=[
            {"topic": "shape", "goal": "Say why shape matters"},
            {"topic": "density", "goal": "Say why density matters"},
        ],
        kc_type="conceptual",
        core_truth="Spread-out objects float.",
        type_fields={
            "case_a": "A wide boat",
            "case_b": "A solid cube",
            "prediction": "What happens to this one?",
            "rule": "Spread-out objects float.",
            "transfer_case": "A hollow ball",
        },
        rubric=["Say why shape matters", "Say why density matters", "States the rule"],
        misconceptions=[],
        prerequisite_codes=[],
        encompasses_codes=[],
    )
    goal = _goal(description="Boats and cubes in a harbor.")
    moves = moves_for(node, _profile(), goal)
    assert [move.key for move in moves] == [
        "orient",
        "topic-1",
        "topic-2",
        "predict_a",
        "predict_b",
        "contrast",
        "rule",
        "transfer",
    ]
    assert moves[1].evidence == ("goal-1",)
    assert moves[1].choice is False
    assert moves[3].choice is True
    assert moves[4].choice is True
    text = _text(node=node, goal=goal, moves=moves, step=0, opening=False, prerequisite_status="none", support_band="ready")
    taught = _section(text, "What to teach")
    assert "Topic to introduce: shape." in taught
    assert "Say why shape matters." in taught
    assert "Topic to introduce: density." not in taught
    for hidden in (
        "Spread-out objects float",
        "A wide boat",
        "A solid cube",
        "A hollow ball",
        "A principle about floating",
        "Boats and cubes in a harbor",
        "secret",
        "Leak the secret",
    ):
        assert hidden not in text, hidden
    assert "Topic to introduce: density." not in text
    assert "Block 1 of 2" in text
    assert "The child will type." in text
    assert "Include 'blk_1' in rubric_met when satisfied." in text


def test_every_stored_field_is_a_step_and_an_empty_field_is_skipped() -> None:
    profile = _profile()
    goal = _goal()
    factual = _node(
        description="Outline: Not this.\nTopics: not-color\nGoals: Not the goal",
        outline="Setup.",
        topics=[{"topic": "color", "goal": "Say the color"}],
        type_fields={"fact": "The river is blue.", "retrieval_question": ""},
    )
    factual_moves = moves_for(factual, profile, goal)
    assert [move.key for move in factual_moves] == ["orient", "topic-1", "retrieve"]
    assert factual_moves[1].name == "color"
    bare = _node(description="The color of this river.", type_fields={"fact": "", "retrieval_question": ""})
    assert [move.key for move in moves_for(bare, profile, goal)] == []

    procedural = _node(
        kc_type="procedural",
        description="Find the missing angle.",
        outline="Find the angle.",
        topics=[{"topic": "Add the angles", "goal": "Say what adding did"}],
        type_fields={
            "steps": ["Add the angles", "Subtract from 180"],
            "blanked_step": 1,
            "solo_problem": "Find the third angle.",
            "solo_check": "80",
        },
        misconceptions=[],
    )
    procedural_moves = moves_for(procedural, profile, goal)
    assert [move.key for move in procedural_moves] == [
        "orient",
        "topic-1",
        "topic-2",
        "decide",
        "faded",
        "solo",
        "why_order",
    ]
    assert procedural_moves[1].name == "Add the angles"
    assert procedural_moves[2].name == "Subtract from 180"
    no_solo = _node(
        kc_type="procedural",
        description="",
        type_fields={"steps": ["Add the angles"], "blanked_step": 0, "solo_problem": "", "solo_check": ""},
        misconceptions=[],
    )
    assert [move.key for move in moves_for(no_solo, _profile(self_explanation=False), goal)] == [
        "topic-1",
        "decide",
        "faded",
    ]

    conceptual = _node(
        kc_type="conceptual",
        description="",
        type_fields={"case_a": "Wide", "case_b": "", "prediction": "Will it float?", "rule": "", "transfer_case": ""},
        misconceptions=[],
    )
    assert [move.key for move in moves_for(conceptual, profile, goal)] == ["predict_a"]

    causal = _node(
        kc_type="causal",
        description="Outline: Not the outline.\nTopics: not-a-link\nGoals: Not the goal",
        outline="A tax.",
        topics=[{"topic": "prices rise", "goal": "Say why prices rise"}],
        type_fields={
            "decision_point": "A council sets a tax.",
            "flawed_claim": "The tax lowers prices.",
            "causal_chain": "The tax rises, so buyers pay more.",
            "counterfactual": "",
        },
        misconceptions=[],
    )
    assert [move.key for move in moves_for(causal, profile, goal)] == ["orient", "topic-1", "stake", "mark", "defend"]
    assert moves_for(causal, profile, goal)[4].choice is False
    marked = next(move for move in moves_for(causal, profile, goal) if move.key == "mark")
    assert marked.choice is True

    synthesis = _node(
        kc_type="synthesis",
        description="",
        core_truth="Use both pieces.",
        type_fields={"mixes": ["earlier-a", "earlier-b"], "faulty_plan": "The rookie swaps them."},
        misconceptions=[],
    )
    assert [move.key for move in moves_for(synthesis, profile, goal)] == [
        "orient",
        "topic-1",
        "topic-2",
        "faulty",
        "correct",
        "which_job",
    ]


def test_an_empty_pair_is_skipped_and_the_description_is_not_the_walk() -> None:
    node = _node(
        description="Outline: Hidden.\nTopics: secret\nGoals: Find the secret",
        outline="Setup.",
        topics=[
            {"topic": "color", "goal": ""},
            {"topic": "", "goal": "Nope"},
            {"topic": "banks", "goal": "Name a bank"},
        ],
        type_fields={"fact": "", "retrieval_question": ""},
    )
    moves = moves_for(node, _profile(), _goal())
    assert [move.key for move in moves] == ["orient", "topic-1"]
    assert moves[1].name == "banks"
    assert moves[1].evidence == ("goal-1",)
