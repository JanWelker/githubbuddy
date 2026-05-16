from __future__ import annotations

from datetime import UTC, datetime, timedelta

from gb import state


def test_load_returns_empty_dict_when_file_missing(isolated_done_cache):
    assert state.load() == {}


def test_save_then_load_roundtrip(isolated_done_cache):
    when = datetime(2026, 5, 16, 12, 0, tzinfo=UTC)
    cache: dict[str, str] = {}
    state.mark_done(cache, "42", when)
    state.save(cache)
    assert state.load() == {"42": when.isoformat()}


def test_load_returns_empty_dict_on_corrupt_file(isolated_done_cache):
    isolated_done_cache.parent.mkdir(parents=True, exist_ok=True)
    isolated_done_cache.write_text("{not valid json")
    assert state.load() == {}


def test_is_already_done_false_when_thread_not_cached():
    assert state.is_already_done({}, "1", datetime(2026, 1, 1, tzinfo=UTC)) is False


def test_is_already_done_true_when_updated_at_equal():
    when = datetime(2026, 1, 1, tzinfo=UTC)
    cache = {"1": when.isoformat()}
    assert state.is_already_done(cache, "1", when) is True


def test_is_already_done_true_when_updated_at_older():
    cached = datetime(2026, 1, 2, tzinfo=UTC)
    earlier = cached - timedelta(hours=1)
    cache = {"1": cached.isoformat()}
    assert state.is_already_done(cache, "1", earlier) is True


def test_is_already_done_false_when_thread_reactivated():
    cached = datetime(2026, 1, 1, tzinfo=UTC)
    later = cached + timedelta(hours=1)
    cache = {"1": cached.isoformat()}
    # New activity advanced updated_at past the cache → re-process.
    assert state.is_already_done(cache, "1", later) is False
