"""Tests for the semprot thread scraper parsing helpers."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture
def semprot_module(monkeypatch):
    """Import ``semprot_scraper`` with minimal bot package stubs.

    Mirrors the stubbing in test_alldebrid_resolver.py to avoid the real
    bot/__init__.py side effects (uvloop, env, sockets).
    """
    project_root = Path(__file__).resolve().parent.parent

    bot_pkg = ModuleType("bot")
    bot_pkg.__path__ = []
    helper_pkg = ModuleType("bot.helper")
    helper_pkg.__path__ = []
    ext_utils_pkg = ModuleType("bot.helper.ext_utils")
    ext_utils_pkg.__path__ = []
    exceptions_mod = ModuleType("bot.helper.ext_utils.exceptions")

    class DirectDownloadLinkException(Exception):
        pass

    exceptions_mod.DirectDownloadLinkException = DirectDownloadLinkException

    mlu_pkg = ModuleType("bot.helper.mirror_leech_utils")
    mlu_pkg.__path__ = []
    download_utils_pkg = ModuleType("bot.helper.mirror_leech_utils.download_utils")
    download_utils_pkg.__path__ = [
        str(project_root / "bot" / "helper" / "mirror_leech_utils" / "download_utils")
    ]

    for name, mod in {
        "bot": bot_pkg,
        "bot.helper": helper_pkg,
        "bot.helper.ext_utils": ext_utils_pkg,
        "bot.helper.ext_utils.exceptions": exceptions_mod,
        "bot.helper.mirror_leech_utils": mlu_pkg,
        "bot.helper.mirror_leech_utils.download_utils": download_utils_pkg,
    }.items():
        monkeypatch.setitem(sys.modules, name, mod)

    sys.modules.pop(
        "bot.helper.mirror_leech_utils.download_utils.semprot_scraper", None
    )
    return importlib.import_module(
        "bot.helper.mirror_leech_utils.download_utils.semprot_scraper"
    )


_HTML = """
<html><head><title>Test Thread</title>
<link rel="canonical" href="https://www.semprot.com/threads/foo.123/"></head>
<body>
<a href="https://mega.nz/abc">m</a>
<a href="https://mediafire.com/x">mf</a>
<a href="/threads/foo.123/page-3">p3</a>
<a href="https://www.semprot.com/members/x">self</a>
<a href="https://gambar123.com/i.jpg">imghost</a>
<a href="mailto:a@b.com">mail</a>
<a href="#top">anchor</a>
<img class="bbImage" src="https://img.example/pic.jpg">
</body></html>
"""


def test_parse_extracts_external_links_only(semprot_module):
    title, canonical, last_page, links = semprot_module._parse(_HTML)
    assert title == "Test Thread"
    assert canonical.endswith("foo.123/")
    assert last_page == 3
    # semprot.com, gambar123.com, mailto, anchor, relative, and the bbImage
    # are all excluded — only genuine external download links remain.
    assert set(links) == {"https://mega.nz/abc", "https://mediafire.com/x"}


def test_is_external_rules(semprot_module):
    ext = semprot_module._is_external
    assert ext("https://mega.nz/x")
    assert not ext("/relative/path")
    assert not ext("mailto:a@b.com")
    assert not ext("#anchor")
    assert not ext("https://x.semprot.com/y")
    assert not ext("https://gambar123.com/i.jpg")
    assert not ext("ftp://host/file")


def test_page_num(semprot_module):
    assert semprot_module._page_num("/threads/x/page-7") == 7
    assert semprot_module._page_num("/threads/x/") == 0
