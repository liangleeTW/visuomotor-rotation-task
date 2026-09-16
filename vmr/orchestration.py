"""
Ties every module together into one runnable block: menu -> calibration ->
schedule -> per-trial loop (instruction? -> hold -> report? -> move ->
feedback -> log) -> ITI -> next trial.

Input polling is injected (poll_events / PygameRelativeMouse) the same way
play_sound is injected into TrialRunner and mixer_module into SoundBank —
this is what lets run_block() be integration-tested headlessly with a
scripted input source instead of requiring a real keyboard/trackpad.

Flags:
    --subject     Subject ID (creates/resumes data/<subject>/<block>/)
    --block       One of: familiarization, baseline, adaptation, post_adaptation
    --seed        RNG seed for the trial schedule (default: random, then recorded)
    --data-dir    Root directory for session data (default: ./data)
    --windowed    Run in a resizable window instead of fullscreen (for dev)

Usage:
    poetry run python -m vmr.orchestration --subject S01 --block familiarization
    poetry run python -m vmr.orchestration --subject S01 --block baseline --windowed
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pygame

from vmr.audio import SoundBank
from vmr.config import Config, load_config
from vmr.display import Renderer
from vmr.display_calibration import require_calibration
from vmr.geometry import GeometryParams
from vmr.input_device import CursorTracker, PygameRelativeMouse
from vmr.logging_io import TrialLogger, save_config_snapshot
from vmr.menu import (
    BLOCKS,
    MenuSelection,
    TextEntryState,
    draw_menu,
    draw_text_entry,
    existing_trial_count,
    handle_menu_key,
    handle_text_entry_key,
    session_paths,
)
from vmr.schedule import Schedule, TrialSpec, build_schedule
from vmr.trial import FrameInput, TrialPhase, TrialRunner


@dataclass
class FrameEvents:
    space_pressed: bool = False
    digit: int | None = None
    side: str | None = None
    backspace: bool = False
    quit_requested: bool = False


_DIGIT_KEYS = {getattr(pygame, f"K_{i}"): i for i in range(10)}


def poll_pygame_events(cfg: Config) -> FrameEvents:
    events = FrameEvents()
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            events.quit_requested = True
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                events.quit_requested = True
            elif event.key == pygame.K_SPACE:
                events.space_pressed = True
            elif event.key == pygame.K_BACKSPACE:
                events.backspace = True
            elif event.key in _DIGIT_KEYS:
                events.digit = _DIGIT_KEYS[event.key]
            elif event.key == pygame.K_LEFT:
                events.side = cfg.report_entry.side_keys["left"]
            elif event.key == pygame.K_RIGHT:
                events.side = cfg.report_entry.side_keys["right"]
    return events


class QuitRequested(Exception):
    pass


PollEventsFn = Callable[[Config], FrameEvents]


def run_trial(
    runner: TrialRunner,
    mouse: PygameRelativeMouse,
    tracker: CursorTracker,
    renderer: Renderer,
    clock: pygame.time.Clock,
    t0: float,
    cfg: Config,
    poll_events: PollEventsFn = poll_pygame_events,
    fps: int = 60,
) -> None:
    """Drives one TrialRunner to completion, rendering each frame."""
    while runner.phase is not TrialPhase.DONE:
        events = poll_events(cfg)
        if events.quit_requested:
            raise QuitRequested
        dx, dy = mouse.poll_delta()
        tracker.apply_delta(dx, dy)
        now = time.perf_counter() - t0
        frame = FrameInput(
            t=now,
            raw_cursor_px=tracker.position,
            space_pressed=events.space_pressed,
            digit=events.digit,
            side=events.side,
            backspace=events.backspace,
        )
        runner.step(frame)
        renderer.render_trial_frame(runner)
        renderer.flip()
        clock.tick(fps)


def wait_for_space(
    renderer: Renderer,
    instruction_key: str,
    poll_events: PollEventsFn = poll_pygame_events,
    cfg: Config | None = None,
    clock: pygame.time.Clock | None = None,
    fps: int = 30,
) -> None:
    clock = clock or pygame.time.Clock()
    renderer.render_instruction(instruction_key)
    renderer.flip()
    while True:
        events = poll_events(cfg)
        if events.quit_requested:
            raise QuitRequested
        if events.space_pressed:
            return
        clock.tick(fps)


def wait_iti(
    duration_ms: int,
    poll_events: PollEventsFn = poll_pygame_events,
    cfg: Config | None = None,
    clock: pygame.time.Clock | None = None,
    fps: int = 60,
) -> None:
    clock = clock or pygame.time.Clock()
    start = time.perf_counter()
    while (time.perf_counter() - start) * 1000.0 < duration_ms:
        events = poll_events(cfg)
        if events.quit_requested:
            raise QuitRequested
        clock.tick(fps)


def run_block(
    subject_id: str,
    block_name: str,
    cfg: Config | None = None,
    seed: int | None = None,
    data_dir: str | Path = "data",
    windowed_size: tuple[int, int] | None = None,
    poll_events: PollEventsFn = poll_pygame_events,
    mouse_factory: Callable[[], PygameRelativeMouse] = PygameRelativeMouse,
) -> Schedule:
    """Runs every not-yet-logged trial of `block_name` for `subject_id`,
    resuming automatically if some trials were already logged. Returns the
    Schedule used (useful for tests/inspection)."""
    cfg = cfg or load_config()
    calibration = require_calibration()

    pygame.init()
    pygame.font.init()
    if windowed_size is not None:
        screen = pygame.display.set_mode(windowed_size)
    else:
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    width, height = screen.get_size()

    params = GeometryParams.from_config(cfg, calibration.px_per_cm, home_x_px=width / 2, home_y_px=height / 2)
    renderer = Renderer(screen, cfg.colors, params)
    sound_bank = SoundBank(cfg.audio)

    schedule = build_schedule(cfg, seed=seed)
    block_trials: list[TrialSpec] = schedule.by_phase(block_name)
    if not block_trials:
        raise ValueError(f"unknown or empty block: {block_name!r}")

    paths = session_paths(data_dir, subject_id, block_name)
    n_existing = existing_trial_count(paths.trials_csv)
    if n_existing == 0:
        paths.trials_csv.parent.mkdir(parents=True, exist_ok=True)
        save_config_snapshot(cfg.raw, paths.config_snapshot_yaml)
        import pandas as pd  # local import: only needed for this one-off save

        pd.DataFrame([vars(t) for t in block_trials]).to_csv(paths.schedule_csv, index=False)

    trials_to_run = block_trials[n_existing:]

    mouse = mouse_factory()
    mouse.start()
    tracker = CursorTracker(home_px=(params.home_x_px, params.home_y_px))
    clock = pygame.time.Clock()
    t0 = time.perf_counter()

    try:
        with TrialLogger(paths.trials_csv, paths.samples_csv) as logger:
            for offset, spec in enumerate(trials_to_run):
                global_index = n_existing + offset
                if spec.show_instruction and spec.instruction_key:
                    wait_for_space(renderer, spec.instruction_key, poll_events, cfg, clock)
                tracker.reset_to_home()
                runner = TrialRunner(spec, cfg, params, play_sound=sound_bank.play)
                run_trial(runner, mouse, tracker, renderer, clock, t0, cfg, poll_events)
                logger.log_trial(global_index, schedule.seed, runner.result, runner.samples)
                wait_iti(cfg.timing.inter_trial_interval_ms, poll_events, cfg, clock)
    except QuitRequested:
        pass
    finally:
        mouse.stop()
        pygame.quit()

    return schedule


def run_interactive_menu(screen: pygame.Surface, clock: pygame.time.Clock | None = None) -> tuple[str, str]:
    """The 起始畫面: block selection, then subject-ID entry. Returns
    (subject_id, block_name). Raises QuitRequested on ESC/window-close."""
    clock = clock or pygame.time.Clock()
    font = pygame.font.SysFont(None, 40)

    selection = MenuSelection(BLOCKS)
    block_name: str | None = None
    while block_name is None:
        draw_menu(screen, font, selection)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                raise QuitRequested
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    raise QuitRequested
                block_name = handle_menu_key(selection, event.key)
        clock.tick(30)

    entry = TextEntryState()
    confirmed = False
    while not confirmed:
        draw_text_entry(screen, font, "Enter subject ID, then press Enter:", entry)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                raise QuitRequested
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    raise QuitRequested
                confirmed = handle_text_entry_key(entry, event)
        clock.tick(30)

    return entry.text, block_name


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", default=None, help="skip the menu and go straight to this subject")
    parser.add_argument(
        "--block", default=None, choices=["familiarization", "baseline", "adaptation", "post_adaptation"],
        help="skip the menu and go straight to this block (requires --subject too)",
    )
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--windowed", action="store_true")
    args = parser.parse_args()
    windowed_size = (1280, 800) if args.windowed else None

    if args.subject and args.block:
        run_block(subject_id=args.subject, block_name=args.block, seed=args.seed, data_dir=args.data_dir, windowed_size=windowed_size)
        return

    pygame.init()
    pygame.font.init()
    screen = pygame.display.set_mode(windowed_size if windowed_size else (0, 0), 0 if windowed_size else pygame.FULLSCREEN)
    try:
        subject_id, block_name = run_interactive_menu(screen)
    except QuitRequested:
        pygame.quit()
        return
    pygame.quit()  # close the menu's window; run_block() opens its own

    run_block(subject_id=subject_id, block_name=block_name, seed=args.seed, data_dir=args.data_dir, windowed_size=windowed_size)


if __name__ == "__main__":
    main()
