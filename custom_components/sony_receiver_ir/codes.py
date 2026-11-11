"""Sony SIRC IR codes for Sony AV receivers.

Sony AV receivers (STR-DH, STR-DN, STR-DG, STR-DA, ...) use 15-bit Sony SIRC
on two addresses:

- 0x30: amplifier keys (power, volume, mute, inputs, numbers, sleep, ...).
- 0xB0: sound field, amplifier menu and cursor keys, and some newer inputs.

Sources: the irdb database (Sony/Receiver devices 48 and 176) and the
RM-AAU014 LIRC capture, which agree on every shared key. The input names on
newer remotes (BD/DVD, GAME, SAT/CATV, VIDEO) are assumed to reuse the codes
of the inputs they replaced (DVD, VIDEO 2, SAT, VIDEO 1); see the README.

Sony receivers only accept a command after seeing the same frame several
times, so every command is sent as three consecutive frames, just like a
short press on the original remote.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique
from typing import override

from infrared_protocols.commands import Command
from infrared_protocols.commands.sony import SonyCommand

SIRC_FRAMES_PER_COMMAND = 3

_ADDR_AMP = (0x30, 8)
_ADDR_SOUND = (0xB0, 8)


@dataclass(frozen=True, slots=True)
class SircFrame:
    """A decoded Sony SIRC frame."""

    address: int
    address_bits: int
    command: int


class SonyRepeatedCommand(SonyCommand):
    """A Sony SIRC command sent as several identical frames.

    Older infrared-protocols releases have no repeat support on SonyCommand,
    so the repetition is done here to work on every supported HA version.
    """

    def __init__(
        self,
        *,
        address: int,
        address_bits: int,
        command: int,
        frames: int = SIRC_FRAMES_PER_COMMAND,
    ) -> None:
        """Initialize the command."""
        super().__init__(address=address, address_bits=address_bits, command=command)
        self.frames = frames

    @override
    def get_raw_timings(self) -> list[int]:
        """Return the raw timings of all frames."""
        return super().get_raw_timings() * self.frames


@unique
class SonyReceiverCode(Enum):
    """Sony AV receiver IR codes as (address, address_bits, command)."""

    # Power
    POWER = (*_ADDR_AMP, 0x15)
    POWER_ON = (*_ADDR_AMP, 0x2E)
    POWER_OFF = (*_ADDR_AMP, 0x2F)
    SLEEP = (*_ADDR_AMP, 0x60)

    # Volume
    VOLUME_UP = (*_ADDR_AMP, 0x12)
    VOLUME_DOWN = (*_ADDR_AMP, 0x13)
    MUTE = (*_ADDR_AMP, 0x14)

    # Inputs (names of current remotes, codes of the inputs they replaced)
    BD_DVD = (*_ADDR_AMP, 0x7D)  # DVD
    GAME = (*_ADDR_AMP, 0x1E)  # VIDEO 2
    SAT_CATV = (*_ADDR_SOUND, 0x03)  # SAT
    VIDEO = (*_ADDR_AMP, 0x22)  # VIDEO 1
    VIDEO_3 = (*_ADDR_AMP, 0x42)
    TV = (*_ADDR_AMP, 0x6A)
    SA_CD_CD = (*_ADDR_AMP, 0x25)
    TUNER = (*_ADDR_AMP, 0x21)

    # Tuner
    PRESET_UP = (*_ADDR_AMP, 0x10)
    PRESET_DOWN = (*_ADDR_AMP, 0x11)
    NUM_1 = (*_ADDR_AMP, 0x00)
    NUM_2 = (*_ADDR_AMP, 0x01)
    NUM_3 = (*_ADDR_AMP, 0x02)
    NUM_4 = (*_ADDR_AMP, 0x03)
    NUM_5 = (*_ADDR_AMP, 0x04)
    NUM_6 = (*_ADDR_AMP, 0x05)
    NUM_7 = (*_ADDR_AMP, 0x06)
    NUM_8 = (*_ADDR_AMP, 0x07)
    NUM_9 = (*_ADDR_AMP, 0x08)
    NUM_0 = (*_ADDR_AMP, 0x09)

    # Sound fields (each press cycles through the modes of that group)
    TWO_CH = (*_ADDR_SOUND, 0x41)
    AFD = (*_ADDR_SOUND, 0x42)
    MOVIE = (*_ADDR_SOUND, 0x43)
    MUSIC = (*_ADDR_SOUND, 0x49)

    # Menu
    AMP_MENU = (*_ADDR_SOUND, 0x77)
    NAV_UP = (*_ADDR_SOUND, 0x78)
    NAV_DOWN = (*_ADDR_SOUND, 0x79)
    NAV_LEFT = (*_ADDR_SOUND, 0x7A)
    NAV_RIGHT = (*_ADDR_SOUND, 0x7B)
    DISPLAY = (*_ADDR_AMP, 0x4B)
    TEST_TONE = (*_ADDR_SOUND, 0x4A)

    @property
    def frame(self) -> SircFrame:
        """Return the SIRC frame of this code."""
        address, address_bits, command = self.value
        return SircFrame(address, address_bits, command)

    def to_command(self) -> Command:
        """Build the IR command for this code."""
        address, address_bits, command = self.value
        return SonyRepeatedCommand(
            address=address, address_bits=address_bits, command=command
        )

    @classmethod
    def from_frame(cls, frame: SircFrame) -> SonyReceiverCode | None:
        """Return the code matching a decoded frame, if any."""
        return _FRAME_TO_CODE.get(frame)


_FRAME_TO_CODE: dict[SircFrame, SonyReceiverCode] = {
    code.frame: code for code in SonyReceiverCode
}

RECEIVER_ADDRESSES: frozenset[tuple[int, int]] = frozenset({_ADDR_AMP, _ADDR_SOUND})

# SIRC decoding tolerances, in microseconds.
_LEADER_MIN, _LEADER_MAX = 1800, 3000
_SPACE_MIN, _SPACE_MAX = 300, 1000
_ZERO_MIN, _ZERO_MAX = 300, 900
_ONE_MIN, _ONE_MAX = 900, 1600
_VALID_BIT_COUNTS = (12, 15, 20)


def decode_sirc(timings: list[int]) -> SircFrame | None:
    """Decode the first valid Sony SIRC frame found in raw timings.

    Accepts signed (mark positive, space negative) or unsigned timings.
    """
    values = [abs(value) for value in timings]
    length = len(values)
    for start in range(length):
        if not _LEADER_MIN <= values[start] <= _LEADER_MAX:
            continue
        bits: list[int] = []
        pos = start + 1
        while (
            len(bits) < 20
            and pos + 1 < length
            and _SPACE_MIN <= values[pos] <= _SPACE_MAX
        ):
            mark = values[pos + 1]
            if _ZERO_MIN <= mark < _ZERO_MAX:
                bits.append(0)
            elif _ONE_MIN <= mark <= _ONE_MAX:
                bits.append(1)
            else:
                break
            pos += 2
        if len(bits) not in _VALID_BIT_COUNTS:
            continue
        # The frame must be followed by a gap (or end of capture), otherwise
        # this is a longer frame that failed to decode.
        if pos < length and values[pos] <= _SPACE_MAX:
            continue
        command = sum(bit << idx for idx, bit in enumerate(bits[:7]))
        address = sum(bit << idx for idx, bit in enumerate(bits[7:]))
        return SircFrame(address, len(bits) - 7, command)
    return None
