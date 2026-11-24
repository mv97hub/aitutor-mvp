"""Archive proof. Unused code moves under app._legacy. Live callers stay."""

from app._legacy import LEGACY_ROUTES_ENABLED
from app._legacy.resolve_decision import Resolution, resolve_decision
from app.kc_moves import Move
from app.main import app


def _mounted_paths() -> list[str]:
    paths: list[str] = []
    for route in app.routes:
        router = getattr(route, "original_router", None)
        if router is None:
            path = getattr(route, "path", "")
            if path:
                paths.append(path)
            continue
        prefix = router.prefix or ""
        for item in router.routes:
            path = getattr(item, "path", "")
            if path:
                paths.append(path if path.startswith(prefix) else f"{prefix}{path}")
    return paths


def test_legacy_routes_stay_off_and_the_app_still_imports() -> None:
    assert LEGACY_ROUTES_ENABLED is False
    assert not hasattr(__import__("app.kc_loop", fromlist=["kc_loop"]), "resolve_decision")
    paths = _mounted_paths()
    assert not any(path.startswith("/_legacy") for path in paths)
    # CreateCourse and the home kid session still call these mounts.
    assert any(path.startswith("/studio") for path in paths)
    assert any(path.startswith("/sessions") for path in paths)


def test_retired_move_resolver_still_runs() -> None:
    move = Move("retrieve", "Retrieve", ("fact",), False)
    same = resolve_decision(
        decision="advance",
        rubric_met=["fact"],
        stored_rubric=[],
        matched_wrong="The river is red.",
        move=move,
        step=0,
        moves=[move],
        move_attempts=0,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        enrichment="on_request",
        window_tries=2,
        last_misconception="The river is red.",
        fragment=False,
        self_explanation=False,
    )
    assert isinstance(same, Resolution)
    assert same.decision == "redirect"
    assert same.mark_fragile is True
    assert same.unit_complete is True
