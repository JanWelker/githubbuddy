# githubbuddy (`gb`)

Personal CLI for daily GitHub chores.

## Setup

```sh
uv sync
cp .env.example .env   # if .env doesn't already exist
$EDITOR .env           # paste your PAT into GITHUB_TOKEN
```

Then either `source .env` before each session, or let `uv` load it per-invocation:

```sh
uv run --env-file .env gb notifications cleanup-merged
# or set it once: export UV_ENV_FILE=.env
```

`.env` is gitignored. See "Personal access token permissions" below for what to put in it.

### Personal access token permissions

This CLI currently **requires a classic PAT** (<https://github.com/settings/tokens/new>). The notifications REST endpoints don't support fine-grained PATs yet — GitHub's docs list them with `fineGrainedPat: false` — so a fine-grained token cannot complete the `notifications cleanup-merged` flow even though the PR-read step alone could.

Per-endpoint requirements (one row per endpoint actually called):

| Endpoint | Used by | Classic scope | Fine-grained PAT |
| --- | --- | --- | --- |
| `GET /notifications` | `notifications cleanup-merged`, `notifications cleanup-failed-ci` | `notifications` | Not supported by GitHub |
| `DELETE /notifications/threads/{id}` | `notifications cleanup-merged`, `notifications cleanup-failed-ci` | `notifications` | Not supported by GitHub |
| `GET /repos/{owner}/{repo}/pulls/{n}` | `notifications cleanup-merged` | `repo` (private) or `public_repo` (public only) | `"Pull requests"` repo permission, read (or `"Contents"`, read) |
| `GET /user/repos` | `prs list`, `issues list` | `repo` (private) or `public_repo` (public only) | `"Metadata"` repo permission, read |
| `GET /repos/{owner}/{repo}/pulls` | `prs list` | `repo` (private) or `public_repo` (public only) | `"Pull requests"` repo permission, read |
| `GET /repos/{owner}/{repo}/issues` | `issues list` | `repo` (private) or `public_repo` (public only) | `"Issues"` repo permission, read |

Pick the union of "Classic scope" cells when creating the token. For now: `notifications` + `repo` (use `public_repo` if you only ever get notifications from public repos and only want to list public ones).

`prs list` and `issues list` are fully covered by fine-grained PATs (`"Metadata"`, `"Pull requests"`, `"Issues"`, all read). Notifications remain the only thing that forces a classic PAT for the CLI as a whole.

What each scope grants (verbatim from <https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps>):

- **`notifications`** — "Grants: read access to a user's notifications, mark as read access to threads, watch and unwatch access to a repository, and read, write, and delete access to thread subscriptions." This is the scope GitHub's REST docs list for both `GET /notifications` and `DELETE /notifications/threads/{id}` (mark as done); the scope description page itself only mentions "mark as read" but the same scope covers the newer "mark as done" endpoint.
- **`repo`** — "Grants full access to public and private repositories including read and write access to code, commit statuses, repository invitations, collaborators, deployment statuses, and repository webhooks." Only read endpoints are actually used (repo listing, pulls, issues) but `repo` is the smallest classic scope that covers reading them in private repos.
- **`public_repo`** — "Limits access to public repositories. That includes read/write access to code, commit statuses, repository projects, collaborators, and deployment statuses for public repositories and organizations." Sufficient if you only need PR data from public repos.

When you add a feature that hits a new endpoint, add a row in the same change — see `CLAUDE.md`.

## Usage

```sh
uv run gb notifications cleanup-merged    # dismiss notifications for merged PRs
uv run gb notifications cleanup-failed-ci # dismiss failed-CI notifications
uv run gb prs list                        # all open PRs in all your repos
uv run gb issues list                     # all open issues in all your repos
```

`prs list` and `issues list` walk every repo the token can see (owned, collaborator, org member), skipping archived repos and repos with no open items, and print one block per repo. In a terminal the number and title are clickable links to github.com; when piped, or with `--plain`, each line ends with the URL instead.

## Develop

```sh
uv run pytest         # tests
uv run ruff check     # lint
uv run ruff format    # format
```
