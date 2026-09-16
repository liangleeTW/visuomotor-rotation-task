"""
Experimenter-facing report-entry state machine (to-decide.md #14).

The experimenter types the spoken landmark magnitude (digits), presses a
side key, then SPACE confirms. This module is pure logic — no keyboard
polling, no rendering — so the trial state machine and the display layer
can each drive/observe it independently and it can be fully unit tested.

Flags:
    (none — this module is imported, not run directly)

Usage:
    poetry run pytest tests/test_report_entry.py -v
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class Stage(Enum):
    ENTERING_MAGNITUDE = auto()
    MAGNITUDE_SET = auto()  # side chosen (or magnitude is 0, side moot); ready to confirm
    CONFIRMED = auto()


@dataclass(frozen=True)
class ReportResult:
    magnitude: int
    side: str | None  # "CW" | "CCW" | None (only None when magnitude == 0)


class ReportEntryState:
    """Tracks one trial's worth of experimenter report entry.

    magnitude_range is inclusive, e.g. (0, 31).
    """

    def __init__(self, magnitude_range: tuple[int, int] = (0, 31)):
        self.magnitude_range = magnitude_range
        self._digits = ""
        self._side: str | None = None
        self.stage = Stage.ENTERING_MAGNITUDE

    def reset(self) -> None:
        self._digits = ""
        self._side = None
        self.stage = Stage.ENTERING_MAGNITUDE

    @property
    def magnitude(self) -> int | None:
        return int(self._digits) if self._digits else None

    @property
    def side(self) -> str | None:
        return self._side

    def input_digit(self, digit: int) -> None:
        """Append a digit (0-9) to the magnitude buffer. No-op once past
        the magnitude-entry stage, or once 2 digits are already entered
        (31 is the largest valid magnitude, so 2 digits is always enough)."""
        if self.stage != Stage.ENTERING_MAGNITUDE:
            return
        if not (0 <= digit <= 9):
            raise ValueError(f"digit must be 0-9, got {digit!r}")
        if len(self._digits) >= 2:
            return
        self._digits += str(digit)

    def backspace(self) -> None:
        """Step backward one input: undo the side selection if one was
        made, otherwise delete the last digit."""
        if self.stage == Stage.MAGNITUDE_SET:
            self._side = None
            self.stage = Stage.ENTERING_MAGNITUDE
            return
        if self.stage == Stage.ENTERING_MAGNITUDE and self._digits:
            self._digits = self._digits[:-1]

    def select_side(self, side: str) -> bool:
        """Finalize the magnitude and record a side. Returns False (no-op)
        if no magnitude has been entered yet or a side was already picked."""
        if side not in ("CW", "CCW"):
            raise ValueError(f"side must be 'CW' or 'CCW', got {side!r}")
        if self.stage != Stage.ENTERING_MAGNITUDE or not self._digits:
            return False
        magnitude = int(self._digits)
        self._side = None if magnitude == 0 else side
        self.stage = Stage.MAGNITUDE_SET
        return True

    def can_confirm(self) -> bool:
        if self.stage != Stage.MAGNITUDE_SET:
            return False
        lo, hi = self.magnitude_range
        return lo <= int(self._digits) <= hi

    def confirm(self) -> ReportResult:
        if not self.can_confirm():
            raise ValueError(
                "report entry is not ready to confirm: "
                f"stage={self.stage}, digits={self._digits!r}, side={self._side!r}"
            )
        result = ReportResult(magnitude=int(self._digits), side=self._side)
        self.stage = Stage.CONFIRMED
        return result
