"""
Experimenter-facing report-entry state machine (to-decide.md #14).

The experimenter types the spoken landmark number exactly as heard, sign
included ("minus 10" -> `-` `1` `0`, "10" -> `1` `0`), then SPACE confirms.
The sign maps onto the ring's own labels (negative = counterclockwise,
positive = clockwise), so the experimenter never has to work out a
direction from the target's position on screen.

This module is pure logic — no keyboard polling, no rendering — so the
trial state machine and the display layer can each drive/observe it
independently and it can be fully unit tested.

Flags:
    (none — this module is imported, not run directly)

Usage:
    poetry run pytest tests/test_report_entry.py -v
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class Stage(Enum):
    ENTERING = auto()
    CONFIRMED = auto()


@dataclass(frozen=True)
class ReportResult:
    magnitude: int
    side: str | None  # "CW" (positive) | "CCW" (negative) | None (only when magnitude == 0)


class ReportEntryState:
    """Tracks one trial's worth of experimenter report entry.

    magnitude_range is inclusive, e.g. (0, 31); it bounds the number
    without its sign.
    """

    def __init__(self, magnitude_range: tuple[int, int] = (0, 31)):
        self.magnitude_range = magnitude_range
        self._negative = False
        self._digits = ""
        self.stage = Stage.ENTERING

    def reset(self) -> None:
        self._negative = False
        self._digits = ""
        self.stage = Stage.ENTERING

    @property
    def magnitude(self) -> int | None:
        return int(self._digits) if self._digits else None

    @property
    def negative(self) -> bool:
        return self._negative

    @property
    def side(self) -> str | None:
        if not self.magnitude:
            return None
        return "CCW" if self._negative else "CW"

    @property
    def text(self) -> str:
        """What the experimenter has typed so far, e.g. "-1" or "12"."""
        return ("-" if self._negative else "") + self._digits

    def input_minus(self) -> None:
        """Mark the number as negative. Only accepted before any digit,
        the order in which the number is spoken ("minus 10")."""
        if self.stage != Stage.ENTERING or self._digits:
            return
        self._negative = True

    def input_digit(self, digit: int) -> None:
        """Append a digit (0-9). No-op once confirmed, or once 2 digits are
        already entered (31 is the largest valid magnitude)."""
        if self.stage != Stage.ENTERING:
            return
        if not (0 <= digit <= 9):
            raise ValueError(f"digit must be 0-9, got {digit!r}")
        if len(self._digits) >= 2:
            return
        self._digits += str(digit)

    def backspace(self) -> None:
        """Delete the last typed character: a digit, or the minus sign once
        no digits are left."""
        if self.stage != Stage.ENTERING:
            return
        if self._digits:
            self._digits = self._digits[:-1]
        else:
            self._negative = False

    def can_confirm(self) -> bool:
        if self.stage != Stage.ENTERING or not self._digits:
            return False
        lo, hi = self.magnitude_range
        return lo <= int(self._digits) <= hi

    def confirm(self) -> ReportResult:
        if not self.can_confirm():
            raise ValueError(f"report entry is not ready to confirm: stage={self.stage}, text={self.text!r}")
        result = ReportResult(magnitude=int(self._digits), side=self.side)
        self.stage = Stage.CONFIRMED
        return result
