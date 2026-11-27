"""HTTP routes for the AI test child harness. All paths start with /kc/harness."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.harness import (
    add_starter_set,
    answer_key,
    cancel_run,
    claim_chat,
    create_persona,
    create_run,
    delete_run,
    dispatch_harness_turn,
    download_run,
    ensure_fixture,
    epistemic_post_test_context,
    finish_chat,
    get_chat,
    get_run,
    list_chats,
    list_personas,
    list_runs,
    pause_run,
    pending_answer_result,
    prepare_harness_turn,
    record_epistemic_post_test,
    record_run_epistemic_post_test,
    record_turn,
    resume_run,
    run_again,
    run_epistemic_post_test_context,
    trim_prompts,
    update_persona,
)
from app.harness_agent import agent_run_view

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


@router.get("/kc/harness/runs/{run_id}/agent")
def get_agent_run(run_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    """Read-only status for the agent calls. Does not claim a chat or start the loop."""
    return agent_run_view(db, run_id)


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


def _markdown(text: str, filename: str) -> Response:
    return Response(
        content=text,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/kc/harness/runs/{run_id}/download")
def get_run_download(run_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    return _markdown(download_run(db, run_id), f"harness-run-{run_id}.md")


@router.get("/kc/harness/chats")
def get_chats(db: Session = Depends(get_db)) -> list[dict]:
    return list_chats(db)


@router.get("/kc/harness/chats/{chat_id}")
def get_one_chat(chat_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return get_chat(db, chat_id)


@router.get("/kc/harness/chats/{chat_id}/answer-key")
def get_answer_key(chat_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return answer_key(db, chat_id)


@router.get("/kc/harness/chats/{chat_id}/pending-turn/{turn_id}")
def get_pending_answer(chat_id: uuid.UUID, turn_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return pending_answer_result(db, chat_id, turn_id)


@router.post("/kc/harness/chats/{chat_id}/pending-turn")
def post_pending_turn(chat_id: uuid.UUID, body: dict, db: Session = Depends(get_db)) -> dict:
    return prepare_harness_turn(db, chat_id, body)


@router.post("/kc/harness/chats/{chat_id}/pending-turn/{turn_id}/dispatch")
def post_dispatch_turn(chat_id: uuid.UUID, turn_id: uuid.UUID, body: dict, db: Session = Depends(get_db)) -> dict:
    return dispatch_harness_turn(db, chat_id, turn_id, body.get("claim_generation"))


@router.post("/kc/harness/chats/{chat_id}/turns")
def post_turn(chat_id: uuid.UUID, body: dict, db: Session = Depends(get_db)) -> dict:
    return record_turn(db, chat_id, body)


@router.post("/kc/harness/chats/{chat_id}/finish")
def post_finish(chat_id: uuid.UUID, body: dict, db: Session = Depends(get_db)) -> dict:
    return finish_chat(db, chat_id, str(body.get("reason") or "completed"), body.get("claim_generation"))


@router.get("/kc/harness/chats/{chat_id}/epistemic-context")
def get_epistemic_context(
    chat_id: uuid.UUID,
    fallback: bool = False,
    db: Session = Depends(get_db),
) -> dict:
    return epistemic_post_test_context(db, chat_id, use_deterministic_fallback=fallback)


@router.post("/kc/harness/chats/{chat_id}/blind-post-test")
def post_blind_post_test(chat_id: uuid.UUID, body: dict, db: Session = Depends(get_db)) -> dict:
    return record_epistemic_post_test(db, chat_id, body)


@router.get("/kc/harness/runs/{run_id}/epistemic-context")
def get_run_epistemic_context(
    run_id: uuid.UUID,
    course_id: uuid.UUID | None = None,
    persona_id: uuid.UUID | None = None,
    fallback: bool = False,
    db: Session = Depends(get_db),
) -> dict:
    return run_epistemic_post_test_context(
        db,
        run_id,
        course_id=course_id,
        persona_id=persona_id,
        use_deterministic_fallback=fallback,
    )


@router.post("/kc/harness/runs/{run_id}/blind-post-test")
def post_run_blind_post_test(run_id: uuid.UUID, body: dict, db: Session = Depends(get_db)) -> dict:
    return record_run_epistemic_post_test(db, run_id, body)
