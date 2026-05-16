"""Thin wrapper around PyGithub.

Everything that actually touches the network lives here so the feature
modules can be unit-tested against a fake with the same surface.
"""

from __future__ import annotations

from typing import Protocol

from github import Auth, Github
from github.Notification import Notification


class GitHubClientProtocol(Protocol):
    def get_notifications(self) -> list[Notification]: ...
    def is_pr_merged(self, repo_full_name: str, pr_number: int) -> bool: ...
    def mark_notification_done(self, notification: Notification) -> None: ...


class GitHubClient:
    def __init__(self, token: str) -> None:
        self._gh = Github(auth=Auth.Token(token))

    def get_notifications(self) -> list[Notification]:
        # all=True: include already-read threads. GitHub's Inbox shows "not done"
        # while the API default filters by "unread" — we want everything still in
        # the inbox so we can dismiss merged-PR threads that the user already opened.
        return list(self._gh.get_user().get_notifications(all=True))

    def is_pr_merged(self, repo_full_name: str, pr_number: int) -> bool:
        return self._gh.get_repo(repo_full_name).get_pull(pr_number).merged

    def mark_notification_done(self, notification: Notification) -> None:
        # PyGithub exposes mark_as_read (PATCH); "done" requires DELETE on the
        # thread URL, which isn't a typed method, so we go through the requester.
        notification._requester.requestJsonAndCheck("DELETE", notification.url)
