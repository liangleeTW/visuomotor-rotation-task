# Visuomotor Rotation Task

A center-out reaching task with a visuomotor rotation and explicit
aiming reports (Taylor, Krakauer & Ivry, 2014 design), run locally with
pygame. See `spec.pdf` for the original task design and `to-decide.md`
for every design decision made while implementing it.

## Setup

```bash
poetry install
```

Then, **once per machine**, before the first session:

1. Apply the macOS settings in `caution.md` (pointer acceleration,
   trackpad gestures, Do Not Disturb, etc.) and verify pointer
   acceleration is actually off, not just set.
2. Add the audio assets once available (`go_beep.wav`, `hit_bell.wav`,
   `miss_buzz.wav`) to `assets/audio/`. Missing files degrade to silent
   playback with a warning, so the experiment runs without them, but
   real sessions need real sounds.

Display calibration (px/cm) is **automatic** — it's detected from the
display's actual physical size via macOS's own APIs the moment a session
starts, no setup step required. You never need to run anything for this
under normal use. If you ever suspect it's wrong (e.g. on an external
monitor with unusual EDID data — reaches would feel mis-scaled relative
to the intended 7cm distance), you can override it once with a manual
ruler measurement, which then takes precedence permanently until you
delete it:
```bash
poetry run python -m vmr.display_calibration          # saves display_calibration.json
poetry run python -m vmr.display_calibration --recalibrate   # redo it
rm display_calibration.json                             # go back to auto-detection
```
Whichever value was actually used for a session (auto-detected or
manually overridden) is recorded in
`data/<subject>/<block>/calibration_used.json` for that session.

## Running a session

```bash
poetry run python run_block.py                                 # interactive menu (起始畫面)
poetry run python run_block.py --subject S01 --block familiarization
poetry run python run_block.py --subject S01 --block baseline --windowed  # dev/testing, not fullscreen
```

Blocks: `familiarization`, `baseline`, `adaptation`, `post_adaptation`.
Re-running the same `--subject`/`--block` **resumes** automatically —
already-logged trials are skipped, not repeated or overwritten. If that
subject/block already has data, you'll be asked to confirm before it
proceeds (add `--yes` to skip the prompt for a known-good scripted
resume) — see caution.md and to-decide.md #32/#33 for why, and #34 for a
related resume caveat around `--seed`.

**Multi-monitor**: the app opens fullscreen on whichever display is
currently set as **Main Display** in System Settings → Displays →
Arrangement — not necessarily the built-in screen, and not "whichever is
bigger." To run on an external monitor, drag the menu bar to it first
(to-decide.md #31). With only one display connected, there's nothing to
configure.

## Data layout

```
data/<subject_id>/<block_name>/
  trials.csv             one row per trial (see vmr/trial.py::TrialResult)
  samples.csv             one row per recorded input sample
  schedule.csv             the exact trial order generated for this block
  config_snapshot.yaml    the config.yaml used, frozen at session start
```

## Development

```bash
poetry run pytest                              # 130 tests, ~3s, no display needed
poetry run marimo edit notebooks/check_session.py   # QC: hit rate, trajectories, missing reports
poetry run marimo edit notebooks/calibration.py     # QC: calibration status, pointer-accel check, sampling rate
```

Tests run headlessly via pygame's dummy video/audio drivers
(`tests/conftest.py`) — no real screen or sound device required.

## Project layout

```
vmr/
  config.py               typed config.yaml loader
  geometry.py              pure math: positions, rotation, hit tests, trajectory angles
  schedule.py              trial-list generation for all four phases
  trial.py                 the trial state machine (TrialRunner)
  report_entry.py          experimenter's aim-report entry logic
  input_device.py          relative-mouse cursor tracking
  audio.py                 sound loading/playback
  display.py               rendering
  menu.py                  起始畫面 (start screen) logic + rendering
  display_calibration.py   px/cm measurement
  logging_io.py             CSV writers
  orchestration.py          ties everything together (run_block, main)
run_block.py               entry point (thin wrapper around vmr.orchestration.main)
config.yaml                 all experiment parameters
notebooks/                  Marimo QC notebooks
tests/                      130 tests covering every module above
caution.md                  pre-flight checklist and setup gotchas
to-decide.md                every design decision, with rationale and revision status
todo.md                     build plan and status
```

## Known gaps (not blocking, see to-decide.md for details)

- Audio assets not yet added (`to-decide.md`, README setup section above)
- Two transitions have no spec-quoted instruction text and currently show
  none (to-decide.md #27): entering the adaptation phase, and entering
  the post-adaptation re-adaptation sub-block
- Achieved sampling rate not yet measured on real hardware (to-decide.md #17)
- Hit-zone radius and a few other spatial defaults are provisional pending
  pilot testing (to-decide.md #12 and others marked "revisit after pilot")
