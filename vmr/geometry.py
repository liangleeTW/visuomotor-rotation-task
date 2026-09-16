"""
Pure geometry functions for the visuomotor rotation task.

No pygame, no I/O, no clock — every function here takes plain numbers/tuples
and returns plain numbers/tuples, so it can (and must) be fully covered by
unit tests before any pixel is ever drawn.

Angle convention (fixed for the whole codebase — see tests for worked
examples):
    - 0 deg = right (+x), 90 deg = up (-y), 180 deg = left (-x), 270 deg = down (+y)
    - increasing degrees sweeps counterclockwise as the participant views
      the screen (standard visual/math convention, adapted for pygame's
      y-down pixel coordinates)
    - "clockwise" (as used in the spec: "60 deg clockwise rotation",
      Taylor et al.'s landmark sign) always means *decreasing* angle in
      this convention

Flags:
    (none — this module is imported, not run directly)

Usage:
    poetry run pytest tests/test_geometry.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Unit conversion
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GeometryParams:
    """Everything geometry.py needs, pre-converted to pixels for one session.

    Built once per session from Config + a runtime-measured px_per_cm
    (see vmr/display_calibration.py) — geometry.py itself never queries the
    display, which is what keeps it pure/testable.
    """

    px_per_cm: float
    home_x_px: float
    home_y_px: float
    home_to_target_px: float
    workspace_boundary_px: float
    home_radius_px: float
    cursor_radius_px: float
    target_radius_px: float
    hit_radius_px: float
    landmark_spacing_deg: float
    landmark_max_magnitude: int

    @classmethod
    def from_config(cls, cfg, px_per_cm: float, home_x_px: float, home_y_px: float) -> "GeometryParams":
        mm_per_cm = 10.0
        px_per_mm = px_per_cm / mm_per_cm
        ws = cfg.workspace
        return cls(
            px_per_cm=px_per_cm,
            home_x_px=home_x_px,
            home_y_px=home_y_px,
            home_to_target_px=ws.home_to_target_cm * px_per_cm,
            workspace_boundary_px=ws.workspace_boundary_cm * px_per_cm,
            home_radius_px=ws.home_radius_mm * px_per_mm,
            cursor_radius_px=ws.cursor_radius_mm * px_per_mm,
            target_radius_px=ws.target_radius_mm * px_per_mm,
            hit_radius_px=ws.hit_radius_mm * px_per_mm,
            landmark_spacing_deg=cfg.landmarks.spacing_deg,
            landmark_max_magnitude=cfg.landmarks.max_magnitude,
        )


Point = tuple[float, float]


# ---------------------------------------------------------------------------
# Angle helpers
# ---------------------------------------------------------------------------


def wrap_deg_360(angle_deg: float) -> float:
    """Wrap an angle to [0, 360)."""
    return angle_deg % 360.0


def wrap_deg_180(angle_deg: float) -> float:
    """Wrap an angle to (-180, 180]."""
    wrapped = wrap_deg_360(angle_deg)
    return wrapped - 360.0 if wrapped > 180.0 else wrapped


def rotate_vector_cw(x: float, y: float, degrees: float) -> Point:
    """Rotate a pixel-space vector clockwise (as the viewer sees it) by
    `degrees`. Negative `degrees` rotates counterclockwise.

    Because pygame's y axis points down, the matrix that produces a
    visually-clockwise rotation applied directly to (x, y) is the same
    matrix that would produce a counterclockwise rotation in a normal
    y-up frame. See tests/test_geometry.py for the derivation check
    (rotating "up" 90 deg clockwise must yield "right").
    """
    phi = math.radians(degrees)
    cos_phi, sin_phi = math.cos(phi), math.sin(phi)
    return (x * cos_phi - y * sin_phi, x * sin_phi + y * cos_phi)


def apply_visuomotor_rotation(raw_vector: Point, rotation_deg: float) -> Point:
    """Transform a raw hand-movement vector (relative to home) into the
    displayed-cursor vector under a visuomotor rotation.

    `rotation_deg` follows the spec's convention: positive = clockwise.
    A 60 deg rotation means the displayed cursor appears 60 deg clockwise
    of where the hand actually points.
    """
    x, y = raw_vector
    return rotate_vector_cw(x, y, rotation_deg)


# ---------------------------------------------------------------------------
# Target / home positions
# ---------------------------------------------------------------------------


def target_position_px(angle_deg: float, params: GeometryParams) -> Point:
    """Absolute pixel position of a target at `angle_deg` from home."""
    theta = math.radians(angle_deg)
    dx = params.home_to_target_px * math.cos(theta)
    dy = -params.home_to_target_px * math.sin(theta)
    return (params.home_x_px + dx, params.home_y_px + dy)


def heading_angle_deg(p_from: Point, p_to: Point) -> float:
    """Angle (in this module's convention) of the vector p_from -> p_to,
    wrapped to [0, 360)."""
    dx = p_to[0] - p_from[0]
    dy = p_to[1] - p_from[1]
    theta = math.degrees(math.atan2(-dy, dx))
    return wrap_deg_360(theta)


def signed_angular_error_deg(heading_deg: float, target_deg: float) -> float:
    """Signed angular error, positive = heading is clockwise of the target.

    Matches Taylor, Krakauer & Ivry (2014)'s convention exactly ("positive
    indicate a clockwise deviation... negative angles indicate
    counterclockwise deviation from the target"), and matches this
    codebase's landmark sign convention (see landmark_absolute_angle_deg).
    """
    return wrap_deg_180(target_deg - heading_deg)


# ---------------------------------------------------------------------------
# Hit / boundary tests
# ---------------------------------------------------------------------------


def distance(p1: Point, p2: Point) -> float:
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def hit_test(cursor_pos_px: Point, target_pos_px: Point, params: GeometryParams) -> bool:
    """True if the displayed cursor circle touches the target circle
    (to-decide.md #12: hit_radius = target_radius + cursor_radius)."""
    return distance(cursor_pos_px, target_pos_px) <= params.hit_radius_px


def boundary_crossed(raw_pos_px: Point, home_pos_px: Point, params: GeometryParams) -> bool:
    """True if the RAW (unrotated) hand position has left the workspace
    boundary. Boundary crossing is always evaluated on raw movement, even
    in trials where the displayed cursor is rotated or hidden."""
    return distance(raw_pos_px, home_pos_px) >= params.workspace_boundary_px


def movement_onset(raw_pos_px: Point, home_pos_px: Point, params: GeometryParams) -> bool:
    """True once the cursor has left the home radius (to-decide.md #1)."""
    return distance(raw_pos_px, home_pos_px) > params.home_radius_px


# ---------------------------------------------------------------------------
# Landmarks (Taylor, Krakauer & Ivry, 2014)
# ---------------------------------------------------------------------------


def landmark_absolute_angle_deg(signed_number: int, target_angle_deg: float, params: GeometryParams) -> float:
    """Absolute angle of a landmark, given its signed number (positive =
    clockwise from target, negative = counterclockwise, per the paper)."""
    return wrap_deg_360(target_angle_deg - signed_number * params.landmark_spacing_deg)


def landmark_position_px(signed_number: int, target_angle_deg: float, params: GeometryParams) -> Point:
    """Pixel position of a landmark tick on the ring (ring radius equals
    the home-to-target distance, per the spec's mockups)."""
    angle = landmark_absolute_angle_deg(signed_number, target_angle_deg, params)
    theta = math.radians(angle)
    dx = params.home_to_target_px * math.cos(theta)
    dy = -params.home_to_target_px * math.sin(theta)
    return (params.home_x_px + dx, params.home_y_px + dy)


def magnitude_side_to_signed(magnitude: int, side: str) -> int:
    """Convert the experimenter's (magnitude, side) entry into the paper's
    signed landmark number. side must be 'CW' or 'CCW'."""
    if side not in ("CW", "CCW"):
        raise ValueError(f"side must be 'CW' or 'CCW', got {side!r}")
    if magnitude == 0:
        return 0
    return magnitude if side == "CW" else -magnitude


def signed_to_magnitude_side(signed_number: int) -> tuple[int, str]:
    """Inverse of magnitude_side_to_signed."""
    if signed_number == 0:
        return 0, "CW"
    return abs(signed_number), ("CW" if signed_number > 0 else "CCW")


# ---------------------------------------------------------------------------
# Trajectory analysis
# ---------------------------------------------------------------------------


def find_radius_crossing(trajectory: list[Point], home_px: Point, radius_px: float) -> Point | None:
    """First point along `trajectory` (a list of positions in chronological
    order, all relative to the same origin as home_px) where distance from
    home reaches `radius_px`, linearly interpolated between the two
    straddling samples for sub-sample accuracy. Returns None if the
    trajectory never reaches that radius (e.g. a trial that timed out
    close to home)."""
    prev = home_px
    prev_dist = 0.0
    for point in trajectory:
        d = distance(point, home_px)
        if d >= radius_px:
            if d == prev_dist:
                return point
            t = (radius_px - prev_dist) / (d - prev_dist)
            return (prev[0] + t * (point[0] - prev[0]), prev[1] + t * (point[1] - prev[1]))
        prev, prev_dist = point, d
    return None


def movement_angle_at_fraction(
    trajectory: list[Point], home_px: Point, target_px: Point, fraction: float
) -> float | None:
    """Heading angle (home -> trajectory) at the point where the movement
    has covered `fraction` of the home-to-target distance. Used for
    movement_angle_at_50pct_reach with fraction=0.5."""
    radius_px = fraction * distance(home_px, target_px)
    crossing = find_radius_crossing(trajectory, home_px, radius_px)
    if crossing is None:
        return None
    return heading_angle_deg(home_px, crossing)


def movement_angle_initial_segment(
    trajectory: list[Point], home_px: Point, r1_px: float, r2_px: float
) -> float | None:
    """Heading angle of the straight line between the trajectory points at
    radius r1_px and r2_px from home — Taylor et al. (2014)'s primary
    heading-angle measure (they use 1 cm and 3 cm). Convert cm to px
    before calling."""
    p1 = find_radius_crossing(trajectory, home_px, r1_px)
    p2 = find_radius_crossing(trajectory, home_px, r2_px)
    if p1 is None or p2 is None:
        return None
    return heading_angle_deg(p1, p2)
