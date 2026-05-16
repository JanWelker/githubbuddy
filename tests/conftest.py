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

    def get_notifications(self) -> list[FakeNotification]:
        return list(self.notifications)

    def is_pr_merged(self, repo_full_name: str, pr_number: int) -> bool:
        self.is_pr_merged_calls.append((repo_full_name, pr_number))
        return self.merged.get((repo_full_name, pr_number), False)

    def mark_notification_done(self, notification: FakeNotification) -> None:
        self.marked_done.append(notification)


@pytest.fixture
def client() -> FakeClient:
    return FakeClient()


@pytest.fixture(autouse=True)
def isolated_done_cache(tmp_path, monkeypatch):
    """Point `gb.state` at a per-test cache file so tests don't share state."""
    cache_file = tmp_path / "done-threads.json"
    monkeypatch.setattr("gb.state.cache_path", lambda: cache_file)
    return cache_file
