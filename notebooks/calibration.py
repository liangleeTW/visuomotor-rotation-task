"""
QC notebook: display calibration status, a live pointer-acceleration
check, and a sampling-rate audit from real session data.

See caution.md — this notebook operationalizes the "verify empirically,
don't trust the OS" checks described there.

Flags:
    data_dir / subject / block   Which session's samples.csv to audit for
                                  achieved sampling rate (set via the UI
                                  text boxes below when running interactively)

Usage:
    poetry run marimo edit notebooks/calibration.py     # interactive, with
                                                          # the live pointer
                                                          # acceleration check
    poetry run python notebooks/calibration.py           # one-shot printout
"""

import marimo

__generated_with = "0.9.34"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    from pathlib import Path

    from vmr.display_calibration import load_calibration

    return Path, load_calibration, mo, pd


@app.cell
def _(load_calibration, mo):
    cal = load_calibration()
    if cal is None:
        mo.md(
            "**No display calibration found.** Run "
            "`poetry run python -m vmr.display_calibration` once on this "
            "machine before starting a session."
        )
    else:
        mo.md(
            f"**Cached calibration**: {cal.px_per_cm:.3f} px/cm, measured "
            f"{cal.measured_at}, at resolution {cal.display_resolution}."
        )
    return


@app.cell
def _(mo):
    mo.md(
        """
        ## Pointer-acceleration check (manual, per caution.md)

        1. Confirm `defaults write -g com.apple.trackpad.scaling -1` has been
           applied and the machine logged out/in since.
        2. Click **Run capture** below, then swipe a fixed physical distance
           on the trackpad *slowly* once, then *quickly* once, within the
           5-second window.
        3. The reported px/sec-independent displacement for both swipes
           should match (within noise) — if the fast swipe travels
           noticeably farther in pixels than the slow one for the same
           physical distance, acceleration is still on.
        """
    )
    return


@app.cell
def _(mo):
    run_capture = mo.ui.run_button(label="Run capture (5s)")
    run_capture
    return (run_capture,)


@app.cell
def _(mo, run_capture):
    if run_capture.value:
        from vmr.input_device import PygameRelativeMouse
        import pygame
        import time

        pygame.init()
        pygame.display.set_mode((400, 300))
        mouse = PygameRelativeMouse()
        mouse.start()
        total_dx = total_dy = 0.0
        n_samples = 0
        start = time.perf_counter()
        while time.perf_counter() - start < 5.0:
            for event in pygame.event.get():
                pass  # drain the queue so the window doesn't appear frozen
            dx, dy = mouse.poll_delta()
            total_dx += dx
            total_dy += dy
            n_samples += 1
        mouse.stop()
        pygame.quit()
        achieved_hz = n_samples / 5.0
        mo.md(
            f"Captured {n_samples} samples over 5s (~{achieved_hz:.0f} Hz). "
            f"Net displacement: ({total_dx:.0f}, {total_dy:.0f}) px."
        )
    else:
        mo.md("_(click the button above to capture)_")
    return


@app.cell
def _(mo):
    data_dir = mo.ui.text(value="data", label="data_dir")
    subject = mo.ui.text(value="S01", label="subject")
    block = mo.ui.text(value="baseline", label="block")
    mo.vstack([data_dir, subject, block])
    return block, data_dir, subject


@app.cell
def _(Path, block, data_dir, mo, pd, subject):
    samples_path = Path(data_dir.value) / subject.value / block.value / "samples.csv"
    if not samples_path.exists():
        mo.md(f"No samples.csv found at {samples_path} yet.")
    else:
        samples = pd.read_csv(samples_path)
        intervals_ms = samples.groupby("global_trial_index")["sample_timestamp"].diff().dropna() * 1000.0
        if len(intervals_ms):
            achieved_hz_from_data = 1000.0 / intervals_ms.median()
            mo.md(
                f"Median inter-sample interval: {intervals_ms.median():.2f} ms "
                f"(~{achieved_hz_from_data:.0f} Hz achieved). "
                f"Range: {intervals_ms.min():.2f}-{intervals_ms.max():.2f} ms."
            )
        else:
            mo.md("Not enough samples to compute an interval distribution yet.")
    return


if __name__ == "__main__":
    app.run()
