"""Ready knowledge-component courses shipped with the studio.

Geometry, macro, and Rome. Inserted when missing. A later seed does not
overwrite them and does not touch catalog courses or kid chats.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.kc import readiness_problems
from app.models import KcGoal, KcNode

COURSES: tuple[dict, ...] = (
    {
        "code": "kc-geometry",
        "title": "Euclidean geometry",
        "description": (
            "Tell congruent triangles apart, find a missing angle, and explain why "
            "two sides and a non-included angle do not prove congruence."
        ),
        "audience": "12-14",
        "kind": "time_boxed",
        "minutes": 30,
        "targets": [
            "geo-angle-sum",
            "geo-missing-angle",
            "geo-congruence",
            "geo-sas-ssa",
            "geo-why-ssa",
            "geo-congruence-plan",
        ],
        "nodes": [
            {
                "code": "geo-angle-sum",
                "title": "Triangle angle sum",
                "kc_type": "factual",
                "core_truth": "The interior angles of a triangle sum to 180 degrees.",
                "rubric": ["States 180 degrees"],
                "type_fields": {
                    "fact": "The interior angles of a triangle add up to 180 degrees.",
                    "retrieval_question": "What do the three interior angles of a triangle add up to?",
                },
            },
            {
                "code": "geo-missing-angle",
                "title": "Find the missing angle",
                "kc_type": "procedural",
                "core_truth": "The missing angle is 180 minus the other two angles.",
                "rubric": ["Subtracts the known angles from 180"],
                "prerequisite_codes": ["geo-angle-sum"],
                "encompasses_codes": ["geo-angle-sum"],
                "type_fields": {
                    "steps": ["Add the two known angles.", "Subtract that sum from 180."],
                    "blanked_step": 1,
                    "solo_problem": "A triangle has angles of 40 degrees and 60 degrees. What is the third angle?",
                    "solo_check": "80 degrees",
                },
            },
            {
                "code": "geo-congruence",
                "title": "What congruence means",
                "kc_type": "conceptual",
                "core_truth": "Congruence means the same size and the same shape.",
                "rubric": ["Says same size and same shape"],
                "type_fields": {
                    "case_a": "Two triangles with the same sides and the same angles, one of them turned.",
                    "case_b": "Two triangles with the same shape and longer sides.",
                    "prediction": "Which pair can be placed exactly on top of each other?",
                    "rule": "Congruent triangles have the same size and the same shape.",
                },
            },
            {
                "code": "geo-included-angle",
                "title": "The included angle",
                "kc_type": "conceptual",
                "core_truth": "The included angle lies between the two sides.",
                "rubric": ["Points to the angle between the two sides"],
                "type_fields": {
                    "case_a": "The angle between side AB and side AC.",
                    "case_b": "The angle at the opposite vertex, not between those two sides.",
                    "prediction": "Which angle is included by sides AB and AC?",
                    "rule": "The included angle is the angle formed between the two given sides.",
                },
            },
            {
                "code": "geo-sas-ssa",
                "title": "SAS versus SSA",
                "kc_type": "conceptual",
                "core_truth": "SAS fixes a triangle and SSA does not.",
                "rubric": [
                    "Names SAS as the proving case",
                    "Says SSA leaves the angle outside the two sides",
                ],
                "prerequisite_codes": ["geo-congruence", "geo-included-angle"],
                "misconceptions": [
                    {"wrong_move": "SSA proves congruence", "broken_kc": "geo-included-angle"}
                ],
                "type_fields": {
                    "case_a": "Two sides with the angle between them fixed.",
                    "case_b": "Two sides with an angle that is not between them.",
                    "prediction": "Which description locks one triangle?",
                    "rule": "SAS proves two triangles congruent. SSA does not, because the angle is not included.",
                },
            },
            {
                "code": "geo-why-ssa",
                "title": "Why SSA fails",
                "kc_type": "causal",
                "core_truth": "SSA fails because the given angle is not included between the two sides.",
                "rubric": ["Says the angle is not between the two sides"],
                "prerequisite_codes": ["geo-sas-ssa"],
                "type_fields": {
                    "decision_point": "You have two sides and an angle that is not between them, and you are about to call the triangles congruent.",
                    "flawed_claim": "The angle can sit anywhere and the triangle is still fixed.",
                    "causal_chain": "The angle is not between the two sides, so the third side can meet them in two places.",
                },
            },
            {
                "code": "geo-congruence-plan",
                "title": "Fix the congruence plan",
                "kc_type": "synthesis",
                "core_truth": "Same size and same shape, together with SAS, show congruence. SSA does not.",
                "rubric": ["Rejects SSA", "Keeps same size and same shape"],
                "prerequisite_codes": ["geo-congruence", "geo-sas-ssa"],
                "type_fields": {
                    "mixes": ["geo-congruence", "geo-sas-ssa"],
                    "faulty_plan": "The triangles look the same and SSA locks them, so they are congruent.",
                },
            },
        ],
    },
    {
        "code": "kc-macro",
        "title": "AP Macroeconomics",
        "description": (
            "Explain scarcity, opportunity cost, a demand shift, a price ceiling, "
            "and how GDP is added up."
        ),
        "audience": "15-17",
        "kind": "mastery",
        "minutes": None,
        "targets": [
            "macro-scarcity",
            "macro-opportunity",
            "macro-supply-demand",
            "macro-ceiling",
            "macro-gdp",
            "macro-policy-mix",
        ],
        "nodes": [
            {
                "code": "macro-scarcity",
                "title": "Scarcity",
                "kc_type": "factual",
                "core_truth": "Scarcity means wants exceed resources.",
                "rubric": ["Says wants exceed resources"],
                "type_fields": {
                    "fact": "Scarcity means wants are greater than the resources that can satisfy them.",
                    "retrieval_question": "What does scarcity mean?",
                },
            },
            {
                "code": "macro-opportunity",
                "title": "Opportunity cost",
                "kc_type": "conceptual",
                "core_truth": "Opportunity cost is the next best alternative given up.",
                "rubric": ["Names the next best alternative"],
                "type_fields": {
                    "case_a": "A city spends its budget on a bridge and cannot build the hospital this year.",
                    "case_b": "A city spends its budget on a bridge and also lists every other project it has ever imagined.",
                    "prediction": "Which cost is the opportunity cost of the bridge?",
                    "rule": "Opportunity cost is the next best alternative given up, not every alternative.",
                },
            },
            {
                "code": "macro-supply-demand",
                "title": "Demand and price",
                "kc_type": "conceptual",
                "core_truth": "Price rises when demand rises and supply does not.",
                "rubric": ["Says demand rose while supply held"],
                "type_fields": {
                    "case_a": "More buyers want the same goods and sellers offer the same amount.",
                    "case_b": "Buyers and sellers both step back by the same amount.",
                    "prediction": "In which case does the price rise?",
                    "rule": "When demand rises and supply holds, the price rises.",
                },
            },
            {
                "code": "macro-quantity",
                "title": "Quantity supplied",
                "kc_type": "conceptual",
                "core_truth": "A lower price does not make sellers offer more.",
                "rubric": ["Says quantity supplied falls when the price falls"],
                "type_fields": {
                    "case_a": "The price falls and sellers offer fewer goods.",
                    "case_b": "The price falls and sellers offer more goods.",
                    "prediction": "Which way does quantity supplied move when the price falls?",
                    "rule": "Quantity supplied falls when the price falls.",
                },
            },
            {
                "code": "macro-ceiling",
                "title": "A binding price ceiling",
                "kc_type": "causal",
                "core_truth": "A binding price ceiling creates a shortage.",
                "rubric": ["Says quantity demanded rises and quantity supplied falls"],
                "prerequisite_codes": ["macro-supply-demand", "macro-quantity"],
                "misconceptions": [
                    {
                        "wrong_move": "a lower price means more goods are sold",
                        "broken_kc": "macro-quantity",
                    }
                ],
                "type_fields": {
                    "decision_point": "Lawmakers set a legal price below the market price.",
                    "flawed_claim": "A lower legal price means more goods are sold.",
                    "causal_chain": "The ceiling raises the amount people want to buy and lowers the amount sellers offer, so a shortage follows.",
                },
            },
            {
                "code": "macro-gdp",
                "title": "Add up GDP",
                "kc_type": "procedural",
                "core_truth": "GDP adds consumption, investment, government spending, and net exports.",
                "rubric": ["Adds consumption, investment, government spending, and net exports"],
                "prerequisite_codes": ["macro-scarcity"],
                "encompasses_codes": ["macro-scarcity"],
                "type_fields": {
                    "steps": [
                        "Add consumption, investment, and government spending.",
                        "Then add net exports.",
                    ],
                    "blanked_step": 1,
                    "solo_problem": "Consumption is 10, investment is 3, government is 4, and net exports are 1. What is GDP?",
                    "solo_check": "18",
                },
            },
            {
                "code": "macro-policy-mix",
                "title": "Fix the policy plan",
                "kc_type": "synthesis",
                "core_truth": "A price cap can empty the shelves, and the opportunity cost is the next best use of those goods.",
                "rubric": ["Rejects the claim that shelves stay full", "Names the next best use"],
                "prerequisite_codes": ["macro-opportunity", "macro-supply-demand"],
                "type_fields": {
                    "mixes": ["macro-opportunity", "macro-supply-demand"],
                    "faulty_plan": "Cap the price and ignore what the city gives up, and the shelves stay full.",
                },
            },
        ],
    },
    {
        "code": "kc-rome",
        "title": "Ancient Rome",
        "description": (
            "Place the Republic before the Empire, tell shared offices from one-man rule, "
            "and explain what crossing the Rubicon with an army did."
        ),
        "audience": "12-14",
        "kind": "curiosity",
        "minutes": None,
        "targets": [
            "rome-republic-fact",
            "rome-shared-rule",
            "rome-senate",
            "rome-rubicon",
            "rome-titles",
        ],
        "nodes": [
            {
                "code": "rome-republic-fact",
                "title": "Republic before Empire",
                "kc_type": "factual",
                "core_truth": "The Republic came before the Empire.",
                "rubric": ["Says the Republic came first"],
                "type_fields": {
                    "fact": "The Roman Republic came before the Roman Empire.",
                    "retrieval_question": "Which came first, the Roman Republic or the Roman Empire?",
                },
            },
            {
                "code": "rome-shared-rule",
                "title": "What a republic is",
                "kc_type": "conceptual",
                "core_truth": "A republic limits offices instead of leaving power in one person for life.",
                "rubric": ["Says power is shared through limited offices"],
                "type_fields": {
                    "case_a": "Consuls serve a short term and the assemblies can refuse them.",
                    "case_b": "One ruler holds power for life and no assembly can refuse him.",
                    "prediction": "Which one is a republic?",
                    "rule": "A republic shares power through limited offices. A monarchy does not.",
                },
            },
            {
                "code": "rome-senate",
                "title": "Senate and assemblies",
                "kc_type": "conceptual",
                "core_truth": "The Senate advised and the assemblies voted.",
                "rubric": ["Says the Senate advised and the assemblies voted"],
                "type_fields": {
                    "case_a": "The Senate debates and advises, and the assemblies vote.",
                    "case_b": "One person announces the law and no vote is taken.",
                    "prediction": "Which one still has a senate that does not rule alone?",
                    "rule": "The Senate advised and the assemblies voted. Neither was a king.",
                },
            },
            {
                "code": "rome-imperium",
                "title": "Where command ended",
                "kc_type": "conceptual",
                "core_truth": "A general's command ended at the Rubicon.",
                "rubric": ["Says the command ended at the boundary"],
                "type_fields": {
                    "case_a": "A general's command covers the province, and it ends when he crosses into Italy.",
                    "case_b": "A general's command follows him into the city because he won a war.",
                    "prediction": "Where does the command end?",
                    "rule": "Imperium over an army ended at the boundary. It did not include marching on the city.",
                },
            },
            {
                "code": "rome-rubicon",
                "title": "Crossing the Rubicon",
                "kc_type": "causal",
                "core_truth": "Crossing the Rubicon with an army started the civil war because his command ended there.",
                "rubric": [
                    "Says his command ended at the river",
                    "Says the crossing started the civil war",
                ],
                "prerequisite_codes": ["rome-shared-rule", "rome-imperium"],
                "misconceptions": [
                    {"wrong_move": "the Senate invited his army", "broken_kc": "rome-imperium"}
                ],
                "type_fields": {
                    "decision_point": "Caesar stands at the Rubicon with his army.",
                    "flawed_claim": "The Senate had invited him to bring the army into Italy.",
                    "causal_chain": "A general's command stopped at the Rubicon, so crossing with an army made him an enemy of the state and started the civil war.",
                },
            },
            {
                "code": "rome-titles",
                "title": "Titles are not a republic",
                "kc_type": "synthesis",
                "core_truth": "Titles and a meeting are not shared power. A republic needs limited offices and a real vote.",
                "rubric": ["Says titles are not enough", "Says a republic needs limited offices and a vote"],
                "prerequisite_codes": ["rome-shared-rule", "rome-senate"],
                "type_fields": {
                    "mixes": ["rome-shared-rule", "rome-senate"],
                    "faulty_plan": "Rome stayed a republic because one man kept the old titles and the Senate still met.",
                },
            },
        ],
    },
)


def _install(db: Session, spec: dict) -> None:
    if db.scalar(select(KcGoal).where(KcGoal.code == spec["code"])) is not None:
        return
    nodes: dict[str, KcNode] = {}
    for item in spec["nodes"]:
        existing = db.scalar(select(KcNode).where(KcNode.code == item["code"]))
        if existing is not None:
            raise RuntimeError(f"{item['code']} already exists without the {spec['code']} course.")
        node = KcNode(
            code=item["code"],
            title=item["title"],
            kc_type=item["kc_type"],
            core_truth=item["core_truth"],
            type_fields=item["type_fields"],
            rubric=list(item["rubric"]),
            misconceptions=list(item.get("misconceptions") or []),
            prerequisite_codes=list(item.get("prerequisite_codes") or []),
            encompasses_codes=list(item.get("encompasses_codes") or []),
        )
        db.add(node)
        nodes[item["code"]] = node
    db.flush()
    from app.kc import _sync_edges

    for node in nodes.values():
        _sync_edges(db, node)
    goal = KcGoal(
        code=spec["code"],
        title=spec["title"],
        description=spec["description"],
        audience=spec["audience"],
        kind=spec["kind"],
        minutes=spec["minutes"],
        target_kc_ids=[str(nodes[code].id) for code in spec["targets"]],
        ready=False,
    )
    db.add(goal)
    db.flush()
    problems = readiness_problems(db, goal)
    if problems:
        raise RuntimeError("; ".join(problems))
    goal.ready = True
    db.flush()


def seed_kc_fixtures(db: Session) -> None:
    for spec in COURSES:
        _install(db, spec)
