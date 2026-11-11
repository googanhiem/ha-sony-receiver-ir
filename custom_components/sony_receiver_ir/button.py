"""Button platform for the Sony Receiver IR integration."""

from dataclasses import dataclass
from typing import override

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .codes import SonyReceiverCode
from .const import CONF_INFRARED_ENTITY_ID
from .entity import SonyReceiverIrEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SonyReceiverIrButtonEntityDescription(ButtonEntityDescription):
    """Describes a Sony Receiver IR button entity."""

    command_code: SonyReceiverCode


def _button(
    key: str, code: SonyReceiverCode, *, enabled: bool = True
) -> SonyReceiverIrButtonEntityDescription:
    return SonyReceiverIrButtonEntityDescription(
        key=key,
        translation_key=key,
        command_code=code,
        entity_registry_enabled_default=enabled,
    )


BUTTON_DESCRIPTIONS: tuple[SonyReceiverIrButtonEntityDescription, ...] = (
    _button("power", SonyReceiverCode.POWER),
    _button("power_on", SonyReceiverCode.POWER_ON),
    _button("power_off", SonyReceiverCode.POWER_OFF),
    _button("sleep", SonyReceiverCode.SLEEP),
    _button("volume_up", SonyReceiverCode.VOLUME_UP),
    _button("volume_down", SonyReceiverCode.VOLUME_DOWN),
    _button("mute", SonyReceiverCode.MUTE),
    _button("bd_dvd", SonyReceiverCode.BD_DVD),
    _button("game", SonyReceiverCode.GAME),
    _button("sat_catv", SonyReceiverCode.SAT_CATV),
    _button("video", SonyReceiverCode.VIDEO),
    # Only on older receivers with three video inputs.
    _button("video_3", SonyReceiverCode.VIDEO_3, enabled=False),
    _button("tv", SonyReceiverCode.TV),
    _button("sa_cd_cd", SonyReceiverCode.SA_CD_CD),
    _button("tuner", SonyReceiverCode.TUNER),
    _button("preset_up", SonyReceiverCode.PRESET_UP),
    _button("preset_down", SonyReceiverCode.PRESET_DOWN),
    _button("num_0", SonyReceiverCode.NUM_0, enabled=False),
    _button("num_1", SonyReceiverCode.NUM_1, enabled=False),
    _button("num_2", SonyReceiverCode.NUM_2, enabled=False),
    _button("num_3", SonyReceiverCode.NUM_3, enabled=False),
    _button("num_4", SonyReceiverCode.NUM_4, enabled=False),
    _button("num_5", SonyReceiverCode.NUM_5, enabled=False),
    _button("num_6", SonyReceiverCode.NUM_6, enabled=False),
    _button("num_7", SonyReceiverCode.NUM_7, enabled=False),
    _button("num_8", SonyReceiverCode.NUM_8, enabled=False),
    _button("num_9", SonyReceiverCode.NUM_9, enabled=False),
    _button("two_ch", SonyReceiverCode.TWO_CH),
    _button("afd", SonyReceiverCode.AFD),
    _button("movie", SonyReceiverCode.MOVIE),
    _button("music", SonyReceiverCode.MUSIC),
    _button("amp_menu", SonyReceiverCode.AMP_MENU),
    _button("up", SonyReceiverCode.NAV_UP),
    _button("down", SonyReceiverCode.NAV_DOWN),
    _button("left", SonyReceiverCode.NAV_LEFT),
    _button("right", SonyReceiverCode.NAV_RIGHT),
    _button("display", SonyReceiverCode.DISPLAY),
    _button("test_tone", SonyReceiverCode.TEST_TONE, enabled=False),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sony Receiver IR buttons from a config entry."""
    if not (infrared_entity_id := entry.data.get(CONF_INFRARED_ENTITY_ID)):
        return
    async_add_entities(
        SonyReceiverIrButton(entry, infrared_entity_id, description)
        for description in BUTTON_DESCRIPTIONS
    )


class SonyReceiverIrButton(
    SonyReceiverIrEntity, InfraredEmitterConsumerEntity, ButtonEntity
):
    """A single remote control key."""

    entity_description: SonyReceiverIrButtonEntityDescription

    def __init__(
        self,
        entry: ConfigEntry,
        infrared_entity_id: str,
        description: SonyReceiverIrButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(entry, unique_id_suffix=description.key)
        self._infrared_emitter_entity_id = infrared_entity_id
        self.entity_description = description

    @override
    async def async_press(self) -> None:
        """Press the button."""
        await self._send_command(self.entity_description.command_code.to_command())
