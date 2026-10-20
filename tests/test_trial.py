"""
Unit tests for vmr.trial.TrialRunner — drives the whole trial lifecycle
with synthetic FrameInput sequences, no pygame or real display involved.

Flags:
    (none — run with pytest)

Usage:
    poetry run pytest tests/test_trial.py -v
"""

import math

import pytest

from vmr import geometry
from vmr.config import load_config
from vmr.geometry import GeometryParams
from vmr.schedule import TrialSpec
from vmr.trial import BOUNDARY, GOOD, HIT, TIMEOUT, TOO_FAST, TOO_SLOW, FrameInput, TrialPhase, TrialRunner

CFG = load_config()
GP = GeometryParams.from_config(CFG, px_per_cm=100.0, home_x_px=0.0, home_y_px=0.0)
DT = 0.01  # 10 ms per simulated frame


def make_spec(
    trial_type="baseline_veridical",
    target_angle_deg=0.0,
    rotation_deg=0.0,
    cursor_visible=True,
    needs_report=False,
):
    return TrialSpec(
        phase="test",
        trial_type=trial_type,
        trial_index=0,
        target_angle_deg=target_angle_deg,
        rotation_deg=rotation_deg,
        cursor_visible_during_movement=cursor_visible,
        needs_report=needs_report,
        show_instruction=False,
        instruction_key=None,
    )


def hold_at_home(runner: TrialRunner, t: float) -> float:
    """Feed frames at home until HOME_HOLD is satisfied. Returns updated t."""
    for _ in range(200):
        runner.step(FrameInput(t=t, raw_cursor_px=(0.0, 0.0)))
        t += DT
        if runner.phase is not TrialPhase.HOME_HOLD:
            return t
    raise AssertionError("home hold never satisfied")


def move_straight_to_target(runner: TrialRunner, t: float, duration_s: float) -> float:
    """Feed frames moving in a straight raw line toward the trial's target,
    reaching it at t = duration_s (a hit actually lands slightly before
    that, once the cursor first enters hit_radius of the target — that's
    what lets duration_s double as an approximate target movement time).
    Returns updated t."""
    return move_straight_to_target_generic(runner, t, runner.home_px, runner.target_pos_px, duration_s)


def run_end_feedback_to_done(runner: TrialRunner, t: float) -> float:
    for _ in range(200):
        runner.step(FrameInput(t=t, raw_cursor_px=runner.target_pos_px))
        t += DT
        if runner.phase is TrialPhase.DONE:
            return t
    raise AssertionError("end feedback never completed")


# ---------------------------------------------------------------------------
# Basic hit lifecycle
# ---------------------------------------------------------------------------


def test_hit_at_good_speed():
    spec = make_spec(target_angle_deg=0.0, rotation_deg=0.0)
    played = []
    runner = TrialRunner(spec, CFG, GP, play_sound=played.append)

    t = hold_at_home(runner, 0.0)
    assert runner.phase is TrialPhase.MOVING
    assert "go_beep" in played

    t = move_straight_to_target(runner, t, duration_s=0.5)  # 500 ms, inside [400,600]
    assert runner.phase is TrialPhase.END_FEEDBACK
    assert runner.end_reason == HIT
    assert runner.speed_feedback == GOOD
    assert "hit_bell" in played

    run_end_feedback_to_done(runner, t)
    assert runner.phase is TrialPhase.DONE
    assert runner.result is not None
    assert runner.result.end_reason == HIT
    assert runner.result.speed_feedback == GOOD
    assert runner.result.target_angle_deg == 0.0
    assert runner.result.movement_angle_at_50pct_reach == pytest.approx(0.0, abs=1.0)


def test_hit_too_fast():
    spec = make_spec()
    runner = TrialRunner(spec, CFG, GP)
    t = hold_at_home(runner, 0.0)
    move_straight_to_target(runner, t, duration_s=0.1)  # 100 ms < 400
    assert runner.end_reason == HIT
    assert runner.speed_feedback == TOO_FAST


def test_hit_too_slow():
    spec = make_spec()
    runner = TrialRunner(spec, CFG, GP)
    t = hold_at_home(runner, 0.0)
    move_straight_to_target(runner, t, duration_s=0.9)  # hit lands well past 600 ms
    assert runner.end_reason == HIT
    assert runner.speed_feedback == TOO_SLOW


# ---------------------------------------------------------------------------
# Boundary / timeout
# ---------------------------------------------------------------------------


def test_boundary_crossed_wrong_direction():
    spec = make_spec(target_angle_deg=0.0)
    runner = TrialRunner(spec, CFG, GP)
    t = hold_at_home(runner, 0.0)
    # move in the OPPOSITE direction from target -> crosses boundary, never hits
    for i in range(200):
        pos = (-i * 20.0, 0.0)
        runner.step(FrameInput(t=t, raw_cursor_px=pos))
        t += DT
        if runner.phase is TrialPhase.END_FEEDBACK:
            break
    assert runner.end_reason == BOUNDARY
    assert runner.speed_feedback is None
    assert runner.movement_time_ms is None


def test_timeout_when_never_leaving_home():
    spec = make_spec()
    runner = TrialRunner(spec, CFG, GP)
    t = hold_at_home(runner, 0.0)
    assert runner.phase is TrialPhase.MOVING
    # stay at home well past target_timeout_ms (2000 ms)
    for _ in range(400):
        runner.step(FrameInput(t=t, raw_cursor_px=(0.0, 0.0)))
        t += DT
        if runner.phase is TrialPhase.END_FEEDBACK:
            break
    assert runner.end_reason == TIMEOUT
    assert runner.movement_onset_timestamp is None
    assert runner.movement_time_ms is None


# ---------------------------------------------------------------------------
# Home-hold dwell logic
# ---------------------------------------------------------------------------


def test_leaving_home_resets_hold_timer():
    spec = make_spec()
    runner = TrialRunner(spec, CFG, GP)
    t = 0.0
    # hold for 300ms (not enough), then leave home, then return and hold full 500ms
    for _ in range(30):
        runner.step(FrameInput(t=t, raw_cursor_px=(0.0, 0.0)))
        t += DT
    assert runner.phase is TrialPhase.HOME_HOLD  # not yet satisfied at 300ms
    runner.step(FrameInput(t=t, raw_cursor_px=(1000.0, 0.0)))  # leave home
    t += DT
    assert runner._home_hold_start_t is None
    t = hold_at_home(runner, t)
    assert runner.phase is TrialPhase.MOVING


# ---------------------------------------------------------------------------
# Visuomotor rotation integration
# ---------------------------------------------------------------------------


def test_rotated_trial_requires_ccw_compensation_to_hit():
    """End-to-end check that TrialRunner's rotation handling matches
    geometry's convention: aiming straight at the target under a 60 deg CW
    rotation should NOT hit; aiming 60 deg CCW of target should."""
    spec_straight = make_spec(target_angle_deg=0.0, rotation_deg=60.0)
    runner = TrialRunner(spec_straight, CFG, GP)
    t = hold_at_home(runner, 0.0)
    # aim straight at the nominal target direction (uncompensated)
    home = runner.home_px
    target = runner.target_pos_px
    t2 = t
    ended = False
    for i in range(200):
        frac = min(1.0, i * DT / 0.5)
        pos = (home[0] + (target[0] - home[0]) * frac, home[1] + (target[1] - home[1]) * frac)
        runner.step(FrameInput(t=t2, raw_cursor_px=pos))
        t2 += DT
        if runner.phase is TrialPhase.END_FEEDBACK:
            ended = True
            break
    assert ended
    assert runner.end_reason == BOUNDARY  # never touches target while uncompensated


def test_rotated_trial_hits_with_compensation():
    spec = make_spec(target_angle_deg=0.0, rotation_deg=60.0)
    runner = TrialRunner(spec, CFG, GP)
    t = hold_at_home(runner, 0.0)
    home = runner.home_px
    compensatory_angle = 0.0 + 60.0  # CCW of target, per geometry convention
    raw_target = geometry.target_position_px(compensatory_angle, GP)
    t = move_straight_to_target_generic(runner, t, home, raw_target, duration_s=0.5)
    assert runner.end_reason == HIT


def move_straight_to_target_generic(runner, t, home, raw_target, duration_s):
    start_t = t
    for _ in range(int(duration_s / DT) + 100):
        frac = min(1.5, (t - start_t) / duration_s)
        pos = (home[0] + (raw_target[0] - home[0]) * frac, home[1] + (raw_target[1] - home[1]) * frac)
        runner.step(FrameInput(t=t, raw_cursor_px=pos))
        t += DT
        if runner.phase in (TrialPhase.END_FEEDBACK, TrialPhase.DONE):
            return t
    raise AssertionError("movement never ended")


# ---------------------------------------------------------------------------
# No-vision trials use RAW position for hit test, not display
# ---------------------------------------------------------------------------


def test_no_vision_hit_uses_raw_position():
    spec = make_spec(trial_type="baseline_no_vision", rotation_deg=None, cursor_visible=False)
    runner = TrialRunner(spec, CFG, GP)
    t = hold_at_home(runner, 0.0)
    t = move_straight_to_target(runner, t, duration_s=0.5)
    assert runner.end_reason == HIT
    # display was never computed (no cursor shown)
    assert all(s.display_x is None and s.display_y is None for s in runner.samples)


# ---------------------------------------------------------------------------
# Report-trial flow
# ---------------------------------------------------------------------------


def test_report_trial_waits_for_valid_confirm():
    spec = make_spec(trial_type="adaptation_report", rotation_deg=60.0, needs_report=True)
    runner = TrialRunner(spec, CFG, GP)
    t = hold_at_home(runner, 0.0)
    assert runner.phase is TrialPhase.REPORT_WAIT

    # SPACE with nothing entered yet: ignored
    runner.step(FrameInput(t=t, raw_cursor_px=(0.0, 0.0), space_pressed=True))
    t += DT
    assert runner.phase is TrialPhase.REPORT_WAIT
    assert runner.go_signal_timestamp is None

    # type "-11" as heard, then SPACE
    runner.step(FrameInput(t=t, raw_cursor_px=(0.0, 0.0), minus=True))
    t += DT
    runner.step(FrameInput(t=t, raw_cursor_px=(0.0, 0.0), digit=1))
    t += DT
    ready_t = t  # last keystroke before SPACE
    runner.step(FrameInput(t=t, raw_cursor_px=(0.0, 0.0), digit=1))
    t += DT
    runner.step(FrameInput(t=t, raw_cursor_px=(0.0, 0.0), space_pressed=True))
    t += DT

    assert runner.phase is TrialPhase.MOVING
    assert runner.reported.magnitude == 11
    assert runner.reported.side == "CCW"
    assert runner.report_registered_timestamp == pytest.approx(ready_t)
    assert runner.experimenter_space_timestamp is not None

    t = move_straight_to_target(runner, t, duration_s=0.5)
    run_end_feedback_to_done(runner, t)
    assert runner.result.reported_number == 11
    assert runner.result.reported_side == "CCW"
    # landmark -11 at target 0 deg -> target - (-11*5.625) = +61.875 deg
    assert runner.result.reported_angle_deg == pytest.approx(11 * CFG.landmarks.spacing_deg)
    assert runner.result.report_wait_max_drift_mm == pytest.approx(0.0)


def test_report_of_zero_needs_only_space():
    spec = make_spec(trial_type="adaptation_report", rotation_deg=60.0, needs_report=True)
    runner = TrialRunner(spec, CFG, GP)
    t = hold_at_home(runner, 0.0)

    runner.step(FrameInput(t=t, raw_cursor_px=(0.0, 0.0), digit=0))
    t += DT
    runner.step(FrameInput(t=t, raw_cursor_px=(0.0, 0.0), space_pressed=True))

    assert runner.phase is TrialPhase.MOVING
    assert runner.reported.magnitude == 0
    assert runner.reported.side is None


def test_drift_during_report_wait_is_reset_and_logged():
    """The cursor is hidden while the report is entered; if the finger
    drifts, SPACE puts the cursor back on home (to-decide.md #35) and the
    drift is logged for QC, without contaminating the reach angles."""
    spec = make_spec(trial_type="adaptation_report", rotation_deg=60.0, needs_report=True)
    resets = []
    runner = TrialRunner(spec, CFG, GP, reset_cursor=lambda: resets.append(True))
    t = hold_at_home(runner, 0.0)

    drifted = (0.0, 200.0)  # 2 cm straight down (px_per_cm = 100), well off home
    runner.step(FrameInput(t=t, raw_cursor_px=drifted, digit=5))
    t += DT
    runner.step(FrameInput(t=t, raw_cursor_px=drifted, space_pressed=True))
    t += DT

    assert resets == [True]
    assert runner.phase is TrialPhase.MOVING
    assert runner.displayed_pos == runner.home_px  # no one-frame flash at the drifted spot
    assert runner.movement_onset_timestamp is None  # still on home after the reset

    # the orchestrator's tracker is now back on home, so the reach starts there
    t = move_straight_to_target(runner, t, duration_s=0.5)
    run_end_feedback_to_done(runner, t)
    assert runner.result.report_wait_max_drift_mm == pytest.approx(20.0)
    assert runner.result.movement_angle_at_50pct_reach == pytest.approx(0.0, abs=1.0)


def test_non_report_trial_has_no_drift_value():
    runner = TrialRunner(make_spec(), CFG, GP)
    t = hold_at_home(runner, 0.0)
    t = move_straight_to_target(runner, t, duration_s=0.5)
    run_end_feedback_to_done(runner, t)
    assert runner.result.report_wait_max_drift_mm is None
