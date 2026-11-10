"""The one default tutor profile. Every student uses this row."""

from __future__ import annotations

import copy
import re
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.engine.choices import (
    HUMOR_MODES,
    INTEREST_WEAVING_MODES,
    METAPHORS,
    PERSONAS,
    PERSONA_VOICE,
    SIDEKICKS,
    VOCABULARY_REGISTERS,
    ids,
)
from app.models import (
    DEFAULT_TUTOR_DESCRIPTION,
    KcSession,
    Student,
    TutorProfile,
    default_kc_tutor_config,
)

PROFILE_ID = "default"

AVATAR_PRESET_CATEGORIES: dict[str, tuple[str, ...]] = {
    "classic_mentor": (
        "default_circle",
        "mentor_cap",
        "open_book",
        "scroll_quill",
        "lightbulb",
        "lantern",
        "glasses_scholar",
        "chalkboard",
    ),
    "animals_companions": (
        "owl",
        "fox",
        "badger",
        "dolphin",
        "turtle",
        "lion",
        "penguin",
        "octopus",
    ),
    "mythic_fantasy": (
        "dragon",
        "wizard_hat",
        "phoenix",
        "unicorn",
        "griffin",
        "crystal_orb",
        "magic_wand",
        "castle_tower",
    ),
    "scifi_space_tech": (
        "robot",
        "rocket",
        "astronaut",
        "planet_ring",
        "satellite",
        "ufo_saucer",
        "circuit_chip",
        "telescope",
    ),
    "science_discovery": (
        "atom",
        "microscope",
        "beaker",
        "dna_helix",
        "magnet",
        "prism_light",
        "gears",
        "globe",
    ),
    "exploration_nature": (
        "compass",
        "mountain",
        "magnifying_glass",
        "treasure_map",
        "campfire",
        "oak_tree",
        "sunburst",
        "ocean_wave",
    ),
    "arts_music_creativity": (
        "palette",
        "music_note",
        "headphones",
        "theater_masks",
        "camera",
        "origami_bird",
        "paintbrush",
        "sparkles",
    ),
    "sports_games_strategy": (
        "chess_knight",
        "trophy",
        "puzzle_piece",
        "soccer_ball",
        "basketball",
        "gamepad",
        "target_bullseye",
        "stopwatch",
    ),
}

AVATAR_PRESETS: tuple[str, ...] = tuple(
    preset
    for group in AVATAR_PRESET_CATEGORIES.values()
    for preset in group
)
AVATAR_PRESET_SET: frozenset[str] = frozenset(AVATAR_PRESETS)


def normalize_avatar_preset(raw: object, *, strict: bool = False) -> str:
    val = str(raw or "").strip()
    if not val:
        return "default_circle"
    if val in AVATAR_PRESET_SET:
        return val
    if strict:
        raise ValueError(f"avatar_preset must be one of the 64 built-in presets (got {val!r})")
    return "default_circle"

LAYER_3_ENUMS: dict[str, set[str]] = {
    "persona": ids(PERSONAS),
    "vocabulary_register": ids(VOCABULARY_REGISTERS),
    "interest_weaving": ids(INTEREST_WEAVING_MODES),
    "metaphors": ids(METAPHORS),
    "humor_and_wit": ids(HUMOR_MODES),
    "sidekick": ids(SIDEKICKS),
}

DEFAULT_KC_OVERARCHING_CONFIG: dict[str, str] = {
    "orient_framing": "elaborate_outline",
    "instructional_stance": "guided_discovery",
    "scaffolding_escalation": "progressive_nudge_then_scaffold",
    "stay_on_course": "brief_answer_then_return",
    "misconception_policy": "explain_and_retry_once",
    "prerequisite_support_policy": "inline_micro_recap",
    "encouragement_style": "process_praise",
    "close_summary_depth": "diagnostic_strengths_and_gaps",
}

DEFAULT_PROFILE: dict[str, object] = {
    "id": PROFILE_ID,
    "name": "Default",
    "slug": "default",
    "description": DEFAULT_TUTOR_DESCRIPTION,
    "avatar_preset": "default_circle",
    "avatar_url": None,
    "is_default": True,
    "persona": "coach",
    "vocabulary_register": "adaptive_to_child",
    "interest_weaving": "subtle_natural",
    "metaphors": "everyday",
    "humor_and_wit": "light_warm",
    "sidekick": "none",
    "lexicon": "adaptive_to_child",
    "use_interests": True,
    "instructive": 3,
    "voice_override": False,
    "struggle_window": "standard",
    "anti_spoiler": True,
    "one_question": True,
    "stay_on_course": True,
    "growth_praise": True,
    "misconception_policy": "explain_and_retry_once",
    "self_explanation": True,
    "enrichment": "on_request",
}

OVERARCHING_ENUMS: dict[str, set[str]] = {
    "orient_framing": {"none", "brief_hook", "elaborate_outline"},
    "instructional_stance": {
        "direct_instruction_first",
        "guided_discovery",
        "productive_challenge_first",
    },
    "scaffolding_escalation": {
        "socratic_probing",
        "progressive_nudge_then_scaffold",
        "worked_example_on_first_miss",
    },
    "stay_on_course": {"strict", "brief_answer_then_return", "exploratory"},
    "misconception_policy": {
        "nudge_without_naming",
        "explain_and_retry_once",
        "immediate_redirect",
    },
    "prerequisite_support_policy": {
        "inline_micro_recap",
        "scaffold_heavily",
        "no_special_adjustment",
    },
    "encouragement_style": {
        "process_praise",
        "matter_of_fact_confirm",
        "minimal",
    },
    "close_summary_depth": {
        "concise",
        "restate_in_learner_words",
        "diagnostic_strengths_and_gaps",
    },
}

_OVERARCHING_ALIASES: dict[str, dict[str, str]] = {
    "encouragement_style": {
        "brief_confirm": "matter_of_fact_confirm",
    },
    "close_summary_depth": {
        "elaborate_strengths_and_weaknesses": "diagnostic_strengths_and_gaps",
    },
    "misconception_policy": {
        "retry_once": "explain_and_retry_once",
    },
}

_LEGACY_LEXICON_TO_REGISTER: dict[str, str] = {
    "1": "everyday_conversational",
    "2": "everyday_conversational",
    "3": "adaptive_to_child",
    "4": "academic_precision",
    "5": "story_rich_expressive",
    "match_child": "adaptive_to_child",
    "early-concrete": "everyday_conversational",
    "middle-grade-vivid": "adaptive_to_child",
    "precise-visual": "academic_precision",
    "analytical-high-school": "academic_precision",
}

_LEGACY_PERSONA_TO_CANONICAL: dict[str, str] = {
    "curious-co-explorer": "explorer",
    "tactical-coach": "coach",
    "debate-moderator": "socratic_mentor",
    "patient-explainer": "coach",
}

_LEGACY_METAPHOR_TO_CANONICAL: dict[str, str] = {
    "playground-sports": "sports",
    "buildings-machines": "everyday",
    "policy-cause": "everyday",
    "none": "everyday",
}

_LEGACY_SIDEKICK_TO_CANONICAL: dict[str, str] = {
    "off": "none",
    "bumbling-partner": "barnaby",
    "rookie-picture": "pixel",
    "pundit": "spark",
}


def map_legacy_lexicon(raw_lexicon: object) -> str:
    """Map legacy lexicon values (1..5, match_child, or older voice ids) to vocabulary_register."""
    if raw_lexicon is None:
        return "adaptive_to_child"
    key = str(raw_lexicon).strip()
    if key in LAYER_3_ENUMS["vocabulary_register"]:
        return key
    return _LEGACY_LEXICON_TO_REGISTER.get(key, "adaptive_to_child")


def map_legacy_use_interests(raw_use_interests: object) -> str:
    """Map legacy boolean use_interests to interest_weaving."""
    if isinstance(raw_use_interests, bool):
        return "subtle_natural" if raw_use_interests else "off"
    text = str(raw_use_interests or "").strip().lower()
    if text in {"false", "no", "0", "off"}:
        return "off"
    if text in {"frequent_thematic"}:
        return "frequent_thematic"
    return "subtle_natural"


def normalize_voice_settings(
    raw: dict | None = None,
    *,
    persona: object = None,
    vocabulary_register: object = None,
    lexicon: object = None,
    interest_weaving: object = None,
    use_interests: object = None,
    metaphors: object = None,
    humor_and_wit: object = None,
    sidekick: object = None,
    strict: bool = False,
) -> dict[str, object]:
    """Normalize the 6 Layer 3 Voice & Persona settings with backward compatibility."""
    src = dict(raw or {})
    for k, v in (
        ("persona", persona),
        ("vocabulary_register", vocabulary_register),
        ("lexicon", lexicon),
        ("interest_weaving", interest_weaving),
        ("use_interests", use_interests),
        ("metaphors", metaphors),
        ("humor_and_wit", humor_and_wit),
        ("sidekick", sidekick),
    ):
        if v is not None:
            src[k] = v

    out_persona = str(src.get("persona") or "coach").strip()
    if out_persona not in LAYER_3_ENUMS["persona"]:
        if strict:
            raise ValueError(f"persona must be one of {sorted(LAYER_3_ENUMS['persona'])}")
        out_persona = "coach"

    raw_reg = src.get("vocabulary_register")
    if raw_reg is not None and str(raw_reg).strip() != "":
        reg_str = str(raw_reg).strip()
        if reg_str in LAYER_3_ENUMS["vocabulary_register"]:
            out_register = reg_str
        elif reg_str in _LEGACY_LEXICON_TO_REGISTER:
            out_register = _LEGACY_LEXICON_TO_REGISTER[reg_str]
        elif strict:
            raise ValueError(
                f"vocabulary_register must be one of {sorted(LAYER_3_ENUMS['vocabulary_register'])}"
            )
        else:
            out_register = map_legacy_lexicon(src.get("lexicon"))
    else:
        out_register = map_legacy_lexicon(src.get("lexicon"))

    raw_weaving = src.get("interest_weaving")
    if raw_weaving is not None and str(raw_weaving).strip() != "":
        weaving_str = str(raw_weaving).strip()
        if weaving_str in LAYER_3_ENUMS["interest_weaving"]:
            out_weaving = weaving_str
        elif strict:
            raise ValueError(
                f"interest_weaving must be one of {sorted(LAYER_3_ENUMS['interest_weaving'])}"
            )
        else:
            out_weaving = map_legacy_use_interests(src.get("use_interests", True))
    elif "use_interests" in src and src.get("use_interests") is not None:
        out_weaving = map_legacy_use_interests(src.get("use_interests"))
    else:
        out_weaving = "subtle_natural"

    out_metaphors = str(src.get("metaphors") or "everyday").strip()
    if out_metaphors not in LAYER_3_ENUMS["metaphors"]:
        if strict:
            raise ValueError(f"metaphors must be one of {sorted(LAYER_3_ENUMS['metaphors'])}")
        out_metaphors = "everyday"

    raw_humor = src.get("humor_and_wit")
    if raw_humor is not None and str(raw_humor).strip() != "":
        humor_str = str(raw_humor).strip()
        if humor_str in LAYER_3_ENUMS["humor_and_wit"]:
            out_humor = humor_str
        elif strict:
            raise ValueError(
                f"humor_and_wit must be one of {sorted(LAYER_3_ENUMS['humor_and_wit'])}"
            )
        else:
            out_humor = "light_warm"
    else:
        out_humor = "light_warm"

    out_sidekick = str(src.get("sidekick") or "none").strip()
    if out_sidekick not in LAYER_3_ENUMS["sidekick"]:
        if strict:
            raise ValueError(f"sidekick must be one of {sorted(LAYER_3_ENUMS['sidekick'])}")
        out_sidekick = "none"

    raw_lex = str(src.get("lexicon") or "").strip()
    synced_lexicon = raw_lex if raw_lex in (ids(VOCABULARY_REGISTERS) | {"early-concrete", "middle-grade-vivid", "precise-visual", "analytical-high-school"}) else out_register
    if raw_reg is not None and str(raw_reg).strip() in LAYER_3_ENUMS["vocabulary_register"]:
        synced_lexicon = out_register

    return {
        "persona": out_persona,
        "vocabulary_register": out_register,
        "interest_weaving": out_weaving,
        "metaphors": out_metaphors,
        "humor_and_wit": out_humor,
        "sidekick": out_sidekick,
        "lexicon": synced_lexicon,
        "use_interests": out_weaving != "off",
    }


def normalize_profile(raw: dict | TutorProfile | None, *, strict: bool = False) -> dict[str, object]:
    """Normalize a tutor profile dict or ORM row into the canonical Layer 3 + Layer 4 shape."""
    if isinstance(raw, TutorProfile):
        cfg_raw = raw.kc_tutor_config if isinstance(raw.kc_tutor_config, dict) else {}
        voice_raw = cfg_raw.get("voice") if isinstance(cfg_raw.get("voice"), dict) else {}
        src: dict[str, object] = {
            "id": getattr(raw, "id", PROFILE_ID) or PROFILE_ID,
            "name": getattr(raw, "name", "Default") or "Default",
            "slug": getattr(raw, "slug", "default") or "default",
            "description": (
                raw.description
                if getattr(raw, "description", None) is not None
                else DEFAULT_TUTOR_DESCRIPTION
            ),
            "avatar_preset": normalize_avatar_preset(
                getattr(raw, "avatar_preset", "default_circle"),
                strict=False,
            ),
            "avatar_url": getattr(raw, "avatar_url", None),
            "is_default": bool(getattr(raw, "is_default", False) or getattr(raw, "id", "") == PROFILE_ID),
            "instructive": raw.instructive,
            "persona": raw.persona,
            "lexicon": raw.lexicon,
            "voice_override": raw.voice_override,
            "metaphors": raw.metaphors,
            "sidekick": raw.sidekick,
            "struggle_window": raw.struggle_window,
            "anti_spoiler": raw.anti_spoiler,
            "one_question": raw.one_question,
            "use_interests": raw.use_interests,
            "stay_on_course": raw.stay_on_course,
            "growth_praise": raw.growth_praise,
            "misconception_policy": raw.misconception_policy,
            "self_explanation": raw.self_explanation,
            "enrichment": raw.enrichment,
            "vocabulary_register": getattr(raw, "_vocabulary_register", None) or voice_raw.get("vocabulary_register"),
            "interest_weaving": getattr(raw, "_interest_weaving", None)
            or (
                voice_raw.get("interest_weaving")
                if raw.use_interests and voice_raw.get("interest_weaving") in {"subtle_natural", "frequent_thematic"}
                else ("off" if raw.use_interests is False else voice_raw.get("interest_weaving"))
            ),
            "humor_and_wit": getattr(raw, "_humor_and_wit", None) or voice_raw.get("humor_and_wit"),
            "kc_tutor_config": cfg_raw,
        }
    elif isinstance(raw, dict):
        cfg_raw = raw.get("kc_tutor_config") if isinstance(raw.get("kc_tutor_config"), dict) else {}
        voice_raw = cfg_raw.get("voice") if isinstance(cfg_raw.get("voice"), dict) else {}
        src = dict(raw)
        if "vocabulary_register" not in src and "vocabulary_register" in voice_raw:
            src["vocabulary_register"] = voice_raw.get("vocabulary_register")
        if "interest_weaving" not in src and "interest_weaving" in voice_raw and "use_interests" not in src:
            src["interest_weaving"] = voice_raw.get("interest_weaving")
        if "humor_and_wit" not in src and "humor_and_wit" in voice_raw:
            src["humor_and_wit"] = voice_raw.get("humor_and_wit")
    else:
        src = {}

    voice = normalize_voice_settings(src, strict=strict)
    cfg = normalize_kc_tutor_config(
        src.get("kc_tutor_config") if isinstance(src.get("kc_tutor_config"), dict) else None,
        strict=strict,
    )
    cfg["voice"] = {
        "persona": str(voice["persona"]),
        "vocabulary_register": str(voice["vocabulary_register"]),
        "interest_weaving": str(voice["interest_weaving"]),
        "metaphors": str(voice["metaphors"]),
        "humor_and_wit": str(voice["humor_and_wit"]),
        "sidekick": str(voice["sidekick"]),
    }
    return {
        **DEFAULT_PROFILE,
        **src,
        **voice,
        "kc_tutor_config": cfg,
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
                val = _OVERARCHING_ALIASES.get(key, {}).get(val, val)
                if val in allowed:
                    base["overarching"][key] = val
                elif strict:
                    raise ValueError(f"overarching.{key} must be one of {sorted(allowed)}")

    raw_voice = raw.get("voice")
    if isinstance(raw_voice, dict):
        voice_norm = normalize_voice_settings(raw_voice, strict=strict)
        base["voice"] = {
            "persona": str(voice_norm["persona"]),
            "vocabulary_register": str(voice_norm["vocabulary_register"]),
            "interest_weaving": str(voice_norm["interest_weaving"]),
            "metaphors": str(voice_norm["metaphors"]),
            "humor_and_wit": str(voice_norm["humor_and_wit"]),
            "sidekick": str(voice_norm["sidekick"]),
        }

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
        name="Default",
        slug="default",
        description=DEFAULT_TUTOR_DESCRIPTION,
        avatar_preset="default_circle",
        avatar_url=None,
        is_default=True,
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
        changed = False
        if not row.kc_tutor_config:
            row.kc_tutor_config = default_kc_tutor_config()
            changed = True
        if not getattr(row, "name", None):
            row.name = "Default"
            changed = True
        if not getattr(row, "slug", None):
            row.slug = "default"
            changed = True
        if getattr(row, "description", None) is None:
            row.description = DEFAULT_TUTOR_DESCRIPTION
            changed = True
        if not getattr(row, "avatar_preset", None):
            row.avatar_preset = "default_circle"
            changed = True
        if not getattr(row, "is_default", False):
            row.is_default = True
            changed = True
        if changed:
            db.flush()
        return row
    row = default_row()
    db.add(row)
    db.flush()
    return row


def reset_default_profile(db: Session) -> TutorProfile:
    """Put the singleton back to the built-in default. Tests use this."""
    row = db.get(TutorProfile, PROFILE_ID)
    fresh = default_row()
    if row is None:
        row = fresh
        db.add(row)
    else:
        _fill(row, fresh)
        row.name = "Default"
        row.slug = "default"
        row.description = DEFAULT_TUTOR_DESCRIPTION
        row.avatar_preset = "default_circle"
        row.avatar_url = None
        row.is_default = True
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


def get_profile_by_id_or_slug(db: Session | None, profile_id: object) -> TutorProfile | None:
    if db is None or profile_id is None:
        return None
    key = str(profile_id).strip()
    if not key:
        return None
    row = db.get(TutorProfile, key)
    if row is not None:
        return row
    row = db.scalar(select(TutorProfile).where(TutorProfile.slug == key))
    if row is not None:
        return row
    if key == "1":
        return db.scalar(select(TutorProfile).where(TutorProfile.is_default.is_(True))) or db.get(
            TutorProfile, PROFILE_ID
        )
    return None


def resolve_active_profile(
    db: Session | None,
    *,
    session: KcSession | None = None,
    student: Student | None = None,
    profile_id: object = None,
) -> TutorProfile:
    """Resolve the active tutor profile: explicit profile_id -> session -> student -> Default."""
    if db is None:
        return default_row()
    if profile_id is not None and str(profile_id).strip():
        found = get_profile_by_id_or_slug(db, profile_id)
        if found is not None:
            return found
    if session is not None and getattr(session, "tutor_profile_id", None):
        found = get_profile_by_id_or_slug(db, session.tutor_profile_id)
        if found is not None:
            return found
    if student is not None and getattr(student, "preferred_tutor_profile_id", None):
        found = get_profile_by_id_or_slug(db, student.preferred_tutor_profile_id)
        if found is not None:
            return found
    return load_profile(db)


def list_profiles(db: Session) -> list[TutorProfile]:
    ensure_default_profile(db)
    stmt = select(TutorProfile).order_by(TutorProfile.is_default.desc(), TutorProfile.id.asc())
    return list(db.scalars(stmt).all())


def unique_tutor_slug(db: Session, name: str, *, exclude_id: str | None = None) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    base = (cleaned or "tutor")[:96]
    if base == PROFILE_ID and exclude_id != PROFILE_ID:
        base = "tutor-default"
    candidate = base
    suffix = 2
    while True:
        existing_id = db.get(TutorProfile, candidate)
        existing_slug = db.scalar(select(TutorProfile).where(TutorProfile.slug == candidate))
        id_clash = existing_id is not None and existing_id.id != exclude_id
        slug_clash = existing_slug is not None and existing_slug.id != exclude_id
        if not id_clash and not slug_clash:
            return candidate
        candidate = f"{base}-{suffix}"
        suffix += 1


def effective_voice_settings(profile: TutorProfile | dict | None) -> dict[str, object]:
    """Return normalized 6 Layer 3 settings for a TutorProfile row or dict."""
    if profile is None:
        return normalize_voice_settings(strict=False)
    norm = normalize_profile(profile, strict=False)
    return {
        "persona": norm["persona"],
        "vocabulary_register": norm["vocabulary_register"],
        "interest_weaving": norm["interest_weaving"],
        "metaphors": norm["metaphors"],
        "humor_and_wit": norm["humor_and_wit"],
        "sidekick": norm["sidekick"],
        "lexicon": norm["lexicon"],
        "use_interests": norm["use_interests"],
    }


_UNSET = object()


def save_profile(
    db: Session,
    *,
    profile_id: str | None = None,
    name: str | None = None,
    description: str | None = None,
    avatar_preset: str | None = None,
    avatar_url: str | None | object = _UNSET,
    instructive: int = 3,
    persona: str = "coach",
    lexicon: str | None = None,
    vocabulary_register: str | None = None,
    interest_weaving: str | None = None,
    humor_and_wit: str | None = None,
    voice_override: bool = False,
    metaphors: str = "everyday",
    sidekick: str = "none",
    struggle_window: str = "standard",
    anti_spoiler: bool = True,
    one_question: bool = True,
    use_interests: bool | None = None,
    stay_on_course: bool = True,
    growth_praise: bool = True,
    misconception_policy: str = "retry_once",
    self_explanation: bool = True,
    enrichment: str = "on_request",
    kc_tutor_config: dict | None = None,
    target_row: TutorProfile | None = None,
) -> TutorProfile:
    if target_row is not None:
        row = target_row
    elif profile_id is not None and str(profile_id).strip():
        found = get_profile_by_id_or_slug(db, profile_id)
        if found is None:
            raise LookupError(f"Tutor profile {profile_id!r} not found")
        row = found
    else:
        row = ensure_default_profile(db)

    if name is not None and str(name).strip():
        cleaned_name = str(name).strip()[:120]
        if row.is_default or row.id == PROFILE_ID:
            row.name = cleaned_name
        else:
            row.name = cleaned_name
    if description is not None:
        row.description = str(description).strip()
    if avatar_preset is not None:
        row.avatar_preset = normalize_avatar_preset(avatar_preset, strict=True)
    if avatar_url is not _UNSET:
        cleaned_url = str(avatar_url).strip() if avatar_url else ""
        row.avatar_url = cleaned_url or None

    existing_cfg = row.kc_tutor_config if isinstance(row.kc_tutor_config, dict) else {}
    existing_voice = existing_cfg.get("voice") if isinstance(existing_cfg.get("voice"), dict) else {}

    incoming_voice = (kc_tutor_config or {}).get("voice") if isinstance(kc_tutor_config, dict) and isinstance((kc_tutor_config or {}).get("voice"), dict) else {}

    eff_vocab = vocabulary_register or incoming_voice.get("vocabulary_register")
    eff_weaving = interest_weaving or incoming_voice.get("interest_weaving")
    eff_humor = humor_and_wit or incoming_voice.get("humor_and_wit") or existing_voice.get("humor_and_wit") or "light_warm"

    voice = normalize_voice_settings(
        persona=persona,
        vocabulary_register=eff_vocab,
        lexicon=lexicon or eff_vocab or PERSONA_VOICE.get(persona, "adaptive_to_child"),
        interest_weaving=eff_weaving,
        use_interests=True if use_interests is None else use_interests,
        metaphors=metaphors,
        humor_and_wit=eff_humor,
        sidekick=sidekick,
        strict=True,
    )

    candidate_lex = str(lexicon or voice["vocabulary_register"])
    if eff_vocab is not None and lexicon is None:
        stored_lexicon = str(voice["vocabulary_register"])
        stored_override = stored_lexicon != PERSONA_VOICE.get(persona, "adaptive_to_child")
    elif voice_override:
        stored_lexicon = candidate_lex
        stored_override = candidate_lex != PERSONA_VOICE.get(persona, candidate_lex)
    elif eff_vocab is not None:
        stored_lexicon = str(voice["vocabulary_register"])
        stored_override = stored_lexicon != PERSONA_VOICE.get(persona, "adaptive_to_child")
    else:
        stored_lexicon = PERSONA_VOICE.get(persona, candidate_lex)
        stored_override = False

    row.instructive = instructive
    row.persona = str(voice["persona"])
    row.lexicon = stored_lexicon
    row.voice_override = stored_override
    row.metaphors = str(voice["metaphors"])
    row.sidekick = str(voice["sidekick"])
    row.struggle_window = struggle_window
    row.anti_spoiler = anti_spoiler
    row.one_question = one_question
    row.use_interests = bool(voice["use_interests"])
    row.stay_on_course = stay_on_course
    row.growth_praise = growth_praise
    row.misconception_policy = misconception_policy
    row.self_explanation = self_explanation
    row.enrichment = enrichment
    if kc_tutor_config is not None:
        norm_cfg = normalize_kc_tutor_config(kc_tutor_config, strict=True)
    else:
        norm_cfg = normalize_kc_tutor_config(row.kc_tutor_config if isinstance(row.kc_tutor_config, dict) else None, strict=False)
    norm_cfg["voice"] = {
        "persona": str(voice["persona"]),
        "vocabulary_register": str(voice["vocabulary_register"] if eff_vocab is not None else map_legacy_lexicon(stored_lexicon)),
        "interest_weaving": str(voice["interest_weaving"]),
        "metaphors": str(voice["metaphors"]),
        "humor_and_wit": str(voice["humor_and_wit"]),
        "sidekick": str(voice["sidekick"]),
    }
    row.kc_tutor_config = norm_cfg
    row.updated_at = _now()
    db.flush()
    return row


def create_tutor_profile(
    db: Session,
    *,
    name: str,
    description: str | None = None,
    avatar_preset: str | None = None,
    avatar_url: str | None = None,
    source_profile_id: str | int | None = None,
    overrides: dict[str, object] | None = None,
) -> TutorProfile:
    ensure_default_profile(db)
    cleaned_name = str(name or "").strip()[:120]
    if not cleaned_name:
        raise ValueError("Tutor name is required")
    slug = unique_tutor_slug(db, cleaned_name)
    source = (
        get_profile_by_id_or_slug(db, source_profile_id)
        if source_profile_id is not None and str(source_profile_id).strip()
        else None
    )
    if source is not None:
        base_norm = normalize_profile(source, strict=False)
        base_cfg = copy.deepcopy(effective_kc_tutor_config(source))
        base_desc = source.description or DEFAULT_TUTOR_DESCRIPTION
        base_avatar = source.avatar_preset or "default_circle"
        base_avatar_url = source.avatar_url
    else:
        base_norm = copy.deepcopy(DEFAULT_PROFILE)
        base_cfg = default_kc_tutor_config()
        base_desc = DEFAULT_TUTOR_DESCRIPTION
        base_avatar = "default_circle"
        base_avatar_url = None

    ovr = dict(overrides or {})
    chosen_desc = (
        str(description).strip()
        if description is not None
        else base_desc
    )
    chosen_preset = normalize_avatar_preset(
        avatar_preset if avatar_preset is not None else base_avatar,
        strict=True,
    )
    chosen_url = (
        (str(avatar_url).strip() or None)
        if avatar_url is not None
        else base_avatar_url
    )

    row = TutorProfile(
        id=slug,
        name=cleaned_name,
        slug=slug,
        description=chosen_desc,
        avatar_preset=chosen_preset,
        avatar_url=chosen_url,
        is_default=False,
        instructive=int(ovr.get("instructive") or base_norm.get("instructive") or 3),
        persona=str(ovr.get("persona") or base_norm.get("persona") or "coach"),
        lexicon=str(ovr.get("lexicon") or base_norm.get("lexicon") or "adaptive_to_child"),
        voice_override=bool(ovr.get("voice_override", base_norm.get("voice_override", False))),
        metaphors=str(ovr.get("metaphors") or base_norm.get("metaphors") or "everyday"),
        sidekick=str(ovr.get("sidekick") or base_norm.get("sidekick") or "none"),
        struggle_window=str(ovr.get("struggle_window") or base_norm.get("struggle_window") or "standard"),
        anti_spoiler=bool(ovr.get("anti_spoiler", True)),
        one_question=bool(ovr.get("one_question", True)),
        use_interests=bool(ovr.get("use_interests", True)),
        stay_on_course=bool(ovr.get("stay_on_course", True)),
        growth_praise=bool(ovr.get("growth_praise", True)),
        misconception_policy=str(ovr.get("misconception_policy") or base_norm.get("misconception_policy") or "explain_and_retry_once"),
        self_explanation=bool(ovr.get("self_explanation", True)),
        enrichment=str(ovr.get("enrichment") or base_norm.get("enrichment") or "on_request"),
        kc_tutor_config=base_cfg,
        updated_at=_now(),
    )
    db.add(row)
    db.flush()

    return save_profile(
        db,
        target_row=row,
        name=cleaned_name,
        description=chosen_desc,
        avatar_preset=chosen_preset,
        avatar_url=chosen_url,
        instructive=int(ovr.get("instructive") or row.instructive or 3),
        persona=str(ovr.get("persona") or base_norm.get("persona") or "coach"),
        lexicon=str(ovr.get("lexicon") or base_norm.get("lexicon") or "adaptive_to_child"),
        vocabulary_register=str(
            ovr.get("vocabulary_register")
            or base_norm.get("vocabulary_register")
            or "adaptive_to_child"
        ),
        interest_weaving=str(
            ovr.get("interest_weaving")
            or base_norm.get("interest_weaving")
            or "subtle_natural"
        ),
        humor_and_wit=str(
            ovr.get("humor_and_wit")
            or base_norm.get("humor_and_wit")
            or "light_warm"
        ),
        voice_override=bool(ovr.get("voice_override", True)),
        metaphors=str(ovr.get("metaphors") or base_norm.get("metaphors") or "everyday"),
        sidekick=str(ovr.get("sidekick") or base_norm.get("sidekick") or "none"),
        struggle_window=str(ovr.get("struggle_window") or base_norm.get("struggle_window") or "standard"),
        anti_spoiler=bool(ovr.get("anti_spoiler", True)),
        one_question=bool(ovr.get("one_question", True)),
        use_interests=bool(ovr.get("use_interests", True)),
        stay_on_course=bool(ovr.get("stay_on_course", True)),
        growth_praise=bool(ovr.get("growth_praise", True)),
        misconception_policy=str(ovr.get("misconception_policy") or base_norm.get("misconception_policy") or "explain_and_retry_once"),
        self_explanation=bool(ovr.get("self_explanation", True)),
        enrichment=str(ovr.get("enrichment") or base_norm.get("enrichment") or "on_request"),
        kc_tutor_config=ovr.get("kc_tutor_config") if isinstance(ovr.get("kc_tutor_config"), dict) else base_cfg,
    )


def reset_tutor_profile(db: Session, profile_id: str | None = None) -> TutorProfile:
    ensure_default_profile(db)
    if profile_id is None or not str(profile_id).strip():
        row = ensure_default_profile(db)
    else:
        found = get_profile_by_id_or_slug(db, profile_id)
        if found is None:
            raise LookupError(f"Tutor profile {profile_id!r} not found")
        row = found
    fresh_cfg = default_kc_tutor_config()
    return save_profile(
        db,
        target_row=row,
        name="Default" if (row.is_default or row.id == PROFILE_ID) else row.name,
        description=DEFAULT_TUTOR_DESCRIPTION if (row.is_default or row.id == PROFILE_ID) else row.description,
        avatar_preset="default_circle" if (row.is_default or row.id == PROFILE_ID) else row.avatar_preset,
        avatar_url=None if (row.is_default or row.id == PROFILE_ID) else row.avatar_url,
        instructive=3,
        persona=str(DEFAULT_PROFILE["persona"]),
        lexicon=str(DEFAULT_PROFILE["lexicon"]),
        vocabulary_register=str(DEFAULT_PROFILE["vocabulary_register"]),
        interest_weaving=str(DEFAULT_PROFILE["interest_weaving"]),
        humor_and_wit=str(DEFAULT_PROFILE["humor_and_wit"]),
        voice_override=False,
        metaphors=str(DEFAULT_PROFILE["metaphors"]),
        sidekick=str(DEFAULT_PROFILE["sidekick"]),
        struggle_window=str(DEFAULT_PROFILE["struggle_window"]),
        anti_spoiler=True,
        one_question=True,
        use_interests=True,
        stay_on_course=True,
        growth_praise=True,
        misconception_policy=str(DEFAULT_PROFILE["misconception_policy"]),
        self_explanation=True,
        enrichment=str(DEFAULT_PROFILE["enrichment"]),
        kc_tutor_config=fresh_cfg,
    )


def delete_tutor_profile(db: Session, profile_id: str) -> None:
    ensure_default_profile(db)
    row = get_profile_by_id_or_slug(db, profile_id)
    if row is None:
        raise LookupError(f"Tutor profile {profile_id!r} not found")
    if row.is_default or row.id == PROFILE_ID:
        raise ValueError("The Default tutor profile cannot be deleted.")
    db.execute(
        update(Student)
        .where(Student.preferred_tutor_profile_id == row.id)
        .values(preferred_tutor_profile_id=None)
    )
    db.execute(
        update(KcSession)
        .where(KcSession.tutor_profile_id == row.id)
        .values(tutor_profile_id=None)
    )
    db.delete(row)
    db.flush()
