# F3 Architecture — Eight Skills, Biomarkers, Frozen Note & Shared Radar

This document summarizes the implemented F3 architecture in `mv97hub/aitutor-mvp` (built on Myuran's standalone F3 plan).

## Core Invariants

1. **One scale (`0–3` → `0–1`), no second ICAP number:** The single post-close batch judge grades eligible skills on `0–3` (`y = grade / 3`), deterministic caps apply before the slow EMA (`alpha = max(0.08, 1 / (n + 3))` from prior `0.50`), and the radar reads that `0–1` average.
2. **Strict package boundary (`apps/api/app/graph2/`):** `graph2/` never imports `kc_prompt.py`, `kc_loop.py`, `kc.py`, or `block_score.py` (enforced by AST test in `apps/api/tests/test_graph2_f3.py`).
3. **LLM calls stay in Next.js (`apps/web`):** FastAPI builds the batch judge prompt + strict JSON schema and validates/persists results; Next.js executes the single batch judge call inside `after()` in `apps/web/app/api/kc/tutor/answer/route.ts` **after** returning the closing reply and synchronous child end card. Model defaults to `GRAPH2_JUDGE_MODEL || tutor_model`.
4. **Harness quarantine:** Students with `is_test=True` or sessions linked to `harness_chats` are never written into `student_educational_state`, `learner_course_state`, or `skill_observation`.
5. **Tutor never sees the radar or a number:** `kc_prompt.py` appends `kc_sessions.frozen_tutor_note` (copied once at `open_session`, immutable for the entire component) verbatim in `"Who you are talking to"`.
6. **Backward compatibility:** Components with `mastery_spec == {}` produce zero skill updates, zero judge calls, and no end card. Claims with explicit `skills` lists (including `[]`) are authoritative; existing F1 claims without a `skills` key fall back to `mastery_spec.skills` intersected with the 11-block capability matrix.

## Module Map

| Layer | File | Responsibility |
| :--- | :--- | :--- |
| **Isolated Graph-2 Package** | `apps/api/app/graph2/signals.py` | Opportunity gate, 11-block skill matrix, word 3-gram overlap (exempting `passage_ela:cite_evidence`), `0.20`/`0.40` caps, 3 sync biomarkers (`own_words_pass`, `hard_recovery_pass`, `on_topic_inquiry_before_known`), affinity, expression, misconceptions, synchronous child end card (`<= 3` evidenced skills + quotes). |
| | `apps/api/app/graph2/judge.py` | Single-call 0–3 batch judge prompt + strict JSON schema + quote-grounding validator + 4th biomarker (`multi_perspective_synthesis`). |
| | `apps/api/app/graph2/state.py` | Harness guard, dual-plane DB persistence (`student_educational_state`, `learner_course_state`, append-only `skill_observation`), slow EMA (guaranteeing revealed blocks never raise a spoke), idempotency (`UNIQUE(session_id, skill)`), session-open note copy, shared radar payload (`< 3` obs hollow `"not enough yet"`). |
| | `apps/api/app/graph2/digest.py` | Frozen 3-line tutor note composer (Strength, Focus, Misconception) using plain-English skill directives with zero numbers or radar mentions. |
| **API & DB** | `apps/api/alembic/versions/047_graph2_skills_and_state.py` | Adds `student_educational_state`, `learner_course_state`, `skill_observation`, `kc_sessions.{frozen_tutor_note, close_end_card, graph2_judge_status}`, and `tutor_token_usage.kind = 'judge'`. |
| | `apps/api/app/routes/graph2.py` | `GET /kc/students/{student_id}/radar` and `POST /kc/tutor/sessions/{session_id}/graph2/judge-{prompt,result,failed}`. |
| | `apps/api/app/routes/parents.py` | `GET /parents/{parent_id}/children/{student_id}/radar` (same `build_radar_payload` behind `require_linked_child`). |
| **Call Sites** | `apps/api/app/kc_loop.py` | `record_substep_evidence` logs per-substep child/tutor lines, reveals/giveaways, and on-topic questions onto `active_block_state` → sealed onto `block_results`. |
| | `apps/api/app/kc.py` | Copies `frozen_tutor_note` on `open_session`, runs sync close on component completion, returns `end_card` and `graph2_judge_pending`. |
| | `apps/api/app/kc_prompt.py` | Appends `frozen_tutor_note` verbatim in `_who_you_are_talking_to`; preserves `claim_ids` in `stored_blocks`. |
| **Web UI & Async Judge** | `apps/web/app/api/kc/tutor/answer/route.ts` | Runs single post-close batch judge via `after()` without blocking the child's closing reply. |
| | `apps/web/components/learn/SkillEndCard.tsx` | Renders child end card (`<= 3` evidenced skills + quotes) on completed components in `KcLesson.tsx`. |
| | `apps/web/components/progress/SkillRadar.tsx` | Shared 8-spoke SVG radar (hollow spokes labeled `"not enough yet"`, never plotting `0.50`) used in `KcCourseProgress.tsx` and `ParentDashboard.tsx` (never in live chat). |
