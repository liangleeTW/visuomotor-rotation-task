"""
Typed loader for config.yaml.

Flags:
    (none — this module is imported, not run directly)

Usage:
    from vmr.config import load_config
    cfg = load_config()                       # loads ./config.yaml
    cfg = load_config("/path/to/config.yaml")  # explicit path
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


@dataclass(frozen=True)
class WorkspaceConfig:
    home_to_target_cm: float
    workspace_boundary_cm: float
    cursor_radius_mm: float
    home_radius_mm: float
    target_radius_mm: float
    hit_radius_mm: float


@dataclass(frozen=True)
class TargetsConfig:
    angles_deg: tuple[float, ...]


@dataclass(frozen=True)
class LandmarksConfig:
    n_positions: int
    spacing_deg: float
    max_magnitude: int


@dataclass(frozen=True)
class RotationConfig:
    adaptation_deg: float
    adaptation_direction: str
    report_training_range_deg: tuple[float, float]


@dataclass(frozen=True)
class TimingConfig:
    inter_trial_interval_ms: int
    home_hold_ms: int
    target_timeout_ms: int
    end_feedback_duration_ms: int
    report_timeout_ms: int | None


@dataclass(frozen=True)
class FeedbackSpeedBandConfig:
    good_min_ms: int
    good_max_ms: int


@dataclass(frozen=True)
class AdaptationCounts:
    regular_per_cycle: int
    aim_report_per_cycle: int
    return_to_baseline_per_cycle: int
    n_cycles: int


@dataclass(frozen=True)
class BaselineCounts:
    veridical: int
    no_vision: int
    report_training: int


@dataclass(frozen=True)
class PostAdaptationCounts:
    exclusion: int
    readaptation: int
    inclusion: int
    order: tuple[str, ...]


@dataclass(frozen=True)
class TrialCountsConfig:
    familiarization: int
    baseline: BaselineCounts
    adaptation: AdaptationCounts
    post_adaptation: PostAdaptationCounts


@dataclass(frozen=True)
class AudioConfig:
    go_beep: str
    hit_bell: str
    miss_buzz: str


@dataclass(frozen=True)
class ReportEntryConfig:
    magnitude_range: tuple[int, int]


@dataclass(frozen=True)
class ColorsConfig:
    background: tuple[int, int, int]
    home: tuple[int, int, int]
    cursor: tuple[int, int, int]
    target_default: tuple[int, int, int]
    hit_good: tuple[int, int, int]
    hit_too_fast: tuple[int, int, int]
    hit_too_slow: tuple[int, int, int]
    landmark: tuple[int, int, int]
    instruction_text: tuple[int, int, int]


@dataclass(frozen=True)
class Config:
    workspace: WorkspaceConfig
    targets: TargetsConfig
    landmarks: LandmarksConfig
    rotation: RotationConfig
    timing: TimingConfig
    feedback_speed_band: FeedbackSpeedBandConfig
    trial_counts: TrialCountsConfig
    audio: AudioConfig
    report_entry: ReportEntryConfig
    colors: ColorsConfig
    raw: dict = field(repr=False)  # full parsed YAML, for anything not modeled above


def load_config(path: str | Path | None = None) -> Config:
    """Load and validate config.yaml into a typed Config object.

    Raises FileNotFoundError if the file is missing, and KeyError/TypeError
    (with the offending key in the message) if a required field is missing
    or malformed — this loader fails loudly rather than silently defaulting,
    per project convention (a wrong default here would corrupt every trial).
    """
    path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"config file not found: {path}")

    with path.open() as f:
        raw = yaml.safe_load(f)

    try:
        workspace = WorkspaceConfig(**raw["workspace"])
        targets = TargetsConfig(angles_deg=tuple(raw["targets"]["angles_deg"]))
        landmarks = LandmarksConfig(**raw["landmarks"])
        rotation = RotationConfig(
            adaptation_deg=raw["rotation"]["adaptation_deg"],
            adaptation_direction=raw["rotation"]["adaptation_direction"],
            report_training_range_deg=tuple(raw["rotation"]["report_training_range_deg"]),
        )
        t = raw["timing_ms"]
        timing = TimingConfig(
            inter_trial_interval_ms=t["inter_trial_interval"],
            home_hold_ms=t["home_hold"],
            target_timeout_ms=t["target_timeout"],
            end_feedback_duration_ms=t["end_feedback_duration"],
            report_timeout_ms=t["report_timeout"],
        )
        fb = raw["feedback_speed_band_ms"]
        feedback_speed_band = FeedbackSpeedBandConfig(
            good_min_ms=fb["good_min"], good_max_ms=fb["good_max"]
        )
        tc = raw["trial_counts"]
        trial_counts = TrialCountsConfig(
            familiarization=tc["familiarization"],
            baseline=BaselineCounts(**tc["baseline"]),
            adaptation=AdaptationCounts(**tc["adaptation"]),
            post_adaptation=PostAdaptationCounts(
                exclusion=tc["post_adaptation"]["exclusion"],
                readaptation=tc["post_adaptation"]["readaptation"],
                inclusion=tc["post_adaptation"]["inclusion"],
                order=tuple(tc["post_adaptation"]["order"]),
            ),
        )
        audio = AudioConfig(**raw["audio"])
        report_entry = ReportEntryConfig(
            magnitude_range=tuple(raw["report_entry"]["magnitude_range"]),
        )
        colors = ColorsConfig(**{k: tuple(v) for k, v in raw["colors"].items()})
    except KeyError as e:
        raise KeyError(f"config.yaml missing required key: {e}") from e

    if rotation.adaptation_direction != "clockwise":
        raise ValueError(
            "rotation.adaptation_direction must be 'clockwise' — the sign "
            "convention throughout vmr.geometry assumes positive rotation_deg "
            "means clockwise; a different value here would silently invert it"
        )

    if abs(workspace.hit_radius_mm - (workspace.target_radius_mm + workspace.cursor_radius_mm)) > 1e-9:
        raise ValueError(
            "workspace.hit_radius_mm does not equal target_radius_mm + "
            "cursor_radius_mm — if this is intentional (a non-geometric hit "
            "radius), update this check; otherwise fix config.yaml"
        )

    return Config(
        workspace=workspace,
        targets=targets,
        landmarks=landmarks,
        rotation=rotation,
        timing=timing,
        feedback_speed_band=feedback_speed_band,
        trial_counts=trial_counts,
        audio=audio,
        report_entry=report_entry,
        colors=colors,
        raw=raw,
    )
