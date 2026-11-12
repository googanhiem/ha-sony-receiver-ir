"""Test the integration ships brand images for light and dark mode."""

from pathlib import Path

from PIL import Image, ImageStat
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_custom_components

BRAND_DIR = (
    Path(__file__).parent.parent / "custom_components" / "sony_receiver_ir" / "brand"
)

# Every image Home Assistant may request. A missing one falls back to another
# image, e.g. dark_icon@2x.png to the black icon@2x.png, which is unreadable
# in dark mode.
IMAGES = [
    f"{prefix}{kind}{scale}.png"
    for prefix in ("", "dark_")
    for kind in ("icon", "logo")
    for scale in ("", "@2x")
]


async def test_has_branding(hass: HomeAssistant) -> None:
    """Test Home Assistant finds the brand folder."""
    integration = (await async_get_custom_components(hass))["sony_receiver_ir"]
    assert integration.has_branding


@pytest.mark.parametrize("image", IMAGES)
def test_brand_image(image: str) -> None:
    """Test each image exists and is readable on its theme's background."""
    with Image.open(BRAND_DIR / image) as img:
        rgba = img.convert("RGBA")
    width, height = rgba.size
    assert height == (512 if "@2x" in image else 256)
    if "icon" in image:
        assert width == height
    visible = rgba.getchannel("A").point(lambda alpha: 255 if alpha > 128 else 0)
    assert visible.getbbox() is not None
    brightness = sum(ImageStat.Stat(rgba.convert("RGB"), mask=visible).mean) / 3
    if image.startswith("dark_"):
        assert brightness > 200, "dark mode image must be light"
    else:
        assert brightness < 60, "light mode image must be dark"
