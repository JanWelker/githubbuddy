"""`gb` CLI entrypoint.

Subcommands are grouped by feature area (e.g. `gb notifications ...`) so
new features can be added without crowding the top level.
"""

from __future__ import annotations

import os
from collections.abc import Callable

import typer

from gb.github_client import GitHubClient, GitHubClientProtocol
from gb.notifications import cleanup_failed_ci_notifications, cleanup_merged_pr_notifications

app = typer.Typer(help="Personal CLI for daily GitHub chores.", no_args_is_help=True)
notifications_app = typer.Typer(help="Work with GitHub notifications.", no_args_is_help=True)
app.add_typer(notifications_app, name="notifications")


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
