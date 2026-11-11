"""Common fixtures for the Sony Receiver IR tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import patch

from infrared_protocols.commands import Command as InfraredCommand
import pytest

from custom_components.sony_receiver_ir.const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    CONF_MODEL,
    DOMAIN,
)
from homeassistant.components.infrared import (
    DATA_COMPONENT,
    InfraredEmitterEntity,
    InfraredReceiverEntity,
)
from homeassistant.components.infrared.const import DOMAIN as INFRARED_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import MockConfigEntry

EMITTER_ENTITY_ID = "infrared.test_ir_emitter"
RECEIVER_ENTITY_ID = "infrared.test_ir_receiver"
ENTRY_ID = "01JTEST0000000000000000000"


class MockInfraredEmitterEntity(InfraredEmitterEntity):
    """Mock infrared emitter entity."""

    _attr_has_entity_name = True

    def __init__(self, unique_id: str, name: str = "Test IR emitter") -> None:
        """Initialize the mock emitter."""
        self._attr_unique_id = unique_id
        self._attr_name = name
        self.send_command_calls: list[InfraredCommand] = []

    async def async_send_command(self, command: InfraredCommand) -> None:
        """Record sent commands."""
        self.send_command_calls.append(command)


class MockInfraredReceiverEntity(InfraredReceiverEntity):
    """Mock infrared receiver entity."""

    _attr_has_entity_name = True

    def __init__(self, unique_id: str, name: str = "Test IR receiver") -> None:
        """Initialize the mock receiver."""
        self._attr_unique_id = unique_id
        self._attr_name = name


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading custom integrations in all tests."""


@pytest.fixture
async def init_infrared(hass: HomeAssistant) -> None:
    """Set up the infrared integration."""
    assert await async_setup_component(hass, INFRARED_DOMAIN, {})
    await hass.async_block_till_done()


@pytest.fixture
async def mock_infrared_emitter_entity(
    hass: HomeAssistant, init_infrared: None
) -> MockInfraredEmitterEntity:
    """Add a mock infrared emitter entity."""
    entity = MockInfraredEmitterEntity("test_ir_emitter")
    await hass.data[DATA_COMPONENT].async_add_entities([entity])
    return entity


@pytest.fixture
async def mock_infrared_receiver_entity(
    hass: HomeAssistant, init_infrared: None
) -> MockInfraredReceiverEntity:
    """Add a mock infrared receiver entity."""
    entity = MockInfraredReceiverEntity("test_ir_receiver")
    await hass.data[DATA_COMPONENT].async_add_entities([entity])
    return entity


@pytest.fixture
def has_receiver() -> bool:
    """Return whether the config entry has a receiver configured."""
    return True


@pytest.fixture
def mock_config_entry(has_receiver: bool) -> MockConfigEntry:
    """Return a mock config entry."""
    data: dict[str, Any] = {
        CONF_MODEL: "STR-DH820",
        CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
    }
    if has_receiver:
        data[CONF_INFRARED_RECEIVER_ENTITY_ID] = RECEIVER_ENTITY_ID
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id=ENTRY_ID,
        title="Sony STR-DH820 via Test IR emitter",
        data=data,
    )


@pytest.fixture
def platforms() -> list[Platform]:
    """Return the platforms to set up."""
    return [Platform.BUTTON, Platform.EVENT, Platform.MEDIA_PLAYER]


@pytest.fixture
def mock_code_to_command() -> Generator[None]:
    """Make SonyReceiverCode.to_command return the code itself.

    Lets tests assert on the code instead of raw timings.
    """
    with patch(
        "custom_components.sony_receiver_ir.codes.SonyReceiverCode.to_command",
        autospec=True,
        side_effect=lambda self: self,
    ):
        yield


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    mock_code_to_command: None,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the Sony Receiver IR integration."""
    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.sony_receiver_ir.PLATFORMS", platforms):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    return mock_config_entry
