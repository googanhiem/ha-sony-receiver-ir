"""Tests for the Sony Receiver IR buttons."""

import pytest

from custom_components.sony_receiver_ir.button import BUTTON_DESCRIPTIONS
from custom_components.sony_receiver_ir.codes import SonyReceiverCode
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import MockConfigEntry
from .conftest import EMITTER_ENTITY_ID, MockInfraredEmitterEntity


@pytest.fixture
def platforms() -> list[Platform]:
    """Return the platforms to set up."""
    return [Platform.BUTTON]


@pytest.mark.usefixtures("init_integration")
async def test_entities_created(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all buttons are registered, with rarely used ones disabled."""
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entries) == len(BUTTON_DESCRIPTIONS)
    disabled = {entry.entity_id for entry in entries if entry.disabled_by}
    assert disabled == {
        "button.sony_av_receiver_video_3",
        "button.sony_av_receiver_test_tone",
        *(f"button.sony_av_receiver_{i}" for i in range(10)),
    }


@pytest.mark.parametrize(
    ("entity_id", "expected_code"),
    [
        ("button.sony_av_receiver_power", SonyReceiverCode.POWER),
        ("button.sony_av_receiver_bd_dvd", SonyReceiverCode.BD_DVD),
        ("button.sony_av_receiver_sa_cd_cd", SonyReceiverCode.SA_CD_CD),
        ("button.sony_av_receiver_movie", SonyReceiverCode.MOVIE),
        ("button.sony_av_receiver_2ch_analog_direct", SonyReceiverCode.TWO_CH),
        ("button.sony_av_receiver_amp_menu", SonyReceiverCode.AMP_MENU),
        ("button.sony_av_receiver_up", SonyReceiverCode.NAV_UP),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_press_sends_code(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    entity_id: str,
    expected_code: SonyReceiverCode,
) -> None:
    """Test pressing a button sends its IR code."""
    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert mock_infrared_emitter_entity.send_command_calls == [expected_code]


@pytest.mark.usefixtures("init_integration")
async def test_availability_follows_emitter(hass: HomeAssistant) -> None:
    """Test buttons follow the emitter availability."""
    hass.states.async_set(EMITTER_ENTITY_ID, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("button.sony_av_receiver_power").state == STATE_UNAVAILABLE
