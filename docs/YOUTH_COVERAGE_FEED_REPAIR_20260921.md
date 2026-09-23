# Youth coverage feed repair — 2026-09-21

## Outcome and scope

All 1,398 original blocking coverage keys now have scored forecasts. The independent
audit found zero repeated scored keys and verified every unrelated retained
forecast field against its original frozen row. This is a local coverage repair,
not a new certification or a production release.

Evidence root: `audit_output_real_final/youth_coverage_feed_repair_20260921_v1/`.
`coverage_repair_integrity.json` records PASS; `original_gap_resolution.csv`
accounts for each original key as `NOW_SCORED`. None of these original gaps was
removed from scoring or reclassified as an exception to improve accuracy.

| Original blocking population | Rows now scored |
| --- | ---: |
| Youth general-season deer | 752 |
| Youth antlerless elk | 444 |
| Youth antlerless deer | 106 |
| Youth doe pronghorn | 96 |
| Total | 1,398 |

## Demonstrated causes and owning repairs

1. The youth general-deer output label `YOUTH_GENERAL_DEER_RESERVE` and pool
   `youth_general_deer` did not match the scorer's parent preference design and
   distinct `youth_general_season_deer` pool. Normalized those identities in the
   existing projection and scorer; adult and youth pools remain separate.
2. Quota-only youth reserve placeholders were counted as completed forecasts by
   the existing source fallback. The declared family runner now hands off only
   explicit `IN_SCOPE_MODEL_PENDING` / `YOUTH_RESERVE_PROBABILITY_INPUT_MISSING`
   placeholders, with `youth_reserve_model_valid=FALSE` and no actual modeled
   probability, when the exact youth code/pool/residency/point source lane has
   positive applicants. The fallback itself is pre-existing; this does not add
   a new cohort model or infer odds from quota totals.

The fallback is a historical same-rung probability roll-forward, not a measured
returning-applicant model. Its forecasts remain experimental. Prior-year 100%
outcomes remain blank under the existing copied-guarantee guard. Real modeled
zero probabilities, real modeled positive probabilities, deliberate
`NO_TRANSITION_EVIDENCE`, and other intentional abstentions are not replaced.
Empty source rows cannot fill a placeholder. Adult or nonresident source evidence
cannot replace a distinct youth resident lane.

There were 1,177 source-inventory fallback handoffs across the nine frozen
candidate files. This is a different population from the 1,398 originally
blocking actual keys: alias repair also restores existing forecast matches, and
some source handoffs remain intentional blanks or have no scorable target row.
Do not conflate these counts.

## Reproduction and evidence boundaries

`scripts/repair_youth_coverage_feeds.py` reuses the declared family owner, final
`mixed_row`, existing projection, scorer and all-family review. It freezes all
nine scoped candidate files before reading any target actual rows for scoring.
New fallback rows use only their source-year canonical. Each freeze records the
source, original forecast, candidate forecast and owning implementation hashes.
The current candidate retains unavailable historical runtime prior/harvest blend
inputs as `None`, as in the baseline replay.

`scripts/audit_youth_coverage_repair.py` independently compares every original
retained forecast row field-for-field, validates replacement eligibility and
added source-family lineage, rejects repeated scored keys, and reconciles the
original gap list. New candidate probabilities are not retroactively written
into the original frozen forecasts.

The adopted acceptance window remains 2017→2018 through 2024→2025. The
2025→2026 fold is a separately labeled diagnostic. These are known retrospective
years, not newly unseen holdouts. The two populated 2026 deer rows with unresolved
youth dimensions remain a source-identity hold; this coverage repair does not
settle them. Existing Bear probability ceilings are not proof of repaired
uncapped certainty risk.

## Completed nine-fold review

All nine physical adjacent-year folds completed, with zero unresolved coverage
gaps in every fold. Combined: **137,940 independent scored keys**, MAE **9.0876 pp**,
P90 **27.6077 pp**, **14,350** errors over 25 pp (**10.4031%**), and zero reported
final-output false guarantees. This pooled tail exceeds the 10% gate and cannot
certify the overall engine. It is not a substitute for individual-design review.

The previous identity-reconciled review had 135,963 keys: the expanded population
adds 1,977 scored keys, including all 1,398 original blocking gaps and additional
newly matched rows. The newly scored errors are retained, not removed to recover
the previous lower MAE/tail. The 2025→2026 diagnostic alone has 17,429 scored keys,
8.6428 pp MAE, 25 pp P90, 9.9834% tail and zero unresolved gaps.

Adopted eight-fold youth results remain **not accepted**:

| Youth source pool | Scored keys | MAE (pp) | P90 (pp) | Tail over 25 pp |
| --- | ---: | ---: | ---: | ---: |
| General-season deer | 1,186 | 49.2583 | 100 | 52.2766% |
| Antlerless deer | 300 | 41.6961 | 100 | 48.3333% |
| Antlerless elk | 1,254 | 41.9983 | 100 | 49.2026% |
| Doe pronghorn | 439 | 18.9240 | 100 | 23.9180% |

These results show that the existing youth fallback is inadequate for
certification. The next accuracy audit should examine these source/target youth
ladders, not reuse adult probabilities or relax thresholds. Adult LE, OIL,
Premium LE and general deer retain their earlier eight-fold numeric/classified
coverage results; no new registry approval is made here.

## Concurrent working-tree changes — promotion remains blocked

The completed workflow deliberately exited **1** with
`BLOCKED_PROTECTED_FILE_CHANGED`. Its final hash check found two files modified
after the baseline was captured:

- `engine/utah/quality/build_source_mapping_and_hunt_crosswalk.py`: an external
  patch prepended imports before the module's `__future__` declaration. This
  caused five tests to fail. Moved the new import below the existing path setup,
  preserving its code; all 120 focused tests then passed. The imported routing
  helpers are not invoked by this coverage repair and are not approved by it.
- `engine/utah_draw_predictive/bear.py`: concurrently changed from SHA-256
  `f7353ff2ac01a99b26ec373c9c3897b9dc4e7d835dab74f835efab92e17d7006` to
  `31ecf4d77b79868be0f8c8b205603ea649320f9f408fac37c951745b51f8970f`.
  Did not revert or adopt this unrelated change. Frozen Bear forecast rows were
  copied from the original forecast, not regenerated from this changed owner.

The separate coverage integrity audit still passes: all original gaps are now
scored, unrelated frozen forecasts are preserved, and no scored keys repeat.
The protected-file audit records the concurrent code changes rather than
silently refreshing their baseline. Official canonical/long/DATABASE files and
the original frozen forecasts were unchanged. The saved candidate evidence is
not a certification of the concurrently edited working tree.

## Verification

- 120 focused youth, source-boundary, identity, observed-outcome and scoring tests passed.
- Independent coverage/forecast-preservation audit: PASS; all 1,398 original gaps now scored.
- Project-memory validation: PASS, 151 checks. Public-manifest exposure guard: PASS.
- All nine candidate files frozen before target scoring; every original forecast preserved separately.
- Full per-family review and protected-input verification: see `review/summary.json`
  and `review/protected_file_verification.json` under the evidence root. Coverage
  passes; the two concurrent code changes keep the protected-file gate blocked.

No canonical numbers, long-truth numbers or DATABASE fields were changed by this
repair. No normal Research runtime rebuild, registry promotion, staging, commit,
push, R2 upload or deployment was performed. Accuracy failures remain failures;
coverage completion alone cannot certify a draw design.
