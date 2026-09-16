"""
Smoke/integration tests for vmr.display, run headlessly (SDL dummy
drivers, set in tests/conftest.py) — these actually initialize pygame and
render real frames, unlike the pure-logic tests elsewhere.

Flags:
    (none — run with pytest)

Usage:
    poetry run pytest tests/test_display.py -v
"""

import pygame
import pytest

from vmr.config import load_config
from vmr.display import INSTRUCTION_TEXT, Renderer
from vmr.geometry import GeometryParams
from vmr.schedule import TrialSpec
from vmr.trial import FrameInput, TrialPhase, TrialRunner

CFG = load_config()
DT = 0.01


@pytest.fixture(scope="module", autouse=True)
def pygame_session():
    pygame.init()
    pygame.font.init()
    yield
    pygame.quit()


@pytest.fixture
def screen():
    return pygame.display.set_mode((1700, 1700))


@pytest.fixture
def params():
    return GeometryParams.from_config(CFG, px_per_cm=100.0, home_x_px=850.0, home_y_px=850.0)


@pytest.fixture
def renderer(screen, params):
    return Renderer(screen, CFG.colors, params)


def make_spec(trial_type="baseline_veridical", target_angle_deg=0.0, rotation_deg=0.0, cursor_visible=True, needs_report=False):
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


def test_home_hold_frame_draws_home_color(renderer, params):
    spec = make_spec()
    runner = TrialRunner(spec, CFG, params)
    runner.step(FrameInput(t=0.0, raw_cursor_px=(params.home_x_px, params.home_y_px)))
    renderer.render_trial_frame(runner)
    # sample near the edge of the home circle, outside the (smaller) cursor
    # circle drawn on top of it at the exact center
    edge = (int(params.home_x_px + params.home_radius_px - 2), int(params.home_y_px))
    pixel = renderer.screen.get_at(edge)[:3]
    assert tuple(pixel) == tuple(CFG.colors.home)


def test_report_wait_frame_draws_target_and_landmarks(renderer, params):
    spec = make_spec(trial_type="adaptation_report", rotation_deg=60.0, needs_report=True)
    runner = TrialRunner(spec, CFG, params)
    t = 0.0
    for _ in range(60):
        runner.step(FrameInput(t=t, raw_cursor_px=(params.home_x_px, params.home_y_px)))
        t += DT
        if runner.phase is TrialPhase.REPORT_WAIT:
            break
    assert runner.phase is TrialPhase.REPORT_WAIT
    renderer.render_trial_frame(runner)
    # sample slightly off the exact target center: landmark "0" sits at
    # the identical position (same radius, target's own angle) and its
    # tiny tick mark overwrites just the center pixel on top of the much
    # larger target circle drawn underneath it
    target_x, target_y = runner.target_pos_px
    target_pixel = renderer.screen.get_at((int(target_x) + 20, int(target_y)))[:3]
    assert tuple(target_pixel) == tuple(CFG.colors.target_default)
    # background should not be uniformly black everywhere (landmarks were drawn)
    corner_ring_pixel_found = False
    for signed in (-31, 0, 31):
        from vmr.geometry import landmark_position_px

        pos = landmark_position_px(signed, spec.target_angle_deg, params)
        px = renderer.screen.get_at((int(pos[0]), int(pos[1])))[:3]
        if tuple(px) != tuple(CFG.colors.background):
            corner_ring_pixel_found = True
    assert corner_ring_pixel_found


def test_end_feedback_frame_draws_hit_color(renderer, params):
    spec = make_spec(target_angle_deg=0.0, rotation_deg=0.0)
    runner = TrialRunner(spec, CFG, params)
    t = 0.0
    for _ in range(60):
        runner.step(FrameInput(t=t, raw_cursor_px=(params.home_x_px, params.home_y_px)))
        t += DT
        if runner.phase is TrialPhase.MOVING:
            break
    home = runner.home_px
    target = runner.target_pos_px
    start_t = t
    duration_s = 0.5
    for _ in range(200):
        frac = min(1.5, (t - start_t) / duration_s)
        pos = (home[0] + (target[0] - home[0]) * frac, home[1] + (target[1] - home[1]) * frac)
        runner.step(FrameInput(t=t, raw_cursor_px=pos))
        t += DT
        if runner.phase is TrialPhase.END_FEEDBACK:
            break
    assert runner.phase is TrialPhase.END_FEEDBACK
    renderer.render_trial_frame(runner)
    pixel = renderer.screen.get_at((int(target[0]), int(target[1])))[:3]
    assert tuple(pixel) == tuple(CFG.colors.hit_good)


def test_boundary_miss_draws_nothing_at_target(renderer, params):
    spec = make_spec()
    runner = TrialRunner(spec, CFG, params)
    t = 0.0
    for _ in range(60):
        runner.step(FrameInput(t=t, raw_cursor_px=(params.home_x_px, params.home_y_px)))
        t += DT
        if runner.phase is TrialPhase.MOVING:
            break
    for i in range(300):
        pos = (params.home_x_px - i * 20.0, params.home_y_px)
        runner.step(FrameInput(t=t, raw_cursor_px=pos))
        t += DT
        if runner.phase is TrialPhase.END_FEEDBACK:
            break
    assert runner.end_reason == "boundary"
    renderer.render_trial_frame(runner)
    pixel = renderer.screen.get_at((int(runner.target_pos_px[0]), int(runner.target_pos_px[1])))[:3]
    assert tuple(pixel) == tuple(CFG.colors.background)  # target disappeared


@pytest.mark.parametrize("key", list(INSTRUCTION_TEXT.keys()))
def test_render_instruction_draws_text(renderer, key):
    renderer.render_instruction(key)
    # scan a band around the vertical center (not a single exact row —
    # font ascent/glyph-ink offsets mean text pixels may sit a few px off
    # from the nominal center line) for any non-background pixel
    w, h = renderer.screen.get_size()
    found_non_background = any(
        tuple(renderer.screen.get_at((x, y))[:3]) != tuple(CFG.colors.background)
        for y in range(h // 2 - 60, h // 2 + 60, 4)
        for x in range(0, w, 5)
    )
    assert found_non_background


def test_render_instruction_unknown_key_does_not_crash(renderer):
    renderer.render_instruction("totally_unknown_key")
