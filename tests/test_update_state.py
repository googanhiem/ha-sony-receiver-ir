"""Tests for the Update state option."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest

from custom_components.sony_receiver_ir.codes import (
    SonyReceiverCode,
    SonyRepeatedCommand,
)
from custom_components.sony_receiver_ir.const import (
    CONF_LEGACY_STATELESS,
    CONF_TRACK_PHYSICAL_REMOTE,
    CONF_UPDATE_STATE,
)
from homeassistant.components.infrared import InfraredReceivedSignal
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_SELECT_SOURCE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.data_entry_flow import FlowResultType

from .common import MockConfigEntry, mock_restore_cache
from .conftest import MockInfraredEmitterEntity, MockInfraredReceiverEntity

ENTITY_ID = "media_player.sony_av_receiver"
EVENT_ENTITY_ID = "event.sony_av_receiver_received_command"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return the platforms to set up."""
    return [Platform.EVENT, Platform.MEDIA_PLAYER]


@pytest.fixture
def update_state() -> bool:
    """Return whether the entry updates the media player state."""
    return False


@pytest.fixture
def mock_config_entry(
    mock_config_entry: MockConfigEntry, update_state: bool
) -> MockConfigEntry:
    """Return the config entry with Update state and remote tracking set."""
    return MockConfigEntry(
        domain=mock_config_entry.domain,
        entry_id=mock_config_entry.entry_id,
        title=mock_config_entry.title,
        version=mock_config_entry.version,
        data=dict(mock_config_entry.data),
        options={CONF_UPDATE_STATE: update_state, CONF_TRACK_PHYSICAL_REMOTE: True},
    )


def _press(
    receiver: MockInfraredReceiverEntity,
    freezer: FrozenDateTimeFactory,
    code: SonyReceiverCode,
) -> None:
    """Press a key on the remote, far enough apart to not be a repeat."""
    freezer.tick(timedelta(seconds=1))
    address, address_bits, command = code.value
    timings = SonyRepeatedCommand(
        address=address, address_bits=address_bits, command=command
    ).get_raw_timings()
    receiver._handle_received_signal(InfraredReceivedSignal(timings=timings))


@pytest.mark.usefixtures("init_integration")
async def test_no_state_sends_commands_without_state(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test commands are sent but never change the shown state."""
    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN

    for service, data in (
        (SERVICE_TURN_OFF, {}),
        (SERVICE_TURN_ON, {}),
        (SERVICE_SELECT_SOURCE, {ATTR_INPUT_SOURCE: "GAME"}),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_ID, **data},
            blocking=True,
        )
        state = hass.states.get(ENTITY_ID)
        assert state.state == STATE_UNKNOWN
        assert state.attributes.get(ATTR_INPUT_SOURCE) is None

    assert mock_infrared_emitter_entity.send_command_calls == [
        SonyReceiverCode.POWER_OFF,
        SonyReceiverCode.POWER_ON,
        SonyReceiverCode.GAME,
    ]


@pytest.mark.usefixtures("init_integration")
async def test_no_state_ignores_physical_remote(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the remote still fires events but no longer changes the state."""
    _press(mock_infrared_receiver_entity, freezer, SonyReceiverCode.POWER_OFF)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN
    assert hass.states.get(EVENT_ENTITY_ID).attributes["event_type"] == "power_off"


@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity",
    "mock_infrared_receiver_entity",
    "mock_code_to_command",
)
async def test_no_state_does_not_restore(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a remembered state is not restored with Update state off."""
    mock_restore_cache(hass, [State(ENTITY_ID, STATE_OFF)])
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN


@pytest.mark.parametrize("update_state", [True])
@pytest.mark.usefixtures("init_integration")
async def test_update_state_keeps_state(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the media player keeps state and follows the remote by default."""
    assert hass.states.get(ENTITY_ID).state == STATE_ON
    _press(mock_infrared_receiver_entity, freezer, SonyReceiverCode.POWER_OFF)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_OFF


def _track_selector(result: dict):
    """Return the Track physical remote selector of an options form."""
    for key, selector in result["data_schema"].schema.items():
        if key == CONF_TRACK_PHYSICAL_REMOTE:
            return selector
    raise AssertionError("Track physical remote is not in the form")


@pytest.mark.parametrize("update_state", [True])
async def test_options_grey_out_tracking_without_update_state(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test turning Update state off greys out tracking and keeps its value."""
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    assert not _track_selector(result).config.get("read_only")
    keys = [str(key) for key in result["data_schema"].schema]
    # Update state comes right before the toggle it greys out, and is on.
    assert keys.index(CONF_UPDATE_STATE) + 1 == keys.index(CONF_TRACK_PHYSICAL_REMOTE)

    # The tracking value is kept even when the form doesn't send it.
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_UPDATE_STATE: False}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert init_integration.options[CONF_UPDATE_STATE] is False
    assert init_integration.options[CONF_TRACK_PHYSICAL_REMOTE] is True
    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN

    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    assert _track_selector(result).config["read_only"] is True

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_UPDATE_STATE: True}
    )
    await hass.async_block_till_done()
    assert init_integration.options[CONF_TRACK_PHYSICAL_REMOTE] is True
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    assert not _track_selector(result).config.get("read_only")


@pytest.fixture
def legacy_options() -> dict:
    """Return options saved by version 0.2.0."""
    return {CONF_LEGACY_STATELESS: True, CONF_TRACK_PHYSICAL_REMOTE: True}


@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity",
    "mock_infrared_receiver_entity",
    "mock_code_to_command",
)
async def test_legacy_stateless_option(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, legacy_options: dict
) -> None:
    """Test a 0.2.0 Stateless entry behaves as Update state off and converts."""
    entry = MockConfigEntry(
        domain=mock_config_entry.domain,
        entry_id=mock_config_entry.entry_id,
        title=mock_config_entry.title,
        version=mock_config_entry.version,
        data=dict(mock_config_entry.data),
        options=legacy_options,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN

    # The form shows Update state off, and tracking greyed out.
    result = await hass.config_entries.options.async_init(entry.entry_id)
    suggested = {
        str(key): key.description.get("suggested_value")
        for key in result["data_schema"].schema
        if key.description
    }
    assert suggested[CONF_UPDATE_STATE] is False
    assert _track_selector(result).config["read_only"] is True

    # Saving replaces the old option with the new one.
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_UPDATE_STATE: True}
    )
    await hass.async_block_till_done()
    assert CONF_LEGACY_STATELESS not in entry.options
    assert entry.options[CONF_UPDATE_STATE] is True
    assert hass.states.get(ENTITY_ID).state == STATE_ON
