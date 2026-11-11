"""Tests for the Sony SIRC encoding and decoding."""

from infrared_protocols.commands.sony import SonyCommand
import pytest

from custom_components.sony_receiver_ir.codes import (
    SIRC_FRAMES_PER_COMMAND,
    SircFrame,
    SonyReceiverCode,
    decode_sirc,
)


def test_power_matches_lirc_capture() -> None:
    """Test power is the 15-bit frame 0x540C from the RM-AAU014 LIRC capture."""
    timings = SonyReceiverCode.POWER.to_command().get_raw_timings()
    frame = timings[: len(timings) // SIRC_FRAMES_PER_COMMAND]
    bits = [1 if mark == 1200 else 0 for mark in frame[2:-1:2]]
    assert len(bits) == 15
    # LIRC writes the transmitted bits MSB first.
    assert int("".join(map(str, bits)), 2) == 0x540C
    assert sum(abs(value) for value in frame) == 45000
    assert timings == frame * SIRC_FRAMES_PER_COMMAND


@pytest.mark.parametrize(
    ("code", "lirc"),
    [
        (SonyReceiverCode.VOLUME_UP, 0x240C),
        (SonyReceiverCode.VOLUME_DOWN, 0x640C),
        (SonyReceiverCode.MUTE, 0x140C),
        (SonyReceiverCode.SA_CD_CD, 0x520C),
        (SonyReceiverCode.TUNER, 0x420C),
        (SonyReceiverCode.SAT_CATV, 0x600D),
        (SonyReceiverCode.MOVIE, 0x610D),
        (SonyReceiverCode.NAV_UP, 0x0F0D),
    ],
)
def test_codes_match_lirc_capture(code: SonyReceiverCode, lirc: int) -> None:
    """Test codes against the RM-AAU014 LIRC capture."""
    frame = code.to_command().get_raw_timings()[: 2 + 2 * 15]
    bits = [1 if mark == 1200 else 0 for mark in frame[2::2]]
    assert int("".join(map(str, bits)), 2) == lirc


def test_commands_match_library_encoder() -> None:
    """Test each frame is identical to the infrared-protocols encoder."""
    for code in SonyReceiverCode:
        address, address_bits, command = code.value
        single = SonyCommand(
            address=address, address_bits=address_bits, command=command
        ).get_raw_timings()
        assert code.to_command().get_raw_timings() == single * 3, code


@pytest.mark.parametrize("code", list(SonyReceiverCode))
def test_round_trip(code: SonyReceiverCode) -> None:
    """Test every code decodes back to itself."""
    frame = decode_sirc(code.to_command().get_raw_timings())
    assert frame == code.frame
    assert SonyReceiverCode.from_frame(frame) is code


@pytest.mark.parametrize(
    "timings",
    [[], [1, 2, 3, 4], [9000, -4500, 560, -560, 560], [2400, -600, 600, -20000]],
)
def test_decode_invalid(timings: list[int]) -> None:
    """Test non-SIRC signals are rejected."""
    assert decode_sirc(timings) is None


def test_decode_12_bit() -> None:
    """Test 12-bit frames (e.g. a Sony TV) are decoded."""
    timings = SonyCommand(address=1, address_bits=5, command=21).get_raw_timings()
    assert decode_sirc(timings) == SircFrame(1, 5, 21)
