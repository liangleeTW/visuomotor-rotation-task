"""
Incremental CSV writers for trial-level and sample-level data, plus
per-session config/schedule snapshotting.

Each trial's row(s) are written and fsync'd as soon as the trial finishes
(during the ITI, never mid-reach) — a crash loses at most the in-flight
trial, never the whole session. See caution.md and todo.md section 9.

Flags:
    (none — this module is imported, not run directly)

Usage:
    poetry run pytest tests/test_logging_io.py -v
"""

from __future__ import annotations

import csv
import os
from dataclasses import asdict, fields
from pathlib import Path

import yaml

from vmr.trial import SampleRecord, TrialResult


class TrialLogger:
    """Appends to trials.csv / samples.csv, creating them (with a header)
    if they don't already exist. Safe to re-open across a resumed session:
    an existing non-empty file is appended to without rewriting its header.
    """

    def __init__(self, trials_path: str | Path, samples_path: str | Path):
        self.trials_path = Path(trials_path)
        self.samples_path = Path(samples_path)
        self._trial_fieldnames = ["global_trial_index", "seed", *[f.name for f in fields(TrialResult)]]
        self._sample_fieldnames = ["global_trial_index", *[f.name for f in fields(SampleRecord)]]
        self._trials_file = self._open_with_header(self.trials_path, self._trial_fieldnames)
        self._samples_file = self._open_with_header(self.samples_path, self._sample_fieldnames)
        self._trials_writer = csv.DictWriter(self._trials_file, fieldnames=self._trial_fieldnames)
        self._samples_writer = csv.DictWriter(self._samples_file, fieldnames=self._sample_fieldnames)

    @staticmethod
    def _open_with_header(path: Path, fieldnames: list[str]):
        path.parent.mkdir(parents=True, exist_ok=True)
        needs_header = not path.exists() or path.stat().st_size == 0
        f = open(path, "a", newline="")
        if needs_header:
            csv.DictWriter(f, fieldnames=fieldnames).writeheader()
            f.flush()
            os.fsync(f.fileno())
        return f

    def log_trial(self, global_trial_index: int, seed: int, result: TrialResult, samples: list[SampleRecord]) -> None:
        row = {"global_trial_index": global_trial_index, "seed": seed, **asdict(result)}
        self._trials_writer.writerow(row)
        self._trials_file.flush()
        os.fsync(self._trials_file.fileno())

        for sample in samples:
            self._samples_writer.writerow({"global_trial_index": global_trial_index, **asdict(sample)})
        self._samples_file.flush()
        os.fsync(self._samples_file.fileno())

    def close(self) -> None:
        self._trials_file.close()
        self._samples_file.close()

    def __enter__(self) -> "TrialLogger":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()


def save_config_snapshot(raw_config: dict, path: str | Path) -> None:
    """Write the exact config used for a session alongside its data, so
    the session remains interpretable even if config.yaml changes later."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.safe_dump(raw_config, f, sort_keys=False)
