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

## Task-specific gotchas
- **Landmark sign convention**: negative = counterclockwise from target,
  positive = clockwise (matches Taylor, Krakauer & Ivry, 2014). A sign flip
  anywhere in the pipeline silently corrupts every explicit/implicit
  calculation without throwing an error — worth a dedicated sanity check
  before the first real subject (see to-decide.md #13).
- Ambient noise: verbal number reports are hand-transcribed by the
  experimenter. A quiet room reduces mishearing (e.g. "13" vs "30", "15" vs
  "50"). Consider having the participant say numbers as two clearly separated
  digits if this turns out to be a problem in piloting.
- Run the full familiarization block and check the QC notebook (timing +
  hit rate) before running real experimental blocks each session.
- Confirm the subject ID / output filename immediately after entering it at
  the start menu — check the actual file on disk exists with the expected
  name before the participant starts moving.
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
- [ ] Subject ID / filename entered and confirmed on disk
- [ ] Familiarization block run and reviewed before the main session
- [ ] Backup performed after the session ends
