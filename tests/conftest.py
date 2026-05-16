"""Shared fixtures.

`FakeNotification` and `FakeClient` mimic the small surface of PyGithub
that `gb.notifications` actually uses, so the feature logic can be
tested without any network or PyGithub objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest


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


def make_pr_notification(
    repo: str = "octocat/hello",
    number: int = 1,
    title: str = "A PR",
) -> FakeNotification:
    return FakeNotification(
        subject=FakeSubject(
            type="PullRequest",
            title=title,
            url=f"https://api.github.com/repos/{repo}/pulls/{number}",
        ),
        repository=FakeRepo(full_name=repo),
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
) -> FakeNotification:
    # Real CheckSuite notifications have subject.url == None; mirror that.
    return FakeNotification(
        subject=FakeSubject(type="CheckSuite", title=title, url=None),
        repository=FakeRepo(full_name=repo),
    )


@dataclass
class FakeClient:
    notifications: list[FakeNotification] = field(default_factory=list)
    # (repo_full_name, pr_number) -> merged?
    merged: dict[tuple[str, int], bool] = field(default_factory=dict)
    marked_done: list[FakeNotification] = field(default_factory=list)

    def get_notifications(self) -> list[FakeNotification]:
        return list(self.notifications)

    def is_pr_merged(self, repo_full_name: str, pr_number: int) -> bool:
        return self.merged.get((repo_full_name, pr_number), False)

    def mark_notification_done(self, notification: FakeNotification) -> None:
        self.marked_done.append(notification)


@pytest.fixture
def client() -> FakeClient:
    return FakeClient()
