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
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pygame

from vmr.audio import SoundBank
from vmr.config import Config, load_config
from vmr.display import Renderer
from vmr.display_calibration import detect_main_display_resolution_px, resolve_calibration, save_calibration
from vmr.geometry import GeometryParams
from vmr.input_device import CursorTracker, PygameRelativeMouse
from vmr.logging_io import TrialLogger, save_config_snapshot
from vmr.menu import (
    BLOCKS,
    ExistingDataStatus,
    MenuSelection,
    TextEntryState,
    check_existing_data,
    draw_duplicate_warning,
    draw_menu,
    draw_text_entry,
    existing_trial_count,
    handle_menu_key,
    handle_text_entry_key,
    normalize_subject_id,
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


def _resolution_matches(a: tuple[int, int], b: tuple[int, int], tolerance: int = 1) -> bool:
    """True if `a` and `b` plausibly describe the same physical display,
    allowing for a 2x HiDPI scale-factor mismatch between the two APIs
    being compared — pygame's desktop sizes and Quartz's
    CGDisplayPixelsWide/High don't reliably agree on whether they report
    logical points or backing pixels for a Retina display."""
    aw, ah = a
    bw, bh = b
    for scale in (1, 2, 0.5):
        if abs(aw * scale - bw) <= tolerance and abs(ah * scale - bh) <= tolerance:
            return True
    return False


def resolve_display_index(quartz_module=None, pygame_module=None) -> int:
    """Which SDL/pygame display index corresponds to whichever display
    macOS currently calls "Main" (has the menu bar).

    pygame's own default (display=0) is NOT reliably the same display —
    confirmed by testing: it stayed on the built-in MacBook panel even
    with an external monitor explicitly set as Main Display in System
    Settings, because SDL's display order follows OS enumeration/
    connection order, not the Main Display setting (to-decide.md #31).
    This instead matches displays by resolution against Quartz's
    CGMainDisplayID, so window placement and vmr.display_calibration's
    auto-detection can never disagree about which screen is meant.

    Falls back to display 0 (pygame's own default) with a warning if
    there's only one display (nothing to disambiguate — that IS display
    0), or if detection fails or is ambiguous (e.g. two displays happen
    to share the exact same resolution).
    """
    pg = pygame_module or pygame
    if pg.display.get_num_displays() <= 1:
        return 0

    main_resolution = detect_main_display_resolution_px(quartz_module)
    if main_resolution is None:
        warnings.warn(
            "could not determine the main display via Quartz; defaulting "
            "to display 0, which may not be the intended screen"
        )
        return 0

    sizes = pg.display.get_desktop_sizes()
    matches = [i for i, size in enumerate(sizes) if _resolution_matches(size, main_resolution)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        warnings.warn(
            f"multiple displays match the main display's resolution {main_resolution}; defaulting to display 0"
        )
    else:
        warnings.warn(
            f"no display matches the main display's resolution {main_resolution}; defaulting to display 0"
        )
    return 0


def open_display(windowed_size: tuple[int, int] | None) -> pygame.Surface:
    """Opens the pygame window: fullscreen on whichever display macOS
    currently considers Main (resolve_display_index), or the given size
    in a regular window for --windowed/dev use (always display 0 there —
    a dev window's exact screen doesn't matter)."""
    if windowed_size is not None:
        return pygame.display.set_mode(windowed_size)
    display_index = resolve_display_index()
    return pygame.display.set_mode((0, 0), pygame.FULLSCREEN, display=display_index)


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

    pygame.init()
    pygame.font.init()
    screen = open_display(windowed_size)
    width, height = screen.get_size()

    # Resolved after the window exists: auto-detection needs the actual
    # pixel resolution, and a manual override (if one was run) always
    # wins over it — see vmr/display_calibration.py.
    calibration = resolve_calibration((width, height))

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
        save_calibration(calibration, paths.calibration_used_json)  # provenance: what px/cm this session actually used
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


def wait_for_duplicate_choice(
    screen: pygame.Surface,
    font: pygame.font.Font,
    clock: pygame.time.Clock,
    subject_id: str,
    block_name: str,
    status: ExistingDataStatus,
) -> str:
    """Blocks until the experimenter picks "resume" (R) or "retry" with a
    different subject ID (N). Raises QuitRequested on ESC/window-close."""
    while True:
        draw_duplicate_warning(screen, font, subject_id, block_name, status)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                raise QuitRequested
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    raise QuitRequested
                if event.key == pygame.K_r:
                    return "resume"
                if event.key == pygame.K_n:
                    return "retry"
        clock.tick(30)


def run_interactive_menu(
    screen: pygame.Surface,
    clock: pygame.time.Clock | None = None,
    data_dir: str | Path = "data",
) -> tuple[str, str]:
    """The 起始畫面: block selection, then subject-ID entry. If that
    subject/block already has trials logged, warns and requires an
    explicit Resume/different-ID choice before proceeding — prevents an
    accidentally-reused subject ID from silently resuming (or worse,
    partially merging into) a different person's data (to-decide.md #32).
    Returns (subject_id, block_name). Raises QuitRequested on
    ESC/window-close/cancel."""
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

    while True:
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

        subject_id = normalize_subject_id(entry.text)  # to-decide.md #33: strip only, case preserved
        status = check_existing_data(data_dir, subject_id, block_name)
        if status is None:
            return subject_id, block_name

        choice = wait_for_duplicate_choice(screen, font, clock, subject_id, block_name, status)
        if choice == "resume":
            return subject_id, block_name
        # "retry": loop back and let them type a different ID


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
    parser.add_argument(
        "--yes", action="store_true",
        help="skip the duplicate-subject confirmation prompt (for scripted/known-good resumes)",
    )
    args = parser.parse_args()
    windowed_size = (1280, 800) if args.windowed else None

    if args.subject and args.block:
        subject_id = normalize_subject_id(args.subject)  # to-decide.md #33
        status = check_existing_data(args.data_dir, subject_id, args.block)
        if status is not None and not args.yes:
            print(
                f"Subject '{subject_id}' / block '{args.block}' already has {status.n_trials} "
                f"trial(s) logged (last touched {status.last_modified})."
            )
            answer = input("Resume this subject? [y/N] ").strip().lower()
            if answer != "y":
                print("Cancelled. Re-run with a different --subject if this is a different participant.")
                return
        run_block(subject_id=subject_id, block_name=args.block, seed=args.seed, data_dir=args.data_dir, windowed_size=windowed_size)
        return

    pygame.init()
    pygame.font.init()
    screen = open_display(windowed_size)
    try:
        subject_id, block_name = run_interactive_menu(screen, data_dir=args.data_dir)
    except QuitRequested:
        pygame.quit()
        return
    pygame.quit()  # close the menu's window; run_block() opens its own

    run_block(subject_id=subject_id, block_name=block_name, seed=args.seed, data_dir=args.data_dir, windowed_size=windowed_size)


if __name__ == "__main__":
    main()
