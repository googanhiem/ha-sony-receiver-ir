"""Tests for the Sony Receiver IR config flow."""

import pytest

from custom_components.sony_receiver_ir.const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    CONF_MODEL,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .common import MockConfigEntry
from .conftest import EMITTER_ENTITY_ID, RECEIVER_ENTITY_ID

pytestmark = pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)


@pytest.mark.parametrize(
    ("user_input", "expected_title"),
    [
        (
            {CONF_MODEL: "STR-DH820", CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID},
            "Sony STR-DH820 via Test IR emitter",
        ),
        (
            {
                CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
                CONF_INFRARED_RECEIVER_ENTITY_ID: RECEIVER_ENTITY_ID,
            },
            "Sony AV receiver via Test IR emitter",
        ),
        (
            {CONF_INFRARED_RECEIVER_ENTITY_ID: RECEIVER_ENTITY_ID},
            "Sony AV receiver via Test IR receiver",
        ),
    ],
)
async def test_user_flow(
    hass: HomeAssistant, user_input: dict[str, str], expected_title: str
) -> None:
    """Test a successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == expected_title
    assert result["data"] == user_input


async def test_user_flow_requires_entity(hass: HomeAssistant) -> None:
    """Test the flow errors when no IR entity is selected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_MODEL: "STR-DH820"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "missing_infrared_entity"}


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the flow aborts when the emitter is already used."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test reconfiguring with the same emitter replaces the data."""
    result = await init_integration.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert dict(init_integration.data) == {CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID}


async def test_reconfigure_requires_entity(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test reconfigure errors when no IR entity is selected."""
    result = await init_integration.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["errors"] == {"base": "missing_infrared_entity"}


async def test_no_infrared_entities(hass: HomeAssistant) -> None:
    """Test the flow aborts when there are no IR entities."""
    for entity_id in (EMITTER_ENTITY_ID, RECEIVER_ENTITY_ID):
        await hass.data["infrared"].async_remove_entity(entity_id)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_entities"
