"""Tests for the Sony Receiver IR media player."""

from typing import Any

import pytest

from custom_components.sony_receiver_ir.codes import (
    SonyReceiverCode,
    SonyRepeatedCommand,
)
from custom_components.sony_receiver_ir.const import DOMAIN
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_SELECT_SOURCE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_UP,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import MockConfigEntry, mock_restore_cache
from .conftest import EMITTER_ENTITY_ID, MockInfraredEmitterEntity

ENTITY_ID = "media_player.sony_av_receiver"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return the platforms to set up."""
    return [Platform.MEDIA_PLAYER]


@pytest.mark.usefixtures("init_integration")
async def test_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the media player and its device."""
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes["device_class"] == "receiver"
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == [
        "BD/DVD",
        "GAME",
        "SAT/CATV",
        "VIDEO",
        "TV",
        "SA-CD/CD",
        "TUNER",
    ]
    device = device_registry.async_get(entity_registry.async_get(ENTITY_ID).device_id)
    assert (device.manufacturer, device.model) == ("Sony", "STR-DH820")


@pytest.mark.parametrize(
    ("service", "service_data", "expected_code"),
    [
        (SERVICE_TURN_ON, {}, SonyReceiverCode.POWER_ON),
        (SERVICE_TURN_OFF, {}, SonyReceiverCode.POWER_OFF),
        (SERVICE_VOLUME_UP, {}, SonyReceiverCode.VOLUME_UP),
        (SERVICE_VOLUME_DOWN, {}, SonyReceiverCode.VOLUME_DOWN),
        (SERVICE_VOLUME_MUTE, {"is_volume_muted": True}, SonyReceiverCode.MUTE),
        (SERVICE_SELECT_SOURCE, {ATTR_INPUT_SOURCE: "GAME"}, SonyReceiverCode.GAME),
        (
            SERVICE_SELECT_SOURCE,
            {ATTR_INPUT_SOURCE: "SAT/CATV"},
            SonyReceiverCode.SAT_CATV,
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_action_sends_code(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    service: str,
    service_data: dict[str, Any],
    expected_code: SonyReceiverCode,
) -> None:
    """Test each media player action sends the right IR code."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
        blocking=True,
    )
    assert mock_infrared_emitter_entity.send_command_calls == [expected_code]


@pytest.mark.usefixtures("init_integration")
async def test_assumed_state_tracking(hass: HomeAssistant) -> None:
    """Test power and source are tracked optimistically."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "TUNER"},
        blocking=True,
    )
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INPUT_SOURCE] == "TUNER"


@pytest.mark.usefixtures("init_integration")
async def test_invalid_source(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Test selecting an unknown source raises."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "PHONO"},
            blocking=True,
        )
    assert mock_infrared_emitter_entity.send_command_calls == []


@pytest.mark.parametrize(
    ("restored", "expected_state", "expected_source"),
    [
        (State(ENTITY_ID, STATE_OFF), STATE_OFF, None),
        (State(ENTITY_ID, STATE_ON, {ATTR_INPUT_SOURCE: "GAME"}), STATE_ON, "GAME"),
    ],
)
@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity",
    "mock_infrared_receiver_entity",
    "mock_code_to_command",
)
async def test_restore_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    restored: State,
    expected_state: str,
    expected_source: str | None,
) -> None:
    """Test the assumed state is restored after a restart."""
    mock_restore_cache(hass, [restored])
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state.state == expected_state
    assert state.attributes.get(ATTR_INPUT_SOURCE) == expected_source


@pytest.mark.usefixtures("init_integration")
async def test_availability_follows_emitter(hass: HomeAssistant) -> None:
    """Test the media player follows the emitter availability."""
    hass.states.async_set(EMITTER_ENTITY_ID, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_send_sirc(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Test sending an arbitrary SIRC code."""
    await hass.services.async_call(
        DOMAIN,
        "send_sirc",
        {ATTR_ENTITY_ID: ENTITY_ID, "address": 0xB0, "address_bits": 8, "command": 12},
        blocking=True,
    )
    [command] = mock_infrared_emitter_entity.send_command_calls
    assert isinstance(command, SonyRepeatedCommand)
    assert (command.address, command.address_bits, command.command) == (0xB0, 8, 12)


@pytest.mark.usefixtures("init_integration")
async def test_send_sirc_invalid(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Test an address too large for its bit width is rejected."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "send_sirc",
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                "address": 0x30,
                "address_bits": 5,
                "command": 1,
            },
            blocking=True,
        )


@pytest.mark.parametrize(
    "mock_config_entry",
    [
        MockConfigEntry(
            domain="sony_receiver_ir",
            data={"infrared_receiver_entity_id": "infrared.test_ir_receiver"},
        )
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_no_emitter_no_media_player(hass: HomeAssistant) -> None:
    """Test no media player is created without an emitter."""
    assert hass.states.get(ENTITY_ID) is None
