"""Event definitions for domubus.

This module provides BaseEvent (Pydantic or dataclass fallback) and StringEvent
for simple string-based events.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, ClassVar
from uuid import uuid4

# Try Pydantic v2, fall back to dataclass
try:
    from pydantic import BaseModel, ConfigDict, Field

    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    BaseModel = None  # type: ignore[misc, assignment]


def _generate_id() -> str:
    """Generate a unique event ID using UUID4."""
    return str(uuid4())


def _generate_timestamp() -> float:
    """Generate a Unix timestamp for the current time."""
    return time.time()


if PYDANTIC_AVAILABLE and BaseModel is not None:

    class BaseEvent(BaseModel):  # type: ignore[no-redef, unused-ignore]
        """Base event class using Pydantic v2.

        Subclass this to create custom events with type-safe payloads.

        Example:
            class DeviceStateChanged(BaseEvent):
                event_type: ClassVar[str] = "device.state.changed"
                device_id: str
                new_state: dict[str, Any]
        """

        model_config = ConfigDict(extra="allow")

        event_type: ClassVar[str] = "base"
        id: str = Field(default_factory=_generate_id)
        timestamp: float = Field(default_factory=_generate_timestamp)

        def to_dict(self) -> dict[str, Any]:
            """Serialize the event to a dictionary."""
            return {"event_type": self.__class__.event_type, **self.model_dump()}

        @classmethod
        def from_dict(cls, data: dict[str, Any]) -> BaseEvent:
            """Deserialize an event from a dictionary."""
            data = data.copy()
            data.pop("event_type", None)
            return cls.model_validate(data)

else:

    @dataclass
    class BaseEvent:  # type: ignore[no-redef]
        """Base event class using dataclass (Pydantic fallback).

        Subclass this to create custom events when Pydantic is not available.

        Example:
            @dataclass
            class DeviceStateChanged(BaseEvent):
                event_type: ClassVar[str] = "device.state.changed"
                device_id: str = ""
                new_state: dict = field(default_factory=dict)
        """

        event_type: ClassVar[str] = "base"
        id: str = field(default_factory=_generate_id)
        timestamp: float = field(default_factory=_generate_timestamp)

        def to_dict(self) -> dict[str, Any]:
            """Serialize the event to a dictionary."""
            return {"event_type": self.__class__.event_type, **asdict(self)}

        @classmethod
        def from_dict(cls, data: dict[str, Any]) -> BaseEvent:
            """Deserialize an event from a dictionary."""
            data = data.copy()
            data.pop("event_type", None)
            return cls(**data)


@dataclass
class StringEvent:
    """Simple string-based event for basic use cases.

    Use this when you don't need a custom event class and just want
    to emit events by name with arbitrary data.

    Example:
        event = StringEvent(event_type="device.light.on", data={"brightness": 100})
    """

    event_type: str
    data: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=_generate_id)
    timestamp: float = field(default_factory=_generate_timestamp)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the event to a dictionary."""
        return {
            "event_type": self.event_type,
            "data": self.data,
            "id": self.id,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StringEvent:
        """Deserialize a StringEvent from a dictionary."""
        return cls(
            event_type=data["event_type"],
            data=data.get("data", {}),
            id=data.get("id", _generate_id()),
            timestamp=data.get("timestamp", _generate_timestamp()),
        )

