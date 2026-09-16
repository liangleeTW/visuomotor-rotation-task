# TODO — Visuomotor Rotation Task

Build order matters: geometry and schedule are pure/testable and don't need a
display, so they come before anything that touches pygame. Each section
should be checked off with its own verification, not just "written."

---

## 0. Environment setup
- [x] `pyproject.toml` via Poetry, Python version pinned
- [x] Add deps: `pygame-ce`, `pyyaml`, `numpy`, `pandas`
- [x] Add dev deps: `marimo`, `pytest`
- [ ] macOS settings applied per `caution.md` (gestures, pointer accel) and
      verified empirically (fixed-distance swipe test) — user's machine, not code
- [ ] Magic Trackpad 3 paired, charge/connection confirmed — user's hardware

## 1. Config
- [x] `config.yaml`: all spec constants — radii, timings, feedback speed
      bands/colors, landmark spacing (5.625° / 64 positions), hit_radius,
      `n_adaptation_cycles`, rotation_deg=60, report-training rotation
      range, RNG seed, audio filenames, post-adaptation block order
- [x] `config.py`: typed loader with validation (fail loudly on missing/bad
      values, not silently default) — see tests/test_config.py

## 2. Geometry module (pure functions, no display — build & test first)
- [x] px↔cm conversion from real display physical size at runtime — geometry.py
      accepts px_per_cm as an input (GeometryParams.from_config); actual
      measurement lives in `vmr/display_calibration.py` (ruler-based
      interactive routine + cached JSON, to-decide.md #18), not auto-detected
      from EDID/OS APIs since those are unreliable for external monitors
- [x] target position from angle + radius
- [x] rotation transform (CW/CCW sign convention), applied to displayed
      cursor only, raw trajectory untouched
- [x] hit test (circle-circle overlap using hit_radius)
- [x] landmark position/number (rotates with target, signed, ±31 range)
- [x] `movement_angle_at_50pct_reach` + general heading-angle helper (plus
      the initial-segment heading angle, to-decide.md #25)
- [x] `tests/test_geometry.py`: rotation sign correctness, hit-test edge
      cases, landmark numbering at multiple target angles, angle-at-radius
      against hand-computed ground truth — 32 tests passing

## 3. Trial schedule
- [x] Trial-list builders per phase: familiarization, baseline (×3
      subtypes), adaptation (×3 subtypes × n_adaptation_cycles),
      post-adaptation (×3 subtypes, fixed order)
- [x] Pure-random target order + no-vision interspersion (v1 default)
- [x] Seeded RNG; full schedule serialized to `schedule.csv` before the
      session starts (so it's inspectable/reproducible independent of runtime)
- [x] `tests/test_schedule.py`: trial counts per block match the spec's
      numbers exactly (16/80/48×N/48) — 18 tests passing

## 4. Input device
- [x] pygame relative-mouse capture: hide OS cursor, grab, `get_rel()`
      (`vmr/input_device.py::PygameRelativeMouse`, tested via a fake pygame
      module — no real display needed)
- [x] Cursor reset-to-home at trial start (`CursorTracker.reset_to_home`)
- [x] Guard against first-delta spike after (re)grab/focus change (discarded
      in `PygameRelativeMouse.start()`)
- [ ] Empirical sampling-rate measurement helper (feeds the timing-audit
      notebook) — deferred to section 12

## 5. Display
- [x] Fullscreen window (`vmr/orchestration.py::run_block`, `pygame.FULLSCREEN`;
      `--windowed` for dev). HiDPI/backing-scale correctness itself can only be
      confirmed on a real Retina display — deferred to pilot (section 13)
- [x] Draw: home, cursor, target, landmark ring + numbers, instruction text
      screens (`vmr/display.py::Renderer`) — real spec-quoted Chinese text
      for the 6 instruction_keys that have it (to-decide.md #26/#27);
      verified headlessly with pixel-sampling smoke tests, 11 tests passing.
      Found and fixed: pygame's default font has no CJK glyphs (renders
      tofu) — now picks a real CJK system font (`stheitimedium` et al.)
- [x] Color feedback states (green/yellow/blue hit bands, red target,
      miss = disappear) — driven by `cfg.colors`, tested
- [ ] Verify True Tone / Night Shift are off before trusting feedback colors
      on the real machine (see caution.md) — user's hardware, not code

## 6. Audio
- [x] Preload go_beep / hit_bell / miss_buzz via `pygame.mixer`
      (`vmr/audio.py::SoundBank`) — missing files (not downloaded yet) warn
      and degrade to silent playback rather than crashing, by design
- [ ] Latency sanity check (play + timestamp, confirm no audible lag) —
      needs real audio hardware + the actual sound files, deferred to pilot

## 7. Trial state machine
- [x] Single generic FSM parameterized by trial_type flags (cursor visible?
      rotation active? report phase?) — `vmr/trial.py::TrialRunner`, one
      class for every trial_type, driven by TrialSpec flags
- [x] Flow: hold-home(500ms) → [report phase → wait SPACE] → go(beep) →
      moving → end-feedback(300ms) → done (ITI itself is orchestrated
      between TrialRunner instances by run_block.py, not inside the FSM)
- [x] End conditions consolidated into one `end_reason` value
      (hit / boundary / timeout) instead of three separate booleans
- [x] Synthetic-trajectory tests drive the real FSM end-to-end (hit at
      good/fast/slow speed, boundary, timeout, home-hold reset, rotation
      compensation, report-confirm flow) — 10 tests passing; a
      command-line `--replay` mode for replaying a real session's samples
      through the FSM is deferred to section 13 (pilot validation)

## 8. Experimenter report-entry UI
- [x] Logic layer complete and tested (`vmr/report_entry.py`): digit entry,
      side selection, backspace, range validation at confirm — 11 tests
      passing
- [x] Live on-screen rendering of the typed magnitude + side
      (`Renderer.draw_report_entry_overlay`, covered by the REPORT_WAIT
      case in test_display.py)

## 9. Data logging
- [x] `trials.csv` writer — per-trial rows, `flush()`+`fsync()` immediately
      on trial completion (`vmr/logging_io.py::TrialLogger`)
- [x] `samples.csv` writer — per-input-event rows, same flush/fsync timing
- [x] Per-session `config_snapshot.yaml` saved alongside the data
      (`save_config_snapshot`); `schedule.csv` already covered by
      `Schedule.save_csv` (section 3); RNG seed is recorded in both
- [x] Reopening the same CSV paths (simulating a resumed session) appends
      without duplicating the header — tested

## 10. Menu / launcher
- [x] 起始畫面: 4 block buttons (Familiarization / Baseline / Adaptation /
      Post-adaptation) — `vmr/menu.py` (pure selection logic, tested) +
      `vmr/orchestration.py::run_interactive_menu` (glue, tested via a
      scripted `pygame.event.get` mock)
- [x] Subject-ID entry + on-screen confirmation (`TextEntryState` +
      `run_interactive_menu`'s second phase)
- [x] Refuse to silently overwrite: `existing_trial_count()` +
      `run_block()`'s resume logic skip already-logged trials rather than
      re-running/overwriting them (see section 11)

## 11. Session orchestration
- [x] `run_block.py` entry point with CLI args (`--subject`, `--block`,
      `--seed`, `--data-dir`, `--windowed`); omitting `--subject`/`--block`
      launches the interactive menu instead. `--debug`/`--replay` not
      added — no concrete need identified yet; add if pilot needs it
- [x] Confirm re-launching a block mid-session doesn't corrupt prior data —
      `test_run_block_resumes_without_rerunning_completed_trials` runs a
      partial block, "resumes" with a fresh run_block() call, and asserts
      exactly the missing trials were appended (no duplicates, no loss)
- [x] Found and fixed along the way: the project package itself was never
      actually installed into the venv (`poetry add` alone doesn't do
      this) — `vmr` only imported when cwd happened to be the project
      root. Fixed with `poetry install`; without it, `notebooks/` scripts
      would fail to import `vmr` at all.

## 12. QC / analysis notebooks (Marimo)
- [x] `check_session.py`: load a subject's CSVs, plot trajectories per
      trial_type (colored by end_reason), flag missing reports, summary
      hit-rate/movement-time table by trial_type. Smoke-tested against a
      synthetic session (both the "no data yet" and "real data" paths)
- [x] `calibration.py`: shows cached px/cm calibration status; a live,
      button-triggered pointer-acceleration capture (records raw deltas
      for 5s, reports achieved Hz + net displacement — only meaningful
      run interactively via `marimo edit`, not in headless/script mode);
      achieved sampling-rate histogram from a real session's samples.csv

## 13. Pilot validation
- [ ] Full self-run of every block/phase end-to-end
- [ ] Confirm hit-zone radius, landmark sign convention, and
      movement-onset threshold feel right (to-decide.md #12–13)
- [ ] Confirm timing-audit sampling rate is adequate for the
      angle-at-50%-reach measure

## 14. Docs
- [x] `README.md`: setup instructions, how to run a session, file/data
      layout, project layout, known gaps
- [ ] Keep `caution.md` and `to-decide.md` updated as decisions firm up
      after piloting
