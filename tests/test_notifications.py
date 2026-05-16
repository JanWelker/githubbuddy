from __future__ import annotations

from datetime import UTC, datetime, timedelta

from gb import state
from gb.notifications import (
    CleanedCheckSuite,
    CleanedPullRequest,
    cleanup_failed_ci_notifications,
    cleanup_merged_pr_notifications,
    is_check_suite_notification,
    is_pr_notification,
    pr_number_from_subject_url,
)
from tests.conftest import (
    FakeClient,
    make_check_suite_notification,
    make_issue_notification,
    make_pr_notification,
)

# --- cleanup-merged --------------------------------------------------------


def test_pr_number_from_subject_url():
    url = "https://api.github.com/repos/octocat/hello/pulls/42"
    assert pr_number_from_subject_url(url) == 42


def test_is_pr_notification_true_for_pr():
    assert is_pr_notification(make_pr_notification()) is True


def test_is_pr_notification_false_for_issue():
    assert is_pr_notification(make_issue_notification()) is False


def test_cleanup_marks_only_merged_prs(client: FakeClient):
    merged = make_pr_notification(repo="octocat/hello", number=1, title="merged one")
    open_pr = make_pr_notification(repo="octocat/hello", number=2, title="still open")
    issue = make_issue_notification(repo="octocat/hello", number=3)
    client.notifications = [merged, open_pr, issue]
    client.merged = {("octocat/hello", 1): True, ("octocat/hello", 2): False}

    cleaned = cleanup_merged_pr_notifications(client)

    assert cleaned == [CleanedPullRequest(repo="octocat/hello", number=1, title="merged one")]
    assert client.marked_done == [merged]


def test_cleanup_ignores_non_pr_notifications_without_calling_merged(client: FakeClient):
    client.notifications = [make_issue_notification()]
    cleaned = cleanup_merged_pr_notifications(client)
    assert cleaned == []
    assert client.marked_done == []


def test_cleanup_merged_returns_empty_when_no_notifications(client: FakeClient):
    assert cleanup_merged_pr_notifications(client) == []
    assert client.marked_done == []


def test_cleanup_merged_handles_multiple_repos(client: FakeClient):
    a = make_pr_notification(repo="a/x", number=1, title="A")
    b = make_pr_notification(repo="b/y", number=7, title="B")
    client.notifications = [a, b]
    client.merged = {("a/x", 1): True, ("b/y", 7): True}

    cleaned = cleanup_merged_pr_notifications(client)

    assert {str(c) for c in cleaned} == {"a/x#1 A", "b/y#7 B"}
    assert client.marked_done == [a, b]


def test_cleaned_pull_request_str_format():
    c = CleanedPullRequest(repo="octocat/hello", number=4, title="hi")
    assert str(c) == "octocat/hello#4 hi"


# --- cleanup-failed-ci -----------------------------------------------------


def test_is_check_suite_notification_true_for_check_suite():
    assert is_check_suite_notification(make_check_suite_notification()) is True


def test_is_check_suite_notification_false_for_pr():
    assert is_check_suite_notification(make_pr_notification()) is False


def test_is_check_suite_notification_false_for_issue():
    assert is_check_suite_notification(make_issue_notification()) is False


def test_cleanup_marks_all_check_suite_notifications(client: FakeClient):
    a = make_check_suite_notification(repo="a/x", title="build broke")
    b = make_check_suite_notification(repo="b/y", title="startup failed")
    client.notifications = [a, b]

    cleaned = cleanup_failed_ci_notifications(client)

    assert cleaned == [
        CleanedCheckSuite(repo="a/x", title="build broke"),
        CleanedCheckSuite(repo="b/y", title="startup failed"),
    ]
    assert client.marked_done == [a, b]


def test_cleanup_failed_ci_ignores_non_check_suite_notifications(client: FakeClient):
    client.notifications = [make_pr_notification(), make_issue_notification()]
    cleaned = cleanup_failed_ci_notifications(client)
    assert cleaned == []
    assert client.marked_done == []


def test_cleanup_failed_ci_returns_empty_when_no_notifications(client: FakeClient):
    assert cleanup_failed_ci_notifications(client) == []
    assert client.marked_done == []


def test_cleanup_failed_ci_mixed_notification_types(client: FakeClient):
    cs = make_check_suite_notification(repo="a/x", title="oops")
    pr = make_pr_notification(repo="a/x", number=1)
    issue = make_issue_notification()
    client.notifications = [pr, cs, issue]

    cleaned = cleanup_failed_ci_notifications(client)

    assert cleaned == [CleanedCheckSuite(repo="a/x", title="oops")]
    assert client.marked_done == [cs]


def test_cleaned_check_suite_str_format():
    c = CleanedCheckSuite(repo="a/x", title="oops")
    assert str(c) == "a/x — oops"


# --- done-cache integration (applies to both cleanup-* functions) -----------


def test_cleanup_merged_skips_threads_already_in_done_cache(client: FakeClient):
    cached = make_pr_notification(repo="a/x", number=1, id="t-1", title="already done")
    fresh = make_pr_notification(repo="a/x", number=2, id="t-2", title="new merged")
    client.notifications = [cached, fresh]
    client.merged = {("a/x", 2): True}

    # Seed the on-disk cache with the first thread at its current updated_at.
    state.save({"t-1": cached.updated_at.isoformat()})

    cleaned = cleanup_merged_pr_notifications(client)

    assert cleaned == [CleanedPullRequest(repo="a/x", number=2, title="new merged")]
    assert client.marked_done == [fresh]
    # Crucially, we should not have hit is_pr_merged for the cached thread.
    assert client.is_pr_merged_calls == [("a/x", 2)]


def test_cleanup_merged_reprocesses_thread_with_newer_updated_at(client: FakeClient):
    earlier = datetime(2026, 5, 1, tzinfo=UTC)
    later = earlier + timedelta(days=1)
    reactivated = make_pr_notification(
        repo="a/x", number=1, id="t-1", title="reactivated", updated_at=later
    )
    client.notifications = [reactivated]
    client.merged = {("a/x", 1): True}
    # Cache says we processed this thread at the earlier timestamp.
    state.save({"t-1": earlier.isoformat()})

    cleaned = cleanup_merged_pr_notifications(client)

    assert len(cleaned) == 1
    assert client.is_pr_merged_calls == [("a/x", 1)]
    assert client.marked_done == [reactivated]


def test_cleanup_merged_persists_newly_dismissed_threads(client: FakeClient, isolated_done_cache):
    n = make_pr_notification(repo="a/x", number=1, id="t-1")
    client.notifications = [n]
    client.merged = {("a/x", 1): True}

    cleanup_merged_pr_notifications(client)

    # Re-load from disk to be sure save() was called, not just the in-memory dict.
    assert state.load() == {"t-1": n.updated_at.isoformat()}


def test_cleanup_failed_ci_skips_threads_already_in_done_cache(client: FakeClient):
    cached = make_check_suite_notification(repo="a/x", id="t-1", title="old failure")
    fresh = make_check_suite_notification(repo="a/x", id="t-2", title="new failure")
    client.notifications = [cached, fresh]
    state.save({"t-1": cached.updated_at.isoformat()})

    cleaned = cleanup_failed_ci_notifications(client)

    assert cleaned == [CleanedCheckSuite(repo="a/x", title="new failure")]
    assert client.marked_done == [fresh]


def test_cleanup_failed_ci_persists_newly_dismissed_threads(client: FakeClient):
    n = make_check_suite_notification(repo="a/x", id="t-7", title="boom")
    client.notifications = [n]

    cleanup_failed_ci_notifications(client)

    assert state.load() == {"t-7": n.updated_at.isoformat()}
