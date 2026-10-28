"""Cross-repo overviews: open PRs and open issues in all my repos.

Pure functions over a `GitHubClientProtocol`. Both listings walk every
repository the token can see and fetch the open items per repo. To keep
the call count down they skip archived repos, repos whose
`open_issues_count` (which GitHub defines to include PRs) is zero, and
repos the caller asks to ignore (see `gb.config`).
"""

from __future__ import annotations

from collections.abc import Collection, Iterator
from dataclasses import dataclass

from gb.github_client import GitHubClientProtocol


def _iter_active_repo_names(client: GitHubClientProtocol, ignore: Collection[str]) -> Iterator[str]:
    """Yield full names of non-archived, non-ignored repos with at least one open issue/PR."""
    ignored = {name.lower() for name in ignore}
    for repo in client.get_repos():
        if repo.archived or repo.open_issues_count == 0:
            continue
        if repo.full_name.lower() in ignored:
            continue
        yield repo.full_name


# --- prs list --------------------------------------------------------------


@dataclass(frozen=True)
class OpenPullRequest:
    repo: str
    number: int
    title: str
    author: str
    draft: bool
    url: str

    def __str__(self) -> str:
        suffix = "  [draft]" if self.draft else ""
        # The plain URL at the end is what terminals turn into a clickable link.
        return f"#{self.number}  {self.title}  @{self.author}{suffix}  {self.url}"


def list_open_pull_requests(
    client: GitHubClientProtocol, *, ignore: Collection[str] = ()
) -> list[OpenPullRequest]:
    """Return every open PR across all repos (minus `ignore`), sorted by repo then number."""
    found: list[OpenPullRequest] = []
    for repo_name in _iter_active_repo_names(client, ignore):
        for pr in client.get_open_pull_requests(repo_name):
            found.append(
                OpenPullRequest(
                    repo=repo_name,
                    number=pr.number,
                    title=pr.title,
                    author=pr.user.login,
                    draft=bool(pr.draft),
                    url=pr.html_url,
                )
            )
    return sorted(found, key=lambda p: (p.repo.lower(), p.number))


# --- issues list -----------------------------------------------------------


@dataclass(frozen=True)
class OpenIssue:
    repo: str
    number: int
    title: str
    author: str
    labels: tuple[str, ...]
    url: str

    def __str__(self) -> str:
        suffix = f"  [{', '.join(self.labels)}]" if self.labels else ""
        return f"#{self.number}  {self.title}  @{self.author}{suffix}  {self.url}"


def is_plain_issue(issue) -> bool:
    """True for real issues; the issues endpoint also returns PRs."""
    return issue.pull_request is None


def list_open_issues(
    client: GitHubClientProtocol, *, ignore: Collection[str] = ()
) -> list[OpenIssue]:
    """Return every open issue (not PRs) across all repos minus `ignore`, sorted by repo, number."""
    found: list[OpenIssue] = []
    for repo_name in _iter_active_repo_names(client, ignore):
        for issue in client.get_open_issues(repo_name):
            if not is_plain_issue(issue):
                continue
            found.append(
                OpenIssue(
                    repo=repo_name,
                    number=issue.number,
                    title=issue.title,
                    author=issue.user.login,
                    labels=tuple(label.name for label in issue.labels),
                    url=issue.html_url,
                )
            )
    return sorted(found, key=lambda i: (i.repo.lower(), i.number))
