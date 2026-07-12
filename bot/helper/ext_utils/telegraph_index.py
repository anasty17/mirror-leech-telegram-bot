"""
Telegraph index builder for BuzzHeavier multi-file uploads.

Ported logic from torrent_bot/modules/telegraph.py (series / file-type
sorting), re-emitted as HTML so it plugs into mirrorbot's existing
``TelegraphHelper.create_page(title, html_content)``.

Behaviour (mirrors torrent_bot):
  • < 2 files  -> caller skips Telegraph entirely (single Cloud Link).
  • >= 2 files -> build one Telegraph page:
      - if >=40% of files look like a series (S01E01 / 1x01 / E01) -> group
        Season -> Episode (video first, subtitles after).
      - else -> group by file type (Video, Audio, Subtitles, ...).
"""

import re
from typing import List, Optional, Tuple

VIDEO_EXTS = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".m4v", ".ts", ".webm", ".flv", ".m2ts"}
SUBTITLE_EXTS = {".srt", ".ass", ".ssa", ".sub", ".vtt", ".idx", ".sup", ".pgs"}
AUDIO_EXTS = {".mp3", ".flac", ".aac", ".opus", ".m4a", ".ogg", ".wav", ".wma", ".dts", ".ac3"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}
DOC_EXTS = {".pdf", ".doc", ".docx", ".txt", ".nfo", ".md", ".epub", ".mobi"}
ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"}

CATEGORY_ORDER = ["video", "audio", "subtitle", "archive", "image", "document", "other"]

CATEGORY_ICON = {
    "video": "🎬",
    "audio": "🎵",
    "subtitle": "📄",
    "archive": "📦",
    "image": "🖼",
    "document": "📃",
    "other": "📁",
}

CATEGORY_LABEL = {
    "video": "Video",
    "audio": "Audio",
    "subtitle": "Subtitles",
    "archive": "Archives",
    "image": "Images",
    "document": "Documents",
    "other": "Other",
}

# Season + Episode:  S01E01  S1E01  1x01  01x01
_RE_SE = re.compile(r"[Ss](\d{1,2})[Ee](\d{1,2})|(\d{1,2})x(\d{1,2})")
# Episode only:  E01  Ep01  Episode.01  (not preceded by another digit)
_RE_EP = re.compile(r"(?<!\d)(?:[Ee][Pp]?|[Ee]pisode[\s._-]?)(\d{1,3})(?!\d)", re.IGNORECASE)


def _ext(filename: str) -> str:
    parts = filename.rsplit(".", 1)
    return ("." + parts[-1].lower()) if len(parts) > 1 else ""


def _categorize(filename: str) -> str:
    e = _ext(filename)
    if e in VIDEO_EXTS:
        return "video"
    if e in SUBTITLE_EXTS:
        return "subtitle"
    if e in AUDIO_EXTS:
        return "audio"
    if e in IMAGE_EXTS:
        return "image"
    if e in DOC_EXTS:
        return "document"
    if e in ARCHIVE_EXTS:
        return "archive"
    return "other"


def _detect_episode(filename: str) -> Optional[Tuple[Optional[int], int]]:
    """Return (season, episode) or (None, episode) or None."""
    m = _RE_SE.search(filename)
    if m:
        if m.group(1):  # Sxx Exx
            return (int(m.group(1)), int(m.group(2)))
        return (int(m.group(3)), int(m.group(4)))
    m = _RE_EP.search(filename)
    if m:
        return (None, int(m.group(1)))
    return None


def _is_series(files: List[Tuple[str, str, int]]) -> bool:
    if not files:
        return False
    hits = sum(1 for f, _, _ in files if _detect_episode(f))
    return hits >= max(1, len(files) * 0.4)


def _fmt_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return ""
    units = ["B", "KB", "MB", "GB", "TB"]
    i, val = 0, float(size_bytes)
    while val >= 1024 and i < len(units) - 1:
        val /= 1024
        i += 1
    return f"{val:.2f} {units[i]}"


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _li(label: str, href: Optional[str]) -> str:
    if href:
        return f'<li><a href="{_escape(href)}" target="_blank">{_escape(label)}</a></li>'
    return f"<li>{_escape(label)}</li>"


def _build_series_html(files: List[Tuple[str, str, int]]) -> str:
    from collections import defaultdict

    by_season = defaultdict(lambda: defaultdict(list))
    no_ep = []
    for fname, url, size in files:
        ep = _detect_episode(fname)
        if ep:
            s, e = ep
            by_season[s if s is not None else 0][e].append((fname, url, size))
        else:
            no_ep.append((fname, url, size))

    out = []
    for season in sorted(by_season):
        heading = "📺 Episodes" if season == 0 else f"📺 Season {season}"
        out.append(f"<h3>{heading}</h3>")
        items = []
        for ep_num in sorted(by_season[season]):
            ep_files = sorted(
                by_season[season][ep_num],
                key=lambda x: (
                    0 if _categorize(x[0]) == "video" else 1 if _categorize(x[0]) == "subtitle" else 2,
                    x[0].lower(),
                ),
            )
            for fname, url, size in ep_files:
                size_str = f" ({_fmt_size(size)})" if size > 0 else ""
                label = f"{CATEGORY_ICON.get(_categorize(fname), '🔗')} E{ep_num:02d} — {fname}{size_str}"
                items.append(_li(label, url or None))
        out.append(f"<ul>{''.join(items)}</ul><br>")
    if no_ep:
        out.append("<h3>📁 Other Files</h3>")
        items = [_li(f"{f} ({_fmt_size(sz)})" if sz > 0 else f, u or None) for f, u, sz in no_ep]
        out.append(f"<ul>{''.join(items)}</ul><br>")
    return "".join(out)


def _build_filetype_html(files: List[Tuple[str, str, int]]) -> str:
    from collections import defaultdict

    grouped = defaultdict(list)
    ext_sets = defaultdict(set)
    for fname, url, size in files:
        cat = _categorize(fname)
        grouped[cat].append((fname, url, size))
        e = _ext(fname)
        if e:
            ext_sets[cat].add(e)

    out = []
    for cat in CATEGORY_ORDER:
        if cat not in grouped:
            continue
        exts_str = ", ".join(sorted(e.upper().lstrip(".") for e in ext_sets[cat]))
        icon = CATEGORY_ICON[cat]
        label = CATEGORY_LABEL[cat]
        heading = f"{icon} {label} ({exts_str})" if exts_str else f"{icon} {label}"
        out.append(f"<h3>{heading}</h3>")
        items = sorted(grouped[cat], key=lambda x: x[0].lower())
        lis = [
            _li(f"{f} ({_fmt_size(sz)})" if sz > 0 else f, u or None)
            for f, u, sz in items
        ]
        out.append(f"<ul>{''.join(lis)}</ul><br>")
    return "".join(out)


def build_telegraph_index_html(files: List[Tuple[str, str, int]]) -> str:
    """
    Build Telegraph HTML content for a list of (filename, url, size) tuples.
    Returns HTML string (may be empty if no files).
    """
    pairs = [(f, u, s) for f, u, s in files if u]
    if len(pairs) < 2:
        return ""
    if _is_series(pairs):
        return _build_series_html(pairs)
    return _build_filetype_html(pairs)
