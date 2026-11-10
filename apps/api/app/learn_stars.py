"""Child-facing stars and explorer rank, computed from course rollups.

+10 for every completed learning block.
+5 when a block is passed on the first try.
+25 when a topic is finished (known or fragile).
+15 more when that topic is known and no counting block was revealed.

Child-facing status words stay encouraging. The technical word for a
finished-with-reveals topic is never returned from here.
"""

from __future__ import annotations

STAR_PER_BLOCK = 10
STAR_FIRST_TRY = 5
STAR_PER_TOPIC = 25
STAR_ZERO_REVEAL = 15

# Stars required to enter each rank. The next threshold is the bar on the progress strip.
EXPLORER_RANKS: tuple[tuple[int, str, int], ...] = (
    (1, "Curious Spark", 0),
    (2, "Concept Builder", 75),
    (3, "Discovery Navigator", 250),
    (4, "Grand Scholar", 600),
)


def child_status_label(status: str, mastery: str = "", *, locked: bool = False) -> str:
    """Map a component rollup onto a label a child can read."""
    if status == "completed" and mastery == "known":
        return "Mastered"
    if status == "completed":
        return "Completed"
    if status == "in_progress":
        return "In Progress"
    if locked:
        return "Locked"
    return "Up Next"


def stars_from_units(units: list[dict]) -> dict:
    """Roll mastery stars from target component rows. Patch units are skipped."""
    targets = [unit for unit in units if not unit.get("patch")]
    completed_blocks = sum(int(unit.get("completed_blocks") or 0) for unit in targets)
    first_try = sum(int(unit.get("first_try_blocks_count") or 0) for unit in targets)
    finished = [unit for unit in targets if unit.get("status") == "completed"]
    crowns = sum(
        1
        for unit in finished
        if unit.get("mastery") == "known" and int(unit.get("revealed_blocks_count") or 0) == 0
    )
    topics = len(finished)
    return {
        "stars": (
            completed_blocks * STAR_PER_BLOCK
            + first_try * STAR_FIRST_TRY
            + topics * STAR_PER_TOPIC
            + crowns * STAR_ZERO_REVEAL
        ),
        "star_block": completed_blocks * STAR_PER_BLOCK,
        "star_first_try": first_try * STAR_FIRST_TRY,
        "star_topic": topics * STAR_PER_TOPIC,
        "star_crown": crowns * STAR_ZERO_REVEAL,
        "finished_topic_count": topics,
        "crown_topic_count": crowns,
    }


def empty_stars() -> dict:
    return {
        "stars": 0,
        "star_block": 0,
        "star_first_try": 0,
        "star_topic": 0,
        "star_crown": 0,
        "finished_topic_count": 0,
        "crown_topic_count": 0,
    }


def explorer_progress(stars: int) -> dict:
    """Map a star total onto a rank and the bar toward the next rank."""
    safe = max(int(stars or 0), 0)
    level, rank, floor = EXPLORER_RANKS[0]
    nxt: int | None = EXPLORER_RANKS[1][2]
    for index, (lv, name, threshold) in enumerate(EXPLORER_RANKS):
        if safe >= threshold:
            level, rank, floor = lv, name, threshold
            nxt = EXPLORER_RANKS[index + 1][2] if index + 1 < len(EXPLORER_RANKS) else None
    if nxt is None:
        percent = 100
    else:
        span = max(nxt - floor, 1)
        percent = min(100, int((safe - floor) * 100 / span))
    return {
        "explorer_level": level,
        "explorer_rank": rank,
        "explorer_floor": floor,
        "explorer_next": nxt,
        "explorer_percent": percent,
    }
