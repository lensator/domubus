# domubus

A type-safe, async/sync event bus for Python with optional Pydantic integration, persistence, and priority handlers. **Zero required dependencies.**

## Features

- ✅ **Async & Sync** - Both async and sync handlers, emit from either context
- ✅ **Zero Dependencies** - Core package uses only Python stdlib
- ✅ **Optional Pydantic** - Type-safe events when Pydantic is installed
- ✅ **Priority Handlers** - Control execution order with priority values
- ✅ **Wildcard Subscriptions** - Subscribe to all events with `*`
- ✅ **One-time Handlers** - Auto-unsubscribe after first execution
- ✅ **Event Filters** - Conditionally execute handlers
- ✅ **JSONL Persistence** - WAL-style event persistence
- ✅ **Fully Typed** - PEP 561 compatible with `py.typed` marker

## Installation

```bash
pip install domubus

# With Pydantic support
pip install domubus[pydantic]
```

## Quick Start

```python
import asyncio
from domubus import EventBus

bus = EventBus()

@bus.on("device.light.on")
async def handle_light_on(event):
    print(f"Light turned on: {event.data}")

@bus.on("device.light.on", priority=100)
def high_priority_handler(event):
    print("This runs first (sync handler)")

async def main():
    await bus.emit_async("device.light.on", {"brightness": 100})

asyncio.run(main())
```

## Typed Events with Pydantic

```python
from typing import ClassVar
from domubus import EventBus, BaseEvent

class DeviceStateChanged(BaseEvent):
    event_type: ClassVar[str] = "device.state.changed"
    device_id: str
    new_state: str

bus = EventBus()

@bus.on("device.state.changed")
async def handle_state_change(event: DeviceStateChanged):
    print(f"Device {event.device_id} -> {event.new_state}")

await bus.emit_async(DeviceStateChanged(device_id="light1", new_state="on"))
```

## Persistence

```python
from domubus import EventBus

# Events are persisted to JSONL file
async with EventBus(persistence_path="~/.myapp/events.jsonl") as bus:
    await bus.emit_async("user.login", {"user_id": "123"})
    
    # History is automatically loaded on context enter
    history = bus.get_history(event_type="user.login")
```

## Wildcard Subscriptions

```python
@bus.on("*")
def log_all_events(event):
    print(f"Event: {event.event_type}")
```

## One-time Handlers

```python
@bus.once("system.ready")
async def on_ready(event):
    print("System ready! (only runs once)")
```

## Event Filters

```python
def only_important(event):
    return event.data.get("priority") == "high"

@bus.on("notification", filter_fn=only_important)
def handle_important(event):
    print(f"Important: {event.data}")
```

## Error Handling

```python
def on_error(exception, event, handler):
    print(f"Handler {handler.__name__} failed: {exception}")

bus = EventBus(error_callback=on_error)
```

## API Reference

### EventBus

- `subscribe(event_type, handler, priority=0, once=False, filter_fn=None)` - Subscribe handler
- `unsubscribe(handler_id)` - Unsubscribe by ID
- `on(event_type, ...)` - Decorator for subscribing
- `once(event_type, ...)` - Decorator for one-time handler
- `emit_async(event, data=None)` - Emit event asynchronously
- `emit(event, data=None)` - Emit (async from sync context)
- `emit_sync(event, data=None)` - Emit synchronously (sync handlers only)
- `get_history(event_type=None, limit=None)` - Get event history
- `clear_history()` - Clear in-memory history
- `clear_handlers()` - Remove all handlers

### Events

- `BaseEvent` - Pydantic-based event (or dataclass fallback)
- `StringEvent` - Simple string-based event with data dict

## License

MIT

