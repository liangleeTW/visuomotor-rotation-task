"""
Runtime px-per-cm calibration (to-decide.md #18).

Rather than trust a display's reported physical size (inaccurate for many
external monitors, and the spec's own `px: 391` figure assumes one
specific screen), this measures it empirically once per machine: an
on-screen line of a known pixel length is measured with a physical ruler,
and the resulting px/cm is cached to disk so future sessions don't need to
re-measure. See caution.md's "verify pointer acceleration empirically"
note — this is the same philosophy applied to screen geometry.

Flags:
    --recalibrate   Force a fresh measurement even if a cached one exists
                     (only relevant to the interactive routine, not to code
                     that just loads a cached value)

Usage:
    poetry run python -m vmr.display_calibration            # run once, interactively
    poetry run python -m vmr.display_calibration --recalibrate
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_CALIBRATION_PATH = Path(__file__).resolve().parent.parent / "display_calibration.json"


@dataclass(frozen=True)
class Calibration:
    px_per_cm: float
    measured_at: str
    display_resolution: tuple[int, int]
    notes: str = ""


def compute_px_per_cm(pixel_length: float, measured_cm: float) -> float:
    """Pure conversion: given a known on-screen pixel length and the
    physical length the experimenter measured with a ruler, return px/cm."""
    if measured_cm <= 0:
        raise ValueError(f"measured_cm must be positive, got {measured_cm!r}")
    if pixel_length <= 0:
        raise ValueError(f"pixel_length must be positive, got {pixel_length!r}")
    return pixel_length / measured_cm


def save_calibration(cal: Calibration, path: str | Path = DEFAULT_CALIBRATION_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(asdict(cal), f, indent=2)


def load_calibration(path: str | Path = DEFAULT_CALIBRATION_PATH) -> Calibration | None:
    path = Path(path)
    if not path.exists():
        return None
    with open(path) as f:
        data = json.load(f)
    return Calibration(display_resolution=tuple(data["display_resolution"]), **{k: v for k, v in data.items() if k != "display_resolution"})


def require_calibration(path: str | Path = DEFAULT_CALIBRATION_PATH) -> Calibration:
    """Load the cached calibration or raise with instructions — used at
    session startup so a missing calibration fails loudly rather than
    silently falling back to a wrong px/cm value."""
    cal = load_calibration(path)
    if cal is None:
        raise FileNotFoundError(
            f"no display calibration found at {path}. Run "
            "`poetry run python -m vmr.display_calibration` once on this "
            "machine before starting a session (see caution.md)."
        )
    return cal


def run_calibration_routine(line_length_px: float = 1000.0, path: str | Path = DEFAULT_CALIBRATION_PATH) -> Calibration:
    """Interactive routine: draws a horizontal line of `line_length_px`
    pixels and has the experimenter measure it with a physical ruler and
    type the result in cm. Not unit-tested (inherently interactive) — the
    pure math it calls (compute_px_per_cm) is tested separately."""
    import pygame  # noqa: PLC0415

    pygame.init()
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    resolution = screen.get_size()
    font = pygame.font.SysFont(None, 36)

    typed = ""
    result_cm: float | None = None
    clock = pygame.time.Clock()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(1)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit(1)
                elif event.key == pygame.K_RETURN and typed:
                    try:
                        result_cm = float(typed)
                        running = False
                    except ValueError:
                        typed = ""
                elif event.key == pygame.K_BACKSPACE:
                    typed = typed[:-1]
                elif event.unicode and (event.unicode.isdigit() or event.unicode == "."):
                    typed += event.unicode

        screen.fill((0, 0, 0))
        cx, cy = resolution[0] // 2, resolution[1] // 2
        x0, x1 = cx - line_length_px / 2, cx + line_length_px / 2
        pygame.draw.line(screen, (255, 255, 255), (x0, cy), (x1, cy), 3)
        pygame.draw.line(screen, (255, 255, 255), (x0, cy - 15), (x0, cy + 15), 3)
        pygame.draw.line(screen, (255, 255, 255), (x1, cy - 15), (x1, cy + 15), 3)

        prompt = font.render("Measure this line with a ruler (cm), type the value, press Enter:", True, (255, 255, 255))
        screen.blit(prompt, (cx - prompt.get_width() // 2, cy - 100))
        typed_surf = font.render(typed or "_", True, (0, 255, 0))
        screen.blit(typed_surf, (cx - typed_surf.get_width() // 2, cy + 40))

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()

    px_per_cm = compute_px_per_cm(line_length_px, result_cm)
    cal = Calibration(
        px_per_cm=px_per_cm,
        measured_at=datetime.now(timezone.utc).isoformat(),
        display_resolution=resolution,
        notes=f"line_length_px={line_length_px}, measured_cm={result_cm}",
    )
    save_calibration(cal, path)
    return cal


if __name__ == "__main__":
    force = "--recalibrate" in sys.argv
    if not force and load_calibration() is not None:
        print(f"Calibration already exists at {DEFAULT_CALIBRATION_PATH}. Pass --recalibrate to redo it.")
    else:
        cal = run_calibration_routine()
        print(f"Saved calibration: {cal.px_per_cm:.3f} px/cm -> {DEFAULT_CALIBRATION_PATH}")
