"""
The 起始畫面 (start screen): block selection and subject-ID entry.

Follows the same "pure state + thin pygame glue" split as report_entry.py
and trial.py — MenuSelection/TextEntryState hold no pygame objects and are
driven by handle_*_key() functions that take plain pygame key constants
(which don't require any display to exist), so the interaction logic is
fully unit-testable. Only draw_menu/draw_text_entry touch a real surface.

Flags:
    (none — this module is imported, not run directly)

Usage:
    poetry run pytest tests/test_menu.py -v
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pygame

BLOCKS: list[str] = ["familiarization", "baseline", "adaptation", "post_adaptation"]
BLOCK_LABELS: dict[str, str] = {
    "familiarization": "Familiarization",
    "baseline": "Baseline",
    "adaptation": "Adaptation",
    "post_adaptation": "Post-adaptation",
}


class MenuSelection:
    def __init__(self, options: list[str] | None = None):
        self.options = list(options) if options is not None else list(BLOCKS)
        self.index = 0

    def move(self, delta: int) -> None:
        self.index = (self.index + delta) % len(self.options)

    @property
    def selected(self) -> str:
        return self.options[self.index]


def handle_menu_key(selection: MenuSelection, key: int) -> str | None:
    """Returns the chosen block name on Enter, else None."""
    if key in (pygame.K_UP, pygame.K_LEFT):
        selection.move(-1)
    elif key in (pygame.K_DOWN, pygame.K_RIGHT):
        selection.move(1)
    elif key == pygame.K_RETURN:
        return selection.selected
    return None


class TextEntryState:
    def __init__(self, initial: str = ""):
        self.text = initial

    def input_char(self, ch: str) -> None:
        if ch and ch.isprintable():
            self.text += ch

    def backspace(self) -> None:
        self.text = self.text[:-1]

    def clear(self) -> None:
        self.text = ""


def handle_text_entry_key(state: TextEntryState, event: pygame.event.Event) -> bool:
    """Returns True when Enter is pressed with non-empty text (confirmed)."""
    if event.key == pygame.K_RETURN:
        return bool(state.text)
    if event.key == pygame.K_BACKSPACE:
        state.backspace()
    elif getattr(event, "unicode", ""):
        state.input_char(event.unicode)
    return False


@dataclass(frozen=True)
class SessionPaths:
    trials_csv: Path
    samples_csv: Path
    schedule_csv: Path
    config_snapshot_yaml: Path
    calibration_used_json: Path


def session_paths(data_dir: str | Path, subject_id: str, block_name: str) -> SessionPaths:
    base = Path(data_dir) / subject_id / block_name
    return SessionPaths(
        trials_csv=base / "trials.csv",
        samples_csv=base / "samples.csv",
        schedule_csv=base / "schedule.csv",
        config_snapshot_yaml=base / "config_snapshot.yaml",
        calibration_used_json=base / "calibration_used.json",
    )


def existing_trial_count(trials_csv: str | Path) -> int:
    """Number of data rows already logged for this subject/block (0 if the
    file doesn't exist yet) — used to refuse silently overwriting a prior
    session (todo.md section 10)."""
    path = Path(trials_csv)
    if not path.exists():
        return 0
    with open(path) as f:
        return max(0, sum(1 for _ in f) - 1)  # minus header


# -- rendering (thin, not unit-tested beyond smoke coverage) -----------------


def draw_menu(screen: pygame.Surface, font: pygame.font.Font, selection: MenuSelection, color=(255, 255, 255)) -> None:
    screen.fill((0, 0, 0))
    w, h = screen.get_size()
    line_height = 50
    top = h / 2 - len(selection.options) * line_height / 2
    for i, option in enumerate(selection.options):
        label = BLOCK_LABELS[option]
        prefix = "> " if i == selection.index else "  "
        surf = font.render(prefix + label, True, color)
        screen.blit(surf, (w / 2 - surf.get_width() / 2, top + i * line_height))
    pygame.display.flip()


def draw_text_entry(screen: pygame.Surface, font: pygame.font.Font, prompt: str, state: TextEntryState, color=(255, 255, 255)) -> None:
    screen.fill((0, 0, 0))
    w, h = screen.get_size()
    prompt_surf = font.render(prompt, True, color)
    screen.blit(prompt_surf, (w / 2 - prompt_surf.get_width() / 2, h / 2 - 60))
    entry_surf = font.render(state.text + "_", True, (0, 255, 0))
    screen.blit(entry_surf, (w / 2 - entry_surf.get_width() / 2, h / 2))
    pygame.display.flip()
