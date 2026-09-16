"""
Builds the pseudorandom trial schedule for one session, seeded and
reproducible.

Randomization policy (to-decide.md #5/#6, "pure random for now"):
    - Target angle assignment is balanced-pseudorandom: within each group of
      trials that shares a target pool, targets are drawn from repeated
      shuffled copies of the full angle list, so counts stay as even as
      possible (this is what the spec's own "pseudorandom_order: true"
      already means, independent of the later "no extra constraints"
      decision).
    - Trial-*type* composition within a mixed group (e.g. which of the 40
      baseline trials are no-vision, or which of the 48 adaptation-cycle
      trials are report/return-to-baseline probes) is a single full
      shuffle — no additional constraints (no minimum spacing, no "not in
      the first N", etc.), per the "pure random" decision.

Instruction-screen timing (to-decide.md #26): the spec is explicit that
some instructions repeat before every occurrence of a trial type
("Presented before each Return-to-baseline probe block"; the report-trial
reminder has the same character — it must repeat because report trials are
scattered among ordinary ones), while others are shown once for a whole
contiguous block (baseline's single combined instruction; each 16-trial
post-adaptation sub-block). TrialSpec.show_instruction encodes this
per-trial so the trial runner doesn't need to re-derive it.

Flags:
    (none — this module is imported, not run directly)

Usage:
    poetry run pytest tests/test_schedule.py -v
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd

from vmr.config import Config

# trial_type -> (phase, rotation source, cursor_visible, needs_report, instruction_key, instruction_scope)
# instruction_scope: "once_per_phase" | "once_per_trial" | "once_per_block" | None
_FIXED_ROTATION = "fixed"
_NO_ROTATION = "none"
_RANDOM_ROTATION = "random"

_TRIAL_TYPE_SPEC = {
    "familiarization": ("familiarization", _NO_ROTATION, True, False, "familiarization", "once_per_phase"),
    "baseline_veridical": ("baseline", _NO_ROTATION, True, False, "baseline", "once_per_phase"),
    "baseline_no_vision": ("baseline", None, False, False, "baseline", "once_per_phase"),
    "baseline_report_training": ("baseline", _RANDOM_ROTATION, True, True, "baseline", "once_per_phase"),
    "adaptation_regular": ("adaptation", _FIXED_ROTATION, True, False, None, None),
    "adaptation_report": ("adaptation", _FIXED_ROTATION, True, True, "adaptation_report", "once_per_trial"),
    "adaptation_return_to_baseline": (
        "adaptation",
        None,
        False,
        False,
        "adaptation_return_to_baseline",
        "once_per_trial",
    ),
    "post_exclusion": ("post_adaptation", None, False, False, "post_exclusion", "once_per_block"),
    "post_readaptation": ("post_adaptation", _FIXED_ROTATION, True, False, "post_readaptation", "once_per_block"),
    "post_inclusion": ("post_adaptation", None, False, False, "post_inclusion", "once_per_block"),
}


@dataclass
class TrialSpec:
    phase: str
    trial_type: str
    trial_index: int  # 0-based within phase
    target_angle_deg: float
    rotation_deg: float | None
    cursor_visible_during_movement: bool
    needs_report: bool
    show_instruction: bool
    instruction_key: str | None
    cycle_index: int | None = None
    probe_index: int | None = None


@dataclass
class Schedule:
    seed: int
    trials: list[TrialSpec] = field(default_factory=list)

    def by_phase(self, phase: str) -> list[TrialSpec]:
        return [t for t in self.trials if t.phase == phase]

    def counts_by_type(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for t in self.trials:
            counts[t.trial_type] = counts.get(t.trial_type, 0) + 1
        return counts

    def to_dataframe(self) -> pd.DataFrame:
        """Full schedule as a DataFrame, one row per trial, with a global
        0-based `global_trial_index` column added on top of each trial's
        phase-local `trial_index`."""
        rows = [dict(asdict(t), seed=self.seed) for t in self.trials]
        df = pd.DataFrame(rows)
        df.insert(0, "global_trial_index", range(len(df)))
        return df

    def save_csv(self, path: str | Path) -> None:
        """Write the schedule to CSV before the session starts, so the
        exact trial order is inspectable/reproducible independent of the
        runtime (todo.md section 3)."""
        self.to_dataframe().to_csv(path, index=False)


def balanced_pseudorandom_targets(rng: random.Random, angles: list[float], count: int) -> list[float]:
    """Return `count` target angles drawn from repeated, independently
    shuffled copies of `angles`, keeping each angle's count as even as
    possible (differs by at most 1 across angles)."""
    result: list[float] = []
    full_cycles, remainder = divmod(count, len(angles))
    for _ in range(full_cycles):
        cycle = list(angles)
        rng.shuffle(cycle)
        result.extend(cycle)
    if remainder:
        leftover = list(angles)
        rng.shuffle(leftover)
        result.extend(leftover[:remainder])
    return result


def _make_trial(
    trial_type: str,
    trial_index: int,
    target_angle_deg: float,
    rotation_deg: float | None,
    is_first_of_contiguous_run: bool,
    is_first_trial_in_phase: bool,
    cycle_index: int | None = None,
    probe_index: int | None = None,
) -> TrialSpec:
    phase, _, cursor_visible, needs_report, instruction_key, scope = _TRIAL_TYPE_SPEC[trial_type]
    if scope == "once_per_phase":
        show_instruction = is_first_trial_in_phase
    elif scope == "once_per_trial":
        show_instruction = True
    elif scope == "once_per_block":
        show_instruction = is_first_of_contiguous_run
    else:
        show_instruction = False
    return TrialSpec(
        phase=phase,
        trial_type=trial_type,
        trial_index=trial_index,
        target_angle_deg=target_angle_deg,
        rotation_deg=rotation_deg,
        cursor_visible_during_movement=cursor_visible,
        needs_report=needs_report,
        show_instruction=show_instruction,
        instruction_key=instruction_key if show_instruction else None,
        cycle_index=cycle_index,
        probe_index=probe_index,
    )


def build_familiarization(cfg: Config, rng: random.Random) -> list[TrialSpec]:
    count = cfg.trial_counts.familiarization
    angles = balanced_pseudorandom_targets(rng, list(cfg.targets.angles_deg), count)
    return [
        _make_trial("familiarization", i, angles[i], rotation_deg=0.0, is_first_of_contiguous_run=(i == 0), is_first_trial_in_phase=(i == 0))
        for i in range(count)
    ]


def build_baseline(cfg: Config, rng: random.Random) -> list[TrialSpec]:
    trials: list[TrialSpec] = []
    bc = cfg.trial_counts.baseline
    angles = list(cfg.targets.angles_deg)

    # Group 1: veridical + no_vision, fully interleaved (pure random label
    # order), each subtype independently target-balanced.
    labels = ["baseline_veridical"] * bc.veridical + ["baseline_no_vision"] * bc.no_vision
    rng.shuffle(labels)
    veridical_targets = iter(balanced_pseudorandom_targets(rng, angles, bc.veridical))
    no_vision_targets = iter(balanced_pseudorandom_targets(rng, angles, bc.no_vision))
    idx = 0
    for label in labels:
        target = next(veridical_targets) if label == "baseline_veridical" else next(no_vision_targets)
        rotation = 0.0 if label == "baseline_veridical" else None
        trials.append(
            _make_trial(label, idx, target, rotation, is_first_of_contiguous_run=(idx == 0), is_first_trial_in_phase=(idx == 0))
        )
        idx += 1

    # Group 2: report training, sequential after group 1 (spec: "後40trial
    # report training"), each trial gets its own random training rotation.
    lo, hi = cfg.rotation.report_training_range_deg
    report_targets = balanced_pseudorandom_targets(rng, angles, bc.report_training)
    for i in range(bc.report_training):
        trials.append(
            _make_trial(
                "baseline_report_training",
                idx,
                report_targets[i],
                rotation_deg=rng.uniform(lo, hi),
                is_first_of_contiguous_run=False,
                is_first_trial_in_phase=False,
            )
        )
        idx += 1

    return trials


def build_adaptation(cfg: Config, rng: random.Random) -> list[TrialSpec]:
    trials: list[TrialSpec] = []
    ac = cfg.trial_counts.adaptation
    angles = list(cfg.targets.angles_deg)
    rotation_deg = cfg.rotation.adaptation_deg
    idx = 0
    for cycle in range(ac.n_cycles):
        labels = (
            ["adaptation_regular"] * ac.regular_per_cycle
            + ["adaptation_report"] * ac.aim_report_per_cycle
            + ["adaptation_return_to_baseline"] * ac.return_to_baseline_per_cycle
        )
        rng.shuffle(labels)

        regular_targets = iter(balanced_pseudorandom_targets(rng, angles, ac.regular_per_cycle))
        report_targets = iter(balanced_pseudorandom_targets(rng, angles, ac.aim_report_per_cycle))
        rtb_targets = iter(balanced_pseudorandom_targets(rng, angles, ac.return_to_baseline_per_cycle))
        probe_counters = {"adaptation_report": 0, "adaptation_return_to_baseline": 0}

        for pos, label in enumerate(labels):
            if label == "adaptation_regular":
                target = next(regular_targets)
                rotation = rotation_deg
                probe_index = None
            elif label == "adaptation_report":
                target = next(report_targets)
                rotation = rotation_deg
                probe_index = probe_counters[label]
                probe_counters[label] += 1
            else:  # adaptation_return_to_baseline
                target = next(rtb_targets)
                rotation = None
                probe_index = probe_counters[label]
                probe_counters[label] += 1

            trials.append(
                _make_trial(
                    label,
                    idx,
                    target,
                    rotation,
                    is_first_of_contiguous_run=False,  # unused for once_per_trial/None scopes here
                    is_first_trial_in_phase=(idx == 0),
                    cycle_index=cycle,
                    probe_index=probe_index,
                )
            )
            idx += 1

    return trials


def build_post_adaptation(cfg: Config, rng: random.Random) -> list[TrialSpec]:
    trials: list[TrialSpec] = []
    pc = cfg.trial_counts.post_adaptation
    angles = list(cfg.targets.angles_deg)
    counts = {"exclusion": pc.exclusion, "readaptation": pc.readaptation, "inclusion": pc.inclusion}
    trial_type_by_key = {
        "exclusion": "post_exclusion",
        "readaptation": "post_readaptation",
        "inclusion": "post_inclusion",
    }
    rotation_by_key = {"exclusion": None, "readaptation": cfg.rotation.adaptation_deg, "inclusion": None}

    idx = 0
    for key in pc.order:  # fixed order, to-decide.md #7
        trial_type = trial_type_by_key[key]
        count = counts[key]
        block_targets = balanced_pseudorandom_targets(rng, angles, count)
        for i in range(count):
            trials.append(
                _make_trial(
                    trial_type,
                    idx,
                    block_targets[i],
                    rotation_by_key[key],
                    is_first_of_contiguous_run=(i == 0),
                    is_first_trial_in_phase=False,  # each sub-block has its own instruction, not phase-level
                )
            )
            idx += 1

    return trials


def build_schedule(cfg: Config, seed: int | None = None) -> Schedule:
    """Build the full session schedule. If `seed` is None, a fresh seed is
    drawn from OS randomness and recorded on the returned Schedule so the
    session remains reproducible after the fact."""
    if seed is None:
        seed = random.SystemRandom().randrange(2**32)
    rng = random.Random(seed)

    trials: list[TrialSpec] = []
    trials.extend(build_familiarization(cfg, rng))
    trials.extend(build_baseline(cfg, rng))
    trials.extend(build_adaptation(cfg, rng))
    trials.extend(build_post_adaptation(cfg, rng))
    return Schedule(seed=seed, trials=trials)
