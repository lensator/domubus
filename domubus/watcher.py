"""File watcher for cross-process event synchronization.

This module provides file watching capability to enable multiple processes
to share events via the same JSONL persistence file.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    pass


class FileWatcher:
    """Watches a JSONL file for new events appended by other processes.

    Uses file position tracking to efficiently detect new lines.
    Only reads events appended after the watcher starts.

    Example:
        watcher = FileWatcher(
            "events.jsonl",
            on_event=lambda e: print(f"New event: {e}"),
            process_id="chat-123",
        )
        await watcher.start()
        # ... events from other processes are now detected ...
        await watcher.stop()
    """

    def __init__(
        self,
        file_path: str | Path,
        *,
        on_event: Callable[[dict[str, Any]], None],
        process_id: str | None = None,
        poll_interval: float = 0.1,
    ) -> None:
        """Initialize the file watcher.

        Args:
            file_path: Path to the JSONL file to watch.
            on_event: Callback for each new event detected.
            process_id: Unique ID for this process (to filter own events).
            poll_interval: Seconds between file checks.
        """
        self.file_path = Path(file_path).expanduser()
        self._on_event = on_event
        self._process_id = process_id or f"proc-{os.getpid()}"
        self._poll_interval = poll_interval

        self._position: int = 0
        self._running = False
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start watching the file for new events."""
        if self._running:
            return

        # Start from end of file (only watch new events)
        if self.file_path.exists():
            self._position = self.file_path.stat().st_size

        self._running = True
        self._task = asyncio.create_task(self._watch_loop())

    async def stop(self) -> None:
        """Stop watching the file."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _watch_loop(self) -> None:
        """Main watch loop - polls file for new content."""
        while self._running:
            try:
                await self._check_file()
            except Exception:
                pass  # Ignore errors, keep watching

            await asyncio.sleep(self._poll_interval)

    async def _check_file(self) -> None:
        """Check file for new lines and process them."""
        if not self.file_path.exists():
            return

        current_size = self.file_path.stat().st_size
        if current_size <= self._position:
            return  # No new data

        # Read new lines
        with open(self.file_path, "r", encoding="utf-8") as f:
            f.seek(self._position)
            new_content = f.read()
            self._position = f.tell()

        # Process each new line
        for line in new_content.splitlines():
            line = line.strip()
            if not line:
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue  # Skip corrupted lines

            # Skip events from this process (avoid echo)
            if event.get("_source_process") == self._process_id:
                continue

            # Dispatch to handler
            self._on_event(event)

    @property
    def is_running(self) -> bool:
        """Check if the watcher is currently running."""
        return self._running

