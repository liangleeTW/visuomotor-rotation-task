"""
Unit tests for vmr.display_calibration (the pure/file-IO/detection parts —
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
    detect_calibration,
    detect_physical_size_mm,
    load_calibration,
    resolve_calibration,
    save_calibration,
)


class _FakeSize:
    def __init__(self, width, height):
        self.width = width
        self.height = height


class _FakeQuartz:
    """Injectable stand-in for the real Quartz module (see
    detect_physical_size_mm's quartz_module parameter)."""

    def __init__(self, width_mm=300.0, height_mm=200.0, raise_error=False):
        self.width_mm = width_mm
        self.height_mm = height_mm
        self.raise_error = raise_error

    def CGMainDisplayID(self):
        if self.raise_error:
            raise RuntimeError("no display attached")
        return 1

    def CGDisplayScreenSize(self, display_id):
        return _FakeSize(self.width_mm, self.height_mm)


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


# ---------------------------------------------------------------------------
# detect_physical_size_mm
# ---------------------------------------------------------------------------


def test_detect_physical_size_mm_plausible():
    result = detect_physical_size_mm(quartz_module=_FakeQuartz(width_mm=344.0, height_mm=193.0))
    assert result == (344.0, 193.0)


def test_detect_physical_size_mm_rejects_too_small():
    result = detect_physical_size_mm(quartz_module=_FakeQuartz(width_mm=1.0, height_mm=1.0))
    assert result is None


def test_detect_physical_size_mm_rejects_too_large():
    result = detect_physical_size_mm(quartz_module=_FakeQuartz(width_mm=5000.0, height_mm=3000.0))
    assert result is None


def test_detect_physical_size_mm_none_on_exception():
    result = detect_physical_size_mm(quartz_module=_FakeQuartz(raise_error=True))
    assert result is None


# ---------------------------------------------------------------------------
# detect_calibration
# ---------------------------------------------------------------------------


def test_detect_calibration_computes_px_per_cm():
    # 254mm wide == 25.4cm; 1000px / 25.4cm ~= 39.37 px/cm
    cal = detect_calibration((1000, 600), quartz_module=_FakeQuartz(width_mm=254.0, height_mm=150.0))
    assert cal is not None
    assert cal.px_per_cm == pytest.approx(39.37, abs=0.01)
    assert cal.display_resolution == (1000, 600)
    assert "auto-detected" in cal.notes


def test_detect_calibration_none_when_detection_fails():
    assert detect_calibration((1000, 600), quartz_module=_FakeQuartz(raise_error=True)) is None


# ---------------------------------------------------------------------------
# resolve_calibration — the entry point sessions actually use
# ---------------------------------------------------------------------------


def test_resolve_calibration_prefers_manual_over_auto(tmp_path):
    path = tmp_path / "cal.json"
    manual = Calibration(px_per_cm=999.0, measured_at="manual", display_resolution=(1000, 600))
    save_calibration(manual, path)
    result = resolve_calibration((1000, 600), path=path, quartz_module=_FakeQuartz(width_mm=254.0, height_mm=150.0))
    assert result == manual  # not the auto-detected ~39.37 px/cm


def test_resolve_calibration_falls_back_to_auto_detection(tmp_path):
    path = tmp_path / "cal.json"  # no manual calibration saved
    result = resolve_calibration((1000, 600), path=path, quartz_module=_FakeQuartz(width_mm=254.0, height_mm=150.0))
    assert result.px_per_cm == pytest.approx(39.37, abs=0.01)
    # auto-detection is not cached to disk (cheap to redo; avoids a stale
    # value surviving a monitor swap)
    assert load_calibration(path) is None


def test_resolve_calibration_raises_with_helpful_message_when_both_unavailable(tmp_path):
    path = tmp_path / "missing.json"
    with pytest.raises(FileNotFoundError, match="display_calibration"):
        resolve_calibration((1000, 600), path=path, quartz_module=_FakeQuartz(raise_error=True))
