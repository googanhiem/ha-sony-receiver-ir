"""Common entity for the Sony Receiver IR integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import CONF_MODEL, DEVICE_NAME, DOMAIN, MANUFACTURER


class SonyReceiverIrEntity(Entity):
    """Sony Receiver IR base entity providing common device info."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, unique_id_suffix: str) -> None:
        """Initialize the entity."""
        self._attr_unique_id = f"{entry.entry_id}_{unique_id_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=DEVICE_NAME,
            manufacturer=MANUFACTURER,
            model=entry.data.get(CONF_MODEL) or "AV receiver",
        )
