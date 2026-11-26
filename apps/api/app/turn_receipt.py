"""One stored result for one learner turn.

The client reuses its turn id when a response is lost. The same payload
returns the saved result. A different payload on that id conflicts. The
model call happens after the claim request commits, so the database lock
is not held while the model runs.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import KcSession, KcTurnReceipt


def payload_hash(payload: str) -> str:
    return hashlib.sha256((payload or "").encode()).hexdigest()


def claim_answer(
    db: Session,
    session: KcSession,
    *,
    turn_id: str,
    revision: int | None,
    answer: str,
    legacy_payload: Callable[[KcTurnReceipt], str],
) -> dict:
    """Claim this answer, or return the result already stored for this turn id."""
    client_turn_id = _turn_id(turn_id)
    # A domain tag distinguishes new submission hashes from legacy transcript hashes.
    digest = payload_hash("answer-v2\0" + answer)
    _lock(db, session)
    existing = _by_turn(db, session.id, client_turn_id)
    if existing is not None:
        if existing.route != "answer":
            raise HTTPException(status_code=409, detail="That turn id belongs to another request.")
        if existing.payload_hash != digest and (
            existing.payload_hash != payload_hash(existing.payload)
            or legacy_payload(existing) != existing.payload
        ):
            raise HTTPException(status_code=409, detail="That turn was already sent with a different answer.")
        if existing.status == "committed" and isinstance(existing.result, dict):
            return {"replayed": True, "result": existing.result}
        _check_revision(session, existing.revision)
        return {"replayed": False, "created": False, "receipt": existing}
    if session.status == "completed":
        raise HTTPException(status_code=422, detail="This component session is already finished.")
    _check_revision(session, revision)
    receipt = KcTurnReceipt(
        session_id=session.id,
        client_turn_id=client_turn_id,
        route="answer",
        revision=int(session.revision or 0),
        payload_hash=digest,
        payload=answer,
        status="claimed",
    )
    _insert(db, receipt)
    return {"replayed": False, "created": True, "receipt": receipt}


def prepare_answer_commit(db: Session, session: KcSession, turn_id: str) -> dict:
    """Look up the claim before the score is written.

    A committed turn returns its saved result even when the client still
    holds an older revision. The lookup happens before that comparison.
    """
    client_turn_id = _turn_id(turn_id)
    _lock(db, session)
    existing = _by_turn(db, session.id, client_turn_id)
    if existing is None or existing.route != "answer":
        raise HTTPException(status_code=409, detail="Claim this turn before scoring it.")
    if existing.status == "committed" and isinstance(existing.result, dict):
        return {"replay": existing.result, "pending": None, "receipt": existing}
    _check_revision(session, existing.revision)
    return {"replay": None, "pending": str(existing.payload or ""), "receipt": existing}


def claim_speech(
    db: Session,
    session: KcSession,
    *,
    turn_id: str,
    revision: int | None,
) -> dict:
    """Mint the opening key before any generated key is written.

    A second tab at this revision does not mint another key. A retry of the
    same turn id receives the key already claimed.
    """
    client_turn_id = _turn_id(turn_id)
    _lock(db, session)
    existing = _by_turn(db, session.id, client_turn_id)
    if existing is not None:
        if existing.route != "speech":
            raise HTTPException(status_code=409, detail="That turn id belongs to another request.")
        if existing.status == "committed" and isinstance(existing.result, dict):
            return {
                "replayed": True,
                "held": False,
                "opening_key": existing.opening_key,
                "session": existing.result,
            }
        return {
            "replayed": False,
            "held": False,
            "opening_key": existing.opening_key,
            "session": None,
        }
    owner = _speech_at_revision(db, session.id, int(session.revision or 0))
    if owner is not None:
        saved = owner.result if owner.status == "committed" and isinstance(owner.result, dict) else None
        return {
            "replayed": saved is not None,
            "held": saved is None,
            "opening_key": owner.opening_key,
            "session": saved,
        }
    _check_revision(session, revision)
    receipt = KcTurnReceipt(
        session_id=session.id,
        client_turn_id=client_turn_id,
        route="speech",
        revision=int(session.revision or 0),
        payload_hash=payload_hash(client_turn_id),
        payload="",
        status="claimed",
        opening_key=str(uuid.uuid4()),
    )
    try:
        _insert(db, receipt)
    except HTTPException:
        owner = _speech_at_revision(db, session.id, int(session.revision or 0))
        if owner is None:
            raise
        saved = owner.result if owner.status == "committed" and isinstance(owner.result, dict) else None
        return {
            "replayed": saved is not None,
            "held": saved is None,
            "opening_key": owner.opening_key,
            "session": saved,
        }
    return {
        "replayed": False,
        "held": False,
        "opening_key": receipt.opening_key,
        "session": None,
        "receipt": receipt,
    }


def speech_commit_owner(db: Session, session: KcSession, turn_id: str) -> dict:
    """The receipt that is allowed to write the opening. A late worker is not."""
    client_turn_id = _turn_id(turn_id)
    _lock(db, session)
    existing = _by_turn(db, session.id, client_turn_id)
    if existing is not None and existing.route == "speech":
        if existing.status == "committed" and isinstance(existing.result, dict):
            return {"write": False, "result": existing.result, "receipt": existing}
        owner = _speech_at_revision(db, session.id, int(existing.revision or 0))
        if owner is not None and owner.id != existing.id and owner.status == "committed":
            return {"write": False, "result": owner.result, "receipt": existing}
        return {"write": True, "result": None, "receipt": existing}
    client_revision = int(existing.revision or 0) if existing is not None else None
    if client_revision is None:
        # This turn never claimed. If someone else already owns the revision, return them.
        # The late worker does not write a second key.
        for revision in {int(session.revision or 0), int(session.revision or 0) - 1}:
            if revision < 0:
                continue
            owner = _speech_at_revision(db, session.id, revision)
            if owner is not None and owner.status == "committed" and isinstance(owner.result, dict):
                return {"write": False, "result": owner.result, "receipt": None}
            if owner is not None and owner.status == "claimed":
                return {"write": False, "result": None, "receipt": None, "held": True, "opening_key": owner.opening_key}
    raise HTTPException(status_code=409, detail="Claim this opening before saving it.")


def seal_receipt(db: Session, session: KcSession, receipt: KcTurnReceipt | None, result: dict) -> dict:
    """Store the response after the learner line, the evidence, and the reply are written."""
    if receipt is None:
        return result
    if receipt.status == "committed" and isinstance(receipt.result, dict):
        return receipt.result
    session.revision = int(session.revision or 0) + 1
    stored = dict(result)
    stored["revision"] = int(session.revision or 0)
    receipt.status = "committed"
    receipt.result = stored
    db.flush()
    return stored


def _turn_id(turn_id: str) -> str:
    cleaned = str(turn_id or "").strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail="A turn id is required.")
    return cleaned[:80]


def _check_revision(session: KcSession, revision: int | None) -> None:
    if revision is None or int(revision) != int(session.revision or 0):
        raise HTTPException(status_code=409, detail="The session changed. Refresh and try again.")


def _lock(db: Session, session: KcSession) -> None:
    db.execute(select(KcSession).where(KcSession.id == session.id).with_for_update())
    db.refresh(session)


def _by_turn(db: Session, session_id: uuid.UUID, turn_id: str) -> KcTurnReceipt | None:
    return db.scalar(
        select(KcTurnReceipt).where(
            KcTurnReceipt.session_id == session_id,
            KcTurnReceipt.client_turn_id == turn_id,
        )
    )


def _speech_at_revision(db: Session, session_id: uuid.UUID, revision: int) -> KcTurnReceipt | None:
    return db.scalar(
        select(KcTurnReceipt).where(
            KcTurnReceipt.session_id == session_id,
            KcTurnReceipt.route == "speech",
            KcTurnReceipt.revision == revision,
        )
    )


def _insert(db: Session, receipt: KcTurnReceipt) -> None:
    db.add(receipt)
    try:
        with db.begin_nested():
            db.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="That turn is already in progress.") from exc
