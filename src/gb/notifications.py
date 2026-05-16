"""Notification-cleanup features.

Pure functions that operate on a `GitHubClientProtocol` so tests can pass
in a fake without monkeypatching PyGithub. Each `cleanup_*` function
returns the list of items it dismissed.

Both cleanup functions filter out threads we've previously dismissed via
the local cache in `gb.state` — GitHub's API returns "done" threads
alongside in-inbox ones, so without the filter we'd redo the per-thread
work every run. See `gb.state` for the full rationale.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from gb import state
from gb.github_client import GitHubClientProtocol


def _iter_not_done(client: GitHubClientProtocol, cache: dict[str, str]) -> Iterator:
    """Yield notifications we haven't already dismissed at their current updated_at."""
    for notif in client.get_notifications():
        if state.is_already_done(cache, str(notif.id), notif.updated_at):
            continue
        yield notif


# --- cleanup-merged: PRs that are already merged ---------------------------


@dataclass(frozen=True)
class CleanedPullRequest:
    repo: str
    number: int
    title: str

    def __str__(self) -> str:
        return f"{self.repo}#{self.number} {self.title}"


def is_pr_notification(notification) -> bool:
    return notification.subject.type == "PullRequest"


def pr_number_from_subject_url(url: str) -> int:
    # subject.url looks like https://api.github.com/repos/<owner>/<repo>/pulls/<n>
    return int(url.rsplit("/", 1)[-1])


def cleanup_merged_pr_notifications(
    client: GitHubClientProtocol,
) -> list[CleanedPullRequest]:
    """Mark every PR notification whose PR is merged as done."""
    cache = state.load()
    cleaned: list[CleanedPullRequest] = []
    for notif in _iter_not_done(client, cache):
        if not is_pr_notification(notif):
            continue
        repo = notif.repository.full_name
        number = pr_number_from_subject_url(notif.subject.url)
        if not client.is_pr_merged(repo, number):
            continue
        client.mark_notification_done(notif)
        state.mark_done(cache, str(notif.id), notif.updated_at)
        cleaned.append(CleanedPullRequest(repo=repo, number=number, title=notif.subject.title))
    state.save(cache)
    return cleaned


# --- cleanup-failed-ci: failed CheckSuite runs -----------------------------


@dataclass(frozen=True)
class CleanedCheckSuite:
    repo: str
    title: str

    def __str__(self) -> str:
        return f"{self.repo} — {self.title}"


def is_check_suite_notification(notification) -> bool:
    return notification.subject.type == "CheckSuite"


def cleanup_failed_ci_notifications(
    client: GitHubClientProtocol,
) -> list[CleanedCheckSuite]:
    """Mark CheckSuite notifications as done.

    GitHub's notification API returns `subject.url = null` for CheckSuite
    threads, so we cannot independently verify each suite's conclusion.
    In practice GitHub only emits CheckSuite notifications for failed
    workflow runs (default user notification settings), so the presence
    of the notification is itself the signal.
    """
    cache = state.load()
    cleaned: list[CleanedCheckSuite] = []
    for notif in _iter_not_done(client, cache):
        if not is_check_suite_notification(notif):
            continue
        client.mark_notification_done(notif)
        state.mark_done(cache, str(notif.id), notif.updated_at)
        cleaned.append(
            CleanedCheckSuite(repo=notif.repository.full_name, title=notif.subject.title)
        )
    state.save(cache)
    return cleaned
