"""Apply a model decision to the active block and substep in a KC session.

Deterministic grading is used strictly for MCQ option index matching
(`picked_index == correct_index`). Open-ended substeps use the model's
structured evaluation (`substep_passed`, `block_complete`, `rubric_met`).
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass

from app.kc_blocks import learner_asks_for_passage, quote_in_text
from app.kc_prompt import (
    HINTS,
    block_evidence_id,
    default_substep_for_block,
    explanation_topic_index,
    explanation_topics,
    initial_block_state,
    max_retries_for_block,
    substeps_for_block,
)
from app.models import KcGoal

SAY_THAT_AGAIN = "Say that again?"


@dataclass(frozen=True)
class BlockResolution:
    decision: str
    hint_tier: str
    move_attempts: int
    reveals: int
    enrichment_turns: int
    rubric_met: list[str]
    misconception: str
    next_step: int
    next_block_id: str | None
    next_block_state: dict
    block_results: list[dict]
    mark_known: bool
    mark_fragile: bool
    redirect: bool
    unit_complete: bool
    advance_block: bool
    passed: bool


def _next_tier(tier: str) -> str:
    try:
        index = HINTS.index(tier)
    except ValueError:
        index = 0
    return HINTS[min(index + 1, len(HINTS) - 1)]


def _clean_ids(values: list[str]) -> list[str]:
    seen: list[str] = []
    for item in values:
        text = str(item).strip()
        if text and text not in seen:
            seen.append(text)
    return seen


def match_mcq_choice_index(answer: str, choices: list[dict]) -> int | None:
    """Deterministically resolve which 0-based choice index the learner picked."""
    cleaned = (answer or "").strip()
    if not cleaned or not choices:
        return None
    first_line = cleaned.splitlines()[0].strip()
    lower = first_line.lower()
    for idx, ch in enumerate(choices):
        if not isinstance(ch, dict):
            continue
        cid = str(ch.get("id") or "").strip().lower()
        ctext = str(ch.get("text") or "").strip().lower()
        if lower == cid or (ctext and lower == ctext):
            return idx
    for idx, ch in enumerate(choices):
        if not isinstance(ch, dict):
            continue
        ctext = str(ch.get("text") or "").strip().lower()
        if ctext and ctext in lower:
            return idx
    return None


def _words(text: str) -> list[str]:
    return [word for word in "".join(ch.lower() if ch.isalnum() else " " for ch in (text or "")).split() if word]


def _matches(answer: str, phrase: str) -> bool:
    from app.kc import matches_phrase

    return matches_phrase(answer, phrase)


def _substantive(answer: str, minimum_words: int = 2) -> bool:
    return len((answer or "").split()) >= minimum_words


def _precise(answer: str, phrase: str) -> bool:
    needed = [word for word in _words(phrase) if len(word) > 3]
    if not needed:
        return _matches(answer, phrase)
    have = set(_words(answer))
    return all(word in have for word in needed)


def _strict_fact(answer: str, phrase: str) -> bool:
    left = " ".join(_words(answer))
    right = " ".join(_words(phrase))
    return bool(left and right and (right in left or left in right))


def _data(block: dict) -> dict:
    raw = block.get("data")
    return raw if isinstance(raw, dict) else {}


def _bcfg(block: dict, cfg: dict) -> dict:
    btype = str(block.get("type") or "topic_goal").strip()
    found = ((cfg or {}).get("blocks") or {}).get(btype)
    return found if isinstance(found, dict) else {}


def mcq_payload(block: dict, state: dict | None) -> tuple[list[dict], int]:
    """Choices and the correct index. Dynamic items come from generated_mcq."""
    data = _data(block)
    mode = str(data.get("mode") or "static").strip()
    stored = state if isinstance(state, dict) else {}
    if mode == "dynamic":
        generated = stored.get("generated_mcq") if isinstance(stored.get("generated_mcq"), dict) else None
        if not generated:
            return [], 0
        raw = generated.get("choices") if isinstance(generated.get("choices"), list) else []
        choices = [
            {"id": str(item.get("id") or chr(ord("a") + index)), "text": str(item.get("text") or "")}
            for index, item in enumerate(raw)
            if isinstance(item, dict)
        ]
        return choices, int(generated.get("correct_index") or 0)
    raw = data.get("choices") if isinstance(data.get("choices"), list) else []
    choices: list[dict] = []
    correct = 0
    for item in raw:
        if not isinstance(item, dict):
            continue
        if item.get("is_correct"):
            correct = len(choices)
        choices.append(
            {"id": str(item.get("id") or chr(ord("a") + len(choices))), "text": str(item.get("text") or "")}
        )
    return choices, correct


_PROCEED_EXACT = {
    "good to proceed",
    "no questions",
    "no question",
    "next topic",
    "next",
    "got it",
    "ready",
    "move on",
    "move on anyway",
    "lets continue",
    "continue to next",
    "close",
    "close and move on",
    "done",
    "skip",
    "no final questions",
    "no final questions lets continue",
    "got it ready for the next topic",
}


def _proceed_text(answer: str) -> str:
    text = (answer or "").lower().replace("—", " ").replace("–", " ").replace("'", "")
    text = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text)
    return " ".join(text.split())


_CONTINUE_QUESTION_MARKERS = (
    "ready for the next challenge",
    "move on to the next part",
    "move on to the next block",
    "move on to the next",
    "close and move on",
    "ready to move on",
    "want to move on",
    "like to move on",
    "or move on",
)


def tutor_asked_to_continue(text: str) -> bool:
    """The previous tutor turn asked the learner to continue or to move on."""
    if "?" not in (text or ""):
        return False
    lowered = (text or "").lower()
    return any(marker in lowered for marker in _CONTINUE_QUESTION_MARKERS)


def worked_continue_answer(answer: str) -> bool:
    """Yes, move on, or next part. A bare yes is only the word yes."""
    text = _proceed_text(answer)
    if not text:
        return False
    if text == "yes":
        return True
    words = text.split()
    if len(words) > 12:
        return False
    if any(token in words for token in ("not", "dont", "wrong", "confused")):
        return False
    return text in {"move on", "next part"} or "move on" in text or "next part" in text


def learner_ready_to_proceed(answer: str, flagged: bool) -> bool:
    """True when the learner wants the next topic or the block summary to finish."""
    if flagged:
        return True
    raw = answer or ""
    lowered = raw.lower()
    if "?" in raw or "elaborat" in lowered:
        return False
    text = _proceed_text(raw)
    if not text:
        return False
    if text in _PROCEED_EXACT:
        return True
    words = text.split()
    if len(words) > 14:
        return False
    if words[0] in {"what", "why", "how", "when", "where", "who", "can", "could", "would", "explain", "tell"}:
        return False
    if any(token in words for token in ("not", "wrong", "dont", "confused")):
        return False
    for phrase in (
        "good to proceed",
        "no questions",
        "no question",
        "no final questions",
        "next topic",
        "move on",
        "move on anyway",
        "lets continue",
        "continue to next",
        "close and move on",
        "next part",
        "got it ready for the next topic",
    ):
        if phrase in text:
            return True
    if text in {"ready", "next"} or text.endswith(" ready"):
        return True
    if "got it" in text:
        return True
    return False


_QUESTION_STARTS = {"what", "why", "how", "who", "can", "could", "would", "explain", "tell"}
_CLAUSE_STARTS = {"when", "where"}
_QUESTION_AUXILIARIES = {
    "did",
    "does",
    "do",
    "is",
    "are",
    "was",
    "were",
    "can",
    "could",
    "would",
    "should",
    "will",
    "has",
    "have",
    "had",
}


def _opens_as_question(words: list[str]) -> bool:
    """A question word. 'When the government borrows' is a clause, not a question."""
    if not words:
        return False
    if words[0] in _QUESTION_STARTS:
        return True
    return words[0] in _CLAUSE_STARTS and len(words) > 1 and words[1] in _QUESTION_AUXILIARIES


def learner_asks_question_or_background(answer: str) -> bool:
    """A question or a request for background, not an attempt at the goal."""
    raw = answer or ""
    if not raw.strip() or learner_ready_to_proceed(raw, False):
        return False
    lowered = raw.lower()
    if "?" in raw or "elaborat" in lowered:
        return True
    text = _proceed_text(raw)
    if not text:
        return False
    words = text.split()
    if _opens_as_question(words):
        return True
    return "background" in text or "more context" in text or "some context" in text


def learner_side_question(answer: str, block: dict | None = None, substep: str = "") -> bool:
    """A who/what/where/why question. Not an attempt, a move-on, or a passage reread.

    The topic-goal explain step and explanatory blocks already stay for questions.
    Every other substep uses this to pause without scoring.
    """
    if not learner_asks_question_or_background(answer):
        return False
    if block is not None and proposed_step_answer(block, substep, answer):
        return False
    if block is not None and str(block.get("type") or "").strip() == "passage_ela":
        if learner_asks_for_passage(answer):
            return False
        # Pointing at the span is the citation assist, not a side question.
        if learner_points_at_span(answer, _data(block)):
            return False
    return True


_STOP_EXPLAINING = (
    "dont want to learn more",
    "do not want to learn more",
    "dont want more",
    "no more explanation",
    "stop explaining",
    "enough explanation",
    "thats enough explanation",
    "that is enough",
)


def learner_done_with_explanation(answer: str) -> bool:
    """True when the learner is leaving the opening explanation for the goal question.

    Got it - move on, a typed reply that means move on, and a typed reply that
    means they do not want to learn more all take this path. Tell me more does not.
    A bare yes is handled on the topic-goal explain step only.
    """
    text = _proceed_text(answer)
    if any(phrase in text for phrase in _STOP_EXPLAINING):
        return True
    return learner_ready_to_proceed(answer, False)


def move_on_agreement(answer: str) -> bool:
    """The whole line is agreement to move on. yes, or a short let's move on.

    A real answer is not this. A question that is not that agreement is not this.
    """
    raw = answer or ""
    text = _proceed_text(raw)
    if not text:
        return False
    if text == "yes":
        return "?" not in raw
    if "?" in raw and not _is_proceed_question(text):
        return False
    words = text.split()
    if len(words) > 8:
        return False
    if words[0] in {"what", "why", "how", "when", "where", "who", "can", "could", "would", "explain", "tell"}:
        return False
    if any(token in words for token in ("not", "dont", "wrong", "confused")):
        return False
    return "move on" in text


_DEEPEN_EXACT = {
    "tell me more",
    "explain more",
    "can you explain more",
    "could you explain more",
    "please explain more",
    "keep learning",
    "i want to keep learning",
    "i want to learn more",
}


def passage_elaboration_request(block: dict, answer: str) -> bool:
    """A request for more help with this passage, without a separate question or topic."""
    return block.get("type") == "passage_ela" and _proceed_text(answer) in _DEEPEN_EXACT


def short_passage_example_requested(block: dict, answer: str, length: str, *, opening: bool) -> bool:
    return not opening and length == "bite_sized" and passage_elaboration_request(block, answer)


def passage_example_question_spoken(block: dict, substep: str, reply: str) -> bool:
    """Only expect a practice answer when the tutor actually asked a different question."""
    field = {"central_idea": "central_idea_question", "cite_evidence": "evidence_prompt",
             "craft_or_inference": "analysis_question"}.get(substep)
    authored = _proceed_text(str(_data(block).get(field) or ""))
    spoken, separator, _ = reply.rpartition("?")
    return bool(separator and authored and not _proceed_text(spoken).endswith(authored))


def passage_example_reply(block: dict, substep: str, state: dict, answer: str) -> bool:
    """A reply to the practice question. Direct evidence and new help requests keep their own paths."""
    if block.get("type") != "passage_ela" or state.get("passage_example_substep") != substep:
        return False
    if passage_elaboration_request(block, answer) or learner_asks_for_passage(answer):
        return False
    if learner_side_question(answer, block, substep) and _opens_as_question(_proceed_text(answer).split()):
        return False
    data = _data(block)
    if substep == "cite_evidence":
        return not (learner_points_at_span(answer, data) or any(quote_in_text(q, answer) for q in _passage_quotes(data)))
    # A single shared detail can answer the example without stating the main idea.
    field = "expected_analysis" if substep == "craft_or_inference" else "expected_central_idea"
    expected = str(data.get(field) or "").strip()
    return not (expected and _precise(answer, expected))


def learner_wants_deeper_explanation(answer: str) -> bool:
    """Tell me more, with no question of their own. That still deepens the same topic."""
    raw = answer or ""
    text = _proceed_text(raw)
    if not text:
        return False
    if text in _DEEPEN_EXACT:
        return True
    if "tell me more" in text and "?" not in raw and "what" not in text.split():
        return True
    return False


def learner_asks_clarification(answer: str) -> bool:
    """A learner question on the topic-goal explain step, not another tell-me-more.

    "what's a lemonade cup?", "what is …", and "can you explain what …" are
    clarifications. "Tell me more" with no question is not.
    """
    raw = answer or ""
    if not raw.strip() or learner_done_with_explanation(raw) or learner_wants_deeper_explanation(raw):
        return False
    text = _proceed_text(raw)
    if text.startswith(("what is ", "what are ", "whats ", "what s ")):
        return True
    if "explain what" in text:
        return True
    return learner_asks_question_or_background(raw)


def learner_wants_recap_elaboration(answer: str) -> bool:
    """elaborate, can you elaborate, or tell me more. Those hold a summary check."""
    raw = answer or ""
    text = _proceed_text(raw)
    if not text:
        return False
    if "elaborat" in raw.lower():
        return True
    return text == "tell me more" or text.startswith("tell me more")


def summary_explicit_move_on(answer: str) -> bool:
    """Let's go, move on, next, or yes. These also close an incomplete summary.

    A question mark does not turn "move on?" into another question.
    A real question that only happens to contain one of these words does not close.
    """
    raw = answer or ""
    if "elaborat" in raw.lower():
        return False
    text = _proceed_text(raw)
    if not text:
        return False
    words = text.split()
    if any(token in words for token in ("not", "dont", "wrong", "confused")):
        return False
    if words[0] in {"what", "why", "how", "when", "where", "who", "can", "could", "would", "explain", "tell"}:
        return False
    if text in {"yes", "next"}:
        return True
    if len(words) > 12:
        return False
    if "lets go" in text or "move on" in text:
        return True
    if "next block" in text or "next part" in text or text.startswith("next "):
        return True
    return False


def _is_proceed_question(text: str) -> bool:
    """A question whose point is to go on, such as what's next, move on?, or can we keep going?"""
    if text in {"whats next", "what next", "what is next", "what s next", "yes", "next", "ok", "okay", "done", "ready"}:
        return True
    if text.startswith(("whats next", "what is next", "what next", "what s next")):
        return True
    if "lets go" in text or "move on" in text:
        return True
    if "can we keep going" in text or "can we go on" in text:
        return True
    return text.startswith("next ") or "next block" in text or "next part" in text or "next topic" in text


def summary_content_question(answer: str) -> bool:
    """A question that stays on a passed summary. A local check on the child's text.

    what's next, move on?, let's go, done, ok, can we keep going, and can we go on
    are not content questions. tell me more and elaborate stay, because the summary
    offered more time.
    """
    raw = answer or ""
    if learner_wants_recap_elaboration(raw):
        return True
    text = _proceed_text(raw)
    if not text:
        return False
    if summary_explicit_move_on(raw) or _is_proceed_question(text):
        return False
    if "?" in raw:
        return True
    first = text.split()[0]
    return first in {
        "what",
        "why",
        "how",
        "when",
        "where",
        "who",
        "which",
        "can",
        "could",
        "would",
        "should",
        "is",
        "are",
        "do",
        "does",
        "did",
        "explain",
        "tell",
    }


def summary_needs_learner_question(answer: str, prior_tutor: str) -> bool:
    """The learner wants a final question but has not supplied its content yet."""
    text = _proceed_text(answer.replace("’", "'"))
    if re.fullmatch(
        r"(?:please )?(?:(?:ask me|can you ask me|can i ask|i have|i want to ask) )?"
        r"(?:one more|another|a|one|a final|a last) question(?: please)?",
        text,
    ):
        return True
    if text not in {
        "yes", "yes please", "yeah", "yeah please", "sure", "sure please", "one more", "one more please",
        "im not sure", "im not sure what you mean", "do you mean i ask you",
    }:
        return False
    return _tutor_invited_learner_question(prior_tutor)


def _tutor_invited_learner_question(prior_tutor: str) -> bool:
    # A short answer responds to the tutor's final question. Earlier sentences
    # may mention asking for help, and a Continue-button reminder can follow it.
    before_question, marker, _ = prior_tutor.rpartition("?")
    ending = before_question if marker else prior_tutor.strip().rstrip(".!;")
    prompt = re.split(r"[.!?;]", ending)[-1]
    prompt = _proceed_text(prompt.replace("’", "'"))
    return bool(re.search(
        r"\b(?:have|got) (?:(?:a|any|one|another|last|final|more|other) )*questions?\b"
        r"|\bany (?:(?:more|last|final|other) )?questions?\b"
        r"|\b(?:like|want) to ask\b|\bwhat(?:s| is) your question\b"
        r"|\bask (?:me|(?:you )?(?:one more|another) question)\b",
        prompt,
    ))


_MCQ_CLOSE = re.compile(
    r"\bbefore we (?:finish|wrap up)\b|\bwhat questions? do you have\b"
    r"|^(?:(?:are you )?ready to|shall we|would you like to|do you want to) "
    r"(?:finish|move on|continue|wrap up)\b"
    r"|\bwould you like to (?:learn|try|do) next\b|^how did you like (?:this|the) lesson\b"
    r"|^(?:thats (?:it|all) for today|(?:were|youre) (?:all )?(?:done|finished)|all done)\b"
    r"|^(?:anything else|all set|does (?:that|this) make sense)$"
)
_MCQ_REASON_REQUEST = re.compile(
    r"^(?:please )?(?:explain|tell me|show me|(?:walk|talk) me through|give (?:me )?(?:a|one|your) reason)\b"
)


def mcq_reason_reply(reply: str) -> str:
    """Replace an early wrap-up and keep substantive teaching in the learner's chat."""
    question = "What helped you choose that answer?"
    sentences = [_proceed_text(part.replace("’", "'")) for part in re.split(r"[.!?;]+", reply) if part.strip()]
    if _tutor_invited_learner_question(reply) or any(_MCQ_CLOSE.search(part) for part in sentences):
        return f"That’s right. {question}"
    # A tutor can ask for a reason with an imperative, for example "Tell me why."
    if "?" in reply or any(_MCQ_REASON_REQUEST.match(part) for part in sentences):
        return reply
    # Score a declarative explanation as delivered even when we need to append the question.
    return f"{reply} {question}"


def summary_ready_signal(answer: str) -> bool:
    """Any reply that is not a question closes a passed summary.

    Local check on the child's text. No extra model call. A content question
    stays. done, what's next, ok, let's go, move on, can we keep going, and
    can we go on all close.
    """
    raw = (answer or "").strip()
    if not raw or learner_wants_recap_elaboration(raw):
        return False
    return not summary_content_question(raw)


def summary_further_question(answer: str) -> bool:
    """A further question or an elaborate request on a finished block.

    Model flags do not turn that line into a move-on. Anything that is not
    a question still completes a passed summary. "move on?" is that move-on.
    A content question closes in the summary resolver. Elaborate still stays.
    """
    if summary_ready_signal(answer):
        return False
    if learner_wants_recap_elaboration(answer):
        return True
    return learner_asks_question_or_background(answer)


def summary_closes_after_question(answer: str) -> bool:
    """One further question on the check-in. The reply answers it and closes.

    The check-in was already asked. Elaborate and tell me more are not this
    question. can we keep going and can we go on are move-ons, not this question.
    """
    if learner_wants_recap_elaboration(answer):
        return False
    if summary_ready_signal(answer):
        return False
    return summary_further_question(answer)


def learner_may_complete_explanation_summary(answer: str) -> bool:
    """A non-question closes an explanatory summary. One further question does too.

    Model flags do not turn a move-on into a stay, and they do not keep a
    content question open. "elaborate", "can you please elaborate?", and
    "tell me more" still stay.
    """
    if summary_ready_signal(answer):
        return True
    if summary_closes_after_question(answer):
        return True
    if summary_further_question(answer):
        return False
    return learner_ready_to_proceed(answer, False)


def explanation_on_last_topic(block: dict, state: dict | None) -> bool:
    """True on the last explain_topic of an explanatory walkthrough."""
    if str(block.get("type") or "") != "explanation":
        return False
    stored = state if isinstance(state, dict) else {}
    if str(stored.get("substep") or "explain_topic") != "explain_topic":
        return False
    topics = explanation_topics(block)
    if not topics:
        return False
    return explanation_topic_index(block, stored) >= len(topics) - 1


def last_topic_question_close(block: dict, state: dict | None, answer: str) -> bool:
    """A question on the last topic is answered, then the block closes.

    Local check on the child's text, the same one a passed summary uses.
    Elaborate and tell me more stay on this topic. No extra model call.
    """
    if not explanation_on_last_topic(block, state):
        return False
    raw = answer or ""
    if not raw.strip() or learner_wants_recap_elaboration(raw):
        return False
    return summary_content_question(raw)


def last_topic_closes_block(block: dict, state: dict | None, answer: str) -> bool:
    """The last explanatory topic ends on this reply.

    A non-question closes, the same rule as a passed summary. A question is
    answered and then the block closes. The two-extra-turn cap closes too.
    Elaborate and tell me more stay until one of those is true.
    """
    if not explanation_on_last_topic(block, state):
        return False
    if not explanation_topic_taught(state):
        return False
    if explanation_topic_capped("explain_topic", state):
        return True
    if summary_ready_signal(answer):
        return True
    return last_topic_question_close(block, state, answer)


def _repeats_thesis(answer: str, state: dict | None) -> bool:
    """The line restates the stored thesis and does not take up the probe."""
    stored = state if isinstance(state, dict) else {}
    thesis = str(stored.get("thesis") or "").strip()
    if not thesis:
        return False
    left = " ".join(_words(answer))
    right = " ".join(_words(thesis))
    if not left or not right:
        return False
    if left == right:
        return True
    return _matches(answer, thesis) and len(left.split()) <= len(right.split()) + 2


def _current_counterexample(block: dict, state: dict | None) -> str:
    data = _data(block)
    counters = [str(item).strip() for item in (data.get("counterexamples") or []) if str(item).strip()]
    if not counters:
        return ""
    stored = state if isinstance(state, dict) else {}
    try:
        index = int(stored.get("probe_turns") or 0)
    except (TypeError, ValueError):
        index = 0
    index = min(max(index, 0), len(counters) - 1)
    return counters[index]


def answer_addresses_substep(
    block: dict,
    substep: str,
    answer: str,
    state: dict | None,
    cfg: dict | None,
) -> bool:
    """Literal wording check for this substep.

    resolve_block_turn uses this only as a fallback. A real answer that the
    model passed (substep_passed or the active step's evidence id) does not
    need this overlap.
    """
    btype = str(block.get("type") or "topic_goal").strip()
    data = _data(block)
    bcfg = _bcfg(block, cfg or {})
    stored = state if isinstance(state, dict) else {}
    if btype == "mcq" and substep == "choice":
        choices, correct = mcq_payload(block, stored)
        if not choices:
            return False
        picked = match_mcq_choice_index(answer, choices)
        return picked is not None and picked == correct
    if btype == "mcq" and substep == "awaiting_why":
        explanation = str(data.get("correct_explanation") or "").strip()
        if explanation:
            return _matches(answer, explanation)
        return _substantive(answer, 4)
    if btype == "topic_goal":
        required = str(data.get("acceptance_criteria") or data.get("goal") or "").strip()
        if not required:
            return _substantive(answer)
        strictness = str(bcfg.get("goal_evaluation_strictness") or "conceptual_gist")
        if strictness == "precise_vocabulary":
            return _precise(answer, required)
        if strictness == "applied_transfer":
            return _matches(answer, required) and len((answer or "").split()) >= len(required.split()) + 3
        return _matches(answer, required)
    if btype == "case_study" and substep == "predict":
        lowered = (answer or "").strip().lower()
        if lowered in {"case-a", "case-b"}:
            return True
        return _matches(answer, str(data.get("case_a") or "")) or _matches(answer, str(data.get("case_b") or ""))
    if btype == "case_study" and substep == "contrast_and_rule":
        return _matches(answer, str(data.get("invariant_principle") or ""))
    if btype == "case_study" and substep == "transfer":
        expected = str(data.get("transfer_expected") or data.get("invariant_principle") or "")
        return _matches(answer, expected)
    if btype == "socratic" and substep == "initial_thesis":
        return _substantive(answer)
    if btype == "socratic" and substep == "counterexample_probe":
        if _repeats_thesis(answer, stored):
            return False
        probe = _current_counterexample(block, stored)
        if probe and _matches(answer, probe):
            return True
        return _matches(answer, str(data.get("target_synthesis") or ""))
    if btype == "curiosity":
        minimum = 2 if bool(bcfg.get("require_initial_prediction", True)) else 1
        return _substantive(answer, minimum)
    if btype == "worked_example" and substep == "faded_step":
        steps = data.get("steps") if isinstance(data.get("steps"), list) else []
        index = int(data.get("faded_step_index") or 0)
        step = steps[index] if 0 <= index < len(steps) else ""
        text = step.get("step_text") if isinstance(step, dict) else str(step)
        if not str(text or "").strip():
            return _substantive(answer)
        ok = _matches(answer, str(text))
        if ok and bool(bcfg.get("require_step_self_explanation", True)):
            return _substantive(answer, 4)
        return ok
    if btype == "worked_example" and substep == "solo_solve":
        expected = str(data.get("solo_expected_answer") or "")
        return _matches(answer, expected) if expected else _substantive(answer)
    if btype == "spot_the_flaw":
        flaw = str(data.get("flaw_description") or "")
        corrected = str(data.get("corrected_version") or "")
        found = _matches(answer, flaw) if flaw else _substantive(answer)
        if str(bcfg.get("critique_depth") or "identify_and_correct") == "identify_only":
            return found
        fixed = _matches(answer, corrected) if corrected else found
        return found and fixed
    if btype == "teach_back":
        required = [str(item).strip() for item in (data.get("required_concepts") or []) if str(item).strip()]
        if not required:
            return _substantive(answer)
        hits = sum(1 for item in required if _matches(answer, item))
        if str(bcfg.get("evaluation_strictness") or "") == "all_required_concepts_exact":
            return hits == len(required)
        return hits >= max(1, (len(required) + 1) // 2)
    if btype == "retrieval_check" and substep == "recall":
        fact = str(data.get("expected_fact") or "")
        if not fact:
            return _substantive(answer)
        if bool(bcfg.get("accept_paraphrase", True)):
            return _matches(answer, fact)
        return _strict_fact(answer, fact)
    if btype == "retrieval_check" and substep == "elaborate_why":
        rationale = str(data.get("expected_why_rationale") or "")
        return _matches(answer, rationale) if rationale else _substantive(answer)
    if btype == "explanation":
        return False
    if btype == "passage_ela":
        return _passage_answer_met(data, substep, answer, bcfg)
    return _substantive(answer)


_EVIDENCE_ALIASES = {
    "peer_follow_up": ("peer_follow_up", "follow_up_question"),
    "peer_follow_up_1": ("peer_follow_up_1",),
    "peer_follow_up_2": ("peer_follow_up_2",),
    "initial_explanation": ("initial_explanation",),
    "faded_step": ("faded_step",),
    "solo_solve": ("solo_solve",),
    "summary_check": ("summary_check",),
}


def _block_prefix(block: dict, index: int) -> str:
    return str(block.get("id") or f"blk_{index + 1}").strip()


def evidence_ids_for_substep(block: dict, index: int, substep: str) -> set[str]:
    """Ids the model may return for this substep, including the block prefix."""
    prefix = _block_prefix(block, index)
    ids = {block_evidence_id(block, index, substep), prefix}
    for alias in _EVIDENCE_ALIASES.get(substep, (substep,)):
        if alias and alias not in {"main", "choice", "critique", "explain"}:
            ids.add(f"{prefix}:{alias}")
    return {item for item in ids if item}


def rubric_covers_substep(block: dict, index: int, substep: str, rubric_met: list[str]) -> bool:
    """True when rubric_met names this step, an alias, or the block prefix.

    A teach-back follow-up has its own id. The explanation id does not cover a
    follow-up, and follow-up 1 does not cover follow-up 2.
    """
    if not substep:
        return False
    met = {str(item).strip() for item in rubric_met if str(item).strip()}
    return bool(evidence_ids_for_substep(block, index, substep) & met)


def _minimum_words(block: dict, substep: str, cfg: dict | None) -> int:
    btype = str(block.get("type") or "topic_goal").strip()
    bcfg = _bcfg(block, cfg or {})
    if btype == "topic_goal" and bool(bcfg.get("fragment_self_explanation", True)):
        return 3
    if btype == "worked_example" and substep == "faded_step" and bool(
        bcfg.get("require_step_self_explanation", True)
    ):
        return 4
    return 2


def learner_gave_real_attempt(block: dict, substep: str, answer: str, cfg: dict | None) -> bool:
    """A substantive try. Proceed phrases, bare yes, questions, and give-ups do not count."""
    if learner_ready_to_proceed(answer, False) or _proceed_text(answer) == "yes":
        return False
    if learner_asks_question_or_background(answer) or _gives_up(answer):
        return False
    return _substantive(answer, _minimum_words(block, substep, cfg))


def _gives_up(answer: str) -> bool:
    """A skip or an 'I don't know', not a paraphrase of the step."""
    text = _proceed_text(answer)
    if text in {"i forget", "i forgot", "i cant remember", "i cannot remember"}:
        return True
    return any(
        phrase in text
        for phrase in (
            "i do not know",
            "i dont know",
            "not sure",
            "no idea",
            "idk",
        )
    )


_STORY_CUES = (
    "once upon",
    "yesterday",
    "the other day",
    "when i was",
    "let me tell",
    "i have a story",
    "side story",
    "my dog",
    "my cat",
    "one time",
    "i remember when",
    "story about",
)

def stay_on_course_enabled(cfg: dict | None) -> bool:
    """True unless Stay on course is exploratory. The default setting stays on."""
    over = (cfg or {}).get("overarching") or {}
    mode = over.get("stay_on_course", "brief_answer_then_return")
    if isinstance(mode, bool):
        return mode
    text = str(mode or "brief_answer_then_return").strip().lower()
    return text not in {"exploratory", "no", "false", "off"}


def _collect_anchor_text(value: object, chunks: list[str]) -> None:
    if isinstance(value, str):
        if value.strip():
            chunks.append(value)
        return
    if isinstance(value, list):
        for item in value:
            _collect_anchor_text(item, chunks)
        return
    if isinstance(value, dict):
        for item in value.values():
            _collect_anchor_text(item, chunks)


def _content_word_set(text: str) -> set[str]:
    """Lesson words, plus a trailing s folded off so "want" meets "wants"."""
    words = {word for word in _words(text) if len(word) > 3}
    stems = {word[:-1] for word in words if word.endswith("s") and len(word) > 4}
    return words | stems


def _anchor_words(block: dict) -> set[str]:
    chunks: list[str] = []
    _collect_anchor_text(_data(block), chunks)
    return _content_word_set(" ".join(chunks))


def ancillary_story(answer: str, block: dict) -> bool:
    """A short aside. A reply that touches the goal is an attempt, even when it is wrong."""
    text = _proceed_text(answer)
    if not text or not any(cue in text for cue in _STORY_CUES):
        return False
    anchors = _anchor_words(block)
    have = {word for word in _words(answer) if len(word) > 3}
    if anchors and (have & anchors):
        return False
    return True


def _matches_mcq_choice(block: dict, answer: str, state: dict | None) -> bool:
    """True when the reply picks a choice, including a wrong one."""
    if str(block.get("type") or "") != "mcq":
        return False
    choices, _correct = mcq_payload(block, state if isinstance(state, dict) else {})
    return match_mcq_choice_index(answer, choices) is not None


def _denies_flaw(block: dict, substep: str, answer: str) -> bool:
    """An explicit judgment on the supplied example is a wrong critique, even without topic words."""
    return (
        block.get("type") == "spot_the_flaw"
        and substep == "critique"
        and _proceed_text(answer) in {
            "looks fine", "looks fine to me", "it looks fine", "it looks fine to me",
            "no flaw", "there is no flaw", "nothing is wrong", "nothing wrong",
        }
    )


def _short_off_topic_remark(
    answer: str,
    block: dict,
    substep: str,
    state: dict | None,
    cfg: dict | None,
) -> bool:
    """An aside that does not use the lesson's words, such as "arsenal are great".

    Sharing none of those words means it is not an attempt, at any length.
    A wrong answer that uses the lesson's words still counts.
    """
    words = _proceed_text(answer).split()
    # One word can be a real try. An off-topic line of any longer length is not.
    if len(words) < 2:
        return False
    if _matches_mcq_choice(block, answer, state) or _denies_flaw(block, substep, answer):
        return False
    anchors = _anchor_words(block)
    if not anchors:
        return False
    if _content_word_set(answer) & anchors:
        return False
    return True


_ACK_WORDS = {
    "k",
    "kk",
    "ok",
    "okay",
    "yeah",
    "yep",
    "yup",
    "yea",
    "ya",
    "sure",
    "mhm",
    "mm",
    "uh",
    "um",
    "hmm",
    "thanks",
    "thx",
    "fine",
    "cool",
    "lol",
    "haha",
}

_COMPLAINT_PHRASES = (
    "this is boring",
    "so boring",
    "im bored",
    "i am bored",
    "this sucks",
    "i hate this",
    "i dont care",
    "this is dumb",
    "so dumb",
)

_BOUNDARY_PHRASES = (
    "ignore the lesson",
    "ignore your",
    "tell me a joke",
    "say a joke",
    "forget the lesson",
    "forget your instructions",
    "you dont have to be a tutor",
    "just chat with me",
    "blah blah",
)


def _echoes_tutor(answer: str, prior_tutor: str) -> bool:
    """The line is mostly the tutor's words, not a new try."""
    prior = _proceed_text(prior_tutor)
    if not prior:
        return False
    text = _proceed_text(answer)
    if text.startswith("yes "):
        text = text[4:].strip()
    words = [word for word in text.split() if len(word) > 2]
    if len(words) < 4:
        return False
    tutor_words = set(prior.split())
    hits = sum(1 for word in words if word in tutor_words)
    return hits >= max(4, (len(words) * 4 + 4) // 5)


def learner_non_answer(
    block: dict,
    substep: str,
    answer: str,
    state: dict | None,
    cfg: dict | None,
    *,
    prior_tutor: str = "",
    covered: bool = False,
) -> bool:
    """A line that stays on the step and does not spend a try.

    yes, a one-word k, a complaint, an echo of the tutor, an off-topic line,
    and a boundary probe. idk is a miss. A line that addresses the step is a try.
    A passed summary and a continue question keep their own close.
    """
    raw = answer or ""
    if not raw.strip() or _gives_up(raw):
        return False
    if str(substep or "") == "summary_check":
        return False
    if learner_ready_to_proceed(raw, False) or learner_done_with_explanation(raw):
        return False
    if _matches_mcq_choice(block, raw, state):
        return False
    if answer_addresses_substep(block, substep, raw, state, cfg):
        return False
    if str(block.get("type") or "") == "passage_ela" and learner_points_at_span(raw, _data(block)):
        return False
    text = _proceed_text(raw)
    if not text:
        return False
    if text == "yes":
        if covered or tutor_asked_to_continue(prior_tutor):
            return False
        return True
    if text in _ACK_WORDS:
        return True
    if text in {"boring", "whatever", "dumb", "sucks"} or any(phrase in text for phrase in _COMPLAINT_PHRASES):
        return True
    if any(phrase in text for phrase in _BOUNDARY_PHRASES):
        return True
    if _echoes_tutor(raw, prior_tutor):
        return True
    return _short_off_topic_remark(raw, block, substep, state, cfg)


def _statement_before_question(answer: str) -> bool:
    """True when a question mark is only checking a statement the learner already made."""
    text = _proceed_text(answer)
    for tail in ("is that right", "is that correct", "isnt it", "right", "correct"):
        marker = " " + tail
        if text.endswith(marker):
            text = text[: -len(marker)].strip()
            break
    words = text.split()
    if len(words) < 4 or _opens_as_question(words):
        return False
    return True


_PROPOSAL_FIELDS = {
    ("retrieval_check", "recall"): "expected_fact",
    ("retrieval_check", "elaborate_why"): "expected_why_rationale",
    ("case_study", "transfer"): "transfer_expected",
    ("worked_example", "solo_solve"): "solo_expected_answer",
}


def _proposal_target(block: dict, substep: str) -> str:
    field = _PROPOSAL_FIELDS.get((block.get("type"), substep))
    return str(_data(block).get(field) or "").strip() if field else ""


_MATH_OPERATOR = re.compile(
    r"[×÷*/+=−]|\s-\s|\b(?:plus|minus|times|add(?:ed)?|subtract(?:ed)?|multipl(?:y|ied)|divid(?:e|ed))\b",
    re.I,
)
_ANSWER_CHECK_OPEN = re.compile(r"^(?:is (?:it|that)|(?:would|could) (?:it|that) be)\s+", re.I)
_SOLO_ANSWER_OPEN = re.compile(r"^is the answer\s+", re.I)
_SOLO_TASK_REQUEST = re.compile(
    r"^(?:supposed|expected|meant) to\b|^(?:explained|rephrased|repeated|clarified)\b(?! by\b)"
    r"|\b(?:question|problem|exercise|task) (?:again|as (?:before|last time))\b", re.I,
)
_ANSWER_CHECK_TAG = re.compile(r",?\s+(?:is that (?:right|correct)|isn['’]t it|right|correct)$", re.I)
_FOLLOWUP = re.compile(r"(?:,?\s+and|[.!])\s+(?:could|would|can|who|what|why|how|when|where)\b", re.I)


def proposed_step_answer(block: dict, substep: str, answer: str) -> str | None:
    """Return proposed content, an empty string for a side question, or None for ordinary grading."""
    target = _proposal_target(block, substep)
    if not target or not answer:
        return None
    # A solo solution may show its working even when the question asks only for the result.
    # The recall rule below requires an operation when the learner is asked for the formula.
    solo = block.get("type") == "worked_example" and substep == "solo_solve"
    formula = not solo and _MATH_OPERATOR.search(target)
    if "?" not in answer and not (formula and _MATH_OPERATOR.search(answer)):
        return None
    # Judge the proposed content. A separate question can ask about something else.
    first = _FOLLOWUP.split(answer.partition("?")[0].strip(), maxsplit=1)[0]
    candidate, opened = _ANSWER_CHECK_OPEN.subn("", first)
    if solo and not opened:
        candidate, opened = _SOLO_ANSWER_OPEN.subn("", first)
    candidate, checked = _ANSWER_CHECK_TAG.subn("", candidate)
    words = _words(candidate)
    if not words or _opens_as_question(words) or words[0] in _QUESTION_AUXILIARIES:
        return ""
    if words[0] in {"possible", "okay", "ok"} or re.search(
        r"^true that\b|\b(?:a hint|some help|more context|you want me to)\b", candidate, re.I
    ):
        return ""
    if solo:
        # A question about the task can start with "Is it ...?" too. Look for
        # a proposed term, a quantity or evidence about the solution. A wrong
        # one-word label still deserves a try even if it shares nothing with the key.
        if _SOLO_TASK_REQUEST.search(candidate):
            return ""
        short_label = opened and re.fullmatch(r"(?:an? )?[\w-]+", candidate, re.I)
        anchors = _content_word_set(target) - _FILLER_ANCHORS
        numerical = any(c.isdigit() for c in target) and re.fullmatch(
            r"[$£€]?[-+]?\d+(?:[.,/]\d+)*\s*%?(?:\s+[a-z]+){0,2}", candidate, re.I
        )
        if short_label or numerical or anchors.intersection(_content_word_set(candidate)) or words == _words(target):
            return candidate
        return ""
    # A declarative statement checked with "..., right?" may paraphrase every word in the key.
    if checked and _statement_before_question(first):
        return candidate
    # A standalone name, abbreviation or number may express the whole proposed fact.
    # Its meaning still needs the grader (e.g. "CO2" for "carbon dioxide").
    if opened and len(words) == 1 and (candidate[:1].isupper() or any(c.isdigit() for c in candidate)):
        return candidate
    # Mentioning the subject of a formula does not propose a calculation.
    if formula:
        return candidate if _MATH_OPERATOR.search(candidate) else ""
    # A paraphrase can share no words with the key. Let the grader evaluate a
    # stated answer or an explicit proposal rather than requiring a vocabulary match.
    if opened or _statement_before_question(first):
        return candidate
    # Short terms, units and numbers can be meaningful parts of a proposal.
    anchors = {w for w in _words(target) if (len(w) >= 3 or w.isdigit()) and w not in _FILLER_ANCHORS}
    anchors.difference_update({"the", "and", "for", "are", "was", "its", "has", "but"})
    return candidate.strip() if anchors.intersection(words) else ""


def answer_grades_with_question_mark(
    block: dict,
    index: int,
    substep: str,
    answer: str,
    state: dict | None,
    cfg: dict | None,
    *,
    substep_passed: bool,
    rubric_met: list[str],
) -> bool:
    """Grade a line that answers the step, question mark included.

    A real question, one the step check and the model's pass flag both miss, stays unscored.
    """
    raw = answer or ""
    if not raw.strip() or _gives_up(raw) or not learner_asks_question_or_background(raw):
        return False
    # "who is Pompey?" and "why did Caesar cross?" stay. "..., right?" does not.
    if _opens_as_question(_proceed_text(raw).split()) and not _statement_before_question(raw):
        return False
    if answer_addresses_substep(block, substep, raw, state, cfg):
        return True
    if not _statement_before_question(raw):
        return False
    if substep_passed:
        return True
    return rubric_covers_substep(block, index, substep, rubric_met)


def unscored_side_request(
    block: dict,
    substep: str,
    answer: str,
    state: dict | None,
    cfg: dict | None,
) -> bool:
    """A question, a short off-topic remark, "tell me", or a side story.

    Not a goal attempt and not a move-on. A question counts even when it shares
    the lesson's words and even without a question mark. A wrong try at the goal
    stays an attempt. Tell me more, and an explicit move-on, keep today's path.
    Safety is decided before this loop runs.
    """
    raw = answer or ""
    if not raw.strip():
        return False
    # A passed summary's move-on, and its one further question, are not "ask the goal again."
    if str(substep or "") == "summary_check" and (
        summary_ready_signal(raw) or summary_closes_after_question(raw)
    ):
        return False
    if learner_ready_to_proceed(raw, False) or learner_done_with_explanation(raw):
        return False
    if learner_wants_deeper_explanation(raw):
        return False
    if str(block.get("type") or "") == "passage_ela":
        from app.kc_blocks import learner_asks_for_passage

        if learner_asks_for_passage(raw):
            return False
        if learner_points_at_span(raw, _data(block)):
            return False
    # Before the goal-overlap check. "What is a computer?" is still a question.
    if learner_asks_question_or_background(raw):
        return learner_side_question(raw, block, substep)
    if _gives_up(raw) or proposed_step_answer(block, substep, raw):
        return False
    if answer_addresses_substep(block, substep, raw, state, cfg):
        return False
    if "tell me" in _proceed_text(raw):
        return True
    if ancillary_story(raw, block):
        return True
    return _short_off_topic_remark(raw, block, substep, state, cfg)


def unanswered_side_turn(
    block: dict,
    substep: str,
    answer: str,
    state: dict | None,
    cfg: dict | None,
) -> bool:
    """One check for the opening explanation and the later steps.

    A question, with or without a question mark, and a short off-topic remark
    are unanswered side turns. On the opening explanation, "Tell me more" with
    no side topic still deepens. A real attempt and an explicit move-on do not.
    """
    raw = answer or ""
    if str(substep or "") == "summary_check" and (
        summary_ready_signal(raw) or summary_closes_after_question(raw)
    ):
        return False
    if str(substep or "") == "explain" and learner_wants_deeper_explanation(raw):
        return False
    return learner_side_question(raw, block, substep) or unscored_side_request(
        block,
        substep,
        raw,
        state,
        cfg,
    )


EXPLAIN_EXTRA_TURN_CAP = 2

# Words a goal sentence carries that do not show a reply is about the topic.
_FILLER_ANCHORS = {
    "about",
    "also",
    "because",
    "been",
    "does",
    "each",
    "explain",
    "from",
    "have",
    "into",
    "more",
    "most",
    "some",
    "than",
    "that",
    "their",
    "them",
    "then",
    "there",
    "they",
    "this",
    "very",
    "were",
    "what",
    "when",
    "where",
    "which",
    "will",
    "with",
    "your",
}


def explain_extra_turns(state: dict | None) -> int:
    """Side remarks and Tell me more turns already spent on this explanation."""
    stored = state if isinstance(state, dict) else {}
    return int(stored.get("elaboration_turns") or 0) + int(stored.get("side_turns") or 0)


def explanation_topic_capped(substep: str, state: dict | None) -> bool:
    """An explanatory topic has used its two extra turns, so the tutor moves on."""
    stored = state if isinstance(state, dict) else {}
    return (
        str(substep or "") == "explain_topic"
        and int(stored.get("elaboration_turns") or 0) >= EXPLAIN_EXTRA_TURN_CAP
    )


def _explanation_point_words(block: dict, state: dict | None) -> set[str]:
    topics = explanation_topics(block)
    if not topics:
        return set()
    topic = topics[explanation_topic_index(block, state)]
    text = " ".join((topic["title"], topic["explanation"], topic["key_points"]))
    return {word for word in _words(text) if len(word) > 3 and word not in _FILLER_ANCHORS}


def _reply_content_words(answer: str) -> list[str]:
    return [word for word in _words(answer) if len(word) > 3 and word not in _FILLER_ANCHORS]


def explanation_topic_taught(state: dict | None) -> bool:
    """True once this topic's body has been spoken.

    A missing mark means the topic is already open, including the block opening.
    An explicit false mark means the topic was only named.
    """
    stored = state if isinstance(state, dict) else {}
    if "topic_taught" not in stored:
        return True
    return bool(stored.get("topic_taught"))


def explanation_restates_topic(block: dict, state: dict | None, answer: str) -> bool:
    """The reply already says this explanatory topic's point, so the lesson moves on.

    A question, a side story, and Tell me more do not. This is a local word check.
    A topic that was only named has not been restated.
    """
    if str(block.get("type") or "") != "explanation":
        return False
    if not explanation_topic_taught(state):
        return False
    raw = answer or ""
    if not raw.strip():
        return False
    stored = state if isinstance(state, dict) else {}
    if str(stored.get("substep") or "explain_topic") == "summary_check":
        return False
    if (
        learner_asks_question_or_background(raw)
        or learner_wants_deeper_explanation(raw)
        or learner_wants_recap_elaboration(raw)
        or learner_ready_to_proceed(raw, False)
        or ancillary_story(raw, block)
    ):
        return False
    words = _reply_content_words(raw)
    point = _explanation_point_words(block, stored)
    if len(words) < 3 or not point:
        return False
    hits = [word for word in words if word in point]
    return len(hits) >= 2 and len(hits) * 2 >= len(words)


def explanation_move_on_reply(block: dict, state: dict | None, answer: str) -> bool:
    """This reply advances an explanatory topic. The spoken reply stays short.

    A restatement, a ready line, a proceed question, or the two-extra-turn cap.
    Not a content question, and not the last topic (that close is its own rule).
    """
    if str(block.get("type") or "") != "explanation":
        return False
    stored = state if isinstance(state, dict) else {}
    if not explanation_topic_taught(stored):
        return False
    if str(stored.get("substep") or "explain_topic") == "summary_check":
        return False
    if explanation_on_last_topic(block, stored):
        return False
    if explanation_topic_capped("explain_topic", stored):
        return True
    raw = answer or ""
    if not raw.strip():
        return False
    if explanation_side_remark(block, raw, stored, None):
        return False
    if learner_wants_recap_elaboration(raw) or learner_wants_deeper_explanation(raw):
        return False
    if explanation_restates_topic(block, stored, raw):
        return True
    if learner_ready_to_proceed(raw, False):
        return True
    return _is_proceed_question(_proceed_text(raw))


def move_on_before_topic_taught(block: dict, state: dict | None, answer: str) -> bool:
    """A move-on while this topic was only named. The reply teaches it first."""
    if explanation_topic_taught(state):
        return False
    stored = state if isinstance(state, dict) else {}
    if str(stored.get("substep") or "explain_topic") != "explain_topic":
        return False
    raw = answer or ""
    if not raw.strip():
        return False
    if learner_wants_deeper_explanation(raw) or learner_wants_recap_elaboration(raw):
        return False
    if explanation_side_remark(block, raw, stored, None):
        return False
    text = _proceed_text(raw)
    if learner_asks_question_or_background(raw) and not _is_proceed_question(text):
        return False
    if explanation_topic_capped("explain_topic", stored):
        return True
    if learner_ready_to_proceed(raw, False) or _is_proceed_question(text):
        return True
    return explanation_on_last_topic(block, stored) and summary_ready_signal(raw)


def explanation_side_remark(
    block: dict,
    answer: str,
    state: dict | None,
    cfg: dict | None,
) -> bool:
    """A short explanatory turn: an aside, or a question on a topic that is not finished.

    The reply is one or two sentences, then one line back. A restatement moves on instead.
    The last topic and the two-extra-turn cap use their own closes.
    """
    if str(block.get("type") or "") != "explanation":
        return False
    raw = answer or ""
    if not raw.strip():
        return False
    stored = state if isinstance(state, dict) else {}
    if str(stored.get("substep") or "") == "summary_check":
        return False
    # The two-extra-turn cap moves on. A question there is answered in the cap line.
    if explanation_topic_capped(str(stored.get("substep") or "explain_topic"), stored):
        return False
    if (
        learner_ready_to_proceed(raw, False)
        or learner_wants_deeper_explanation(raw)
        or learner_done_with_explanation(raw)
        or _is_proceed_question(_proceed_text(raw))
        or explanation_restates_topic(block, stored, raw)
    ):
        return False
    # "I get it" and "let's go" are ready signals. The model flag decides whether they move.
    if _proceed_text(raw) in {"ok", "okay", "i get it", "lets go"}:
        return False
    # A real question on a topic that is not finished. The last topic has its own close.
    # Elaborate and tell me more stay on the longer path. One or two sentences, then one line back.
    if (
        not explanation_on_last_topic(block, stored)
        and learner_asks_question_or_background(raw)
        and not learner_wants_recap_elaboration(raw)
    ):
        return True
    point = _explanation_point_words(block, stored)
    overlap = bool(point and set(_reply_content_words(raw)) & point)
    if learner_asks_question_or_background(raw) and not overlap:
        return True
    if ancillary_story(raw, block):
        return True
    return _short_off_topic_remark(raw, block, "explain_topic", stored, cfg)


def answers_during_explanation(
    block: dict,
    answer: str,
    state: dict | None,
    cfg: dict | None,
) -> bool:
    """An on-topic try at the goal, typed before the goal question was asked.

    A question, a move-on, Tell me more, a give-up, a side story, and a short
    remark that shares none of the lesson's words are not a try.
    """
    raw = answer or ""
    if not raw.strip():
        return False
    if learner_done_with_explanation(raw) or learner_wants_deeper_explanation(raw):
        return False
    if not learner_gave_real_attempt(block, "main", raw, cfg):
        return False
    if unscored_side_request(block, "explain", raw, state, cfg):
        return False
    if answer_addresses_substep(block, "main", raw, state, cfg):
        return True
    anchors = _anchor_words(block) - _FILLER_ANCHORS
    have = {word for word in _words(raw) if len(word) > 3}
    return bool(anchors & have)


def explain_step_turn(
    block: dict,
    answer: str,
    state: dict | None,
    cfg: dict | None,
) -> str:
    """What the opening explanation does with this message. The prompt and the loop both read it.

    ask: Got it - move on, or a typed move-on. The goal question opens.
    attempt: an on-topic answer. The goal question opens and the answer is scored as a try.
    cap: two extra turns are already spent. The tutor asks the goal question itself.
    aside, clarify, and deepen stay on the explanation, unless the model's
    decision says the learner is ready.
    """
    raw = answer or ""
    side = stay_on_course_enabled(cfg) and unanswered_side_turn(block, "explain", raw, state, cfg)
    clarifying = learner_asks_clarification(raw)
    bare_yes = _proceed_text(raw) == "yes" and "?" not in raw
    if not side:
        if (learner_done_with_explanation(raw) or bare_yes) and not clarifying:
            return "ask"
        if answers_during_explanation(block, raw, state, cfg):
            return "attempt"
    if explain_extra_turns(state) >= EXPLAIN_EXTRA_TURN_CAP:
        return "cap"
    if side:
        return "aside"
    if clarifying:
        return "clarify"
    return "deepen"


def model_ready_counts(kind: str, answer: str) -> bool:
    """The model's ready flag is read only on a turn that would otherwise stay. Tell me more always deepens."""
    return kind in {"aside", "clarify", "deepen"} and not learner_wants_deeper_explanation(answer)


def model_accepts_substep(
    block: dict,
    index: int,
    substep: str,
    answer: str,
    cfg: dict | None,
    *,
    substep_passed: bool,
    rubric_met: list[str],
) -> bool:
    """Trust the model on a real answer. Literal overlap is not required.

    passage_ela stays on its own check. A help, skip, or too-short reply does not pass.
    """
    if str(block.get("type") or "").strip() == "passage_ela" or _denies_flaw(block, substep, answer):
        return False
    if not learner_gave_real_attempt(block, substep, answer, cfg):
        return False
    if substep_passed:
        return True
    return rubric_covers_substep(block, index, substep, rubric_met)


def _central_beyond_detail(answer: str, central: str, distractor: str) -> bool:
    """A minor detail that also sits inside the central idea does not pass on its own."""
    if not central:
        return _substantive(answer)
    if not _matches(answer, central):
        return False
    if not distractor or not _matches(answer, distractor):
        return True
    extra = [word for word in _words(central) if len(word) > 3 and word not in set(_words(distractor))]
    if not extra:
        return True
    have = set(_words(answer))
    hits = sum(1 for word in extra if word in have)
    return hits >= max(1, (len(extra) + 1) // 2)


def _passage_quotes(data: dict) -> list[str]:
    raw = data.get("verbatim_evidence_quotes")
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item or "").strip()]


def learner_points_at_span(answer: str, data: dict) -> bool:
    """The learner points at where the evidence is, without quoting it.

    A reread is not this. A required verbatim quote is not this.
    """
    if learner_asks_for_passage(answer):
        return False
    quotes = _passage_quotes(data)
    if any(quote_in_text(quote, answer) for quote in quotes):
        return False
    text = _proceed_text(answer)
    if not text:
        return False
    cues = (
        "paragraph",
        "that sentence",
        "this sentence",
        "that part",
        "this part",
        "the span",
        "those lines",
        "that line",
        "this line",
    )
    return any(cue in text for cue in cues)


def _contextual_citation_met(data: dict, answer: str, bcfg: dict, passed: bool) -> bool:
    """Wording can establish the passage; the grader checks the speaker and meaning."""
    if not passed:
        return False
    quoted = re.findall(r"""["“]([^"”]+)["”]|(?:^|\s)[‘'](.+?)[’'](?=\s|[.,!?]|$)""", answer)
    fragments = [double or single for double, single in quoted]
    mode = bcfg.get("passage_ela_evidence_mode", "quote_or_close_paraphrase")
    if mode == "paragraph_reference":
        return _passage_answer_met(data, "cite_evidence", answer, bcfg)
    if fragments:
        # Learners may omit the edition's punctuation when typing a quoted line.
        passage = " ".join(_words(str(data.get("passage_text") or "")))
        return any(quote_in_text(" ".join(_words(line)), passage) for line in fragments)
    if mode == "exact_quote_required":
        # Without quote marks an authored quotation can still identify the exact span.
        return any(quote_in_text(quote, answer) for quote in _passage_quotes(data))
    return bool(answer.strip())


def _passage_answer_met(data: dict, substep: str, answer: str, bcfg: dict) -> bool:
    if substep == "cite_evidence":
        quotes = _passage_quotes(data)
        mode = str(bcfg.get("passage_ela_evidence_mode") or "quote_or_close_paraphrase")
        if mode == "exact_quote_required":
            return any(quote_in_text(quote, answer) for quote in quotes)
        if mode == "paragraph_reference":
            text = _proceed_text(answer)
            numbered = "paragraph" in text and any(ch.isdigit() for ch in (answer or ""))
            grounded = any(_matches(answer, quote) for quote in quotes) or _substantive(answer, 6)
            return numbered and grounded
        if any(quote_in_text(quote, answer) or _matches(answer, quote) for quote in quotes):
            return True
        return _matches(answer, str(data.get("expected_central_idea") or ""))
    if substep == "craft_or_inference":
        expected = str(data.get("expected_analysis") or "").strip()
        return _matches(answer, expected) if expected else _substantive(answer, 4)
    return _central_beyond_detail(
        answer,
        str(data.get("expected_central_idea") or "").strip(),
        str(data.get("distractor_detail") or "").strip(),
    )


def _block_title(block: dict, step_index: int) -> str:
    btype = str(block.get("type") or "topic_goal").strip()
    data = block.get("data") if isinstance(block.get("data"), dict) else {}
    if btype == "topic_goal":
        return str(data.get("topic") or f"Block {step_index + 1}").strip()
    if btype == "mcq":
        return str(data.get("question_stem") or data.get("target_skill") or f"Block {step_index + 1}").strip()
    if btype == "case_study":
        return str(data.get("invariant_principle") or f"Block {step_index + 1}").strip()
    if btype == "socratic":
        return str(data.get("central_dilemma") or f"Block {step_index + 1}").strip()
    if btype == "curiosity":
        return str(data.get("phenomenon_hook") or f"Block {step_index + 1}").strip()
    if btype == "worked_example":
        return str(data.get("problem_statement") or f"Block {step_index + 1}").strip()
    if btype == "spot_the_flaw":
        return str(data.get("flaw_description") or f"Block {step_index + 1}").strip()
    if btype == "teach_back":
        return str(data.get("peer_persona_prompt") or f"Block {step_index + 1}").strip()
    if btype == "retrieval_check":
        return str(data.get("recall_prompt") or f"Block {step_index + 1}").strip()
    if btype == "passage_ela":
        return str(data.get("passage_title") or f"Block {step_index + 1}").strip()
    if btype == "explanation":
        title = str(data.get("block_title") or "").strip()
        if title:
            return title
        topics = data.get("topics") if isinstance(data.get("topics"), list) else []
        if topics and isinstance(topics[0], dict):
            topic_title = str(topics[0].get("title") or "").strip()
            if topic_title:
                return topic_title
    return f"Block {step_index + 1}"


def _explanation_stay(
    *,
    state: dict,
    index: int,
    bid: str,
    results: list[dict],
    met: list[str],
    reveals: int,
    move_attempts: int,
    enrichment_turns: int,
) -> BlockResolution:
    return BlockResolution(
        decision="stay",
        hint_tier="nudge",
        move_attempts=move_attempts,
        reveals=reveals,
        enrichment_turns=enrichment_turns,
        rubric_met=met,
        misconception="",
        next_step=index,
        next_block_id=bid,
        next_block_state=state,
        block_results=results,
        mark_known=False,
        mark_fragile=False,
        redirect=False,
        unit_complete=False,
        advance_block=False,
        passed=False,
    )


def _resolve_explanation_turn(
    *,
    answer: str,
    substep_passed: bool,
    block_complete: bool,
    block: dict,
    blocks: list[dict],
    index: int,
    bid: str,
    state: dict,
    substep: str,
    results: list[dict],
    met: list[str],
    reveals: int,
    move_attempts: int,
    cfg: dict,
    strong_text: str,
    work_text: str,
    enrichment_turns: int = 0,
    learner_ready: bool = False,
) -> BlockResolution:
    """Walk topics, then the summary. Questions stay. Ready moves on. Never quizzes.

    A topic allows two extra turns. The next reply moves to the next topic or the summary.
    """
    topics = explanation_topics(block)
    topic_index = explanation_topic_index(block, state)
    if substep not in {"explain_topic", "summary_check"}:
        substep = "explain_topic"
    state["substep"] = substep
    state["topic_index"] = topic_index
    # Older active walkthroughs counted changing topics as attempts. They only record participation.
    state.pop("block_attempts", None)
    on_last = substep == "explain_topic" and bool(topics) and topic_index >= len(topics) - 1
    if move_on_before_topic_taught(block, state, answer):
        # The topic was only named. This reply teaches it. The index does not move.
        state["topic_taught"] = True
        return _explanation_stay(
            state=state,
            index=index,
            bid=bid,
            results=results,
            met=met,
            reveals=reveals,
            move_attempts=move_attempts,
            enrichment_turns=enrichment_turns,
        )
    if substep == "summary_check":
        # The model cannot close this check by setting the flags. A further
        # question stays. A reply that is not a question completes the block.
        ready = learner_may_complete_explanation_summary(answer)
    elif on_last and last_topic_closes_block(block, state, answer):
        # One agreement on the last topic is enough. Do not open a summary
        # that teaches the block again and asks whether to move on.
        ready = True
    elif on_last:
        ready = False
    elif explanation_side_remark(block, answer, state, cfg):
        # This line is a side remark. A pass flag about the previous line does not score it.
        ready = False
    else:
        flagged = bool(substep_passed) or bool(block_complete) or bool(learner_ready)
        # A reply that already restates this topic moves on. The model does not
        # have to flag it, and the topic is not taught again.
        ready = (
            learner_ready_to_proceed(answer, flagged)
            or explanation_topic_capped(substep, state)
            or explanation_restates_topic(block, state, answer)
        )
    if not ready:
        state["elaboration_turns"] = int(state.get("elaboration_turns") or 0) + 1
        return _explanation_stay(
            state=state,
            index=index,
            bid=bid,
            results=results,
            met=met,
            reveals=reveals,
            move_attempts=move_attempts,
            enrichment_turns=enrichment_turns,
        )
    state["elaboration_turns"] = 0
    if substep == "explain_topic" and topics and topic_index < len(topics) - 1:
        state["topic_index"] = topic_index + 1
        state["substep"] = "explain_topic"
        # This reply teaches the topic it opens.
        state["topic_taught"] = True
        return _explanation_stay(
            state=state,
            index=index,
            bid=bid,
            results=results,
            met=met,
            reveals=reveals,
            move_attempts=0,
            enrichment_turns=enrichment_turns,
        )
    title = _block_title(block, index)
    ev_id = block_evidence_id(block, index, "summary_check")
    if ev_id not in met:
        met.append(ev_id)
    results.append(
        {
            "id": bid,
            "block_id": bid,
            "block_type": "explanation",
            "title": title,
            "outcome": "engaged",
            "attempts": 0,
            "strong": strong_text or title,
            "work_on": work_text,
            "summary": "Completed the walkthrough.",
        }
    )
    return _advance_or_close_component(
        blocks=blocks,
        index=index,
        results=results,
        met=met,
        reveals=reveals,
        cfg=cfg,
    )


def _unscored_stay(
    *,
    hint: str,
    move_attempts: int,
    reveals: int,
    enrichment_turns: int,
    rubric: list[str],
    index: int,
    bid: str,
    state: dict,
    results: list[dict],
) -> BlockResolution:
    """Stay on this substep. The reply was a question, so the attempt count does not move."""
    return BlockResolution(
        decision="stay",
        hint_tier=hint if hint in HINTS else "nudge",
        move_attempts=move_attempts,
        reveals=reveals,
        enrichment_turns=enrichment_turns,
        rubric_met=rubric,
        misconception="",
        next_step=index,
        next_block_id=bid,
        next_block_state=state,
        block_results=results,
        mark_known=False,
        mark_fragile=False,
        redirect=False,
        unit_complete=False,
        advance_block=False,
        passed=False,
    )


def reply_is_unreadable(reply: str) -> bool:
    """An empty reply, or one that is only dots, is not something the child can read.

    Empty text, whitespace, invisible characters, and a dots-only line are the
    same. The child hears the fixed line, and the try is not counted.
    """
    import unicodedata

    visible = [
        ch
        for ch in (reply or "")
        if not ch.isspace() and unicodedata.category(ch) not in {"Cf", "Cc"}
    ]
    text = "".join(visible)
    if not text:
        return True
    compact = text.replace(".", "").replace("…", "").replace("·", "").replace("。", "")
    return not compact


def hold_for_blank_reply(
    *,
    blocks: list[dict],
    step: int,
    active_block_state: dict,
    block_results: list[dict],
    move_attempts: int,
    hint_tier: str,
    reveals: int,
    enrichment_turns: int,
    rubric_met: list[str],
) -> BlockResolution:
    """A blank model reply stays. It does not count a try and does not move the topic.

    The child hears a fixed line. This does not call the model again.
    """
    index = min(max(int(step or 0), 0), max(len(blocks) - 1, 0))
    block = blocks[index] if blocks else {}
    bid = str(block.get("id") or f"blk_{index + 1}").strip()
    state = dict(active_block_state or {})
    tier = hint_tier if hint_tier in HINTS else "nudge"
    return BlockResolution(
        decision="stay",
        hint_tier=tier,
        move_attempts=int(move_attempts or 0),
        reveals=int(reveals or 0),
        enrichment_turns=int(enrichment_turns or 0),
        rubric_met=_clean_ids(list(rubric_met or [])),
        misconception="",
        next_step=index,
        next_block_id=bid or None,
        next_block_state=state,
        block_results=[dict(row) for row in (block_results or []) if isinstance(row, dict)],
        mark_known=False,
        mark_fragile=False,
        redirect=False,
        unit_complete=False,
        advance_block=False,
        passed=False,
    )


def resolve_block_turn(
    *,
    decision: str,
    substep_passed: bool,
    block_complete: bool,
    rubric_met: list[str],
    stored_rubric: list[str],
    matched_wrong: str,
    blocks: list[dict],
    step: int,
    active_block_state: dict,
    block_results: list[dict],
    move_attempts: int,
    hint_tier: str,
    reveals: int,
    enrichment_turns: int,
    cfg: dict,
    goal: KcGoal | None,
    last_misconception: str,
    answer: str,
    fragment: bool = False,
    strong: str = "",
    work_on: str = "",
    prior_tutor: str = "",
    learner_ready: bool = False,
) -> BlockResolution:
    tier = hint_tier if hint_tier in HINTS else "nudge"
    fresh = _clean_ids(list(rubric_met))
    met = _clean_ids([*stored_rubric, *fresh])
    index = min(max(int(step or 0), 0), len(blocks) - 1)
    block = blocks[index]
    btype = str(block.get("type") or "topic_goal").strip()
    bid = str(block.get("id") or f"blk_{index + 1}").strip()
    data = block.get("data") if isinstance(block.get("data"), dict) else {}
    bcfg = ((cfg.get("blocks") or {}).get(btype)) or {}
    over = cfg.get("overarching") or {}
    misc_policy = str(over.get("misconception_policy") or "explain_and_retry_once")

    state = dict(active_block_state or {})
    substeps = substeps_for_block(block, cfg)
    substep = str(state.get("substep") or (substeps[0] if substeps else "main"))
    if substep not in substeps and not (btype == "mcq" and substep == "awaiting_why"):
        substep = substeps[0] if substeps else "main"
    dialogue_turns = int(state.get("dialogue_turns") or 0) + 1
    state["dialogue_turns"] = dialogue_turns
    state["substep"] = substep
    example_reply = passage_example_reply(block, substep, state, answer)
    state.pop("passage_example_substep", None)
    if substep == "summary_check" and summary_needs_learner_question(answer, prior_tutor):
        return _unscored_stay(
            hint=tier, move_attempts=move_attempts, reveals=reveals, enrichment_turns=enrichment_turns,
            rubric=_clean_ids(list(stored_rubric)), index=index, bid=bid, state=state,
            results=[dict(row) for row in block_results if isinstance(row, dict)],
        )
    if (
        btype == "worked_example"
        and substep == "faded_step"
        and "solo_solve" in substeps
        and bool(state.get("revealed_substep"))
    ):
        # The faded answer was given on an earlier turn. This reply asks the solo problem.
        state["faded_answer_given"] = True
        state["revealed_substep"] = False
        state["substep"] = "solo_solve"
        held = [dict(row) for row in (block_results or []) if isinstance(row, dict)]
        return _unscored_stay(
            hint="nudge",
            move_attempts=0,
            reveals=reveals,
            enrichment_turns=enrichment_turns,
            rubric=met,
            index=index,
            bid=bid,
            state=state,
            results=held,
        )
    if (
        btype == "worked_example"
        and substep == "faded_step"
        and "solo_solve" in substeps
        and rubric_covers_substep(block, index, "faded_step", _clean_ids(list(stored_rubric)))
    ):
        # The faded step already passed. Grade this reply against the solo problem.
        substep = "solo_solve"
        state["substep"] = substep

    # A giveaway is sticky. A later correct answer does not record the block as passed.
    # A reveal the loop already counted is not counted again when that answer arrives.
    already_revealed = bool(state.get("revealed_substep") or state.get("recall_revealed"))
    if tutor_gave_away_answer(block, state, substep, prior_tutor):
        state["answer_given_away"] = True
        if already_revealed:
            state["giveaway_counted"] = True

    results = [dict(r) for r in (block_results or []) if isinstance(r, dict)]
    if btype == "explanation":
        return _resolve_explanation_turn(
            answer=answer,
            substep_passed=substep_passed,
            block_complete=block_complete,
            block=block,
            blocks=blocks,
            index=index,
            bid=bid,
            state=state,
            substep=substep,
            results=results,
            met=met,
            reveals=reveals,
            move_attempts=move_attempts,
            cfg=cfg,
            strong_text=(strong or "").strip(),
            work_text=(work_on or "").strip(),
            enrichment_turns=enrichment_turns,
            learner_ready=learner_ready,
        )
    early_answer = False
    if btype == "topic_goal" and substep == "explain":
        kind = explain_step_turn(block, answer, state, cfg)
        ready = bool(learner_ready) and model_ready_counts(kind, answer)
        stored_only = _clean_ids(list(stored_rubric))

        def explain_result(rubric: list[str]) -> BlockResolution:
            return BlockResolution(
                decision="stay",
                hint_tier="nudge",
                move_attempts=0,
                reveals=reveals,
                enrichment_turns=enrichment_turns,
                rubric_met=rubric,
                misconception="",
                next_step=index,
                next_block_id=bid,
                next_block_state=state,
                block_results=results,
                mark_known=False,
                mark_fragile=False,
                redirect=False,
                unit_complete=False,
                advance_block=False,
                passed=False,
            )

        if kind in {"ask", "attempt", "cap"} or ready:
            # The goal question opens. Block order does not change, and the goal still has to be passed.
            state["substep"] = "main"
            state["elaboration_turns"] = 0
            state["side_turns"] = 0
            # A short reply during the explanation is not the goal answer.
            state["fragment_prompted"] = True
            if kind == "attempt":
                # The answer came before the question. It is scored below as the first try.
                early_answer = True
                substep = "main"
                move_attempts = 0
                tier = "nudge"
            elif kind == "ask":
                return explain_result(met)
            else:
                # The ready flag and the cap score nothing.
                return explain_result(stored_only)
        elif kind == "aside":
            # A question or a short aside is answered. It is not a deeper lesson and is not a score.
            state["side_turns"] = int(state.get("side_turns") or 0) + 1
            return _unscored_stay(
                hint=tier,
                move_attempts=move_attempts,
                reveals=reveals,
                enrichment_turns=enrichment_turns,
                rubric=stored_only,
                index=index,
                bid=bid,
                state=state,
                results=results,
            )
        else:
            # Tell me more deepens this explanation. The goal question waits.
            state["elaboration_turns"] = int(state.get("elaboration_turns") or 0) + 1
            return explain_result(met)
    # Same side-turn check on later steps. An early answer was already checked above.
    # A question mark does not hide a line that answers the step. Check that, and the
    # model's pass flag, before the unscored stay. A real question still stays.
    proposal = proposed_step_answer(block, substep, answer)
    grade_attempt = bool(proposal) if proposal is not None else answer_grades_with_question_mark(
        block,
        index,
        substep,
        answer,
        state,
        cfg,
        substep_passed=bool(substep_passed),
        rubric_met=fresh,
    )
    gave_up = _gives_up(answer)
    covered_step = rubric_covers_substep(block, index, substep, met)
    side_turn = (
        not early_answer
        and not gave_up
        and not grade_attempt
        and stay_on_course_enabled(cfg)
        and unanswered_side_turn(block, substep, answer, state, cfg)
    )
    # yes, k, a complaint, an echo, an off-topic line, or a boundary probe.
    # Same step, same count. idk is not one of these.
    non_answer = (
        not early_answer
        and not gave_up
        and not grade_attempt
        and stay_on_course_enabled(cfg)
        and learner_non_answer(
            block,
            substep,
            answer,
            state,
            cfg,
            prior_tutor=prior_tutor,
            covered=covered_step,
        )
    )
    # The model already scored this line. An off-topic word check does not drop it.
    # A question is not that line: "who is Pompey?" stays even when the flag is set.
    scored_try = (
        not learner_asks_question_or_background(answer)
        and not ancillary_story(answer, block)
        and (
            rubric_covers_substep(block, index, substep, fresh)
            or (bool(substep_passed) and learner_gave_real_attempt(block, substep, answer, cfg))
        )
    )
    if scored_try:
        side_turn = False
        non_answer = False
    # Asking to hear more about the passage is on-topic help, even in exploratory mode.
    if example_reply or passage_elaboration_request(block, answer) or (not matched_wrong and (side_turn or non_answer)):
        # Unscored help. Same block, same substep, same attempt count.
        return _unscored_stay(
            hint=tier,
            move_attempts=move_attempts,
            reveals=reveals,
            enrichment_turns=enrichment_turns,
            rubric=_clean_ids(list(stored_rubric)),
            index=index,
            bid=bid,
            state=state,
            results=results,
        )
    max_retries = max_retries_for_block(block, cfg, goal)

    # A choice is removed in the multiple-choice branch below, whatever the model tags.
    # A repeated tag reveals this block and continues. It does not end the unit.
    if matched_wrong and not (btype == "mcq" and substep == "choice"):
        should_redirect = misc_policy == "immediate_redirect" or last_misconception == matched_wrong
        if should_redirect:
            tries = int(state.get("block_attempts") or 0) + 1
            state["block_attempts"] = tries
            results.append(
                {
                    "id": bid,
                    "block_id": bid,
                    "block_type": btype,
                    "title": _block_title(block, index),
                    "attempts": tries,
                    "outcome": "revealed",
                    "strong": "",
                    "work_on": matched_wrong,
                    "summary": f"Revealed after a repeated misconception: {matched_wrong}",
                }
            )
            return _advance_or_close_component(
                blocks=blocks,
                index=index,
                results=results,
                met=met,
                reveals=reveals + 1,
                cfg=cfg,
                misconception=matched_wrong,
            )
        attempts = move_attempts + 1
        bumped = _next_tier(tier)
        if bumped == "reveal":
            bumped = "scaffold"
        return BlockResolution(
            decision="stay",
            hint_tier=bumped,
            move_attempts=attempts,
            reveals=reveals,
            enrichment_turns=enrichment_turns,
            rubric_met=met,
            misconception=matched_wrong,
            next_step=index,
            next_block_id=bid,
            next_block_state=state,
            block_results=results,
            mark_known=False,
            mark_fragile=False,
            redirect=False,
            unit_complete=False,
            advance_block=False,
            passed=False,
        )

    strong_text = (strong or "").strip()
    work_text = (work_on or "").strip()
    if proposal:
        # A wrong denominator can share every word with the expected formula.
        # For an exact fallback, keep operators, units and order, and let the
        # grader resolve any further text after the learner's first question.
        target = _proposal_target(block, substep)
        literal = not answer.partition("?")[2].strip() and (
            proposal.strip().rstrip(".!") == target.rstrip(".!")
        )
    else:
        literal = answer_addresses_substep(block, substep, answer, state, cfg)
    model_pass = model_accepts_substep(
        block,
        index,
        substep,
        answer,
        cfg,
        substep_passed=bool(substep_passed),
        rubric_met=fresh if proposal else met,
    )
    # A question mark kept the real-attempt check false. The model still passed this line.
    if not model_pass and grade_attempt and (
        bool(substep_passed) or rubric_covers_substep(block, index, substep, fresh)
    ):
        model_pass = True
    contextual_citation = btype == "passage_ela" and substep == "cite_evidence" and bool(data.get("evidence_context"))
    if contextual_citation:
        literal = False
        model_pass = _contextual_citation_met(data, answer, bcfg, bool(substep_passed))
    # Keyword overlap is only the fallback. A model pass on a real answer stands.
    addressed = model_pass or literal
    if btype == "socratic" and substep == "counterexample_probe" and _repeats_thesis(answer, state):
        # Repeating the thesis does not answer the probe, even when the model marks it passed.
        addressed = False
        model_pass = False
    if btype == "spot_the_flaw":
        flaw_text = str(data.get("flaw_description") or "")
        repair_text = str(data.get("corrected_version") or "")
        if flaw_text and _matches(answer, flaw_text):
            state["flaw_identified"] = True
        identify_only = str(bcfg.get("critique_depth") or "identify_and_correct") == "identify_only"
        if (
            not identify_only
            and state.get("flaw_identified")
            and repair_text
            and _matches(answer, repair_text)
            and learner_gave_real_attempt(block, substep, answer, cfg)
        ):
            # The repair can arrive after the flaw. Supplying it does not erase the identification.
            addressed = True
            model_pass = True

    def note_try() -> int:
        total = int(state.get("block_attempts") or 0) + 1
        state["block_attempts"] = total
        return total

    def stay(attempts: int, hint: str, *, reveals_now: int | None = None) -> BlockResolution:
        return BlockResolution(
            decision="stay",
            hint_tier=hint if hint in HINTS else "nudge",
            move_attempts=attempts,
            reveals=reveals if reveals_now is None else reveals_now,
            enrichment_turns=enrichment_turns,
            rubric_met=met,
            misconception="",
            next_step=index,
            next_block_id=bid,
            next_block_state=state,
            block_results=results,
            mark_known=False,
            mark_fragile=False,
            redirect=False,
            unit_complete=False,
            advance_block=False,
            passed=False,
        )

    def finish(outcome: str, attempts: int, reveals_now: int) -> BlockResolution:
        if state.get("answer_given_away") and outcome == "passed":
            outcome = "revealed"
        if (
            state.get("answer_given_away")
            and outcome == "revealed"
            and not already_revealed
            and not state.get("giveaway_counted")
            and reveals_now <= reveals
        ):
            reveals_now = reveals + 1
            state["giveaway_counted"] = True
        title = _block_title(block, index)
        noted_strong = strong_text or (title if outcome == "passed" else "")
        noted_work = work_text or ("" if outcome == "passed" else f"Look again at {title}.")
        evidence_substep = substep
        if evidence_substep == "summary_check":
            evidence_substep = str(state.get("last_task_substep") or substep)
        evidence_id = block_evidence_id(block, index, evidence_substep)
        results.append(
            {
                "id": bid,
                "block_id": bid,
                "block_type": btype,
                "title": title,
                "outcome": outcome,
                "attempts": attempts,
                "strong": noted_strong,
                "work_on": noted_work,
                "summary": f"{outcome} {btype} after {attempts} tries",
            }
        )
        if evidence_id not in met:
            met.append(evidence_id)
        return _advance_or_close_component(
            blocks=blocks,
            index=index,
            results=results,
            met=met,
            reveals=reveals_now,
            cfg=cfg,
        )

    if btype == "passage_ela" and learner_asks_for_passage(answer):
        policy = str(bcfg.get("passage_ela_reread_policy") or "free_reprint")
        if policy == "free_reprint":
            return stay(move_attempts, tier)

    if btype == "passage_ela" and substep == "cite_evidence" and not contextual_citation and learner_points_at_span(answer, data):
        # Pointing at the span settles citation as assisted and leaves the other steps alone.
        state["citation_assisted"] = True
        note_try()
        if "craft_or_inference" in substeps:
            state["substep"] = "craft_or_inference"
        return stay(0, "nudge")

    if btype == "topic_goal" and substep == "main" and learner_ready_to_proceed(answer, False):
        tries = note_try()
        covered = rubric_covers_substep(block, index, "main", met) or bool(substep_passed)
        # "move on" after the goal evidence is already met is a pass, not a give-up.
        if covered or (addressed and not state.get("revealed_substep")):
            return finish("passed", tries, reveals)
        return finish("revealed", tries, reveals + 1)

    if (
        btype == "topic_goal"
        and bool(bcfg.get("fragment_self_explanation", True))
        and fragment
        and not state.get("fragment_prompted")
        and not unscored_side_request(block, substep, answer, state, cfg)
        and not learner_side_question(answer, block, substep)
        and not (substep == "summary_check" and summary_ready_signal(answer))
    ):
        state["fragment_prompted"] = True
        return stay(move_attempts, tier)

    task_steps = substeps[:-1] if substeps and substeps[-1] == "summary_check" else list(substeps)
    on_last_task = bool(task_steps) and bool(substeps) and substeps[-1] == "summary_check" and (
        substep == task_steps[-1] or (btype == "mcq" and substep == "awaiting_why")
    )

    def _summary_outcome() -> str:
        if state.get("answer_given_away") or state.get("revealed_substep"):
            return "revealed"
        if btype == "curiosity" and not _counts_toward_mastery(block, cfg):
            return "engaged"
        return "passed"

    def _clean_mid_pass() -> bool:
        """A passed final step in the middle of the component skips the summary check.

        A reveal, a giveaway, and the last block still stop for summary_check.
        forecast_this_turn calls resolve_block_turn, so it takes this same branch.
        """
        if index >= len(blocks) - 1:
            return False
        if state.get("revealed_substep") or state.get("recall_revealed"):
            return False
        if state.get("answer_given_away") or state.get("giveaway_counted"):
            return False
        return True

    def _enter_summary(*, revealed: bool) -> BlockResolution:
        state["last_task_substep"] = substep
        state["substep"] = "summary_check"
        if revealed:
            state["revealed_substep"] = True
            return stay(0, "reveal", reveals_now=reveals + 1)
        return stay(0, "nudge")

    def _resolve_summary_check() -> BlockResolution:
        # A passed summary closes on any reply that is not a question, in this turn.
        # That reply is not sent back to the goal. An incomplete summary still
        # closes only on let's go, move on, next, or yes, so a late correct
        # answer can still clear the miss.
        passed_summary = not state.get("revealed_substep")
        if (passed_summary and summary_ready_signal(answer)) or summary_explicit_move_on(answer):
            tries = int(state.get("block_attempts") or 0) or 1
            return finish(_summary_outcome(), tries, reveals)
        stored_task = str(state.get("last_task_substep") or "").strip()
        task_substep = stored_task or (substeps[-2] if len(substeps) >= 2 else substep)
        demonstrated = model_accepts_substep(
            block,
            index,
            task_substep,
            answer,
            cfg,
            substep_passed=bool(substep_passed),
            rubric_met=met,
        ) or (
            bool(substep_passed)
            and answer_addresses_substep(block, task_substep, answer, state, cfg)
        )
        move_phrase = learner_ready_to_proceed(answer, False)
        if state.get("revealed_substep") and demonstrated and not move_phrase:
            state["revealed_substep"] = False
            note_try()
            if block_complete:
                return finish(_summary_outcome(), int(state.get("block_attempts") or 1), reveals)
            return stay(0, "nudge")
        if demonstrated and state.get("revealed_substep"):
            state["revealed_substep"] = False
        # The check-in was the previous turn. One further question is answered
        # here, then the block closes. Elaborate still stays.
        if summary_closes_after_question(answer):
            tries = int(state.get("block_attempts") or 0) or 1
            return finish(_summary_outcome(), tries, reveals)
        if summary_further_question(answer):
            return stay(move_attempts, "nudge")
        ready = learner_ready_to_proceed(answer, bool(substep_passed) or bool(block_complete))
        if not ready:
            return stay(move_attempts + 1, "nudge")
        tries = int(state.get("block_attempts") or 0) or 1
        return finish(_summary_outcome(), tries, reveals)

    if btype == "mcq" and substep == "choice":
        choices, correct_idx = mcq_payload(block, state)
        if not choices:
            return stay(move_attempts, tier)
        picked = match_mcq_choice_index(answer, choices)
        mcq_state = dict(state.get("mcq") or {})
        if "frozen_key" in mcq_state:
            try:
                correct_idx = int(mcq_state["frozen_key"])
            except (TypeError, ValueError):
                mcq_state["frozen_key"] = correct_idx
        else:
            mcq_state["frozen_key"] = correct_idx
        correct_idx = max(0, min(int(correct_idx), len(choices) - 1))
        eliminated_now: list[int] = []
        for item in mcq_state.get("eliminated_indices") or []:
            try:
                eliminated_now.append(int(item))
            except (TypeError, ValueError):
                continue
        visible = [index for index in range(len(choices)) if index not in set(eliminated_now)]
        mcq_state["choices"] = choices
        mcq_state["correct_index"] = correct_idx
        if picked is not None and picked == correct_idx:
            if len(visible) <= 1:
                state["choice_assisted"] = True
            note_try()
            confirm_mode = str(bcfg.get("confirm_why_on_correct") or "on_retry_only")
            need_why = confirm_mode == "always" or (confirm_mode == "on_retry_only" and move_attempts > 0)
            state["mcq"] = mcq_state
            if need_why:
                state["substep"] = "awaiting_why"
                return stay(0, "nudge")
            if _clean_mid_pass():
                return finish("passed", int(state.get("block_attempts") or 1), reveals)
            return _enter_summary(revealed=False)
        eliminated = list(mcq_state.get("eliminated_indices") or [])
        if picked is not None and picked not in eliminated:
            eliminated.append(picked)
        mcq_state["eliminated_indices"] = eliminated
        state["mcq"] = mcq_state
        note_try()
        if move_attempts + 1 >= max_retries:
            return _enter_summary(revealed=True)
        bumped = _next_tier(tier)
        if bumped == "reveal":
            bumped = "scaffold"
        return stay(move_attempts + 1, bumped)

    def _proceeding() -> bool:
        return learner_ready_to_proceed(answer, False) or _proceed_text(answer) == "yes"

    if _proceeding():
        relevant = substep
        if substep == "summary_check":
            relevant = str(state.get("last_task_substep") or "").strip() or (
                substeps[-2] if len(substeps) >= 2 else substep
            )
        covered = rubric_covers_substep(block, index, relevant, met) or (
            relevant != substep and rubric_covers_substep(block, index, substep, met)
        )
        # A proceed phrase never reveals a step the model already awarded.
        if covered or (bool(substep_passed) and not state.get("revealed_substep")):
            if not (state.get("revealed_substep") and not covered):
                tries = int(state.get("block_attempts") or 0) or 1
                return finish("passed", tries, reveals)

    # A continue question is already on screen. Yes, move on, and next part close it.
    # A bare yes does not close an ordinary worked step.
    if (
        btype == "worked_example"
        and tutor_asked_to_continue(prior_tutor)
        and worked_continue_answer(answer)
        and not (on_last_task and (model_pass or (addressed and bool(substep_passed))))
    ):
        tries = int(state.get("block_attempts") or 0) or 1
        close_step = substep
        if substep == "summary_check":
            close_step = str(state.get("last_task_substep") or "solo_solve")
        evidence_met = rubric_covers_substep(block, index, close_step, met) or bool(substep_passed)
        if evidence_met or (substep == "summary_check" and not state.get("revealed_substep")):
            return finish("passed", tries, reveals)
        reveal_count = reveals if state.get("revealed_substep") else reveals + 1
        return finish("revealed", tries, reveal_count)

    if substep == "summary_check":
        return _resolve_summary_check()

    if btype == "socratic" and substep == "counterexample_probe" and addressed:
        depth = max(1, int(bcfg.get("dialogue_depth_turns", 2) or 2))
        probes = int(state.get("probe_turns") or 0) + 1
        state["probe_turns"] = probes
        note_try()
        if probes < depth:
            return stay(move_attempts, "nudge")
        # Addressing this probe counts. The thesis id does not.
        if _clean_mid_pass():
            return finish(_summary_outcome(), int(state.get("block_attempts") or 1), reveals)
        return _enter_summary(revealed=False)

    # The model pass is enough. Literal overlap still needs the model flag,
    # except a topic_goal reply that already states the chain: that finishes main.
    # An unfinished summary is not this step, so a late correct answer can still clear a miss.
    # "What's next?" is not a real attempt, so it does not pass an open goal.
    chain_on_main = (
        btype == "topic_goal"
        and substep == "main"
        and literal
        and (
            learner_gave_real_attempt(block, substep, answer, cfg)
            or (grade_attempt and _substantive(answer, _minimum_words(block, substep, cfg)))
        )
    )
    satisfied = model_pass or (literal and bool(substep_passed)) or chain_on_main
    if on_last_task and satisfied:
        note_try()
        # The step divider opens the next block. Do not stop for a summary question.
        if btype == "worked_example":
            given = bool(state.get("revealed_substep") or state.get("faded_answer_given"))
            outcome = "revealed" if given else "passed"
            return finish(outcome, int(state.get("block_attempts") or 1), reveals)
        if _clean_mid_pass():
            return finish(_summary_outcome(), int(state.get("block_attempts") or 1), reveals)
        return _enter_summary(revealed=False)

    if addressed:
        if btype == "socratic" and substep == "initial_thesis":
            state["thesis"] = (answer or "").strip()
        note_try()
        if substep in task_steps:
            position = task_steps.index(substep)
            if position < len(task_steps) - 1:
                state["substep"] = task_steps[position + 1]
                state["probe_turns"] = 0
                return stay(0, "nudge")
            if btype == "passage_ela":
                return finish("passed", int(state.get("block_attempts") or 1), reveals)
        if on_last_task:
            if move_attempts + 1 >= max_retries:
                return _enter_summary(revealed=True)
            return stay(move_attempts + 1, tier)
        if decision == "stay" and not block_complete and move_attempts + 1 < max_retries:
            return stay(move_attempts + 1, tier)
        outcome = "revealed" if state.get("revealed_substep") else "passed"
        return finish(outcome, int(state.get("block_attempts") or 1), reveals)

    tries = note_try()
    if move_attempts + 1 >= max_retries:
        if btype == "case_study" and substep == "predict" and "contrast_and_rule" in task_steps:
            # The supplied prediction stays assisted. The rule is still open.
            state["prediction_supplied"] = True
            state["substep"] = "contrast_and_rule"
            return stay(0, "nudge", reveals_now=reveals + 1)
        if btype == "case_study" and substep == "contrast_and_rule" and "transfer" in task_steps:
            state["rule_supplied"] = True
            state["substep"] = "transfer"
            return stay(0, "nudge", reveals_now=reveals + 1)
        if btype == "passage_ela" and substep in task_steps:
            position = task_steps.index(substep)
            if position < len(task_steps) - 1:
                state["substep"] = task_steps[position + 1]
                return stay(0, "reveal", reveals_now=reveals + 1)
        if btype == "worked_example" and substep == "faded_step" and "solo_solve" in substeps:
            # State the faded answer and stop. The solo problem waits for a later turn.
            state["revealed_substep"] = True
            state["faded_answer_given"] = True
            return stay(0, "reveal", reveals_now=reveals + 1)
        if btype == "retrieval_check" and substep == "recall" and "elaborate_why" in substeps:
            # The fact is shown. The why question still has to be asked. The unit stays open.
            state["substep"] = "elaborate_why"
            state["recall_revealed"] = True
            return stay(0, "nudge", reveals_now=reveals + 1)
        if on_last_task:
            return _enter_summary(revealed=True)
        return finish("revealed", tries, reveals + 1)
    bumped = _next_tier(tier)
    if bumped == "reveal":
        bumped = "scaffold"
    return stay(move_attempts + 1, bumped)


def _counts_toward_mastery(block: dict, cfg: dict) -> bool:
    kind = str(block.get("type") or "").strip()
    if kind not in {"curiosity", "explanation"}:
        return True
    bcfg = ((cfg or {}).get("blocks") or {}).get(kind) or {}
    return bool(bcfg.get("counts_toward_mastery_score", False))


_GIVEAWAY_CUES = (
    "say it back",
    "say that back",
    "put it in your own words",
    "repeat it",
    "repeat that",
    "say it again",
    "say that again",
    "now you say",
    "your turn to say",
    "giving you the answer",
    "give you the answer",
    "the answer is",
    "here's the answer",
    "here is the answer",
)


def _folded(text: str) -> str:
    return " ".join((text or "").lower().split())


def _required_chain(block: dict, substep: str) -> str:
    """The answer this step requires. A giveaway is this chain, said out loud."""
    data = _data(block)
    btype = str(block.get("type") or "").strip()
    if btype == "topic_goal":
        return str(data.get("acceptance_criteria") or data.get("goal") or "").strip()
    if btype == "retrieval_check":
        if substep == "elaborate_why":
            return str(data.get("expected_why_rationale") or "").strip()
        return str(data.get("expected_fact") or "").strip()
    if btype == "worked_example" and substep == "solo_solve":
        return str(data.get("solo_expected_answer") or "").strip()
    if btype == "worked_example" and substep == "faded_step":
        steps = data.get("steps") if isinstance(data.get("steps"), list) else []
        index = int(data.get("faded_step_index") or 0)
        step = steps[index] if 0 <= index < len(steps) else ""
        text = step.get("step_text") if isinstance(step, dict) else str(step)
        return str(text or "").strip()
    if btype == "mcq" and substep == "awaiting_why":
        return str(data.get("correct_explanation") or "").strip()
    if btype == "spot_the_flaw":
        return str(data.get("corrected_version") or "").strip()
    if btype == "socratic":
        return str(data.get("target_synthesis") or "").strip()
    if btype == "case_study":
        return str(data.get("invariant_principle") or data.get("transfer_expected") or "").strip()
    return ""


def _asks_to_repeat_or_gives_answer(text: str) -> bool:
    folded = _folded(text)
    return any(cue in folded for cue in _GIVEAWAY_CUES)


def tutor_read_correct_choice(block: dict, state: dict | None, prior_tutor: str) -> bool:
    """The previous reply names the correct option, rather than listing the menu."""
    if str(block.get("type") or "").strip() != "mcq":
        return False
    choices, correct = mcq_payload(block, state if isinstance(state, dict) else {})
    if not choices or correct < 0 or correct >= len(choices):
        return False
    folded = _folded(prior_tutor)
    if not folded:
        return False
    correct_text = _folded(str(choices[correct].get("text") or ""))
    if len(correct_text) < 4 or correct_text not in folded:
        return False
    others = [
        _folded(str(item.get("text") or ""))
        for index, item in enumerate(choices)
        if index != correct and _folded(str(item.get("text") or ""))
    ]
    if others and all(item in folded for item in others):
        return False
    return True


def _worked_answer_and_reason(block: dict) -> tuple[str, str]:
    """The faded step's answer and its reason. Empty unless both are stored apart."""
    if str(block.get("type") or "").strip() != "worked_example":
        return "", ""
    data = _data(block)
    steps = data.get("steps") if isinstance(data.get("steps"), list) else []
    try:
        index = int(data.get("faded_step_index") or 0)
    except (TypeError, ValueError):
        index = 0
    step = steps[index] if 0 <= index < len(steps) and isinstance(steps[index], dict) else {}
    answer = str(step.get("step_text") or "").strip()
    reason = str(step.get("rationale") or "").strip()
    folded_answer = _folded(answer)
    folded_reason = _folded(reason)
    if not folded_answer or not folded_reason:
        return "", ""
    if folded_answer == folded_reason or folded_reason in folded_answer or folded_answer in folded_reason:
        return "", ""
    return answer, reason


def tutor_stated_answer_and_reason(block: dict, prior_tutor: str) -> bool:
    """The tutor already said who wins and why. That line is a giveaway.

    Stating the required chain with no reason, and with no ask to repeat it,
    is not this.
    """
    answer, reason = _worked_answer_and_reason(block)
    if not answer:
        return False
    return _matches(prior_tutor, answer) and _matches(prior_tutor, reason)


def tutor_gave_away_answer(block: dict, state: dict | None, substep: str, prior_tutor: str) -> bool:
    """The tutor read the correct choice, stated the answer and the reason, or asked for the chain back.

    A later correct line does not undo this. The stored outcome stays revealed.
    """
    stored = state if isinstance(state, dict) else {}
    if stored.get("answer_given_away"):
        return True
    if tutor_read_correct_choice(block, stored, prior_tutor):
        return True
    if tutor_stated_answer_and_reason(block, prior_tutor):
        return True
    task = substep
    if substep == "summary_check":
        task = str(stored.get("last_task_substep") or "").strip() or substep
    chain = _required_chain(block, task)
    if not chain or not _asks_to_repeat_or_gives_answer(prior_tutor):
        return False
    return _matches(prior_tutor, chain)


def _outcome_succeeded(row: dict | None) -> bool:
    if not isinstance(row, dict):
        return False
    return str(row.get("outcome") or "") in {"passed", "engaged"}


def _advance_or_close_component(
    *,
    blocks: list[dict],
    index: int,
    results: list[dict],
    met: list[str],
    reveals: int,
    cfg: dict,
    misconception: str = "",
) -> BlockResolution:
    if index < len(blocks) - 1:
        next_idx = index + 1
        next_blk = blocks[next_idx]
        next_id = str(next_blk.get("id") or f"blk_{next_idx + 1}").strip()
        return BlockResolution(
            decision="advance",
            hint_tier="nudge",
            move_attempts=0,
            reveals=reveals,
            enrichment_turns=0,
            rubric_met=met,
            misconception=misconception,
            next_step=next_idx,
            next_block_id=next_id,
            next_block_state=initial_block_state(next_blk, cfg, previous=blocks[index]),
            block_results=results,
            mark_known=False,
            mark_fragile=False,
            redirect=False,
            unit_complete=False,
            advance_block=True,
            passed=False,
        )

    by_id = {
        str(row.get("id") or row.get("block_id") or ""): row
        for row in results
        if isinstance(row, dict)
    }
    fragile = False
    counted = False
    for position, block in enumerate(blocks):
        if not _counts_toward_mastery(block, cfg):
            continue
        counted = True
        key = str(block.get("id") or f"blk_{position + 1}").strip()
        row = by_id.get(key)
        if not _outcome_succeeded(row):
            fragile = True
    if not counted:
        fragile = False
    return BlockResolution(
        decision="complete",
        hint_tier="reveal" if fragile else "nudge",
        move_attempts=0,
        reveals=reveals,
        enrichment_turns=0,
        rubric_met=met,
        misconception=misconception,
        next_step=index,
        next_block_id=str(blocks[index].get("id") or f"blk_{index + 1}").strip(),
        next_block_state={"substep": "done", "dialogue_turns": 0},
        block_results=results,
        mark_known=not fragile,
        mark_fragile=fragile,
        redirect=False,
        unit_complete=True,
        advance_block=False,
        passed=not fragile,
    )


@dataclass(frozen=True)
class SpokenTurn:
    """What the reply should do. stay, advance, or close."""

    speech: str
    unit_complete: bool
    advance_block: bool
    revealed: bool
    next_substep: str
    decision: str
    reveal_stop: bool = False


@dataclass(frozen=True)
class TurnForecast:
    """Loop outcome for this child line, computed before the model speaks.

    applies is false on an opening and when there is no child line.
    depends_on_model is true when a pass and a miss would not say the same thing.
    """

    applies: bool
    depends_on_model: bool
    chosen: SpokenTurn | None
    if_correct: SpokenTurn | None
    if_not: SpokenTurn | None


def _spoken_turn(resolution: BlockResolution, *, before_substep: str, before_topic: int) -> SpokenTurn:
    state = resolution.next_block_state if isinstance(resolution.next_block_state, dict) else {}
    substep = str(state.get("substep") or "")
    topic = int(state.get("topic_index") or 0)
    revealed = bool(state.get("revealed_substep") or state.get("recall_revealed"))
    if resolution.hint_tier == "reveal":
        revealed = True
    if resolution.unit_complete or resolution.advance_block:
        speech = "close"
    elif substep != before_substep or topic != before_topic:
        speech = "advance"
    else:
        speech = "stay"
    # A faded-step reveal stays on that step. It is not an advance to the solo problem.
    reveal_stop = (
        speech == "stay"
        and resolution.hint_tier == "reveal"
        and substep == "faded_step"
        and substep == before_substep
        and not resolution.unit_complete
        and not resolution.advance_block
    )
    return SpokenTurn(
        speech=speech,
        unit_complete=bool(resolution.unit_complete),
        advance_block=bool(resolution.advance_block),
        revealed=revealed,
        next_substep=substep,
        decision=str(resolution.decision or "stay"),
        reveal_stop=reveal_stop,
    )


def _same_speech(left: SpokenTurn, right: SpokenTurn) -> bool:
    return (
        left.speech == right.speech
        and left.unit_complete == right.unit_complete
        and left.advance_block == right.advance_block
        and left.revealed == right.revealed
        and left.next_substep == right.next_substep
        and left.reveal_stop == right.reveal_stop
    )


def forecast_this_turn(
    *,
    blocks: list[dict],
    step: int,
    active_block_state: dict,
    block_results: list[dict],
    answer: str,
    cfg: dict,
    goal: KcGoal | None,
    stored_rubric: list[str],
    move_attempts: int,
    hint_tier: str,
    reveals: int,
    enrichment_turns: int,
    fragment: bool = False,
    prior_tutor: str = "",
    opening: bool = False,
) -> TurnForecast:
    """Run the loop twice on copies. No model call.

    One run assumes the model accepts the line. The other assumes it does not.
    When both say the same thing, the turn is known. Otherwise the prompt
    carries both, labeled if correct and if not.
    """
    empty = TurnForecast(False, False, None, None, None)
    if opening or not str(answer or "").strip():
        return empty
    before = active_block_state if isinstance(active_block_state, dict) else {}
    before_substep = str(before.get("substep") or "")
    before_topic = int(before.get("topic_index") or 0)

    def run(passed: bool) -> SpokenTurn:
        resolution = resolve_block_turn(
            decision="advance" if passed else "stay",
            substep_passed=passed,
            block_complete=False,
            rubric_met=[],
            stored_rubric=list(stored_rubric or []),
            matched_wrong="",
            blocks=copy.deepcopy(blocks),
            step=step,
            active_block_state=copy.deepcopy(before),
            block_results=copy.deepcopy(block_results or []),
            move_attempts=move_attempts,
            hint_tier=hint_tier,
            reveals=reveals,
            enrichment_turns=enrichment_turns,
            cfg=cfg,
            goal=goal,
            last_misconception="",
            answer=answer,
            fragment=fragment,
            prior_tutor=prior_tutor,
            learner_ready=False,
        )
        return _spoken_turn(resolution, before_substep=before_substep, before_topic=before_topic)

    accepted = run(True)
    missed = run(False)
    if _same_speech(accepted, missed):
        return TurnForecast(True, False, accepted, accepted, missed)
    return TurnForecast(True, True, None, accepted, missed)

