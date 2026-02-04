"""Integration tests for domubus package."""

import asyncio
from pathlib import Path
from typing import ClassVar

import pytest

from domubus import EventBus, BaseEvent, StringEvent, PYDANTIC_AVAILABLE


class TestBasicIntegration:
    """Basic integration scenarios."""

    @pytest.mark.asyncio
    async def test_device_control_scenario(self):
        """Simulate device control event flow."""
        bus = EventBus()
        state_changes = []
        confirmations = []

        @bus.on("device.command.send")
        async def process_command(event):
            # Simulate processing command
            device_id = event.data.get("device_id")
            action = event.data.get("action")
            # Emit state change
            await bus.emit_async("device.state.changed", {
                "device_id": device_id,
                "old_state": "off",
                "new_state": action,
            })

        @bus.on("device.state.changed")
        async def log_state_change(event):
            state_changes.append(event.data)

        @bus.on("device.state.changed", priority=100)
        async def send_confirmation(event):
            confirmations.append(f"Confirmed: {event.data['device_id']}")

        # Trigger the flow
        await bus.emit_async("device.command.send", {
            "device_id": "light_living_room",
            "action": "on",
        })

        assert len(state_changes) == 1
        assert state_changes[0]["device_id"] == "light_living_room"
        assert state_changes[0]["new_state"] == "on"
        assert len(confirmations) == 1

    @pytest.mark.asyncio
    async def test_error_isolation(self):
        """Handlers with errors don't affect other handlers."""
        bus = EventBus()
        results = []

        @bus.on("test.event", priority=100)
        def first_handler(e):
            results.append("first")

        @bus.on("test.event", priority=50)
        def bad_handler(e):
            raise RuntimeError("This handler fails")

        @bus.on("test.event", priority=0)
        def last_handler(e):
            results.append("last")

        await bus.emit_async("test.event")

        # Both non-failing handlers should run
        assert "first" in results
        assert "last" in results


class TestPersistenceIntegration:
    """Integration tests with persistence."""

    @pytest.mark.asyncio
    async def test_event_replay(self, tmp_path: Path):
        """Events can be replayed from persistence."""
        file_path = tmp_path / "replay.jsonl"
        replayed_events = []

        # Session 1: Emit events
        async with EventBus(persistence_path=file_path) as bus:
            await bus.emit_async("user.action", {"action": "click", "target": "btn1"})
            await bus.emit_async("user.action", {"action": "type", "target": "input1"})
            await bus.emit_async("user.action", {"action": "submit", "target": "form1"})

        # Session 2: Replay from history
        async with EventBus(persistence_path=file_path) as bus:
            history = bus.get_history(event_type="user.action")

            for event_dict in history:
                replayed_events.append(event_dict["data"])

        assert len(replayed_events) == 3
        assert replayed_events[0]["action"] == "click"
        assert replayed_events[2]["action"] == "submit"


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not installed")
class TestPydanticIntegration:
    """Integration tests with Pydantic events."""

    @pytest.mark.asyncio
    async def test_typed_event_flow(self):
        """Typed Pydantic events work end-to-end."""
        from pydantic import Field

        class DeviceCommand(BaseEvent):
            event_type: ClassVar[str] = "device.command"
            device_id: str
            action: str

        class DeviceState(BaseEvent):
            event_type: ClassVar[str] = "device.state"
            device_id: str
            state: str

        bus = EventBus()
        states = []

        @bus.on("device.command")
        async def process_command(event: DeviceCommand):
            state_event = DeviceState(
                device_id=event.device_id,
                state=event.action
            )
            await bus.emit_async(state_event)

        @bus.on("device.state")
        async def log_state(event: DeviceState):
            states.append(event)

        await bus.emit_async(DeviceCommand(device_id="light1", action="on"))

        assert len(states) == 1
        assert states[0].device_id == "light1"
        assert states[0].state == "on"


class TestConcurrency:
    """Concurrency tests."""

    @pytest.mark.asyncio
    async def test_concurrent_emit(self):
        """Multiple concurrent emits work correctly."""
        bus = EventBus()
        received = []
        lock = asyncio.Lock()

        @bus.on("concurrent.event")
        async def handler(event):
            async with lock:
                received.append(event.data.get("id"))

        # Emit 100 events concurrently
        tasks = [
            bus.emit_async("concurrent.event", {"id": i})
            for i in range(100)
        ]
        await asyncio.gather(*tasks)

        assert len(received) == 100
        assert set(received) == set(range(100))

