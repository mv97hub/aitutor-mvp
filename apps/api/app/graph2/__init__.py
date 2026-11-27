"""Graph-2 cognitive skills, biomarkers, frozen tutor note, and shared radar.

Architectural boundary: modules in this package MUST NEVER import
`app.kc_prompt`, `app.kc_loop`, `app.kc`, or `app.block_score`.
"""

from app.graph2.digest import compose_tutor_note
from app.graph2.judge import build_judge_bundle, validate_judge_output
from app.graph2.signals import (
    MIN_OBSERVATIONS_FOR_RADAR,
    OVERLAP_CAP,
    OVERLAP_THRESHOLD,
    PRIOR_SCORE,
    REVEAL_CAP,
    SKILL_LABELS,
    CloseAnalysis,
    EligibleSkillEvidence,
    analyze_component_close,
    three_gram_overlap,
)
from app.graph2.state import (
    apply_judge_results,
    apply_sync_close,
    build_radar_payload,
    copy_note_for_session_open,
    is_harness_student_or_session,
    mark_judge_failed,
    prepare_judge_request,
)

__all__ = [
    "CloseAnalysis",
    "EligibleSkillEvidence",
    "MIN_OBSERVATIONS_FOR_RADAR",
    "OVERLAP_CAP",
    "OVERLAP_THRESHOLD",
    "PRIOR_SCORE",
    "REVEAL_CAP",
    "SKILL_LABELS",
    "analyze_component_close",
    "apply_judge_results",
    "apply_sync_close",
    "build_judge_bundle",
    "build_radar_payload",
    "compose_tutor_note",
    "copy_note_for_session_open",
    "is_harness_student_or_session",
    "mark_judge_failed",
    "prepare_judge_request",
    "three_gram_overlap",
    "validate_judge_output",
]
