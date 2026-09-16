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
from vmr.menu import BLOCKS
from vmr.orchestration import FrameEvents, run_block, run_interactive_menu


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

    def __init__(self, delta=(50.0, 50.0), settle_polls=3):
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
    monkeypatch.setattr("vmr.orchestration.require_calibration", lambda: fake_calibration)

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

    assert trials_path.exists()
    assert samples_path.exists()
    assert schedule_path.exists()
    assert snapshot_path.exists()

    with open(trials_path) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["trial_type"] == "familiarization"
    assert rows[0]["end_reason"] == "boundary"  # diagonal path can't reach a cardinal target first

    with open(samples_path) as f:
        sample_rows = list(csv.DictReader(f))
    assert len(sample_rows) > 0


def test_run_interactive_menu_returns_selection_and_subject_id(monkeypatch):
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

    subject_id, block_name = run_interactive_menu(screen, clock=pygame.time.Clock())
    assert block_name == BLOCKS[1]  # one K_DOWN from the first option
    assert subject_id == "s01"
    pygame.quit()


def test_run_block_resumes_without_rerunning_completed_trials(tmp_path, monkeypatch):
    fake_calibration = Calibration(px_per_cm=50.0, measured_at="test", display_resolution=(400, 300))
    monkeypatch.setattr("vmr.orchestration.require_calibration", lambda: fake_calibration)

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
