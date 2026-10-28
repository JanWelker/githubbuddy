"""Thin wrapper around PyGithub.

Everything that actually touches the network lives here so the feature
modules can be unit-tested against a fake with the same surface.
"""

from __future__ import annotations

from typing import Protocol

from github import Auth, Github
from github.Issue import Issue
from github.Notification import Notification
from github.PullRequest import PullRequest
from github.Repository import Repository


class GitHubClientProtocol(Protocol):
    def get_notifications(self) -> list[Notification]: ...
    def is_pr_merged(self, repo_full_name: str, pr_number: int) -> bool: ...
    def mark_notification_done(self, notification: Notification) -> None: ...
    def get_repos(self) -> list[Repository]: ...
    def get_open_pull_requests(self, repo_full_name: str) -> list[PullRequest]: ...
    def get_open_issues(self, repo_full_name: str) -> list[Issue]: ...


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

    def get_repos(self) -> list[Repository]:
        # GET /user/repos — every repo the token can see: owned, collaborator,
        # and org-member repos. Archived repos are included; features filter.
        return list(self._gh.get_user().get_repos())

    def get_open_pull_requests(self, repo_full_name: str) -> list[PullRequest]:
        # lazy=True skips the GET /repos/{owner}/{repo} round trip; only the
        # pulls listing hits the network.
        repo = self._gh.get_repo(repo_full_name, lazy=True)
        return list(repo.get_pulls(state="open"))

    def get_open_issues(self, repo_full_name: str) -> list[Issue]:
        # GET /repos/{owner}/{repo}/issues also returns PRs (each PR is an
        # issue to the REST API); callers filter on `issue.pull_request`.
        repo = self._gh.get_repo(repo_full_name, lazy=True)
        return list(repo.get_issues(state="open"))
