"""
Unit tests for vmr.report_entry.

Flags:
    (none — run with pytest)

Usage:
    poetry run pytest tests/test_report_entry.py -v
"""

import pytest

from vmr.report_entry import ReportEntryState, Stage


def test_typical_entry_flow():
    r = ReportEntryState()
    r.input_digit(1)
    r.input_digit(2)
    assert r.magnitude == 12
    assert r.select_side("CCW") is True
    assert r.stage == Stage.MAGNITUDE_SET
    assert r.can_confirm()
    result = r.confirm()
    assert result.magnitude == 12
    assert result.side == "CCW"
    assert r.stage == Stage.CONFIRMED


def test_zero_magnitude_has_no_side():
    r = ReportEntryState()
    r.input_digit(0)
    assert r.select_side("CW") is True  # side key still needs pressing to advance stage
    assert r.side is None  # but magnitude 0 has no meaningful side
    result = r.confirm()
    assert result.magnitude == 0
    assert result.side is None


def test_cannot_confirm_before_side_selected():
    r = ReportEntryState()
    r.input_digit(5)
    assert not r.can_confirm()
    with pytest.raises(ValueError):
        r.confirm()


def test_cannot_select_side_before_any_digit():
    r = ReportEntryState()
    assert r.select_side("CW") is False


def test_out_of_range_magnitude_rejected_at_confirm():
    r = ReportEntryState(magnitude_range=(0, 31))
    r.input_digit(4)
    r.input_digit(5)  # 45, out of range
    r.select_side("CW")
    assert not r.can_confirm()
    with pytest.raises(ValueError):
        r.confirm()


def test_max_two_digits():
    r = ReportEntryState()
    r.input_digit(3)
    r.input_digit(1)
    r.input_digit(9)  # ignored, already 2 digits
    assert r.magnitude == 31


def test_backspace_undoes_side_first_then_digit():
    r = ReportEntryState()
    r.input_digit(2)
    r.input_digit(0)
    r.select_side("CW")
    assert r.stage == Stage.MAGNITUDE_SET
    r.backspace()
    assert r.stage == Stage.ENTERING_MAGNITUDE
    assert r.magnitude == 20  # digits untouched by the side-undo
    r.backspace()
    assert r.magnitude == 2


def test_reset_clears_everything():
    r = ReportEntryState()
    r.input_digit(9)
    r.select_side("CCW")
    r.confirm()
    r.reset()
    assert r.magnitude is None
    assert r.side is None
    assert r.stage == Stage.ENTERING_MAGNITUDE


def test_invalid_digit_raises():
    r = ReportEntryState()
    with pytest.raises(ValueError):
        r.input_digit(10)


def test_invalid_side_raises():
    r = ReportEntryState()
    r.input_digit(1)
    with pytest.raises(ValueError):
        r.select_side("left")


def test_no_input_after_confirmed():
    r = ReportEntryState()
    r.input_digit(1)
    r.select_side("CW")
    r.confirm()
    r.input_digit(5)  # no-op, stage is CONFIRMED
    assert r.magnitude == 1
