"""Tests for the ``-ad`` CLI flag."""

from __future__ import annotations

import importlib
import sys
from types import ModuleType

import pytest


def _stub_bot_package(monkeypatch):
    bot_pkg = ModuleType("bot")
    bot_pkg.LOGGER = type("L", (), {"info": staticmethod(lambda *a, **k: None)})
    helper_pkg = ModuleType("bot.helper")
    ext_utils_pkg = ModuleType("bot.helper.ext_utils")
    monkeypatch.setitem(sys.modules, "bot", bot_pkg)
    monkeypatch.setitem(sys.modules, "bot.helper", helper_pkg)
    monkeypatch.setitem(sys.modules, "bot.helper.ext_utils", ext_utils_pkg)


@pytest.fixture
def arg_parser(monkeypatch):
    """Import only ``arg_parser`` from bot_utils without firing module-level
    side effects elsewhere in the package."""
    _stub_bot_package(monkeypatch)
    sys.modules.pop("bot.helper.ext_utils.bot_utils", None)
    # ``bot_utils`` itself imports several Telegram-only helpers, so we
    # load it from source via execfile-style trick to avoid pulling in
    # the full bot stack.
    from importlib import util
    from pathlib import Path

    file_path = (
        Path(__file__).resolve().parent.parent
        / "bot"
        / "helper"
        / "ext_utils"
        / "bot_utils.py"
    )
    src = file_path.read_text(encoding="utf-8")
    # Strip imports that drag in Telegram + DB dependencies; we only
    # need ``arg_parser`` for these tests.
    namespace: dict[str, object] = {}
    # Provide minimal stubs the function references.
    namespace["loads"] = __import__("ast").literal_eval
    snippet_start = src.find("def arg_parser(")
    snippet_end = src.find("\ndef ", snippet_start + 1)
    if snippet_end == -1:
        snippet_end = len(src)
    snippet = src[snippet_start:snippet_end]
    exec(snippet, namespace)  # noqa: S102 - test-only controlled exec
    return namespace["arg_parser"]


def test_ad_bool_flag_set(arg_parser):
    args = {"-ad": False, "-z": False, "link": ""}
    arg_parser(["http://x", "-ad"], args)
    assert args["-ad"] is True
    assert args["link"] == "http://x"



def test_unknown_flag_left_alone(arg_parser):
    args = {"-ad": False, "link": ""}
    arg_parser(["http://x", "-unknown"], args)
    assert args["-ad"] is False
