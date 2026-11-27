# F4 — Dynamic Block Policy Router (`select_next_block`)

Implemented with **zero database migrations** on top of live F3 (`047`), F2 (`048`), and F6 (`049`).

## Standing Rules Enforced
- **One scale, no second ICAP number:** Demand derives deterministically from block type (`HIGH_DEMAND_BLOCKS` vs. `LOWER_DEMAND_BLOCKS`) and `KcNode.mastery_spec.claims`.
- **Legacy-course safety:** When `mastery_spec` is empty (`{}`), routing falls back cleanly to sequential order (`index + 1`).
- **Frozen session snapshot:** Modality affinity is copied once from `StudentEducationalState.block_affinity` when a real session opens (`active_block_state.frozen_modality_affinity`), never queried live mid-component. Harness children do not read learner state.
- **Exact forecast/resolve parity:** Both `resolve_block_turn()` and `forecast_this_turn()` route through `select_next_block()`.
- **No fabricated F3 skill evidence:** Blocks marked `outcome = "fast_tracked"` earn non-fragile completion credit (`_walk_fragile`, `_last_block_finished`, `block_score`) while F3's `analyze_component_close()` strictly skips them so skipped blocks never create fake skill observations or affinity counts.

## Three Routing Policies
1. **Dylan Rule (Fast-Track Compression):** Unassisted Try-1 pass (`reveals == 0`, `attempts <= 1`) on a high-demand block with `confidence == "high"` or `affect in ("bored", "curious_stretch")` marks downstream lower-demand blocks whose `claim_ids` are already covered as `outcome = "fast_tracked"` and jumps straight to the next uncovered claim or capstone.
2. **Struggle Modality Pivot:** On `outcome == "revealed"` or `affect == "frustrated"`, selects the remaining unstarted block whose modality has a strictly higher Laplace-smoothed independent success rate in `frozen_modality_affinity`, returning later to complete any skipped blocks before closing.
3. **Broken-KC Prerequisite Redirect:** When a revealed miss matches a misconception with a `broken_kc` code, closes cleanly with `decision = "redirect"`, `redirect = True`, `mark_fragile = True`, and persists `kc_sessions.redirect_kc_id`.

## Key Files
- Router & forecast parity: `apps/api/app/kc_loop.py` (`select_next_block`, `_advance_or_close_component`, `forecast_this_turn`)
- Affect vocabulary: `apps/api/app/kc_prompt.py`, `apps/api/app/kc_moves.py` (`bored`, `curious_stretch`)
- Scoring, closure, redirect & frozen affinity: `apps/api/app/block_score.py`, `apps/api/app/kc.py`, `apps/api/app/graph2/signals.py`
- Tests: `apps/api/tests/test_f4_dynamic_router.py`
