from __future__ import annotations

import io

import pytest
from rich.console import Console
from typer.testing import CliRunner

from gb import cli
from gb.repos import OpenIssue, OpenPullRequest
from tests.conftest import (
    FakeClient,
    FakeRepo,
    make_check_suite_notification,
    make_issue,
    make_issue_notification,
    make_pr,
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


def test_version_flag_prints_package_version():
    import re

    from gb import __version__

    result = runner.invoke(cli.app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == __version__
    # Sanity: matches a PEP 440-ish dotted form, not the placeholder string.
    assert re.match(r"\d+\.\d+\.\d+", __version__)


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


def test_prs_list_reports_nothing_open():
    cli.set_client_factory(lambda: FakeClient(repos=[FakeRepo("a/b")]))
    result = runner.invoke(cli.app, ["prs", "list"])
    assert result.exit_code == 0, result.output
    assert "No open pull requests." in result.output


def test_prs_list_groups_by_repo():
    fake = FakeClient(
        repos=[FakeRepo("a/b"), FakeRepo("c/d")],
        open_pulls={
            "a/b": [
                make_pr(1, "one", "alice", html_url="https://github.com/a/b/pull/1"),
                make_pr(2, "two", "bob", draft=True, html_url="https://github.com/a/b/pull/2"),
            ],
            "c/d": [make_pr(9, "nine", "carol", html_url="https://github.com/c/d/pull/9")],
        },
    )
    cli.set_client_factory(lambda: fake)
    result = runner.invoke(cli.app, ["prs", "list"])
    assert result.exit_code == 0, result.output
    assert result.output == (
        "a/b (2)\n"
        "  #1  one  @alice  https://github.com/a/b/pull/1\n"
        "  #2  two  @bob  [draft]  https://github.com/a/b/pull/2\n"
        "c/d (1)\n"
        "  #9  nine  @carol  https://github.com/c/d/pull/9\n"
    )


def test_issues_list_reports_nothing_open():
    cli.set_client_factory(lambda: FakeClient(repos=[FakeRepo("a/b")]))
    result = runner.invoke(cli.app, ["issues", "list"])
    assert result.exit_code == 0, result.output
    assert "No open issues." in result.output


def test_issues_list_groups_by_repo_and_drops_prs():
    fake = FakeClient(
        repos=[FakeRepo("a/b")],
        open_issues={
            "a/b": [
                make_issue(
                    4,
                    "bug report",
                    "alice",
                    labels=["bug"],
                    html_url="https://github.com/a/b/issues/4",
                ),
                make_issue(5, "a PR", "bob", pull_request=object()),
            ]
        },
    )
    cli.set_client_factory(lambda: fake)
    result = runner.invoke(cli.app, ["issues", "list"])
    assert result.exit_code == 0, result.output
    assert (
        result.output
        == "a/b (1)\n  #4  bug report  @alice  [bug]  https://github.com/a/b/issues/4\n"
    )


def test_top_level_help_lists_prs_and_issues_groups():
    result = runner.invoke(cli.app, ["--help"])
    assert "prs" in result.output
    assert "issues" in result.output


def _terminal_console() -> tuple[Console, io.StringIO]:
    buf = io.StringIO()
    return Console(file=buf, force_terminal=True, width=120, color_system="standard"), buf


def test_render_prs_links_number_and_title_without_printing_url():
    console, buf = _terminal_console()
    prs = [
        OpenPullRequest("a/b", 1, "one", "alice", False, "https://github.com/a/b/pull/1"),
        OpenPullRequest("a/b", 2, "two", "bob", True, "https://github.com/a/b/pull/2"),
    ]
    cli.render_grouped_by_repo(prs, console)
    out = buf.getvalue()
    # OSC 8 hyperlink carries the URL; the URL is not printed as visible text.
    assert "\x1b]8;" in out and "https://github.com/a/b/pull/1" in out
    assert "  https://github.com/a/b/pull/1" not in out
    for word in ("a/b", "#1", "one", "@alice", "#2", "two", "@bob", "draft"):
        assert word in out


def test_render_issues_shows_labels():
    console, buf = _terminal_console()
    issues = [OpenIssue("a/b", 4, "bug report", "alice", ("bug", "p1"), "https://x/4")]
    cli.render_grouped_by_repo(issues, console)
    assert "bug, p1" in buf.getvalue()


def test_prs_list_plain_flag_prints_urls():
    fake = FakeClient(
        repos=[FakeRepo("a/b")],
        open_pulls={"a/b": [make_pr(1, "one", "alice", html_url="https://github.com/a/b/pull/1")]},
    )
    cli.set_client_factory(lambda: fake)
    result = runner.invoke(cli.app, ["prs", "list", "--plain"])
    assert result.exit_code == 0, result.output
    assert result.output == "a/b (1)\n  #1  one  @alice  https://github.com/a/b/pull/1\n"


def _two_repo_client() -> FakeClient:
    return FakeClient(
        repos=[FakeRepo("a/keep"), FakeRepo("a/drop")],
        open_pulls={"a/keep": [make_pr(1, "keep")], "a/drop": [make_pr(2, "drop")]},
        open_issues={"a/keep": [make_issue(1, "keep")], "a/drop": [make_issue(2, "drop")]},
    )


def test_prs_list_ignore_flag_skips_repo():
    cli.set_client_factory(_two_repo_client)
    result = runner.invoke(cli.app, ["prs", "list", "--ignore", "A/DROP"])
    assert result.exit_code == 0, result.output
    assert "a/keep" in result.output and "a/drop" not in result.output


def test_issues_list_reads_ignore_from_config(isolated_config):
    isolated_config.write_text('[repos]\nignore = ["a/drop"]\n')
    cli.set_client_factory(_two_repo_client)
    result = runner.invoke(cli.app, ["issues", "list"])
    assert result.exit_code == 0, result.output
    assert "a/keep" in result.output and "a/drop" not in result.output


def test_list_reports_malformed_config(isolated_config):
    isolated_config.write_text("[repos\n")
    cli.set_client_factory(_two_repo_client)
    result = runner.invoke(cli.app, ["prs", "list"])
    assert result.exit_code == 1
    assert "config.toml" in result.output
