# Visuomotor Rotation Task

A center-out reaching task with a visuomotor rotation and explicit
aiming reports (Taylor, Krakauer & Ivry, 2014 design), run locally on a Mac
with pygame. The participant slides a finger on a trackpad, hidden under an
occluder, to move a cursor from the screen centre to a target. In some
blocks the cursor's movement is rotated 60° clockwise relative to the hand,
and on some trials the participant says aloud where they are aiming before
reaching.

Other documents:
- `caution.md`: **read before every session**. Pre-flight checklist and
  setup traps that can silently spoil data.
- `to-decide.md`: design choices that are still open or provisional,
  explained in plain language, to settle with pilot testing.

## Hardware

| Item | Notes |
|---|---|
| Mac running macOS | Screen size and the "Main Display" are detected through macOS APIs. Keep the power adapter connected during sessions. |
| Apple Magic Trackpad 3 | Charged or wired, paired, placed at a fixed marked position on the table. |
| Occluder | Hides the hand and trackpad from the participant. Must not touch the trackpad surface. |
| Headphones | For the go beep, hit bell and miss buzz. |
| Keyboard | Reachable by the **experimenter only**. Used for the start screen, SPACE to continue, and typing aim reports. |
| External monitor (optional) | Must be set as **Main Display** before launch (see [Multi-monitor](#multi-monitor)). |

Several macOS settings (trackpad gestures, pointer acceleration, Do Not
Disturb, True Tone, etc.) **must** be changed before the first session.
They are listed with how to verify them in `caution.md`.

## Software setup

Requirements: Python 3.12 and [Poetry](https://python-poetry.org/).

```bash
git clone <this repo> && cd visuomotor-rotation-task
poetry install                 # installs pygame-ce, pandas, etc. and the vmr package
poetry run pytest -q           # sanity check: all tests should pass, no screen needed
```

The sound files (`go_beep.wav`, `hit_bell.wav`, `miss_buzz.wav`) are already
in `assets/audio/`. If one is missing, the program warns and plays silence
instead of crashing.

**Display calibration (px/cm) is automatic.** Each time a block starts, the
program reads the screen's physical size from macOS and converts the task's
real-world distances (e.g. target 7 cm from home) into pixels. Nothing to
set up. If a monitor reports its size wrongly (reaches feel too long or too
short), override it once with a ruler measurement:

```bash
poetry run python -m vmr.display_calibration                 # saves display_calibration.json
poetry run python -m vmr.display_calibration --recalibrate   # redo it
rm display_calibration.json                                   # go back to auto-detection
```

The value actually used is saved with each session in
`data/<subject>/<block>/calibration_used.json` (see `to-decide.md` #18).

## How the experiment runs

### 1. Overview: four blocks

A full session is four blocks, run in this order. **Each block is a separate
launch** of the program: when a block finishes, the program closes, and the
experimenter launches the next one.

```mermaid
flowchart LR
    F["<b>1. Familiarization</b><br/>16 trials<br/>no rotation<br/>learn the reaching movement"]
    B["<b>2. Baseline</b><br/>80 trials<br/>no consistent rotation<br/>normal + no-cursor trials,<br/>then aim-report practice"]
    A["<b>3. Adaptation</b><br/>48 trials per cycle, 1 cycle<br/>cursor rotated 60° clockwise<br/>with occasional aim-report and<br/>no-cursor test trials"]
    P["<b>4. Post-adaptation</b><br/>48 trials<br/>'don't use adjustment' test,<br/>re-adaptation,<br/>'use adjustment' test"]
    F --> B --> A --> P
```

### 2. Launching a block

```mermaid
flowchart TD
    L["Experimenter runs<br/>poetry run python run_block.py"] --> Q{"--subject and --block<br/>given on the command line?"}

    Q -- "no" --> M["Start screen:<br/>choose block with ↑/↓, press Enter"]
    M --> ID["Type participant ID, press Enter"]
    ID --> D{"Data already saved for<br/>this ID + block?"}
    D -- "no" --> RUN
    D -- "yes" --> W["Warning screen:<br/>R = resume this participant<br/>N = type a different ID<br/>ESC = cancel"]
    W -- "N" --> ID
    W -- "R" --> RUN
    W -- "ESC" --> X["Program closes"]

    Q -- "yes" --> D2{"Data already saved for<br/>this ID + block?"}
    D2 -- "no" --> RUN
    D2 -- "yes" --> T["Terminal asks:<br/>Resume this subject? y/N"]
    T -- "y" --> RUN
    T -- "N" --> X

    RUN["Block runs full-screen<br/>(trials already saved are skipped)"] --> E["All trials done, or ESC pressed:<br/>program closes, data so far is kept"]
```

### 3. Screens inside each block

Instruction screens show the Chinese instruction text and stay up until the
experimenter presses SPACE. "Trial" boxes are the single-trial sequence in
section 4.

**Familiarization**

```mermaid
flowchart LR
    I["Instruction screen:<br/>reach fast like shooting<br/>after the beep"] --> T["16 trials<br/>4 targets, random order<br/>cursor visible, no rotation"] --> E["End"]
```

**Baseline**

```mermaid
flowchart LR
    I["Instruction screen (one for the whole block):<br/>reach after the beep; some trials<br/>have no cursor; some trials you<br/>say a number first"]
    G1["40 trials, randomly mixed:<br/>34 normal (cursor visible)<br/>6 no-cursor"]
    G2["40 aim-report practice trials:<br/>say a number, then reach;<br/>each trial a random rotation<br/>between 30° CCW and 30° CW"]
    I --> G1 --> G2 --> E["End"]
```

No new instruction screen appears between the two parts of baseline.

**Adaptation** (60° clockwise rotation throughout)

```mermaid
flowchart TD
    S["Block starts<br/>(no instruction screen, see to-decide.md item 27)"] --> N{"Next trial in the<br/>random order of 48"}
    N -- "40 of 48" --> R["Regular trial<br/>rotated cursor visible"]
    N -- "4 of 48" --> IR["Instruction screen:<br/>say where you'll aim, then wait for the beep"] --> AR["Aim-report trial<br/>number ring, rotated cursor visible"]
    N -- "4 of 48" --> IN["Instruction screen:<br/>don't use the adjustment you learned"] --> NC["No-cursor test trial<br/>cursor hidden during the reach"]
    R --> M{"More trials?"}
    AR --> M
    NC --> M
    M -- "yes" --> N
    M -- "no" --> E["End"]
```

With more than one cycle (`config.yaml` → `n_cycles`), the 48-trial mix
repeats once per cycle.

**Post-adaptation** (fixed order for everyone)

```mermaid
flowchart LR
    I1["Instruction screen:<br/>don't use the adjustment<br/>you learned"] --> X["16 'exclusion' trials<br/>cursor hidden"]
    X --> R["16 re-adaptation trials<br/>60° rotation back on, cursor visible<br/>(no instruction screen, see to-decide.md item 27)"]
    R --> I2["Instruction screen:<br/>use the adjustment<br/>you learned"] --> C["16 'inclusion' trials<br/>cursor hidden"] --> E["End"]
```

### 4. A single trial

Every trial in every block follows the same sequence; trial kinds differ
only in whether the cursor is visible during the reach, whether it is
rotated, and whether there is an aim report (table below).

```mermaid
flowchart TD
    H["<b>Hold</b><br/>Screen: green home circle + white cursor<br/>(cursor starts on home).<br/>Participant keeps the cursor on home for 500 ms"]
    H -- "cursor leaves home:<br/>500 ms count restarts" --> H
    H --> Q{"Aim-report trial?"}

    Q -- "yes" --> RP["<b>Report</b><br/>Screen: home + red target + number ring, no cursor.<br/>Participant says the number they'll aim at, e.g. minus 10.<br/>Experimenter types it as heard: - 1 0, then SPACE.<br/>Cursor is put back on home (drift is discarded)"]
    RP --> GO
    Q -- "no" --> GO

    GO["<b>Go</b><br/>Red target shown (if not already) + beep"] --> MV["<b>Reach</b><br/>Screen: red target (+ number ring on report trials);<br/>cursor visible or hidden depending on trial kind;<br/>home circle disappears once the cursor leaves it"]

    MV -- "cursor touches target" --> HIT["<b>Hit</b>: bell<br/>target turns green (400-600 ms reach),<br/>yellow (too fast) or blue (too slow)"]
    MV -- "hand moves past 7 cm<br/>or 2 s since the beep" --> MISS["<b>Miss</b>: buzz<br/>target disappears"]

    HIT --> FB["Feedback shown 300 ms"]
    MISS --> FB
    FB --> ITI["<b>Pause</b> 2 s<br/>(currently the last feedback frame<br/>stays on screen during the pause)"]
    ITI --> NEXT["Next trial (or its instruction screen)"]
```

On no-cursor trials the hit test uses the hidden hand position, so the
participant still hears the bell or buzz and sees the target change.

| Trial kind | Block | Cursor during reach | Rotation | Aim report |
|---|---|---|---|---|
| familiarization | Familiarization | visible | none | no |
| baseline_veridical | Baseline | visible | none | no |
| baseline_no_vision | Baseline | hidden | none | no |
| baseline_report_training | Baseline | visible | random, 30° CCW to 30° CW | yes |
| adaptation_regular | Adaptation | visible | 60° CW | no |
| adaptation_report | Adaptation | visible | 60° CW | yes |
| adaptation_return_to_baseline | Adaptation | hidden | none (not visible) | no |
| post_exclusion | Post-adaptation | hidden | none (not visible) | no |
| post_readaptation | Post-adaptation | visible | 60° CW | no |
| post_inclusion | Post-adaptation | hidden | none (not visible) | no |

The "trial kind" names are the values in the `trial_type` column of
`trials.csv`.

## Running a session

Go through the checklist at the end of `caution.md` first.

```bash
poetry run python run_block.py                                       # start screen: pick block + type ID
poetry run python run_block.py --subject S01 --block familiarization  # skip the start screen
poetry run python run_block.py --subject S01 --block baseline --windowed  # in a window, for testing only
```

| Flag | Meaning |
|---|---|
| `--subject` | Participant ID. Spaces around it are removed; upper/lower case matters (`S01` ≠ `s01`). |
| `--block` | `familiarization`, `baseline`, `adaptation` or `post_adaptation`. |
| `--seed` | Number that fixes the random trial order. Leave out for a new random order (it is saved in `schedule.csv`). Pass the saved one when resuming, see below. |
| `--data-dir` | Where data are saved (default `./data`). |
| `--windowed` | Run in a 1280×800 window instead of full-screen. For development only. |
| `--yes` | Skip the "data already exists, resume?" question. |

**ESC** quits at any time; every finished trial is already saved.
Re-running the same participant ID and block **resumes**: trials already
saved are skipped, never repeated or overwritten. To keep the originally
planned trial order when resuming, pass the original seed (`seed` column of
that block's `schedule.csv`) with `--seed` (`to-decide.md` #34).

### Multi-monitor

The program opens full-screen on the display macOS calls **Main Display**
(the one with the menu bar), not necessarily the laptop screen and not
necessarily the larger one. To use an external monitor, open System
Settings → Displays → Arrangement and drag the white menu-bar strip onto it
before launching (`to-decide.md` #31). With one screen there is nothing to
set.

## Data layout

```
data/<subject_id>/<block_name>/
  trials.csv              one row per trial (see vmr/trial.py::TrialResult)
  samples.csv             one row per recorded finger-position sample
  schedule.csv            the planned trial order for this block, with its seed
  config_snapshot.yaml    the config.yaml in force when the block started
  calibration_used.json   the px/cm value used, and whether auto-detected or measured
```

`data/` is not tracked by git. **Back it up after every session.**

## Development

```bash
poetry run pytest                                   # all tests, headless, no screen/sound needed
poetry run marimo edit notebooks/check_session.py   # QC: hit rate, trajectories, missing reports
poetry run marimo edit notebooks/calibration.py     # QC: calibration, pointer-acceleration check, sampling rate
```

Tests run headlessly via pygame's dummy video/audio drivers
(`tests/conftest.py`).

## Project layout

```
vmr/
  config.py                typed config.yaml loader
  geometry.py              pure math: positions, rotation, hit tests, trajectory angles
  schedule.py              trial-list generation for all four blocks
  trial.py                 the trial state machine (TrialRunner)
  report_entry.py          experimenter's aim-report entry logic
  input_device.py          relative-mouse cursor tracking
  audio.py                 sound loading/playback
  display.py               rendering and instruction texts
  menu.py                  start screen (起始畫面) logic + rendering
  display_calibration.py   px/cm detection and manual override
  logging_io.py            CSV writers
  orchestration.py         ties everything together (run_block, main)
run_block.py               the command to launch a block (wraps vmr.orchestration.main)
config.yaml                all experiment parameters
assets/audio/              go beep, hit bell, miss buzz
notebooks/                 marimo QC notebooks
tests/                     tests for every module above
caution.md                 pre-session checklist and setup traps
to-decide.md               open and provisional design decisions
```

## Known gaps

See `to-decide.md` section A for details.

- No instruction text exists for entering the adaptation block or the
  re-adaptation part of post-adaptation (#27).
- Resuming an interrupted block uses a new random order unless the original
  `--seed` is passed (#34).
- Achieved sampling rate not yet measured on the real hardware (#17).
- Hit-zone size and other spatial defaults are provisional until piloting
  (#12 and the rest of section B).
