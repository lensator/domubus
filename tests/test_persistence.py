"""Tests for domubus.persistence module."""

import json
import tempfile
from pathlib import Path

import pytest

from domubus.persistence import JSONLPersistence


class TestJSONLPersistence:
    """Tests for JSONLPersistence."""

    def test_append_and_load(self, tmp_path: Path):
        """Can append events and load them back."""
        file_path = tmp_path / "events.jsonl"
        persistence = JSONLPersistence(file_path)
        persistence.open()

        event1 = {"event_type": "test1", "data": {"a": 1}}
        event2 = {"event_type": "test2", "data": {"b": 2}}
        persistence.append(event1)
        persistence.append(event2)
        persistence.close()

        # Reload
        loaded = persistence.load()
        assert len(loaded) == 2
        assert loaded[0] == event1
        assert loaded[1] == event2

    def test_creates_parent_dirs(self, tmp_path: Path):
        """Creates parent directories if they don't exist."""
        file_path = tmp_path / "nested" / "dir" / "events.jsonl"
        persistence = JSONLPersistence(file_path)
        persistence.open()
        persistence.append({"test": True})
        persistence.close()

        assert file_path.exists()

    def test_load_empty_file(self, tmp_path: Path):
        """Load returns empty list for empty/nonexistent file."""
        file_path = tmp_path / "empty.jsonl"
        persistence = JSONLPersistence(file_path)

        loaded = persistence.load()
        assert loaded == []

    def test_skips_corrupted_lines(self, tmp_path: Path):
        """Load skips corrupted JSON lines."""
        file_path = tmp_path / "corrupted.jsonl"

        # Write mixed valid/invalid lines
        with open(file_path, "w") as f:
            f.write('{"event_type": "valid1"}\n')
            f.write('not valid json\n')
            f.write('{"event_type": "valid2"}\n')
            f.write('}\n')

        persistence = JSONLPersistence(file_path)
        loaded = persistence.load()

        assert len(loaded) == 2
        assert loaded[0]["event_type"] == "valid1"
        assert loaded[1]["event_type"] == "valid2"

    def test_max_events_limit(self, tmp_path: Path):
        """Load respects max_events limit."""
        file_path = tmp_path / "limit.jsonl"
        persistence = JSONLPersistence(file_path, max_events=3)
        persistence.open()

        for i in range(10):
            persistence.append({"event_type": f"event{i}"})
        persistence.close()

        loaded = persistence.load()
        assert len(loaded) == 3
        # Should be the last 3 events
        assert loaded[0]["event_type"] == "event7"
        assert loaded[1]["event_type"] == "event8"
        assert loaded[2]["event_type"] == "event9"

    def test_compact(self, tmp_path: Path):
        """Compact reduces file to max_events."""
        file_path = tmp_path / "compact.jsonl"
        persistence = JSONLPersistence(file_path, max_events=5)
        persistence.open()

        for i in range(20):
            persistence.append({"event_type": f"event{i}"})
        persistence.close()

        removed = persistence.compact()
        assert removed == 15

        # Verify file now has only 5 events
        loaded = persistence.load()
        assert len(loaded) == 5
        assert loaded[0]["event_type"] == "event15"

    def test_clear(self, tmp_path: Path):
        """Clear removes all events."""
        file_path = tmp_path / "clear.jsonl"
        persistence = JSONLPersistence(file_path)
        persistence.open()
        persistence.append({"test": True})
        persistence.close()

        persistence.clear()
        loaded = persistence.load()
        assert loaded == []

    def test_event_count(self, tmp_path: Path):
        """event_count returns correct count."""
        file_path = tmp_path / "count.jsonl"
        persistence = JSONLPersistence(file_path)
        persistence.open()

        assert persistence.event_count() == 0
        persistence.append({"event": 1})
        persistence.append({"event": 2})
        persistence.close()

        assert persistence.event_count() == 2

    def test_is_open(self, tmp_path: Path):
        """is_open returns correct state."""
        file_path = tmp_path / "open.jsonl"
        persistence = JSONLPersistence(file_path)

        assert not persistence.is_open()
        persistence.open()
        assert persistence.is_open()
        persistence.close()
        assert not persistence.is_open()

    def test_fsync_disabled(self, tmp_path: Path):
        """Can disable fsync for faster writes."""
        file_path = tmp_path / "nofsync.jsonl"
        persistence = JSONLPersistence(file_path, fsync=False)
        persistence.open()
        persistence.append({"test": True})
        persistence.close()

        loaded = persistence.load()
        assert len(loaded) == 1

