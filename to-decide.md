# To-Decide / Open Parameters

Every design choice made while turning the task description into a
program, written so that someone who has **not** read the code can follow
it. For each item: what it is, what the program does right now, and what to
watch for during pilot testing.

Items keep their original numbers (#1–#37), because the code, `caution.md`
and `README.md` refer to them by number. They are grouped by how much
attention they still need:

- **A. Open — needs a human decision**: nothing sensible can be chosen
  without you.
- **B. Provisional — confirm during piloting**: a reasonable default is in
  place, but only a real pilot session can tell whether it's right.
- **C. Settled — for the record**: decided (by the PI or engineering); listed
  so the reasoning is not lost. Reopen any of them if piloting suggests so.

"Where to change" points to the setting or file to edit if the decision
changes. Most are in `config.yaml`, which needs no programming.

### Words used throughout

- **Home**: the small green circle in the screen centre where every reach
  starts.
- **Cursor**: the small white dot that represents the participant's finger on
  the trackpad. The participant's hand is hidden under an occluder, so the
  cursor is all they see of their own movement.
- **Target**: the red circle, 7 cm from home, in one of four directions
  (right, up, left, down).
- **Rotation**: on rotated trials the cursor's movement is turned by a fixed
  angle relative to the hand's real movement. With a 60° clockwise rotation,
  moving the hand straight up makes the cursor go up-and-to-the-right, so the
  participant must learn to aim 60° counter-clockwise of the target.
- **Landmark ring**: numbers printed in a circle around home on "report"
  trials. Before reaching, the participant says aloud which number they are
  aiming at — this measures their *explicit* (conscious) aiming strategy.
- **Experimenter**: the person at the keyboard. The participant never touches
  the keyboard.

---

## A. Open — needs a human decision

27. **Two moments have no instruction text in the task description.**
    Every other change of task comes with a written instruction screen, but
    these two do not:
    - the switch from baseline into the **adaptation** block (when the 60°
      rotation first turns on), and
    - the start of the **re-adaptation** part of the post-adaptation block
      (when the rotation turns back on after the "don't use your
      adjustment" trials).

    Right now, the program shows **no** instruction screen at either point;
    the rotation simply starts. No wording has been invented.
    **Decide**: should participants get a written or spoken heads-up at
    either moment, and if so, what exactly should it say?
    Where to change: `vmr/display.py` (instruction texts) and
    `vmr/schedule.py` (which trials get an instruction screen).

34. **Resuming an interrupted block can change the planned trial order.**
    Each block's trial order (which target comes when, and where the special
    trials fall) is shuffled using a random number called the *seed*. The
    same seed always gives the same order. If a block is interrupted (e.g.
    ESC pressed after 30 trials) and started again, the program correctly
    skips the 30 trials already recorded — **but it makes a brand-new random
    order unless the original seed is typed in again**. So "trial 31 onward"
    may not be what was originally planned: a target or special trial could
    be repeated or skipped compared with the plan.
    **Current workaround**: when resuming, look up the seed in that block's
    `schedule.csv` (column `seed`) and pass it with `--seed`.
    **Decide**: should the program read back the original seed
    automatically when resuming? (Recommended — it's a small change.)

36. **What the screen shows during the 2-second pause between trials.**
    The spec only gives the pause length (`inter_trial_interval_ms: 2000`),
    not what is on screen. Many psychology experiments show a small light
    grey fixation cross in the centre during this time: it keeps the
    participant's gaze where home will appear and makes "between trials"
    visibly different from "trial running". Many reaching studies
    (including Taylor et al., 2014) use a blank screen instead, so the
    cross is not needed for comparability, and it would be a deviation
    from the spec.
    Currently the screen is not redrawn during the pause: after a miss it
    is black, but after a hit the coloured target stays visible for the
    whole 2 s (a bug, to be fixed whichever option is chosen).
    **Decide**: blank black screen, or a light grey fixation cross?

37. **On-screen warning when the finger moves before the beep.**
    Before each trial the cursor must stay inside home for 500 ms; if it
    leaves, the count restarts and the trial waits, with no message, so a
    fidgeting participant can look like a frozen program. The spec has no
    warning for this. Current approach: no on-screen warning; the
    experimenter tells participants to rest their finger still on the
    trackpad until the beep and reminds them verbally if needed (see
    `caution.md`). The cursor is drawn at least 3 px so a participant who
    did move can see it and steer back into home.
    Possible additions if piloting shows it's needed:
    - a short grey message under home while the finger moves, e.g.
      「請保持手指不動，等待「嗶」聲」 (wording for the PI to approve);
    - freezing the cursor on home during the wait while still requiring
      500 ms of stillness, so the cursor can never be lost (e.g. moved off
      the screen) — the trial then simply continues 500 ms after the
      finger stops.
    **Related**: the beep always comes exactly 500 ms after the hold
    starts, so participants could learn to anticipate it. A random wait
    (e.g. 500–1000 ms) would prevent that but differs from the spec's fixed
    500 ms. **Decide** after piloting.

19. **Which MacBook will run the study (model and year)?** Only matters for
    knowing whether the screen can refresh at 120 Hz (which allows finer
    movement recording, see #17). Not needed for anything else: screen size
    is detected automatically (#18).

20. **Should the trial order have extra rules?** At the moment the order is
    purely random (#5). Common extra rules in the literature: never the same
    target more than twice in a row; no "no-cursor" trial among the first
    or last few baseline trials. None are applied.
    **Decide** after piloting whether any of these are wanted.

---

## B. Provisional — confirm during piloting

12. **How close the cursor must get to "hit" the target.**
    The trial counts as a hit as soon as the cursor dot (0.5 mm radius)
    touches the target circle (5 mm radius), i.e. when the centres are within
    5.5 mm. This matches the dashed ring just outside the target in the task
    illustration.
    **Watch for**: hit rates that are much too high or too low, or whether
    that dashed ring was meant as a deliberately *larger* catch zone.
    Where to change: `config.yaml` → `workspace: hit_radius_mm`.

13. **Layout and numbering of the landmark ring.**
    64 numbered positions evenly spaced around the full circle (one every
    5.625°). The number **0** sits on the target. Numbers increase going
    **clockwise** (+1 … +31) and go negative going **counter-clockwise**
    (−1 … −31). The ring turns with the target, so 0 is always on whichever
    target is shown. Copied exactly from Taylor, Krakauer & Ivry (2014,
    *J Neurosci* 34(8):3023–3032), the study this task is based on, so
    results are directly comparable.
    **Watch for**: if the spacing is too fine or coarse to read, or the
    sign convention is confusing to participants. Before the first real
    participant, check once by hand that "aim at −10" really means
    counter-clockwise — a sign flip would silently corrupt every
    explicit-aim measure (see `caution.md`).
    Where to change: `config.yaml` → `landmarks`.

14. **How the experimenter types the participant's spoken number.**
    The experimenter types the number **exactly as heard**, sign included,
    then presses SPACE:
    - "10" → `1` `0` SPACE
    - "minus 10" → `-` `1` `0` SPACE
    - "0" → `0` SPACE

    Top-row keys and the numeric keypad both work (including the keypad
    `-`). The number appears in the bottom-left corner in the same format
    as the ring (`回報: -10`), so the participant can catch a misheard
    number. BACKSPACE deletes the last character. A number above 31 cannot
    be confirmed: SPACE silently does nothing.
    SPACE both records the report and sounds the "go" beep, so the
    participant can't start before the report is entered. Until SPACE, no
    cursor is shown (see #35).
    In `trials.csv` the report is stored as `reported_number` (without sign)
    plus `reported_side` (`CCW` for negative, `CW` for positive, empty for
    0), and `reported_angle_deg` (the direction it points to).
    `report_registered_timestamp` is the time of the last keystroke before
    SPACE, i.e. when transcription finished.
    *Changed 2026-10-20*: replaced the earlier "type the size, then press ←
    or → for the side" entry, which made the experimenter convert "minus"
    into a screen direction (hard when the target is at the bottom).
    **Watch for**: whether mistakes happen, e.g. mishearing "13" vs "30",
    or a forgotten `-`.

17. **How often the finger position is recorded.**
    The position is read once per screen refresh (about 60 times per
    second on a standard screen). This is the simplest reliable method. A
    faster, more complicated method (reading the trackpad directly at the
    operating-system level) is possible if needed.
    **Watch for**: after the pilot, check the achieved rate in
    `notebooks/calibration.py`. If ~60 samples/s is too coarse for the
    planned analyses (e.g. velocity profiles), switch to the faster method.

18. **Converting centimetres to screen pixels.**
    All distances are set in real-world units (target 7 cm from home, etc.).
    The program converts them to pixels using the screen's real physical
    size, which macOS reports automatically each time a block starts, so it
    works on any monitor without setup. The task description's fixed
    "391 px" only fit one particular screen.
    If a monitor reports its size wrongly (some external monitors do), the
    reaches will feel too long or too short. In that case, measure the
    screen once with a ruler (`poetry run python -m vmr.display_calibration`);
    the measured value then always overrides the automatic one until its
    file (`display_calibration.json`) is deleted. The value actually used is
    saved with every session's data (`calibration_used.json`).
    **Watch for**: on a new external monitor, check that file's `px_per_cm`
    is plausible (24–27" monitor ≈ 35–45 px/cm).

26. **When instruction screens appear.**
    The task description's wording implies three different patterns:
    - **Once at the start of the block**: familiarization, and baseline.
      Baseline has a single combined instruction covering all its trial
      kinds (normal, no-cursor, and report trials).
    - **Before every single occurrence**: the "say your aim first" reminder
      before each report trial in adaptation, and the "don't use your
      adjustment" reminder before each no-cursor test trial in adaptation.
      These trials are scattered among normal trials, and the description
      says "presented before each … probe".
    - **Once at the start of each sub-block**: the "don't use your
      adjustment" and "use your adjustment" parts of the post-adaptation
      block (16 trials each).

    Every instruction screen stays up until the experimenter presses SPACE.
    **Watch for**: if the per-trial reminders feel repetitive. With only 4
    of each among 40 normal trials they should rarely appear back to back.
    Where to change: `vmr/schedule.py`.

28. **What "movement time" measures.**
    Movement time is from when the finger **leaves home** to when the cursor
    reaches the target — *not* from the beep. It drives the speed feedback
    (target turns green if 400–600 ms, yellow if faster, blue if slower).
    So the time taken to react to the beep doesn't count against the
    participant, only the reach itself. This is the usual meaning of
    "movement time" in motor-control research.
    **Watch for**: if the intention was to include reaction time (i.e.
    timed from the beep), this is a one-line change in `vmr/trial.py`.

35. **Finger drift while the aim report is entered.**
    While the experimenter is entering the report, the cursor is hidden
    (on rotated trials a visible cursor would reveal the rotation before
    the reach), so the participant can't see if their finger slides off
    home. Previously, the reach then started from wherever the hidden
    cursor had drifted to, which corrupts reaction time, movement time and
    reach direction, and could even end the trial instantly.
    *Fixed 2026-10-20*: when SPACE is pressed, the cursor is put back on
    home, so the reach always starts there. Input is relative, so where
    the finger physically sits on the trackpad doesn't matter. The largest
    drift during the report is saved per trial as
    `report_wait_max_drift_mm` (empty on non-report trials), and
    `notebooks/check_session.py` lists report trials that drifted more than
    the home radius (2.5 mm), which may mean the participant started moving
    early. Reach-direction measures use only movement after the beep.
    Note that `samples.csv` still contains the drifted positions recorded
    during the report, followed by a jump back to home at the beep.
    **Watch for**: how often drift happens in piloting. If often, consider
    a stronger "keep still until the beep" instruction, or excluding
    trials above some drift threshold.

29. **Holding still on home before each trial.**
    The participant must keep the cursor on home for 500 ms *without
    interruption* before the target appears. If the cursor slips off home
    during that time, the 500 ms count starts over (rather than pausing and
    continuing). Usual convention; not stated in the task description.

---

## C. Settled — for the record

### Decided by the PI (2026-09-16 discussion)

1. **When "movement onset" happens**: the moment the cursor leaves home
   (moves more than 2.5 mm from the centre).
2. **When the 2-second time limit starts**: at the "go" beep, for every
   trial type. If the target isn't reached within 2 s, the trial ends as a
   miss.
3. **Number of adaptation cycles**: 1. A cycle = 48 rotated trials (40
   normal, 4 report, 4 no-cursor tests). Can be raised later in
   `config.yaml` → `trial_counts: adaptation: n_cycles`.
4. **Direction of the rotation**: the cursor is turned 60° **clockwise**, so
   the participant must aim counter-clockwise to compensate.
5. **Randomising the trial order**: plain random, no extra rules, for both
   which target appears and where the no-cursor trials fall. (Each target
   still appears about equally often within each kind of trial.)
6. **Rotation on baseline report-practice trials**: each of these 40
   trials gets its own random rotation between 30° counter-clockwise and
   30° clockwise, so participants practise reporting an aim that differs
   from the target, without learning any one consistent rotation.
7. **Order inside the post-adaptation block**: the same for everyone —
   (1) "don't use your adjustment" no-cursor trials → (2) re-adaptation
   with the rotation back on → (3) "use your adjustment" no-cursor trials.
8. **Cursor reset between trials**: the cursor jumps back to home at the
   start of every trial, so the participant can lift and reposition their
   finger anywhere on the trackpad between trials. Any finger movement
   during the pause or an instruction screen is discarded, so every trial
   starts exactly on home (fixed 2026-10-20: before, that movement was
   applied all at once on the trial's first frame, pushing the cursor off
   home). The same reset happens again at the beep on report trials (#35).
9. **Familiarization targets**: the 4 standard directions. ("八個點" in the
   description was a typo; the illustration shows 4.)
10. **Trackpad**: external Apple Magic Trackpad 3.
11. **Software**: Python with pygame (pygame-ce).

### Data-file format (decided by engineering, 2026-09-16)

These affect only how results are written to `trials.csv`, not what the
participant experiences.

15. **Names for the post-adaptation trial kinds.** The task description
    reused labels from the adaptation block for these, which would make
    them impossible to tell apart in the data. They are now labelled:
    `post_exclusion` ("don't use your adjustment"), `post_readaptation`
    (rotation back on), and `post_inclusion` ("use your adjustment").
16. **What the "rotation" column records.** It holds the rotation applied
    to the *visible* cursor on that trial. On trials with no visible cursor
    it is left empty, even inside the adaptation block, because nothing was
    rotated on screen. The block-level rotation (0° baseline, 60°
    adaptation) is recorded once in the saved `config_snapshot.yaml`.
21. **One "how did the trial end" column** (`end_reason`: `hit`, `boundary`
    = went past 7 cm without hitting, or `timeout` = 2 s ran out) instead of
    three yes/no columns that could contradict each other.
22. **Target position is stored in pixels as well as its direction**, so old
    data stays interpretable even if distances are changed later.
23. **A `phase` column** (familiarization / baseline / adaptation /
    post_adaptation) for easy grouping in analysis.
24. **Counting columns renamed and start at 0**: `cycle_index` (which
    adaptation cycle) and `probe_index` (which report / no-cursor test
    trial within a cycle), matching `trial_index`.
25. **Two measures of reach direction are saved.** (a) The direction of the
    hand at the point halfway to the target (the description's measure),
    and (b) the direction of the early part of the movement, 1–3 cm from
    home — the measure Taylor et al. (2014) use. (b) is a backup in case (a)
    turns out noisy.

### Practical safeguards (decided by engineering)

30. **Chinese instruction text.** pygame's built-in font has no Chinese
    characters and silently draws empty boxes instead. The program now
    picks a Chinese-capable font installed on the Mac (e.g. STHeiti,
    PingFang). **If the instructions show boxes on a new Mac**, that Mac
    lacks all the listed fonts; add one it has to `_CJK_FONT_CANDIDATES` in
    `vmr/display.py`.

31. **Which screen the experiment opens on, with two monitors.** It opens
    full-screen on whichever display macOS calls the **Main Display** (the
    one with the menu bar) — set in System Settings → Displays → Arrangement
    by dragging the white menu-bar strip onto the desired screen. This is
    *not* necessarily the laptop screen and *not* necessarily the bigger
    one. With one screen there's nothing to set. Known limitation: with two
    monitors of identical resolution, the program can't tell them apart,
    falls back to the first one, and prints a warning.

32. **Protection against reusing a participant ID by mistake.** Data are
    saved in a folder named after the participant ID and block. Before this
    safeguard, typing an ID that had been used before (e.g. "S01" for a new
    person weeks later) would silently add the new person's trials to the
    old person's file, or silently do nothing if that block was already
    complete. Now, if that ID + block already has data, the program stops
    and asks: **R** = resume this same participant, **N** = type a different
    ID, **ESC** = cancel. When started from the command line it asks
    `Resume this subject? [y/N]` (skippable with `--yes`).
    This does not fix the resume-order problem in #34.

33. **Tidying typed participant IDs.** Accidental spaces before or after an
    ID are removed, so "S01 " can't slip past the check in #32 as a
    "different" participant. An ID made only of spaces is refused.
    Upper/lower case is **kept on purpose** (PI decision, 2026-09-18):
    `S01` and `s01` are different participants.
