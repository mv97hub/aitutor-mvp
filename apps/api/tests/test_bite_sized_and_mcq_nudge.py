"""Regression tests for bite_sized length cap and Try-1 MCQ wrong-pick non-reveal guard (run 826d51c0)."""

from __future__ import annotations

from tests.test_kc_prompt import _node, _section, _student, _text


def _mcq_node():
    return _node(
        code="HIST-1",
        title="Treaty of Versailles",
        description="Main terms of the 1919 treaty.",
        core_truth="Germany lost territory, colonies, and most of its military.",
        blocks=[
            {
                "id": "mcq-1",
                "type": "mcq",
                "data": {
                    "mode": "static",
                    "question_stem": "After World War I, what rule did Germany have to follow?",
                    "choices": [
                        {"id": "a", "text": "Give up land and most of its army.", "is_correct": True},
                        {
                            "id": "b",
                            "text": "Keep all of its colonies.",
                            "is_correct": False,
                            "distractor_rationale": "Germany lost all overseas colonies.",
                        },
                        {"id": "c", "text": "Have a very big army.", "is_correct": False},
                    ],
                    "correct_explanation": "Germany had to give up land, colonies, and shrink its army to 100,000.",
                },
            }
        ],
    )


def _explanation_node():
    return _node(
        code="HIST-EXP",
        title="Treaty of Versailles",
        description="Walkthrough of the 1919 treaty.",
        core_truth="The treaty ended WWI and imposed harsh terms on Germany.",
        blocks=[
            {
                "id": "exp-1",
                "type": "explanation",
                "data": {
                    "block_title": "The Treaty of Versailles",
                    "topics": [
                        {"title": "Ending the War", "explanation": "Leaders met in Paris in 1919 to end WWI."},
                        {"title": "Main Terms", "explanation": "Germany gave up land and reduced its army."},
                    ],
                },
            }
        ],
    )


def test_mcq_first_wrong_pick_adds_non_reveal_guard_and_withholds_correct_takeaway() -> None:
    prompt = _text(
        node=_mcq_node(),
        student=_student(age=6, child_profile={"reading_level": "emerging", "response_length": "bite_sized"}),
        opening=False,
        attempts=0,
        last_answer="Keep all of its colonies.",
        active_block_state={"substep": "choice", "dialogue_turns": 1, "block_attempts": 0},
    )
    this_turn = _section(prompt, "This turn")
    what_to_teach = _section(prompt, "What to teach")

    assert "Wrong-pick guard:" in this_turn
    assert "Do NOT name, quote, paraphrase, or give away the correct option." in this_turn
    assert "DO NOT NAME, QUOTE, PARAPHRASE, OR REVEAL ON THIS TURN" in what_to_teach
    assert "Correct explanation takeaway:" not in what_to_teach


def test_mcq_correct_or_reveal_turn_keeps_correct_explanation_takeaway() -> None:
    # Opening turn still retains the stored takeaway for planning.
    opening_prompt = _text(
        node=_mcq_node(),
        student=_student(age=10, child_profile={"response_length": "balanced"}),
        opening=True,
        attempts=0,
        last_answer="",
        active_block_state={"substep": "choice", "dialogue_turns": 0, "block_attempts": 0},
    )
    assert "Wrong-pick guard:" not in _section(opening_prompt, "This turn")
    assert "Correct explanation takeaway:" in _section(opening_prompt, "What to teach")

    # Exhausted-retries reveal turn does NOT block revealing the correct answer.
    reveal_prompt = _text(
        node=_mcq_node(),
        student=_student(age=6, child_profile={"reading_level": "emerging", "response_length": "bite_sized"}),
        opening=False,
        attempts=1,
        last_answer="Have a very big army.",
        active_block_state={"substep": "choice", "dialogue_turns": 2, "block_attempts": 1},
    )
    assert "Wrong-pick guard:" not in _section(reveal_prompt, "This turn")
    assert "Correct explanation takeaway:" in _section(reveal_prompt, "What to teach")


def test_bite_sized_enforces_two_sentence_cap_in_this_turn_and_explanation_transition() -> None:
    bite_prompt = _text(
        node=_explanation_node(),
        student=_student(age=6, child_profile={"reading_level": "emerging", "response_length": "bite_sized"}),
        opening=False,
        last_answer="Got it, move on!",
        active_block_state={"substep": "explain_topic", "topic_index": 0, "topic_taught": True, "dialogue_turns": 1},
    )
    this_turn = _section(bite_prompt, "This turn")
    what_to_teach = _section(bite_prompt, "What to teach")

    assert "Length cap (bite_sized):" in this_turn
    assert "at most 2 short sentences total (under 260 characters)" in this_turn
    assert "Keep the whole reply inside the bite_sized cap" in bite_prompt
    # Preserve existing phrase contract for explanation transitions.
    assert "teach the next topic in full" in bite_prompt.lower()

    # Balanced learners do NOT get the bite_sized 2-sentence cap.
    balanced_prompt = _text(
        node=_explanation_node(),
        student=_student(age=10, child_profile={"response_length": "balanced"}),
        opening=False,
        last_answer="Got it, move on!",
        active_block_state={"substep": "explain_topic", "topic_index": 0, "topic_taught": True, "dialogue_turns": 1},
    )
    assert "Length cap (bite_sized):" not in _section(balanced_prompt, "This turn")
    assert "inside the bite_sized cap" not in balanced_prompt
