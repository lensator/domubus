"""Type definitions for domubus event bus."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol, TypeVar, Union, runtime_checkable

# TypeVar for event types
EventT = TypeVar("EventT", bound="BaseEventProtocol")
EventT_co = TypeVar("EventT_co", bound="BaseEventProtocol", covariant=True)


@runtime_checkable
class BaseEventProtocol(Protocol):
    """Protocol that all events must satisfy.

    All events (Pydantic BaseEvent, StringEvent, or custom) must have these attributes.
    """

    @property
    def event_type(self) -> str:
        """The event type identifier (e.g., 'device.light.on')."""
        ...

    @property
    def timestamp(self) -> float:
        """Unix timestamp when the event was created."""
        ...

    @property
    def id(self) -> str:
        """Unique identifier for this event instance."""
        ...

    def to_dict(self) -> dict[str, Any]:
        """Serialize the event to a dictionary."""
        ...


# Handler callback types
SyncHandler = Callable[[Any], None]
"""Synchronous handler that receives an event and returns nothing."""

AsyncHandler = Callable[[Any], Awaitable[None]]
"""Asynchronous handler that receives an event and returns nothing."""

Handler = Union[SyncHandler, AsyncHandler]
"""Union type for both sync and async handlers."""

# Error callback type
ErrorCallback = Callable[[Exception, Any, Handler], None]
"""Callback invoked when a handler raises an exception.

Args:
    exception: The exception that was raised.
    event: The event that was being processed.
    handler: The handler that raised the exception.
"""

# Filter function type
EventFilter = Callable[[Any], bool]
"""Filter function to conditionally execute handlers.

Args:
    event: The event to check.

Returns:
    True if the handler should be executed, False otherwise.
"""

