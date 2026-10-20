"""
QC notebook: loads one subject/block's logged data and gives a first-pass
read on data quality — hit rate, timing distributions, trajectory shapes,
any report trials that were skipped or came back empty, and report
trials where the participant drifted off home before the go signal.

Flags (set the mo.ui.text default values below, or edit them interactively
via `marimo edit`):
    data_dir    Root directory holding session data (default: "data")
    subject     Subject ID folder name (default: "S01")
    block       One of familiarization / baseline / adaptation / post_adaptation

Usage:
    poetry run marimo edit notebooks/check_session.py     # interactive
    poetry run python notebooks/check_session.py           # one-shot printout
"""

import marimo

__generated_with = "0.9.34"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    from pathlib import Path

    return Path, mo, pd


@app.cell
def _(mo):
    data_dir = mo.ui.text(value="data", label="data_dir")
    subject = mo.ui.text(value="S01", label="subject")
    block = mo.ui.text(value="baseline", label="block")
    mo.vstack([data_dir, subject, block])
    return block, data_dir, subject


@app.cell
def _(Path, block, data_dir, pd, subject):
    session_dir = Path(data_dir.value) / subject.value / block.value
    trials_path = session_dir / "trials.csv"
    samples_path = session_dir / "samples.csv"

    if not trials_path.exists():
        trials = pd.DataFrame()
        samples = pd.DataFrame()
        print(f"No data found at {trials_path} yet.")
    else:
        trials = pd.read_csv(trials_path)
        samples = pd.read_csv(samples_path) if samples_path.exists() else pd.DataFrame()
        print(f"Loaded {len(trials)} trials, {len(samples)} samples from {session_dir}")
    return samples, session_dir, trials


@app.cell
def _(mo, trials):
    if trials.empty:
        mo.md("_(no trials to summarize)_")
    else:
        summary = trials.groupby("trial_type").agg(
            n=("trial_index", "count"),
            hit_rate=("end_reason", lambda s: (s == "hit").mean()),
            mean_movement_time_ms=("movement_time_ms", "mean"),
        )
        mo.ui.table(summary.reset_index())
    return


@app.cell
def _(mo, trials):
    # flag report trials with no recorded report (experimenter never
    # confirmed, or the trial ended some other way before REPORT_WAIT
    # completed) — these need a second look before analysis
    report_types = {"baseline_report_training", "adaptation_report"}
    if trials.empty:
        mo.md("_(no trials)_")
    else:
        missing_reports = trials[
            trials["trial_type"].isin(report_types) & trials["reported_number"].isna()
        ]
        if len(missing_reports):
            mo.md(f"**{len(missing_reports)} report trial(s) missing a reported_number:**")
            mo.ui.table(missing_reports[["trial_index", "trial_type", "end_reason"]])
        else:
            mo.md("All report trials have a recorded report. ✓")
    return


@app.cell
def _(mo, trials):
    # flag report trials where the (hidden) cursor left home while the
    # report was being entered — the participant may have started moving
    # early. The cursor is put back on home at SPACE either way
    # (to-decide.md #35); this is for judging whether to exclude the trial.
    drift_threshold_mm = 2.5  # = home radius (config.yaml workspace.home_radius_mm)
    if trials.empty or "report_wait_max_drift_mm" not in trials:
        mo.md("_(no report-wait drift data)_")
    else:
        drifted = trials[trials["report_wait_max_drift_mm"] > drift_threshold_mm]
        if len(drifted):
            mo.md(f"**{len(drifted)} report trial(s) drifted off home during the report:**")
            mo.ui.table(drifted[["trial_index", "trial_type", "report_wait_max_drift_mm"]])
        else:
            mo.md("No report trial drifted off home during the report. ✓")
    return


@app.cell
def _(mo, samples, trials):
    import matplotlib.pyplot as plt

    if trials.empty or samples.empty:
        mo.md("_(no trajectories to plot)_")
        fig = None
    else:
        fig, ax = plt.subplots(figsize=(6, 6))
        for gti, group in samples.groupby("global_trial_index"):
            end_reason = trials.loc[trials["trial_index"] == gti, "end_reason"]
            color = {"hit": "tab:green", "boundary": "tab:red", "timeout": "tab:orange"}.get(
                end_reason.iloc[0] if len(end_reason) else None, "gray"
            )
            ax.plot(group["raw_x"], group["raw_y"], color=color, alpha=0.5, linewidth=1)
        ax.set_aspect("equal")
        ax.set_title("Raw trajectories (green=hit, red=boundary, orange=timeout)")
        ax.invert_yaxis()  # screen y grows downward
    fig
    return


if __name__ == "__main__":
    app.run()
