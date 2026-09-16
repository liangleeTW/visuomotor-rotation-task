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

## Still open — informational only, not blocking v1 code

19. Exact MacBook model/year — useful to know whether ProMotion (120 Hz) is
    available, but not required given #18 above computes geometry at
    runtime regardless of model.
20. Whether to add trial-order constraints later (no >2 consecutive repeats
    of a target, no-vision trials excluded from first/last N of baseline,
    etc.) — deferred per "pure random for now" (#5).
