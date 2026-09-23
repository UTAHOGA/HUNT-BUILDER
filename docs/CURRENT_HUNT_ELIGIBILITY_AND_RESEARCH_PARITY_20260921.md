# Current-hunt eligibility and Research selection parity

Status: **LOCAL CANDIDATE / NOT DEPLOYED**. Date: 2026-09-21.

## Eligibility is not catalog membership or certification

The broad catalog retains 1,848 codes. Its current-selection projection now uses
the hash-recorded inputs in `data/hunt-eligibility-2026.json`: DATABASE identity,
retained dated Planner rows, the reviewed active baseline, and the separate
current identity/quota feeder audit. It does not create a new truth authority.

| Classification | Codes | Current selectable |
| --- | ---: | --- |
| Current 2026 Planner evidence | 1,386 | Yes |
| Retained active 2026 baseline, no current Planner match | 38 | Yes |
| Historical/retired catalog evidence | 104 | No |
| Explicit noncurrent feeder evidence | 2 | No |
| Reference with insufficient current eligibility evidence | 318 | No |
| Total | 1,848 | 1,424 selectable; 424 separately retained |

The 424 are not all proven discontinued hunts. Unverified references remain
distinct from documented historical records. No source catalog, DATABASE row,
canonical, or historical PDF was deleted. Retired PD1025 is excluded while
successor PD1050 remains selectable. Filtering also runs after synthetic Builder
additions, and historical direct Research selections withhold current reports.

The generator records 26 current Planner codes absent from the broad catalog;
it does not silently add those other-program records. This is a retained-evidence
reconciliation, not a fresh DWR census, and is not a claim that every selectable
code has public draw odds. The 38 baseline-only codes retain their evidence label.

Owners: `scripts/build-current-hunt-eligibility-2026.py`,
`assets/js/current-hunt-eligibility.js`, `data.js`, `app.js`. The manifest is
included in the website packager; missing eligibility evidence fails closed.

## Why the summary could disagree with the ladder

The browser does not directly read either DATABASE.csv or the yearly canonicals.
It loads released derived Research summary/index/per-hunt JSON. DATABASE supplies
current identity and permit-reference context through the catalog. Historical
draw truth remains yearly canonicals -> long file -> engine -> Research artifacts.
Current permit references and historical awarded permits are different quantities.

The local presentation repair addresses demonstrated defects without altering
model probabilities:

- The summary now uses the same exact selected point row as the ladder. A missing
  rung cannot borrow the first/highest engine row's probability.
- A default pool resolves only one unambiguous residency pool; an explicit pool
  cannot silently fall back to a different adult/youth pool.
- The Outlook panel consumes the core selected row and shared odds/harvest display.
- Only explicitly named harvest-percent fields can supply harvest success. Draw
  success ratios, prior draw probabilities, and harvested counts are not harvest
  percentages. A recorded 0.5 percent stays 0.5 percent, not 50 percent.

Browser checks cover MB6011 Resident 12/30 and Nonresident 12, BR7004 Resident 12,
DA1001 Resident 3, and retired PD1025. Core/ladder/Outlook agree; MB6011 harvest
stays 87 percent across points; unsupported probabilities remain blank. Existing
very-small-odds percentage rounding (e.g. a positive probability displayed as 0%)
is not corrected by this selection repair. Other metadata contracts are not
claimed fully reconciled by these six checks.

## Fresh antlerless verification: not certified

Regenerated all nine source-only adjacent-year forecasts, 2017->2018 through
2025->2026, using the existing engine and final `mixed_row` calculation. Scored
against the full exact-target-year adult canonical population, not the older
previously-scored subset or a mixed adult/youth join. These are known historical
years: this replay is verification, not newly untouched blind evidence.

| Preference design | Scored | MAE (pp) | P90 error (pp) | Error >25 pp |
| --- | ---: | ---: | ---: | ---: |
| Antlerless deer | 1,181 | 11.637 | 45.555 | 17.528% |
| Antlerless elk | 6,335 | 16.558 | 60.500 | 25.762% |
| Doe pronghorn | 1,256 | 12.410 | 49.900 | 16.640% |

All three fail the frozen limits (10 pp MAE / 30 pp P90 / 10% tail). Formal false
guarantees are zero; near-certainty misses remain 35 deer / 215 elk / 54 doe.
The census retains 2,249 missing forecasts (905 NO_TRANSITION_EVIDENCE and 1,344
absent), 576 positive-applicant rows without official probability, and 30,360
zero-applicant rows. Those gaps need source classification; they are not erased
from the coverage denominator to obtain a pass. Total scored: 8,772.

Evidence:
`audits/prediction_release_candidates/antlerless_eligibility_followup_20260921_v1/`
and `full_adult_census/verification.json`, `scores.csv`, `census.csv` within it.
`scripts/verify-antlerless-adjacent-year-forecasts.py` reuses the retained
pool-aware actual projector and hashes forecasts/actual inputs; it is an audit
wrapper, not a replacement engine. No engine formula or registry was changed
by this task. Existing owner edits present at task start were used as-is.

## Verification and release boundary

- Eligibility JavaScript contract, Research certification guidance and ladder
  panel tests pass. Eligibility Python tests: 4 passed. Research source-scope
  tests: 11 passed. Six local browser cases pass with no JavaScript page errors.
- Antlerless preference plus historical target-year tests: 16 passed, 2 failed.
  The two existing failures require every forecast to be nonblank despite
  intentional NO_TRANSITION_EVIDENCE rows. They remain reported and unwaived.
- Project-memory validation still has the two pre-existing DATABASE raw-hash /
  stale prediction-build failures. No authority input hash was replaced merely
  to obtain a pass.
- No full build was run: this dirty main checkout's build can regenerate data
  and differs from the isolated previously released corrective worktree.
  Inclusion in the packager and local browser checks are not a production build
  or all-hunt live validation.
- Nothing staged, committed, pushed, uploaded to R2, or deployed. Historical
  truth and current DATABASE were not edited. Antlerless remains NOT CERTIFIED /
  DO NOT PROMOTE. The same is true of the recorded Bear decision; this task did
  not reevaluate Bear.

Next: classify the 2,249 antlerless forecast gaps against exact source ladders,
then isolate repeatable cutoff/demand errors by family and residency without
using held-out actuals as forecast inputs or relaxing acceptance limits.
