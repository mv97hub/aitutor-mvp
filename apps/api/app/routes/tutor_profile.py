from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DEFAULT_TUTOR_DESCRIPTION, TutorProfile
from app.schemas import TutorProfileCreateIn, TutorProfileIn, TutorProfileOut
from app.tutor_profile import (
    PROFILE_ID,
     _UNSET,
    create_tutor_profile,
    delete_tutor_profile,
    effective_kc_tutor_config,
    effective_voice_settings,
    ensure_default_profile,
    get_profile_by_id_or_slug,
    list_profiles,
    normalize_avatar_preset,
    reset_tutor_profile,
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
    is_def = bool(getattr(row, "is_default", False) or row.id == PROFILE_ID)
    return TutorProfileOut(
        id=str(row.id or PROFILE_ID),
        name=str(getattr(row, "name", None) or "Default"),
        slug=str(getattr(row, "slug", None) or row.id or "default"),
        description=str(
            row.description
            if getattr(row, "description", None) is not None
            else DEFAULT_TUTOR_DESCRIPTION
        ),
        avatar_preset=normalize_avatar_preset(
            getattr(row, "avatar_preset", "default_circle"),
            strict=False,
        ),
        avatar_url=getattr(row, "avatar_url", None),
        is_default=is_def,
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


def _save_from_body(
    db: Session,
    body: TutorProfileIn,
    *,
    profile_id: str | None = None,
) -> TutorProfile:
    provided = set(body.model_fields_set)
    try:
        return save_profile(
            db,
            profile_id=profile_id,
            name=body.name if "name" in provided else None,
            description=body.description if "description" in provided else None,
            avatar_preset=body.avatar_preset if "avatar_preset" in provided else None,
            avatar_url=body.avatar_url if "avatar_url" in provided else _UNSET,
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
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/tutor-profiles", response_model=list[TutorProfileOut])
def get_tutor_profiles(db: Session = Depends(get_db)) -> list[TutorProfileOut]:
    return [_out(row) for row in list_profiles(db)]


@router.post("/tutor-profiles", response_model=TutorProfileOut)
def post_tutor_profile(
    body: TutorProfileCreateIn,
    db: Session = Depends(get_db),
) -> TutorProfileOut:
    provided = set(body.model_fields_set)
    overrides: dict[str, object] = {}
    for key in (
        "instructive",
        "persona",
        "lexicon",
        "vocabulary_register",
        "interest_weaving",
        "humor_and_wit",
        "voice_override",
        "metaphors",
        "sidekick",
        "struggle_window",
        "anti_spoiler",
        "one_question",
        "use_interests",
        "stay_on_course",
        "growth_praise",
        "misconception_policy",
        "self_explanation",
        "enrichment",
        "kc_tutor_config",
    ):
        if key in provided:
            overrides[key] = getattr(body, key)
    try:
        row = create_tutor_profile(
            db,
            name=body.name,
            description=body.description if "description" in provided else None,
            avatar_preset=body.avatar_preset if "avatar_preset" in provided else None,
            avatar_url=body.avatar_url if "avatar_url" in provided else None,
            source_profile_id=body.source_profile_id,
            overrides=overrides,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _out(row)


@router.get("/tutor-profiles/{profile_id}", response_model=TutorProfileOut)
def get_single_tutor_profile(
    profile_id: str,
    db: Session = Depends(get_db),
) -> TutorProfileOut:
    ensure_default_profile(db)
    row = get_profile_by_id_or_slug(db, profile_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Tutor profile not found")
    return _out(row)


@router.put("/tutor-profiles/{profile_id}", response_model=TutorProfileOut)
def put_single_tutor_profile(
    profile_id: str,
    body: TutorProfileIn,
    db: Session = Depends(get_db),
) -> TutorProfileOut:
    ensure_default_profile(db)
    row = _save_from_body(db, body, profile_id=profile_id)
    return _out(row)


@router.post("/tutor-profiles/{profile_id}/reset", response_model=TutorProfileOut)
def post_reset_single_tutor_profile(
    profile_id: str,
    db: Session = Depends(get_db),
) -> TutorProfileOut:
    try:
        row = reset_tutor_profile(db, profile_id=profile_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _out(row)


@router.delete("/tutor-profiles/{profile_id}")
def remove_tutor_profile(
    profile_id: str,
    db: Session = Depends(get_db),
) -> dict:
    try:
        delete_tutor_profile(db, profile_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"deleted": True, "id": profile_id}


@router.get("/tutor-profile", response_model=TutorProfileOut)
def get_tutor_profile(
    profile_id: str | None = None,
    db: Session = Depends(get_db),
) -> TutorProfileOut:
    ensure_default_profile(db)
    if profile_id is not None and str(profile_id).strip():
        row = get_profile_by_id_or_slug(db, profile_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Tutor profile not found")
        return _out(row)
    return _out(ensure_default_profile(db))


@router.put("/tutor-profile", response_model=TutorProfileOut)
def put_tutor_profile(
    body: TutorProfileIn,
    profile_id: str | None = None,
    db: Session = Depends(get_db),
) -> TutorProfileOut:
    row = _save_from_body(db, body, profile_id=profile_id)
    return _out(row)


@router.post("/tutor-profile/reset", response_model=TutorProfileOut)
def post_reset_tutor_profile(
    profile_id: str | None = None,
    db: Session = Depends(get_db),
) -> TutorProfileOut:
    try:
        row = reset_tutor_profile(db, profile_id=profile_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _out(row)
