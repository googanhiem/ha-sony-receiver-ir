"""Constants for the Sony Receiver IR integration."""

from collections.abc import Mapping
from typing import Any

DOMAIN = "sony_receiver_ir"
CONF_INFRARED_ENTITY_ID = "infrared_entity_id"
CONF_INFRARED_RECEIVER_ENTITY_ID = "infrared_receiver_entity_id"
CONF_MODEL = "model"
CONF_TRACK_PHYSICAL_REMOTE = "track_physical_remote"
DEFAULT_TRACK_PHYSICAL_REMOTE = True
# Update state: the media player keeps an assumed power and source state.
# When off it only sends commands, which also turns off following the
# physical remote.
CONF_UPDATE_STATE = "update_state"
DEFAULT_UPDATE_STATE = True
# Version 0.2.0 stored the opposite, as "stateless".
CONF_LEGACY_STATELESS = "stateless"


def update_state_enabled(options: Mapping[str, Any]) -> bool:
    """Return whether the media player keeps state, honouring 0.2.0 options."""
    if CONF_UPDATE_STATE in options:
        return bool(options[CONF_UPDATE_STATE])
    return not options.get(CONF_LEGACY_STATELESS, False)


# Dispatcher signal for keys received from the remote, formatted with the entry ID.
SIGNAL_RECEIVED_COMMAND = f"{DOMAIN}_received_command_{{}}"

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
