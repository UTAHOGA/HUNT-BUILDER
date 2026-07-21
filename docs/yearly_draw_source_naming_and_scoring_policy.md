# Yearly Draw Source Naming And Scoring Policy

This policy applies to every permit-year draw-odds folder under:

```text
pipeline/RAW/hunt_unit_database/<SOURCE_YEAR>/pdf/draw_odds/
```

The purpose is to keep source routing, file naming, and score-key construction
stable from year to year. A hunt should not drift between draw, reference, and
inventory classifications just because one year's PDF title was cleaner than
another year's title.

## Canonical Filename Rule

Every active draw-result PDF should use:

```text
<SOURCE_YEAR>_PERMITS=<TARGET_YEAR>_MODEL__<SOURCE_TITLE>_DRAW_RESULTS.pdf
```

Where:

- `TARGET_YEAR = SOURCE_YEAR + 1`
- title text is uppercase
- spaces and punctuation become underscores where practical
- official abbreviations stay intact when they clarify the source: `G.S.`,
  `D.H.`, `L.E.`, `P.L.E.`, `O.I.L.`
- CWMU files may live under a `CWMU/` subfolder but keep the same filename rule
- parent bundles, originals, purchase pages, and point-summary pages may remain
  in source/reference subfolders, but they are not the active scoring source

## CWMU Folder Rule

CWMU sources use a two-level stack under active `draw_odds`:

```text
draw_odds/
  CWMU/
    ANTLERLESS CWMU/
    BIG GAME CWMU/
```

Use `CWMU/ANTLERLESS CWMU/` for:

- adult antlerless CWMU draw results
- youth antlerless CWMU draw results
- CWMU doe pronghorn draw results

Use `CWMU/BIG GAME CWMU/` for:

- CWMU big-game draw results
- CWMU limited-entry/O.I.L.-style species splits
- species/sex CWMU big-game child PDFs

If a year publishes CWMU rows inside a first-level parent bundle, peel those CWMU
pages or child PDFs into this stack before promoting the source as active for
scoring. The parent bundle stays outside active `draw_odds`, under an ignored or
reference folder.

## Draw-Hunt Rule

`PREFERENCE_POINT` is a draw-hunt indicator when it appears in an official
draw-results source. It must not be used by itself to mark a row or source as
`REFERENCE_ONLY`.

These are official draw-result families when backed by draw-results PDFs:

- `GENERAL_SEASON_DEER`
- `YOUTH_GENERAL_SEASON_DEER`
- `LIFETIME_GENERAL_SEASON_DEER`
- `DEDICATED_HUNTER_DEER`
- `YOUTH_DEDICATED_HUNTER_DEER`
- `ADULT_ANTLERLESS`
- `YOUTH_ANTLERLESS`
- `YOUTH_ANY_BULL_ELK`
- `LE_BIG_GAME`
- `PLE_BIG_GAME`
- `OIL_BIG_GAME`
- `CWMU_BIG_GAME`
- `BEAR_DRAW_RESULTS`
- `COUGAR`
- `TURKEY`
- `SPORTSMAN`

## Non-Scoring Source Roles

The following sources are valid lineage or inventory inputs, but are not direct
probability-scoring sources:

- parent bundles
- original unsplit bundles when split child PDFs are active
- purchase pages
- bonus-point summary pages
- point-only pages
- permit-quota inventory files
- conservation or auction permit files

Conservation permits are benefit or auction permits, not public draw permits.

## Total Lane Rule

`TOTAL` is a lane, not an `All` residency value.

When an official PDF supplies only a total applicant pool for a preference draw,
the row remains scoreable if it has real `p_draw` and nonzero applicants. Do not
invent resident/nonresident lanes when the source only supports total.

When a source supplies resident and nonresident lanes, total permits are expected
to reconcile to the resident plus nonresident allocation.

## Draw-Line Rows

Official ladder rows with zero applicants or no probability remain part of the
actual draw-line ladder. They are structural authority rows, not MAE/RMSE rows.
They help define what is above, at, or below the draw line.

## Cougar Exception

Cougar is a draw-result family through permit year 2023 when backed by draw
results. After permit year 2023, cougar sources are license/status context unless
the source explicitly publishes draw-results rows.

This is the only standing year-to-year exception in the draw/source-role policy.

## Bear Rule

Limited-entry black bear draw-result rows are draw rows. Bear pursuit,
harvest-objective, status, conservation, or inventory-only rows are not public
draw probability rows.

## Key Construction

Scoring comparable rows use:

```text
target_year
source_family
draw_system_type
draw_pool
hunt_code
score_scope
residency
points
probability_metric
```

joined as `official_score_key_v2`.

The file name may help infer source family, but it is not the score key. The
source alias manifest and PDF-derived row shape are the routing authority.

## Collision Policy

If two files normalize to the same path:

- do not overwrite either file
- compare hashes
- keep one active source only when the duplicate is proven identical
- otherwise mark the collision for review
- parent or reference copies stay inactive for scoring

## Required Audit

Every yearly source audit should report:

- files by year
- files by source family
- files by source role
- active scoring files
- parent/reference files
- unresolved aliases
- collision targets
- unknown source-family candidates
- whether cougar is pre- or post-2023 policy

Certification blocks if an active scoring source is unknown, unresolved, or
mapped only through a parent/reference file.
