# ADR-0009: Restricted-pursuit limited-evidence policy

- Status: Accepted and frozen for prospective candidate evaluation; not a model acceptance or release
- Date: 2026-09-20
- Authority: Tyler's explicit instruction to freeze this policy before scoring the next revised candidate
- Policy ID: `bear-restricted-pursuit-limited-evidence.v1`
- Machine contract: `governance/bear-restricted-pursuit-limited-evidence.v1.json`
- Extends ADR-0006/0007 with a separate provisional review outcome. Does not
  supersede their `CERTIFIED` thresholds or publication contract, or ADR-0008.

## Decision and scope

Only `BEAR_RESTRICTED_PURSUIT_BONUS` may use this pathway. Limited-entry Bear
hunting, purchased pursuit, harvest-objective availability and all other
families are excluded. A census of the eligible official history can be too
small to reach 400 scored point rows. Repeating folds, duplicating rows,
combining programs or residencies, or adding zero-applicant/reference rows
does not create evidence.

This policy permits a separate local evidence outcome,
`PROVISIONALLY_VALIDATED_LIMITED_EVIDENCE`, labeled exactly
**“Provisionally validated—limited evidence”**, only after every safeguard
below passes. It is not `CERTIFIED`. The 400-row minimum remains unchanged for
ordinary certification; only the provisional review substitutes a complete
history census and grouped uncertainty review for that minimum. No lower
arbitrary point-row cutoff is substituted.

No existing Bear candidate receives this outcome through this decision.
Previously viewed historical results, including the five- and eight-fold
reviews, remain development/diagnostic evidence, not newly unseen holdouts.
Current accuracy failures remain failures. The existing production registry
and four certified core designs are unchanged.

## Unchanged accuracy and source gates

| Gate | Requirement |
| --- | --- |
| Following-year comparisons | At least two distinct adjacent-year comparisons |
| Mean absolute probability error | At most 0.10 (10 percentage points) |
| 90th-percentile absolute probability error | At most 0.30 |
| Fraction with absolute error strictly greater than 0.25 | At most 0.10 |
| False guarantees | Zero, using ADR-0006's `0.999999` definition |
| Unclassified eligible actual gaps | Zero |

Use the existing scorer's point-row weighting, error definitions and quantile
convention. Applicant-weighted or cluster-weighted metrics may be additional
diagnostics, never replacements selected to produce a pass. Score the exact
final website calculation, not just the family output. Retain uncapped
false-certainty diagnostics; moving a probability ceiling is not a repair.

All ADR-0008 source boundaries continue to apply: official PDF-linked yearly
canonicals/unified truth, reconciled R/NR lanes, no aggregate `All` reuse,
no duplicates or hunt-total double counting, source-year-only forecasts,
pre-draw identity evidence, program-local point behavior and no historical
`DATABASE.csv` reads. No target result may supply forecast demand or quota.

## Complete coverage, not a selected successful subset

Before scoring, freeze an inventory of all eligible official restricted-pursuit
history from the project's 2017 start through the declared evidence cutoff.
Source year 2017 can support the first 2018 target; six source years do not
mean six independent comparisons. Inventory missing official documents too;
an unresolved source gap blocks review rather than shrinking the census.

For each target year, retain exact code, verified identity/regime, residency,
point level, source path/page/hash, eligibility decision and its evidence.
Every eligible actual must reconcile to either a numeric forecast or an
explicit, source-supported missing-forecast disposition. Report scored and
missing counts and coverage rates overall and for every subgroup. Present-but-
blank forecasts count as gaps. An unscorable official row needs its own
disposition; it is not a success or a replacement sample.

A gap is acceptable only when the source-only rule genuinely prevents a
forecast (for example, no comparable prior lane, changed program/boundary,
no transition evidence or unavailable supported quota). Missing implementation,
unexplained joins and source defects block. A later realized miss or allocation
change may not be relabeled as a gap. All numeric misses remain scored.

## Across-year, hunt and residency safeguards

Publish local audit breakdowns for each target year, verified hunt identity,
residency, year-by-residency and hunt-by-year-by-residency, including sparse
and empty cells. Include row/applicant counts, cluster counts, MAE, P90, tail,
bias, false guarantees and every missing-forecast reason.

The pooled design and each resident/nonresident lane must meet the unchanged
accuracy gates; neither residency can rescue the other. A lane without
scorable evidence cannot be called provisionally validated. Year/hunt cells
are not separately certified. Flag every cell exceeding any accuracy limit;
the same hunt/regime/residency exceeding the same limit in two or more
distinct target years is a recurring failure and blocks the provisional
outcome. Do not drop a bad year/hunt or invent a new population after scoring.

## Grouped uncertainty specification

Related point rows are not independent observations. The atomic primary block
is `(target_draw_year, verified_hunt_identity, program_regime)` containing ALL
point levels and both residency lanes. Identity groups are fixed from reviewed
pre-draw lineage; a boundary/program change starts a new regime. Residency
metrics use the appropriate rows inside the same resampled blocks, not a
separately cherry-picked resample.

Freeze these three nonparametric resampling analyses:

1. **Hunt/year blocks:** sample the observed blocks with replacement, keeping
   all their rows together and the original number of blocks per replicate.
2. **Whole hunt histories:** sample verified hunt/regime groups with replacement,
   preserving all their target years and rows; this checks repeated-hunt dependence.
3. **Whole draw years:** sample target years with replacement, preserving every
   hunt and point row; this checks shared year effects.

Use 10,000 replicates per analysis, NumPy `Generator(PCG64(20260920))` reset
for each analysis, lexically sorted group IDs and equal-probability group draws.
Recompute the existing row-weighted MAE, P90, tail and bias inside each
replicate. Report two-sided percentile 95% intervals (linear quantiles at
0.025/0.975), separately for the pooled design and each residency, for all
three analyses. Also report leave-one-year-out and leave-one-hunt-out metric
ranges and all threshold crossings. Never report the narrowest interval alone.

These are dependence-sensitivity intervals, not a claim that one clustering
choice captures every correlation. Report the number of unique years, hunts
and hunt/year blocks; never label the point-row count or the resample count
as the independent sample size. Each analysis needs at least two contributing
groups for each reported population. Empty/undefined replicates and omitted
intervals must be disclosed, not redrawn or filled; an unestimable required
interval blocks the provisional outcome as insufficient evidence.

The numerical acceptance gates apply to the original metrics, not a favorable
bootstrap replicate or bound. Interval width and sensitivity remain explicit
limited-evidence qualifications, not a new post-hoc accuracy threshold.
The resampling implementation must pass synthetic block-integrity,
determinism and empty-group tests before any revised candidate is scored.
This policy-only change does not implement or claim to have run that analysis.

## Freeze order, status and genuinely unseen confirmation

1. Verify this ADR and machine-policy hashes against `engine-authority.json`.
   A change requires a new version/ADR and approval before a new scoring run;
   never overwrite the frozen v1 to fit results.
2. Before scoring the next revised candidate, retain a timestamped manifest
   binding those policy hashes, source inventory/cutoff, eligibility and gap
   rules, reviewed identity groups, fold roster, implementation/scorer versions,
   parameter choices and random seeds. Record all previously viewed results.
3. Freeze source-only forecasts and the final publication calculation's exact
   bytes before the scoring process opens each following-year actual. Record
   all attempted candidates, not only the best one. Reusing known historical
   results is development evaluation, not genuinely unseen confirmation.
4. Produce a separate, hash-linked local policy review. Failed accuracy or
   recurring errors mean `NOT_VALIDATED_ACCURACY`; missing source, coverage,
   leakage or uncertainty evidence means `INSUFFICIENT_EVIDENCE`. Only a
   complete passing review may emit the provisional label. Preserve every
   blocking reason when more than one applies.
5. Preregister and seal a prospective forecast before a later drawing and
   before anyone developing/selecting this candidate has seen its results.
   Use a later year if the proposed holdout has already been inspected.
   Score that unchanged forecast once official results arrive, with the same
   source, coverage, accuracy and subgroup requirements. Failed confirmation
   must be reported; do not retune and call the same drawing unseen again.

Until that confirmation, the strongest permitted evidence label is provisional.
Confirmation alone does not grant `CERTIFIED`: ordinary ADR-0006/0007 gates
and a separate production review still apply. If the 400-row requirement is
still unmet, any future full-certification exception needs its own prospective
approval; it is not silently granted here.

The provisional outcome is a local review field, not a new production registry
status or public probability permission. `certified_p_draw*` remains blank for
non-certified rows. No runtime/UI, source truth, quota, saved predictions,
registry, R2 object or deployed site is changed by adopting this policy.
