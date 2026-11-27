# F2 — Quarantined Blind Pre/Post Evaluator

Implemented on top of F1 (`mastery_spec`) and F3 (`graph2`).

## Standing Rules
- **AST-enforced quarantine:** `apps/api/app/blind_evaluator.py` reads ONLY `KcGoal` (`id`, `code`, `title`, `description`, `audience`, `standards`, `target_kc_ids`) and `KcNode` (`id`, `code`, `title`, `description`, `core_truth`, `mastery_spec`). It never imports `kc_prompt`, `kc_loop`, `kc`, `block_score`, or `graph2`, and never accesses `.blocks`, `KcSession`, `KcMessage`, or `KcModelPrompt`.
- **Tutor isolation:** The live tutor never imports `blind_evaluator` and never sees exam items or pre/post scores.
- **40 / 30 / 30 isomorphic forms:** Frozen per `(goal_id, phase, spec_fingerprint)` (`scenario_mcq` 40%, `misconception_trap` 30%, `short_transfer` 30%). Answer keys (`correct_choice_id`, `trap_rationale`, `rubric_key`, `key_points`) are never sent to learner clients.
- **Hake normalized gain:** `g = (post - pre) / max(1.0 - pre, 0.05)`.
- **Epistemic-sandbox mode:** Optional `run_blind_post_test` in `harness.py` extracts only the tutor's assistant messages from either a single `HarnessChat` (`/kc/harness/chats/{chat_id}/epistemic-context`) or all completed components of one course in a `HarnessRun` (`/kc/harness/runs/{run_id}/epistemic-context`), runs a blank-slate exam agent, and records `mode='epistemic_sandbox'` without mutating real learner state.

## Key Files
- Migration: `apps/api/alembic/versions/048_blind_evaluator_tables.py` (`blind_exams`, `blind_exam_attempts`)
- Quarantined evaluator: `apps/api/app/blind_evaluator.py`
- API routes: `apps/api/app/routes/blind_exam.py`, `apps/api/app/routes/parents.py`, `apps/api/app/routes/harness.py`
- Next.js exam API & quiet UI: `apps/web/app/api/kc/exam/{prepare,submit,epistemic}/route.ts`, `apps/web/app/learn/[studentId]/course/[courseId]/exam/page.tsx`, `apps/web/components/learn/BlindExamClient.tsx`
- Tests: `apps/api/tests/test_blind_evaluator_quarantine.py`, `apps/api/tests/test_blind_evaluator.py`, `apps/web/lib/blind-exam.test.ts`
