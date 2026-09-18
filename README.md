<div align="center">

# ⚡ FileHub

### Unified Telegram download, processing & cloud transfer bot

A modern, self-hosted Telegram automation platform for downloading, processing, mirroring, cloning and uploading files across Telegram, torrents, direct links, Google Drive, rclone remotes and other supported sources.

[![Tests](https://github.com/RecklessEvadingDriver/mirror-leech-telegram-bot/actions/workflows/tests.yml/badge.svg?branch=filehub-dev)](https://github.com/RecklessEvadingDriver/mirror-leech-telegram-bot/actions/workflows/tests.yml)
[![Repository QA](https://github.com/RecklessEvadingDriver/mirror-leech-telegram-bot/actions/workflows/repo-qa.yml/badge.svg?branch=filehub-dev)](https://github.com/RecklessEvadingDriver/mirror-leech-telegram-bot/actions/workflows/repo-qa.yml)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/github/license/RecklessEvadingDriver/mirror-leech-telegram-bot)](LICENSE)

[Features](#-features) • [Architecture](#-architecture) • [Quick Start](#-quick-start) • [Configuration](#-configuration) • [Commands](#-commands) • [Security](#-security) • [Development](#-development)

</div>

---

## ✨ Overview

**FileHub** is a customized and hardened fork of the Mirror-Leech Telegram Bot ecosystem.

It combines multiple download engines, cloud backends and file-processing tools behind a single Telegram interface. A user can send a direct link, magnet, torrent, NZB, Telegram file or supported media URL and route the result to Telegram, Google Drive, rclone or supported upload backends.

The project is designed for private/self-hosted deployments and includes queue management, per-user settings, persistent MongoDB configuration, interactive file selection, status tracking, RSS automation and production-focused QA checks.

> **Important:** FileHub is intended for files and services you are authorized to access. Deployers are responsible for complying with applicable laws and third-party service terms.

---

## 🚀 Features

### Download engines

| Source / Engine | Support |
|---|:---:|
| Direct HTTP / HTTPS links | ✅ |
| aria2 | ✅ |
| qBittorrent / magnet / torrent | ✅ |
| Telegram files & links | ✅ |
| yt-dlp | ✅ |
| gallery-dl | ✅ |
| SABnzbd / NZB | ✅ |
| JDownloader | ✅ |
| Google Drive | ✅ |
| rclone remotes | ✅ |
| Supported direct-link generators | ✅ |

### Upload destinations

| Destination | Support |
|---|:---:|
| Telegram | ✅ |
| Google Drive | ✅ |
| rclone-supported clouds | ✅ |
| BuzzHeavier | ✅ |
| GoFile | ✅ |
| Clone / server-side transfer where supported | ✅ |

### File processing

- Archive and extract with 7-Zip
- Split large files for Telegram
- Join split files
- Rename files before upload
- FFmpeg video/audio processing
- Screenshots and sample-video generation
- Media conversion and remuxing
- Metadata / MediaInfo workflows
- Include/exclude extension filters
- Name substitution rules
- Multi-link and bulk processing

### Task management

- Global queue system
- Download and upload queues
- Active-task status pages
- Per-user task visibility
- Pause / cancel / force-start flows
- Torrent/NZB file selection
- Seeding controls
- Multi-task commands
- Task status pagination
- Persistent incomplete-task notifications

### User & admin controls

- Authorized users/chats/topics
- Owner and sudo permission levels
- Per-user settings
- Per-user thumbnails
- Per-user rclone configuration
- MongoDB-backed persistence
- Bot settings from Telegram
- RSS feeds and filtering
- Runtime engine settings
- Configurable FileHub branding

---

## 🧱 Architecture

```text
                         TELEGRAM
                            │
                    ┌───────▼───────┐
                    │    FileHub    │
                    │      Bot      │
                    └───────┬───────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
   Direct / TG        Torrent / NZB       Media / Cloud
      Links            aria2 / qB        yt-dlp / Drive
        │                   │                   │
        └───────────────────┼───────────────────┘
                            ▼
                    ┌───────────────┐
                    │  Task Engine  │
                    │ Queue / State │
                    └───────┬───────┘
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
       FFmpeg            Archive          Metadata
          │                 │                 │
          └─────────────────┼─────────────────┘
                            ▼
                    ┌───────────────┐
                    │ Storage Layer │
                    └───────┬───────┘
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
      Telegram           GDrive            rclone
```

### Core stack

- **Python / asyncio** — bot runtime
- **Pyrogram** — Telegram client
- **aria2** — direct/torrent transfers
- **qBittorrent** — torrent engine
- **SABnzbd** — Usenet/NZB engine
- **JDownloader** — supported hoster workflows
- **yt-dlp / gallery-dl** — media downloaders
- **FFmpeg / 7-Zip** — media and archive processing
- **MongoDB** — persistence
- **FastAPI + Gunicorn/Uvicorn** — file selector/web services
- **Docker / Docker Compose** — deployment

---

## ⚙️ Quick Start

### 1. Clone FileHub

```bash
git clone -b filehub-dev https://github.com/RecklessEvadingDriver/mirror-leech-telegram-bot.git filehub
cd filehub
```

### 2. Create your configuration

```bash
cp config_sample.py config.py
```

At minimum configure:

```python
BOT_TOKEN = "YOUR_BOT_TOKEN"
OWNER_ID = 123456789
TELEGRAM_API = 123456
TELEGRAM_HASH = "YOUR_TELEGRAM_API_HASH"
```

### 3. Build and run

```bash
docker compose up -d --build
```

View logs:

```bash
docker compose logs -f
```

Stop FileHub:

```bash
docker compose down
```

---

## 🔧 Configuration

FileHub reads configuration from `config.py` and can persist runtime settings in MongoDB when `DATABASE_URL` is configured.

### Required

| Variable | Description |
|---|---|
| `BOT_TOKEN` | Telegram bot token from BotFather |
| `OWNER_ID` | Telegram numeric user ID of the bot owner |
| `TELEGRAM_API` | Telegram API ID from `my.telegram.org` |
| `TELEGRAM_HASH` | Telegram API hash |

### Access & persistence

| Variable | Description |
|---|---|
| `DATABASE_URL` | MongoDB connection string |
| `DATABASE_NAME` | MongoDB database name |
| `AUTHORIZED_CHATS` | Authorized users, chats and optional topic IDs |
| `SUDO_USERS` | Additional privileged Telegram user IDs |
| `USER_SESSION_STRING` | Optional Telegram user session |
| `CMD_SUFFIX` | Optional suffix appended to bot commands |

Topic-specific authorization format:

```text
-1001234567890|10
-1001234567890|10|12
```

### Storage

| Variable | Description |
|---|---|
| `GDRIVE_ID` | Default Google Drive destination |
| `INDEX_URL` | Optional Drive index URL |
| `RCLONE_PATH` | Default rclone destination |
| `DEFAULT_UPLOAD` | Default upload backend |
| `UPLOAD_PATHS` | Named upload destinations |
| `USE_SERVICE_ACCOUNTS` | Enable trusted Google service accounts |

### Transfer behavior

| Variable | Description |
|---|---|
| `QUEUE_ALL` | Global concurrent task limit |
| `QUEUE_DOWNLOAD` | Download queue limit |
| `QUEUE_UPLOAD` | Upload queue limit |
| `STATUS_UPDATE_INTERVAL` | Status refresh interval |
| `STATUS_LIMIT` | Tasks displayed per status page |
| `LEECH_SPLIT_SIZE` | Telegram split size |
| `EXCLUDED_EXTENSIONS` | Extensions excluded from uploads |
| `INCLUDED_EXTENSIONS` | Restrict uploads to selected extensions |

### Media downloaders

| Variable | Description |
|---|---|
| `YT_DLP_OPTIONS` | Global yt-dlp options |
| `GALLERY_DL_OPTIONS` | Global gallery-dl options |

### FileHub branding

This fork supports centralized presentation settings for the bot name, tagline and repository link. FileHub branding can be changed without rewriting command modules.

> The complete and authoritative list of options lives in [`config_sample.py`](config_sample.py).

---

## 🤖 Commands

Command aliases may vary depending on `CMD_SUFFIX` and deployment configuration.

### Transfers

```text
/mirror       Mirror a direct link or supported source
/qbmirror     Mirror using qBittorrent
/jdmirror     Mirror using JDownloader
/nzbmirror    Mirror an NZB
/leech        Download and upload to Telegram
/qbleech      qBittorrent → Telegram
/jdleech      JDownloader → Telegram
/nzbleech     NZB → Telegram
/ytdl         yt-dlp mirror
/ytdlleech    yt-dlp → Telegram
/gallerydl    gallery-dl mirror
/clone        Clone supported cloud content
```

### Task control

```text
/status       Show active tasks
/cancel       Cancel a task
/cancelall    Cancel tasks by status
/forcestart   Force queued task start
/sel          Open torrent/NZB file selection
```

### Drive & search

```text
/list         Search configured Google Drives
/count        Count Drive files/folders
/del          Delete supported Drive content (privileged)
/search       Torrent/search integrations
/nzbsearch    Search configured NZB providers
```

### Settings & administration

```text
/us           User settings
/bs           Bot settings
/users        User overview
/auth         Authorize user/chat/topic
/unauth       Remove authorization
/addsudo      Add sudo user
/rmsudo       Remove sudo user
/stats        Server statistics
/ping         Bot latency
/restart      Restart bot
/log          Retrieve logs
/rss          RSS manager
/help         Command help
```

### Owner-only execution

```text
/shell
/exec
/aexec
/clearlocals
```

These commands are intentionally powerful and remain restricted to the configured owner.

---

## 🔐 Security

FileHub includes additional hardening beyond the original fork baseline.

### Current protections

- Owner / sudo / authorized-user separation
- Callback ownership checks
- Signed HMAC tokens for the web file selector
- Constant-time selector token verification
- TLS certificate verification enabled for hardened network paths
- Bounded synchronous HTTP timeouts
- Safer parsing instead of user-reachable Python `eval()`
- Hardened NZB XML parsing with `defusedxml`
- Restricted handling of user-provided Google pickle credentials
- Safer subprocess execution for updater/JDownloader/settings flows
- Tight permissions for `.netrc`, rclone configs, account files and credential files
- Bounded SABnzbd startup retries
- Sanitized web errors instead of exposing raw Python exceptions
- Persistent repository security scanning

### Credential guidance

Never commit any of the following:

```text
config.py
.env
.netrc
token.pickle
accounts/
rclone.conf
cookies.txt
Telegram session strings
API keys
MongoDB credentials
```

Use repository secrets, deployment environment variables or a protected private configuration store.

---

## ✅ Quality Assurance

Every development push is checked by GitHub Actions.

### Test workflow

- Python 3.11
- Python 3.12
- pytest regression suite

### Repository QA workflow

- Compile all Python modules
- Ruff critical-error checks
- Shell syntax validation
- YAML validation
- Docker Compose validation
- `config_sample.py` compilation
- Bandit security analysis
- `pip-audit` dependency vulnerability scanning

Recent hardening work reduced the repository security scan to **zero high-severity Bandit findings** and the dependency audit reported **no known vulnerabilities** at the time of the latest QA pass.

---

## 🗂️ Project Structure

```text
.
├── bot/
│   ├── core/                     # Config, startup, handlers, clients
│   ├── helper/
│   │   ├── ext_utils/            # Shared utilities & database helpers
│   │   ├── mirror_leech_utils/   # Download/upload engines
│   │   └── telegram_helper/      # Telegram UI, filters and commands
│   └── modules/                  # Bot command modules
├── web/                          # File selector / web service
├── tests/                        # Regression tests
├── .github/workflows/            # CI + repository QA
├── config_sample.py              # Full configuration reference
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## 🧪 Development

Create a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install development requirements:

```bash
pip install -r requirements-dev.txt
```

Run tests:

```bash
pytest -q
```

Compile-check the project:

```bash
python -m compileall -q bot web tests *.py
```

Run critical Ruff checks:

```bash
ruff check . --select E9,F63,F7,F82
```

Run Bandit:

```bash
bandit -r bot web update.py -q -ll
```

---

## 🐳 Deployment Notes

For production deployments:

1. Use a dedicated server/VPS or isolated container environment.
2. Keep Telegram, MongoDB and cloud credentials outside Git.
3. Restrict access to qBittorrent, SABnzbd, JDownloader and any exposed web UI.
4. Put public web endpoints behind HTTPS and a trusted reverse proxy.
5. Configure MongoDB authentication and network restrictions.
6. Use persistent volumes for required runtime state.
7. Review `config_sample.py` before every major update.
8. Keep the FileHub branch updated and let CI pass before deployment.

---

## 🧭 Roadmap

- [x] FileHub branding layer
- [x] Repository-wide QA workflow
- [x] Python 3.11 / 3.12 regression testing
- [x] Authorization hardening
- [x] Web selector signing
- [x] TLS and timeout hardening
- [x] Safer configuration parsing
- [x] Credential permission hardening
- [ ] Unified FileHub Telegram dashboard
- [ ] Rich task cards and navigation
- [ ] Expanded storage abstraction
- [ ] Additional queue policies and quotas
- [ ] Deployment health checks
- [ ] Fully reproducible dependency lockfile

---

## 🤝 Contributing

Development happens on the `filehub-dev` branch.

```bash
git checkout filehub-dev
git pull origin filehub-dev
```

Before opening a pull request:

```bash
pytest -q
python -m compileall -q bot web tests *.py
ruff check . --select E9,F63,F7,F82
```

Keep changes focused, avoid committing credentials, and include regression coverage for bug fixes whenever possible.

---

## 🙏 Upstream & Credits

FileHub builds on the excellent work of the open-source Mirror-Leech Telegram Bot community.

Primary upstream repository:

- [`anasty17/mirror-leech-telegram-bot`](https://github.com/anasty17/mirror-leech-telegram-bot)

The project also incorporates or integrates technologies and ideas from aria2, qBittorrent, SABnzbd, JDownloader, yt-dlp, gallery-dl, rclone, Pyrogram, FastAPI, FFmpeg and their respective open-source communities.

Please preserve upstream licenses and attribution when redistributing this project.

---

<div align="center">

### FileHub

**Download • Process • Queue • Mirror • Upload**

Built for self-hosted Telegram automation.

[Repository](https://github.com/RecklessEvadingDriver/mirror-leech-telegram-bot) · [Pull Requests](https://github.com/RecklessEvadingDriver/mirror-leech-telegram-bot/pulls) · [Issues](https://github.com/RecklessEvadingDriver/mirror-leech-telegram-bot/issues)

</div>
