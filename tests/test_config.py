"""
Unit tests for vmr.config.

Flags:
    (none — run with pytest)

Usage:
    poetry run pytest tests/test_config.py -v
"""

import pytest

from vmr.config import load_config


def test_loads_default_config():
    cfg = load_config()
    assert cfg.workspace.home_to_target_cm == 7.0
    assert cfg.targets.angles_deg == (0, 90, 180, 270)
    assert cfg.landmarks.n_positions == 64
    assert cfg.landmarks.spacing_deg == pytest.approx(5.625)
    assert cfg.rotation.adaptation_deg == 60.0
    assert cfg.trial_counts.familiarization == 16
    assert cfg.trial_counts.baseline.veridical == 34
    assert cfg.trial_counts.baseline.no_vision == 6
    assert cfg.trial_counts.baseline.report_training == 40
    assert cfg.trial_counts.adaptation.regular_per_cycle == 40
    assert cfg.trial_counts.adaptation.n_cycles == 1
    assert cfg.trial_counts.post_adaptation.order == ("exclusion", "readaptation", "inclusion")


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/config.yaml")


def test_hit_radius_consistency_check(tmp_path):
    bad = tmp_path / "bad_config.yaml"
    good = load_config()
    text = good.raw
    import copy

    text = copy.deepcopy(text)
    text["workspace"]["hit_radius_mm"] = 999.0  # inconsistent with target+cursor radius
    import yaml

    bad.write_text(yaml.dump(text))
    with pytest.raises(ValueError, match="hit_radius_mm"):
        load_config(bad)


def test_wrong_rotation_direction_rejected(tmp_path):
    bad = tmp_path / "bad_config.yaml"
    good = load_config()
    import copy

    text = copy.deepcopy(good.raw)
    text["rotation"]["adaptation_direction"] = "counterclockwise"
    import yaml

    bad.write_text(yaml.dump(text))
    with pytest.raises(ValueError, match="clockwise"):
        load_config(bad)
