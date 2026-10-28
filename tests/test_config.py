from __future__ import annotations

import pytest

from gb import config


def test_load_returns_defaults_when_file_missing(isolated_config):
    assert config.load() == config.Config()


def test_load_reads_ignored_repos_case_insensitively(isolated_config):
    isolated_config.write_text('[repos]\nignore = ["SomuCH-cloud/Homelab", "a/b"]\n')
    cfg = config.load()
    assert cfg.ignored_repos == frozenset({"somuch-cloud/homelab", "a/b"})
    assert cfg.is_ignored("somuch-cloud/HOMELAB") is True
    assert cfg.is_ignored("a/c") is False


def test_load_rejects_malformed_toml(isolated_config):
    isolated_config.write_text("[repos\nignore = [")
    with pytest.raises(config.ConfigError, match="config.toml"):
        config.load()


@pytest.mark.parametrize("body", ['[repos]\nignore = "a/b"', "[repos]\nignore = [1]", "repos = 3"])
def test_load_rejects_wrong_types(isolated_config, body):
    isolated_config.write_text(body)
    with pytest.raises(config.ConfigError):
        config.load()
