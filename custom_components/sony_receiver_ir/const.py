"""Constants for the Sony Receiver IR integration."""

from collections.abc import Mapping
from typing import Any

DOMAIN = "sony_receiver_ir"
CONF_INFRARED_ENTITY_ID = "infrared_entity_id"
CONF_INFRARED_RECEIVER_ENTITY_ID = "infrared_receiver_entity_id"
CONF_MODEL = "model"

MANUFACTURER = "Sony"
DEVICE_NAME = "Sony AV Receiver"

# The four HDMI inputs whose names can be changed in the options, keyed by
# the option that holds the custom name, with Sony's default name.
RENAMEABLE_INPUTS: dict[str, str] = {
    "name_bd_dvd": "BD/DVD",
    "name_game": "GAME",
    "name_sat_catv": "SAT/CATV",
    "name_video": "VIDEO",
}
FIXED_INPUTS: tuple[str, ...] = ("TV", "SA-CD/CD", "TUNER")


def input_name(options: Mapping[str, Any], option_key: str) -> str:
    """Return the custom name of an input, or Sony's default name."""
    name = str(options.get(option_key) or "").strip()
    return name or RENAMEABLE_INPUTS[option_key]
