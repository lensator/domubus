"""Tests for domubus.events module."""

import time
from dataclasses import dataclass

import pytest

from domubus.events import PYDANTIC_AVAILABLE, BaseEvent, StringEvent


class TestStringEvent:
    """Tests for StringEvent dataclass."""

    def test_create_basic(self):
        """StringEvent can be created with just event_type."""
        event = StringEvent(event_type="test.event")
        assert event.event_type == "test.event"
        assert event.data == {}
        assert event.id  # UUID generated
        assert event.timestamp > 0

    def test_create_with_data(self):
        """StringEvent can be created with data dict."""
        data = {"key": "value", "count": 42}
        event = StringEvent(event_type="test.data", data=data)
        assert event.event_type == "test.data"
        assert event.data == data

    def test_to_dict(self):
        """StringEvent can serialize to dict."""
        event = StringEvent(event_type="test.serialize", data={"foo": "bar"})
        d = event.to_dict()
        assert d["event_type"] == "test.serialize"
        assert d["data"] == {"foo": "bar"}
        assert "id" in d
        assert "timestamp" in d

    def test_from_dict(self):
        """StringEvent can deserialize from dict."""
        original = StringEvent(event_type="test.deserialize", data={"x": 1})
        d = original.to_dict()
        restored = StringEvent.from_dict(d)
        assert restored.event_type == original.event_type
        assert restored.data == original.data
        assert restored.id == original.id

    def test_unique_ids(self):
        """Each StringEvent gets a unique ID."""
        e1 = StringEvent(event_type="test")
        e2 = StringEvent(event_type="test")
        assert e1.id != e2.id


class TestBaseEvent:
    """Tests for BaseEvent (Pydantic or dataclass fallback)."""

    def test_create_basic(self):
        """BaseEvent can be created."""
        event = BaseEvent()
        assert event.event_type == "base"
        assert event.id
        assert event.timestamp > 0

    def test_to_dict(self):
        """BaseEvent can serialize to dict."""
        event = BaseEvent()
        d = event.to_dict()
        assert d["event_type"] == "base"
        assert "id" in d
        assert "timestamp" in d

    def test_from_dict(self):
        """BaseEvent can deserialize from dict."""
        original = BaseEvent()
        d = original.to_dict()
        restored = BaseEvent.from_dict(d)
        assert restored.id == original.id


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not installed")
class TestPydanticBaseEvent:
    """Tests for BaseEvent when Pydantic is available."""

    def test_subclass_with_fields(self):
        """Can create BaseEvent subclass with typed fields."""
        from typing import ClassVar

        from pydantic import Field

        class DeviceEvent(BaseEvent):
            event_type: ClassVar[str] = "device.test"
            device_id: str = Field(default="unknown")
            state: str = Field(default="off")

        event = DeviceEvent(device_id="light1", state="on")
        assert event.event_type == "device.test"
        assert event.device_id == "light1"
        assert event.state == "on"

        d = event.to_dict()
        assert d["event_type"] == "device.test"
        assert d["device_id"] == "light1"
        assert d["state"] == "on"

    def test_extra_fields_allowed(self):
        """BaseEvent allows extra fields."""
        from typing import ClassVar

        class FlexEvent(BaseEvent):
            event_type: ClassVar[str] = "flex"

        # Pydantic v2 with extra="allow" should accept extra fields
        event = FlexEvent.model_validate({"custom_field": "value"})
        assert event.model_extra.get("custom_field") == "value"


class TestPydanticAvailability:
    """Tests for PYDANTIC_AVAILABLE flag."""

    def test_flag_is_bool(self):
        """PYDANTIC_AVAILABLE is a boolean."""
        assert isinstance(PYDANTIC_AVAILABLE, bool)

