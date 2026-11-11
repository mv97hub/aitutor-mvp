"""The KC chats ask the model to plan, then to write the component."""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

from app.kc_model import (
    CREATOR_RULES,
    DEFAULT_KC_CHAT_MODEL,
    KC_CHAT_MODELS,
    checked_discussion,
    checked_model,
    creator_bundle,
)

def _sib(codes: list[str]) -> list[dict]:
    return [
        {"code": code, "title": code.replace("-", " ").title(), "summary": f"About {code}."} for code in codes
    ]


GEOMETRY = (
    "Tell congruent triangles apart, find a missing angle, and explain why "
    "two sides and a non-included angle do not prove congruence."
)


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
        siblings=_sib(["missing-angle"]),
        previous=None,
        message="Draft this component.",
        model="gpt-4.1",
    )
    prompt = bundle["system_prompt"]
    assert "You are an expert curriculum maker for one knowledge component of a course." in prompt
    assert "Fill every field that can be entered" in prompt
    assert "title, description, outline, core_truth," in prompt
    assert "Mastery is the fuller rigorous treatment" in prompt
    assert "description" in bundle["schema"]["required"]
    assert "Outline: The interior angles." in prompt
    assert "outline" in bundle["schema"]["required"]
    assert "blocks" in bundle["schema"]["required"]
    blocks = bundle["schema"]["properties"]["blocks"]
    assert blocks["type"] == "array"
    assert "topics" not in bundle["schema"]["properties"]
    assert "Go into the topic before you fill the outline, the core truth, the blocks, and the links." in prompt
    assert "The discussion answers the latest user message." in prompt
    assert "Do not change how an answer is scored" in prompt
    assert CREATOR_RULES.split(".")[0] in prompt
    assert checked_discussion("Here is the draft.", "Triangle angle sum") == "Here is the draft."
    with pytest.raises(ValueError, match="before you fill"):
        checked_discussion("Title:", "Triangle angle sum")
    with pytest.raises(ValueError, match="latest message"):
        checked_discussion("  ", "Triangle angle sum")
    kept = checked_discussion(
        "Triangle angle sum is the fact that the three interior angles make a straight line, "
        "which is why a missing angle is the rest of 180 degrees.",
        "Triangle angle sum",
    )
    assert kept.startswith("Triangle angle sum")


def test_a_follow_up_answers_the_message_and_revises_only_those_blocks() -> None:
    bundle = creator_bundle(
        course_title="Euclidean geometry",
        course_description=GEOMETRY,
        audience="12-14",
        kind="mastery",
        minutes=None,
        node_title="Triangle angle sum",
        node_code="angle-sum",
        node_description="Outline: The interior angles.\nTopics: 180 degrees\nGoals: State the sum",
        siblings=_sib(["missing-angle"]),
        previous={
            "core_truth": "Angles sum to 180.",
            "blocks": [{"id": "blk_1", "type": "topic_goal", "data": {"topic": "sum", "goal": "State it"}}],
        },
        message="what else should this course cover?",
        model="gpt-4.1",
    )
    prompt = bundle["system_prompt"]
    assert bundle["user_prompt"] == "what else should this course cover?"
    assert "This message is a follow-up." in prompt
    assert "say what to add or change and why" in prompt
    assert "Revise only the blocks that message is about." in prompt
    assert "Still return the full draft so Push draft stays a straight copy." in prompt
    assert "Current blocks: topic_goal." in prompt
    assert checked_discussion("Cover congruence next.", "Triangle angle sum") == "Cover congruence next."


def test_draft_reply_lists_filled_block_fields() -> None:
    from app.kc import _draft_reply

    text = _draft_reply(
        {
            "title": "River fact",
            "description": "The river is blue.",
            "outline": "How the river looks.",
            "topics": [{"topic": "color", "goal": "Recall the color"}],
            "kc_type": "factual",
            "type_fields": {"fact": "The river is blue.", "retrieval_question": "What color?"},
            "core_truth": "The river is blue.",
            "rubric": ["Recall the color"],
            "blocks": [
                {
                    "id": "blk_1",
                    "type": "topic_goal",
                    "data": {
                        "topic": "color",
                        "goal": "Recall the color",
                        "acceptance_criteria": "",
                        "teaching_notes": "Use the banks.",
                    },
                },
                {
                    "id": "blk_2",
                    "type": "mcq",
                    "data": {
                        "mode": "static",
                        "question_stem": "What color is the river?",
                        "choices": [
                            {
                                "id": "a",
                                "text": "blue",
                                "is_correct": True,
                                "distractor_rationale": "",
                                "misconception_code": "",
                            },
                            {
                                "id": "b",
                                "text": "red",
                                "is_correct": False,
                                "distractor_rationale": "the banks look red",
                                "misconception_code": "zz-other",
                            },
                        ],
                        "correct_explanation": "It is blue.",
                        "target_skill": None,
                    },
                },
                {
                    "id": "blk_3",
                    "type": "socratic",
                    "data": {
                        "central_dilemma": "Why is it blue?",
                        "initial_probe": "What do you think?",
                        "counterexamples": ["A muddy river", ""],
                        "target_synthesis": "Depth and sky.",
                    },
                },
                {
                    "id": "blk_4",
                    "type": "worked_example",
                    "data": {
                        "problem_statement": "Name the color",
                        "steps": [
                            {"step_text": "Look", "rationale": "the water"},
                            {"step_text": "Name it", "rationale": None},
                        ],
                        "faded_step_index": 1,
                        "solo_problem": "A new river",
                        "solo_expected_answer": "blue",
                    },
                },
            ],
            "misconceptions": [{"wrong_move": "It is red", "broken_kc": "zz-other"}],
            "prerequisite_codes": ["zz-other"],
            "encompasses_codes": [],
        }
    )
    assert text == (
        "Draft for River fact only. Other components stay as they are.\n"
        "Description: The river is blue.\n"
        "Outline: How the river looks.\n"
        "1. Topic / Goal\n"
        "Topic: color\n"
        "Goal: Recall the color\n"
        "Teaching notes: Use the banks.\n"
        "2. Multiple Choice Question\n"
        "Mode: static\n"
        "Question stem: What color is the river?\n"
        "Choices:\n"
        "- a. blue (correct)\n"
        "- b. red (trap: the banks look red; misconception: zz-other)\n"
        "Correct explanation: It is blue.\n"
        "3. Socratic Discussion\n"
        "Central dilemma: Why is it blue?\n"
        "Opening probe: What do you think?\n"
        "Counterexamples: A muddy river\n"
        "Target synthesis: Depth and sky.\n"
        "4. Worked Example + Faded Step\n"
        "Problem statement: Name the color\n"
        "Steps:\n"
        "- Look (the water)\n"
        "- Name it\n"
        "Faded step: 1\n"
        "Solo problem: A new river\n"
        "Solo expected answer: blue\n"
        "Core truth: The river is blue.\n"
        "Misconceptions: It is red (zz-other)\n"
        "Prerequisites: zz-other\n"
        "Encompasses: none\n"
        "Nothing is saved until you push it."
    )
    assert "\nTopics:" not in text
    assert "\nType:" not in text
    assert "Fact:" not in text
    assert "Retrieval question:" not in text
    assert "Rubric:" not in text


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
        siblings=_sib(["missing-angle", "congruence"]),
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
        siblings=_sib([]),
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
        siblings=_sib(other_codes),
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
    variants = props["blocks"]["items"]["anyOf"]
    assert "topic_goal" in [item["properties"]["type"]["enum"][0] for item in variants]
    assert "allOf" not in bundle["schema"]
    prompt = bundle["system_prompt"]
    assert "ordered blocks[] array" in prompt
    assert "Do not ask for two mixes." not in prompt
    assert "history" not in props


def test_creator_schema_keeps_each_block_type_on_its_own_fields() -> None:
    bundle = creator_bundle(
        course_title="Euclidean geometry",
        course_description=GEOMETRY,
        audience="12-14",
        kind="mastery",
        minutes=None,
        node_title="Triangle angle sum",
        node_code="angle-sum",
        node_description="The interior angles add to a straight line.",
        allowed_block_types=["topic_goal", "mcq"],
        siblings=_sib(["missing-angle"]),
        previous=None,
        message="Draft this component.",
        model="gpt-4.1",
    )
    prompt = bundle["system_prompt"]
    assert "You may ONLY generate blocks" in prompt
    assert "topic_goal" in prompt
    assert "mcq" in prompt
    assert "socratic" not in prompt
    variants = bundle["schema"]["properties"]["blocks"]["items"]["anyOf"]
    assert [item["properties"]["type"]["enum"] for item in variants] == [["topic_goal"], ["mcq"]]
    topic = variants[0]["properties"]["data"]
    assert topic["required"] == ["topic", "goal", "acceptance_criteria", "teaching_notes"]
    assert topic["additionalProperties"] is False
    assert topic["properties"]["topic"]["type"] == "string"
    assert topic["properties"]["goal"]["type"] == "string"
    assert topic["properties"]["acceptance_criteria"]["type"] == ["string", "null"]
    assert topic["properties"]["teaching_notes"]["type"] == ["string", "null"]
    assert "question_stem" not in topic["properties"]
    assert "case_a" not in topic["properties"]
    modes = variants[1]["properties"]["data"]["anyOf"]
    static, dynamic = modes
    assert static["required"] == ["mode", "question_stem", "choices", "correct_explanation"]
    assert static["properties"]["question_stem"]["type"] == "string"
    assert static["properties"]["correct_explanation"]["type"] == ["string", "null"]
    assert "target_skill" not in static["properties"]
    choice = static["properties"]["choices"]["items"]
    assert choice["required"] == ["id", "text", "is_correct", "distractor_rationale", "misconception_code"]
    assert choice["properties"]["text"]["type"] == "string"
    assert choice["properties"]["is_correct"]["type"] == "boolean"
    assert choice["properties"]["distractor_rationale"]["type"] == ["string", "null"]
    assert choice["properties"]["misconception_code"]["type"] == ["string", "null"]
    assert dynamic["required"] == [
        "mode",
        "target_skill",
        "distractor_guidance",
        "difficulty",
        "num_choices",
        "stem_constraints",
    ]
    assert dynamic["properties"]["target_skill"]["type"] == "string"
    assert dynamic["properties"]["distractor_guidance"]["type"] == "string"
    assert dynamic["properties"]["difficulty"]["type"] == ["string", "null"]
    assert dynamic["properties"]["num_choices"]["type"] == ["integer", "null"]
    assert dynamic["properties"]["num_choices"]["minimum"] == 3
    assert dynamic["properties"]["num_choices"]["maximum"] == 5
    assert dynamic["properties"]["stem_constraints"]["type"] == ["string", "null"]
    assert "question_stem" not in dynamic["properties"]


def _strict_schema_gaps(node: object, path: str = "$") -> list[str]:
    """The OpenAI strict rule that produced invalid_json_schema for kc_draft."""
    gaps: list[str] = []
    if isinstance(node, dict):
        properties = node.get("properties")
        if isinstance(properties, dict):
            required = node.get("required")
            if node.get("additionalProperties") is not False:
                gaps.append(f"{path} additionalProperties must be false")
            if not isinstance(required, list) or list(required) != list(properties):
                missing = [key for key in properties if not isinstance(required, list) or key not in required]
                gaps.append(f"{path} required must include every property. Missing {missing}.")
        for key, value in node.items():
            gaps.extend(_strict_schema_gaps(value, f"{path}.{key}"))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            gaps.extend(_strict_schema_gaps(value, f"{path}[{index}]"))
    return gaps


def test_creator_schema_accepts_strict_structured_output() -> None:
    full = _creator(["missing-angle"])
    gaps = _strict_schema_gaps(full["schema"])
    assert gaps == [], "invalid_json_schema: " + "; ".join(gaps)
    variants = full["schema"]["properties"]["blocks"]["items"]["anyOf"]
    by_type = {item["properties"]["type"]["enum"][0]: item["properties"]["data"] for item in variants}
    assert list(by_type) == [
        "topic_goal",
        "mcq",
        "case_study",
        "socratic",
        "curiosity",
        "worked_example",
        "spot_the_flaw",
        "teach_back",
        "retrieval_check",
        "explanation",
    ]
    topic = by_type["topic_goal"]
    assert "acceptance_criteria" in topic["required"]
    assert topic["properties"]["acceptance_criteria"]["type"] == ["string", "null"]
    assert topic["properties"]["topic"]["type"] == "string"
    worked = by_type["worked_example"]
    assert worked["properties"]["faded_step_index"]["type"] == ["integer", "null"]
    assert worked["properties"]["solo_problem"]["type"] == "string"
    assert worked["properties"]["steps"]["items"]["properties"]["rationale"]["type"] == ["string", "null"]
    assert worked["properties"]["steps"]["items"]["properties"]["step_text"]["type"] == "string"
    assert by_type["curiosity"]["properties"]["wonder_branches"]["type"] == ["array", "null"]
    assert by_type["teach_back"]["properties"]["peer_follow_up_question"]["type"] == "string"
    assert "case_a" not in topic["properties"]
    narrow = creator_bundle(
        course_title="Euclidean geometry",
        course_description=GEOMETRY,
        audience="12-14",
        kind="mastery",
        minutes=None,
        node_title="Triangle angle sum",
        node_code="angle-sum",
        node_description="The interior angles add to a straight line.",
        allowed_block_types=["topic_goal"],
        siblings=_sib(["missing-angle"]),
        previous=None,
        message="Draft this component.",
        model="gpt-4.1",
    )
    items = narrow["schema"]["properties"]["blocks"]["items"]
    assert "anyOf" not in items
    assert items["properties"]["type"]["enum"] == ["topic_goal"]
    assert "question_stem" not in items["properties"]["data"]["properties"]
    assert _strict_schema_gaps(narrow["schema"]) == []


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
