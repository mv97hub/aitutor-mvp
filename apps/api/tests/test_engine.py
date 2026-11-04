import inspect
from pathlib import Path

from app.engine.assemble import RESPONSE_SCHEMA, TURN_TEMPERATURE, assemble, hint_tier_for, struggle_limit
from app.engine.defaults import age_band_for, profile_for_age
from app.engine.placeholders import affect_layer, memory_layer, metacognition_layer
from app.engine.types import (
    HintLadder,
    Layer1Beat,
    Layer2Student,
    Layer3Tutor,
    Layer4Discourse,
    Layer5Affect,
    MisconceptionTrap,
    RubricCriterion,
    WidgetChoice,
    WidgetTask,
)


def _beat(**overrides) -> Layer1Beat:
    base = dict(
        course_title="Ancient Rome",
        unit_title="The Republic",
        continuity="King Tarquin abused solo lifetime power. The Republic answered with two consuls.",
        quest_code="ROM-U2-Q1",
        quest_title="The Two-Captain Rule",
        beat_role="mystery_hook",
        beat_position=1,
        beat_count=4,
        bloom_level="analyze",
        cognitive_load="medium",
        prompt="What is one advantage and one problem of two consuls?",
        rubric=(
            RubricCriterion("advantage", "Stops one bully.", 50),
            RubricCriterion("problem", "Names deadlock.", 50),
        ),
        misconceptions=(
            MisconceptionTrap("solo", "One boss is always safer.", "The veto is the check."),
        ),
        hint_ladder=HintLadder("Ask about an attack.", "Two kids, one controller.", "Fill in the blank."),
        widget=None,
        pass_score=70,
        gate_cleared=False,
        finished=False,
    )
    base.update(overrides)
    return Layer1Beat(**base)


def _layers():
    return (
        _beat(),
        Layer2Student(
            display_name="Storm",
            age_band="9-11",
            reading_level="middle-grade",
            modality="story",
            interests=("weather",),
            attempt_count=0,
            zpd="on-level",
        ),
        Layer3Tutor(
            persona="Curious Co-Explorer",
            lexicon="vivid middle-grade",
            metaphors="sports-team captain and playground rules",
            sidekick="a sidekick with a clear flaw",
        ),
        Layer4Discourse(
            socratic_strictness="balanced",
            struggle_window="minimum",
            anti_spoiler=True,
            pacing="short-turns-one-question",
        ),
        affect_layer(),
        metacognition_layer(),
        memory_layer(),
    )


def test_assemble_takes_seven_separate_layers() -> None:
    names = [name for name, param in inspect.signature(assemble).parameters.items() if param.kind is param.POSITIONAL_OR_KEYWORD]
    assert names == [
        "beat",
        "student",
        "tutor",
        "discourse",
        "affect",
        "metacognition",
        "memory",
    ]


def test_engine_package_does_not_import_the_database() -> None:
    root = Path(__file__).resolve().parents[1] / "app" / "engine"
    text = "\n".join(path.read_text() for path in root.glob("*.py"))
    assert "sqlalchemy" not in text
    assert "app.models" not in text
    assert "app.database" not in text


def test_prompt_includes_all_seven_layers_and_keeps_tutor_settings_apart() -> None:
    bundle = assemble(*_layers())
    text = bundle.system_prompt
    assert bundle.temperature == TURN_TEMPERATURE
    assert bundle.response_schema == RESPONSE_SCHEMA
    assert bundle.response_schema["required"] == [
        "reply",
        "rubric_met",
        "misconception",
        "hint_tier",
        "advance",
        "diagram",
    ]
    for heading in (
        "Layer 1 — Active move",
        "Layer 2 — Student",
        "Layer 3 — Tutor agent",
        "Layer 4 — Discourse",
        "Layer 5 — Affect",
        "Layer 6 — Metacognition",
        "Layer 7 — Memory",
    ):
        assert heading in text
    student = text.split("Layer 2 — Student", 1)[1].split("Layer 3 — Tutor agent", 1)[0]
    tutor = text.split("Layer 3 — Tutor agent", 1)[1].split("Layer 4 — Discourse", 1)[0]
    assert "weather" in student
    assert "Curious Co-Explorer" not in student
    assert "Curious Co-Explorer" in tutor
    assert "weather" not in tutor
    assert "Growth-mindset praise only" in text
    assert "one self-explanation line" in text
    assert "No live Leitner scheduling" in text
    assert "stating the answer that passes the move is not" in text.lower()
    assert "worked answer" not in text.lower()
    assert "At most a few sentences" not in text
    assert "Teach, then ask." in text
    assert "One question per turn, and it comes last." in text
    assert "student could retell" in text
    assert "Do not say hint to the student." in text
    assert "Do not ask a second question." in text
    assert "Do not teach the next move." in text
    assert "King Tarquin abused solo lifetime power" in text
    assert "advantage (weight 50)" in text
    assert "Live hint tier for this turn: nudge" in text


def test_attempt_count_selects_the_hint_rung() -> None:
    layers = list(_layers())
    layers[1] = Layer2Student(
        display_name="Storm",
        age_band="9-11",
        reading_level="middle-grade",
        modality="story",
        interests=(),
        attempt_count=2,
        zpd="support",
    )
    text = assemble(*layers).system_prompt
    assert hint_tier_for(2) == "scaffold"
    assert "Live hint tier for this turn: scaffold" in text
    assert "Fill in the blank." in text


def test_struggle_window_then_worked_answer() -> None:
    assert struggle_limit("minimum") == 2
    layers = list(_layers())
    layers[1] = Layer2Student(
        display_name="Storm",
        age_band="9-11",
        reading_level="middle-grade",
        modality="story",
        interests=(),
        attempt_count=2,
        zpd="support",
    )
    text = assemble(*layers).system_prompt
    assert "The struggle window is over" in text
    assert "why the worked answer fits" in text.lower()
    assert "Set advance to true" in text
    assert "stating the answer that passes the move is not" not in text.lower()


def test_kickoff_states_the_goal_and_not_later_answers() -> None:
    layers = list(_layers())
    layers[0] = _beat(
        learning_goal="Two consuls can veto each other, which stops a new king and can deadlock.",
        success_criterion=(
            RubricCriterion("veto", "Each consul can veto.", 50),
            RubricCriterion("stall", "They can deadlock.", 50),
        ),
        beat_objectives=("Later answer: the plebeian walkout of 494.",),
    )
    text = assemble(*layers, kickoff=True).system_prompt
    assert "what finished work looks like" in text
    assert "short teaching of the first idea" in text
    assert "Do not ask them to pick an answer." in text
    assert "Do not invent a different topic" in text
    assert "Two consuls can veto each other, which stops a new king and can deadlock." in text
    assert "Done looks like:" in text
    assert "plebeian walkout of 494" not in text
    assert "Do not preview later moves" in text
    assert "advance to false" in text


def test_opening_hold_keeps_the_choice_out_of_the_kickoff() -> None:
    widget = WidgetTask(
        type="multi",
        prompt="Which of these are archaeological clues?",
        choices=(
            WidgetChoice("wall", "A wall dated to early Rome.", ""),
            WidgetChoice("pottery", "Pottery found under the Forum.", ""),
        ),
        answer=("wall", "pottery"),
        explain=False,
        grade=None,
    )
    layers = list(_layers())
    layers[0] = _beat(
        beat_role="try",
        prompt="Which of these are archaeological clues rather than the wolf legend?",
        widget=widget,
        learning_goal="I can tell a legend from an archaeological clue.",
    )
    text = assemble(*layers, kickoff=True, hold_widget=True).system_prompt
    assert "what finished work looks like" in text
    assert "choice widget is not on screen" in text
    assert "Invite them to choose" not in text
    assert "pottery" not in text.lower()
    assert "Which of these are archaeological clues" not in text
    reply = assemble(*layers, hold_widget=True).system_prompt
    assert "not on screen yet" in reply
    assert "This reply teaches the move." in reply
    assert "appears after this reply" not in reply
    assert "own words" in reply
    assert "Invite them to choose" not in reply
    assert "pottery" not in reply.lower()
    graded = assemble(*layers, hold_widget=True, grade_writing=True).system_prompt
    assert "Mark rubric_met from those words." in graded
    assert "Set rubric_met to []" not in graded.split("The choice widget is not on screen yet.")[-1]


def test_check_and_unstick_are_the_only_times_the_choices_appear() -> None:
    widget = WidgetTask(
        type="multi",
        prompt="Which of these are archaeological clues?",
        choices=(
            WidgetChoice("wall", "A wall dated to early Rome.", ""),
            WidgetChoice("pottery", "Pottery found under the Forum.", ""),
        ),
        answer=("wall", "pottery"),
        explain=False,
        grade=None,
    )
    layers = list(_layers())
    layers[0] = _beat(widget=widget, beat_role="try", prompt="Sort a find from a story.")
    layers[1] = Layer2Student(
        display_name="Storm",
        age_band="9-11",
        reading_level="middle-grade",
        modality="story",
        interests=(),
        attempt_count=2,
        zpd="support",
    )
    check = assemble(*layers, widget_offer="check", withhold_answer=True).system_prompt
    assert "explained in their own words" in check
    assert "Invite them to choose" in check
    assert "Correct answer, for you only" not in check
    assert "The struggle window is over" not in check
    unstick = assemble(*layers, widget_offer="unstick", withhold_answer=True).system_prompt
    assert "one structured try" in unstick
    assert "about to open" in unstick
    assert "Correct answer, for you only" not in unstick
    assert "The struggle window is over" not in unstick


def test_widget_answer_stays_hidden_until_the_window() -> None:
    widget = WidgetTask(
        type="single",
        prompt="Which one?",
        choices=(WidgetChoice("deadlock", "They stall.", ""), WidgetChoice("king", "One becomes king.", "no")),
        answer="deadlock",
        explain=False,
        grade=None,
    )
    layers = list(_layers())
    layers[0] = _beat(widget=widget, beat_role="try")
    hidden = assemble(*layers).system_prompt
    assert "Correct answer, for you only" not in hidden
    assert "stays hidden" in hidden
    layers[1] = Layer2Student(
        display_name="Storm",
        age_band="9-11",
        reading_level="middle-grade",
        modality="story",
        interests=(),
        attempt_count=2,
        zpd="support",
    )
    shown = assemble(*layers).system_prompt
    assert "Correct answer, for you only: deadlock." in shown
    assert "worked answer" in shown.lower()


def test_a_failed_try_gets_a_fuller_explanation() -> None:
    layers = list(_layers())
    layers[1] = Layer2Student(
        display_name="Storm",
        age_band="9-11",
        reading_level="middle-grade",
        modality="story",
        interests=(),
        attempt_count=1,
        zpd="support",
    )
    text = assemble(*layers).system_prompt
    assert "The student missed." in text
    assert "what they tried" in text
    assert "what the idea actually is" in text
    assert "Do not give the worked answer yet." in text
    assert "Do not say hint to the student." in text
    assert "Do not ask a second question." in text
    assert "Do not teach the next move." in text
    assert "The struggle window is over" not in text


def test_engage_and_name_teach_before_the_question() -> None:
    layers = list(_layers())
    layers[0] = _beat(
        beat_role="engage",
        prompt="Two consuls can each veto, which stops a king and can also deadlock.",
    )
    engage = assemble(*layers).system_prompt
    assert "Expand this idea" in engage
    assert "Do not turn it into a quiz stem." in engage
    assert "The one question comes last." in engage
    assert "No choice box." in engage
    assert "Two consuls can each veto" in engage
    layers[0] = _beat(
        beat_role="name",
        prompt="A veto stops a king, and the same veto can freeze a decision.",
    )
    name = assemble(*layers).system_prompt
    assert "Name teaches, then asks." in name
    assert "set advance to true" in name.lower()
    assert "Do not start the next move." in name


def _discourse(**overrides) -> Layer4Discourse:
    base = dict(
        socratic_strictness="balanced",
        struggle_window="minimum",
        anti_spoiler=True,
        pacing="short-turns-one-question",
    )
    base.update(overrides)
    return Layer4Discourse(**base)


def _with_discourse(**overrides):
    layers = list(_layers())
    layers[3] = _discourse(**overrides)
    return layers


def test_socratic_slider_asks_before_it_explains() -> None:
    assert struggle_limit("short") == 1
    assert struggle_limit("standard") == 2
    assert struggle_limit("long") == 3
    text = assemble(*_with_discourse(instructive=1)).system_prompt
    assert "One short question" in text
    assert "Almost no explanation" in text
    assert "Teach, then ask." not in text
    layers = _with_discourse(instructive=1)
    layers[1] = Layer2Student(
        display_name="Storm",
        age_band="9-11",
        reading_level="middle-grade",
        modality="story",
        interests=(),
        attempt_count=1,
        zpd="support",
    )
    missed = assemble(*layers).system_prompt
    assert "almost no explanation" in missed.lower()
    assert "The student missed. Explain what they tried" not in missed
    assert "The struggle window is over" not in missed


def test_instructive_slider_teaches_longer_and_explains_a_miss_sooner() -> None:
    opening = assemble(*_with_discourse(instructive=5)).system_prompt
    assert "fuller lesson" in opening.lower()
    assert "why it matters" in opening.lower()
    assert "longer explanation" in opening.lower()
    layers = _with_discourse(instructive=5)
    layers[1] = Layer2Student(
        display_name="Storm",
        age_band="9-11",
        reading_level="middle-grade",
        modality="story",
        interests=(),
        attempt_count=1,
        zpd="support",
    )
    missed = assemble(*layers).system_prompt
    assert "longer explanation" in missed.lower()
    assert "Do not wait" in missed
    assert "The struggle window is over" not in missed


def test_switches_change_questions_interests_and_praise() -> None:
    questions = assemble(*_with_discourse(one_question=False)).system_prompt
    assert "Do not ask a second question." not in questions
    assert "second question is allowed" in questions.lower()
    interests = assemble(*_with_discourse(use_interests=False)).system_prompt
    assert "Examples stay on the subject" in interests
    assert "Do not use those hobbies" in interests
    layers = list(_layers())
    layers[4] = Layer5Affect(praise="result-or-effort")
    praise = assemble(*layers).system_prompt
    assert "Growth-mindset praise is off" in praise
    assert "Growth-mindset praise only" not in praise


def test_closed_tutor_choices_and_sidekick_off() -> None:
    layers = list(_layers())
    layers[2] = Layer3Tutor(
        persona="debate-moderator",
        lexicon="analytical-high-school",
        metaphors="none",
        sidekick="off",
    )
    layers[0] = _beat(beat_role="teach_back")
    text = assemble(*layers).system_prompt
    assert "debate moderator" in text.lower()
    assert "plain language only" in text.lower()
    assert "Sidekick is off" in text
    assert "Do not invent a partner" in text


def test_diagram_prompt_is_a_geometry_triangle_when_a_picture_helps() -> None:
    rome = assemble(*_layers())
    described = str(rome.response_schema["properties"]["diagram"])
    assert "triangle" in described
    assert "graph" in described
    assert "map" in described
    assert "only when a picture makes that idea clearer" in rome.system_prompt
    assert "A triangle is only inside the geometry course." in rome.system_prompt
    layers = list(_layers())
    layers[0] = _beat(course_code="geometry", course_title="Euclidean and Coordinate Geometry I")
    geometry = assemble(*layers).system_prompt
    assert "only when a picture makes that idea clearer" in geometry
    assert 'kind "triangle"' in geometry
    assert "This course gets no picture." not in geometry


def test_course_scope_rule_names_the_course_only_when_the_switch_is_on() -> None:
    on = assemble(*_layers()).system_prompt
    assert on.split("Layer 1", 1)[0].startswith("You are the tutor for Storm.")
    assert "Stay on Ancient Rome." in on.split("Layer 1", 1)[0]
    assert "Depth inside Ancient Rome stays allowed" in on
    assert (
        "go as deep as the student needs on Ancient Rome, unit The Republic, "
        "and quest The Two-Captain Rule, including closely related ideas that serve this learning goal."
    ) in on
    assert "acknowledge it in one short line and return to Ancient Rome." in on
    assert "Do not explain that subject." in on
    assert "Do not keep chatting about it." in on
    assert "If they wander off, answer in one sentence and come back." not in on
    assert "stay on topic" not in on.lower()
    assert "Teach, then ask." in on

    off = assemble(*_with_discourse(stay_on_course=False)).system_prompt
    assert "Stay on Ancient Rome." not in off
    assert "acknowledge it in one short line" not in off
    assert "If they wander off, answer in one sentence and come back." in off
    assert "Teach, then ask." in off

    layers = list(_layers())
    layers[1] = Layer2Student(
        display_name="Storm",
        age_band="9-11",
        reading_level="middle-grade",
        modality="story",
        interests=(),
        attempt_count=2,
        zpd="support",
    )
    revealed = assemble(*layers).system_prompt
    assert "The struggle window is over" in revealed
    assert "why the worked answer fits" in revealed.lower()
    assert "Stay on Ancient Rome." in revealed
    assert "acknowledge it in one short line and return to Ancient Rome." in revealed


def test_studio_goals_are_walked_and_an_empty_show_close_ends_without_a_question() -> None:
    from app.engine.types import GoalPoint

    baseline = assemble(*_layers()).system_prompt
    assert "Walk these goals in order" not in baseline
    assert "The close has no question" not in baseline
    layers = list(_layers())
    layers[0] = _beat(
        beat_role="show",
        goals=(
            GoalPoint(
                "Understand that the angles of a triangle add to 180°",
                "States that the three angles add to 180° and uses that to find a missing angle.",
            ),
            GoalPoint("Name an exterior angle", "Points to an exterior angle on a drawn triangle."),
        ),
    )
    walked = assemble(*layers).system_prompt
    assert "Walk these goals in order" in walked
    assert "Goal 1:" in walked and "Goal 2:" in walked
    assert "Criterion 1:" in walked and "Criterion 2:" in walked
    assert "The close has no question" not in walked
    layers[0] = _beat(beat_role="show", empty_close=True)
    empty = assemble(*layers).system_prompt
    assert "The close has no question. End the quest without asking one. Set advance to true." in empty
    layers[0] = _beat(beat_role="engage")
    engage_plain = assemble(*layers).system_prompt
    layers[0] = _beat(beat_role="engage", empty_close=True)
    assert assemble(*layers).system_prompt == engage_plain
    assert "The close has no question" not in engage_plain


def test_age_band_defaults() -> None:
    assert age_band_for(10) == "9-11"
    assert age_band_for(13) == "12-14"
    assert age_band_for(16) == "15-17"
    assert "Co-Explorer" in profile_for_age(10).persona
    assert "Commander" in profile_for_age(13).persona
    assert "Moderator" in profile_for_age(16).persona
    assert profile_for_age(16).socratic_strictness == "balanced"
    assert profile_for_age(13).anti_spoiler is True
    assert profile_for_age(10).pacing == "short-turns-one-question"
