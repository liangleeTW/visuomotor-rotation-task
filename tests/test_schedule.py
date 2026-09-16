"""
Unit tests for vmr.schedule.

Flags:
    (none — run with pytest)

Usage:
    poetry run pytest tests/test_schedule.py -v
"""

from collections import Counter

import pandas as pd
import pytest

from vmr.config import load_config
from vmr.schedule import build_schedule

CFG = load_config()


@pytest.fixture
def schedule():
    return build_schedule(CFG, seed=12345)


# ---------------------------------------------------------------------------
# Trial counts — must match spec exactly
# ---------------------------------------------------------------------------


def test_total_trial_count(schedule):
    bc = CFG.trial_counts.baseline
    ac = CFG.trial_counts.adaptation
    pc = CFG.trial_counts.post_adaptation
    expected = (
        CFG.trial_counts.familiarization
        + bc.veridical + bc.no_vision + bc.report_training
        + ac.n_cycles * (ac.regular_per_cycle + ac.aim_report_per_cycle + ac.return_to_baseline_per_cycle)
        + pc.exclusion + pc.readaptation + pc.inclusion
    )
    assert len(schedule.trials) == expected


def test_counts_by_type(schedule):
    counts = schedule.counts_by_type()
    bc = CFG.trial_counts.baseline
    ac = CFG.trial_counts.adaptation
    pc = CFG.trial_counts.post_adaptation
    assert counts["familiarization"] == CFG.trial_counts.familiarization
    assert counts["baseline_veridical"] == bc.veridical
    assert counts["baseline_no_vision"] == bc.no_vision
    assert counts["baseline_report_training"] == bc.report_training
    assert counts["adaptation_regular"] == ac.n_cycles * ac.regular_per_cycle
    assert counts["adaptation_report"] == ac.n_cycles * ac.aim_report_per_cycle
    assert counts["adaptation_return_to_baseline"] == ac.n_cycles * ac.return_to_baseline_per_cycle
    assert counts["post_exclusion"] == pc.exclusion
    assert counts["post_readaptation"] == pc.readaptation
    assert counts["post_inclusion"] == pc.inclusion


# ---------------------------------------------------------------------------
# Target balance
# ---------------------------------------------------------------------------


def test_familiarization_targets_exactly_balanced(schedule):
    fam = schedule.by_phase("familiarization")
    counts = Counter(t.target_angle_deg for t in fam)
    assert set(counts.values()) == {4}  # 16 trials / 4 targets, evenly divisible


def test_baseline_veridical_targets_nearly_balanced(schedule):
    veridical = [t for t in schedule.trials if t.trial_type == "baseline_veridical"]
    counts = Counter(t.target_angle_deg for t in veridical)
    assert sum(counts.values()) == 34
    assert max(counts.values()) - min(counts.values()) <= 1


def test_adaptation_return_to_baseline_each_target_once_per_cycle(schedule):
    rtb = [t for t in schedule.trials if t.trial_type == "adaptation_return_to_baseline" and t.cycle_index == 0]
    counts = Counter(t.target_angle_deg for t in rtb)
    assert set(counts.values()) == {1}  # spec: "each target appears once"


# ---------------------------------------------------------------------------
# rotation_deg per trial type
# ---------------------------------------------------------------------------


def test_rotation_values_by_type(schedule):
    for t in schedule.trials:
        if t.trial_type == "familiarization":
            assert t.rotation_deg == 0.0
        elif t.trial_type == "baseline_veridical":
            assert t.rotation_deg == 0.0
        elif t.trial_type == "baseline_no_vision":
            assert t.rotation_deg is None
        elif t.trial_type == "baseline_report_training":
            lo, hi = CFG.rotation.report_training_range_deg
            assert lo <= t.rotation_deg <= hi
        elif t.trial_type in ("adaptation_regular", "adaptation_report", "post_readaptation"):
            assert t.rotation_deg == CFG.rotation.adaptation_deg
        elif t.trial_type in ("adaptation_return_to_baseline", "post_exclusion", "post_inclusion"):
            assert t.rotation_deg is None


def test_cursor_visibility_by_type(schedule):
    invisible_types = {"baseline_no_vision", "adaptation_return_to_baseline", "post_exclusion", "post_inclusion"}
    for t in schedule.trials:
        expected_visible = t.trial_type not in invisible_types
        assert t.cursor_visible_during_movement == expected_visible


# ---------------------------------------------------------------------------
# reproducibility
# ---------------------------------------------------------------------------


def test_same_seed_gives_identical_schedule():
    s1 = build_schedule(CFG, seed=42)
    s2 = build_schedule(CFG, seed=42)
    assert [(t.trial_type, t.target_angle_deg, t.rotation_deg) for t in s1.trials] == [
        (t.trial_type, t.target_angle_deg, t.rotation_deg) for t in s2.trials
    ]


def test_different_seeds_give_different_order():
    s1 = build_schedule(CFG, seed=1)
    s2 = build_schedule(CFG, seed=2)
    order1 = [t.trial_type for t in s1.trials]
    order2 = [t.trial_type for t in s2.trials]
    assert order1 != order2


def test_no_seed_still_records_one(schedule=None):
    s = build_schedule(CFG)
    assert isinstance(s.seed, int)


# ---------------------------------------------------------------------------
# instruction timing (to-decide.md #26)
# ---------------------------------------------------------------------------


def test_familiarization_instruction_shown_once(schedule):
    fam = schedule.by_phase("familiarization")
    assert fam[0].show_instruction is True
    assert all(t.show_instruction is False for t in fam[1:])


def test_baseline_instruction_shown_once_for_whole_phase(schedule):
    baseline = schedule.by_phase("baseline")
    assert baseline[0].show_instruction is True
    assert all(t.show_instruction is False for t in baseline[1:])


def test_adaptation_report_and_rtb_instructions_shown_every_time(schedule):
    for t in schedule.trials:
        if t.trial_type in ("adaptation_report", "adaptation_return_to_baseline"):
            assert t.show_instruction is True
        if t.trial_type == "adaptation_regular":
            assert t.show_instruction is False


def test_post_adaptation_instruction_shown_once_per_contiguous_block(schedule):
    post = schedule.by_phase("post_adaptation")
    shown = [t for t in post if t.show_instruction]
    # exclusion and inclusion each have spec-quoted instruction text and are
    # shown once; re-adaptation has no distinct instruction (to-decide.md #27)
    assert len(shown) == 2
    assert [t.trial_type for t in shown] == ["post_exclusion", "post_inclusion"]
    # and each is the first trial of its contiguous run
    for i, t in enumerate(post):
        if t.show_instruction:
            assert i == 0 or post[i - 1].trial_type != t.trial_type


# ---------------------------------------------------------------------------
# probe_index / cycle_index bookkeeping
# ---------------------------------------------------------------------------


def test_probe_index_resets_and_increments_within_cycle(schedule):
    for cycle in range(CFG.trial_counts.adaptation.n_cycles):
        reports = [
            t for t in schedule.trials if t.trial_type == "adaptation_report" and t.cycle_index == cycle
        ]
        assert [t.probe_index for t in reports] == list(range(len(reports)))


def test_non_adaptation_trials_have_no_cycle_index(schedule):
    for t in schedule.trials:
        if t.phase != "adaptation":
            assert t.cycle_index is None
            assert t.probe_index is None


# ---------------------------------------------------------------------------
# CSV serialization
# ---------------------------------------------------------------------------


def test_to_dataframe_matches_trial_count(schedule):
    df = schedule.to_dataframe()
    assert len(df) == len(schedule.trials)
    assert list(df["global_trial_index"]) == list(range(len(df)))
    assert (df["seed"] == schedule.seed).all()


def test_save_csv_round_trips(schedule, tmp_path):
    path = tmp_path / "schedule.csv"
    schedule.save_csv(path)
    assert path.exists()
    reloaded = pd.read_csv(path)
    assert len(reloaded) == len(schedule.trials)
    assert list(reloaded["trial_type"]) == [t.trial_type for t in schedule.trials]
