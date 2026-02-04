"""Persistence layer for domubus.

This module provides WAL-style (Write-Ahead Logging) persistence to JSONL files.
Events are appended one per line as JSON, enabling efficient append and recovery.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import IO, Any


class JSONLPersistence:
    """WAL-style persistence to JSONL file.

    Events are appended as JSON lines to a file. On load, corrupted lines are
    skipped gracefully. The file can be compacted to remove old events.

    Example:
        persistence = JSONLPersistence("~/.myapp/events.jsonl", max_events=10000)
        persistence.open()
        persistence.append({"event_type": "test", "data": {}})
        events = persistence.load()
        persistence.close()
    """

    def __init__(
        self,
        file_path: str | Path,
        *,
        max_events: int = 10000,
        fsync: bool = True,
    ) -> None:
        """Initialize persistence.

        Args:
            file_path: Path to the JSONL file (will be created if not exists).
            max_events: Maximum events to keep when loading/compacting.
            fsync: If True, flush and fsync after each write for durability.
        """
        self.file_path = Path(file_path).expanduser()
        self.max_events = max_events
        self.fsync = fsync
        self._file: IO[str] | None = None

    def open(self) -> None:
        """Open file for appending."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.file_path, "a", encoding="utf-8")

    def close(self) -> None:
        """Close file handle."""
        if self._file:
            self._file.close()
            self._file = None

    def is_open(self) -> bool:
        """Check if the file is currently open."""
        return self._file is not None

    def append(self, event: dict[str, Any]) -> None:
        """Append an event to file (WAL-style).

        Args:
            event: Event dictionary to persist.
        """
        if not self._file:
            self.open()

        assert self._file is not None  # For type checker
        line = json.dumps(event, separators=(",", ":"), default=str)
        self._file.write(line + "\n")

        if self.fsync:
            self._file.flush()
            os.fsync(self._file.fileno())

    def load(self) -> list[dict[str, Any]]:
        """Load all events from file.

        Corrupted lines are skipped. Only returns the last max_events.

        Returns:
            List of event dictionaries.
        """
        if not self.file_path.exists():
            return []

        events: list[dict[str, Any]] = []
        with open(self.file_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue  # Skip corrupted lines

        # Return only last max_events
        return events[-self.max_events :]

    def _load_all(self) -> list[dict[str, Any]]:
        """Load ALL events from file (ignores max_events limit)."""
        if not self.file_path.exists():
            return []

        events: list[dict[str, Any]] = []
        with open(self.file_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return events

    def compact(self) -> int:
        """Compact file to only keep max_events.

        Returns:
            Number of events removed.
        """
        events = self._load_all()
        if len(events) <= self.max_events:
            return 0

        removed = len(events) - self.max_events
        kept = events[-self.max_events :]

        # Rewrite file
        self.close()
        with open(self.file_path, "w", encoding="utf-8") as f:
            for event in kept:
                line = json.dumps(event, separators=(",", ":"), default=str)
                f.write(line + "\n")

        self.open()
        return removed

    def clear(self) -> None:
        """Clear all events from the file."""
        self.close()
        if self.file_path.exists():
            self.file_path.unlink()
        self.open()

    def event_count(self) -> int:
        """Count events in the file."""
        if not self.file_path.exists():
            return 0
        with open(self.file_path, encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())

