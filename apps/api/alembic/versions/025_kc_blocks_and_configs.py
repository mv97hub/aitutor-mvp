"""Ordered block architecture on kc_nodes, allowed block scope on kc_goals,
block state on kc_sessions, and kc_tutor_config on tutor_profiles.

Revision ID: 025_kc_blocks_and_configs
Revises: 025_kc_topic_pairs
Create Date: 2026-11-08
"""

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "025_kc_blocks_and_configs"
down_revision: Union[str, None] = "025_kc_topic_pairs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ALL_BLOCK_TYPES = [
    "topic_goal",
    "mcq",
    "case_study",
    "socratic",
    "curiosity",
    "worked_example",
    "spot_the_flaw",
    "teach_back",
    "retrieval_check",
]


def _migrate_node_blocks(row: dict) -> tuple[list[dict], list[str]]:
    blocks: list[dict] = []
    title = str(row.get("title") or "Concept").strip()
    core_truth = str(row.get("core_truth") or "").strip()
    kc_type = str(row.get("kc_type") or "").strip()
    raw_topics = row.get("topics")
    raw_fields = row.get("type_fields")
    fields = raw_fields if isinstance(raw_fields, dict) else {}

    pair_sources: list[dict] = []
    if isinstance(raw_topics, list):
        pair_sources.extend(item for item in raw_topics if isinstance(item, dict))
    if isinstance(fields.get("pairs"), list):
        pair_sources.extend(item for item in fields["pairs"] if isinstance(item, dict))

    seen_pairs: set[tuple[str, str]] = set()
    for item in pair_sources:
        topic = str(item.get("topic") or "").strip()
        goal = str(item.get("goal") or "").strip()
        if topic and goal and (topic.lower(), goal.lower()) not in seen_pairs:
            seen_pairs.add((topic.lower(), goal.lower()))
            blocks.append(
                {
                    "id": f"blk_{len(blocks) + 1}",
                    "type": "topic_goal",
                    "data": {
                        "topic": topic,
                        "goal": goal,
                        "acceptance_criteria": "",
                        "teaching_notes": "",
                    },
                }
            )

    if kc_type == "factual":
        fact = str(fields.get("fact") or core_truth).strip()
        question = str(fields.get("retrieval_question") or "").strip()
        if fact or question:
            blocks.append(
                {
                    "id": f"blk_{len(blocks) + 1}",
                    "type": "retrieval_check",
                    "data": {
                        "recall_prompt": question or f"What is the key fact about {title}?",
                        "expected_fact": fact or title,
                        "elaborative_why_prompt": f"Why does this fact hold for {title}?",
                        "expected_why_rationale": core_truth or fact or title,
                    },
                }
            )
    elif kc_type == "procedural":
        raw_steps = fields.get("steps")
        step_list = (
            [str(s).strip() for s in raw_steps if str(s).strip()]
            if isinstance(raw_steps, list)
            else []
        )
        if len(step_list) == 1:
            step_list.append(f"Verify the result for {title}.")
        blanked = fields.get("blanked_step")
        try:
            faded_idx = int(blanked) if blanked is not None else max(0, len(step_list) - 1)
        except (TypeError, ValueError):
            faded_idx = max(0, len(step_list) - 1)
        if step_list:
            faded_idx = min(max(0, faded_idx), len(step_list) - 1)
        solo_problem = str(fields.get("solo_problem") or "").strip()
        solo_check = str(fields.get("solo_check") or core_truth).strip()
        if step_list or solo_problem:
            if len(step_list) < 2:
                step_list = [f"Set up {title}.", f"Complete {title}."]
                faded_idx = 1
            blocks.append(
                {
                    "id": f"blk_{len(blocks) + 1}",
                    "type": "worked_example",
                    "data": {
                        "problem_statement": f"Worked example for {title}",
                        "steps": [{"step_text": s, "rationale": ""} for s in step_list],
                        "faded_step_index": faded_idx,
                        "solo_problem": solo_problem or f"Solve a parallel problem for {title}.",
                        "solo_expected_answer": solo_check or core_truth or title,
                    },
                }
            )
    elif kc_type == "conceptual":
        case_a = str(fields.get("case_a") or "").strip()
        case_b = str(fields.get("case_b") or "").strip()
        prediction = str(fields.get("prediction") or "").strip()
        rule = str(fields.get("rule") or core_truth).strip()
        transfer = str(fields.get("transfer_case") or "").strip()
        if case_a or case_b or prediction or rule:
            blocks.append(
                {
                    "id": f"blk_{len(blocks) + 1}",
                    "type": "case_study",
                    "data": {
                        "case_a": case_a or f"Case A for {title}",
                        "case_b": case_b or f"Case B for {title}",
                        "prediction_prompt": prediction or f"How do Case A and Case B compare on {title}?",
                        "invariant_principle": rule or core_truth or title,
                        "transfer_prompt": transfer,
                        "transfer_expected": (rule or core_truth or title) if transfer else "",
                    },
                }
            )
    elif kc_type == "causal":
        decision = str(fields.get("decision_point") or "").strip()
        flawed = str(fields.get("flawed_claim") or "").strip()
        chain = str(fields.get("causal_chain") or core_truth).strip()
        counter = str(fields.get("counterfactual") or "").strip()
        if flawed:
            blocks.append(
                {
                    "id": f"blk_{len(blocks) + 1}",
                    "type": "spot_the_flaw",
                    "data": {
                        "rookie_work": flawed,
                        "flaw_description": decision or flawed,
                        "underlying_misconception": flawed,
                        "corrected_version": chain or core_truth or title,
                    },
                }
            )
        if decision or counter or (chain and not flawed):
            blocks.append(
                {
                    "id": f"blk_{len(blocks) + 1}",
                    "type": "socratic",
                    "data": {
                        "central_dilemma": decision or f"Why does {title} unfold this way?",
                        "initial_probe": f"What is at stake in {decision or title}?",
                        "counterexamples": [counter or flawed or f"What if the key condition in {title} changed?"],
                        "target_synthesis": chain or core_truth or title,
                    },
                }
            )
    elif kc_type == "synthesis":
        faulty = str(fields.get("faulty_plan") or "").strip()
        raw_mixes = fields.get("mixes")
        mixes = (
            [str(m).strip() for m in raw_mixes if str(m).strip()]
            if isinstance(raw_mixes, list)
            else []
        )
        if faulty or mixes or core_truth:
            mix_note = f"Misapplies {', '.join(mixes)}" if mixes else (faulty or f"Flawed plan for {title}")
            blocks.append(
                {
                    "id": f"blk_{len(blocks) + 1}",
                    "type": "spot_the_flaw",
                    "data": {
                        "rookie_work": faulty or f"A rookie mixes earlier ideas on {title}.",
                        "flaw_description": mix_note,
                        "underlying_misconception": faulty or mix_note,
                        "corrected_version": core_truth or title,
                    },
                }
            )

    rubric: list[str] = []
    for blk in blocks:
        btype = blk.get("type")
        data = blk.get("data") or {}
        criterion = ""
        if btype == "topic_goal":
            criterion = str(data.get("goal") or "").strip()
        elif btype == "mcq":
            criterion = str(data.get("target_skill") or data.get("question_stem") or "").strip()
        elif btype == "case_study":
            criterion = str(data.get("invariant_principle") or "").strip()
        elif btype == "socratic":
            criterion = str(data.get("target_synthesis") or "").strip()
        elif btype == "curiosity":
            criterion = str(data.get("bridge_to_unit") or "").strip()
        elif btype == "worked_example":
            criterion = str(data.get("solo_expected_answer") or "").strip()
        elif btype == "spot_the_flaw":
            criterion = str(data.get("corrected_version") or "").strip()
        elif btype == "teach_back":
            reqs = data.get("required_concepts") or []
            criterion = "; ".join(str(r).strip() for r in reqs if str(r).strip())
        elif btype == "retrieval_check":
            criterion = str(data.get("expected_fact") or "").strip()
        if criterion and criterion not in rubric:
            rubric.append(criterion)

    return blocks, rubric


def upgrade() -> None:
    from app.models import default_kc_tutor_config

    op.add_column(
        "kc_nodes",
        sa.Column("blocks", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "kc_goals",
        sa.Column(
            "allowed_block_types",
            sa.JSON(),
            nullable=False,
            server_default=sa.text(f"'{json.dumps(ALL_BLOCK_TYPES)}'"),
        ),
    )
    op.add_column(
        "kc_sessions",
        sa.Column("active_block_id", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "kc_sessions",
        sa.Column(
            "active_block_state",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column(
        "kc_sessions",
        sa.Column(
            "block_results",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.add_column(
        "tutor_profiles",
        sa.Column(
            "kc_tutor_config",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )

    bind = op.get_bind()
    rows = list(
        bind.execute(
            sa.text(
                "SELECT id, title, core_truth, topics, kc_type, type_fields, rubric FROM kc_nodes"
            )
        ).mappings()
    )
    for row in rows:
        blocks, derived_rubric = _migrate_node_blocks(dict(row))
        existing_rubric = row["rubric"] if isinstance(row["rubric"], list) else []
        final_rubric = derived_rubric or [str(r).strip() for r in existing_rubric if str(r).strip()]
        bind.execute(
            sa.text(
                "UPDATE kc_nodes SET blocks = CAST(:blocks AS JSON), "
                "rubric = CAST(:rubric AS JSON) WHERE id = :id"
            ),
            {
                "blocks": json.dumps(blocks),
                "rubric": json.dumps(final_rubric),
                "id": row["id"],
            },
        )

    bind.execute(
        sa.text("UPDATE kc_goals SET allowed_block_types = CAST(:allowed AS JSON)"),
        {"allowed": json.dumps(ALL_BLOCK_TYPES)},
    )
    bind.execute(
        sa.text("UPDATE kc_sessions SET recipe = 'block_walk'"),
    )
    bind.execute(
        sa.text("UPDATE tutor_profiles SET kc_tutor_config = CAST(:cfg AS JSON)"),
        {"cfg": json.dumps(default_kc_tutor_config())},
    )

    op.drop_constraint("ck_kc_nodes_type", "kc_nodes", type_="check")
    op.drop_column("kc_nodes", "type_fields")
    op.drop_column("kc_nodes", "kc_type")


def downgrade() -> None:
    op.add_column(
        "kc_nodes",
        sa.Column("kc_type", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "kc_nodes",
        sa.Column(
            "type_fields",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.create_check_constraint(
        "ck_kc_nodes_type",
        "kc_nodes",
        "kc_type IS NULL OR kc_type IN ('factual', 'procedural', 'conceptual', 'causal', 'synthesis')",
    )
    op.drop_column("tutor_profiles", "kc_tutor_config")
    op.drop_column("kc_sessions", "block_results")
    op.drop_column("kc_sessions", "active_block_state")
    op.drop_column("kc_sessions", "active_block_id")
    op.drop_column("kc_goals", "allowed_block_types")
    op.drop_column("kc_nodes", "blocks")
