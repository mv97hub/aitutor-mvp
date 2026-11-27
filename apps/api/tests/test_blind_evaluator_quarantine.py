"""AST-enforced quarantine tests for F2 (apps/api/app/blind_evaluator.py).

Guarantees:
1. `blind_evaluator.py` never imports `kc_prompt`, `kc_loop`, `kc`, `block_score`, or `graph2`.
2. `blind_evaluator.py` never imports or references `KcSession`, `KcMessage`, `KcModelPrompt`,
   `HarnessChat`, `HarnessTurn`, or `KcState`.
3. `blind_evaluator.py` never accesses `.blocks` or string key `"blocks"` on any node/dict.
4. Neither `kc_prompt.py` nor `kc_loop.py` imports `blind_evaluator` (the live tutor never sees the exam).
"""

from __future__ import annotations

import ast
from pathlib import Path

API_APP = Path(__file__).resolve().parents[1] / "app"

FORBIDDEN_MODULE_PREFIXES = (
    "app.kc_prompt",
    "app.kc_loop",
    "app.kc",
    "app.block_score",
    "app.graph2",
    "app.harness",
    "kc_prompt",
    "kc_loop",
    "block_score",
    "graph2",
)

FORBIDDEN_IDENTIFIERS = {
    "KcSession",
    "KcMessage",
    "KcModelPrompt",
    "HarnessChat",
    "HarnessTurn",
    "KcState",
    "kc_prompt",
    "kc_loop",
    "block_score",
}


def _parse(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_blind_evaluator_has_zero_forbidden_imports_or_runtime_reads() -> None:
    tree = _parse(API_APP / "blind_evaluator.py")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for bad in FORBIDDEN_MODULE_PREFIXES:
                    assert alias.name != bad and not alias.name.startswith(f"{bad}."), (
                        f"blind_evaluator.py imported forbidden module {alias.name!r}"
                    )
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for bad in FORBIDDEN_MODULE_PREFIXES:
                assert mod != bad and not mod.startswith(f"{bad}."), (
                    f"blind_evaluator.py imported from forbidden module {mod!r}"
                )
            for alias in node.names:
                assert alias.name not in FORBIDDEN_IDENTIFIERS, (
                    f"blind_evaluator.py imported forbidden symbol {alias.name!r}"
                )
        elif isinstance(node, ast.Name):
            assert node.id not in FORBIDDEN_IDENTIFIERS, (
                f"blind_evaluator.py referenced forbidden identifier {node.id!r}"
            )
        elif isinstance(node, ast.Attribute):
            assert node.attr != "blocks", "blind_evaluator.py must never access `.blocks`"
            assert node.attr not in FORBIDDEN_IDENTIFIERS, (
                f"blind_evaluator.py accessed forbidden attribute {node.attr!r}"
            )
        elif isinstance(node, ast.Subscript):
            sl = node.slice
            if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
                assert sl.value.lower() != "blocks", "blind_evaluator.py must never read ['blocks']"
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "getattr" and len(node.args) >= 2:
                arg = node.args[1]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    assert arg.value.lower() != "blocks", "blind_evaluator.py must never getattr(..., 'blocks')"


def test_live_tutor_never_imports_blind_evaluator() -> None:
    for rel in ("kc_prompt.py", "kc_loop.py"):
        tree = _parse(API_APP / rel)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "blind_evaluator" not in alias.name, f"{rel} must not import blind_evaluator"
            elif isinstance(node, ast.ImportFrom):
                assert "blind_evaluator" not in (node.module or ""), f"{rel} must not import blind_evaluator"
