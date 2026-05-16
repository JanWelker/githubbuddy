# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`gb` — a personal CLI for the user's daily GitHub chores. New features will be added over time as subcommands grouped by area (e.g. `gb notifications ...`).

Auth is a Personal Access Token in the `GITHUB_TOKEN` env var (scopes: `notifications`, `repo`).

## Commands

```sh
uv sync                                       # install / refresh deps
uv run gb <subcommand>                        # run the CLI
uv run pytest                                 # run all tests
uv run pytest tests/test_notifications.py     # single file
uv run pytest -k cleanup_marks_only_merged    # single test by name
uv run ruff check                             # lint
uv run ruff format                            # format
```

The project is a `uv` workspace (`pyproject.toml` + `uv.lock`, src layout). The package lives under `src/gb/`, the CLI entry point is `gb = "gb.cli:app"`.

## Git workflow

`main` is protected on github.com: the `checks` CI job must pass before any commit lands, and force-push and branch deletion are disabled. PR review is **not** required.

For any change: branch → commit → `gh pr create`. Direct pushes to `main` are technically allowed (no PR-review requirement) but protection rejects pushes whose commits haven't already passed CI somewhere — branching is the path of least resistance. After opening the PR, mark it for auto-merge with `gh pr merge --auto --squash`; with no reviewers required, GitHub merges as soon as `checks` is green. Renovate uses the same machinery (`platformAutomerge: true` in `.github/renovate.json`) and merges its own PRs automatically.

**Use Conventional Commits** (`feat:`, `fix:`, `chore:`, `ci:`, `docs:`, `refactor:`, optionally with a `(scope)` and a trailing `!` for breaking). Release-please reads these to decide the next version and to generate the changelog — see "Versioning & releases" below.

## Versioning & releases

The package version lives in **one place**: `pyproject.toml`'s `version` field. `src/gb/__init__.py` reads it back via `importlib.metadata.version("githubbuddy")`. Do not duplicate the version string anywhere else (don't hand-edit `__init__.py`).

Releases are driven by [release-please](https://github.com/googleapis/release-please) (`.github/workflows/release-please.yml` + `release-please-config.json` + `.release-please-manifest.json`). The config file has **no** leading dot — that's the upstream action's default and a non-dotted name is what the action looks for; the manifest file does have a leading dot. On every push to `main` it inspects the conventional-commit history since the last tag and either creates or updates a "release PR" that:

- Bumps `pyproject.toml` `version` (feat → minor, fix → patch, `!` → major; pre-1.0 majors stay minor by config).
- Updates `CHANGELOG.md`.
- Updates `.release-please-manifest.json`.

Merging that release PR causes the action to create the matching `vX.Y.Z` git tag and a GitHub Release with the generated notes. **Do not bump the version by hand and do not create tags manually** — let release-please own that flow. If a release needs to happen on a different cadence, edit `Release-As: X.Y.Z` into a commit message rather than touching files directly.

## Architecture

The codebase enforces one rule that everything else follows from: **anything that touches PyGithub or the network lives in `src/gb/github_client.py`. Feature modules never import `github` directly.**

This makes features unit-testable without mocking PyGithub. Concretely:

- `github_client.GitHubClient` is the only place that holds a `Github(...)` instance and calls into it.
- `github_client.GitHubClientProtocol` declares the small surface that features actually use (`get_notifications`, `is_pr_merged`, `mark_notification_done`, ...). Features depend on the Protocol, not the concrete class.
- Feature modules (e.g. `src/gb/notifications.py`) are pure functions that take a `GitHubClientProtocol`. They return plain dataclasses; printing is the CLI's job, not theirs.
- `cli.py` wires it together. It owns a `_client_factory` indirection (`set_client_factory(...)`) so tests can swap in a fake without monkeypatching env vars or PyGithub.
- `tests/conftest.py` provides `FakeClient` + `FakeNotification` dataclasses implementing the protocol. New features should extend these instead of mocking PyGithub objects.

When adding a feature: add the method to `GitHubClient` **and** `GitHubClientProtocol`, extend `FakeClient` with a matching stub, then build the feature as pure functions in a new `src/gb/<feature>.py`. Wire a subcommand in `cli.py` (typically under a new `typer.Typer()` subgroup).

## Token permissions doc — keep in sync

`README.md` has a "Personal access token permissions" table with one row per REST endpoint the CLI actually calls, listing the classic scope and the fine-grained permission (or "Not supported by GitHub" if `fineGrainedPat: false`). **Every new feature must update this table in the same change** — add a row per new endpoint, or just append the new subcommand to the "Used by" cell of an existing row if the endpoint is already listed. If the feature only reuses already-listed endpoints, say so in the PR description so the omission is intentional, not forgotten.

Do not invent permission names. Permissions GitHub doesn't actually expose (e.g. there is no fine-grained "Notifications" permission today) will fail at token-creation time and waste the user's setup attempts. Look the real values up before writing:

1. List every REST endpoint the new code touches, directly or via PyGithub. (For PyGithub calls, trace through to the underlying endpoint — e.g. `Repository.get_pull(n)` → `GET /repos/{owner}/{repo}/pulls/{n}`.)
2. For each endpoint, open its REST docs page on docs.github.com and find the "Fine-grained access tokens for ..." block. The page's underlying JSON has a `progAccess` field — `fineGrainedPat: true/false` and `permissions: [...]` are the authoritative answer. If `fineGrainedPat` is false, the row's fine-grained cell is "Not supported by GitHub" and the CLI as a whole stays on a classic PAT.
3. For the classic scope, find the "Works with the following token types" / scope block on the same endpoint page.
4. Add or update one row per endpoint in the README table and re-derive the "pick the union" recommendation underneath if the union changed.

If a new feature is fully covered by fine-grained PATs and notifications is the only thing blocking fine-grained for the whole CLI, call that out — it may be worth letting users with fine-grained tokens run a subset of commands. Don't make that change silently.

## PyGithub gotchas

- "Mark as done" is **not** the same as "mark as read". Read = PATCH; done = DELETE on the thread URL. PyGithub only exposes `mark_as_read()` directly, so `GitHubClient.mark_notification_done` calls `notification._requester.requestJsonAndCheck("DELETE", notification.url)` — this is intentional, don't "fix" it to `mark_as_read`.
- "Read/unread" and "in the Inbox / done" are **independent axes**. The GitHub UI's Inbox tab shows "not done"; `GET /notifications` defaults to `all=false` which means **unread only**. A PR you've opened in the browser is read-but-still-in-inbox and the API will hide it from you by default. `GitHubClient.get_notifications()` passes `all=True` on purpose so cleanup logic sees everything still in the inbox. Do not "optimize" this away.
- Notification `subject.url` for PRs is the REST API URL ending in `/pulls/<n>` — parse the trailing segment to get the PR number (see `pr_number_from_subject_url`).
- `subject.url` is **null** for `CheckSuite` notifications. You cannot fetch the suite from the notification alone, so you also can't independently verify its conclusion. `cleanup_failed_ci_notifications` in `gb.notifications` therefore treats the presence of a CheckSuite notification as the failure signal — by default GitHub only emits these on failed workflow runs. Don't "fix" this by inventing a URL or scraping the title.
