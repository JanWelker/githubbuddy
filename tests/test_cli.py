from __future__ import annotations

import pytest
from typer.testing import CliRunner

from gb import cli
from tests.conftest import (
    FakeClient,
    make_check_suite_notification,
    make_issue_notification,
    make_pr_notification,
)

runner = CliRunner()


@pytest.fixture(autouse=True)
def reset_factory():
    """Restore the real factory after each test."""
    original = cli._client_factory
    yield
    cli.set_client_factory(original)


def test_cleanup_merged_reports_nothing_to_do():
    cli.set_client_factory(lambda: FakeClient())
    result = runner.invoke(cli.app, ["notifications", "cleanup-merged"])
    assert result.exit_code == 0, result.output
    assert "No merged PR notifications" in result.output


def test_cleanup_merged_marks_and_reports():
    fake = FakeClient(
        notifications=[
            make_pr_notification(repo="octocat/hello", number=1, title="merged one"),
            make_pr_notification(repo="octocat/hello", number=2, title="still open"),
            make_issue_notification(),
        ],
        merged={("octocat/hello", 1): True, ("octocat/hello", 2): False},
    )
    cli.set_client_factory(lambda: fake)

    result = runner.invoke(cli.app, ["notifications", "cleanup-merged"])

    assert result.exit_code == 0, result.output
    assert "Marked 1 notification(s) as done" in result.output
    assert "octocat/hello#1 merged one" in result.output
    assert "octocat/hello#2" not in result.output
    assert len(fake.marked_done) == 1


def test_missing_token_exits_nonzero(monkeypatch):
    # Use the real factory (which reads the env) by resetting it.
    cli.set_client_factory(lambda: cli.GitHubClient(cli._require_token()))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    result = runner.invoke(cli.app, ["notifications", "cleanup-merged"])
    assert result.exit_code == 1
    assert "GITHUB_TOKEN" in result.output


def test_top_level_help_lists_notifications_group():
    result = runner.invoke(cli.app, ["--help"])
    assert result.exit_code == 0
    assert "notifications" in result.output


def test_cleanup_failed_ci_reports_nothing_to_do():
    cli.set_client_factory(lambda: FakeClient())
    result = runner.invoke(cli.app, ["notifications", "cleanup-failed-ci"])
    assert result.exit_code == 0, result.output
    assert "No failed CI notifications" in result.output


def test_cleanup_failed_ci_marks_and_reports():
    fake = FakeClient(
        notifications=[
            make_check_suite_notification(repo="a/x", title="build broke"),
            make_check_suite_notification(repo="b/y", title="startup failed"),
            make_pr_notification(),
        ],
    )
    cli.set_client_factory(lambda: fake)

    result = runner.invoke(cli.app, ["notifications", "cleanup-failed-ci"])

    assert result.exit_code == 0, result.output
    assert "Marked 2 notification(s) as done" in result.output
    assert "a/x — build broke" in result.output
    assert "b/y — startup failed" in result.output
    assert len(fake.marked_done) == 2
