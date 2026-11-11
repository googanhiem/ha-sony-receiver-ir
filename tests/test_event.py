"""Tests for the Sony Receiver IR event entity."""

from unittest.mock import patch

from infrared_protocols.commands.nec import NECCommand
from infrared_protocols.commands.sony import SonyCommand
import pytest

from custom_components.sony_receiver_ir.codes import (
    SonyReceiverCode,
    SonyRepeatedCommand,
)
from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.components.infrared import InfraredReceivedSignal
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant

from .conftest import RECEIVER_ENTITY_ID, MockInfraredReceiverEntity

ENTITY_ID = "event.sony_av_receiver_received_command"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return the platforms to set up."""
    return [Platform.EVENT]


def _receive(receiver: MockInfraredReceiverEntity, timings: list[int]) -> None:
    receiver._handle_received_signal(InfraredReceivedSignal(timings=timings))


def _real_timings(code: SonyReceiverCode) -> list[int]:
    address, address_bits, command = code.value
    return SonyRepeatedCommand(
        address=address, address_bits=address_bits, command=command
    ).get_raw_timings()


@pytest.mark.parametrize(
    ("code", "expected_event_type"),
    [
        (SonyReceiverCode.POWER, "power"),
        (SonyReceiverCode.VOLUME_UP, "volume_up"),
        (SonyReceiverCode.BD_DVD, "bd_dvd"),
        (SonyReceiverCode.SAT_CATV, "sat_catv"),
        (SonyReceiverCode.NAV_LEFT, "nav_left"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_event_fires(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    code: SonyReceiverCode,
    expected_event_type: str,
) -> None:
    """Test a received remote key fires the matching event."""
    _receive(mock_infrared_receiver_entity, _real_timings(code))
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
    assert state.attributes[ATTR_EVENT_TYPE] == expected_event_type
    assert state.attributes["command"] == code.value[2]


@pytest.mark.usefixtures("init_integration")
async def test_unknown_command_on_receiver_address(
    hass: HomeAssistant, mock_infrared_receiver_entity: MockInfraredReceiverEntity
) -> None:
    """Test an unmapped command on a receiver address fires 'unknown'."""
    timings = SonyCommand(address=0x30, address_bits=8, command=0x7F).get_raw_timings()
    _receive(mock_infrared_receiver_entity, timings)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).attributes[ATTR_EVENT_TYPE] == "unknown"


@pytest.mark.parametrize(
    "timings",
    [
        # Sony TV power (Sony SIRC, but another device address)
        SonyCommand(address=0x01, address_bits=5, command=21).get_raw_timings(),
        NECCommand(address=0xFB04, command=0x08).get_raw_timings(),
        [1, 2, 3, 4],
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_ignored_signals(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    timings: list[int],
) -> None:
    """Test signals not meant for the receiver are ignored."""
    _receive(mock_infrared_receiver_entity, timings)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_EVENT_TYPE) is None


@pytest.mark.usefixtures("init_integration")
async def test_repeated_frames_are_one_press(
    hass: HomeAssistant, mock_infrared_receiver_entity: MockInfraredReceiverEntity
) -> None:
    """Test frames of a held key received separately fire a single event."""
    frame = SonyCommand(address=0x30, address_bits=8, command=0x12).get_raw_timings()
    events: list[str] = []
    hass.bus.async_listen(
        "state_changed",
        lambda event: (
            event.data["entity_id"] == ENTITY_ID
            and events.append(event.data["new_state"].state)
        ),
    )
    clock = "custom_components.sony_receiver_ir.event.time.monotonic"
    with patch(clock, return_value=100.0):
        _receive(mock_infrared_receiver_entity, frame)
    with patch(clock, return_value=100.045):
        _receive(mock_infrared_receiver_entity, frame)
    with patch(clock, return_value=100.09):
        _receive(mock_infrared_receiver_entity, frame)
    await hass.async_block_till_done()
    assert len(events) == 1

    # A new press after the key was released fires again.
    with patch(clock, return_value=101.0):
        _receive(mock_infrared_receiver_entity, frame)
    await hass.async_block_till_done()
    assert len(events) == 2


@pytest.mark.parametrize("has_receiver", [False])
@pytest.mark.usefixtures("init_integration")
async def test_no_receiver_no_event(hass: HomeAssistant) -> None:
    """Test no event entity is created without a receiver."""
    assert hass.states.get(ENTITY_ID) is None


@pytest.mark.usefixtures("init_integration")
async def test_availability_follows_receiver(hass: HomeAssistant) -> None:
    """Test the event entity follows the receiver availability."""
    hass.states.async_set(RECEIVER_ENTITY_ID, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
