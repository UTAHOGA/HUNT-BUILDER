# 2026 source-pool label recovery

Applied locally to the 2026 yearly draw canonical and canonical-derived long file.
No engine, forecast, DATABASE, current hunt-master, quota, applicant count, award,
probability, or live runtime was changed.

## Result

- 27,751 previously blank `source_is_youth` cells recovered from retained source
  evidence; the same 27,751 metadata cells synchronized into the long file.
- Post-application raw endpoint comparison: 21,806 matching rows, 109,030 numeric
  cells, zero differences. Every populated applicant/award component was checked,
  including explicit zero regular awards.
- 10,236 empty display rungs have no corresponding endpoint row. They remain
  classified as structural records, not verified zero probabilities.
- 520 rows retain unresolved source-pool metadata: 518 have no applicants or
  awards, and two positive-applicant rows have equal raw vectors in both pools.
- 272 reference records remain outside draw-outcome numeric verification.
- 39 focused tests passed. Strict long-file comparison passes all 338,574 rows
  across ten yearly canonicals and all 103 columns.

The two positive ambiguities are DB1592 / Nonresident / 3 points and DB1630 /
Nonresident / 2 points. In the retained UtahDraws endpoint, the first has 1 applicant
and 1 award in both pools; the second has 2 applicants and 2 awards in both pools.
Neither can be assigned a pool from those identical counts alone. These are two
rows, not two wholly unavailable hunts.

## Recovery rules and boundaries

1. Preserve explicit pool flags and check source identifiers for conflicts.
2. Where the exact endpoint hunt has only one typed pool across *all* its rows,
   recover that flag. Never infer it from one sparse rung alone.
3. For shared-code PDF-derived rows, an exact multirow parent-table fingerprint
   may identify a pool. It requires at least two distinct positive anchors and a
   real competing-pool value contradiction; conflicting keys remain unresolved.
4. A positive row may also be matched by its complete populated numeric vector
   to a unique raw record with the same hunt, residency and points. No nearest
   match, percentages, or forecast error is used. Equal vectors remain ambiguous.
   This is same-year transcription reconciliation, not a blind prediction test.
5. Preserve coalesced or conflicting labels. The application guard caught one
   TK1018 row with combined true/false source identifiers in the first candidate;
   it was left ambiguous in the final version, not replaced by the first flag.
6. Do not inherit a prior-year label solely from a continuing hunt code.

Recovery methods for the newly filled cells: 26,424 exact single-pool endpoint
hunts, 1,142 exact positive source-row vectors and 185 exact parent-table vectors.

## Hunt eligibility is not the endpoint pool flag

The separate recovery ledger records Planner eligibility, its source URL, and
hash-verified guidebook code/page references. EB1007 is explicitly a draw-only
youth hunt in Planner and the 2026 Big Game Application guidebook (pages 39/54),
but its endpoint records have `IsYouth=False`. That flag therefore cannot be
treated as a general adult-only eligibility label. General entries without an
explicit youth-only designation are described as such, not asserted adult-only.

## General-season deer totals versus residency records

The user's supplied identities match the retained current Planner:

| Code | Unit and weapon | Planner total | Endpoint resident regular-round quota | Endpoint nonresident regular-round quota |
| --- | --- | ---: | ---: | ---: |
| DB1592 | Kamas; early any legal weapon | 200 | 97 | 10 |
| DB1630 | Boulder/Kaiparowits; restricted muzzleloader | 720 | 349 | 39 |

These are different source fields/scopes and capture dates, not a requirement
that the regular-round pair equal the Planner total. No source was overwritten
with another. The retained September-2 UtahDraws general-deer package contains
107 entries: 105 ordinary deer hunts, DB0008 extended-archery reference, and GDR
point purchase. All 105 ordinary hunts have typed resident/nonresident rows,
explicit regular-round quota fields and both source-pool flags. In the fresh
September-21 Planner, their residency fields are zero and the combined total is
populated. The same pattern is therefore broad, not unique to these two hunts.
Planner-only split zeroes cannot justify removing official residency lanes.

## Evidence, backups, hashes

Final pre-application candidate, label-by-label evidence, raw-parent hashes,
guidebook references, application receipt and rollback copies:
`audit_output_phase1_candidate/source_pool_recovery_20260921_v4/`.
Post-application numeric replay:
`audit_output_phase1_candidate/source_pool_recovery_20260921_postapply/`.

New 2026 canonical SHA-256:
`527ff21fbd9a49d1868488f8ca783ba16bb123ee806cd3c57e115d03d1dbe039`.
New long SHA-256:
`8dc4d037e0be6ac14bdd8281673d44e5af7f2f6a55168e4c66dca5302c3ac209`.

Both prior files have hash-verified rollback copies. Every other cell was compared
before replacement; zero nonlabel changes were allowed. All earlier candidates
and audit reports remain retained under their original hashes.

The existing freeze validator initially rejected the established column order
despite matching column sets. It now uses the owning builder's
`stable_output_header` contract, retaining strict row/value checks and rejecting
missing/duplicate columns. Regression testing proves actual cell changes still
fail. The failed initial report and passing final report are both retained.

This metadata revision supersedes older source-label audit counts, not previous
engine acceptance results or deployed runtime hashes. The broad numeric/source
closure gate remains blocked by the explicitly unresolved rows/scopes. Existing
DATABASE authority/stale-build failures remain unwaived. No stage, commit, push,
upload, certification promotion or deployment occurred.
