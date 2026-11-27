"""Exercise scenario assignment and the learner/control breakdown without any model calls."""
from types import SimpleNamespace

from app import harness

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


def test_unreached_river_example_records_the_reason_and_closes_the_fixture_session():
    from sqlalchemy import select
    from app.database import SessionLocal
    from app.harness_scenario_fixture import SCENARIO_FIXTURE_CODE
    from app.models import HarnessPersona, KcGoal, KcSession, Student

    with SessionLocal() as db:
        child = next(row for row in harness.add_starter_set(db) if row["number"] == 2)
        persona = db.get(HarnessPersona, child["id"])
        persona.child_profile = {**persona.child_profile, "response_length": "detailed"}
        harness.ensure_fixture(db)
        course = db.scalar(select(KcGoal).where(KcGoal.code == SCENARIO_FIXTURE_CODE))
        river = next(n for n in harness.load_targets(db, course) if n.code == "harness-scenario-river")
        run = harness.create_run(db, {
            "persona_ids": [child["id"]], "course_ids": [str(course.id)], "component_ids": [str(river.id)],
            "scenario": "river-example-practice", "scenario_group": "reader", "behavior": "script",
            "iterations": 1, "turn_limit": 2, "tutor_models": ["gpt-4.1-mini"],
        })
        chat = harness.claim_chat(db, run["id"])
        session = db.get(KcSession, chat["session_id"])
        assert db.get(Student, session.student_id).child_profile["response_length"] == "bite_sized"
        assert persona.child_profile["response_length"] == "detailed"
        detail = harness.finish_chat(db, chat["id"], "scenario_not_reached", chat["claim_generation"])
        assert detail["ended_how"] == "scenario_not_reached"
        assert detail["turns"] == [] and detail["turn_count"] == 0
        assert session.status == "completed"
        assert harness.get_run(db, run["id"])["status"] == "completed"
        assert detail["component_score"] is None and detail["block_outcomes"] == []
