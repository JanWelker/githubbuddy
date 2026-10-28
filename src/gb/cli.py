"""`gb` CLI entrypoint.

Subcommands are grouped by feature area (e.g. `gb notifications ...`) so
new features can be added without crowding the top level.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from itertools import groupby

import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text

from gb import __version__
from gb.github_client import GitHubClient, GitHubClientProtocol
from gb.notifications import cleanup_failed_ci_notifications, cleanup_merged_pr_notifications
from gb.repos import OpenIssue, OpenPullRequest, list_open_issues, list_open_pull_requests

app = typer.Typer(help="Personal CLI for daily GitHub chores.", no_args_is_help=True)
notifications_app = typer.Typer(help="Work with GitHub notifications.", no_args_is_help=True)
app.add_typer(notifications_app, name="notifications")
prs_app = typer.Typer(help="Work with pull requests across all your repos.", no_args_is_help=True)
app.add_typer(prs_app, name="prs")
issues_app = typer.Typer(help="Work with issues across all your repos.", no_args_is_help=True)
app.add_typer(issues_app, name="issues")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(
        False,
        "--version",
        help="Show the version and exit.",
        is_eager=True,
        callback=_version_callback,
    ),
) -> None:
    pass


def _default_client_factory() -> GitHubClientProtocol:
    return GitHubClient(_require_token())


# Indirection so tests can inject a fake client without monkeypatching env vars.
_client_factory: Callable[[], GitHubClientProtocol] = _default_client_factory


def _require_token() -> str:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        typer.echo("Error: GITHUB_TOKEN is not set.", err=True)
        raise typer.Exit(code=1)
    return token


def set_client_factory(factory: Callable[[], GitHubClientProtocol]) -> None:
    """Override the client factory (used by tests)."""
    global _client_factory
    _client_factory = factory


@notifications_app.command("cleanup-merged")
def cleanup_merged() -> None:
    """Mark notifications for already-merged PRs as done."""
    client = _client_factory()
    cleaned = cleanup_merged_pr_notifications(client)
    if not cleaned:
        typer.echo("No merged PR notifications to clean up.")
        return
    typer.echo(f"Marked {len(cleaned)} notification(s) as done:")
    for item in cleaned:
        typer.echo(f"  - {item}")


@notifications_app.command("cleanup-failed-ci")
def cleanup_failed_ci() -> None:
    """Mark notifications for failed CI check suites as done."""
    client = _client_factory()
    cleaned = cleanup_failed_ci_notifications(client)
    if not cleaned:
        typer.echo("No failed CI notifications to clean up.")
        return
    typer.echo(f"Marked {len(cleaned)} notification(s) as done:")
    for item in cleaned:
        typer.echo(f"  - {item}")


def _echo_grouped_by_repo(items: Sequence[OpenPullRequest | OpenIssue]) -> None:
    """Plain text: one header line per repo, then `str(item)` lines ending in the URL.

    Used when stdout is not a terminal (pipes, tests) or with --plain, so the
    URL stays greppable instead of hiding inside a terminal hyperlink.
    """
    for repo, group in groupby(items, key=lambda item: item.repo):
        members = list(group)
        typer.echo(f"{repo} ({len(members)})")
        for item in members:
            typer.echo(f"  {item}")


def _badges(item: OpenPullRequest | OpenIssue) -> Text:
    if isinstance(item, OpenPullRequest):
        return Text("draft", style="yellow") if item.draft else Text("")
    return Text(", ".join(item.labels), style="magenta")


def render_grouped_by_repo(items: Sequence[OpenPullRequest | OpenIssue], console: Console) -> None:
    """Rich output: a bold repo header and an aligned table per repo.

    The number and title are OSC 8 hyperlinks to the item on github.com, so
    the long URL doesn't have to be printed (and wrapped) on every line.
    """
    # Fixed widths so the columns line up across repos, not just within one.
    number_width = max(len(f"#{item.number}") for item in items)
    author_width = max(len(f"@{item.author}") for item in items)
    for repo, group in groupby(items, key=lambda item: item.repo):
        members = list(group)
        header = Text(repo, style="bold")
        header.append(f"  {len(members)}", style="dim")
        console.print(header)
        table = Table(box=None, show_header=False, pad_edge=False, padding=(0, 1))
        table.add_column(justify="right", style="cyan", no_wrap=True, width=number_width)
        table.add_column(ratio=1)
        table.add_column(style="dim", no_wrap=True, width=author_width)
        table.add_column(no_wrap=True)
        for item in members:
            link = f"link {item.url}"
            table.add_row(
                Text(f"#{item.number}", style=link),
                Text(item.title, style=link),
                Text(f"@{item.author}"),
                _badges(item),
            )
        console.print(table)


_console = Console()

PLAIN_OPTION = typer.Option(
    False,
    "--plain",
    help="Plain text with one URL per line (the default when stdout is not a terminal).",
)


def _emit(items: Sequence[OpenPullRequest | OpenIssue], plain: bool) -> None:
    if plain or not _console.is_terminal:
        _echo_grouped_by_repo(items)
    else:
        render_grouped_by_repo(items, _console)


@prs_app.command("list")
def prs_list(plain: bool = PLAIN_OPTION) -> None:
    """List all open pull requests in all your repos."""
    client = _client_factory()
    prs = list_open_pull_requests(client)
    if not prs:
        typer.echo("No open pull requests.")
        return
    _emit(prs, plain)


@issues_app.command("list")
def issues_list(plain: bool = PLAIN_OPTION) -> None:
    """List all open issues in all your repos."""
    client = _client_factory()
    issues = list_open_issues(client)
    if not issues:
        typer.echo("No open issues.")
        return
    _emit(issues, plain)
