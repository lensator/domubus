"""Extended tests for domubus.bus module."""

import asyncio
from pathlib import Path

import pytest

from domubus import EventBus, StringEvent


class TestEventBusHistory:
    """Tests for EventBus history methods."""

    @pytest.mark.asyncio
    async def test_history_maintained(self):
        """Events are added to history."""
        bus = EventBus()
        await bus.emit_async("event.1")
        await bus.emit_async("event.2")

        history = bus.get_history()
        assert len(history) == 2
        assert history[0]["event_type"] == "event.1"
        assert history[1]["event_type"] == "event.2"

    @pytest.mark.asyncio
    async def test_history_limit(self):
        """History respects history_limit."""
        bus = EventBus(history_limit=3)

        for i in range(10):
            await bus.emit_async(f"event.{i}")

        history = bus.get_history()
        assert len(history) == 3
        assert history[0]["event_type"] == "event.7"
        assert history[2]["event_type"] == "event.9"

    @pytest.mark.asyncio
    async def test_history_filter_by_type(self):
        """get_history() can filter by event type."""
        bus = EventBus()
        await bus.emit_async("device.light.on")
        await bus.emit_async("device.thermostat.set")
        await bus.emit_async("device.light.off")

        light_events = bus.get_history(event_type="device.light.on")
        assert len(light_events) == 1

    @pytest.mark.asyncio
    async def test_history_with_limit(self):
        """get_history() respects limit parameter."""
        bus = EventBus()
        for i in range(10):
            await bus.emit_async(f"event.{i}")

        history = bus.get_history(limit=3)
        assert len(history) == 3
        assert history[-1]["event_type"] == "event.9"

    def test_clear_history(self):
        """clear_history() empties history."""
        bus = EventBus()
        bus.emit_sync("test.event")
        assert len(bus.get_history()) == 1

        bus.clear_history()
        assert len(bus.get_history()) == 0


class TestEventBusEmitSync:
    """Tests for emit_sync method."""

    def test_emit_sync_calls_sync_handlers(self):
        """emit_sync() calls sync handlers."""
        bus = EventBus()
        received = []

        @bus.on("test.sync")
        def handler(e):
            received.append(e)

        bus.emit_sync("test.sync", {"data": 1})

        assert len(received) == 1

    def test_emit_sync_skips_async_handlers(self):
        """emit_sync() skips async handlers."""
        bus = EventBus()
        sync_calls = []
        async_calls = []

        @bus.on("test.mixed")
        def sync_handler(e):
            sync_calls.append(1)

        @bus.on("test.mixed")
        async def async_handler(e):
            async_calls.append(1)

        bus.emit_sync("test.mixed")

        assert len(sync_calls) == 1
        assert len(async_calls) == 0


class TestEventBusContextManager:
    """Tests for context manager support."""

    @pytest.mark.asyncio
    async def test_async_context_manager(self, tmp_path: Path):
        """async with loads and saves persistence."""
        file_path = tmp_path / "events.jsonl"

        # First run - emit events
        async with EventBus(persistence_path=file_path) as bus:
            await bus.emit_async("event.1", {"data": "first"})
            await bus.emit_async("event.2", {"data": "second"})

        # Second run - verify history loaded
        async with EventBus(persistence_path=file_path) as bus:
            history = bus.get_history()
            assert len(history) == 2
            assert history[0]["event_type"] == "event.1"

    def test_sync_context_manager(self, tmp_path: Path):
        """sync with loads and saves persistence."""
        file_path = tmp_path / "events.jsonl"

        # First run
        with EventBus(persistence_path=file_path) as bus:
            bus.emit_sync("sync.event.1")
            bus.emit_sync("sync.event.2")

        # Second run
        with EventBus(persistence_path=file_path) as bus:
            history = bus.get_history()
            assert len(history) == 2


class TestEventBusWildcard:
    """Tests for wildcard event subscriptions."""

    @pytest.mark.asyncio
    async def test_wildcard_receives_all(self):
        """Wildcard handler receives all events."""
        bus = EventBus()
        received = []

        @bus.on("*")
        def wildcard_handler(e):
            received.append(e.event_type)

        await bus.emit_async("device.light.on")
        await bus.emit_async("system.shutdown")
        await bus.emit_async("user.login")

        assert len(received) == 3
        assert "device.light.on" in received
        assert "system.shutdown" in received
        assert "user.login" in received

    @pytest.mark.asyncio
    async def test_wildcard_with_specific(self):
        """Wildcard and specific handlers both called."""
        bus = EventBus()
        calls = []

        @bus.on("*")
        def wildcard(e):
            calls.append("wildcard")

        @bus.on("device.light.on")
        def specific(e):
            calls.append("specific")

        await bus.emit_async("device.light.on")

        assert "wildcard" in calls
        assert "specific" in calls

