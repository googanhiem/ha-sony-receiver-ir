"""Event platform for the Sony Receiver IR integration.

Fires an event whenever a receiver key of the original Sony remote is received by the
configured infrared receiver.
"""

import logging
import time
from typing import override

from homeassistant.components.event import EventEntity
from homeassistant.components.infrared import (
    InfraredReceivedSignal,
    InfraredReceiverConsumerEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .codes import RECEIVER_ADDRESSES, SircFrame, SonyReceiverCode, decode_sirc
from .const import CONF_INFRARED_RECEIVER_ENTITY_ID
from .entity import SonyReceiverIrEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

EVENT_TYPE_UNKNOWN = "unknown"
EVENT_TYPES: list[str] = [
    *(code.name.lower() for code in SonyReceiverCode),
    EVENT_TYPE_UNKNOWN,
]

# A Sony remote repeats the frame every 45 ms for as long as a key is held.
# Frames of the same key closer together than this are one key press.
REPEAT_WINDOW = 0.2


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sony Receiver IR event entity from a config entry."""
    if not (receiver_entity_id := entry.data.get(CONF_INFRARED_RECEIVER_ENTITY_ID)):
        return
    async_add_entities([SonyReceiverIrReceivedCommandEvent(entry, receiver_entity_id)])


class SonyReceiverIrReceivedCommandEvent(
    SonyReceiverIrEntity, InfraredReceiverConsumerEntity, EventEntity
):
    """Event entity that fires when a Sony receiver remote key is received."""

    _attr_translation_key = "received_command"
    _attr_event_types = EVENT_TYPES

    def __init__(self, entry: ConfigEntry, receiver_entity_id: str) -> None:
        """Initialize the event entity."""
        super().__init__(entry, unique_id_suffix="received_command")
        self._infrared_receiver_entity_id = receiver_entity_id
        self._last_frame: SircFrame | None = None
        self._last_frame_time = 0.0

    @callback
    @override
    def _handle_signal(self, signal: InfraredReceivedSignal) -> None:
        """Handle a received IR signal."""
        frame = decode_sirc(signal.timings)
        if (
            frame is None
            or (frame.address, frame.address_bits) not in RECEIVER_ADDRESSES
        ):
            return

        now = time.monotonic()
        is_repeat = (
            frame == self._last_frame and now - self._last_frame_time < REPEAT_WINDOW
        )
        self._last_frame = frame
        self._last_frame_time = now
        if is_repeat:
            return

        code = SonyReceiverCode.from_frame(frame)
        event_type = code.name.lower() if code else EVENT_TYPE_UNKNOWN
        _LOGGER.debug(
            "Received Sony receiver IR command %s (address 0x%02X/%d bits, command 0x%02X)",
            event_type,
            frame.address,
            frame.address_bits,
            frame.command,
        )
        self._trigger_event(
            event_type,
            {
                "address": frame.address,
                "address_bits": frame.address_bits,
                "command": frame.command,
            },
        )
        self.async_write_ha_state()
