# AGENTS.md

Guidance for AI agents (Claude Code) working on this repository.

## Project overview

`seo-cli` is a Python CLI that wraps two Google APIs into a single tool:

- **Google Analytics Data / Admin API** (GA4)
- **Google Search Console API** (GSC)

It is primarily consumed by Claude Code during SEO research tasks. The end-user
artifact is the launcher script `./seo-cli` at the repository root.

## Tech stack

- Python 3.12+ (`.python-version` pins 3.12)
- Package manager: **uv** (lockfile: `uv.lock`)
- CLI framework: **click** (preferred over argparse because subcommands are nested two levels deep)
- Google SDKs:
  - `google-analytics-data` — GA4 Data API
  - `google-analytics-admin` — GA4 Admin API
  - `google-api-python-client` — GSC (Discovery-based client)
  - `google-auth` — ADC resolution and OAuth2 credentials
- Settings format: TOML (stdlib `tomllib`) or JSON, stored in an env var

### context7 MCP

When touching any of these libraries, use the **context7 MCP** to fetch current
docs / examples before coding. Don't rely on memory — Google SDKs change often.

- `google-analytics-data` (GA4)
- `google-analytics-admin`
- `google-api-python-client` / `googleapiclient`
- `google-auth`

## Repository layout

```
seo-cli/
├── pyproject.toml             # Project metadata + deps + [project.scripts] entry point
├── uv.lock
├── .python-version
├── seo-cli                    # zsh launcher (sources .loadenv.sh, execs `uv run`)
├── .loadenv.sh                # gitignored; sources secrets from 1Password via `op read`
├── README.md                  # End-user documentation
├── AGENTS.md                  # This file (symlinked from CLAUDE.md)
├── CLAUDE.md -> AGENTS.md
├── src/
│   └── seo_cli/
│       ├── __init__.py
│       ├── __main__.py        # `python -m seo_cli` entry
│       ├── cli.py             # click root group; registers the 3 subgroups
│       ├── auth.py            # Credentials resolution (profile → ADC fallback)
│       ├── settings.py        # TOML / JSON loader; profile lookup
│       ├── output.py          # json / tsv / human formatters
│       ├── profile/
│       │   └── commands.py    # `profile list`
│       ├── google_analytics/
│       │   ├── client.py      # build_admin_client / build_data_client / helpers
│       │   └── commands.py    # 6 subcommands
│       └── google_search_console/
│           ├── client.py      # build_service / row flattening
│           └── commands.py    # 6 subcommands
├── _issues/                   # gitignored; issue tracking workspace (see workflow)
└── .claude/
    └── skills/
        └── test-seo-cli/
            └── SKILL.md       # Verification playbook (invoked by "seo-cli をテスト")
```

## Setup

```bash
uv sync
```

That creates `.venv/` and installs pinned deps. The CLI is available as:

- `.venv/bin/seo-cli ...` (direct)
- `uv run seo-cli ...` (recommended)
- `./seo-cli ...` (launcher; sources `.loadenv.sh` first)

## Running locally

### First time

1. Ensure 1Password desktop app is running (the launcher's `.loadenv.sh` calls `op read`).
2. Run `./seo-cli profile list` to confirm profiles load.

### Everyday

```bash
./seo-cli google-analytics account-summaries
./seo-cli google-search-console sites-list
```

### Without the launcher (no env loading)

```bash
uv run seo-cli --help
```

## Running tests / verification

There is a verification playbook at `.claude/skills/test-seo-cli/SKILL.md`.
When a user says "seo-cli をテスト" / "test seo-cli", follow that skill:
run Level 0 → 1 → 2 → ... and stop at the first failing level to localize
the problem.

There are no automated unit tests yet. If adding them, use `pytest` (already
listed as a dev dependency in `pyproject.toml`) and place tests under `tests/`.

## Adding a new command

Pattern to follow:

1. Decide which group it belongs to: `google_analytics`, `google_search_console`, or `profile`.
2. Open the group's `commands.py` and add a new `@<group>.command(...)` function.
3. Use the existing shared options: `_format_option`, `_property_id_option`
   (GA), `_site_url_option` (GSC).
4. Call `build_admin_client()` / `build_data_client()` / `build_service()` to
   get an authenticated client — do **not** call `get_credentials` directly
   from a command.
5. Wrap `HttpError` (GSC) with `click.ClickException(f"GSC API error: {e}")`.
   For GA4 proto-based responses, let exceptions bubble up (`google.api_core.exceptions.*` have reasonable messages).
6. Build the result as JSON-serializable types and call `emit(data, format=format_)`.
7. Run `uv run seo-cli <group> <command> --help` to verify the option surface.

### User-visible strings must be English

All click docstrings, option help text, and `ClickException` / `UsageError`
messages are in English. Do not introduce Japanese into command output or
--help text. (Code comments and `_issues/*/ISSUE.md` content may remain
Japanese if that matches the surrounding context.)

## Authentication model

- Credentials are never checked in. They live in 1Password (or a local env var for dev).
- `auth.get_credentials(service, scopes)` resolves in this order per invocation:
  1. The active profile's `google_analytics_credentials_json` /
     `google_search_console_credentials_json` (service-specific key)
  2. The active profile's `credentials_json` (shared fallback)
  3. ADC (`google.auth.default`), which checks
     `GOOGLE_APPLICATION_CREDENTIALS`, then gcloud's
     `application_default_credentials.json`, then GCE/GKE metadata server.
- The JSON payload can be a service-account key or an authorized_user JSON;
  `_credentials_from_info` dispatches on the `type` field.
- The active profile comes from the root `--profile` option, pulled from
  `click.get_current_context().obj["profile"]`. Commands do not pass this
  through explicitly.

## Distribution

Not a deployed service; installed locally. To expose on PATH:

```bash
ln -s /Users/ytyng/workspace/seo-cli/seo-cli ~/home-files/bin/seo-cli
```

There is no release / publish step. Changes are consumed directly from the
working tree.

## Claude / agent workflow

### Issue tracking

For non-trivial work, create an issue folder and a narrative file:

```bash
/create-issue-folder <short description>
```

This produces `_issues/YYYYMMDD-<slug>/ISSUE.md`. Append investigation notes,
decisions, and progress updates as the work proceeds.

To resume and drive an issue forward:

```bash
/resolve-issue                 # uses the most recent ISSUE.md in context
/resolve-issue <file-or-folder>
```

### Review → commit → PR

```bash
# Stage relevant files first
/review-stage                  # Claude reviews the staging diff
git commit -m "..."            # after fixes
/feature-pr                    # push a feature branch and open the PR
/wait-copilot-review           # wait for Copilot review
/review-pr-comment             # handle review comments
```

### When touching the CLI

- Run `uv run seo-cli --help` and the group/command `--help` after any CLI surface change.
- For auth or settings changes, use `.claude/skills/test-seo-cli/SKILL.md` Level 0–1 to verify locally without real API calls.
- Update `README.md` if the public interface changes.
- Update this file (`AGENTS.md`) if the agent workflow, layout, or auth model changes.

## Sandbox caveats (Claude Code only)

Claude Code's sandbox blocks:

- Writes to `~/.cache/uv/` → use `UV_CACHE_DIR="$(pwd)/.uv-cache" uv sync` or call `.venv/bin/seo-cli` directly.
- Reads of `**/*.pem` → any HTTPS call fails (affects all real API verification). Claude can verify Level 0–1 of the test skill but must delegate Level 2+ to the user's terminal.
- `op read` → `.loadenv.sh` fails inside the sandbox; do not rely on it from agent-driven runs.

Normal user execution (outside Claude Code) has none of these restrictions.
