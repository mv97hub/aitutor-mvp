"""The one default tutor profile. Every student uses this row."""

from __future__ import annotations

import copy
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.engine.choices import PERSONA_VOICE
from app.models import TutorProfile, default_kc_tutor_config

PROFILE_ID = "default"

OVERARCHING_ENUMS: dict[str, set[str]] = {
    "orient_framing": {"none", "brief_hook", "elaborate_outline"},
    "stay_on_course": {"strict", "brief_answer_then_return", "exploratory"},
    "misconception_policy": {"explain_and_retry_once", "immediate_redirect"},
    "encouragement_style": {"process_praise", "minimal"},
    "close_summary_depth": {
        "concise",
        "restate_in_learner_words",
        "diagnostic_strengths_and_gaps",
    },
}

BLOCK_CONFIG_SPECS: dict[str, dict[str, tuple]] = {
    "topic_goal": {
        "explanation_depth": ("int", 1, 5),
        "max_retries_before_reveal": ("int", 1, 5),
        "hint_ladder_style": (
            "enum",
            {"progressive_nudge_analogy_scaffold", "socratic_questions_only", "direct_scaffold"},
        ),
        "goal_evaluation_strictness": (
            "enum",
            {"conceptual_gist", "precise_vocabulary", "applied_transfer"},
        ),
        "fragment_self_explanation": ("bool",),
        "enrichment_mode": ("enum", {"direct", "on_request", "offer"}),
    },
    "mcq": {
        "max_retry_attempts": ("int", 1, 4),
        "wrong_answer_explanation_depth": ("int", 1, 3),
        "disable_eliminated_choices": ("bool",),
        "confirm_why_on_correct": ("enum", {"never", "on_retry_only", "always"}),
        "correct_pass_explanation_depth": ("enum", {"brief_confirm", "reinforce_why"}),
    },
    "case_study": {
        "case_presentation": (
            "enum",
            {"sequential_predict_then_contrast", "side_by_side_single_turn"},
        ),
        "explanation_depth": ("int", 1, 5),
        "max_retries_before_reveal": ("int", 1, 5),
        "require_transfer_application": ("bool",),
    },
    "socratic": {
        "dialogue_depth_turns": ("int", 1, 4),
        "challenge_intensity": (
            "enum",
            {"gentle_clarification", "counterexample_entrapment", "devil_advocate"},
        ),
        "max_retries_before_reveal": ("int", 1, 5),
        "hint_when_stuck": ("enum", {"highlight_contradiction", "give_analogy"}),
    },
    "curiosity": {
        "max_wonder_turns": ("int", 1, 3),
        "require_initial_prediction": ("bool",),
        "counts_toward_mastery_score": ("bool",),
        "hook_framing_style": (
            "enum",
            {"mystery_paradox", "real_world_surprise", "thought_experiment"},
        ),
    },
    "worked_example": {
        "fading_level": ("enum", {"single_blanked_step", "two_steps"}),
        "require_step_self_explanation": ("bool",),
        "max_retries_before_reveal": ("int", 1, 4),
        "wrong_step_explanation_depth": ("int", 1, 3),
    },
    "spot_the_flaw": {
        "critique_depth": ("enum", {"identify_only", "identify_and_correct"}),
        "wrong_answer_explanation_depth": ("int", 1, 3),
        "max_retries_before_reveal": ("int", 1, 4),
        "show_misconception_why": ("bool",),
    },
    "teach_back": {
        "peer_confusion_level": ("enum", {"curious_beginner", "stubborn_misconception"}),
        "follow_up_questions_count": ("int", 0, 2),
        "max_retries_before_reveal": ("int", 1, 4),
        "evaluation_strictness": (
            "enum",
            {"plain_language_clarity", "all_required_concepts_exact"},
        ),
    },
    "retrieval_check": {
        "cue_scaffolding": ("enum", {"free_recall_first", "cued_hint_on_first_miss"}),
        "require_elaborative_why": ("bool",),
        "max_retries_before_reveal": ("int", 1, 4),
        "accept_paraphrase": ("bool",),
    },
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_kc_tutor_config(
    raw: dict | None,
    *,
    strict: bool = False,
) -> dict:
    """Merge and validate overarching + 9 block-type tutor configurations."""
    base = default_kc_tutor_config()
    if not isinstance(raw, dict):
        return base

    raw_over = raw.get("overarching")
    if isinstance(raw_over, dict):
        for key, allowed in OVERARCHING_ENUMS.items():
            if key in raw_over and raw_over[key] is not None:
                val = str(raw_over[key]).strip()
                if val in allowed:
                    base["overarching"][key] = val
                elif strict:
                    raise ValueError(f"overarching.{key} must be one of {sorted(allowed)}")

    raw_blocks = raw.get("blocks")
    if isinstance(raw_blocks, dict):
        for btype, specs in BLOCK_CONFIG_SPECS.items():
            bcfg = raw_blocks.get(btype)
            if not isinstance(bcfg, dict):
                continue
            for key, spec in specs.items():
                if key not in bcfg or bcfg[key] is None:
                    continue
                kind = spec[0]
                val = bcfg[key]
                if kind == "bool":
                    if isinstance(val, bool):
                        base["blocks"][btype][key] = val
                    elif str(val).lower() in {"true", "yes", "1"}:
                        base["blocks"][btype][key] = True
                    elif str(val).lower() in {"false", "no", "0"}:
                        base["blocks"][btype][key] = False
                    elif strict:
                        raise ValueError(f"blocks.{btype}.{key} must be a boolean")
                elif kind == "int":
                    low, high = spec[1], spec[2]
                    try:
                        ival = int(val)
                    except (TypeError, ValueError) as exc:
                        if strict:
                            raise ValueError(f"blocks.{btype}.{key} must be an integer") from exc
                        continue
                    if low <= ival <= high:
                        base["blocks"][btype][key] = ival
                    elif strict:
                        raise ValueError(f"blocks.{btype}.{key} must be between {low} and {high}")
                    else:
                        base["blocks"][btype][key] = min(high, max(low, ival))
                elif kind == "enum":
                    allowed = spec[1]
                    sval = str(val).strip()
                    if sval in allowed:
                        base["blocks"][btype][key] = sval
                    elif strict:
                        raise ValueError(f"blocks.{btype}.{key} must be one of {sorted(allowed)}")
    return base


def effective_kc_tutor_config(profile: TutorProfile | None) -> dict:
    """Return a normalized kc_tutor_config for this profile."""
    if profile is None:
        return default_kc_tutor_config()
    raw = getattr(profile, "kc_tutor_config", None)
    return normalize_kc_tutor_config(raw if isinstance(raw, dict) else None, strict=False)


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
        stay_on_course=True,
        growth_praise=True,
        misconception_policy="retry_once",
        self_explanation=True,
        enrichment="on_request",
        kc_tutor_config=default_kc_tutor_config(),
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
    row.stay_on_course = source.stay_on_course
    row.growth_praise = source.growth_praise
    row.misconception_policy = source.misconception_policy
    row.self_explanation = source.self_explanation
    row.enrichment = source.enrichment
    row.kc_tutor_config = copy.deepcopy(source.kc_tutor_config or default_kc_tutor_config())
    row.updated_at = _now()
    return row


def ensure_default_profile(db: Session) -> TutorProfile:
    """Insert the default row when it is missing. Never overwrite a saved profile."""
    row = db.get(TutorProfile, PROFILE_ID)
    if row is not None:
        if not row.kc_tutor_config:
            row.kc_tutor_config = default_kc_tutor_config()
            db.flush()
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
    instructive: int = 3,
    persona: str,
    lexicon: str,
    voice_override: bool = False,
    metaphors: str,
    sidekick: str,
    struggle_window: str = "standard",
    anti_spoiler: bool = True,
    one_question: bool = True,
    use_interests: bool = True,
    stay_on_course: bool = True,
    growth_praise: bool = True,
    misconception_policy: str = "retry_once",
    self_explanation: bool = True,
    enrichment: str = "on_request",
    kc_tutor_config: dict | None = None,
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
    row.stay_on_course = stay_on_course
    row.growth_praise = growth_praise
    row.misconception_policy = misconception_policy
    row.self_explanation = self_explanation
    row.enrichment = enrichment
    if kc_tutor_config is not None:
        row.kc_tutor_config = normalize_kc_tutor_config(kc_tutor_config, strict=True)
    elif not row.kc_tutor_config:
        row.kc_tutor_config = default_kc_tutor_config()
    row.updated_at = _now()
    db.flush()
    return row
