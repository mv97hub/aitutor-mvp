# F6 — Active Parent Co-Pilot & Revocable Teacher Snapshot

Implemented on top of F3 (`047_graph2_skills_and_state`) and F2 (`048_blind_evaluator_tables`).

## Key Architectural Decisions
- **Reuse F3's `learner_course_state` table** (adding `course_mode` and `parent_policy_locks`) instead of introducing a parallel `student_course_policies` table, preserving a single source of truth per `(student_id, goal_id)`.
- **Zero mutation of shared `tutor_profiles` or active sessions:** Parent Co-Pilot locks write exclusively to `learner_course_state.parent_policy_locks` and are copied onto the **next** component's frozen session note (`copy_note_for_session_open`), never mid-lesson and never with radar numbers.
- **Strict privacy & harness isolation:**
  - Harness / test children (`student.is_test == True` or `HarnessChat` linkage) never persist `parent_session_digests` or `teacher_share_tokens`.
  - Teacher share tokens store **only** their SHA-256 hex digest (`token_hash`). The raw URL-safe token is displayed once at creation, revokes instantly to `404`, and exposes strictly read-only mastery, standards, active misconceptions, 8-skill radar, and F2 blind exam Hake gain (first name only; zero chat transcripts, prompts, or private parent controls).

## Key Files
- Migration: `apps/api/alembic/versions/049_parent_copilot_share.py` (`kc_goals` catalog metadata, `learner_course_state.course_mode` + `parent_policy_locks`, `parent_session_digests`, `teacher_share_tokens`)
- Backend service & routes: `apps/api/app/parent_copilot.py`, `apps/api/app/routes/parents.py`, `apps/api/app/routes/teacher_share.py`
- Component close & frozen-note hooks: `apps/api/app/kc.py`, `apps/api/app/graph2/state.py`
- Frontend Co-Pilot & Teacher Snapshot: `apps/web/lib/parent-copilot.ts`, `apps/web/components/parent/ParentCopilotPanel.tsx`, `apps/web/components/parent/ParentDashboard.tsx`, `apps/web/app/parent/[parentId]/page.tsx`, `apps/web/app/teacher/share/[token]/page.tsx`
- Tests: `apps/api/tests/test_parent_copilot_f6.py`, `apps/web/lib/parent-copilot.test.ts`
