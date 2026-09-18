# To-Decide / Open Parameters

Status of every open question from the spec review. Items marked "engineer
default" are my best call so the build isn't blocked — all are config values,
trivial to change later. Revisit after the first pilot subject.

---

## Decided by PI (2026-09-16 discussion)

1. **Movement-onset** = cursor leaves the 14 px (2.5 mm) home radius.
2. **Timeout clock** starts at the go signal (beep), for all trial types.
3. **Number of adaptation cycles** = 1 for now, exposed as `n_adaptation_cycles`
   in `config.yaml` for future changes.
4. **Rotation sign**: 60° CW cursor rotation ⇒ participant must aim CCW to
   compensate.
5. **Pseudorandomization** = pure random (no extra constraints) for target
   order and no-vision-trial placement, v1.
6. **Report-training rotation range** = pure random uniform in [−30°, +30°],
   resampled every trial.
7. **Post-adaptation block order** = fixed for all subjects: return-to-baseline
   (exclusion) → re-adaptation → inclusion ("use learned adjustment"). An
   instruction screen precedes every sub-block that needs one (baseline
   report-training, each adaptation-report probe, and all three
   post-adaptation sub-blocks).
8. **Cursor reset**: internal cursor snaps to home at the start of every
   trial; participant is free to reposition their finger on the trackpad
   between trials (this is what relative/delta input buys us).
9. **Familiarization target count** = 4 (0/90/180/270°). The "八個點" text in
   the spec is an error; the illustrated layout (4 targets) is correct.
10. **Trackpad** = external Magic Trackpad 3 (already purchased).
11. **Framework** = pygame (pygame-ce).

---

## Decided by engineer — defaults, please sanity-check after pilot

12. **Hit-zone radius** = cursor circle (r = 3 px / 0.5 mm) touching target
    circle (r = 28 px / 5 mm) → `hit_radius = 31 px` (≈5.5 mm), i.e. standard
    circle-overlap contact test. This matches the dashed "just outside the
    solid target" ring shown in the familiarization slide.
    **Revisit if**: pilot subjects find it too easy or too hard, or if the
    dashed circle in the mockup was meant to represent a specific larger
    catch radius rather than geometric circle-overlap.

13. **Landmark ring** = 64 positions, 5.625° apart, full circle. Landmark "0"
    at the target; +1…+31 clockwise, −1…−31 counterclockwise; ring rotates
    rigidly with the target. Taken directly from Taylor, Krakauer & Ivry
    (2014, *J Neurosci* 34(8):3023–3032) — the paper this task's
    report/adaptation-report design is clearly modeled on. Using their exact
    scheme makes results directly comparable to that literature.
    **Revisit if**: you want a coarser/finer ring, or a different max
    magnitude than ±31.

14. **Experimenter report-entry UI**: type the spoken magnitude (0–31 digits,
    live-echoed on the experimenter's screen), press ← or → (or L/R) for
    side (skipped when magnitude is 0), SPACE confirms — SPACE both locks the
    report and triggers the go signal, per spec.
    **Revisit if**: this feels slow or error-prone during piloting; see
    the comparison table in chat for alternatives considered.

15. **Post-adaptation trial_type labels** (the spec's slides reused
    mid-adaptation labels by copy-paste, which would make these
    indistinguishable in the CSV):
    - `post_exclusion` — was generically "return-to-baseline" in the
      post-adaptation section
    - `post_readaptation` — was mislabeled `adaptation_regular` in the spec
    - `post_inclusion` — was mislabeled `adaptation_return_to_baseline` in
      the spec (no-cursor / no-feedback behavior is unchanged, only the
      trial_type string changes)
    **Revisit if**: you'd rather these share a label with their mid-adaptation
    counterparts and be distinguished only by a `phase` column instead.

16. **`rotation_deg` semantics**: always means "rotation applied to the
    *displayed* cursor this trial" — `null` whenever no cursor is shown
    (no-vision / no-feedback trial types), even though a perturbation is
    nominally "in force" in the background. The block-level perturbation
    (0° baseline / 60° adaptation & re-adaptation / none during
    inclusion & exclusion probes) is documented once in `config.yaml`, not
    duplicated per row.
    **Revisit if**: you want per-row redundancy for easier ad hoc filtering
    without joining against the config — trivial to add a second column.

17. **Sampling**: poll trackpad deltas once per rendered frame via pygame in
    v1, rather than a raw Quartz/pyobjc event tap. Achieved Hz will be
    measured empirically in the pilot's timing-audit notebook.
    **Revisit if**: the measured rate (likely ~60–125 Hz) turns out too
    coarse for the velocity-profile analyses you want — then we add the
    event tap.

18. **px↔cm conversion**: computed at runtime from the actual display's
    physical panel size and current resolution, not hardcoded to the spec's
    `px: 391` (which assumes one specific display/resolution). Makes the
    code correct on whatever machine actually runs it.
    **Revised 2026-09-18** (raised by PI: calibration shouldn't be a
    mandatory manual step): `resolve_calibration()` now auto-detects the
    physical size via macOS's own Quartz API (`CGDisplayScreenSize`),
    which is accurate for a real, connected display — no setup required,
    the experiment runs out of the box. A manually-measured calibration
    (the ruler routine, `python -m vmr.display_calibration`) is saved to
    `display_calibration.json` at the project root and, if present,
    **always overrides** auto-detection — it exists only for the rare case
    auto-detection is wrong (e.g. some external monitors report bad EDID
    data) or Quartz is unavailable. Auto-detected values are never cached
    to disk (detection is instant, and not caching means a monitor swap
    is picked up immediately); whichever value was actually used is
    recorded per-session in `data/<subject>/<block>/calibration_used.json`
    for provenance.
    **Revisit if**: you swap to an external monitor where auto-detection
    turns out to be wrong — the symptom would be reaches feeling
    mis-scaled relative to the intended 7cm distance. Run the manual
    calibration once to override it.

---

## Decided by engineer — schema cleanup (delegated 2026-09-16)

21. **Collapse `hit_target` / `boundary_crossed` / `timeout` into one
    `end_reason` field** (`hit` / `boundary` / `timeout`). They're mutually
    exclusive by construction; one enum can't be logged inconsistently the
    way three independent booleans can.
22. **Keep `target_x`/`target_y`** even though they're derivable from
    `target_angle_deg` + the workspace radius — logging the actual px
    protects old sessions' data from silent reinterpretation if the radius
    config ever changes.
23. **Add a `phase` column** (`familiarization` / `baseline` / `adaptation` /
    `post_adaptation`), separate from `trial_type`, so analysis can group by
    phase without string-parsing trial_type values.
24. **Rename** `adaptation_block` → `cycle_index`, `probe_number` →
    `probe_index` — both 0-based, consistent with `trial_index`.
25. **Add a secondary derived angle**: alongside
    `movement_angle_at_50pct_reach`, also log heading angle from the initial
    trajectory segment (1–3 cm from home), which is what Taylor et al. (2014)
    use for their primary heading-angle measure. Costs nothing to compute and
    gives a literature-standard fallback if the 50%-reach measure turns out
    noisier than expected.

26. **Instruction-screen timing** (implemented in `vmr/schedule.py`): three
    scopes, inferred from the spec's own wording rather than applied
    uniformly:
    - `once_per_phase` — familiarization and baseline (all three baseline
      trial types share one combined instruction, per the spec's single
      "Baseline-section start" text covering veridical/no-vision/report
      scenarios together); shown only before the very first trial.
    - `once_per_trial` — `adaptation_report` and
      `adaptation_return_to_baseline`. These are scattered individually
      among ordinary adaptation trials (pure-random interleaving), and the
      spec explicitly says "Presented before each Return-to-baseline probe
      block" — read literally, that's every occurrence, not once per cycle.
    - `once_per_block` — the post-adaptation exclusion and inclusion
      sub-blocks (each a contiguous 16-trial run per to-decide.md #7),
      shown once at the start of each. Re-adaptation gets none — see #27.
    **Revisit if**: the once-per-trial reminders for report/return-to-baseline
    probes feel repetitive in piloting — could be softened to "only if the
    previous trial was a different type," though that's what once_per_trial
    already reduces to when these probes are sparse among 40 regular trials.

28. **`movement_time_ms` window**: measured from `movement_onset_timestamp`
    to the end-of-movement timestamp (hit/boundary/timeout), not from
    `go_signal_timestamp`. This is what feeds the 400–600 ms speed-feedback
    band, so it excludes reaction time (the delay before the hand starts
    moving) and counts only the reach itself — standard motor-control
    convention, and the only reading consistent with "movement time" as a
    name distinct from "reaction time."
    **Revisit if**: you actually want the band to include reaction time
    (i.e. measured from the beep) — a one-line change in
    `vmr/trial.py::_end_trial`.

29. **Home-hold dwell**: the 500 ms hold must be *continuous* — if the
    cursor leaves the home radius before 500 ms accumulates, the dwell
    timer resets to zero rather than pausing/resuming. Standard convention
    for center-out reaching tasks; not stated explicitly in the spec.

30. **Instruction-text font**: pygame's bundled default font has no CJK
    glyphs — it silently renders Chinese text as tiny "tofu" boxes rather
    than erroring, which would have gone unnoticed without pixel-level
    testing. `vmr/display.py` now picks a real CJK-capable system font
    (`stheitimedium`, confirmed present and rendering correctly on this
    Mac) with a fallback list, rather than trusting `SysFont(None, ...)`.
    **Revisit if**: the target Mac doesn't have any of the candidate fonts
    installed — check `pygame.font.get_fonts()` on that machine and add
    whichever CJK font it does have to `_CJK_FONT_CANDIDATES`.

31. **Which physical display shows the experiment, on a multi-monitor
    setup**: pygame's own default (`display=0`) is **not** reliably the
    display macOS calls "Main" — confirmed by live testing: with an
    external monitor explicitly set as Main Display in System Settings,
    `display=0` still opened on the built-in MacBook panel. SDL's display
    enumeration order follows OS connection/detection order, not the Main
    Display setting; Apple's own docs for the underlying enumeration API
    note the first entry "is not necessarily the main display." This also
    meant calibration (`CGMainDisplayID`) and window placement could
    silently disagree about which screen was meant.
    `vmr/orchestration.py::resolve_display_index` now matches pygame
    display indices against Quartz's `CGMainDisplayID` **by resolution**
    (tolerant of a 2x HiDPI points-vs-pixels mismatch between the two
    APIs), so display selection and calibration are structurally tied to
    the same "Main Display" concept and can't disagree. With only one
    display connected there's nothing to disambiguate, so it returns 0
    immediately — the "no external monitor → falls back to the built-in
    screen" behavior is automatic. Falls back to 0 with a `warnings.warn`
    if detection fails or two displays share an identical resolution
    (rare for laptop+external, but not impossible).
    **To use it**: set the desired display as Main Display in System
    Settings → Displays → Arrangement (drag the menu-bar strip onto it)
    before launching. Verified against this dev machine's real displays
    (not mocked): correctly resolved to the display matching
    `CGMainDisplayID`'s actual resolution.
    **Revisit if**: you get two displays with truly identical native
    resolutions (e.g. two of the exact same external monitor model) — the
    resolution-matching heuristic can't disambiguate that case and will
    fall back to display 0 with a warning.

32. **Duplicate subject-ID protection**: `(subject_id, block_name)` is the
    *entire* identity key for where data is saved — there is no
    participant-identity check, so accidentally reusing an ID (e.g. weeks
    later, for a different real person) would previously either silently
    do nothing (if the prior block was fully complete — `trials_to_run`
    would be empty) or, worse, silently merge a second person's trials
    into the same file as a partially-completed prior session, with
    logging appending in both cases (never overwriting — that part was
    already safe). Both the interactive menu (after the subject-ID text
    is confirmed) and the CLI `--subject`/`--block` path now check
    `vmr/menu.py::check_existing_data` and require an explicit choice
    before proceeding if that subject/block already has trials logged:
    the menu shows a Resume/different-ID/Cancel screen
    (`draw_duplicate_warning`, `wait_for_duplicate_choice`); the CLI
    prints the same information and asks via `input()`, with a `--yes`
    flag to skip the prompt for scripted/known-good resumes.
    **What this does not fix**: a genuinely intentional resume after a
    real interruption still uses a fresh random schedule unless the
    original `--seed` is passed explicitly — see #34; auto-recovering the
    seed from the existing `schedule.csv` on resume would be the complete
    fix and hasn't been implemented.
    **Revisit if**: this prompt feels like it fires too often for a
    workflow that deliberately reruns a block under the same ID.

33. **Subject-ID whitespace/case normalization**: leading/trailing
    whitespace is stripped before a subject ID is ever used to build a
    path or checked against existing data (`vmr/menu.py::normalize_subject_id`,
    applied on both the menu and CLI paths) — a stray space from a
    copy-paste or an errant space-bar tap can't be a legitimate part of
    an ID, and without stripping it would also let a whitespace-variant
    ID slip past the duplicate-ID check in #32 entirely (this normalization
    is load-bearing for #32, not merely cosmetic). A whitespace-only entry
    is also no longer accepted as a valid subject ID at all
    (`handle_text_entry_key` requires non-whitespace content to confirm).
    **Case is deliberately NOT normalized** — `S01` and `s01` are treated
    as different subjects, per PI decision (2026-09-18), not an oversight.

## Still open — informational only, not blocking v1 code

19. Exact MacBook model/year — useful to know whether ProMotion (120 Hz) is
    available, but not required given #18 above computes geometry at
    runtime regardless of model.
20. Whether to add trial-order constraints later (no >2 consecutive repeats
    of a target, no-vision trials excluded from first/last N of baseline,
    etc.) — deferred per "pure random for now" (#5).
34. **Resume doesn't recover the original seed.** `build_schedule()` draws
    a fresh random seed every launch unless `--seed` is passed explicitly;
    resuming a partially-completed block (`n_existing > 0` trials already
    logged) doesn't read back the seed that was actually used the first
    time from `schedule.csv`/`trials.csv`'s `seed` column — it just slices
    "the first N trials" off of whatever schedule the current call
    happens to generate. If that's a different seed than the original run,
    "trial N onward" isn't the trial sequence that was actually planned.
    Raised alongside #32 but not fixed: the natural fix is to have resume
    look up and reuse the recorded seed automatically (warning if the
    caller passed a conflicting one), at the same point `check_existing_data`
    already reads the prior session's files.
27. **Spec gap**: two transitions have no quoted instruction text, unlike
    every other section boundary:
    - entering the adaptation phase itself (only `adaptation_report` and
      `adaptation_return_to_baseline` have explicit instruction text;
      plain `adaptation_regular` trials — and the transition into the
      rotated phase generally — have none)
    - entering the post-adaptation **re-adaptation** sub-block (exclusion
      and inclusion each have quoted Chinese instructions; re-adaptation's
      spec pages show the same plain rotated-trial mechanics as
      `adaptation_regular`, with no text box)
    Not inventing wording for either; `vmr/schedule.py` currently shows no
    instruction screen for `post_readaptation` and none for entering
    adaptation. Flagging so you can decide whether participants need a
    verbal heads-up before either transition.
