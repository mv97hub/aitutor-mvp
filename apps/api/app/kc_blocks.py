"""Cleaning and checks for the passage_ela block.

Other block types are not rewritten here. Callers apply these helpers only
when the block type is passage_ela.
"""

from __future__ import annotations

import re

PASSAGE_TITLE_LIMIT = 160
PASSAGE_TEXT_LIMIT = 4000

PASSAGE_GENRES = (
    "informational",
    "literary",
    "argumentative",
    "historical_primary",
)

ANALYSIS_FOCI = (
    "inference",
    "vocab_in_context",
    "author_purpose_structure",
    "evaluate_argument",
)

PASSAGE_SUBSTEPS = (
    "central_idea",
    "cite_evidence",
    "craft_or_inference",
)

PASSAGE_CAP_RULE = (
    "Include the full Passage text verbatim (preserving paragraph breaks) before asking the question. "
    "The response_length sentence cap (2 to 4 sentences) applies ONLY to your coaching and question below the passage, never to the passage text itself."
)

_TOKEN = re.compile(r"\S+")

_PASSAGE_ASKS = (
    "show me the passage",
    "show the passage",
    "see the passage",
    "see that passage",
    "what passage",
    "which passage",
    "whats the passage",
    "what is the passage",
    "read the passage",
    "reread the passage",
    "reread",
    "re read",
    "read it again",
    "read that again",
    "passage again",
    "see paragraph",
    "show paragraph",
    "read paragraph",
    "paragraph again",
    "can i see the passage",
    "can i see paragraph",
    "let me see the passage",
    "let me read the passage",
    "let me reread",
)


def _ask_text(answer: str) -> str:
    text = (answer or "").lower().replace("—", " ").replace("–", " ").replace("'", "")
    text = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text)
    return " ".join(text.split())


def learner_asks_for_passage(answer: str) -> bool:
    """True when the learner wants the passage shown again, not when they answer from it."""
    text = _ask_text(answer)
    if not text:
        return False
    return any(phrase in text for phrase in _PASSAGE_ASKS)


def clip_passage_text(value: object) -> str:
    """Keep paragraph breaks. Cap the passage at 4,000 characters."""
    text = "" if value is None else str(value)
    if len(text) <= PASSAGE_TEXT_LIMIT:
        return text
    return text[:PASSAGE_TEXT_LIMIT]


def clip_passage_title(value: object) -> str:
    return str(value or "").strip()[:PASSAGE_TITLE_LIMIT]


def clean_genre(value: object) -> str:
    text = str(value or "").strip()
    if text in PASSAGE_GENRES:
        return text
    return "informational"


def clean_analysis_focus(value: object) -> str:
    text = str(value or "").strip()
    if text in ANALYSIS_FOCI:
        return text
    return "inference"


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def align_quote_to_passage(quote: str, passage: str) -> str | None:
    """Return the passage span that matches the quote, ignoring case and whitespace.

    The span is copied from passage_text, so the stored quote is verbatim.
    """
    quote_tokens = [(match.group().casefold(), match.start(), match.end()) for match in _TOKEN.finditer(quote or "")]
    passage_tokens = [(match.group().casefold(), match.start(), match.end()) for match in _TOKEN.finditer(passage or "")]
    if not quote_tokens or not passage_tokens:
        return None
    wanted = [token for token, _start, _end in quote_tokens]
    have = [token for token, _start, _end in passage_tokens]
    width = len(wanted)
    if width > len(have):
        return None
    for index in range(len(have) - width + 1):
        if have[index : index + width] != wanted:
            continue
        start = passage_tokens[index][1]
        end = passage_tokens[index + width - 1][2]
        return passage[start:end]
    return None


def quote_in_text(quote: str, text: str) -> bool:
    return align_quote_to_passage(quote, text) is not None


def clean_evidence_quotes(quotes: object, passage: str) -> list[str]:
    """Keep up to three quotes that actually occur in the passage, in passage wording."""
    raw_items: list[str] = []
    if isinstance(quotes, str):
        raw_items = [quotes]
    elif isinstance(quotes, list):
        raw_items = [str(item) for item in quotes if str(item or "").strip()]
    kept: list[str] = []
    for item in raw_items:
        aligned = align_quote_to_passage(item, passage)
        if aligned and aligned not in kept:
            kept.append(aligned)
        if len(kept) == 3:
            break
    return kept


def clean_passage_ela_data(data: dict | None) -> dict:
    """Normalize one passage_ela data object. Unknown keys are dropped."""
    raw = data if isinstance(data, dict) else {}
    passage_text = clip_passage_text(raw.get("passage_text"))
    return {
        "passage_title": clip_passage_title(raw.get("passage_title")),
        "passage_genre": clean_genre(raw.get("passage_genre")),
        "passage_text": passage_text,
        "central_idea_question": _text(raw.get("central_idea_question")),
        "expected_central_idea": _text(raw.get("expected_central_idea")),
        "distractor_detail": _text(raw.get("distractor_detail")),
        "evidence_prompt": _text(raw.get("evidence_prompt")),
        "verbatim_evidence_quotes": clean_evidence_quotes(raw.get("verbatim_evidence_quotes"), passage_text),
        "analysis_focus": clean_analysis_focus(raw.get("analysis_focus")),
        "analysis_question": _text(raw.get("analysis_question")),
        "expected_analysis": _text(raw.get("expected_analysis")),
    }


def passage_ela_gap(data: dict | None) -> str:
    """Readiness gap for a passage_ela block, or empty when it can be taught."""
    cleaned = clean_passage_ela_data(data)
    if not cleaned["passage_title"] or not cleaned["passage_text"].strip():
        return "needs a passage title and passage text"
    if not cleaned["central_idea_question"] or not cleaned["expected_central_idea"]:
        return "needs a central idea question and the expected central idea"
    if not cleaned["evidence_prompt"]:
        return "needs an evidence prompt"
    count = len(cleaned["verbatim_evidence_quotes"])
    if count < 2 or count > 3:
        return "needs 2 or 3 evidence quotes copied from the passage"
    if not cleaned["analysis_question"] or not cleaned["expected_analysis"]:
        return "needs an analysis question and the expected analysis"
    return ""


def passage_paragraphs(text: str) -> list[str]:
    parts = [part.strip() for part in str(text or "").split("\n\n") if part.strip()]
    if parts:
        return parts
    stripped = str(text or "").strip()
    return [stripped] if stripped else []


def passage_display_mode(cfg: dict | None) -> str:
    bcfg = ((cfg or {}).get("blocks") or {}).get("passage_ela") or {}
    mode = str(bcfg.get("passage_ela_display_mode") or "full_on_open").strip()
    if mode == "chunked_by_paragraph":
        return mode
    return "full_on_open"


def passage_reread_policy(cfg: dict | None) -> str:
    bcfg = ((cfg or {}).get("blocks") or {}).get("passage_ela") or {}
    policy = str(bcfg.get("passage_ela_reread_policy") or "free_reprint").strip()
    if policy == "free_reprint":
        return policy
    return "free_reprint"


def passage_reprint_kind(
    block: dict,
    cfg: dict | None,
    *,
    opening: bool,
    last_answer: str,
) -> str:
    """full, paragraph, or empty when this turn should not print passage text."""
    if str(block.get("type") or "").strip() != "passage_ela":
        return ""
    if learner_asks_for_passage(last_answer) and passage_reread_policy(cfg) == "free_reprint":
        return "full"
    if opening:
        if passage_display_mode(cfg) == "chunked_by_paragraph":
            return "paragraph"
        return "full"
    return ""
