"""Exercise scenario assignment and the learner/control breakdown without any model calls."""
from types import SimpleNamespace

from app import harness
from app.harness_report import run_summary


def test_seed_identifies_the_scenario_and_explicit_tutor_pairs_share_draws():
    def assign(personas, paired=False):
        return {
            (persona, model, repeat): harness.scenario_seed(
                19, persona, "course", "component", model, "profile", repeat, paired=paired
            )
            for persona in personas for model in ["tutor-a", "tutor-b"] for repeat in (1, 2)
        }

    rows = assign(["p1", "p2"])
    assert rows == assign(["p2", "p1"])
    assert len(set(rows.values())) == len(rows)
    paired = assign(["p1", "p2"], paired=True)
    assert paired["p1", "tutor-a", 1] == paired["p1", "tutor-b", 1]
    assert paired["p1", "tutor-a", 1] != paired["p1", "tutor-a", 2]


def test_only_passage_paragraphs_seen_in_this_block_are_offered_for_rereading():
    text = "The first tree was an oak.\n\nThe second was a cedar."
    messages = [SimpleNamespace(step=0, role="assistant", content=text),
                SimpleNamespace(step=1, role="assistant", content="Let's read. The first tree was an oak. What grew there?"),
                SimpleNamespace(step=1, role="user", content="The second was a cedar.")]
    assert harness.seen_passage(text, messages, 1) == "The first tree was an oak."


def test_reporting_counts_opportunities_by_profile_block_and_observed_outcome():
    def row(role, name, block, outcome):
        return {"simulation_role": role, "persona_name": name, "ended_how": "completed", "report_turns": [
            {"block_type_before": block, "learner_observation": outcome, "choice_fallback": False},
        ]}

    cases = [row("learner", "AI_Child5", "curiosity", "unscored"),
             row("answer_key_control", "AI_Child13", "spot_the_flaw", "advanced_after_attempt"),
             row("script", "AI_Child14", "spot_the_flaw", "stayed_after_attempt")]
    summary = run_summary(cases)
    counts = {(r["role"], r["profile"], r["block"], r["outcome"]): r["turns"] for r in summary["opportunities"]}
    assert counts == {("learner", "AI_Child5", "curiosity", "unscored"): 1,
                      ("answer_key_control", "AI_Child13", "spot_the_flaw", "advanced_after_attempt"): 1,
                      ("script", "AI_Child14", "spot_the_flaw", "stayed_after_attempt"): 1}
    assert "Learner-visible" in summary["text"]


def test_distinct_variant_streams_and_explicit_family_pairing():
    identity = (71, "child", "course", "node", "model", "profile", 1)
    a = {"scenario": "tentative", "group": "formula"}
    b = {"scenario": "plain", "group": "formula"}
    assert harness.scenario_seed(*identity, **a) != harness.scenario_seed(*identity, **b)
    assert harness.scenario_seed(*identity, **a, paired=True) == harness.scenario_seed(*identity, **b, paired=True)
    assert harness.scenario_seed(*identity, **a, paired=True) != harness.scenario_seed(
        *identity, scenario="aside", group="aside", paired=True
    )


def test_profile_roles_and_historical_seeds_survive_reordering_on_run_again():
    from app.database import SessionLocal
    from app.models import HarnessChat, HarnessRun, KcGoal, KcNode

    with SessionLocal() as db:
        personas = {row["number"]: str(row["id"]) for row in harness.add_starter_set(db)}
        node = KcNode(code="profile-seed-case", title="Practice")
        db.add(node)
        db.flush()
        goal = KcGoal(code="profile-seed-case", title="Practice course", target_kc_ids=[str(node.id)], ready=True)
        db.add(goal)
        db.flush()
        body = {"component_ids": [str(node.id)], "persona_ids": [personas[14], personas[5]],
                "tutor_models": ["gpt-4.1-mini"], "iterations": 2, "seed": 15, "behavior": "rule"}
        first = harness.create_run(db, body)
        roles = {row["child"]["number"]: row["child"]["simulation_role"] for row in first["chat_rows"]}
        assert roles == {14: "answer_key_control", 5: "learner"}
        # Old exported seeds used a positional formula. Do not recalculate them when re-running.
        old = {}
        for i, row in enumerate(first["chat_rows"]):
            chat = db.get(HarnessChat, row["id"])
            chat.seed = 900 + i
            old[(chat.persona_id, chat.iteration)] = chat.seed
        run = db.get(HarnessRun, first["id"])
        run.plan = {**run.plan, "persona_ids": list(reversed(body["persona_ids"]))}
        again = harness.run_again(db, run.id)
        assert {(c["persona_id"], c["iteration"]): c["seed"] for c in again["chat_rows"]} == old
        free = harness.create_run(db, {**body, "behavior": "free"})
        assert all(row["child"]["simulation_role"] == "learner" for row in free["chat_rows"])
        script = harness.create_run(db, {**body, "behavior": "script", "scenario": "example"})
        assert all(row["child"]["simulation_role"] == "script" for row in script["chat_rows"])


def test_paired_reader_variants_change_only_the_temporary_learners_response_length():
    from sqlalchemy import select
    from app.database import SessionLocal
    from app.harness_scenario_fixture import SCENARIO_FIXTURE_CODE
    from app.models import HarnessChat, HarnessPersona, KcGoal, Student

    with SessionLocal() as db:
        personas = {row["number"]: row for row in harness.add_starter_set(db)}
        harness.ensure_fixture(db)
        course = db.scalar(select(KcGoal).where(KcGoal.code == SCENARIO_FIXTURE_CODE))
        river = next(n for n in harness.load_targets(db, course) if n.code == "harness-scenario-river")
        for num in (2, 8):
            persona = db.get(HarnessPersona, personas[num]["id"])
            original = dict(persona.child_profile)
            seeds = set()
            for scenario, length in [("reread-short", "bite_sized"), ("reread-detail", "detailed")]:
                run = harness.create_run(db, {
                    "persona_ids": [str(persona.id)], "component_ids": [str(river.id)],
                    "scenario": scenario, "scenario_group": "reader", "behavior": "script",
                    "iterations": 1, "seed": 2611, "pair_tutor_seeds": True, "tutor_models": ["gpt-4.1-mini"],
                })
                claimed = harness.claim_chat(db, run["id"])
                assert claimed["child"]["child_profile"] == {**original, "response_length": length}
                learner = db.get(Student, db.get(HarnessChat, claimed["id"]).student_id)
                assert learner.child_profile["response_length"] == length
                seeds.add(claimed["seed"])
            db.refresh(persona)
            assert persona.child_profile == original
            assert len(seeds) == 1


def test_known_boundary_situations_count_wordings_together_and_setup_separately():
    cases = [{"persona_name": "AI_Child12", "scenario": "aside", "simulation_role": "script", "report_turns": [
        {"child_text": "my dog biscuit sleeps on my bed", "block_type_before": "curiosity", "scenario_exercised": True},
        {"child_text": "my drawing has a purple tree in it", "block_type_before": "curiosity", "scenario_exercised": True},
        {"child_text": "earlier setup turn", "block_type_before": "topic_goal", "scenario_exercised": False}
    ]}, {"persona_name": "AI_Child12", "report_turns": [{"child_text": "yes"}]}]
    summary = run_summary(cases)
    assert "ordinary aside (2 turns, Scripted control)" in summary["text"]
    assert {(r["scenario"], r["role"]): r["turns"] for r in summary["opportunities"]} == {
        ("aside", "script"): 2, ("aside (setup)", "script"): 1, ("unspecified", "legacy_unknown"): 1,
    }


def test_loading_fixtures_makes_independent_curiosity_flaw_and_cpi_cases_selectable():
    from sqlalchemy import select
    from app.database import SessionLocal
    from app.models import KcGoal
    from app.harness_scenario_fixture import SCENARIO_FIXTURE_CODE, RATE
    with SessionLocal() as db:
        first = harness.ensure_fixture(db)
        second = harness.ensure_fixture(db)
        assert first["id"] == second["id"]
        course = db.scalar(select(KcGoal).where(KcGoal.code == SCENARIO_FIXTURE_CODE))
        assert course.ready
        targets = {node.code: node for node in harness.load_targets(db, course)}
        for code, kind in [("curiosity", "curiosity"), ("flaw", "spot_the_flaw")]:
            blocks = targets[f"harness-scenario-{code}"].blocks
            assert [b["type"] for b in blocks] == [kind]
        assert targets["harness-scenario-cpi"].blocks[1]["data"]["solo_problem"] == RATE
        assert targets["harness-scenario-choice"].blocks[0]["data"]["question_stem"] == RATE
        assert "stress" in targets["harness-scenario-hamlet"].title.lower()


def test_multiple_tutor_variants_with_the_same_seed_are_compared_once_by_profile_and_model():
    from app.harness_report import compare_runs
    def chat(name, model, profile):
        return {"id": name, "seed": 60, "persona_name": "child", "component_id": "task",
                "tutor_model": model, "seed_profile": profile, "ended_how": "completed"}
    left = [chat("a1", "m1", "p1"), chat("a2", "m1", "p2")]
    right = [chat("b2", "m1", "p2"), chat("b1", "m1", "p1")]
    assert compare_runs(left, right)["matched"] == 2
    assert compare_runs(left, [chat("unknown", "other", "p3")])["matched"] == 0
    assert compare_runs(left[:1], [chat("unpaired", "other", "p3")])["matched"] == 0
    assert compare_runs([{**left[0], "paired_seeds": True}],
                        [{**chat("paired", "other", "p3"), "paired_seeds": True}])["matched"] == 1
