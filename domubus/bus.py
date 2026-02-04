"""Core EventBus implementation for domubus.

This module provides the main EventBus class that combines handlers, events,
and optional persistence into a unified async/sync event bus.
"""

from __future__ import annotations

import asyncio
import os
import threading
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Union

from domubus.events import BaseEvent, StringEvent
from domubus.handlers import HandlerEntry, HandlerRegistry
from domubus.persistence import JSONLPersistence
from domubus.watcher import FileWatcher

if TYPE_CHECKING:
    from domubus.types import ErrorCallback, EventFilter, Handler


class EventBus:
    """Async/sync event bus with optional persistence.

    Supports both sync and async handlers, priority ordering, wildcard
    subscriptions, one-time handlers, and optional JSONL persistence.

    Example:
        async with EventBus(persistence_path="events.jsonl") as bus:
            @bus.on("device.light.on")
            async def handle_light_on(event):
                print(f"Light turned on: {event}")

            await bus.emit_async("device.light.on", {"brightness": 100})
    """

    # Event type registry for deserialization
    _event_registry: dict[str, type[BaseEvent]] = {}

    @classmethod
    def register_event_type(cls, event_class: type[BaseEvent]) -> None:
        """Register an event class for deserialization.

        Args:
            event_class: A BaseEvent subclass with an event_type class variable.
        """
        event_type = getattr(event_class, "event_type", None)
        if event_type:
            cls._event_registry[event_type] = event_class

    @classmethod
    def register_event_types(cls, *event_classes: type[BaseEvent]) -> None:
        """Register multiple event classes for deserialization."""
        for event_class in event_classes:
            cls.register_event_type(event_class)

    def __init__(
        self,
        *,
        history_limit: int = 1000,
        persistence_path: str | Path | None = None,
        error_callback: ErrorCallback | None = None,
        process_id: str | None = None,
    ) -> None:
        """Initialize EventBus.

        Args:
            history_limit: Max events to keep in memory history.
            persistence_path: Optional path to JSONL file for persistence.
            error_callback: Optional callback for handler exceptions.
            process_id: Unique ID for this process (for cross-process sync).
        """
        self._registry = HandlerRegistry()
        self._history: deque[dict[str, Any]] = deque(maxlen=history_limit)
        self._error_callback = error_callback
        self._lock = threading.RLock()
        self._process_id = process_id or f"proc-{os.getpid()}"
        self._persistence_path = Path(persistence_path) if persistence_path else None

        # Optional persistence
        self._persistence: JSONLPersistence | None = None
        if persistence_path:
            self._persistence = JSONLPersistence(persistence_path)

        # File watcher for cross-process events
        self._watcher: FileWatcher | None = None

    # Context manager support (async)
    async def __aenter__(self) -> EventBus:
        """Async context manager entry - loads history from persistence."""
        if self._persistence:
            self._persistence.open()
            for event_dict in self._persistence.load():
                self._history.append(event_dict)
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit - closes persistence."""
        if self._persistence:
            self._persistence.close()

    # Context manager support (sync)
    def __enter__(self) -> EventBus:
        """Sync context manager entry - loads history from persistence."""
        if self._persistence:
            self._persistence.open()
            for event_dict in self._persistence.load():
                self._history.append(event_dict)
        return self

    def __exit__(self, *args: Any) -> None:
        """Sync context manager exit - closes persistence."""
        if self._persistence:
            self._persistence.close()

    # Subscription methods
    def subscribe(
        self,
        event_type: str,
        handler: Handler,
        *,
        priority: int = 0,
        once: bool = False,
        filter_fn: EventFilter | None = None,
    ) -> str:
        """Subscribe a handler to an event type.

        Args:
            event_type: Event type to subscribe to ("*" for all events).
            handler: Handler function (sync or async).
            priority: Execution priority (higher = earlier, default 0).
            once: If True, handler is removed after first call.
            filter_fn: Optional filter function to conditionally execute.

        Returns:
            Handler ID for later unsubscription.
        """
        with self._lock:
            return self._registry.subscribe(event_type, handler, priority, once, filter_fn)

    def unsubscribe(self, handler_id: str) -> bool:
        """Unsubscribe a handler by ID.

        Args:
            handler_id: The ID returned from subscribe().

        Returns:
            True if handler was found and removed.
        """
        with self._lock:
            return self._registry.unsubscribe(handler_id)

    def on(
        self,
        event_type: str,
        *,
        priority: int = 0,
        once: bool = False,
        filter_fn: EventFilter | None = None,
    ) -> Callable[[Handler], Handler]:
        """Decorator to subscribe a handler.

        Example:
            @bus.on("device.light.on")
            async def handle_light_on(event):
                print(event)
        """

        def decorator(handler: Handler) -> Handler:
            self.subscribe(event_type, handler, priority=priority, once=once, filter_fn=filter_fn)
            return handler

        return decorator

    def once(
        self,
        event_type: str,
        *,
        priority: int = 0,
        filter_fn: EventFilter | None = None,
    ) -> Callable[[Handler], Handler]:
        """Decorator to subscribe a one-time handler.

        The handler will be automatically unsubscribed after first execution.
        """
        return self.on(event_type, priority=priority, once=True, filter_fn=filter_fn)

    # Emit methods
    async def emit_async(
        self,
        event: Union[BaseEvent, StringEvent, str],
        data: dict[str, Any] | None = None,
    ) -> None:
        """Emit an event asynchronously.

        Args:
            event: Event object or string event type.
            data: Optional data dict (only used when event is a string).
        """
        # Normalize to event object
        if isinstance(event, str):
            event = StringEvent(event_type=event, data=data or {})

        event_type = event.event_type
        event_dict = event.to_dict()

        # Add source process ID for cross-process filtering
        event_dict["_source_process"] = self._process_id

        # Add to history and persist
        with self._lock:
            self._history.append(event_dict)
            if self._persistence:
                self._persistence.append(event_dict)

        # Get handlers and execute
        handlers = self._registry.get_handlers(event_type)
        handlers_to_remove: list[str] = []

        for handler in handlers:
            # Check filter
            if handler.filter_fn and not handler.filter_fn(event):
                continue

            try:
                if handler.is_async:
                    coro = handler.callback(event)
                    if coro is not None:
                        await coro
                else:
                    handler.callback(event)
            except Exception as e:
                if self._error_callback:
                    self._error_callback(e, event, handler.callback)

            if handler.once:
                handlers_to_remove.append(handler.id)

        # Remove once handlers
        for handler_id in handlers_to_remove:
            self._registry.unsubscribe(handler_id)

    def emit(
        self,
        event: Union[BaseEvent, StringEvent, str],
        data: dict[str, Any] | None = None,
    ) -> None:
        """Emit an event (sync wrapper for async emit).

        If called from an async context, schedules as a task.
        If called from sync context, runs in a new event loop.

        Args:
            event: Event object or string event type.
            data: Optional data dict (only used when event is a string).
        """
        try:
            loop = asyncio.get_running_loop()
            # Already in async context - schedule as task
            loop.create_task(self.emit_async(event, data))
        except RuntimeError:
            # No running loop - create one
            asyncio.run(self.emit_async(event, data))

    def emit_sync(
        self,
        event: Union[BaseEvent, StringEvent, str],
        data: dict[str, Any] | None = None,
    ) -> None:
        """Emit an event synchronously (only runs sync handlers).

        This method only executes sync handlers and skips async handlers.
        Use this when you need guaranteed synchronous execution.

        Args:
            event: Event object or string event type.
            data: Optional data dict (only used when event is a string).
        """
        # Normalize to event object
        if isinstance(event, str):
            event = StringEvent(event_type=event, data=data or {})

        event_type = event.event_type
        event_dict = event.to_dict()

        # Add source process ID for cross-process filtering
        event_dict["_source_process"] = self._process_id

        # Add to history and persist
        with self._lock:
            self._history.append(event_dict)
            if self._persistence:
                self._persistence.append(event_dict)

        # Get handlers and execute (sync only)
        handlers = self._registry.get_handlers(event_type)
        handlers_to_remove: list[str] = []

        for handler in handlers:
            # Skip async handlers
            if handler.is_async:
                continue

            # Check filter
            if handler.filter_fn and not handler.filter_fn(event):
                continue

            try:
                handler.callback(event)
            except Exception as e:
                if self._error_callback:
                    self._error_callback(e, event, handler.callback)

            if handler.once:
                handlers_to_remove.append(handler.id)

        # Remove once handlers
        for handler_id in handlers_to_remove:
            self._registry.unsubscribe(handler_id)

    # History access
    def get_history(
        self,
        event_type: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get event history, optionally filtered by type.

        Args:
            event_type: Filter by event type (None for all).
            limit: Max events to return (None for all).

        Returns:
            List of event dictionaries (newest last).
        """
        with self._lock:
            events = list(self._history)

        if event_type:
            events = [e for e in events if e.get("event_type") == event_type]

        if limit:
            events = events[-limit:]

        return events

    def clear_history(self) -> None:
        """Clear in-memory event history."""
        with self._lock:
            self._history.clear()

    def clear_handlers(self) -> None:
        """Remove all handlers."""
        with self._lock:
            self._registry.clear()

    def handler_count(self, event_type: str | None = None) -> int:
        """Count handlers, optionally filtered by event type."""
        return self._registry.handler_count(event_type)

    # Cross-process synchronization
    async def start_sync(self, poll_interval: float = 0.1) -> None:
        """Start watching for events from other processes.

        When enabled, events written to the persistence file by other processes
        are automatically dispatched to local handlers.

        Args:
            poll_interval: Seconds between file checks (default 0.1s).
        """
        if not self._persistence_path:
            raise RuntimeError("Cannot sync without persistence_path")

        if self._watcher and self._watcher.is_running:
            return  # Already running

        self._watcher = FileWatcher(
            self._persistence_path,
            on_event=self._handle_external_event,
            process_id=self._process_id,
            poll_interval=poll_interval,
        )
        await self._watcher.start()

    async def stop_sync(self) -> None:
        """Stop watching for events from other processes."""
        if self._watcher:
            await self._watcher.stop()
            self._watcher = None

    def _handle_external_event(self, event_dict: dict[str, Any]) -> None:
        """Handle an event from another process.

        Dispatches the event to local handlers without re-persisting.

        Args:
            event_dict: The event dictionary from the file.
        """
        event_type = event_dict.get("event_type", "")
        if not event_type:
            return

        # Try to deserialize to registered event type
        event_class = self._event_registry.get(event_type)
        if event_class:
            try:
                # Remove internal fields before deserializing
                clean_dict = {k: v for k, v in event_dict.items() if not k.startswith("_")}
                event = event_class(**clean_dict)
            except Exception:
                # Fall back to StringEvent if deserialization fails
                event = StringEvent(
                    event_type=event_type,
                    data=event_dict.get("data", event_dict),
                )
        else:
            # No registered class, use StringEvent
            event = StringEvent(
                event_type=event_type,
                data=event_dict.get("data", event_dict),
            )

        # Add to local history (but don't re-persist)
        with self._lock:
            self._history.append(event_dict)

        # Dispatch to handlers (sync only for now)
        handlers = self._registry.get_handlers(event_type)
        handlers_to_remove: list[str] = []

        for handler in handlers:
            if handler.filter_fn and not handler.filter_fn(event):
                continue

            try:
                if handler.is_async:
                    # Schedule async handlers
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(handler.callback(event))
                    except RuntimeError:
                        pass  # No loop, skip async handler
                else:
                    handler.callback(event)
            except Exception as e:
                if self._error_callback:
                    self._error_callback(e, event, handler.callback)

            if handler.once:
                handlers_to_remove.append(handler.id)

        for handler_id in handlers_to_remove:
            self._registry.unsubscribe(handler_id)

    @property
    def is_syncing(self) -> bool:
        """Check if cross-process sync is active."""
        return self._watcher is not None and self._watcher.is_running

