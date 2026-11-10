from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import TutorProfile
from app.schemas import TutorProfileIn, TutorProfileOut
from app.tutor_profile import (
    effective_kc_tutor_config,
    effective_voice_settings,
    ensure_default_profile,
    save_profile,
)

router = APIRouter()


def _out(row: TutorProfile) -> TutorProfileOut:
    voice = effective_voice_settings(row)
    cfg = effective_kc_tutor_config(row)
    cfg["voice"] = {
        "persona": str(voice["persona"]),
        "vocabulary_register": str(voice["vocabulary_register"]),
        "interest_weaving": str(voice["interest_weaving"]),
        "metaphors": str(voice["metaphors"]),
        "humor_and_wit": str(voice["humor_and_wit"]),
        "sidekick": str(voice["sidekick"]),
    }
    return TutorProfileOut(
        instructive=row.instructive,
        persona=row.persona,
        lexicon=row.lexicon,
        vocabulary_register=str(voice["vocabulary_register"]),
        interest_weaving=str(voice["interest_weaving"]),
        humor_and_wit=str(voice["humor_and_wit"]),
        voice_override=row.voice_override,
        metaphors=row.metaphors,
        sidekick=row.sidekick,
        struggle_window=row.struggle_window,
        anti_spoiler=row.anti_spoiler,
        one_question=row.one_question,
        use_interests=row.use_interests,
        stay_on_course=row.stay_on_course,
        growth_praise=row.growth_praise,
        misconception_policy=row.misconception_policy,
        self_explanation=row.self_explanation,
        enrichment=row.enrichment,
        kc_tutor_config=cfg,
        updated_at=row.updated_at,
    )


@router.get("/tutor-profile", response_model=TutorProfileOut)
def get_tutor_profile(db: Session = Depends(get_db)) -> TutorProfileOut:
    return _out(ensure_default_profile(db))


@router.put("/tutor-profile", response_model=TutorProfileOut)
def put_tutor_profile(body: TutorProfileIn, db: Session = Depends(get_db)) -> TutorProfileOut:
    row = save_profile(
        db,
        instructive=body.instructive,
        persona=body.persona,
        lexicon=body.lexicon,
        vocabulary_register=body.vocabulary_register,
        interest_weaving=body.interest_weaving,
        humor_and_wit=body.humor_and_wit,
        voice_override=body.voice_override,
        metaphors=body.metaphors,
        sidekick=body.sidekick,
        struggle_window=body.struggle_window,
        anti_spoiler=body.anti_spoiler,
        one_question=body.one_question,
        use_interests=body.use_interests,
        stay_on_course=body.stay_on_course,
        growth_praise=body.growth_praise,
        misconception_policy=body.misconception_policy,
        self_explanation=body.self_explanation,
        enrichment=body.enrichment,
        kc_tutor_config=body.kc_tutor_config,
    )
    return _out(row)
