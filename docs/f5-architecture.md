# F5 — Jargon-Free Cold-Start DAG Placement & Bjork Memory Decay Warmups

Implemented cleanly on top of live F2 (`048`), F3 (`047`), F4, and F6 (`049`) via additive migration **`050_f5_placement_state`**.

## Schema Impact (`050_f5_placement_state`)
- Reuses F3/F6's single `(student_id, goal_id)` table `learner_course_state` by adding two backwards-compatible columns:
  - `placement_status` (`not_started | in_progress | completed | skipped`, default `not_started`)
  - `placement_state` (`JSON`, default `{}`)
- Zero changes to `kc_states` (reuses `status`, `stability`, `last_practiced`, `result`).

## Part A — Hint-Weighted Storage Strength & Bjork Forgetting Curve
- **Initial Storage Strength ($SS_k$) at component close (`initial_stability_for_session`):**
  - `1.00` — Attempt-1 independent pass
  - `0.70` — Attempt-2 or nudge-assisted pass
  - `0.45` — Attempt-3+ or scaffold/analogy-assisted pass
  - Preserves `+0.25` FIRe trickle onto encompassed ancestors and keeps `stability` strictly out of the live tutor prompt.
- **Live Wall-Clock Retrieval Strength (`retrieval_strength`):**
  - $RS_k(t) = \exp\left(-\Delta t_{\text{days}} / (7.0 \cdot SS_k)\right)$ computed on every `"known"` unit in `progress()`.
  - When `RS < 0.65`, `progress()` surfaces a 2-minute `retrieval_check` warmup in `warmups[]` (ordered most decayed first) without exposing the answer key.
  - Submitting a passing warmup via `POST /kc/tutor/courses/{course_id}/warmups/{kc_id}/submit` boosts storage strength:
    $$SS_k \leftarrow \text{round}(1.8 \cdot SS_k + 0.5, 2)$$
    and resets `last_practiced = now()`. Misses give a gentle refresher with zero penalty.

## Part B — Jargon-Free Topological Median DAG Placement (`kc_placement.py`)
- **Eligibility:** Ready, unstarted course with `>= 4` target components for a real learner (`is_test == False`).
- **2-Option Course Entry on `/learn`:** Children can choose *"Start from the beginning"* (`POST .../placement/skip`) or *"Find my starting spot"* (`POST .../placement/start`).
- **Topological Binary Search (`build_course_dag` + `answer_placement_probe`):**
  - Orders `target_kc_ids` topologically via `kc_edges(kind='prerequisite_of')` (with JSON `prerequisite_codes` fallback and cycle-safe Kahn ordering).
  - Probes the unsettled median node `v_med` with an everyday scenario question and a mandatory zero-shame `"Not sure yet — teach me this!"` option, converging in at most `min(4, ceil(log2(N)))` probes.
  - On pass: surmise-propagates `status='known'`, `stability=0.75`, `result={'source': 'placement_surmise'}` onto `v_med` and all transitive prerequisites $\text{Anc}(v_{\text{med}})$, narrowing to the upper half.
  - On miss or unsure: narrows gently to the lower half with zero penalty.
  - Converges on the ZPD outer fringe $O(K_0)$ and sets `learner_course_state.placement_status = 'completed'`.
  - Restarting a course (`restart_course`) cleanly resets `placement_status = 'not_started'` and `placement_state = {}`.

## Key Files
- Migration: `apps/api/alembic/versions/050_f5_placement_state.py`
- Backend engine: `apps/api/app/kc_placement.py`, `apps/api/app/kc.py`, `apps/api/app/routes/kc.py`, `apps/api/app/models.py`
- Frontend `/learn` UI: `apps/web/components/learn/CoursePlacementModal.tsx`, `apps/web/components/learn/MemoryWarmupCard.tsx`, `apps/web/components/learn/ChildHome.tsx`, `apps/web/components/learn/LearnQuestPanel.tsx`, `apps/web/components/KcTutor.tsx`, `apps/web/lib/kc.ts`
- Tests: `apps/api/tests/test_f5_placement_and_decay.py`, `apps/web/lib/__tests__/f5-placement.test.ts`
