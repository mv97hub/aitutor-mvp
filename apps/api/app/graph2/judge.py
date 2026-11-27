"""Single-call 0-3 batch judge prompt builder and strict output validator.

Runs after the closing reply is sent. Grades ONLY the eligible skills for that
component on a single 0-3 scale (no second ICAP number). Never imports
`app.kc_prompt`, `app.kc_loop`, `app.kc`, or `app.block_score`.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.graph2.signals import EligibleSkillEvidence, SKILL_LABELS

SKILL_RUBRIC_ANCHORS: dict[str, dict[str, str]] = {
    "evidence": {
        "criterion": "Did the child rest their answer on a specific line, number, or fact from the given material?",
        "0": "No evidence cited or fabricated detail not in the material.",
        "1": "Vague gesture to the material without pointing to a concrete line, number, or fact.",
        "2": "Points to a relevant fact, line, or number from the material to back up the answer.",
        "3": "Accurately anchors the reasoning in specific evidence from the material and links it clearly to the claim.",
    },
    "perspectives": {
        "criterion": "Did the child represent a second viewpoint fairly so both sides are real?",
        "0": "Single viewpoint only or dismisses the other side without representing it.",
        "1": "Acknowledges another view exists but caricatures or barely states it.",
        "2": "States both viewpoints fairly with real reasons on each side.",
        "3": "Weighs both perspectives fairly and synthesizes the tension or trade-off between them.",
    },
    "causes": {
        "criterion": "Did the child identify what produces the result or what changes if one cause is removed?",
        "0": "Does not identify a causal mechanism or confuses correlation/symptom with cause.",
        "1": "Names a partial factor without connecting how it produces the outcome.",
        "2": "States a clear cause-and-effect link explaining what produces the outcome.",
        "3": "Traces the causal mechanism accurately, including what shifts if a key cause changes or is removed.",
    },
    "inquiry": {
        "criterion": "Did the child question a claim, a source, or their own answer with genuine curiosity?",
        "0": "Accepts claims passively with no questioning or probing.",
        "1": "Asks a surface clarification without testing the claim or boundary.",
        "2": "Asks a relevant why/what-if question or challenges a claim with a concrete test.",
        "3": "Probes assumptions, boundary cases, or unverified evidence with a sharp, on-topic question.",
    },
    "errors": {
        "criterion": "Did the child locate and explain the broken step in flawed reasoning?",
        "0": "Misses the flaw or agrees with the broken step.",
        "1": "Sense that something is wrong without pinpointing where the step breaks.",
        "2": "Identifies the specific broken step accurately.",
        "3": "Pinpoints the broken step, explains why it fails, and repairs it cleanly.",
    },
    "transfer": {
        "criterion": "Did the child carry the underlying idea into a new situation or surface case?",
        "0": "Cannot apply the idea outside the original wording or repeats the old example.",
        "1": "Partial carry-over to the new situation with missing or mixed-up mapping.",
        "2": "Correctly applies the underlying principle to the new situation.",
        "3": "Cleanly maps the invariant principle onto the novel case and explains why it holds there.",
    },
    "explaining": {
        "criterion": "Did the child explain the idea clearly for someone else in their own words?",
        "0": "Cannot explain the idea or only repeats fragments verbatim.",
        "1": "Incomplete explanation that leaves out the core idea or stays unclear to a listener.",
        "2": "Clear, accurate plain-language explanation in the child's own words.",
        "3": "Lucid, audience-aware explanation in own words with a helpful example or concrete framing.",
    },
    "calibration": {
        "criterion": "Did the child realistically gauge certainty or name what evidence would change their mind?",
        "0": "No reflection on certainty or claims total certainty without basis.",
        "1": "States a bare confidence level without explaining what supports or could revise it.",
        "2": "Matches certainty reasonably to evidence or names a plausible revision trigger.",
        "3": "Clearly calibrates confidence to what is verified and names specific evidence that would make them revise.",
    },
}


@dataclass(frozen=True)
class GradedSkillResult:
    skill: str
    rubric_grade: int
    raw_y: float
    cap_applied: str | None
    capped_y: float
    quote: str
    rationale: str


@dataclass(frozen=True)
class ValidatedJudgeBatch:
    grades: list[GradedSkillResult]
    multi_perspective_synthesis: bool


def build_judge_bundle(
    *,
    component_title: str,
    eligible_skills: dict[str, EligibleSkillEvidence],
) -> dict:
    """Build the single prompt + strict JSON schema for the post-close batch judge."""
    ordered_keys = list(eligible_skills.keys())
    if not ordered_keys:
        return {}

    blocks_text: list[str] = [
        f"Component: {component_title or 'Lesson component'}",
        "Grade ONLY the listed eligible skills on an integer 0-3 scale based strictly on the child's lines.",
        "For every skill, quote a short verbatim snippet from the child's lines below (never invent words).",
        "Do not invent skills outside the list. Do not use any second scale.",
    ]

    for key in ordered_keys:
        ev = eligible_skills[key]
        anchor = SKILL_RUBRIC_ANCHORS[key]
        label = SKILL_LABELS.get(key, key)
        child_block = "\n".join(f'  - "{line}"' for line in ev.child_lines) or '  - "(no substantive line)"'
        extra_q = ""
        if ev.on_topic_questions:
            qs = "\n".join(f'  - "{q}"' for q in ev.on_topic_questions)
            extra_q = f"\nOn-topic learner questions observed before close (signal only, not an automatic grade):\n{qs}"
        blocks_text.append(
            "\n".join(
                [
                    f"### Skill: {key} ({label})",
                    f"Claim ({ev.claim_id}): {ev.claim_statement}",
                    f"Block: {ev.block_type} ({ev.block_id}) | Substeps: {', '.join(ev.substeps)}",
                    f"Criterion: {anchor['criterion']}",
                    f"Rubric 0: {anchor['0']}",
                    f"Rubric 1: {anchor['1']}",
                    f"Rubric 2: {anchor['2']}",
                    f"Rubric 3: {anchor['3']}",
                    f"Child lines:\n{child_block}{extra_q}",
                ]
            )
        )

    has_perspectives = "perspectives" in eligible_skills
    if has_perspectives:
        blocks_text.append(
            "Also set `multi_perspective_synthesis` to true ONLY if the child genuinely integrated "
            "competing perspectives into a nuanced synthesis (equivalent to a 3/3 on Perspectives)."
        )
    else:
        blocks_text.append("Set `multi_perspective_synthesis` to false (Perspectives was not eligible).")

    system_prompt = (
        "You are a strict, calm educational rubric grader. "
        "Score each eligible skill independently from 0 to 3 using the anchors provided. "
        "Never grade unasked skills. Quote only verbatim text from the child's lines."
    )

    response_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "grades": {
                "type": "array",
                "minItems": len(ordered_keys),
                "maxItems": len(ordered_keys),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "skill": {"type": "string", "enum": ordered_keys},
                        "grade": {"type": "integer", "minimum": 0, "maximum": 3},
                        "quote": {"type": "string"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["skill", "grade", "quote", "rationale"],
                },
            },
            "multi_perspective_synthesis": {"type": "boolean"},
        },
        "required": ["grades", "multi_perspective_synthesis"],
    }

    return {
        "system_prompt": system_prompt,
        "user_prompt": "\n\n".join(blocks_text),
        "response_schema": response_schema,
        "eligible_skills": ordered_keys,
        "temperature": 0.0,
    }


def _grounded_quote(raw_quote: str, ev: EligibleSkillEvidence) -> str:
    candidate = " ".join(str(raw_quote or "").split()).strip()
    if candidate:
        low = candidate.lower()
        for line in (*ev.child_lines, *ev.on_topic_questions):
            if low in " ".join(line.split()).lower():
                return candidate[:240]
    return ev.best_quote[:240]


def validate_judge_output(
    raw_output: dict,
    eligible_skills: dict[str, EligibleSkillEvidence],
) -> ValidatedJudgeBatch:
    """Validate structured judge grades and apply deterministic caps before EMA.

    Caps:
    - Revealed or giveaway step forces y <= 0.20 (cap_applied = 'revealed' or 'giveaway').
    - 3-gram overlap >= 0.65 (non-exempt) forces y <= 0.40 (cap_applied = 'overlap').
    """
    if not isinstance(raw_output, dict):
        raise ValueError("Judge output must be an object.")
    raw_grades = raw_output.get("grades")
    if not isinstance(raw_grades, list):
        raise ValueError("Judge output must include a grades array.")

    seen: set[str] = set()
    validated: list[GradedSkillResult] = []
    for item in raw_grades:
        if not isinstance(item, dict):
            continue
        skill = str(item.get("skill") or "").strip().lower()
        if skill not in eligible_skills or skill in seen:
            continue
        raw_grade = item.get("grade")
        if isinstance(raw_grade, bool) or not isinstance(raw_grade, int) or not (0 <= raw_grade <= 3):
            raise ValueError(f"Invalid rubric grade for {skill!r}: must be integer 0..3.")
        seen.add(skill)
        ev = eligible_skills[skill]
        raw_y = round(raw_grade / 3.0, 4)
        cap_applied: str | None = None
        capped_y = raw_y
        if ev.cap is not None:
            if raw_y > ev.cap:
                capped_y = ev.cap
                cap_applied = ev.cap_reason
            elif ev.revealed_or_giveaway:
                # Record reveal/giveaway cap attribution even when raw_y <= 0.20 (e.g. grade=0).
                capped_y = min(raw_y, ev.cap)
                cap_applied = ev.cap_reason

        quote = _grounded_quote(str(item.get("quote") or ""), ev)
        rationale = " ".join(str(item.get("rationale") or "").split()).strip()[:300]
        validated.append(
            GradedSkillResult(
                skill=skill,
                rubric_grade=raw_grade,
                raw_y=raw_y,
                cap_applied=cap_applied,
                capped_y=round(capped_y, 4),
                quote=quote,
                rationale=rationale,
            )
        )

    if not validated and eligible_skills:
        raise ValueError("Judge output contained no valid grades for eligible skills.")

    # 4th biomarker comes ONLY from the judge, and only when perspectives was eligible & unrevealed.
    perspectives_ev = eligible_skills.get("perspectives")
    allow_synth = bool(
        perspectives_ev is not None
        and not perspectives_ev.revealed_or_giveaway
        and raw_output.get("multi_perspective_synthesis") is True
    )
    return ValidatedJudgeBatch(grades=validated, multi_perspective_synthesis=allow_synth)
