"""Tests for the GoFile uploader result handling."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def gofile_module(monkeypatch):
    """Import GoFile uploader with its bot dependencies stubbed."""
    bot_pkg = ModuleType("bot")
    bot_pkg.__path__ = []
    core_pkg = ModuleType("bot.core")
    core_pkg.__path__ = []
    config_module = ModuleType("bot.core.config_manager")

    class Config:
        GOFILE_API_KEY = ""

    config_module.Config = Config
    helper_pkg = ModuleType("bot.helper")
    helper_pkg.__path__ = []
    ext_utils_pkg = ModuleType("bot.helper.ext_utils")
    ext_utils_pkg.__path__ = []
    bot_utils_module = ModuleType("bot.helper.ext_utils.bot_utils")
    async def sync_to_async(func, *args, **kwargs):
        return func(*args, **kwargs)

    bot_utils_module.sync_to_async = sync_to_async
    files_utils_module = ModuleType("bot.helper.ext_utils.files_utils")
    files_utils_module.get_mime_type = lambda path: "application/octet-stream"
    mirror_pkg = ModuleType("bot.helper.mirror_leech_utils")
    mirror_pkg.__path__ = []
    upload_pkg = ModuleType("bot.helper.mirror_leech_utils.upload_utils")
    upload_pkg.__path__ = [
        str(
            Path(__file__).resolve().parent.parent
            / "bot"
            / "helper"
            / "mirror_leech_utils"
            / "upload_utils"
        )
    ]

    modules = {
        "bot": bot_pkg,
        "bot.core": core_pkg,
        "bot.core.config_manager": config_module,
        "bot.helper": helper_pkg,
        "bot.helper.ext_utils": ext_utils_pkg,
        "bot.helper.ext_utils.bot_utils": bot_utils_module,
        "bot.helper.ext_utils.files_utils": files_utils_module,
        "bot.helper.mirror_leech_utils": mirror_pkg,
        "bot.helper.mirror_leech_utils.upload_utils": upload_pkg,
    }
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    module_name = "bot.helper.mirror_leech_utils.upload_utils.gofile_uploader"
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


class _FakeResponse:
    status_code = 200
    text = ""

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, responses):
        self._responses = iter(responses)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def get(self, *_args, **_kwargs):
        return next(self._responses)

    async def post(self, *_args, **_kwargs):
        return next(self._responses)


def _make_listener():
    return SimpleNamespace(
        is_cancelled=False,
        name="test-upload",
        on_upload_complete=AsyncMock(),
        on_upload_error=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_single_file_upload_reports_link_and_mime_type(
    gofile_module, tmp_path, monkeypatch
):
    file_path = tmp_path / "file.bin"
    file_path.write_bytes(b"data")
    listener = _make_listener()
    client = _FakeClient(
        [
            _FakeResponse({"status": "ok", "data": {"servers": [{"name": "store1"}]}}),
            _FakeResponse(
                {
                    "status": "ok",
                    "data": {"downloadPage": "https://gofile.io/d/test"},
                }
            ),
        ]
    )
    monkeypatch.setattr(gofile_module, "AsyncClient", lambda **_: client)
    monkeypatch.setattr(gofile_module, "get_mime_type", lambda _: "application/test")

    await gofile_module.GoFileUploader(listener, str(file_path)).upload()

    listener.on_upload_complete.assert_awaited_once_with(
        "https://gofile.io/d/test", 1, 0, "application/test"
    )
    listener.on_upload_error.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_reports_error_when_all_files_fail(
    gofile_module, tmp_path, monkeypatch
):
    file_path = tmp_path / "file.bin"
    file_path.write_bytes(b"data")
    listener = _make_listener()
    client = _FakeClient(
        [
            _FakeResponse({"status": "ok", "data": {"servers": [{"name": "store1"}]}}),
            _FakeResponse({"status": "error", "data": {}}),
        ]
    )
    monkeypatch.setattr(gofile_module, "AsyncClient", lambda **_: client)

    await gofile_module.GoFileUploader(listener, str(file_path)).upload()

    listener.on_upload_error.assert_awaited_once()
    listener.on_upload_complete.assert_not_awaited()
