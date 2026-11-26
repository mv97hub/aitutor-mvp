"""Small selectable lesson components for the named, synthetic regression scenarios."""

from app.kc_course_io import SCHEMA, _BLOCK_EXAMPLES

SCENARIO_FIXTURE_CODE = "harness-profile-scenarios"
FORMULA = "The inflation rate is the change in CPI divided by the old CPI, times 100."
RATE = "CPI rose from 120 to 132. What was the percentage inflation rate?"
RATE_ANSWER = "The index rose by 12 points. 12 divided by 120 is 0.1, or 10%."
HAMLET = (
    "To be, or not to be, that is the question:\n"
    "Whether 'tis nobler in the mind to suffer\n"
    "The slings and arrows of outrageous fortune,\n"
    "Or to take arms against a sea of troubles."
)


def _component(code, title, aim, blocks):
    return {
        "code": f"harness-scenario-{code}", "title": title, "description": aim, "summary": aim,
        "core_truth": aim, "outline": aim, "rubric": [aim], "standards": ["hs1"],
        "blocks": [{"id": f"{code}_{index}", "type": kind, "data": data} for index, (kind, data) in enumerate(blocks)],
    }


def scenario_fixture_document() -> dict:
    return {
        "schema": SCHEMA,
        "course": {
            "code": SCENARIO_FIXTURE_CODE, "title": "Harness fixture · learner scenarios", "subject": "Harness",
            "description": "Select a component to exercise a specific simulated learner scenario.",
            "grade_band": "9-11", "kind": "mastery", "estimated_minutes": 25,
            "brief": "Synthetic lessons for comparing a learner's observable actions. Select one component to keep a run small.",
            "outcomes": ["Explain a prediction or an inference using the evidence given."],
            "standards": [{"code": "hs1", "text": "Use the evidence given in each question."}],
        },
        "units": [{"title": "Learner scenarios", "summary": "Independent tests and a labelled difficulty stress case.",
                   "components": [
            _component("curiosity", "Predict what happens to ice", "Give a prediction and a reason.", [("curiosity", {
                "phenomenon_hook": "Two equal ice cubes sit on plates, one in sunlight and one in shade.",
                "prediction_question": "Which cube do you think will melt first? Why?",
                "bridge_to_unit": "The warmer surroundings transfer energy to the ice.", "wonder_branches": None,
            })]),
            _component("flaw", "Find the wrong total", "Explain why three pairs make six.", [("spot_the_flaw", {
                "rookie_work": "I counted three pairs of socks. Three plus two is five, so there are five socks.",
                "flaw_description": "Each of the three pairs has two socks.",
                "underlying_misconception": "Adding the number of pairs and the size of one pair.",
                "corrected_version": "Two plus two plus two makes six socks.",
            })]),
            _component("cpi", "Inflation formula, practice and a new topic",
                       "Use the starting index as the denominator in a percent change.", [
                ("retrieval_check", {"recall_prompt": "What is the formula for the inflation rate using CPI?",
                                     "expected_fact": FORMULA, "elaborative_why_prompt": "Why divide by the old index?",
                                     "expected_why_rationale": "The old index is the starting amount."}),
                ("worked_example", {"problem_statement": "CPI goes from 100 to 105. Work out the inflation rate.",
                                    "steps": [{"step_text": "Subtract 100 from 105 to get 5 points.", "rationale": "Find the change."},
                                              {"step_text": "Divide 5 by 100 and multiply by 100 to get 5%.",
                                               "rationale": "Use the starting index as the denominator."}],
                                    "faded_step_index": 1, "solo_problem": RATE, "solo_expected_answer": RATE_ANSWER}),
                ("retrieval_check", {"recall_prompt": "Who wrote Romeo and Juliet?", "expected_fact": "William Shakespeare.",
                                     "elaborative_why_prompt": "Is Romeo and Juliet a play or a novel?",
                                     "expected_why_rationale": "It is a play, written for actors to perform."}),
            ]),
            _component("choice", "Inflation choice and reasoning", "Explain why 12 points here equals 10 percent.", [("mcq", {
                "mode": "static", "question_stem": RATE, "choices": [
                    {"id": "a", "text": "10%", "is_correct": True},
                    {"id": "b", "text": "12%", "is_correct": False, "distractor_rationale": "Counts points as percent."}],
                "correct_explanation": RATE_ANSWER,
            })]),
            _component("inference", "Interpret a character's feelings", "Distinguish behavior from proof of a feeling.", [("socratic", {
                "central_dilemma": "In a fictional story, a child looks away when a caregiver returns.",
                "initial_probe": "Does avoidant behavior prove the character does not care about their caregiver?",
                "counterexamples": ["Consider another character who first looks away, then asks the caregiver for help."],
                "target_synthesis": "Avoidant behavior alone cannot prove how much a character cares.",
            })]),
            _component("river", "Short informational passage · River roads", "Connect the main idea to the river passage.",
                       [("passage_ela", _BLOCK_EXAMPLES["passage_ela"])]),
            _component("hamlet", "Difficulty stress case · Hamlet", "Interpret the opening contrast in Hamlet's speech.",
                       [("passage_ela", {"passage_title": "Hamlet, Act III", "passage_genre": "literary",
                                         "passage_text": HAMLET, "central_idea_question": "What is the central idea of this passage?",
                                         "expected_central_idea": "The speaker weighs enduring trouble against taking action.",
                                         "distractor_detail": "A sea is mentioned.", "evidence_prompt": "Find words for each alternative.",
                                         "verbatim_evidence_quotes": ["in the mind to suffer", "take arms against a sea of troubles."],
                                         "analysis_focus": "inference", "analysis_question": "What makes the choice difficult for the speaker?",
                                         "expected_analysis": "The speaker must weigh enduring hardship against taking action."})]),
        ]}],
    }
