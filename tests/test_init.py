"""Tests for the Sony Receiver IR setup and diagnostics."""

from custom_components.sony_receiver_ir.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .common import MockConfigEntry
from .conftest import (
    EMITTER_ENTITY_ID,
    RECEIVER_ENTITY_ID,
)


async def test_setup_and_unload(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test setting up and unloading a config entry."""
    assert init_integration.state is ConfigEntryState.LOADED
    assert hass.states.get("media_player.sony_av_receiver") is not None
    assert hass.states.get("event.sony_av_receiver_received_command") is not None

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()
    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_diagnostics(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test diagnostics return the entry data."""
    assert await async_get_config_entry_diagnostics(hass, init_integration) == {
        "model": "STR-DH820",
        "infrared_entity_id": EMITTER_ENTITY_ID,
        "infrared_receiver_entity_id": RECEIVER_ENTITY_ID,
    }
