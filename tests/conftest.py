"""Shared fixtures.

`FakeNotification` and `FakeClient` mimic the small surface of PyGithub
that `gb.notifications` actually uses, so the feature logic can be
tested without any network or PyGithub objects.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

_id_counter = itertools.count(1)


def _next_id() -> str:
    return str(next(_id_counter))


_DEFAULT_UPDATED_AT = datetime(2026, 1, 1, tzinfo=UTC)


@dataclass
class FakeSubject:
    type: str
    title: str
    url: str | None


@dataclass
class FakeRepo:
    full_name: str
    archived: bool = False
    # GitHub counts open PRs in open_issues_count too.
    open_issues_count: int = 1


@dataclass
class FakeUser:
    login: str


@dataclass
class FakeLabel:
    name: str


@dataclass
class FakePullRequest:
    number: int
    title: str
    user: FakeUser
    draft: bool = False
    html_url: str = ""


@dataclass
class FakeIssue:
    number: int
    title: str
    user: FakeUser
    labels: list[FakeLabel] = field(default_factory=list)
    html_url: str = ""
    # Non-None marks the issue as actually being a PR, like PyGithub's Issue.pull_request.
    pull_request: object | None = None


def make_pr(number: int = 1, title: str = "A PR", author: str = "alice", **kw) -> FakePullRequest:
    return FakePullRequest(number=number, title=title, user=FakeUser(author), **kw)


def make_issue(
    number: int = 1, title: str = "An issue", author: str = "alice", labels: list[str] = (), **kw
) -> FakeIssue:
    return FakeIssue(
        number=number,
        title=title,
        user=FakeUser(author),
        labels=[FakeLabel(n) for n in labels],
        **kw,
    )


@dataclass
class FakeNotification:
    subject: FakeSubject
    repository: FakeRepo
    id: str = field(default_factory=_next_id)
    updated_at: datetime = _DEFAULT_UPDATED_AT


def make_pr_notification(
    repo: str = "octocat/hello",
    number: int = 1,
    title: str = "A PR",
    *,
    id: str | None = None,
    updated_at: datetime = _DEFAULT_UPDATED_AT,
) -> FakeNotification:
    return FakeNotification(
        subject=FakeSubject(
            type="PullRequest",
            title=title,
            url=f"https://api.github.com/repos/{repo}/pulls/{number}",
        ),
        repository=FakeRepo(full_name=repo),
        id=id if id is not None else _next_id(),
        updated_at=updated_at,
    )


def make_issue_notification(repo: str = "octocat/hello", number: int = 99) -> FakeNotification:
    return FakeNotification(
        subject=FakeSubject(
            type="Issue",
            title="An issue",
            url=f"https://api.github.com/repos/{repo}/issues/{number}",
        ),
        repository=FakeRepo(full_name=repo),
    )


def make_check_suite_notification(
    repo: str = "octocat/hello",
    title: str = "CI failed",
    *,
    id: str | None = None,
    updated_at: datetime = _DEFAULT_UPDATED_AT,
) -> FakeNotification:
    # Real CheckSuite notifications have subject.url == None; mirror that.
    return FakeNotification(
        subject=FakeSubject(type="CheckSuite", title=title, url=None),
        repository=FakeRepo(full_name=repo),
        id=id if id is not None else _next_id(),
        updated_at=updated_at,
    )


@dataclass
class FakeClient:
    notifications: list[FakeNotification] = field(default_factory=list)
    # (repo_full_name, pr_number) -> merged?
    merged: dict[tuple[str, int], bool] = field(default_factory=dict)
    marked_done: list[FakeNotification] = field(default_factory=list)
    # Records calls to is_pr_merged so tests can assert we skipped cached threads.
    is_pr_merged_calls: list[tuple[str, int]] = field(default_factory=list)
    repos: list[FakeRepo] = field(default_factory=list)
    # repo_full_name -> open PRs / open issues (issues may include PR-backed entries)
    open_pulls: dict[str, list[FakePullRequest]] = field(default_factory=dict)
    open_issues: dict[str, list[FakeIssue]] = field(default_factory=dict)
    # Records which repos were queried so tests can assert skips.
    queried_repos: list[str] = field(default_factory=list)

    def get_notifications(self) -> list[FakeNotification]:
        return list(self.notifications)

    def is_pr_merged(self, repo_full_name: str, pr_number: int) -> bool:
        self.is_pr_merged_calls.append((repo_full_name, pr_number))
        return self.merged.get((repo_full_name, pr_number), False)

    def mark_notification_done(self, notification: FakeNotification) -> None:
        self.marked_done.append(notification)

    def get_repos(self) -> list[FakeRepo]:
        return list(self.repos)

    def get_open_pull_requests(self, repo_full_name: str) -> list[FakePullRequest]:
        self.queried_repos.append(repo_full_name)
        return list(self.open_pulls.get(repo_full_name, []))

    def get_open_issues(self, repo_full_name: str) -> list[FakeIssue]:
        self.queried_repos.append(repo_full_name)
        return list(self.open_issues.get(repo_full_name, []))


@pytest.fixture
def client() -> FakeClient:
    return FakeClient()


@pytest.fixture(autouse=True)
def isolated_done_cache(tmp_path, monkeypatch):
    """Point `gb.state` at a per-test cache file so tests don't share state."""
    cache_file = tmp_path / "done-threads.json"
    monkeypatch.setattr("gb.state.cache_path", lambda: cache_file)
    return cache_file


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Point `gb.config` at a per-test (absent by default) config file."""
    config_file = tmp_path / "config.toml"
    monkeypatch.setattr("gb.config.config_path", lambda: config_file)
    return config_file
