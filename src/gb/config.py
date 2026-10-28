"""User configuration.

Config file: `$XDG_CONFIG_HOME/gb/config.toml` (default `~/.config/gb/config.toml`).

```toml
[repos]
# Repositories `prs list` / `issues list` skip, as owner/name (case-insensitive).
ignore = ["somuch-cloud/homelab"]
```

A missing file means defaults. A malformed file is an error: silently
ignoring it would make a typo look like the setting doesn't work.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    ignored_repos: frozenset[str] = field(default_factory=frozenset)

    def is_ignored(self, repo_full_name: str) -> bool:
        return repo_full_name.lower() in self.ignored_repos


def config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "gb" / "config.toml"


def load() -> Config:
    path = config_path()
    if not path.exists():
        return Config()
    try:
        data = tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    return parse(data, source=str(path))


def parse(data: dict, *, source: str = "config") -> Config:
    repos = data.get("repos", {})
    if not isinstance(repos, dict):
        raise ConfigError(f"{source}: [repos] must be a table")
    ignore = repos.get("ignore", [])
    if not isinstance(ignore, list) or not all(isinstance(r, str) for r in ignore):
        raise ConfigError(f"{source}: repos.ignore must be a list of strings")
    return Config(ignored_repos=frozenset(r.lower() for r in ignore))
