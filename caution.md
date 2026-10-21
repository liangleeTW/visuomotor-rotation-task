# Caution & Pre-Flight Notes

Running notes on things that matter before/while running this experiment.
Add to this file whenever something bites you during setup or piloting.

---

## macOS system settings (set up once, re-verify periodically)

### Trackpad gestures — MUST disable (System Settings → Trackpad)
The reach movements in this task are fast swipes, which is exactly the motion
that triggers several macOS gestures. All of the following must be OFF:
- **Shake mouse pointer to locate** (System Settings → Accessibility → Pointer
  Control → Trackpad Options). This is the most dangerous one — a fast reach
  looks identical to a "shake" and will balloon the cursor size mid-trial.
- Mission Control (3/4-finger swipe up)
- App Exposé (3/4-finger swipe down)
- Swipe between full-screen apps (3/4-finger swipe left/right)
- Swipe between pages (2-finger swipe left/right)
- Notification Centre / Control Centre edge swipes
- Smart zoom, pinch to zoom, rotate
- Look up & data detectors (force click)
- Launchpad (pinch with thumb + 3 fingers), Show Desktop (spread with thumb + 3 fingers)
- Tap to Click, Secondary Click, Three-finger drag — turn OFF (we never click; any
  accidental tap should do nothing)

### Pointer acceleration — MUST disable and VERIFY empirically
```
defaults write -g com.apple.trackpad.scaling -1
```
Requires log-out/log-in (or reboot) to take effect. **Don't trust the setting —
verify it**: swipe a fixed physical distance on the trackpad slowly, then
quickly, and confirm the on-screen cursor travels the same number of pixels
both times. Acceleration is a speed-dependent gain, and this task's core DV is
the *angle* of a *fast* movement — any residual acceleration is a confound
that will not show up as an obvious bug, only as noisier/biased angle data.

### Other settings
- **Do Not Disturb / Focus mode**: ON for every session
- **Screensaver**: Never (during the session)
- **Display sleep / auto-lock**: set to Never for the session duration
- **Auto-brightness**: OFF, fixed brightness level
- **True Tone**: OFF — it shifts color temperature, and the task's feedback
  (green/yellow/blue hit colors, red target) depends on consistent color
- **Night Shift**: OFF, same reason
- **Siri / "Hey Siri"**: OFF — this task involves constant verbal speech from
  the participant; don't let the OS listen to it
- Close all other apps, mute Slack/Mail/Messages/calendar notifications
- Keep the power adapter connected the whole session (battery mode can dim
  the display and throttle performance)

## Hardware setup
- Magic Trackpad 3: charged or wired, paired, placed at a fixed marked
  position on the table every session (consistent hand posture across
  subjects matters)
- Occluder over the hand/trackpad: confirm it doesn't rest on or drag against
  the trackpad surface (adds friction, subtly changes the motor task)
- Headphones on before starting — all audio (go-beep / hit-bell / miss-buzz)
  routes through headphones, not laptop speakers. Check volume is audible but
  not startling using the familiarization block.
- Keyboard positioned so only the **experimenter** can reach it (SPACE
  confirm + report-entry keys are experimenter-only, never participant-facing)
- **If using an external/extended monitor**: set it as the **Main Display**
  in System Settings → Displays → Arrangement (drag the menu-bar strip onto
  it) *before* launching. The app opens fullscreen on whichever display is
  Main — it does not default to the built-in MacBook screen, and does not
  default to "whichever monitor is bigger" either (to-decide.md #31). With
  only one display connected, there's nothing to set — it's automatically
  Main and the app uses it.

## Task-specific gotchas
- **Landmark sign convention**: negative = counterclockwise from target,
  positive = clockwise (matches Taylor, Krakauer & Ivry, 2014). A sign flip
  anywhere in the pipeline silently corrupts every explicit/implicit
  calculation without throwing an error — worth a dedicated sanity check
  before the first real subject (see to-decide.md #13).
- **Hold still until the beep**: before each trial the cursor must stay
  inside the green home circle for 500 ms. If the participant moves, the
  trial silently waits (there is no on-screen warning, to-decide.md #37)
  and can look frozen. Tell participants during familiarization: after
  each trial, lift the finger, put it back at the starting spot, and rest
  it still until the beep. If a trial seems stuck, check whether the
  white cursor is outside home and remind them verbally.
- **Starting spot on the trackpad**: the cursor always starts on home no
  matter where the finger is, so a finger resting near the trackpad's
  edge can run out of surface before completing the 7 cm reach. Mark a
  starting spot near the middle of the trackpad, and check in the pilot
  that full reaches up, down, left and right all fit (up/down is the
  tighter direction on the Magic Trackpad).
- **Aim reports**: the participant reads the ring label aloud, sign included
  ("minus 10"); the experimenter types it exactly as heard (`-` `1` `0`)
  and presses SPACE (to-decide.md #14). Tell participants to keep their
  finger still until the beep: the cursor is hidden while the report is
  entered, so they can't see themselves drifting. Drift is discarded at
  the beep but logged; check the drift table in
  `notebooks/check_session.py` after the session (to-decide.md #35).
- Ambient noise: verbal number reports are hand-transcribed by the
  experimenter. A quiet room reduces mishearing (e.g. "13" vs "30", "15" vs
  "50"). Consider having the participant say numbers as two clearly separated
  digits if this turns out to be a problem in piloting.
- Run the full familiarization block and check the QC notebook (timing +
  hit rate) before running real experimental blocks each session.
- Confirm the subject ID / output filename immediately after entering it at
  the start menu — check the actual file on disk exists with the expected
  name before the participant starts moving.
- **Reusing a subject ID for a different real person** (e.g. weeks later,
  by accident) is now caught: both the menu and the `--subject` CLI flag
  warn and require an explicit Resume/different-ID choice if that
  subject/block already has trials logged (to-decide.md #32). Read that
  prompt when it appears — it exists specifically for the case where "S01"
  looks right but isn't the same person as last time. Leading/trailing
  whitespace in a typed ID is stripped automatically; case is not
  (`S01` and `s01` are different subjects, to-decide.md #33).
- **This does not make same-subject resume fully safe on its own**: if a
  block was genuinely interrupted and you're resuming it, pass the same
  `--seed` you used originally (recorded in that subject/block's
  `schedule.csv`) — otherwise the remaining trials come from a freshly
  randomized schedule, not the one actually planned (to-decide.md #34).
- Local storage only, no server: **back up the data folder after every
  session** (external drive, cloud sync, whatever is convenient) — a single
  disk failure with no backup loses everything.
- **Display calibration (px/cm) is automatic**, detected fresh each session
  from the display's real physical size — no manual step needed under
  normal use. It's recorded per-session in
  `data/<subject>/<block>/calibration_used.json`; if you ever switch to an
  unfamiliar external monitor, glance at that file's `px_per_cm` once to
  make sure it's a plausible value (a 24"-27" monitor should land roughly
  in the 35-45 px/cm range) before trusting a full session to it. If it
  looks wrong, run `poetry run python -m vmr.display_calibration` once to
  override it with a ruler measurement (to-decide.md #18).

## Known open technical decisions
See `to-decide.md` for parameters (hit-zone radius, sampling approach, etc.)
that are provisional engineering defaults, to be confirmed or retuned after
the first pilot subject.

## Pre-session checklist
- [ ] Trackpad gestures disabled (especially Shake-to-locate)
- [ ] Pointer acceleration OFF — verified empirically this week, not just set
- [ ] Trackpad charged/connected, placed at marked position
- [ ] Occluder in place, not touching trackpad surface
- [ ] Headphones on, volume checked
- [ ] Do Not Disturb on, other apps closed
- [ ] Display brightness fixed, True Tone & Night Shift off
- [ ] Power adapter connected
- [ ] External monitor (if used) set as Main Display before launching
- [ ] Keyboard input source set to ABC / U.S. (not a Chinese input method),
      so typed participant IDs and aim reports reach the experiment
- [ ] Subject ID / filename entered and confirmed on disk; if a duplicate
      warning appears, actually stop and check before choosing Resume
- [ ] Familiarization block run and reviewed before the main session
- [ ] Backup performed after the session ends
