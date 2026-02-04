"""Tests for domubus.bus module."""

import asyncio
from pathlib import Path

import pytest

from domubus import EventBus, StringEvent


class TestEventBusSubscription:
    """Tests for EventBus subscription methods."""

    def test_subscribe_returns_id(self):
        """subscribe() returns handler ID."""
        bus = EventBus()

        def handler(e):
            pass

        handler_id = bus.subscribe("test", handler)
        assert handler_id
        assert isinstance(handler_id, str)

    def test_unsubscribe(self):
        """unsubscribe() removes handler."""
        bus = EventBus()

        def handler(e):
            pass

        handler_id = bus.subscribe("test", handler)
        assert bus.handler_count("test") == 1

        result = bus.unsubscribe(handler_id)
        assert result is True
        assert bus.handler_count("test") == 0

    def test_on_decorator(self):
        """@bus.on() decorator registers handler."""
        bus = EventBus()

        @bus.on("test.event")
        def handler(e):
            pass

        assert bus.handler_count("test.event") == 1

    def test_once_decorator(self):
        """@bus.once() decorator registers one-time handler."""
        bus = EventBus()
        calls = []

        @bus.once("test.once")
        def handler(e):
            calls.append(1)

        assert bus.handler_count("test.once") == 1


class TestEventBusEmit:
    """Tests for EventBus emit methods."""

    @pytest.mark.asyncio
    async def test_emit_async_with_string(self):
        """emit_async() works with string event type."""
        bus = EventBus()
        received = []

        @bus.on("test.string")
        async def handler(event):
            received.append(event)

        await bus.emit_async("test.string", {"key": "value"})

        assert len(received) == 1
        assert received[0].event_type == "test.string"
        assert received[0].data == {"key": "value"}

    @pytest.mark.asyncio
    async def test_emit_async_with_event_object(self):
        """emit_async() works with StringEvent object."""
        bus = EventBus()
        received = []

        @bus.on("test.object")
        async def handler(event):
            received.append(event)

        event = StringEvent(event_type="test.object", data={"foo": "bar"})
        await bus.emit_async(event)

        assert len(received) == 1
        assert received[0] is event

    @pytest.mark.asyncio
    async def test_emit_async_sync_handler(self):
        """emit_async() calls sync handlers correctly."""
        bus = EventBus()
        received = []

        @bus.on("test.sync")
        def handler(event):  # sync handler
            received.append(event)

        await bus.emit_async("test.sync")

        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_priority_ordering(self):
        """Handlers are called in priority order."""
        bus = EventBus()
        order = []

        @bus.on("test.priority", priority=0)
        def low(e):
            order.append("low")

        @bus.on("test.priority", priority=100)
        def high(e):
            order.append("high")

        @bus.on("test.priority", priority=50)
        def medium(e):
            order.append("medium")

        await bus.emit_async("test.priority")

        assert order == ["high", "medium", "low"]

    @pytest.mark.asyncio
    async def test_once_handler_removed(self):
        """Once handlers are removed after first execution."""
        bus = EventBus()
        calls = []

        @bus.once("test.once")
        def handler(e):
            calls.append(1)

        await bus.emit_async("test.once")
        await bus.emit_async("test.once")

        assert len(calls) == 1
        assert bus.handler_count("test.once") == 0

    @pytest.mark.asyncio
    async def test_filter_fn(self):
        """Filter function prevents handler execution."""
        bus = EventBus()
        received = []

        def only_important(event):
            return event.data.get("important", False)

        @bus.on("test.filter", filter_fn=only_important)
        def handler(e):
            received.append(e)

        await bus.emit_async("test.filter", {"important": False})
        await bus.emit_async("test.filter", {"important": True})

        assert len(received) == 1
        assert received[0].data["important"] is True

    @pytest.mark.asyncio
    async def test_error_callback(self):
        """Error callback is called on handler exception."""
        errors = []

        def on_error(exc, event, handler):
            errors.append((exc, event, handler))

        bus = EventBus(error_callback=on_error)

        @bus.on("test.error")
        def bad_handler(e):
            raise ValueError("Test error")

        await bus.emit_async("test.error")

        assert len(errors) == 1
        assert isinstance(errors[0][0], ValueError)

