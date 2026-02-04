"""Handler management for domubus.

This module provides HandlerEntry (individual handler) and HandlerRegistry
(collection of handlers with priority ordering and wildcard support).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from domubus.types import EventFilter, Handler

WILDCARD = "*"


@dataclass
class HandlerEntry:
    """Represents a registered event handler.

    Attributes:
        id: Unique identifier for this handler registration.
        event_type: The event type this handler listens to ("*" for wildcard).
        callback: The handler function (sync or async).
        priority: Execution priority (higher = earlier execution).
        once: If True, handler is removed after first execution.
        filter_fn: Optional filter function to conditionally execute.
    """

    id: str
    event_type: str
    callback: Handler
    priority: int = 0
    once: bool = False
    filter_fn: EventFilter | None = None

    @property
    def is_async(self) -> bool:
        """Check if the handler is an async function."""
        return asyncio.iscoroutinefunction(self.callback)

    @property
    def name(self) -> str:
        """Get the handler function name."""
        return getattr(self.callback, "__name__", repr(self.callback))


class HandlerRegistry:
    """Manages event handlers with priority ordering and wildcard support.

    Handlers are stored per event type and sorted by priority (highest first).
    Wildcard handlers ("*") receive all events.

    Example:
        registry = HandlerRegistry()
        handler_id = registry.subscribe("device.light.on", my_handler, priority=10)
        handlers = registry.get_handlers("device.light.on")
        registry.unsubscribe(handler_id)
    """

    def __init__(self) -> None:
        """Initialize an empty handler registry."""
        self._handlers: dict[str, list[HandlerEntry]] = {}
        self._wildcard_handlers: list[HandlerEntry] = []

    def subscribe(
        self,
        event_type: str,
        callback: Handler,
        priority: int = 0,
        once: bool = False,
        filter_fn: EventFilter | None = None,
    ) -> str:
        """Register a handler for an event type.

        Args:
            event_type: Event type to subscribe to ("*" for all events).
            callback: Handler function (sync or async).
            priority: Execution priority (higher = earlier, default 0).
            once: If True, handler is removed after first call.
            filter_fn: Optional filter function to conditionally execute.

        Returns:
            Unique handler ID for later unsubscription.
        """
        handler_id = str(uuid4())
        entry = HandlerEntry(
            id=handler_id,
            event_type=event_type,
            callback=callback,
            priority=priority,
            once=once,
            filter_fn=filter_fn,
        )

        if event_type == WILDCARD:
            self._wildcard_handlers.append(entry)
            self._wildcard_handlers.sort(key=lambda h: -h.priority)
        else:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(entry)
            self._handlers[event_type].sort(key=lambda h: -h.priority)

        return handler_id

    def unsubscribe(self, handler_id: str) -> bool:
        """Remove a handler by its ID.

        Args:
            handler_id: The ID returned from subscribe().

        Returns:
            True if handler was found and removed, False otherwise.
        """
        # Check specific handlers
        for handlers in self._handlers.values():
            for i, h in enumerate(handlers):
                if h.id == handler_id:
                    handlers.pop(i)
                    return True

        # Check wildcard handlers
        for i, h in enumerate(self._wildcard_handlers):
            if h.id == handler_id:
                self._wildcard_handlers.pop(i)
                return True

        return False

    def get_handlers(self, event_type: str) -> list[HandlerEntry]:
        """Get all handlers for an event type (including wildcards).

        Args:
            event_type: The event type to get handlers for.

        Returns:
            List of handlers sorted by priority (highest first).
        """
        specific = self._handlers.get(event_type, [])
        # Merge specific and wildcard, re-sort by priority
        all_handlers = list(specific) + list(self._wildcard_handlers)
        return sorted(all_handlers, key=lambda h: -h.priority)

    def clear(self) -> None:
        """Remove all handlers."""
        self._handlers.clear()
        self._wildcard_handlers.clear()

    def handler_count(self, event_type: str | None = None) -> int:
        """Count handlers, optionally filtered by event type."""
        if event_type is None:
            total = sum(len(h) for h in self._handlers.values())
            return total + len(self._wildcard_handlers)
        if event_type == WILDCARD:
            return len(self._wildcard_handlers)
        return len(self._handlers.get(event_type, []))

