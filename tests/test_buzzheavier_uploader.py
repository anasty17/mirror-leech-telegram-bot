"""Unit tests for the current BuzzHeavier uploader implementation."""

from __future__ import annotations

import asyncio
import importlib
import os
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def buzzheavier_module(monkeypatch):
    project_root = Path(__file__).resolve().parent.parent

    bot_pkg = ModuleType("bot")
    bot_pkg.__path__ = []
    config_pkg = ModuleType("bot.core")
    config_pkg.__path__ = []
    config_manager = ModuleType("bot.core.config_manager")

    class Config:
        BUZZHEAVIER_ACCOUNT_ID = ""

    config_manager.Config = Config

    helper_pkg = ModuleType("bot.helper")
    helper_pkg.__path__ = []
    ext_utils_pkg = ModuleType("bot.helper.ext_utils")
    ext_utils_pkg.__path__ = []

    bot_utils = ModuleType("bot.helper.ext_utils.bot_utils")

    async def sync_to_async(func, *args, **kwargs):
        return func(*args, **kwargs)

    bot_utils.sync_to_async = sync_to_async

    files_utils = ModuleType("bot.helper.ext_utils.files_utils")
    files_utils.get_mime_type = lambda _: "application/octet-stream"

    mlu_pkg = ModuleType("bot.helper.mirror_leech_utils")
    mlu_pkg.__path__ = []
    upload_utils_pkg = ModuleType(
        "bot.helper.mirror_leech_utils.upload_utils"
    )
    upload_utils_pkg.__path__ = [
        str(
            project_root
            / "bot"
            / "helper"
            / "mirror_leech_utils"
            / "upload_utils"
        )
    ]

    monkeypatch.setitem(sys.modules, "bot", bot_pkg)
    monkeypatch.setitem(sys.modules, "bot.core", config_pkg)
    monkeypatch.setitem(sys.modules, "bot.core.config_manager", config_manager)
    monkeypatch.setitem(sys.modules, "bot.helper", helper_pkg)
    monkeypatch.setitem(sys.modules, "bot.helper.ext_utils", ext_utils_pkg)
    monkeypatch.setitem(sys.modules, "bot.helper.ext_utils.bot_utils", bot_utils)
    monkeypatch.setitem(sys.modules, "bot.helper.ext_utils.files_utils", files_utils)
    monkeypatch.setitem(sys.modules, "bot.helper.mirror_leech_utils", mlu_pkg)
    monkeypatch.setitem(
        sys.modules,
        "bot.helper.mirror_leech_utils.upload_utils",
        upload_utils_pkg,
    )

    module_name = (
        "bot.helper.mirror_leech_utils.upload_utils.buzzheavier_uploader"
    )
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def _make_listener():
    return SimpleNamespace(
        is_cancelled=False,
        size=0,
        up_dest="bh",
        user_dict={},
        on_upload_complete=AsyncMock(),
        on_upload_error=AsyncMock(),
    )


class _FakeClient:
    def __init__(self, *args, **kwargs):
        self.closed = False

    async def aclose(self):
        self.closed = True


@pytest.mark.asyncio
async def test_upload_walks_directory(buzzheavier_module, tmp_path, monkeypatch):
    file_a = tmp_path / "a.bin"
    file_b = tmp_path / "sub" / "b.bin"
    file_b.parent.mkdir()
    file_a.write_bytes(b"a" * 16)
    file_b.write_bytes(b"b" * 16)

    listener = _make_listener()
    uploader = buzzheavier_module.BuzzHeavierUploader(listener, str(tmp_path))

    monkeypatch.setattr(buzzheavier_module, "AsyncClient", _FakeClient)
    monkeypatch.setattr(
        uploader, "_create_directory", AsyncMock(return_value="root-id")
    )

    uploaded = []

    async def fake_upload_file(file_path, parent_id):
        uploaded.append((os.path.basename(file_path), parent_id))
        uploader._files += 1
        return f"https://buzzheavier.com/{os.path.basename(file_path)}"

    monkeypatch.setattr(uploader, "_upload_file", fake_upload_file)

    await uploader.upload()

    assert sorted(name for name, _ in uploaded) == ["a.bin", "b.bin"]
    listener.on_upload_error.assert_not_awaited()
    listener.on_upload_complete.assert_awaited_once()
    args = listener.on_upload_complete.await_args.args
    assert args[0] == "https://buzzheavier.com/root-id"
    assert args[1] == 2
    assert args[3] == "Folder"


@pytest.mark.asyncio
async def test_upload_reports_setup_error(buzzheavier_module, tmp_path, monkeypatch):
    listener = _make_listener()
    uploader = buzzheavier_module.BuzzHeavierUploader(listener, str(tmp_path))
    monkeypatch.setattr(buzzheavier_module, "AsyncClient", _FakeClient)
    monkeypatch.setattr(
        uploader,
        "_create_directory",
        AsyncMock(side_effect=RuntimeError("create failed")),
    )

    await uploader.upload()

    listener.on_upload_error.assert_awaited_once()
    listener.on_upload_complete.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_file_aborts_when_cancelled(
    buzzheavier_module, tmp_path
):
    file_a = tmp_path / "a.bin"
    file_a.write_bytes(b"a" * 32)
    listener = _make_listener()
    listener.is_cancelled = True
    uploader = buzzheavier_module.BuzzHeavierUploader(listener, str(file_a))

    with pytest.raises(asyncio.CancelledError):
        await anext(uploader._stream_file(str(file_a), 8))


def test_status_interface_exposed(buzzheavier_module, tmp_path):
    listener = _make_listener()
    uploader = buzzheavier_module.BuzzHeavierUploader(listener, str(tmp_path))
    assert uploader.processed_bytes == 0
    assert isinstance(uploader.speed, (int, float))


def test_config_account_id_is_used(buzzheavier_module, tmp_path, monkeypatch):
    monkeypatch.setattr(
        buzzheavier_module.Config, "BUZZHEAVIER_ACCOUNT_ID", "abc-123"
    )
    listener = _make_listener()
    uploader = buzzheavier_module.BuzzHeavierUploader(listener, str(tmp_path))
    assert uploader._account_id == "abc-123"


def test_mt_destination_requires_user_account(buzzheavier_module, tmp_path):
    listener = _make_listener()
    listener.up_dest = "mt:bh"
    with pytest.raises(ValueError, match="BUZZHEAVIER_ACCOUNT_ID"):
        buzzheavier_module.BuzzHeavierUploader(listener, str(tmp_path))
