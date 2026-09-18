"""
Runtime px-per-cm resolution (to-decide.md #18).

px/cm is auto-detected by default — macOS reports the physical size of a
connected display accurately via Quartz (CGDisplayScreenSize), which is
what resolve_calibration() uses automatically on every run, no setup
required. A manually-measured calibration (via the interactive ruler
routine below, saved to disk) is only needed as an override, for the rare
case auto-detection is wrong or unavailable (e.g. some external monitors
with missing/incorrect EDID data, or a machine without Quartz). If a
manual calibration file exists, it always takes precedence over
auto-detection, since running it is a deliberate correction.

Flags:
    --recalibrate   Force a fresh manual measurement even if a cached one
                     exists (only relevant to the interactive routine)

Usage:
    poetry run python -m vmr.display_calibration            # manual override, interactive
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


# Physical sizes outside this range indicate CGDisplayScreenSize returned
# garbage (some external-monitor/adapter combinations report 0 or absurd
# values) rather than a real display — reject rather than silently using
# a wrong px/cm.
_MIN_PLAUSIBLE_MM = 100.0
_MAX_PLAUSIBLE_MM = 2000.0


def detect_physical_size_mm(quartz_module=None) -> tuple[float, float] | None:
    """Auto-detect the main display's physical size in mm via Quartz.
    Returns None (never raises) if Quartz isn't available (non-macOS, or
    not installed) or the reported size is missing/implausible — callers
    should fall back to manual calibration in that case."""
    if quartz_module is None:
        try:
            import Quartz as quartz_module  # noqa: PLC0415
        except ImportError:
            return None
    try:
        display_id = quartz_module.CGMainDisplayID()
        size = quartz_module.CGDisplayScreenSize(display_id)
        width_mm, height_mm = size.width, size.height
    except Exception:
        return None
    if not (_MIN_PLAUSIBLE_MM <= width_mm <= _MAX_PLAUSIBLE_MM):
        return None
    if not (_MIN_PLAUSIBLE_MM <= height_mm <= _MAX_PLAUSIBLE_MM):
        return None
    return (width_mm, height_mm)


def detect_calibration(screen_resolution_px: tuple[int, int], quartz_module=None) -> Calibration | None:
    """Auto-detected Calibration for the given pixel resolution, or None
    if detection isn't possible (see detect_physical_size_mm)."""
    physical = detect_physical_size_mm(quartz_module)
    if physical is None:
        return None
    width_mm, height_mm = physical
    width_px, _height_px = screen_resolution_px
    px_per_cm = compute_px_per_cm(width_px, width_mm / 10.0)
    return Calibration(
        px_per_cm=px_per_cm,
        measured_at=datetime.now(timezone.utc).isoformat(),
        display_resolution=tuple(screen_resolution_px),
        notes=f"auto-detected via Quartz CGDisplayScreenSize ({width_mm:.1f}mm x {height_mm:.1f}mm)",
    )


def resolve_calibration(
    screen_resolution_px: tuple[int, int],
    path: str | Path = DEFAULT_CALIBRATION_PATH,
    quartz_module=None,
) -> Calibration:
    """The single entry point sessions should use. A manual calibration on
    disk (an explicit correction the experimenter made) always wins;
    otherwise this auto-detects fresh on every call — detection is cheap,
    so there's no need to cache it, and not caching it means a monitor
    swap is picked up immediately rather than sticking with a stale value.
    Raises only if both are unavailable."""
    manual = load_calibration(path)
    if manual is not None:
        return manual
    detected = detect_calibration(screen_resolution_px, quartz_module)
    if detected is not None:
        return detected
    raise FileNotFoundError(
        f"could not auto-detect this display's physical size, and no manual "
        f"calibration is cached at {path}. Run "
        "`poetry run python -m vmr.display_calibration` once on this "
        "machine (see caution.md)."
    )


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
