"""Media player platform for the Sony Receiver IR integration."""

from typing import override

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .codes import SIRC_FRAMES_PER_COMMAND, SonyReceiverCode, SonyRepeatedCommand
from .const import CONF_INFRARED_ENTITY_ID, DOMAIN
from .entity import SonyReceiverIrEntity

try:  # Home Assistant 2026.11+ validates with probatio.
    import probatio as vol
except ImportError:  # pragma: no cover - older Home Assistant releases
    import voluptuous as vol

PARALLEL_UPDATES = 1

SERVICE_SEND_SIRC = "send_sirc"
ATTR_ADDRESS = "address"
ATTR_ADDRESS_BITS = "address_bits"
ATTR_COMMAND = "command"
ATTR_FRAMES = "frames"

SEND_SIRC_SCHEMA = {
    vol.Required(ATTR_ADDRESS): vol.All(vol.Coerce(int), vol.Range(min=0, max=0x1FFF)),
    vol.Required(ATTR_ADDRESS_BITS): vol.All(vol.Coerce(int), vol.In([5, 8, 13])),
    vol.Required(ATTR_COMMAND): vol.All(vol.Coerce(int), vol.Range(min=0, max=0x7F)),
    vol.Optional(ATTR_FRAMES, default=SIRC_FRAMES_PER_COMMAND): vol.All(
        vol.Coerce(int), vol.Range(min=1, max=20)
    ),
}

SOURCE_TO_CODE: dict[str, SonyReceiverCode] = {
    "BD/DVD": SonyReceiverCode.BD_DVD,
    "GAME": SonyReceiverCode.GAME,
    "SAT/CATV": SonyReceiverCode.SAT_CATV,
    "VIDEO": SonyReceiverCode.VIDEO,
    "TV": SonyReceiverCode.TV,
    "SA-CD/CD": SonyReceiverCode.SA_CD_CD,
    "TUNER": SonyReceiverCode.TUNER,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sony Receiver IR media player from a config entry."""
    if not (infrared_entity_id := entry.data.get(CONF_INFRARED_ENTITY_ID)):
        return
    async_add_entities([SonyReceiverIrMediaPlayer(entry, infrared_entity_id)])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SEND_SIRC, SEND_SIRC_SCHEMA, "async_send_sirc"
    )


class SonyReceiverIrMediaPlayer(
    SonyReceiverIrEntity,
    InfraredEmitterConsumerEntity,
    MediaPlayerEntity,
    RestoreEntity,
):
    """Sony AV receiver controlled over infrared.

    Infrared is one-way, so power state and source are assumed from the last
    command sent and restored across restarts.
    """

    _attr_name = None
    _attr_assumed_state = True
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, entry: ConfigEntry, infrared_entity_id: str) -> None:
        """Initialize the media player."""
        super().__init__(entry, unique_id_suffix="media_player")
        self._infrared_emitter_entity_id = infrared_entity_id
        self._attr_state = MediaPlayerState.ON
        self._attr_source = None
        self._attr_source_list = list(SOURCE_TO_CODE)

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the assumed power state and source."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is None:
            return
        if last_state.state == MediaPlayerState.OFF:
            self._attr_state = MediaPlayerState.OFF
        if (source := last_state.attributes.get("source")) in SOURCE_TO_CODE:
            self._attr_source = source

    async def _send(self, code: SonyReceiverCode) -> None:
        """Send a code to the receiver."""
        await self._send_command(code.to_command())

    @override
    async def async_turn_on(self) -> None:
        """Turn on the receiver."""
        await self._send(SonyReceiverCode.POWER_ON)
        self._attr_state = MediaPlayerState.ON
        self.async_write_ha_state()

    @override
    async def async_turn_off(self) -> None:
        """Turn off the receiver."""
        await self._send(SonyReceiverCode.POWER_OFF)
        self._attr_state = MediaPlayerState.OFF
        self.async_write_ha_state()

    @override
    async def async_volume_up(self) -> None:
        """Send volume up."""
        await self._send(SonyReceiverCode.VOLUME_UP)

    @override
    async def async_volume_down(self) -> None:
        """Send volume down."""
        await self._send(SonyReceiverCode.VOLUME_DOWN)

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Toggle mute (the receiver only has a mute toggle)."""
        await self._send(SonyReceiverCode.MUTE)

    @override
    async def async_select_source(self, source: str) -> None:
        """Switch to an input using its discrete code."""
        if (code := SOURCE_TO_CODE.get(source)) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_source",
                translation_placeholders={"source": source},
            )
        await self._send(code)
        self._attr_source = source
        self.async_write_ha_state()

    async def async_send_sirc(
        self, address: int, address_bits: int, command: int, frames: int
    ) -> None:
        """Send an arbitrary Sony SIRC code."""
        try:
            ir_command = SonyRepeatedCommand(
                address=address,
                address_bits=address_bits,
                command=command,
                frames=frames,
            )
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_sirc",
                translation_placeholders={"error": str(err)},
            ) from err
        await self._send_command(ir_command)
