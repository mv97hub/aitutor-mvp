"""Parents, their linked children, and the parent-safe chat views.

There is no login. A parent id in the URL is the only gate, the same as the kid
pages. The link check below keeps one parent's pages on the children they chose.
A parent never receives model prompts or token counts: the chat detail here has neither key.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, joinedload

from app.kc import _ready_course_cards, kc_chat_detail, kc_chat_summaries
from app.learn_stars import stars_from_units
from app.models import KcSession, Parent, ParentStudent, Student
from app.present import student_out
from app.schemas import KcChatComponent, KcChatCourse, KcChatMessage, StudentOut

# A household week starts Monday at midnight in this zone. The product has no per-parent zone yet.
PARENT_WEEK_ZONE = ZoneInfo("America/New_York")


class ParentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ParentStudentsIn(BaseModel):
    student_ids: list[uuid.UUID] = Field(default_factory=list)


class ParentOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    child_count: int = 0


class ParentChatSummary(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    student_display_name: str
    course_id: uuid.UUID
    course_code: str
    course_title: str
    kc_id: uuid.UUID
    kc_code: str
    kc_title: str
    step_label: str
    status: str
    score: int | None = None
    created_at: datetime
    updated_at: datetime
    message_count: int


class ParentChatStudent(BaseModel):
    id: uuid.UUID
    display_name: str


class ParentChatDetail(BaseModel):
    """Same shape the admin chat view reads, minus the prompts and the student profile."""

    id: uuid.UUID
    status: str
    step_label: str
    score: int | None = None
    attempts: int
    created_at: datetime
    updated_at: datetime
    student: ParentChatStudent
    course: KcChatCourse
    component: KcChatComponent
    messages: list[KcChatMessage]


class ParentWeekCounts(BaseModel):
    sessions: int = 0
    topics_finished: int = 0
    stars: int = 0
    blocks_passed: int = 0
    blocks_revealed: int = 0
    days_active: int = 0


class ParentAttentionItem(BaseModel):
    """One line to revisit. Title and detail only: never a chat message."""

    course_id: uuid.UUID
    title: str
    detail: str = ""


class ParentDashboardChild(BaseModel):
    student_id: uuid.UUID
    display_name: str
    courses_started: int = 0
    courses_finished: int = 0
    stars: int = 0
    finished_topics: int = 0
    topics_mastered: int = 0
    topics_fragile: int = 0
    current_course_id: uuid.UUID | None = None
    current_course_title: str = ""
    current_topic_title: str = ""
    last_active_at: datetime | None = None
    attention: list[ParentAttentionItem] = Field(default_factory=list)
    week: ParentWeekCounts = Field(default_factory=ParentWeekCounts)


class ParentDashboardActivity(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    student_display_name: str
    course_id: uuid.UUID
    course_title: str
    kc_title: str
    status: str
    updated_at: datetime


class ParentDashboardOut(BaseModel):
    """Household view. No chat text, prompts, or safety-event bodies."""

    week_starts_at: datetime
    recent: list[ParentDashboardActivity]
    children: list[ParentDashboardChild]


def _clean_name(value: str) -> str:
    name = " ".join(value.split())
    if not name:
        raise HTTPException(status_code=422, detail="Write a name for the parent.")
    return name[:120]


def _child_count(db: Session, parent_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.count()).select_from(ParentStudent).where(ParentStudent.parent_id == parent_id)
        )
        or 0
    )


def parent_out(db: Session, parent: Parent) -> ParentOut:
    return ParentOut(
        id=parent.id,
        name=parent.name,
        created_at=parent.created_at,
        child_count=_child_count(db, parent.id),
    )


def parent_or_404(db: Session, parent_id: uuid.UUID) -> Parent:
    parent = db.get(Parent, parent_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="That parent was not found.")
    return parent


def list_parents(db: Session) -> list[ParentOut]:
    rows = db.scalars(select(Parent).order_by(func.lower(Parent.name), Parent.created_at)).all()
    return [parent_out(db, row) for row in rows]


def create_parent(db: Session, name: str) -> ParentOut:
    parent = Parent(name=_clean_name(name))
    db.add(parent)
    db.flush()
    return parent_out(db, parent)


def linked_students(db: Session, parent_id: uuid.UUID) -> list[Student]:
    rows = db.scalars(
        select(Student)
        .join(ParentStudent, ParentStudent.student_id == Student.id)
        .where(ParentStudent.parent_id == parent_id)
    ).all()
    return sorted(rows, key=lambda student: (student.display_name or "").lower())


def linked_student_outs(db: Session, parent_id: uuid.UUID) -> list[StudentOut]:
    parent_or_404(db, parent_id)
    return [student_out(student) for student in linked_students(db, parent_id)]


def set_linked_students(db: Session, parent_id: uuid.UUID, student_ids: list[uuid.UUID]) -> list[StudentOut]:
    parent_or_404(db, parent_id)
    wanted = list(dict.fromkeys(student_ids))
    if wanted:
        found = set(db.scalars(select(Student.id).where(Student.id.in_(wanted))).all())
        missing = [item for item in wanted if item not in found]
        if missing:
            raise HTTPException(status_code=422, detail="One of those children was not found.")
    current = set(db.scalars(select(ParentStudent.student_id).where(ParentStudent.parent_id == parent_id)).all())
    removed = current - set(wanted)
    if removed:
        db.execute(
            delete(ParentStudent).where(
                ParentStudent.parent_id == parent_id, ParentStudent.student_id.in_(removed)
            )
        )
    for student_id in wanted:
        if student_id not in current:
            db.add(ParentStudent(parent_id=parent_id, student_id=student_id))
    db.flush()
    return [student_out(student) for student in linked_students(db, parent_id)]


def require_linked_child(db: Session, parent_id: uuid.UUID, student_id: uuid.UUID) -> Student:
    """404 for an unknown parent, 403 when the child is not one of theirs."""
    parent_or_404(db, parent_id)
    linked = db.scalar(
        select(ParentStudent.id).where(
            ParentStudent.parent_id == parent_id, ParentStudent.student_id == student_id
        )
    )
    student = db.get(Student, student_id) if linked is not None else None
    if student is None:
        raise HTTPException(status_code=403, detail="That child is not linked to this parent.")
    return student


def parent_chat_summaries(db: Session, parent_id: uuid.UUID, student_id: uuid.UUID) -> list[ParentChatSummary]:
    require_linked_child(db, parent_id, student_id)
    return [ParentChatSummary(**row) for row in kc_chat_summaries(db, student_id)]


def parent_chat_detail(
    db: Session, parent_id: uuid.UUID, student_id: uuid.UUID, session_id: uuid.UUID
) -> ParentChatDetail:
    require_linked_child(db, parent_id, student_id)
    row = db.get(KcSession, session_id)
    if row is None or row.student_id != student_id:
        raise HTTPException(status_code=404, detail="That chat was not found.")
    detail = kc_chat_detail(db, session_id)
    detail.pop("prompts", None)
    detail.pop("token_usage", None)
    detail["student"] = {"id": detail["student"]["id"], "display_name": detail["student"]["display_name"]}
    return ParentChatDetail(**detail)


def parent_week_start(now: datetime | None = None) -> datetime:
    """Monday 00:00 in the parent week zone, for the week that contains `now`."""
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    local = moment.astimezone(PARENT_WEEK_ZONE)
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight - timedelta(days=midnight.weekday())


def _aware(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment


def session_star_unit(status: str, block_results: list, reveals: int) -> dict:
    """One session as the unit shape `stars_from_units` already scores.

    Topic and crown points apply only when the session is completed.
    Block points come from passed and revealed outcomes stored on that session.
    """
    rows = [item for item in block_results if isinstance(item, dict)]
    passed = [item for item in rows if item.get("outcome") == "passed"]
    revealed_rows = [item for item in rows if item.get("outcome") == "revealed"]
    first_try = 0
    for item in passed:
        try:
            attempts = int(item.get("attempts") or 1)
        except (TypeError, ValueError):
            attempts = 1
        if attempts <= 1:
            first_try += 1
    revealed = max(len(revealed_rows), int(reveals or 0))
    finished = status == "completed"
    mastery = ""
    if finished:
        mastery = "fragile" if revealed else "known"
    return {
        "patch": False,
        "status": "completed" if finished else ("in_progress" if rows else "not_started"),
        "mastery": mastery,
        "completed_blocks": len(passed) + len(revealed_rows),
        "first_try_blocks_count": first_try,
        "revealed_blocks_count": revealed if finished else len(revealed_rows),
    }


def _empty_week() -> dict:
    return {
        "sessions": 0,
        "topics_finished": 0,
        "stars": 0,
        "blocks_passed": 0,
        "blocks_revealed": 0,
        "days_active": 0,
    }


def _outcome_counts(block_results: object) -> tuple[int, int]:
    """Passed and revealed blocks stored on one session. Other outcomes are skipped."""
    rows = block_results if isinstance(block_results, list) else []
    passed = 0
    revealed = 0
    for item in rows:
        if not isinstance(item, dict):
            continue
        outcome = item.get("outcome")
        if outcome == "passed":
            passed += 1
        elif outcome == "revealed":
            revealed += 1
    return passed, revealed


def _week_counts(rows: list[KcSession]) -> dict[uuid.UUID, dict]:
    """Sessions touched this week, plus stars for topics completed this week.

    A topic counts once. When several completed sessions share it, the newest
    session's star total is the one that counts. In-progress chats count as
    sessions and do not add stars. Passed blocks, revealed blocks, and the
    New York days with a chat are counted from every row already loaded.
    """
    counts: dict[uuid.UUID, dict] = {}
    seen: set[tuple[uuid.UUID, uuid.UUID]] = set()
    active_days: dict[uuid.UUID, set] = {}
    ordered = sorted(rows, key=lambda row: (_aware(row.updated_at), row.id), reverse=True)
    for row in ordered:
        bucket = counts.get(row.student_id)
        if bucket is None:
            bucket = _empty_week()
            counts[row.student_id] = bucket
        bucket["sessions"] += 1
        passed, revealed = _outcome_counts(row.block_results)
        bucket["blocks_passed"] += passed
        bucket["blocks_revealed"] += revealed
        active_days.setdefault(row.student_id, set()).add(
            _aware(row.updated_at).astimezone(PARENT_WEEK_ZONE).date()
        )
        if row.status != "completed":
            continue
        key = (row.student_id, row.kc_id)
        if key in seen:
            continue
        seen.add(key)
        bucket["topics_finished"] += 1
        results = row.block_results if isinstance(row.block_results, list) else []
        unit = session_star_unit(row.status, results, int(row.reveals or 0))
        bucket["stars"] += int(stars_from_units([unit])["stars"])
    for student_id, bucket in counts.items():
        bucket["days_active"] = len(active_days.get(student_id, ()))
    return counts


def _as_uuid(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str) and value:
        try:
            return uuid.UUID(value)
        except ValueError:
            return None
    return None


def _as_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return _aware(value)
    if isinstance(value, str) and value:
        try:
            return _aware(datetime.fromisoformat(value))
        except ValueError:
            return None
    return None


def _attention_items(cards: list[dict]) -> list[dict]:
    """At most three revisit lines: a fragile course, then that card's opportunities.

    Later cards are dropped once three lines are filled. The text is the course
    or component title and a short detail, never a chat message.
    """
    items: list[dict] = []

    def add(course_id: object, title: object, detail: object) -> None:
        if len(items) >= 3:
            return
        parsed = _as_uuid(course_id)
        if parsed is None:
            return
        items.append(
            {
                "course_id": parsed,
                "title": str(title or "").strip() or "Course",
                "detail": str(detail or "").strip(),
            }
        )

    for card in cards:
        fragile = int(card.get("fragile_count") or 0)
        if fragile > 0:
            noun = "topic" if fragile == 1 else "topics"
            add(card.get("id"), card.get("title"), f"{fragile} {noun} completed but still fragile")
        for opp in card.get("opportunities_preview") or []:
            if len(items) >= 3:
                return items
            if not isinstance(opp, dict):
                continue
            add(card.get("id"), opp.get("component_title") or card.get("title"), opp.get("summary") or "")
        if len(items) >= 3:
            return items
    return items


def _child_progress(cards: list[dict]) -> dict:
    started = [card for card in cards if card.get("started")]
    finished = [card for card in cards if card.get("course_complete")]
    open_courses = [card for card in started if not card.get("course_complete")]
    open_courses.sort(key=lambda card: str(card.get("last_active_at") or ""), reverse=True)
    current = open_courses[0] if open_courses else None
    topic = current.get("current_topic") if current else None
    topic_title = ""
    if isinstance(topic, dict):
        topic_title = str(topic.get("title") or "")
    return {
        "courses_started": len(started),
        "courses_finished": len(finished),
        "stars": sum(int(card.get("stars") or 0) for card in cards),
        "finished_topics": sum(int(card.get("finished_topic_count") or 0) for card in cards),
        "topics_mastered": sum(int(card.get("known_count") or 0) for card in cards),
        "topics_fragile": sum(int(card.get("fragile_count") or 0) for card in cards),
        "current_course_id": _as_uuid(current.get("id")) if current else None,
        "current_course_title": str(current.get("title") or "") if current else "",
        "current_topic_title": topic_title,
        "last_active_at": _as_datetime(current.get("last_active_at")) if current else None,
        "attention": _attention_items(cards),
    }


def parent_dashboard(db: Session, parent_id: uuid.UUID, *, now: datetime | None = None) -> ParentDashboardOut:
    """One read for the parent home: last 10 chats, progress, and this week.

    Stars in `week` are the star total of topics completed since Monday, using
    the same point values as the child view. They are not a lifetime total.
    Passed blocks, revealed blocks, and days with a chat come from those week
    rows. Attention is at most three lines and carries no chat text.
    """
    parent_or_404(db, parent_id)
    students = linked_students(db, parent_id)
    start = parent_week_start(now)
    if not students:
        return ParentDashboardOut(week_starts_at=start, recent=[], children=[])
    ids = [student.id for student in students]
    recent_rows = db.scalars(
        select(KcSession)
        .where(KcSession.student_id.in_(ids))
        .options(
            joinedload(KcSession.student),
            joinedload(KcSession.goal),
            joinedload(KcSession.component),
        )
        .order_by(KcSession.updated_at.desc(), KcSession.id.desc())
        .limit(10)
    ).unique().all()
    week_rows = db.scalars(
        select(KcSession).where(KcSession.student_id.in_(ids), KcSession.updated_at >= start)
    ).all()
    weeks = _week_counts(week_rows)
    cards = _ready_course_cards(db, students)
    children: list[ParentDashboardChild] = []
    for student in students:
        progress = _child_progress(cards.get(student.id, []))
        week = weeks.get(student.id, _empty_week())
        children.append(
            ParentDashboardChild(
                student_id=student.id,
                display_name=student.display_name,
                week=ParentWeekCounts(**week),
                **progress,
            )
        )
    recent = [
        ParentDashboardActivity(
            id=row.id,
            student_id=row.student_id,
            student_display_name=row.student.display_name if row.student is not None else "",
            course_id=row.goal_id,
            course_title=row.goal.title if row.goal is not None else "",
            kc_title=row.component.title if row.component is not None else "",
            status=row.status,
            updated_at=_aware(row.updated_at),
        )
        for row in recent_rows
    ]
    return ParentDashboardOut(week_starts_at=start, recent=recent, children=children)
