"""Config flow for the Sony Receiver IR integration."""

from typing import Any, override

from homeassistant.components.infrared import (
    DOMAIN as INFRARED_DOMAIN,
    async_get_emitters,
    async_get_receivers,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    TextSelector,
)

from .const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    CONF_MODEL,
    DOMAIN,
)

try:  # Home Assistant 2026.11+ validates with probatio.
    import probatio as vol
except ImportError:  # pragma: no cover - older Home Assistant releases
    import voluptuous as vol


@callback
def _receiver_schema(hass: HomeAssistant) -> vol.Schema:
    """Return the model and emitter/receiver selection schema."""
    return vol.Schema(
        {
            vol.Optional(CONF_MODEL): TextSelector(),
            vol.Optional(CONF_INFRARED_ENTITY_ID): EntitySelector(
                EntitySelectorConfig(
                    domain=INFRARED_DOMAIN,
                    include_entities=async_get_emitters(hass),
                )
            ),
            vol.Optional(CONF_INFRARED_RECEIVER_ENTITY_ID): EntitySelector(
                EntitySelectorConfig(
                    domain=INFRARED_DOMAIN,
                    include_entities=async_get_receivers(hass),
                )
            ),
        }
    )


def _has_infrared_entity(user_input: dict[str, Any]) -> bool:
    """Return True if an emitter or a receiver was selected."""
    return bool(
        user_input.get(CONF_INFRARED_ENTITY_ID)
        or user_input.get(CONF_INFRARED_RECEIVER_ENTITY_ID)
    )


class SonyReceiverIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sony Receiver IR."""

    VERSION = 1

    def _entity_name(self, entity_id: str) -> str:
        """Return the friendly name of an entity for the entry title."""
        entry = er.async_get(self.hass).async_get(entity_id)
        if entry is None:
            return entity_id
        return entry.name or entry.original_name or entity_id

    @callback
    def _async_abort_infrared_entities_match(
        self, user_input: dict[str, Any], exclude_entry_id: str | None = None
    ) -> None:
        """Abort if another entry already uses one of these IR entities."""
        for entry in self._async_current_entries(include_ignore=False):
            if entry.entry_id == exclude_entry_id:
                continue
            for key in (CONF_INFRARED_ENTITY_ID, CONF_INFRARED_RECEIVER_ENTITY_ID):
                if (value := user_input.get(key)) and entry.data.get(key) == value:
                    raise AbortFlow("already_configured")

    @callback
    def _async_has_infrared_entities(self) -> bool:
        """Return True if any infrared emitter or receiver exists."""
        return bool(async_get_emitters(self.hass) or async_get_receivers(self.hass))

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the infrared entity selection."""
        if not self._async_has_infrared_entities():
            return self.async_abort(reason="no_infrared_entities")

        errors: dict[str, str] = {}
        if user_input is not None:
            if _has_infrared_entity(user_input):
                self._async_abort_infrared_entities_match(user_input)
                title_entity_id = user_input.get(
                    CONF_INFRARED_ENTITY_ID
                ) or user_input.get(CONF_INFRARED_RECEIVER_ENTITY_ID)
                model = user_input.get(CONF_MODEL) or "AV receiver"
                return self.async_create_entry(
                    title=f"Sony {model} via {self._entity_name(title_entity_id)}",
                    data=user_input,
                )
            errors["base"] = "missing_infrared_entity"

        return self.async_show_form(
            step_id="user",
            data_schema=_receiver_schema(self.hass),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the infrared entities."""
        entry = self._get_reconfigure_entry()
        if not self._async_has_infrared_entities():
            return self.async_abort(reason="no_infrared_entities")

        errors: dict[str, str] = {}
        if user_input is not None:
            if _has_infrared_entity(user_input):
                self._async_abort_infrared_entities_match(
                    user_input, exclude_entry_id=entry.entry_id
                )
                # Replace rather than update the data, so a cleared optional
                # selector removes that entity from the entry.
                return self.async_update_reload_and_abort(entry, data=user_input)
            errors["base"] = "missing_infrared_entity"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _receiver_schema(self.hass), entry.data
            ),
            errors=errors,
        )
