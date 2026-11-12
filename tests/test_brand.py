"""Test the integration ships its brand images."""

from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_custom_components


async def test_has_branding(hass: HomeAssistant) -> None:
    """Test Home Assistant finds the brand folder."""
    integration = (await async_get_custom_components(hass))["sony_receiver_ir"]
    assert integration.has_branding
