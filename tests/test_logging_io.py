"""
Unit tests for vmr.logging_io.

Flags:
    (none — run with pytest)

Usage:
    poetry run pytest tests/test_logging_io.py -v
"""

import csv

import yaml

from vmr.config import load_config
from vmr.logging_io import TrialLogger, save_config_snapshot
from vmr.trial import SampleRecord, TrialResult


def make_result(trial_index=0, end_reason="hit"):
    return TrialResult(
        phase="baseline",
        trial_type="baseline_veridical",
        trial_index=trial_index,
        cycle_index=None,
        probe_index=None,
        target_id=0,
        target_angle_deg=0.0,
        target_x=700.0,
        target_y=0.0,
        rotation_deg=0.0,
        cursor_visible_during_movement=True,
        reported_number=None,
        reported_side=None,
        reported_angle_deg=None,
        report_registered_timestamp=None,
        experimenter_space_timestamp=None,
        target_onset_timestamp=0.5,
        go_signal_timestamp=0.5,
        movement_onset_timestamp=0.55,
        movement_end_timestamp=0.95,
        end_reason=end_reason,
        movement_time_ms=400.0,
        speed_feedback="good",
        movement_angle_at_50pct_reach=1.2,
        movement_angle_initial_segment=1.0,
        report_wait_max_drift_mm=None,
    )


def make_samples(n=3):
    return [SampleRecord(sample_timestamp=i * 0.01, raw_x=i * 10.0, raw_y=0.0, display_x=i * 10.0, display_y=0.0) for i in range(n)]


def test_creates_files_with_header(tmp_path):
    trials_path = tmp_path / "trials.csv"
    samples_path = tmp_path / "samples.csv"
    with TrialLogger(trials_path, samples_path) as logger:
        logger.log_trial(0, seed=42, result=make_result(), samples=make_samples(3))

    with open(trials_path) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["trial_type"] == "baseline_veridical"
    assert rows[0]["global_trial_index"] == "0"
    assert rows[0]["seed"] == "42"

    with open(samples_path) as f:
        srows = list(csv.DictReader(f))
    assert len(srows) == 3
    assert srows[1]["raw_x"] == "10.0"
    assert srows[1]["global_trial_index"] == "0"


def test_appends_across_multiple_trials(tmp_path):
    trials_path = tmp_path / "trials.csv"
    samples_path = tmp_path / "samples.csv"
    with TrialLogger(trials_path, samples_path) as logger:
        for i in range(3):
            logger.log_trial(i, seed=1, result=make_result(trial_index=i), samples=make_samples(2))

    with open(trials_path) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3
    assert [r["trial_index"] for r in rows] == ["0", "1", "2"]

    with open(samples_path) as f:
        srows = list(csv.DictReader(f))
    assert len(srows) == 6


def test_reopening_does_not_duplicate_header(tmp_path):
    trials_path = tmp_path / "trials.csv"
    samples_path = tmp_path / "samples.csv"

    with TrialLogger(trials_path, samples_path) as logger:
        logger.log_trial(0, seed=1, result=make_result(), samples=make_samples(1))

    # simulate resuming a session: a fresh TrialLogger over the same files
    with TrialLogger(trials_path, samples_path) as logger:
        logger.log_trial(1, seed=1, result=make_result(trial_index=1), samples=make_samples(1))

    with open(trials_path) as f:
        lines = f.readlines()
    header_lines = [line for line in lines if line.startswith("global_trial_index,seed,phase")]
    assert len(header_lines) == 1
    with open(trials_path) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2


def test_null_fields_round_trip_as_empty(tmp_path):
    trials_path = tmp_path / "trials.csv"
    samples_path = tmp_path / "samples.csv"
    with TrialLogger(trials_path, samples_path) as logger:
        logger.log_trial(0, seed=1, result=make_result(), samples=[])

    with open(trials_path) as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["reported_number"] == ""
    assert rows[0]["cycle_index"] == ""


def test_flush_persists_immediately(tmp_path):
    trials_path = tmp_path / "trials.csv"
    samples_path = tmp_path / "samples.csv"
    logger = TrialLogger(trials_path, samples_path)
    logger.log_trial(0, seed=1, result=make_result(), samples=make_samples(1))
    # without closing the logger, the data must already be on disk
    with open(trials_path) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    logger.close()


def test_save_config_snapshot_round_trips(tmp_path):
    cfg = load_config()
    path = tmp_path / "config_snapshot.yaml"
    save_config_snapshot(cfg.raw, path)
    reloaded = yaml.safe_load(path.read_text())
    assert reloaded == cfg.raw
