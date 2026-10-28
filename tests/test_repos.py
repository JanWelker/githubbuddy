from __future__ import annotations

from gb.repos import OpenIssue, OpenPullRequest, list_open_issues, list_open_pull_requests
from tests.conftest import FakeClient, FakeRepo, make_issue, make_pr

# --- prs list --------------------------------------------------------------


def test_list_open_prs_empty_when_no_repos(client: FakeClient):
    assert list_open_pull_requests(client) == []


def test_list_open_prs_collects_across_repos_sorted():
    client = FakeClient(
        repos=[FakeRepo("zed/last"), FakeRepo("Alpha/first")],
        open_pulls={
            "zed/last": [make_pr(7, "zed pr", "bob")],
            "Alpha/first": [
                make_pr(3, "second", "carol", draft=True),
                make_pr(1, "first", "alice"),
            ],
        },
    )
    assert list_open_pull_requests(client) == [
        OpenPullRequest("Alpha/first", 1, "first", "alice", False, ""),
        OpenPullRequest("Alpha/first", 3, "second", "carol", True, ""),
        OpenPullRequest("zed/last", 7, "zed pr", "bob", False, ""),
    ]


def test_list_open_prs_skips_archived_and_idle_repos():
    client = FakeClient(
        repos=[
            FakeRepo("a/active"),
            FakeRepo("a/archived", archived=True),
            FakeRepo("a/idle", open_issues_count=0),
        ],
        open_pulls={"a/archived": [make_pr()], "a/idle": [make_pr()]},
    )
    assert list_open_pull_requests(client) == []
    assert client.queried_repos == ["a/active"]


def test_open_pr_str_marks_draft():
    assert str(make_open_pr(draft=True)) == "#5  Title  @alice  [draft]"
    assert str(make_open_pr(draft=False)) == "#5  Title  @alice"


def make_open_pr(**kw) -> OpenPullRequest:
    base = dict(repo="a/b", number=5, title="Title", author="alice", draft=False, url="")
    return OpenPullRequest(**{**base, **kw})


# --- issues list -----------------------------------------------------------


def test_list_open_issues_excludes_pull_requests():
    client = FakeClient(
        repos=[FakeRepo("a/b")],
        open_issues={
            "a/b": [
                make_issue(2, "real issue", "bob", labels=["bug", "help wanted"]),
                make_issue(3, "actually a PR", "bob", pull_request=object()),
            ]
        },
    )
    assert list_open_issues(client) == [
        OpenIssue("a/b", 2, "real issue", "bob", ("bug", "help wanted"), ""),
    ]


def test_list_open_issues_skips_archived_and_idle_repos():
    client = FakeClient(
        repos=[FakeRepo("a/archived", archived=True), FakeRepo("a/idle", open_issues_count=0)],
        open_issues={"a/archived": [make_issue()], "a/idle": [make_issue()]},
    )
    assert list_open_issues(client) == []
    assert client.queried_repos == []


def test_open_issue_str_lists_labels():
    issue = OpenIssue("a/b", 9, "Title", "alice", ("bug",), "")
    assert str(issue) == "#9  Title  @alice  [bug]"
    assert str(OpenIssue("a/b", 9, "Title", "alice", (), "")) == "#9  Title  @alice"
