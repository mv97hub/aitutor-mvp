"""Knowledge-component studio and kid tutor. Catalog and kid chat stay on their own routes."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.kc import (
    _course_or_404,
    _node_or_404,
    _student_or_404,
    accept_model_turn,
    add_component,
    append_kc_model_prompt,
    apply_component,
    apply_decision,
    course_of_node,
    course_out,
    create_course,
    creator_prompt_for,
    creator_thread,
    delete_kc_course,
    delete_node,
    kc_chat_detail,
    kc_chat_summaries,
    kc_prompt_out,
    mark_node_complete,
    mark_ready,
    network,
    node_out,
    note_component_saved,
    bind_course_tutor,
    course_tutor_choice,
    learner_roster,
    open_session,
    progress,
    start_course,
    prompt_for,
    push_course,
    record_ai_push,
    record_speech,
    rename_component,
    reorder_course,
    restart_course,
    session_out,
    structure,
    turn,
    tutor_courses,
    tutor_variables,
    update_course,
)
from app.kc_course_draft import (
    answer_follow_ups,
    apply_chat,
    course_chat_prompt,
    delete_unit,
    preview_chat,
    pipeline_out,
    reset_pipeline,
    save_blueprint,
    save_statements,
    store_stage,
    stage_prompt,
)
from app.kc_course_io import (
    export_course,
    external_course_prompt,
    import_into_course,
    import_new_course,
    preview_document,
)
from app.kc_prompt_tester import PromptTesterIn, preview_kc_prompt
from app.schemas import KcChatDetail, KcChatSummary, ModelPromptIn, ModelPromptOut, TokenUsageIn, TokenUsageTurn
from app.token_usage import record_token_usage, usage_out, usage_report

router = APIRouter()


class CourseIn(BaseModel):
    title: str
    description: str = ""
    audience: str = "9-11"
    kind: str = "mastery"
    minutes: int | None = None
    code: str | None = None
    allowed_block_types: list[str] | None = None
    intake: dict | None = None


class CoursePatch(BaseModel):
    title: str | None = None
    description: str | None = None
    audience: str | None = None
    kind: str | None = None
    minutes: int | None = None
    allowed_block_types: list[str] | None = None
    intake: dict | None = None


class DraftIn(BaseModel):
    message: str = ""
    model: str = ""
    allowed_block_types: list[str] | None = None


class StagePromptIn(BaseModel):
    model: str = ""
    unit: int | None = None


class StageResultIn(BaseModel):
    result: dict
    unit: int | None = None


class BlueprintIn(BaseModel):
    blueprint: dict
    approve: bool = False


class StatementsIn(BaseModel):
    statements: list[dict | str] = Field(default_factory=list)
    confirm: bool = False


class AnswersIn(BaseModel):
    answers: list[dict] = Field(default_factory=list)
    skip: bool = False


class ChatPromptIn(BaseModel):
    model: str = ""
    messages: list[dict] = Field(default_factory=list)


class ChatApplyIn(BaseModel):
    proposal: dict


class CourseFileIn(BaseModel):
    document: dict
    mode: str = "replace"


class ExternalPromptIn(BaseModel):
    title: str = ""
    grade: str = ""
    audience: str = ""
    curriculum: str = ""
    block_notes: str = ""


def _course_file(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


class ModelTurnIn(BaseModel):
    message: str
    discussion: str = ""
    draft: dict
    allowed_block_types: list[str] | None = None


class PushCourseIn(BaseModel):
    components: list[dict]


class AddComponentIn(BaseModel):
    title: str


class ReorderIn(BaseModel):
    ids: list[str]


class RenameIn(BaseModel):
    title: str


class DeleteIn(BaseModel):
    password: str = ""


class ComponentIn(BaseModel):
    title: str | None = None
    description: str | None = None
    outline: str | None = None
    topics: list | None = None
    blocks: list[dict] = Field(default_factory=list)
    kc_type: str | None = None
    type_fields: dict = Field(default_factory=dict)
    core_truth: str = ""
    rubric: list[str] | None = None
    misconceptions: list[dict] = Field(default_factory=list)
    prerequisite_codes: list[str] = Field(default_factory=list)
    encompasses_codes: list[str] = Field(default_factory=list)


class OpenSessionIn(BaseModel):
    student_id: uuid.UUID
    course_id: uuid.UUID
    kc_id: uuid.UUID
    tutor_profile_id: str | int | None = None


class StartLearningIn(BaseModel):
    student_id: uuid.UUID
    course_id: uuid.UUID
    kc_id: uuid.UUID | None = None
    tutor_profile_id: str | int | None = None


class BindCourseTutorIn(BaseModel):
    student_id: uuid.UUID
    tutor_profile_id: str | int


class RestartCourseIn(BaseModel):
    student_id: uuid.UUID


class TurnIn(BaseModel):
    answer: str


class DecisionIn(BaseModel):
    reply: str
    decision: str
    substep_passed: bool = False
    block_complete: bool = False
    generated_mcq: dict | None = None
    rubric_met: list[str] = Field(default_factory=list)
    misconception: str | None = None
    hint_tier: str = "nudge"
    help_requested: bool = False
    off_course: bool = False
    affect: str = "engaged"
    confidence: str = "ok"
    score_justification: str = ""
    what_was_strong: str = ""
    what_to_work_on: str = ""
    justification: str = ""
    strong: str = ""
    work_on: str = ""
    safety_flag: str = "none"


class SpeechIn(BaseModel):
    content: str
    generated_mcq: dict | None = None
    safety_flag: str = "none"


@router.get("/kc/courses")
def list_courses(db: Session = Depends(get_db)) -> list[dict]:
    from sqlalchemy import select

    from app.models import KcGoal

    goals = db.scalars(select(KcGoal).order_by(KcGoal.title))
    return [course_out(db, goal) for goal in goals]


@router.post("/kc/courses")
def post_course(body: CourseIn, db: Session = Depends(get_db)) -> dict:
    goal = create_course(
        db,
        title=body.title,
        description=body.description,
        audience=body.audience,
        kind=body.kind,
        minutes=body.minutes,
        code=body.code,
        allowed_block_types=body.allowed_block_types,
        intake=body.intake,
    )
    return course_out(db, goal)


@router.post("/kc/courses/import-preview")
def post_import_preview(body: CourseFileIn) -> dict:
    try:
        return preview_document(body.document)
    except ValueError as exc:
        raise _course_file(exc) from exc


@router.post("/kc/courses/external-prompt")
def post_external_prompt(body: ExternalPromptIn) -> dict:
    return {
        "prompt": external_course_prompt(
            title=body.title,
            grade=body.grade,
            audience=body.audience,
            curriculum=body.curriculum,
            block_notes=body.block_notes,
        )
    }


@router.post("/kc/courses/import")
def post_course_import(body: CourseFileIn, db: Session = Depends(get_db)) -> dict:
    try:
        goal = import_new_course(db, body.document)
    except ValueError as exc:
        raise _course_file(exc) from exc
    return course_out(db, goal)


@router.get("/kc/courses/{course_id}")
def get_course(course_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return course_out(db, _course_or_404(db, course_id))


@router.patch("/kc/courses/{course_id}")
def patch_course(course_id: uuid.UUID, body: CoursePatch, db: Session = Depends(get_db)) -> dict:
    goal = _course_or_404(db, course_id)
    fields = body.model_dump(exclude_unset=True)
    return course_out(db, update_course(db, goal, fields))


@router.post("/kc/courses/{course_id}/draft-finish")
def post_course_draft_finish(course_id: uuid.UUID, body: FinishDraftIn, db: Session = Depends(get_db)) -> dict:
    goal = _course_or_404(db, course_id)
    return finish_model_course(goal, body.message, body.proposal, body.allowed_block_types)


@router.get("/kc/courses/{course_id}/pipeline")
def get_course_pipeline(course_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return pipeline_out(_course_or_404(db, course_id))


@router.delete("/kc/courses/{course_id}/pipeline")
def delete_course_pipeline(
    course_id: uuid.UUID, components: bool = False, db: Session = Depends(get_db)
) -> dict:
    return reset_pipeline(db, _course_or_404(db, course_id), clear_components=components)


@router.delete("/kc/courses/{course_id}/units/{unit_index}")
def delete_course_unit(course_id: uuid.UUID, unit_index: int, db: Session = Depends(get_db)) -> dict:
    return delete_unit(db, _course_or_404(db, course_id), unit_index)


@router.get("/kc/courses/{course_id}/export")
def get_course_export(course_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return export_course(db, _course_or_404(db, course_id))


@router.post("/kc/courses/{course_id}/import")
def post_course_file(course_id: uuid.UUID, body: CourseFileIn, db: Session = Depends(get_db)) -> dict:
    try:
        goal = import_into_course(db, _course_or_404(db, course_id), body.document, body.mode)
    except ValueError as exc:
        raise _course_file(exc) from exc
    return course_out(db, goal)


@router.post("/kc/courses/{course_id}/chat/prompt")
def post_course_chat_prompt(course_id: uuid.UUID, body: ChatPromptIn, db: Session = Depends(get_db)) -> dict:
    return course_chat_prompt(db, _course_or_404(db, course_id), body.model, body.messages)


@router.post("/kc/courses/{course_id}/chat/preview")
def post_course_chat_preview(course_id: uuid.UUID, body: ChatApplyIn, db: Session = Depends(get_db)) -> dict:
    return preview_chat(db, _course_or_404(db, course_id), body.proposal)


@router.post("/kc/courses/{course_id}/chat/apply")
def post_course_chat_apply(course_id: uuid.UUID, body: ChatApplyIn, db: Session = Depends(get_db)) -> dict:
    return apply_chat(db, _course_or_404(db, course_id), body.proposal)


@router.post("/kc/courses/{course_id}/pipeline/answers")
def post_pipeline_answers(course_id: uuid.UUID, body: AnswersIn, db: Session = Depends(get_db)) -> dict:
    return answer_follow_ups(db, _course_or_404(db, course_id), body.answers, body.skip)


@router.put("/kc/courses/{course_id}/pipeline/blueprint")
def put_pipeline_blueprint(course_id: uuid.UUID, body: BlueprintIn, db: Session = Depends(get_db)) -> dict:
    return save_blueprint(db, _course_or_404(db, course_id), body.blueprint, body.approve)


@router.put("/kc/courses/{course_id}/pipeline/standards")
def put_pipeline_standards(course_id: uuid.UUID, body: StatementsIn, db: Session = Depends(get_db)) -> dict:
    return save_statements(db, _course_or_404(db, course_id), body.statements, body.confirm)


@router.post("/kc/courses/{course_id}/pipeline/{stage}/prompt")
def post_pipeline_prompt(
    course_id: uuid.UUID, stage: str, body: StagePromptIn, db: Session = Depends(get_db)
) -> dict:
    return stage_prompt(db, _course_or_404(db, course_id), stage, body.model, body.unit)


@router.post("/kc/courses/{course_id}/pipeline/{stage}")
def post_pipeline_stage(
    course_id: uuid.UUID, stage: str, body: StageResultIn, db: Session = Depends(get_db)
) -> dict:
    return store_stage(db, _course_or_404(db, course_id), stage, body.result, body.unit)


@router.post("/kc/courses/{course_id}/push")
def post_course_push(course_id: uuid.UUID, body: PushCourseIn, db: Session = Depends(get_db)) -> dict:
    goal = _course_or_404(db, course_id)
    return course_out(db, push_course(db, goal, body.components))


@router.post("/kc/courses/{course_id}/components")
def post_component(course_id: uuid.UUID, body: AddComponentIn, db: Session = Depends(get_db)) -> dict:
    goal = _course_or_404(db, course_id)
    add_component(db, goal, body.title)
    return course_out(db, goal)


@router.post("/kc/courses/{course_id}/reorder")
def post_reorder(course_id: uuid.UUID, body: ReorderIn, db: Session = Depends(get_db)) -> dict:
    goal = _course_or_404(db, course_id)
    return course_out(db, reorder_course(db, goal, body.ids))


@router.get("/kc/courses/{course_id}/structure")
def get_structure(course_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return structure(db, _course_or_404(db, course_id))


@router.get("/kc/courses/{course_id}/network")
def get_network(course_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return network(db, _course_or_404(db, course_id))


@router.post("/kc/courses/{course_id}/delete")
def post_course_delete(course_id: uuid.UUID, body: DeleteIn, db: Session = Depends(get_db)) -> dict:
    delete_kc_course(db, _course_or_404(db, course_id), body.password)
    return {"deleted": True}


@router.post("/kc/courses/{course_id}/ready")
def post_ready(course_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    goal = _course_or_404(db, course_id)
    return course_out(db, mark_ready(db, goal))


@router.get("/kc/nodes/{node_id}")
def get_node(node_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return node_out(db, _node_or_404(db, node_id))


@router.put("/kc/nodes/{node_id}")
def put_node(node_id: uuid.UUID, body: ComponentIn, db: Session = Depends(get_db)) -> dict:
    node = apply_component(db, _node_or_404(db, node_id), body.model_dump())
    return node_out(db, node)


@router.patch("/kc/nodes/{node_id}")
def patch_node(node_id: uuid.UUID, body: RenameIn, db: Session = Depends(get_db)) -> dict:
    node = rename_component(db, _node_or_404(db, node_id), body.title)
    return node_out(db, node)


@router.post("/kc/nodes/{node_id}/complete")
def post_node_complete(node_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    node = mark_node_complete(db, _node_or_404(db, node_id))
    return node_out(db, node)


@router.get("/kc/nodes/{node_id}/thread")
def get_node_thread(node_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return creator_thread(db, _node_or_404(db, node_id))


@router.post("/kc/nodes/{node_id}/creator-prompt")
def post_creator_prompt(node_id: uuid.UUID, body: DraftIn, db: Session = Depends(get_db)) -> dict:
    return creator_prompt_for(
        db,
        _node_or_404(db, node_id),
        body.message,
        body.model,
        body.allowed_block_types,
    )


@router.post("/kc/nodes/{node_id}/model-turn")
def post_model_turn(node_id: uuid.UUID, body: ModelTurnIn, db: Session = Depends(get_db)) -> dict:
    return accept_model_turn(
        db,
        _node_or_404(db, node_id),
        body.message,
        body.discussion,
        body.draft,
        body.allowed_block_types,
    )


@router.post("/kc/nodes/{node_id}/push")
def post_node_push(node_id: uuid.UUID, body: ComponentIn, db: Session = Depends(get_db)) -> dict:
    node = apply_component(db, _node_or_404(db, node_id), body.model_dump())
    note_component_saved(db, node)
    record_ai_push(db, node)
    return node_out(db, node)


@router.delete("/kc/nodes/{node_id}")
def remove_node(node_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    delete_node(db, _node_or_404(db, node_id))
    return {"ok": True}


@router.get("/kc/tutor/courses")
def get_tutor_courses(
    student_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    return tutor_courses(db, student_id=student_id)


@router.get("/kc/tutor/learners")
def get_learners(db: Session = Depends(get_db)) -> list[dict]:
    return learner_roster(db)


@router.post("/kc/tutor/start")
def post_tutor_start(body: StartLearningIn, db: Session = Depends(get_db)) -> dict:
    student = _student_or_404(db, body.student_id)
    goal = _course_or_404(db, body.course_id)
    session = start_course(
        db,
        student,
        goal,
        tutor_profile_id=body.tutor_profile_id,
        kc_id=body.kc_id,
    )
    out = session_out(db, session)
    prog = progress(db, goal, student)
    out["stars"] = prog["stars"]
    out["course_stars"] = prog["stars"]
    return out


@router.post("/kc/tutor/courses/{course_id}/tutor")
def post_course_tutor(
    course_id: uuid.UUID,
    body: BindCourseTutorIn,
    db: Session = Depends(get_db),
) -> dict:
    student = _student_or_404(db, body.student_id)
    goal = _course_or_404(db, course_id)
    bind_course_tutor(db, student, goal, body.tutor_profile_id, update_preferred=True)
    return course_tutor_choice(db, student, goal.id)


@router.get("/kc/tutor/courses/{course_id}")
def get_tutor_course(
    course_id: uuid.UUID,
    student_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> dict:
    return progress(db, _course_or_404(db, course_id), _student_or_404(db, student_id))


@router.post("/kc/tutor/courses/{course_id}/restart")
def post_tutor_restart(
    course_id: uuid.UUID,
    body: RestartCourseIn,
    db: Session = Depends(get_db),
) -> dict:
    return restart_course(db, _course_or_404(db, course_id), _student_or_404(db, body.student_id))


@router.post("/kc/tutor/sessions")
def post_tutor_session(body: OpenSessionIn, db: Session = Depends(get_db)) -> dict:
    student = _student_or_404(db, body.student_id)
    goal = _course_or_404(db, body.course_id)
    node = _node_or_404(db, body.kc_id)
    return session_out(
        db,
        open_session(
            db,
            student,
            goal,
            node,
            tutor_profile_id=body.tutor_profile_id,
        ),
    )


def _session_or_404(db: Session, session_id: uuid.UUID):
    from app.models import KcSession

    row = db.get(KcSession, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="That session is not open.")
    return row


@router.get("/kc/tutor/sessions/{session_id}")
def get_tutor_session(session_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return session_out(db, _session_or_404(db, session_id))


@router.get("/kc/tutor/variables")
def get_tutor_variables(
    student_id: uuid.UUID | None = None,
    course_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    tutor_profile_id: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    from app.kc import _tutor_meta_dict
    from app.models import KcSession
    from app.tutor_profile import resolve_active_profile

    variables = tutor_variables(
        db,
        student_id=student_id,
        course_id=course_id,
        session_id=session_id,
        tutor_profile_id=tutor_profile_id,
    )
    sess = db.get(KcSession, session_id) if session_id is not None else None
    stud = (
        _student_or_404(db, sess.student_id)
        if sess is not None
        else (_student_or_404(db, student_id) if student_id is not None else None)
    )
    profile = resolve_active_profile(db, session=sess, student=stud, profile_id=tutor_profile_id)
    from app.models import effective_child_profile

    child = effective_child_profile(stud) if stud is not None else None
    return {
        "variables": variables,
        "tutor_model": "" if child is None else child["tutor_model"],
        **_tutor_meta_dict(profile),
    }


@router.get("/kc/tutor/sessions/{session_id}/prompt")
def get_tutor_prompt(session_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return prompt_for(db, _session_or_404(db, session_id))


@router.post("/kc/tutor/sessions/{session_id}/speech")
def post_tutor_speech(session_id: uuid.UUID, body: SpeechIn, db: Session = Depends(get_db)) -> dict:
    return record_speech(
        db,
        _session_or_404(db, session_id),
        body.content,
        body.generated_mcq,
        body.safety_flag,
    )


@router.post("/kc/tutor/sessions/{session_id}/turn")
def post_tutor_turn(session_id: uuid.UUID, body: TurnIn, db: Session = Depends(get_db)) -> dict:
    return turn(db, _session_or_404(db, session_id), body.answer)


@router.post("/kc/tutor/sessions/{session_id}/decision")
def post_tutor_decision(session_id: uuid.UUID, body: DecisionIn, db: Session = Depends(get_db)) -> dict:
    return apply_decision(db, _session_or_404(db, session_id), body.model_dump())


@router.get("/kc/sessions", response_model=list[KcChatSummary])
def list_kc_chats(
    student_id: uuid.UUID | None = None, db: Session = Depends(get_db)
) -> list[KcChatSummary]:
    return kc_chat_summaries(db, student_id)


@router.get("/kc/sessions/{session_id}", response_model=KcChatDetail)
def get_kc_chat(session_id: uuid.UUID, db: Session = Depends(get_db)) -> KcChatDetail:
    return kc_chat_detail(db, session_id)


@router.post("/kc/prompt-tester")
def post_prompt_tester(body: PromptTesterIn) -> dict:
    """Build the tutor prompt from the form. Does not write a session or change a course."""
    return preview_kc_prompt(body)


@router.post("/kc/admin/prompt-preview")
def post_admin_prompt_preview(body: PromptTesterIn) -> dict:
    """Alias for previewing the KC tutor prompt from admin tools."""
    return preview_kc_prompt(body)


@router.post("/kc/sessions/{session_id}/model-prompts", response_model=ModelPromptOut)
def post_kc_model_prompt(
    session_id: uuid.UUID, body: ModelPromptIn, db: Session = Depends(get_db)
) -> ModelPromptOut:
    return kc_prompt_out(
        append_kc_model_prompt(
            db,
            _session_or_404(db, session_id),
            body.system_prompt,
            list(body.messages),
            body.model,
            body.message_id,
            list(body.rubric_met),
            body.misconception,
        )
    )


@router.post("/kc/sessions/{session_id}/token-usage", response_model=TokenUsageTurn)
def post_token_usage(
    session_id: uuid.UUID, body: TokenUsageIn, db: Session = Depends(get_db)
) -> dict:
    return usage_out(
        record_token_usage(
            db,
            _session_or_404(db, session_id),
            kind=body.kind,
            model=body.model,
            input_tokens=body.input_tokens,
            output_tokens=body.output_tokens,
            cached_tokens=body.cached_tokens,
            message_id=body.message_id,
        )
    )


@router.get("/kc/token-usage")
def get_token_usage(
    student_id: uuid.UUID | None = None,
    start: date | None = None,
    end: date | None = None,
    all_time: bool = False,
    model: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    return usage_report(
        db,
        student_id=student_id,
        start=start,
        end=end,
        all_time=all_time,
        model=model,
    )
