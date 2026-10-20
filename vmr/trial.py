"""
The single generic trial state machine that drives every trial type
(familiarization, baseline, adaptation, post-adaptation) — parameterized
by a schedule.TrialSpec's flags rather than one class per trial type.

TrialRunner is a pure "stepper": the caller (the pygame main loop) feeds
it one FrameInput per iteration (current time, raw cursor position, and
any keys pressed this frame) and reads back .phase / .result. No pygame
or wall-clock access happens inside this module, which is what makes the
whole lifecycle unit-testable with synthetic input sequences (see
tests/test_trial.py) before any display code exists.

Flow:
    HOME_HOLD -> [REPORT_WAIT -> ] MOVING -> END_FEEDBACK -> DONE

The cursor is hidden during REPORT_WAIT, so any drift then is invisible to
the participant. On SPACE the runner calls reset_cursor() to put the
cursor back on home before the reach (to-decide.md #35), and logs the
largest drift as report_wait_max_drift_mm for QC. Reach-angle measures use
only samples from the go signal onward.

Flags:
    (none — this module is imported, not run directly)

Usage:
    poetry run pytest tests/test_trial.py -v
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable

from vmr import geometry
from vmr.config import Config
from vmr.geometry import GeometryParams, Point
from vmr.report_entry import ReportEntryState
from vmr.schedule import TrialSpec

# Taylor, Krakauer & Ivry (2014)'s initial-segment heading-angle measure.
_INITIAL_SEGMENT_R1_CM = 1.0
_INITIAL_SEGMENT_R2_CM = 3.0

HIT = "hit"
BOUNDARY = "boundary"
TIMEOUT = "timeout"

GOOD = "good"
TOO_FAST = "too_fast"
TOO_SLOW = "too_slow"


class TrialPhase(Enum):
    HOME_HOLD = auto()
    REPORT_WAIT = auto()
    MOVING = auto()
    END_FEEDBACK = auto()
    DONE = auto()


@dataclass(frozen=True)
class FrameInput:
    t: float
    raw_cursor_px: Point
    space_pressed: bool = False
    digit: int | None = None
    minus: bool = False
    backspace: bool = False


@dataclass(frozen=True)
class SampleRecord:
    sample_timestamp: float
    raw_x: float
    raw_y: float
    display_x: float | None
    display_y: float | None


@dataclass
class TrialResult:
    phase: str
    trial_type: str
    trial_index: int
    cycle_index: int | None
    probe_index: int | None
    target_id: int
    target_angle_deg: float
    target_x: float
    target_y: float
    rotation_deg: float | None
    cursor_visible_during_movement: bool
    reported_number: int | None
    reported_side: str | None
    reported_angle_deg: float | None
    report_registered_timestamp: float | None
    experimenter_space_timestamp: float | None
    target_onset_timestamp: float
    go_signal_timestamp: float
    movement_onset_timestamp: float | None
    movement_end_timestamp: float
    end_reason: str
    movement_time_ms: float | None
    speed_feedback: str | None
    movement_angle_at_50pct_reach: float | None
    movement_angle_initial_segment: float | None
    report_wait_max_drift_mm: float | None  # report trials only; how far the hidden cursor strayed from home


class TrialRunner:
    def __init__(
        self,
        spec: TrialSpec,
        cfg: Config,
        params: GeometryParams,
        play_sound: Callable[[str], None] | None = None,
        reset_cursor: Callable[[], None] | None = None,
    ):
        self.spec = spec
        self.cfg = cfg
        self.params = params
        self.play_sound = play_sound or (lambda name: None)
        self.reset_cursor = reset_cursor or (lambda: None)

        self.home_px: Point = (params.home_x_px, params.home_y_px)
        self.target_pos_px: Point = geometry.target_position_px(spec.target_angle_deg, params)

        self.phase = TrialPhase.HOME_HOLD
        self.report_entry = ReportEntryState(cfg.report_entry.magnitude_range) if spec.needs_report else None
        self.reported = None

        self.samples: list[SampleRecord] = []
        self.result: TrialResult | None = None

        self.target_onset_timestamp: float | None = None
        self.go_signal_timestamp: float | None = None
        self.movement_onset_timestamp: float | None = None
        self.movement_end_timestamp: float | None = None
        self.report_registered_timestamp: float | None = None
        self.experimenter_space_timestamp: float | None = None
        self.end_reason: str | None = None
        self.movement_time_ms: float | None = None
        self.speed_feedback: str | None = None

        self._home_hold_start_t: float | None = None
        self._report_ready_t: float | None = None
        self._end_feedback_start_t: float | None = None
        self._displayed_pos: Point | None = self.home_px
        self._report_wait_max_drift_px: float | None = None
        self._moving_samples_start = 0

    # -- public -----------------------------------------------------------

    @property
    def displayed_pos(self) -> Point | None:
        """The most recently computed displayed-cursor position (None if
        the current trial type never shows a cursor). For rendering."""
        return self._displayed_pos

    def step(self, frame: FrameInput) -> None:
        if self.phase is TrialPhase.DONE:
            return

        if self.phase is TrialPhase.HOME_HOLD:
            self._step_home_hold(frame)
        elif self.phase is TrialPhase.REPORT_WAIT:
            self._step_report_wait(frame)
        elif self.phase is TrialPhase.MOVING:
            self._step_moving(frame)
        elif self.phase is TrialPhase.END_FEEDBACK:
            self._step_end_feedback(frame)

    # -- phase handlers -----------------------------------------------------

    def _compute_display_pos(self, raw: Point) -> Point | None:
        if not self.spec.cursor_visible_during_movement:
            return None
        raw_vec = (raw[0] - self.home_px[0], raw[1] - self.home_px[1])
        rotation = self.spec.rotation_deg or 0.0
        disp_vec = geometry.apply_visuomotor_rotation(raw_vec, rotation)
        return (self.home_px[0] + disp_vec[0], self.home_px[1] + disp_vec[1])

    def _record_sample(self, frame: FrameInput) -> None:
        display = self._compute_display_pos(frame.raw_cursor_px)
        self._displayed_pos = display
        self.samples.append(
            SampleRecord(
                sample_timestamp=frame.t,
                raw_x=frame.raw_cursor_px[0],
                raw_y=frame.raw_cursor_px[1],
                display_x=display[0] if display is not None else None,
                display_y=display[1] if display is not None else None,
            )
        )

    def _step_home_hold(self, frame: FrameInput) -> None:
        self._record_sample(frame)
        inside = geometry.distance(frame.raw_cursor_px, self.home_px) <= self.params.home_radius_px
        if not inside:
            self._home_hold_start_t = None
            return
        if self._home_hold_start_t is None:
            self._home_hold_start_t = frame.t
            return
        held_ms = (frame.t - self._home_hold_start_t) * 1000.0
        if held_ms >= self.cfg.timing.home_hold_ms:
            self._on_home_hold_satisfied(frame.t)

    def _on_home_hold_satisfied(self, t: float) -> None:
        self.target_onset_timestamp = t
        if self.spec.needs_report:
            self.phase = TrialPhase.REPORT_WAIT
        else:
            self._trigger_go_signal(t)

    def _step_report_wait(self, frame: FrameInput) -> None:
        self._record_sample(frame)
        drift = geometry.distance(frame.raw_cursor_px, self.home_px)
        self._report_wait_max_drift_px = max(self._report_wait_max_drift_px or 0.0, drift)
        entry = self.report_entry
        if frame.minus:
            entry.input_minus()
        if frame.digit is not None:
            entry.input_digit(frame.digit)
        if frame.backspace:
            entry.backspace()
        # The report is "registered" at the last keystroke that left it
        # confirmable, i.e. when the experimenter finished transcribing it.
        if frame.minus or frame.digit is not None or frame.backspace:
            self._report_ready_t = frame.t if entry.can_confirm() else None
        if frame.space_pressed and entry.can_confirm():
            self.reported = entry.confirm()
            self.report_registered_timestamp = self._report_ready_t
            self.experimenter_space_timestamp = frame.t
            self._trigger_go_signal(frame.t)

    def _trigger_go_signal(self, t: float) -> None:
        if self.phase is TrialPhase.REPORT_WAIT:
            # Discard drift during the (cursor-hidden) report wait: the reach
            # starts from home, as on every other trial (to-decide.md #35).
            self.reset_cursor()
            self._displayed_pos = self.home_px if self.spec.cursor_visible_during_movement else None
        self._moving_samples_start = len(self.samples)
        self.go_signal_timestamp = t
        self.play_sound("go_beep")
        self.phase = TrialPhase.MOVING

    def _step_moving(self, frame: FrameInput) -> None:
        self._record_sample(frame)
        raw = frame.raw_cursor_px

        if self.movement_onset_timestamp is None and geometry.movement_onset(raw, self.home_px, self.params):
            self.movement_onset_timestamp = frame.t

        hit_pos = self._displayed_pos if self.spec.cursor_visible_during_movement else raw
        hit = geometry.hit_test(hit_pos, self.target_pos_px, self.params)
        boundary = geometry.boundary_crossed(raw, self.home_px, self.params)
        elapsed_ms = (frame.t - self.go_signal_timestamp) * 1000.0
        timed_out = elapsed_ms >= self.cfg.timing.target_timeout_ms

        if hit:
            self._end_trial(frame.t, HIT)
        elif boundary:
            self._end_trial(frame.t, BOUNDARY)
        elif timed_out:
            self._end_trial(frame.t, TIMEOUT)

    def _end_trial(self, t: float, reason: str) -> None:
        self.movement_end_timestamp = t
        self.end_reason = reason
        if reason == HIT:
            if self.movement_onset_timestamp is not None:
                self.movement_time_ms = (t - self.movement_onset_timestamp) * 1000.0
            else:
                self.movement_time_ms = 0.0
            band = self.cfg.feedback_speed_band
            if self.movement_time_ms < band.good_min_ms:
                self.speed_feedback = TOO_FAST
            elif self.movement_time_ms > band.good_max_ms:
                self.speed_feedback = TOO_SLOW
            else:
                self.speed_feedback = GOOD
            self.play_sound("hit_bell")
        else:
            self.movement_time_ms = None
            self.speed_feedback = None
            self.play_sound("miss_buzz")
        self._end_feedback_start_t = t
        self.phase = TrialPhase.END_FEEDBACK

    def _step_end_feedback(self, frame: FrameInput) -> None:
        elapsed_ms = (frame.t - self._end_feedback_start_t) * 1000.0
        if elapsed_ms >= self.cfg.timing.end_feedback_duration_ms:
            self._finalize(frame.t)

    def _finalize(self, t: float) -> None:
        trajectory = [(s.raw_x, s.raw_y) for s in self.samples[self._moving_samples_start :]]
        angle_50 = geometry.movement_angle_at_fraction(trajectory, self.home_px, self.target_pos_px, 0.5)
        r1_px = _INITIAL_SEGMENT_R1_CM * self.params.px_per_cm
        r2_px = _INITIAL_SEGMENT_R2_CM * self.params.px_per_cm
        angle_init = geometry.movement_angle_initial_segment(trajectory, self.home_px, r1_px, r2_px)

        drift_mm = None
        if self._report_wait_max_drift_px is not None:
            drift_mm = self._report_wait_max_drift_px / self.params.px_per_cm * 10.0

        reported_angle = None
        if self.reported is not None:
            signed = geometry.magnitude_side_to_signed(self.reported.magnitude, self.reported.side or "CW")
            reported_angle = geometry.landmark_absolute_angle_deg(signed, self.spec.target_angle_deg, self.params)

        target_id = list(self.cfg.targets.angles_deg).index(self.spec.target_angle_deg)

        self.result = TrialResult(
            phase=self.spec.phase,
            trial_type=self.spec.trial_type,
            trial_index=self.spec.trial_index,
            cycle_index=self.spec.cycle_index,
            probe_index=self.spec.probe_index,
            target_id=target_id,
            target_angle_deg=self.spec.target_angle_deg,
            target_x=self.target_pos_px[0],
            target_y=self.target_pos_px[1],
            rotation_deg=self.spec.rotation_deg,
            cursor_visible_during_movement=self.spec.cursor_visible_during_movement,
            reported_number=self.reported.magnitude if self.reported else None,
            reported_side=self.reported.side if self.reported else None,
            reported_angle_deg=reported_angle,
            report_registered_timestamp=self.report_registered_timestamp,
            experimenter_space_timestamp=self.experimenter_space_timestamp,
            target_onset_timestamp=self.target_onset_timestamp,
            go_signal_timestamp=self.go_signal_timestamp,
            movement_onset_timestamp=self.movement_onset_timestamp,
            movement_end_timestamp=self.movement_end_timestamp,
            end_reason=self.end_reason,
            movement_time_ms=self.movement_time_ms,
            speed_feedback=self.speed_feedback,
            movement_angle_at_50pct_reach=angle_50,
            movement_angle_initial_segment=angle_init,
            report_wait_max_drift_mm=drift_mm,
        )
        self.phase = TrialPhase.DONE
