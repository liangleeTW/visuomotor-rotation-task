"""
Integration smoke test for vmr.orchestration.run_block(): actually runs
pygame (headless, dummy drivers) through one full trial end-to-end —
menu-less block run, instruction screen, hold, move, feedback, ITI,
CSV logging — with input polling and the mouse device both injected so
the test is deterministic and fast, not a real interactive session.

This does not replace the pilot self-run (todo.md section 13); it only
proves the modules actually wire together correctly.

Flags:
    (none — run with pytest)

Usage:
    poetry run pytest tests/test_orchestration.py -v
"""

import csv
import dataclasses

import pygame
import pytest

from vmr.config import load_config
from vmr.display_calibration import Calibration
from vmr.menu import BLOCKS, ExistingDataStatus
from vmr.orchestration import (
    FrameEvents,
    QuitRequested,
    _resolution_matches,
    resolve_display_index,
    run_block,
    run_interactive_menu,
    wait_for_duplicate_choice,
)


def make_fast_test_config():
    """A copy of the real config with near-zero timing and a single
    familiarization trial, so the integration test runs in well under a
    second instead of minutes."""
    cfg = load_config()
    fast_timing = dataclasses.replace(
        cfg.timing,
        home_hold_ms=10,
        target_timeout_ms=1000,  # generous: the fake mouse "settles" for a
        # few polls before moving, and that settling time counts against
        # this budget too (real time keeps passing regardless of phase)
        end_feedback_duration_ms=10,
        inter_trial_interval_ms=10,
    )
    fast_counts = dataclasses.replace(cfg.trial_counts, familiarization=1)
    return dataclasses.replace(cfg, timing=fast_timing, trial_counts=fast_counts)


class FakeMouse:
    """Stays put for the first `settle_polls` calls (long enough for
    HOME_HOLD to be satisfied — moving immediately would mean the cursor
    never registers as "inside home", hanging the trial forever), then
    reports a constant diagonal delta every call after that. The diagonal
    guarantees the raw cursor crosses the workspace boundary quickly
    regardless of which of the 4 cardinal targets was randomly assigned,
    without the fake needing to know the target position."""

    def __init__(self, delta=(50.0, 50.0), settle_polls=10):
        self.delta = delta
        self.settle_polls = settle_polls
        self._calls = 0
        self.started = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def poll_delta(self):
        self._calls += 1
        if self._calls <= self.settle_polls:
            return (0.0, 0.0)
        return self.delta


def always_space(cfg) -> FrameEvents:
    return FrameEvents(space_pressed=True)


def test_run_block_familiarization_end_to_end(tmp_path, monkeypatch):
    fake_calibration = Calibration(px_per_cm=50.0, measured_at="test", display_resolution=(400, 300))
    monkeypatch.setattr("vmr.orchestration.resolve_calibration", lambda screen_resolution_px: fake_calibration)

    cfg = make_fast_test_config()
    schedule = run_block(
        subject_id="TEST01",
        block_name="familiarization",
        cfg=cfg,
        seed=1,
        data_dir=tmp_path,
        windowed_size=(400, 300),
        poll_events=always_space,
        mouse_factory=lambda: FakeMouse(),
    )
    assert len(schedule.by_phase("familiarization")) == 1

    trials_path = tmp_path / "TEST01" / "familiarization" / "trials.csv"
    samples_path = tmp_path / "TEST01" / "familiarization" / "samples.csv"
    schedule_path = tmp_path / "TEST01" / "familiarization" / "schedule.csv"
    snapshot_path = tmp_path / "TEST01" / "familiarization" / "config_snapshot.yaml"
    calibration_path = tmp_path / "TEST01" / "familiarization" / "calibration_used.json"

    assert trials_path.exists()
    assert samples_path.exists()
    assert schedule_path.exists()
    assert snapshot_path.exists()
    assert calibration_path.exists()

    with open(trials_path) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["trial_type"] == "familiarization"
    assert rows[0]["end_reason"] == "boundary"  # diagonal path can't reach a cardinal target first

    with open(samples_path) as f:
        sample_rows = list(csv.DictReader(f))
    assert len(sample_rows) > 0


def test_run_interactive_menu_returns_selection_and_subject_id(monkeypatch, tmp_path):
    pygame.init()
    pygame.font.init()
    screen = pygame.display.set_mode((400, 300))

    # each pygame.event.get() call returns the next scripted batch, so the
    # two phases (block selection, then subject-ID entry) can't bleed into
    # each other the way posting everything into one real queue would
    scripted_batches = iter(
        [
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN, unicode="")],
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="")],
            [
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_s, unicode="s"),
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_0, unicode="0"),
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1, unicode="1"),
            ],
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="")],
        ]
    )
    monkeypatch.setattr(pygame.event, "get", lambda: next(scripted_batches, []))

    subject_id, block_name = run_interactive_menu(screen, clock=pygame.time.Clock(), data_dir=tmp_path)
    assert block_name == BLOCKS[1]  # one K_DOWN from the first option
    assert subject_id == "s01"
    pygame.quit()


def test_run_interactive_menu_strips_whitespace_from_subject_id(monkeypatch, tmp_path):
    """to-decide.md #33: leading/trailing whitespace is stripped, and a
    whitespace-only entry doesn't count as confirmed."""
    pygame.init()
    pygame.font.init()
    screen = pygame.display.set_mode((400, 300))

    scripted_batches = iter(
        [
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="")],  # pick BLOCKS[0]
            # a leading space, then "S01", then a trailing space, then Enter
            [
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, unicode=" "),
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_s, unicode="S"),
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_0, unicode="0"),
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1, unicode="1"),
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, unicode=" "),
            ],
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="")],
        ]
    )
    monkeypatch.setattr(pygame.event, "get", lambda: next(scripted_batches, []))

    subject_id, block_name = run_interactive_menu(screen, clock=pygame.time.Clock(), data_dir=tmp_path)
    assert subject_id == "S01"  # not " S01 ", and case preserved
    assert block_name == BLOCKS[0]
    pygame.quit()


def test_run_interactive_menu_warns_on_duplicate_and_retry_lets_you_pick_a_new_id(monkeypatch, tmp_path):
    """to-decide.md #32: an ID that already has trials logged must be
    confirmed, not silently resumed or silently rejected."""
    pygame.init()
    pygame.font.init()
    screen = pygame.display.set_mode((400, 300))

    # Pre-populate S01/familiarization with one logged trial.
    from vmr.menu import session_paths

    paths = session_paths(tmp_path, "S01", BLOCKS[0])
    paths.trials_csv.parent.mkdir(parents=True)
    paths.trials_csv.write_text("a,b\n1,2\n")

    scripted_batches = iter(
        [
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="")],  # pick BLOCKS[0]
            [  # type "S01", confirm -> triggers the duplicate warning
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_s, unicode="S"),
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_0, unicode="0"),
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1, unicode="1"),
            ],
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="")],
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_n, unicode="n")],  # "different ID" choice
            [  # type "S02", confirm -> no existing data, returns immediately
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_s, unicode="S"),
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_0, unicode="0"),
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_2, unicode="2"),
            ],
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="")],
        ]
    )
    monkeypatch.setattr(pygame.event, "get", lambda: next(scripted_batches, []))

    subject_id, block_name = run_interactive_menu(screen, clock=pygame.time.Clock(), data_dir=tmp_path)
    assert subject_id == "S02"
    assert block_name == BLOCKS[0]
    pygame.quit()


def test_run_interactive_menu_duplicate_resume_choice_keeps_same_id(monkeypatch, tmp_path):
    pygame.init()
    pygame.font.init()
    screen = pygame.display.set_mode((400, 300))

    from vmr.menu import session_paths

    paths = session_paths(tmp_path, "S01", BLOCKS[0])
    paths.trials_csv.parent.mkdir(parents=True)
    paths.trials_csv.write_text("a,b\n1,2\n")

    scripted_batches = iter(
        [
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="")],  # pick BLOCKS[0]
            [
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_s, unicode="S"),
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_0, unicode="0"),
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1, unicode="1"),
            ],
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="")],
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r, unicode="r")],  # "resume" choice
        ]
    )
    monkeypatch.setattr(pygame.event, "get", lambda: next(scripted_batches, []))

    subject_id, block_name = run_interactive_menu(screen, clock=pygame.time.Clock(), data_dir=tmp_path)
    assert subject_id == "S01"
    assert block_name == BLOCKS[0]
    pygame.quit()


def test_wait_for_duplicate_choice_escape_raises_quit(monkeypatch):
    pygame.init()
    pygame.font.init()
    screen = pygame.display.set_mode((400, 300))
    font = pygame.font.SysFont(None, 32)
    monkeypatch.setattr(
        pygame.event, "get", lambda: [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode="")]
    )
    status = ExistingDataStatus(n_trials=3, last_modified="2026-01-01 00:00")
    with pytest.raises(QuitRequested):
        wait_for_duplicate_choice(screen, font, pygame.time.Clock(), "S01", BLOCKS[0], status)
    pygame.quit()


# ---------------------------------------------------------------------------
# resolve_display_index / _resolution_matches (to-decide.md #31)
# ---------------------------------------------------------------------------


class _FakeDisplayModule:
    def __init__(self, num_displays, sizes):
        self._num = num_displays
        self._sizes = sizes

    def get_num_displays(self):
        return self._num

    def get_desktop_sizes(self):
        return self._sizes


class _FakePygameForDisplay:
    def __init__(self, num_displays, sizes):
        self.display = _FakeDisplayModule(num_displays, sizes)


class _FakeQuartzForDisplay:
    def __init__(self, width_px, height_px, raise_error=False):
        self.width_px = width_px
        self.height_px = height_px
        self.raise_error = raise_error

    def CGMainDisplayID(self):
        if self.raise_error:
            raise RuntimeError("no display")
        return 1

    def CGDisplayPixelsWide(self, display_id):
        return self.width_px

    def CGDisplayPixelsHigh(self, display_id):
        return self.height_px


def test_resolution_matches_exact():
    assert _resolution_matches((1920, 1080), (1920, 1080))


def test_resolution_matches_2x_scale():
    assert _resolution_matches((1512, 982), (3024, 1964))  # points vs. backing pixels
    assert _resolution_matches((3024, 1964), (1512, 982))


def test_resolution_matches_false_when_unrelated():
    assert not _resolution_matches((1920, 1080), (1512, 982))


def test_resolve_display_index_single_display_skips_quartz_entirely():
    pg = _FakePygameForDisplay(num_displays=1, sizes=[(1512, 982)])
    quartz = _FakeQuartzForDisplay(width_px=0, height_px=0, raise_error=True)  # would blow up if ever called
    assert resolve_display_index(quartz_module=quartz, pygame_module=pg) == 0


def test_resolve_display_index_matches_main_display_by_resolution():
    # this is the exact scenario that was broken: main display is the
    # SECOND entry in pygame's enumeration, not index 0
    pg = _FakePygameForDisplay(num_displays=2, sizes=[(1512, 982), (1920, 1080)])
    quartz = _FakeQuartzForDisplay(width_px=1920, height_px=1080)
    assert resolve_display_index(quartz_module=quartz, pygame_module=pg) == 1


def test_resolve_display_index_falls_back_to_zero_when_no_match(recwarn):
    pg = _FakePygameForDisplay(num_displays=2, sizes=[(1512, 982), (1920, 1080)])
    quartz = _FakeQuartzForDisplay(width_px=2560, height_px=1440)  # matches neither
    assert resolve_display_index(quartz_module=quartz, pygame_module=pg) == 0
    assert any("no display matches" in str(w.message) for w in recwarn.list)


def test_resolve_display_index_falls_back_to_zero_when_ambiguous(recwarn):
    pg = _FakePygameForDisplay(num_displays=2, sizes=[(1920, 1080), (1920, 1080)])
    quartz = _FakeQuartzForDisplay(width_px=1920, height_px=1080)
    assert resolve_display_index(quartz_module=quartz, pygame_module=pg) == 0
    assert any("multiple displays match" in str(w.message) for w in recwarn.list)


def test_resolve_display_index_falls_back_to_zero_when_detection_fails(recwarn):
    pg = _FakePygameForDisplay(num_displays=2, sizes=[(1512, 982), (1920, 1080)])
    quartz = _FakeQuartzForDisplay(width_px=0, height_px=0, raise_error=True)
    assert resolve_display_index(quartz_module=quartz, pygame_module=pg) == 0
    assert any("could not determine the main display" in str(w.message) for w in recwarn.list)


def test_run_block_resumes_without_rerunning_completed_trials(tmp_path, monkeypatch):
    fake_calibration = Calibration(px_per_cm=50.0, measured_at="test", display_resolution=(400, 300))
    monkeypatch.setattr("vmr.orchestration.resolve_calibration", lambda screen_resolution_px: fake_calibration)

    cfg = load_config()
    cfg = dataclasses.replace(
        cfg,
        timing=dataclasses.replace(cfg.timing, home_hold_ms=10, target_timeout_ms=1000, end_feedback_duration_ms=10, inter_trial_interval_ms=10),
        trial_counts=dataclasses.replace(cfg.trial_counts, familiarization=2),
    )

    common_kwargs = dict(
        subject_id="TEST02",
        block_name="familiarization",
        cfg=cfg,
        seed=7,
        data_dir=tmp_path,
        windowed_size=(400, 300),
        poll_events=always_space,
        mouse_factory=lambda: FakeMouse(),
    )

    # Run once, but simulate a crash after 1 trial by monkeypatching the
    # trial count down to 1 for this call only, matching how a real
    # resumed session would find a partially-completed block on disk.
    partial_cfg = dataclasses.replace(cfg, trial_counts=dataclasses.replace(cfg.trial_counts, familiarization=1))
    run_block(**{**common_kwargs, "cfg": partial_cfg})

    trials_path = tmp_path / "TEST02" / "familiarization" / "trials.csv"
    with open(trials_path) as f:
        assert len(list(csv.DictReader(f))) == 1

    # Resume with the full 2-trial schedule (same seed): only the missing
    # trial should be appended, not a duplicate of trial 0.
    run_block(**common_kwargs)
    with open(trials_path) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert [r["trial_index"] for r in rows] == ["0", "1"]


# ---------------------------------------------------------------------------
# main() CLI-path duplicate-ID confirmation (to-decide.md #32)
# ---------------------------------------------------------------------------


def test_main_cli_path_cancels_on_no_without_calling_run_block(tmp_path, monkeypatch):
    from vmr.menu import session_paths
    from vmr.orchestration import main

    paths = session_paths(tmp_path, "S01", "familiarization")
    paths.trials_csv.parent.mkdir(parents=True)
    paths.trials_csv.write_text("a,b\n1,2\n")

    called = []
    monkeypatch.setattr("vmr.orchestration.run_block", lambda **kwargs: called.append(kwargs))
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    monkeypatch.setattr(
        "sys.argv", ["run_block.py", "--subject", "S01", "--block", "familiarization", "--data-dir", str(tmp_path)]
    )

    main()
    assert called == []  # run_block must never have been invoked


def test_main_cli_path_proceeds_on_yes_flag_without_prompting(tmp_path, monkeypatch):
    from vmr.menu import session_paths
    from vmr.orchestration import main

    paths = session_paths(tmp_path, "S01", "familiarization")
    paths.trials_csv.parent.mkdir(parents=True)
    paths.trials_csv.write_text("a,b\n1,2\n")

    called = []

    def fake_input(prompt=""):
        raise AssertionError("input() should not be called when --yes is passed")

    monkeypatch.setattr("vmr.orchestration.run_block", lambda **kwargs: called.append(kwargs))
    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr(
        "sys.argv",
        ["run_block.py", "--subject", "S01", "--block", "familiarization", "--data-dir", str(tmp_path), "--yes"],
    )

    main()
    assert len(called) == 1
    assert called[0]["subject_id"] == "S01"


def test_main_cli_path_normalizes_whitespace_in_subject_flag(tmp_path, monkeypatch):
    from vmr.orchestration import main

    called = []
    monkeypatch.setattr("vmr.orchestration.run_block", lambda **kwargs: called.append(kwargs))
    monkeypatch.setattr(
        "sys.argv", ["run_block.py", "--subject", "  S01  ", "--block", "familiarization", "--data-dir", str(tmp_path)]
    )

    main()
    assert len(called) == 1
    assert called[0]["subject_id"] == "S01"


@pytest.mark.parametrize("key", [pygame.K_7, pygame.K_KP7])
def test_top_row_and_keypad_digits_both_register(monkeypatch, key):
    from vmr.orchestration import poll_pygame_events

    monkeypatch.setattr(pygame.event, "get", lambda: [pygame.event.Event(pygame.KEYDOWN, key=key, unicode="7")])
    assert poll_pygame_events(load_config()).digit == 7


@pytest.mark.parametrize("key", [pygame.K_MINUS, pygame.K_KP_MINUS])
def test_main_and_keypad_minus_both_register(monkeypatch, key):
    from vmr.orchestration import poll_pygame_events

    monkeypatch.setattr(pygame.event, "get", lambda: [pygame.event.Event(pygame.KEYDOWN, key=key, unicode="-")])
    assert poll_pygame_events(load_config()).minus is True


class StrayMovementMouse(FakeMouse):
    """Reports a large delta on its first poll — finger movement that
    accumulated while the instruction screen / ITI was showing."""

    def poll_delta(self):
        if self._calls == 0:
            self._calls += 1
            return (300.0, 300.0)
        return super().poll_delta()


def test_movement_between_trials_is_discarded(tmp_path, monkeypatch):
    fake_calibration = Calibration(px_per_cm=50.0, measured_at="test", display_resolution=(400, 300))
    monkeypatch.setattr("vmr.orchestration.resolve_calibration", lambda screen_resolution_px: fake_calibration)

    run_block(
        subject_id="TEST01",
        block_name="familiarization",
        cfg=make_fast_test_config(),
        seed=1,
        data_dir=tmp_path,
        windowed_size=(400, 300),
        poll_events=always_space,
        mouse_factory=lambda: StrayMovementMouse(),
    )
    with open(tmp_path / "TEST01" / "familiarization" / "samples.csv") as f:
        first = next(csv.DictReader(f))
    assert float(first["raw_x"]) == pytest.approx(200.0)  # home = window centre
    assert float(first["raw_y"]) == pytest.approx(150.0)
