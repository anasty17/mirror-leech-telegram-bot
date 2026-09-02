"""Regression tests for cancel-all callback authorization."""

from __future__ import annotations

import ast
from pathlib import Path


def test_cancel_all_update_returns_after_not_yours():
    source = (
        Path(__file__).resolve().parent.parent / "bot" / "modules" / "cancel_task.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)

    func = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "cancel_all_update"
    )

    auth_guard = next(
        node
        for node in func.body
        if isinstance(node, ast.If)
        and "query.from_user.id" in ast.unparse(node.test)
    )

    assert any(isinstance(stmt, ast.Return) for stmt in auth_guard.body), (
        "Unauthorized cancel-all callbacks must return immediately after "
        "showing the Not Yours alert."
    )
