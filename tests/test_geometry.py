"""
Unit tests for vmr.geometry.

Flags:
    (none — run with pytest)

Usage:
    poetry run pytest tests/test_geometry.py -v
"""

import math

import pytest

from vmr import geometry as geo

# A fixed set of params for tests that need one: 100 px/cm, home at origin,
# 7 cm reach (700 px), round numbers chosen to make expected values obvious.
PARAMS = geo.GeometryParams(
    px_per_cm=100.0,
    home_x_px=0.0,
    home_y_px=0.0,
    home_to_target_px=700.0,
    workspace_boundary_px=700.0,
    home_radius_px=25.0,
    cursor_radius_px=5.0,
    target_radius_px=50.0,
    hit_radius_px=55.0,
    landmark_spacing_deg=5.625,
    landmark_max_magnitude=31,
)


def approx_point(p, expected, tol=1e-6):
    assert p[0] == pytest.approx(expected[0], abs=tol)
    assert p[1] == pytest.approx(expected[1], abs=tol)


# ---------------------------------------------------------------------------
# wrap helpers
# ---------------------------------------------------------------------------


def test_wrap_deg_360():
    assert geo.wrap_deg_360(0) == 0
    assert geo.wrap_deg_360(360) == 0
    assert geo.wrap_deg_360(370) == pytest.approx(10)
    assert geo.wrap_deg_360(-10) == pytest.approx(350)


def test_wrap_deg_180():
    assert geo.wrap_deg_180(0) == 0
    assert geo.wrap_deg_180(180) == 180
    assert geo.wrap_deg_180(181) == pytest.approx(-179)
    assert geo.wrap_deg_180(-181) == pytest.approx(179)
    assert geo.wrap_deg_180(359) == pytest.approx(-1)


# ---------------------------------------------------------------------------
# rotate_vector_cw — the sign convention everything else depends on
# ---------------------------------------------------------------------------


def test_rotate_up_90_clockwise_gives_right():
    # "up" on screen = (0, -1) in pixel coords (y grows downward)
    up = (0.0, -1.0)
    result = geo.rotate_vector_cw(*up, degrees=90.0)
    approx_point(result, (1.0, 0.0))  # "right"


def test_rotate_right_90_clockwise_gives_down():
    right = (1.0, 0.0)
    result = geo.rotate_vector_cw(*right, degrees=90.0)
    approx_point(result, (0.0, 1.0))  # "down"


def test_rotate_zero_degrees_is_identity():
    v = (3.0, -4.0)
    approx_point(geo.rotate_vector_cw(*v, degrees=0.0), v)


def test_rotate_negative_degrees_is_counterclockwise():
    # rotating "up" by -90 (i.e. 90 CCW) should give "left"
    up = (0.0, -1.0)
    result = geo.rotate_vector_cw(*up, degrees=-90.0)
    approx_point(result, (-1.0, 0.0))


def test_rotate_360_is_identity():
    v = (12.3, -45.6)
    approx_point(geo.rotate_vector_cw(*v, degrees=360.0), v)


# ---------------------------------------------------------------------------
# target_position_px — the four cardinal targets
# ---------------------------------------------------------------------------


def test_target_positions_cardinal():
    approx_point(geo.target_position_px(0, PARAMS), (700.0, 0.0))    # right
    approx_point(geo.target_position_px(90, PARAMS), (0.0, -700.0))  # up
    approx_point(geo.target_position_px(180, PARAMS), (-700.0, 0.0))  # left
    approx_point(geo.target_position_px(270, PARAMS), (0.0, 700.0))  # down


def test_heading_angle_matches_target_position_round_trip():
    for angle in [0, 30, 90, 137, 180, 270, 359]:
        pos = geo.target_position_px(angle, PARAMS)
        recovered = geo.heading_angle_deg((0.0, 0.0), pos)
        assert recovered == pytest.approx(angle % 360, abs=1e-6)


# ---------------------------------------------------------------------------
# apply_visuomotor_rotation — ties rotation sign to the task's compensation
# ---------------------------------------------------------------------------


def test_rotation_shifts_displayed_heading_by_rotation_deg():
    """If a raw movement points at angle theta, and the display is rotated
    `rotation_deg` clockwise, the displayed cursor should appear at
    (theta - rotation_deg), per this module's convention."""
    target_angle = 90.0
    rotation_deg = 60.0
    raw_vector = geo.target_position_px(target_angle, PARAMS)  # aimed straight at target
    displayed_vector = geo.apply_visuomotor_rotation(raw_vector, rotation_deg)
    displayed_angle = geo.heading_angle_deg((0.0, 0.0), displayed_vector)
    assert displayed_angle == pytest.approx(geo.wrap_deg_360(target_angle - rotation_deg))


def test_ccw_compensation_lands_on_target_under_cw_rotation():
    """This is the core sanity check for the task: under a 60 deg clockwise
    rotation, aiming 60 deg counterclockwise of the target (i.e. at
    target_angle + 60) must make the displayed cursor land exactly on the
    target."""
    target_angle = 0.0
    rotation_deg = 60.0
    compensatory_raw_angle = target_angle + rotation_deg  # CCW of target
    raw_vector = geo.target_position_px(compensatory_raw_angle, PARAMS)
    displayed_vector = geo.apply_visuomotor_rotation(raw_vector, rotation_deg)
    displayed_pos = (PARAMS.home_x_px + displayed_vector[0], PARAMS.home_y_px + displayed_vector[1])
    target_pos = geo.target_position_px(target_angle, PARAMS)
    assert geo.distance(displayed_pos, target_pos) < 1e-6
    assert geo.hit_test(displayed_pos, target_pos, PARAMS)


# ---------------------------------------------------------------------------
# signed_angular_error_deg
# ---------------------------------------------------------------------------


def test_signed_angular_error_clockwise_is_positive():
    # heading is 10 deg clockwise of target (lower angle in our convention)
    target = 90.0
    heading = 80.0
    assert geo.signed_angular_error_deg(heading, target) == pytest.approx(10.0)


def test_signed_angular_error_counterclockwise_is_negative():
    target = 90.0
    heading = 100.0
    assert geo.signed_angular_error_deg(heading, target) == pytest.approx(-10.0)


def test_signed_angular_error_wraps_correctly():
    # target at 5 deg, heading at 355 deg: going clockwise (decreasing
    # angle) from 5, 5 - 10 = -5 == 355 (mod 360) -> heading is 10 deg
    # clockwise of target, so the error should be +10, not -10.
    assert geo.signed_angular_error_deg(355.0, 5.0) == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# landmarks
# ---------------------------------------------------------------------------


def test_landmark_zero_is_target_direction():
    angle = geo.landmark_absolute_angle_deg(0, target_angle_deg=45.0, params=PARAMS)
    assert angle == pytest.approx(45.0)


def test_landmark_positive_is_clockwise_from_target():
    # +1 landmark should be 5.625 deg clockwise (lower angle) of a 90 deg target
    angle = geo.landmark_absolute_angle_deg(1, target_angle_deg=90.0, params=PARAMS)
    assert angle == pytest.approx(90.0 - 5.625)


def test_landmark_negative_is_counterclockwise_from_target():
    angle = geo.landmark_absolute_angle_deg(-1, target_angle_deg=90.0, params=PARAMS)
    assert angle == pytest.approx(90.0 + 5.625)


@pytest.mark.parametrize(
    "magnitude,side,expected_signed",
    [(0, "CW", 0), (12, "CW", 12), (12, "CCW", -12), (31, "CCW", -31)],
)
def test_magnitude_side_round_trip(magnitude, side, expected_signed):
    signed = geo.magnitude_side_to_signed(magnitude, side)
    assert signed == expected_signed
    back_magnitude, back_side = geo.signed_to_magnitude_side(signed)
    assert back_magnitude == magnitude
    if magnitude != 0:
        assert back_side == side


def test_magnitude_side_rejects_bad_side():
    with pytest.raises(ValueError):
        geo.magnitude_side_to_signed(5, "left")


def test_compensatory_landmark_is_negative_for_cw_rotation():
    """Ties the landmark sign convention to the task: under a 60 deg CW
    rotation, the correct compensatory aim (60 deg CCW of target) must map
    to a NEGATIVE (CCW-side) landmark number, matching the participant
    instruction confirmed for this task."""
    target_angle = 0.0
    rotation_deg = 60.0
    compensatory_angle = target_angle + rotation_deg
    # signed_number such that landmark_absolute_angle == compensatory_angle:
    # target - signed*spacing == compensatory  =>  signed = (target - compensatory) / spacing
    signed_number = round((target_angle - compensatory_angle) / PARAMS.landmark_spacing_deg)
    assert signed_number < 0
    magnitude, side = geo.signed_to_magnitude_side(signed_number)
    assert side == "CCW"


# ---------------------------------------------------------------------------
# hit / boundary / onset tests
# ---------------------------------------------------------------------------


def test_hit_test_true_when_touching():
    target_pos = (700.0, 0.0)
    cursor_pos = (700.0 + PARAMS.hit_radius_px - 1.0, 0.0)
    assert geo.hit_test(cursor_pos, target_pos, PARAMS)


def test_hit_test_false_when_far():
    target_pos = (700.0, 0.0)
    cursor_pos = (700.0 + PARAMS.hit_radius_px + 50.0, 0.0)
    assert not geo.hit_test(cursor_pos, target_pos, PARAMS)


def test_boundary_crossed():
    home = (0.0, 0.0)
    assert not geo.boundary_crossed((699.0, 0.0), home, PARAMS)
    assert geo.boundary_crossed((700.0, 0.0), home, PARAMS)
    assert geo.boundary_crossed((900.0, 0.0), home, PARAMS)


def test_movement_onset():
    home = (0.0, 0.0)
    assert not geo.movement_onset((10.0, 0.0), home, PARAMS)  # inside home radius (25px)
    assert geo.movement_onset((30.0, 0.0), home, PARAMS)


# ---------------------------------------------------------------------------
# trajectory analysis
# ---------------------------------------------------------------------------


def _straight_line_trajectory(angle_deg: float, n_points: int = 50, max_r: float = 750.0) -> list[geo.Point]:
    theta = math.radians(angle_deg)
    return [
        (i / n_points * max_r * math.cos(theta), -i / n_points * max_r * math.sin(theta))
        for i in range(1, n_points + 1)
    ]


def test_find_radius_crossing_interpolates():
    traj = _straight_line_trajectory(angle_deg=0.0, n_points=10, max_r=100.0)
    # samples at r = 10, 20, ..., 100; crossing at r=45 should land between
    # the 40 and 50 samples, i.e. at x=45
    crossing = geo.find_radius_crossing(traj, home_px=(0.0, 0.0), radius_px=45.0)
    assert crossing is not None
    assert crossing[0] == pytest.approx(45.0, abs=1e-6)
    assert crossing[1] == pytest.approx(0.0, abs=1e-6)


def test_find_radius_crossing_returns_none_if_never_reached():
    traj = _straight_line_trajectory(angle_deg=0.0, n_points=10, max_r=50.0)
    assert geo.find_radius_crossing(traj, home_px=(0.0, 0.0), radius_px=1000.0) is None


def test_movement_angle_at_fraction_straight_reach():
    target_pos = geo.target_position_px(30.0, PARAMS)
    traj = _straight_line_trajectory(angle_deg=30.0, n_points=200, max_r=PARAMS.home_to_target_px)
    angle = geo.movement_angle_at_fraction(traj, home_px=(0.0, 0.0), target_px=target_pos, fraction=0.5)
    assert angle == pytest.approx(30.0, abs=0.5)


def test_movement_angle_initial_segment_straight_reach():
    traj = _straight_line_trajectory(angle_deg=17.0, n_points=500, max_r=700.0)
    angle = geo.movement_angle_initial_segment(traj, home_px=(0.0, 0.0), r1_px=100.0, r2_px=300.0)
    assert angle == pytest.approx(17.0, abs=0.5)


def test_movement_angle_initial_segment_detects_curved_reach():
    """A trajectory that reaches straight out at one angle and then bends
    to a different final heading should give an initial-segment angle
    matching the START angle, not the end — this is the whole point of
    using the early segment rather than the endpoint/final heading."""
    n = 700
    traj = []
    for i in range(1, n + 1):
        r = float(i)
        # straight at 10 deg out to r=300, then bends to 40 deg for the rest
        angle = 10.0 if r <= 300.0 else 40.0
        theta = math.radians(angle)
        traj.append((r * math.cos(theta), -r * math.sin(theta)))
    early_angle = geo.movement_angle_initial_segment(traj, home_px=(0.0, 0.0), r1_px=50.0, r2_px=150.0)
    assert early_angle == pytest.approx(10.0, abs=0.5)
