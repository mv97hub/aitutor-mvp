"""HTTP routes for the AI test child harness. All paths start with /kc/harness."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.harness import (
    add_starter_set,
    answer_key,
    cancel_run,
    claim_chat,
    compare,
    create_persona,
    create_run,
    create_suite,
    delete_run,
    ensure_fixture,
    findings_for_run,
    finish_chat,
    get_chat,
    get_run,
    list_personas,
    list_recommendations,
    list_runs,
    list_suites,
    pause_run,
    plan_preview,
    record_turn,
    resume_run,
    run_again,
    run_report,
    save_evaluation,
    save_recommendations,
    set_baseline,
    trial_profile,
    trim_prompts,
    update_persona,
    update_recommendation,
)

router = APIRouter()


@router.get("/kc/harness/personas")
def get_personas(include_archived: bool = False, db: Session = Depends(get_db)) -> list[dict]:
    return list_personas(db, include_archived=include_archived)


@router.post("/kc/harness/personas")
def post_persona(body: dict, db: Session = Depends(get_db)) -> dict:
    return create_persona(db, body)


@router.patch("/kc/harness/personas/{persona_id}")
def patch_persona(persona_id: uuid.UUID, body: dict, db: Session = Depends(get_db)) -> dict:
    return update_persona(db, persona_id, body)


@router.post("/kc/harness/personas/starter")
def post_starter(db: Session = Depends(get_db)) -> list[dict]:
    return add_starter_set(db)


@router.post("/kc/harness/plan-preview")
def post_preview(body: dict, db: Session = Depends(get_db)) -> dict:
    return plan_preview(db, body)


@router.post("/kc/harness/fixture")
def post_fixture(db: Session = Depends(get_db)) -> dict:
    return ensure_fixture(db)


@router.get("/kc/harness/runs")
def get_runs(db: Session = Depends(get_db)) -> list[dict]:
    return list_runs(db)


@router.post("/kc/harness/runs")
def post_run(body: dict, db: Session = Depends(get_db)) -> dict:
    return create_run(db, body)


@router.get("/kc/harness/runs/{run_id}")
def get_one_run(run_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return get_run(db, run_id)


@router.post("/kc/harness/runs/{run_id}/pause")
def post_pause(run_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return pause_run(db, run_id)


@router.post("/kc/harness/runs/{run_id}/resume")
def post_resume(run_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return resume_run(db, run_id)


@router.post("/kc/harness/runs/{run_id}/cancel")
def post_cancel(run_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return cancel_run(db, run_id)


@router.delete("/kc/harness/runs/{run_id}")
def remove_run(run_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return delete_run(db, run_id)


@router.post("/kc/harness/runs/{run_id}/again")
def post_again(run_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return run_again(db, run_id)


@router.post("/kc/harness/runs/{run_id}/trim")
def post_trim(run_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return trim_prompts(db, run_id=run_id)


@router.post("/kc/harness/trim")
def post_trim_all(db: Session = Depends(get_db)) -> dict:
    return trim_prompts(db)


@router.post("/kc/harness/runs/{run_id}/claim")
def post_claim(run_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    claimed = claim_chat(db, run_id)
    return {"chat": claimed}


@router.get("/kc/harness/runs/{run_id}/report")
def get_report(run_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return run_report(db, run_id)


@router.get("/kc/harness/runs/{run_id}/findings")
def get_findings(run_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return findings_for_run(db, run_id)


@router.post("/kc/harness/compare")
def post_compare(body: dict, db: Session = Depends(get_db)) -> dict:
    return compare(db, uuid.UUID(str(body.get("left"))), uuid.UUID(str(body.get("right"))))


@router.get("/kc/harness/chats/{chat_id}")
def get_one_chat(chat_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return get_chat(db, chat_id)


@router.get("/kc/harness/chats/{chat_id}/answer-key")
def get_answer_key(chat_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return answer_key(db, chat_id)


@router.post("/kc/harness/chats/{chat_id}/turns")
def post_turn(chat_id: uuid.UUID, body: dict, db: Session = Depends(get_db)) -> dict:
    return record_turn(db, chat_id, body)


@router.post("/kc/harness/chats/{chat_id}/finish")
def post_finish(chat_id: uuid.UUID, body: dict, db: Session = Depends(get_db)) -> dict:
    return finish_chat(db, chat_id, str(body.get("reason") or "completed"))


@router.post("/kc/harness/chats/{chat_id}/evaluations")
def post_evaluation(chat_id: uuid.UUID, body: dict, db: Session = Depends(get_db)) -> dict:
    return save_evaluation(db, chat_id, body)


@router.get("/kc/harness/suites")
def get_suites(db: Session = Depends(get_db)) -> list[dict]:
    return list_suites(db)


@router.post("/kc/harness/suites")
def post_suite(body: dict, db: Session = Depends(get_db)) -> dict:
    return create_suite(db, body)


@router.post("/kc/harness/suites/{suite_id}/baseline")
def post_baseline(suite_id: uuid.UUID, body: dict, db: Session = Depends(get_db)) -> dict:
    return set_baseline(db, suite_id, uuid.UUID(str(body.get("run_id"))))


@router.get("/kc/harness/recommendations")
def get_recommendations(run_id: uuid.UUID | None = None, db: Session = Depends(get_db)) -> list[dict]:
    return list_recommendations(db, run_id=run_id)


@router.post("/kc/harness/recommendations")
def post_recommendations(body: dict, db: Session = Depends(get_db)) -> list[dict]:
    return save_recommendations(db, body)


@router.patch("/kc/harness/recommendations/{card_id}")
def patch_recommendation(card_id: uuid.UUID, body: dict, db: Session = Depends(get_db)) -> dict:
    return update_recommendation(db, card_id, body)


@router.post("/kc/harness/recommendations/{card_id}/trial")
def post_trial(card_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return trial_profile(db, card_id)
