"""Local cache of notification threads we've already dismissed.

GitHub's REST API does **not** expose a "done" filter — `GET /notifications`
with `all=true` returns dismissed threads alongside in-inbox ones, and the
notification JSON has no "done" field. (The web UI's Inbox tab filters
client-side using state that isn't surfaced in the API.) So once we mark
a thread done via `DELETE /notifications/threads/{id}`, it keeps coming
back on the next fetch, and the cleanup logic would redo the (expensive)
per-thread merge check and DELETE call every run.

This module persists which thread IDs we've dismissed, keyed by `updated_at`
at dismissal time. A thread is considered "already done" iff its current
`updated_at` is <= the cached value; new activity advances `updated_at`
past the cached value and the thread is re-processed.

Cache file: `$XDG_CACHE_HOME/gb/done-threads.json`
            (default `~/.cache/gb/done-threads.json`).
Shared across every `gb notifications` subcommand.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path


def cache_path() -> Path:
    base = os.environ.get("XDG_CACHE_HOME")
    root = Path(base) if base else Path.home() / ".cache"
    return root / "gb" / "done-threads.json"


def load() -> dict[str, str]:
    path = cache_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save(cache: dict[str, str]) -> None:
    path = cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n")


def is_already_done(cache: dict[str, str], thread_id: str, updated_at: datetime) -> bool:
    cached = cache.get(thread_id)
    if cached is None:
        return False
    try:
        return updated_at <= datetime.fromisoformat(cached)
    except ValueError:
        return False


def mark_done(cache: dict[str, str], thread_id: str, updated_at: datetime) -> None:
    cache[thread_id] = updated_at.isoformat()
