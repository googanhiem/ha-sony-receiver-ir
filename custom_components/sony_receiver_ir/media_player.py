"""Media player platform for the Sony Receiver IR integration."""

from collections.abc import Mapping
from typing import Any, override

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .codes import SIRC_FRAMES_PER_COMMAND, SonyReceiverCode, SonyRepeatedCommand
from .const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_TRACK_PHYSICAL_REMOTE,
    DEFAULT_TRACK_PHYSICAL_REMOTE,
    DOMAIN,
    SIGNAL_RECEIVED_COMMAND,
    input_name,
    update_state_enabled,
)
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

# Codes of the renameable HDMI inputs, by option key.
RENAMEABLE_INPUT_CODES: dict[str, SonyReceiverCode] = {
    "name_bd_dvd": SonyReceiverCode.BD_DVD,
    "name_game": SonyReceiverCode.GAME,
    "name_sat_catv": SonyReceiverCode.SAT_CATV,
    "name_video": SonyReceiverCode.VIDEO,
}
FIXED_INPUT_CODES: dict[str, SonyReceiverCode] = {
    "TV": SonyReceiverCode.TV,
    "SA-CD/CD": SonyReceiverCode.SA_CD_CD,
    "TUNER": SonyReceiverCode.TUNER,
}
# Input keys that switch to an input that isn't in the source list.
OTHER_INPUT_EVENT_TYPES = {SonyReceiverCode.VIDEO_3.name.lower()}


def source_to_code(options: Mapping[str, Any]) -> dict[str, SonyReceiverCode]:
    """Return the source list, using the custom input names from the options."""
    sources = {
        input_name(options, key): code for key, code in RENAMEABLE_INPUT_CODES.items()
    }
    sources.update(FIXED_INPUT_CODES)
    return sources


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
    command sent, or the last key received from the remote, and restored
    across restarts. With Update state off there is no state at all: the
    entity only sends commands.
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
        self._source_to_code = source_to_code(entry.options)
        self._attr_source_list = list(self._source_to_code)
        self._event_type_to_source = {
            code.name.lower(): source for source, code in self._source_to_code.items()
        }
        self._signal = SIGNAL_RECEIVED_COMMAND.format(entry.entry_id)
        self._stateless = not update_state_enabled(entry.options)
        self._track_physical_remote = not self._stateless and entry.options.get(
            CONF_TRACK_PHYSICAL_REMOTE, DEFAULT_TRACK_PHYSICAL_REMOTE
        )
        if self._stateless:
            self._attr_state = None

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the assumed state and follow keys received from the remote."""
        await super().async_added_to_hass()
        if self._stateless:
            return
        if self._track_physical_remote:
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass, self._signal, self._async_handle_received_command
                )
            )
        if (last_state := await self.async_get_last_state()) is None:
            return
        if last_state.state == MediaPlayerState.OFF:
            self._attr_state = MediaPlayerState.OFF
        if (source := last_state.attributes.get("source")) in self._source_to_code:
            self._attr_source = source

    @callback
    def _async_handle_received_command(self, event_type: str) -> None:
        """Update the assumed state from a key pressed on the remote."""
        if event_type == "power_on":
            self._attr_state = MediaPlayerState.ON
        elif event_type == "power_off":
            self._attr_state = MediaPlayerState.OFF
        elif event_type == "power":
            self._attr_state = (
                MediaPlayerState.OFF
                if self._attr_state == MediaPlayerState.ON
                else MediaPlayerState.ON
            )
        elif (source := self._event_type_to_source.get(event_type)) is not None:
            self._attr_source = source
        elif event_type in OTHER_INPUT_EVENT_TYPES:
            self._attr_source = None
        else:
            return
        self.async_write_ha_state()

    @callback
    def _async_set_assumed_state(
        self, *, state: MediaPlayerState | None = None, source: str | None = None
    ) -> None:
        """Remember the state a sent command puts the device in, if updating state."""
        if self._stateless:
            return
        if state is not None:
            self._attr_state = state
        if source is not None:
            self._attr_source = source
        self.async_write_ha_state()

    async def _send(self, code: SonyReceiverCode) -> None:
        """Send a code to the receiver."""
        await self._send_command(code.to_command())

    @override
    async def async_turn_on(self) -> None:
        """Turn on the receiver."""
        await self._send(SonyReceiverCode.POWER_ON)
        self._async_set_assumed_state(state=MediaPlayerState.ON)

    @override
    async def async_turn_off(self) -> None:
        """Turn off the receiver."""
        await self._send(SonyReceiverCode.POWER_OFF)
        self._async_set_assumed_state(state=MediaPlayerState.OFF)

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
        if (code := self._source_to_code.get(source)) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_source",
                translation_placeholders={"source": source},
            )
        await self._send(code)
        self._async_set_assumed_state(source=source)

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
