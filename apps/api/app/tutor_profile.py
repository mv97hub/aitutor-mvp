"""The one default tutor profile. Every student uses this row."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.engine.choices import PERSONA_VOICE
from app.models import TutorProfile

PROFILE_ID = "default"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def default_row() -> TutorProfile:
    return TutorProfile(
        id=PROFILE_ID,
        instructive=3,
        persona="curious-co-explorer",
        lexicon="middle-grade-vivid",
        voice_override=False,
        metaphors="playground-sports",
        sidekick="bumbling-partner",
        struggle_window="standard",
        anti_spoiler=True,
        one_question=True,
        use_interests=True,
        growth_praise=True,
        updated_at=_now(),
    )


def _fill(row: TutorProfile, source: TutorProfile) -> TutorProfile:
    row.instructive = source.instructive
    row.persona = source.persona
    row.lexicon = source.lexicon
    row.voice_override = source.voice_override
    row.metaphors = source.metaphors
    row.sidekick = source.sidekick
    row.struggle_window = source.struggle_window
    row.anti_spoiler = source.anti_spoiler
    row.one_question = source.one_question
    row.use_interests = source.use_interests
    row.growth_praise = source.growth_praise
    row.updated_at = _now()
    return row


def ensure_default_profile(db: Session) -> TutorProfile:
    """Insert the default row when it is missing. Never overwrite a saved profile."""
    row = db.get(TutorProfile, PROFILE_ID)
    if row is not None:
        return row
    row = default_row()
    db.add(row)
    db.flush()
    return row


def reset_default_profile(db: Session) -> TutorProfile:
    """Put the singleton back to the built-in default. Tests use this."""
    row = db.get(TutorProfile, PROFILE_ID)
    if row is None:
        row = default_row()
        db.add(row)
    else:
        _fill(row, default_row())
    db.flush()
    return row


def load_profile(db: Session | None) -> TutorProfile:
    """The row the prompt assembler and the struggle window read.

    A missing row uses the same defaults as a fresh database. Callers that
    can write should use ensure_default_profile instead.
    """
    if db is None:
        return default_row()
    row = db.get(TutorProfile, PROFILE_ID)
    if row is None:
        return default_row()
    return row


def save_profile(
    db: Session,
    *,
    instructive: int,
    persona: str,
    lexicon: str,
    voice_override: bool,
    metaphors: str,
    sidekick: str,
    struggle_window: str,
    anti_spoiler: bool,
    one_question: bool,
    use_interests: bool,
    growth_praise: bool,
) -> TutorProfile:
    row = ensure_default_profile(db)
    if voice_override and lexicon != PERSONA_VOICE[persona]:
        stored_lexicon = lexicon
        stored_override = True
    else:
        stored_lexicon = PERSONA_VOICE[persona]
        stored_override = False
    row.instructive = instructive
    row.persona = persona
    row.lexicon = stored_lexicon
    row.voice_override = stored_override
    row.metaphors = metaphors
    row.sidekick = sidekick
    row.struggle_window = struggle_window
    row.anti_spoiler = anti_spoiler
    row.one_question = one_question
    row.use_interests = use_interests
    row.growth_praise = growth_praise
    row.updated_at = _now()
    db.flush()
    return row
