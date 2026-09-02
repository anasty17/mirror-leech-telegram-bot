# FileHub Full Repository QA Report

Date: 2026-09-02
Branch: `filehub-dev`

## Scope

This audit covers the repository as a whole rather than only the customized start/help flow:

- Python syntax and critical static errors across `bot/`, `web/`, `tests/`, and root Python scripts
- pytest on Python 3.11 and 3.12
- shell-script syntax
- YAML/workflow syntax
- Docker Compose configuration parsing
- sample configuration compilation
- medium/high security scanning
- dependency vulnerability auditing
- manual review of startup/update, permissions, queue/cancellation, web file selector, upload backends, handlers and authorization

## Automated QA status

### Passing

- Python compile-all: PASS
- Ruff critical error set (`E9,F63,F7,F82`): PASS after GoFile fix
- Shell syntax (`bash -n`): PASS
- YAML parsing: PASS
- Docker Compose config: PASS
- `config_sample.py` compilation: PASS
- Dependency audit (`pip-audit`): no known vulnerabilities reported
- pytest Python 3.11: PASS
- pytest Python 3.12: PASS

## Bugs fixed during QA

### Critical: cancel-all authorization fallthrough

A non-sudo user could press another user's cancel-all callback, receive `Not Yours!`, but execution continued because the handler did not return. Fixed by terminating the callback immediately and adding regression coverage.

### Critical: startup updater shell injection

`update.py` previously interpolated `UPSTREAM_REPO` and `UPSTREAM_BRANCH` into a `shell=True` command. These values can originate from configuration/database state. Replaced with argument-based `git` subprocess calls and safer database fallback handling.

### High: GoFile uploader undefined runtime state

`GoFileUploader.upload()` referenced `first_link` and `files_dict` without guaranteed initialization. The completion callback also did not match the non-leech upload callback contract. Fixed initialization, success accounting, and completion arguments.

### Authorization/config fixes from the preceding QA pass

- fixed `/auth` topic parsing
- fixed `/unauth` topic parsing
- persisted topic authorization changes to MongoDB
- hardened sudo target parsing
- fixed `-bh` boolean argument handling

## Release blockers still open

### CRITICAL: user-reachable Python `eval()`

Multiple non-owner flows evaluate user-controlled text as Python expressions. These must be replaced with `ast.literal_eval`, explicit boolean parsing, or structured JSON parsing before this bot is considered safe for multi-user deployment.

Confirmed locations include:

- `bot/modules/users_settings.py`
- `bot/modules/ytdlp.py`
- `bot/modules/gallery_dl.py`
- `bot/helper/ext_utils/bot_utils.py`
- `bot/helper/common.py`

Additional `eval()` calls exist in bot settings and Google Drive paths. Owner-only `/exec` and `/shell` are intentional privileged features and should remain strictly owner-only rather than being confused with the unsafe parsing calls above.

### HIGH: deterministic web file-selector PIN

`web/wserver.py` derives the selector PIN from the torrent GID itself by taking its first four digits. Anyone who learns the GID can calculate the PIN. The endpoint also accepts state-changing POST operations for selection/rename.

Replace this with a server-secret HMAC/token, preferably short-lived and scoped to the specific task/user.

### HIGH: TLS certificate verification disabled

Security scanning identified `verify=False` in several network-facing paths, including:

- `bot/helper/mirror_leech_utils/download_utils/tldv_downloader.py`
- `bot/modules/rss.py`
- `bot/modules/ytdlp.py`

These requests are vulnerable to machine-in-the-middle interception. Certificate validation should be enabled by default, with any compatibility override explicit and narrowly scoped.

### HIGH: excessive filesystem permissions

The Dockerfile uses `chmod 777 /app`, and startup code applies permissive permissions to extracted account material. Secrets, tokens, cookies and service-account files should not be world-readable/writable.

Recommended defaults:

- application directory: `755` or tighter
- secret/token files: `600`
- private directories: `700`

### MEDIUM: direct-link generators without network timeouts

Numerous synchronous `requests.get()` / `requests.post()` calls in `direct_link_generator.py` have no timeout. A dead or malicious host can block a worker indefinitely. Apply a shared connect/read timeout to every external request.

### MEDIUM: startup loops can hide permanent failures

`update_nzb_options()` retries indefinitely with a bare exception handler. A permanent SABnzbd/configuration failure can leave startup stuck forever without a terminal error. Use bounded retries/backoff and preserve the last exception.

### MEDIUM: web error information disclosure

The global FastAPI exception handler includes raw exception text in the HTTP response. Internal paths, backend messages or implementation details can leak to clients. Log the detailed exception server-side and return a generic public error.

### MEDIUM: unpinned runtime dependencies

`requirements.txt` is almost entirely unpinned. Current dependency auditing reports no known vulnerabilities, but deployments are not reproducible and upstream releases can break the bot without a repository change. Introduce a lock/constraints file generated from tested versions.

### MEDIUM: unsafe XML parser for NZB search

`bot/modules/nzb_search.py` parses remote XML with the standard ElementTree parser. Use `defusedxml` for untrusted XML responses.

### REVIEW: pickle credential loading

Google Drive credentials are loaded using pickle. This is safe only when token files are fully trusted and cannot be replaced by untrusted users. Maintain strict file ownership/permissions or migrate to a non-executable credential serialization format where possible.

## Intentional privileged operations

The following are security-sensitive but intentional when owner-only filters remain correct:

- `/shell`
- synchronous `/exec`
- asynchronous `/aexec`

Do not broaden these handlers to sudo or authorized users.

## Current assessment

Functional/static quality: GOOD

Automated regression baseline: GOOD

Deployment reproducibility: NEEDS IMPROVEMENT

Multi-user security: NOT READY until user-controlled `eval()` calls and web selector authorization are fixed.

Production recommendation: do not merge `filehub-dev` into the production/default branch until the CRITICAL and HIGH release blockers above are resolved and the full QA workflows remain green.
