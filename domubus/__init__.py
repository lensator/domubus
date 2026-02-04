"""domubus - Async/sync event bus with optional Pydantic integration.

A type-safe, async/sync event bus with optional Pydantic integration,
persistence, and priority handlers. Zero required dependencies.

Example:
    from domubus import EventBus, BaseEvent

    class DeviceStateChanged(BaseEvent):
        event_type = "device.state.changed"
        device_id: str
        new_state: str

    bus = EventBus()

    @bus.on("device.state.changed")
    async def handle_state_change(event: DeviceStateChanged):
        print(f"Device {event.device_id} -> {event.new_state}")

    await bus.emit_async(DeviceStateChanged(device_id="light1", new_state="on"))
"""

from domubus.bus import EventBus
from domubus.events import PYDANTIC_AVAILABLE, BaseEvent, StringEvent
from domubus.handlers import HandlerEntry, HandlerRegistry
from domubus.persistence import JSONLPersistence
from domubus.types import (
    AsyncHandler,
    BaseEventProtocol,
    ErrorCallback,
    EventFilter,
    EventT,
    EventT_co,
    Handler,
    SyncHandler,
)
from domubus.watcher import FileWatcher

__version__ = "0.1.0"

__all__ = [
    # Core
    "EventBus",
    # Events
    "BaseEvent",
    "StringEvent",
    "PYDANTIC_AVAILABLE",
    # Handlers
    "HandlerEntry",
    "HandlerRegistry",
    # Persistence
    "JSONLPersistence",
    # Watcher
    "FileWatcher",
    # Types
    "Handler",
    "SyncHandler",
    "AsyncHandler",
    "ErrorCallback",
    "EventFilter",
    "BaseEventProtocol",
    "EventT",
    "EventT_co",
    # Metadata
    "__version__",
]

