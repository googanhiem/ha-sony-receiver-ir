"""Tests for renaming the receiver inputs in the options flow."""

import pytest

from custom_components.sony_receiver_ir.codes import SonyReceiverCode
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_SELECT_SOURCE,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .common import MockConfigEntry
from .conftest import MockInfraredEmitterEntity

MEDIA_PLAYER = "media_player.sony_av_receiver"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return the platforms to set up."""
    return [Platform.BUTTON, Platform.MEDIA_PLAYER]


async def _rename(
    hass: HomeAssistant, entry: MockConfigEntry, user_input: dict[str, str]
) -> dict:
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=user_input
    )
    await hass.async_block_till_done()
    return result


async def test_rename_inputs(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test renamed inputs show up in the source list and on the buttons."""
    result = await _rename(
        hass,
        init_integration,
        {"name_bd_dvd": " Apple TV ", "name_game": "PS5", "name_video": ""},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    # Names are trimmed and empty fields are not stored.
    assert dict(init_integration.options) == {
        "name_bd_dvd": "Apple TV",
        "name_game": "PS5",
    }

    state = hass.states.get(MEDIA_PLAYER)
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == [
        "Apple TV",
        "PS5",
        "SAT/CATV",
        "VIDEO",
        "TV",
        "SA-CD/CD",
        "TUNER",
    ]
    # Button entity IDs stay the same; only their names change.
    assert (
        hass.states.get("button.sony_av_receiver_game").attributes[ATTR_FRIENDLY_NAME]
        == "Sony AV Receiver PS5"
    )
    assert (
        hass.states.get("button.sony_av_receiver_video").attributes[ATTR_FRIENDLY_NAME]
        == "Sony AV Receiver Video"
    )

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: MEDIA_PLAYER, ATTR_INPUT_SOURCE: "PS5"},
        blocking=True,
    )
    assert mock_infrared_emitter_entity.send_command_calls == [SonyReceiverCode.GAME]
    assert hass.states.get(MEDIA_PLAYER).attributes[ATTR_INPUT_SOURCE] == "PS5"


async def test_rename_back_to_defaults(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test clearing the names restores Sony's names."""
    await _rename(hass, init_integration, {"name_game": "PS5"})
    result = await _rename(hass, init_integration, {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert dict(init_integration.options) == {}
    assert hass.states.get(MEDIA_PLAYER).attributes[ATTR_INPUT_SOURCE_LIST][:4] == [
        "BD/DVD",
        "GAME",
        "SAT/CATV",
        "VIDEO",
    ]


@pytest.mark.parametrize(
    "user_input",
    [
        {"name_bd_dvd": "Console", "name_game": "console"},
        {"name_sat_catv": "tv"},
        {"name_video": "GAME"},
    ],
)
async def test_duplicate_names(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    user_input: dict[str, str],
) -> None:
    """Test two inputs cannot end up with the same name."""
    result = await _rename(hass, init_integration, user_input)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "duplicate_input_name"}
    assert dict(init_integration.options) == {}
