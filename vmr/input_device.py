"""
Trackpad input handling: relative-delta cursor tracking, decoupled from
pygame so the accumulation logic is unit-testable on its own.

Flags:
    (none — this module is imported, not run directly)

Usage:
    poetry run pytest tests/test_input_device.py -v
"""

from __future__ import annotations


class CursorTracker:
    """Accumulates relative mouse deltas into an absolute pixel position.

    Using relative deltas (rather than the OS cursor's absolute position)
    is what lets the participant lift their finger and re-place it on the
    trackpad between trials without any edge-clipping or discontinuity —
    see caution.md and to-decide.md #8.
    """

    def __init__(self, home_px: tuple[float, float]):
        self._home_px = home_px
        self.position = home_px

    def reset_to_home(self) -> tuple[float, float]:
        """Snap the tracked cursor back to home (to-decide.md #8: happens
        at the start of every trial)."""
        self.position = self._home_px
        return self.position

    def apply_delta(self, dx: float, dy: float) -> tuple[float, float]:
        x, y = self.position
        self.position = (x + dx, y + dy)
        return self.position


class PygameRelativeMouse:
    """Thin wrapper around pygame's relative-mouse mode.

    Hides the OS cursor and grabs input so pygame reports motion as
    relative deltas rather than absolute window coordinates (avoids the
    screen-edge clipping problem described in caution.md). The first
    delta after (re-)grabbing can contain a spurious accumulated jump, so
    callers should discard one poll immediately after start().
    """

    def __init__(self, pygame_module=None):
        # pygame is passed in (rather than imported at module scope) so
        # this class can be imported/tested even where pygame's video
        # subsystem isn't usable; production code passes the real module.
        if pygame_module is None:
            import pygame as pygame_module  # noqa: PLC0415
        self._pg = pygame_module
        self._active = False

    def start(self) -> None:
        self._pg.mouse.set_visible(False)
        self._pg.event.set_grab(True)
        self._pg.mouse.get_rel()  # discard any pre-grab accumulated delta
        self._active = True

    def stop(self) -> None:
        self._pg.event.set_grab(False)
        self._pg.mouse.set_visible(True)
        self._active = False

    def poll_delta(self) -> tuple[int, int]:
        if not self._active:
            raise RuntimeError("PygameRelativeMouse.start() must be called before polling")
        return self._pg.mouse.get_rel()

    def __enter__(self) -> "PygameRelativeMouse":
        self.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self.stop()
