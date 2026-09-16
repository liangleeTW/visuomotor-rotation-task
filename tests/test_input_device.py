"""
Unit tests for vmr.input_device.

Flags:
    (none — run with pytest)

Usage:
    poetry run pytest tests/test_input_device.py -v
"""

import pytest

from vmr.input_device import CursorTracker, PygameRelativeMouse


# ---------------------------------------------------------------------------
# CursorTracker (pure)
# ---------------------------------------------------------------------------


def test_starts_at_home():
    tracker = CursorTracker(home_px=(100.0, 200.0))
    assert tracker.position == (100.0, 200.0)


def test_apply_delta_accumulates():
    tracker = CursorTracker(home_px=(0.0, 0.0))
    tracker.apply_delta(5.0, -3.0)
    tracker.apply_delta(2.0, 1.0)
    assert tracker.position == (7.0, -2.0)


def test_reset_to_home_discards_accumulated_position():
    tracker = CursorTracker(home_px=(50.0, 50.0))
    tracker.apply_delta(100.0, 100.0)
    assert tracker.position != (50.0, 50.0)
    result = tracker.reset_to_home()
    assert result == (50.0, 50.0)
    assert tracker.position == (50.0, 50.0)


# ---------------------------------------------------------------------------
# PygameRelativeMouse — driven with a fake pygame module (no real display
# needed, since the class takes the module as a constructor argument)
# ---------------------------------------------------------------------------


class _FakeMouse:
    def __init__(self):
        self.visible = True
        self._rel = (0, 0)
        self.get_rel_calls = 0

    def set_visible(self, flag):
        self.visible = flag

    def get_rel(self):
        self.get_rel_calls += 1
        return self._rel

    def set_pending_rel(self, dx, dy):
        self._rel = (dx, dy)


class _FakeEvent:
    def __init__(self):
        self.grabbed = False

    def set_grab(self, flag):
        self.grabbed = flag


class _FakePygame:
    def __init__(self):
        self.mouse = _FakeMouse()
        self.event = _FakeEvent()


@pytest.fixture
def fake_pygame():
    return _FakePygame()


def test_start_hides_cursor_and_grabs(fake_pygame):
    device = PygameRelativeMouse(pygame_module=fake_pygame)
    device.start()
    assert fake_pygame.mouse.visible is False
    assert fake_pygame.event.grabbed is True


def test_start_discards_pending_delta(fake_pygame):
    fake_pygame.mouse.set_pending_rel(999, 999)  # simulate pre-grab accumulated jump
    device = PygameRelativeMouse(pygame_module=fake_pygame)
    device.start()
    assert fake_pygame.mouse.get_rel_calls == 1  # discarded exactly once
    fake_pygame.mouse.set_pending_rel(3, 4)
    assert device.poll_delta() == (3, 4)


def test_stop_restores_cursor_and_ungrabs(fake_pygame):
    device = PygameRelativeMouse(pygame_module=fake_pygame)
    device.start()
    device.stop()
    assert fake_pygame.mouse.visible is True
    assert fake_pygame.event.grabbed is False


def test_poll_before_start_raises(fake_pygame):
    device = PygameRelativeMouse(pygame_module=fake_pygame)
    with pytest.raises(RuntimeError):
        device.poll_delta()


def test_context_manager(fake_pygame):
    with PygameRelativeMouse(pygame_module=fake_pygame) as device:
        assert fake_pygame.mouse.visible is False
        fake_pygame.mouse.set_pending_rel(1, 2)
        assert device.poll_delta() == (1, 2)
    assert fake_pygame.mouse.visible is True
