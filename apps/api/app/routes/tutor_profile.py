from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import TutorProfile
from app.schemas import TutorProfileIn, TutorProfileOut
from app.tutor_profile import ensure_default_profile, save_profile

router = APIRouter()


def _out(row: TutorProfile) -> TutorProfileOut:
    return TutorProfileOut(
        instructive=row.instructive,
        persona=row.persona,
        lexicon=row.lexicon,
        voice_override=row.voice_override,
        metaphors=row.metaphors,
        sidekick=row.sidekick,
        struggle_window=row.struggle_window,
        anti_spoiler=row.anti_spoiler,
        one_question=row.one_question,
        use_interests=row.use_interests,
        stay_on_course=row.stay_on_course,
        growth_praise=row.growth_praise,
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
        voice_override=body.voice_override,
        metaphors=body.metaphors,
        sidekick=body.sidekick,
        struggle_window=body.struggle_window,
        anti_spoiler=body.anti_spoiler,
        one_question=body.one_question,
        use_interests=body.use_interests,
        stay_on_course=body.stay_on_course,
        growth_praise=body.growth_praise,
    )
    return _out(row)
