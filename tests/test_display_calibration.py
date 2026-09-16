"""
Unit tests for vmr.display_calibration (the pure/file-IO parts only —
run_calibration_routine is interactive and exercised manually, per
todo.md section 12/13).

Flags:
    (none — run with pytest)

Usage:
    poetry run pytest tests/test_display_calibration.py -v
"""

import pytest

from vmr.display_calibration import (
    Calibration,
    compute_px_per_cm,
    load_calibration,
    require_calibration,
    save_calibration,
)


def test_compute_px_per_cm():
    assert compute_px_per_cm(1000.0, 10.0) == pytest.approx(100.0)


def test_compute_px_per_cm_rejects_nonpositive_cm():
    with pytest.raises(ValueError):
        compute_px_per_cm(1000.0, 0.0)
    with pytest.raises(ValueError):
        compute_px_per_cm(1000.0, -5.0)


def test_compute_px_per_cm_rejects_nonpositive_pixels():
    with pytest.raises(ValueError):
        compute_px_per_cm(0.0, 10.0)


def test_load_missing_calibration_returns_none(tmp_path):
    assert load_calibration(tmp_path / "nope.json") is None


def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "cal.json"
    cal = Calibration(px_per_cm=123.456, measured_at="2026-09-16T00:00:00Z", display_resolution=(1920, 1080), notes="test")
    save_calibration(cal, path)
    reloaded = load_calibration(path)
    assert reloaded == cal


def test_require_calibration_raises_with_helpful_message(tmp_path):
    with pytest.raises(FileNotFoundError, match="display_calibration"):
        require_calibration(tmp_path / "missing.json")


def test_require_calibration_returns_cached_value(tmp_path):
    path = tmp_path / "cal.json"
    cal = Calibration(px_per_cm=100.0, measured_at="now", display_resolution=(2560, 1600))
    save_calibration(cal, path)
    assert require_calibration(path) == cal
