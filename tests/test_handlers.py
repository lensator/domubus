"""Tests for domubus.handlers module."""

import asyncio

import pytest

from domubus.handlers import WILDCARD, HandlerEntry, HandlerRegistry


class TestHandlerEntry:
    """Tests for HandlerEntry dataclass."""

    def test_sync_handler_detection(self):
        """Detects sync handlers correctly."""

        def sync_fn(event):
            pass

        entry = HandlerEntry(
            id="test-1", event_type="test", callback=sync_fn
        )
        assert not entry.is_async

    def test_async_handler_detection(self):
        """Detects async handlers correctly."""

        async def async_fn(event):
            pass

        entry = HandlerEntry(
            id="test-2", event_type="test", callback=async_fn
        )
        assert entry.is_async

    def test_handler_name(self):
        """Gets handler function name."""

        def my_handler(event):
            pass

        entry = HandlerEntry(id="test-3", event_type="test", callback=my_handler)
        assert entry.name == "my_handler"


class TestHandlerRegistry:
    """Tests for HandlerRegistry."""

    def test_subscribe_returns_id(self):
        """subscribe() returns a unique handler ID."""
        registry = HandlerRegistry()

        def handler(e):
            pass

        id1 = registry.subscribe("test", handler)
        id2 = registry.subscribe("test", handler)
        assert id1 != id2

    def test_get_handlers(self):
        """get_handlers() returns subscribed handlers."""
        registry = HandlerRegistry()
        called = []

        def handler(e):
            called.append(e)

        registry.subscribe("test.event", handler)
        handlers = registry.get_handlers("test.event")
        assert len(handlers) == 1
        assert handlers[0].callback == handler

    def test_priority_ordering(self):
        """Handlers are returned in priority order (highest first)."""
        registry = HandlerRegistry()
        order = []

        def low(e):
            order.append("low")

        def high(e):
            order.append("high")

        def medium(e):
            order.append("medium")

        registry.subscribe("test", low, priority=0)
        registry.subscribe("test", high, priority=100)
        registry.subscribe("test", medium, priority=50)

        handlers = registry.get_handlers("test")
        assert [h.name for h in handlers] == ["high", "medium", "low"]

    def test_wildcard_subscription(self):
        """Wildcard handlers receive all events."""
        registry = HandlerRegistry()

        def wildcard_handler(e):
            pass

        registry.subscribe(WILDCARD, wildcard_handler)

        handlers1 = registry.get_handlers("device.light.on")
        handlers2 = registry.get_handlers("system.shutdown")

        assert len(handlers1) == 1
        assert len(handlers2) == 1
        assert handlers1[0].callback == wildcard_handler

    def test_unsubscribe(self):
        """unsubscribe() removes handler."""
        registry = HandlerRegistry()

        def handler(e):
            pass

        handler_id = registry.subscribe("test", handler)
        assert registry.handler_count("test") == 1

        result = registry.unsubscribe(handler_id)
        assert result is True
        assert registry.handler_count("test") == 0

    def test_unsubscribe_unknown_id(self):
        """unsubscribe() returns False for unknown ID."""
        registry = HandlerRegistry()
        result = registry.unsubscribe("nonexistent-id")
        assert result is False

    def test_clear(self):
        """clear() removes all handlers."""
        registry = HandlerRegistry()

        def handler(e):
            pass

        registry.subscribe("test", handler)
        registry.subscribe(WILDCARD, handler)
        registry.clear()

        assert registry.handler_count() == 0

    def test_handler_count(self):
        """handler_count() returns correct counts."""
        registry = HandlerRegistry()

        def handler(e):
            pass

        registry.subscribe("a", handler)
        registry.subscribe("a", handler)
        registry.subscribe("b", handler)
        registry.subscribe(WILDCARD, handler)

        assert registry.handler_count() == 4
        assert registry.handler_count("a") == 2
        assert registry.handler_count("b") == 1
        assert registry.handler_count(WILDCARD) == 1

