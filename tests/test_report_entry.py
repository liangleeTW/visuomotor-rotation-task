"""
Unit tests for vmr.report_entry.

Flags:
    (none — run with pytest)

Usage:
    poetry run pytest tests/test_report_entry.py -v
"""

import pytest

from vmr.report_entry import ReportEntryState, ReportResult, Stage


def type_text(r: ReportEntryState, text: str) -> None:
    for ch in text:
        if ch == "-":
            r.input_minus()
        else:
            r.input_digit(int(ch))


def test_positive_number_is_clockwise():
    r = ReportEntryState()
    type_text(r, "12")
    assert r.text == "12"
    assert r.can_confirm()
    assert r.confirm() == ReportResult(magnitude=12, side="CW")
    assert r.stage == Stage.CONFIRMED


def test_negative_number_is_counterclockwise():
    r = ReportEntryState()
    type_text(r, "-10")
    assert r.text == "-10"
    assert r.confirm() == ReportResult(magnitude=10, side="CCW")


@pytest.mark.parametrize("text", ["0", "-0", "00"])
def test_zero_has_no_side(text):
    r = ReportEntryState()
    type_text(r, text)
    assert r.confirm() == ReportResult(magnitude=0, side=None)


def test_minus_ignored_after_digits():
    r = ReportEntryState()
    type_text(r, "5-")
    assert r.text == "5"
    assert r.confirm().side == "CW"


def test_cannot_confirm_before_any_digit():
    r = ReportEntryState()
    assert not r.can_confirm()
    r.input_minus()
    assert not r.can_confirm()
    with pytest.raises(ValueError):
        r.confirm()


def test_out_of_range_magnitude_rejected_at_confirm():
    r = ReportEntryState(magnitude_range=(0, 31))
    type_text(r, "-45")
    assert not r.can_confirm()
    with pytest.raises(ValueError):
        r.confirm()


def test_max_two_digits():
    r = ReportEntryState()
    type_text(r, "319")  # third digit ignored
    assert r.magnitude == 31


def test_backspace_deletes_digits_then_minus():
    r = ReportEntryState()
    type_text(r, "-20")
    r.backspace()
    assert r.text == "-2"
    r.backspace()
    assert r.text == "-"
    r.backspace()
    assert r.text == ""
    assert not r.negative


def test_reset_clears_everything():
    r = ReportEntryState()
    type_text(r, "-9")
    r.confirm()
    r.reset()
    assert r.text == ""
    assert r.side is None
    assert r.stage == Stage.ENTERING


def test_invalid_digit_raises():
    r = ReportEntryState()
    with pytest.raises(ValueError):
        r.input_digit(10)


def test_no_input_after_confirmed():
    r = ReportEntryState()
    type_text(r, "1")
    r.confirm()
    r.input_digit(5)
    r.input_minus()
    r.backspace()
    assert r.text == "1"
