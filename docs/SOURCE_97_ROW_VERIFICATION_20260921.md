# Remaining 97 source rows: numeric verification and identity limits

Status: 95 numerically verified; two legacy pool identities remain unresolved.
No canonical, long truth, DATABASE, engine, frozen forecast or runtime changed.

## Results

| Population | Reviewed | Result |
| --- | ---: | --- |
| Sportsman 2017-2024 | 87 | Original PDF values match in 1,068 comparisons |
| DB0008 legacy PDF-derived rows | 8 | Five applicant/award fields per row match retained UtahDraws records |
| DB1592 NR/3 and DB1630 NR/2 legacy rows | 2 | Counts match both pools; missing legacy pool label remains ambiguous |

The Sportsman reports are multi-hunt outcome tables, not point ladders. The
new parser reads displayed coordinates (including rotated 2017 pages), retains
exact codes, checks each row's arithmetic, and reconciles all parsed rows to
the printed grand total. Duplicate codes, unparsed rows and bad totals fail.
The 2021 report legitimately contains both CG1000 and CG9999; its footnote says
the extra cougar permit was offered once. No code alias or fixed species count
was used to force completeness.

Cell evidence distinguishes printed outcome counts, count-derived probability,
ratio formatting normalization, random-only component normalization, and the
2017 nonparticipating nonresident N/A representation. N/A is retained in source
evidence; its canonical zero representation is not a nonresident odds claim.

## DB0008 correction to the earlier reference-only interpretation

DB0008 is explicitly an extended-archery-only general-season buck deer draw
permit. Evidence:

- `pipeline/RAW/hunt_unit_database/2026/pdf/guidebooks/biggameapp.pdf`, physical/printed pages 9 and 44; SHA256 `84e2e3529b527291eb7a8dbe4ab814f6687d719e5c0116fc7dc318756ed9cd75`.
- `pipeline/RAW/hunt_unit_database/2026/pdf/guidebooks/field_regs.pdf`, pages 9 and 44; SHA256 `f7ac56f7f4ba480f63c512d31af2247f852d065ba2e2d4f8cf1ceeea688fc94b`.
- [Official DWR extended-archery explanation](https://wildlife.utah.gov/extendedarchery).
- Retained September-2 general-season deer endpoint: HuntID 1182, preference-point design, separate residency and IsYouth records.

Each of the eight old rows has a unique matching positive raw vector. Audit-only
pool recovery reuses the existing source-label recovery helper; it does not
guess adult/youth from hunt names or treat missing endpoint rows as zero odds.
The eight rows include both source pools. Their canonical availability labels
are incorrect, and the classifier also contains a generic extended-archery
random-target branch. That scoped metadata/routing repair remains required;
these verified outcomes must not be discarded as reference-only.

## Why two legacy rows still have no pool assignment

- DB1592 / Nonresident / 3: 1 applicant, 1 award in both raw pools.
- DB1630 / Nonresident / 2: 2 applicants, 2 awards in both raw pools.

Both adult and youth versions already exist as independently labeled canonical
endpoint records with exact HuntID, pool flag and source-row identifiers. The
targeted receipt records their canonical line numbers and identifiers. The
legacy generated-PDF path is not present; numeric equality cannot reconstruct
which pool that unlabelled copy meant. No duplicate was deleted or assigned a
pool to improve scoring. Retain the legacy ambiguity outside independent scoring
and use the already verified typed endpoint records, subject to the normal
scoring and release gates. No new forecast sample was created by this audit.

## Evidence and reproduction

Full audit: `audit_output_real_final/source97_verified_row_review_20260921/`.
Targeted receipt: `audit_output_real_final/source97_resolution_20260921/`.
Old reports preserved. The full audit still exits BLOCKED because remaining
source uncertainties (including nonscorable structural records) are not waived.

```powershell
python engine/utah/quality/build_source_mapping_and_hunt_crosswalk.py --out-dir audit_output_real_final/source97_verified_row_review_20260921
python scripts/review_remaining_source_rows.py --previous audit_output_real_final/locked_integrity_source_row_review_20260921 --current audit_output_real_final/source97_verified_row_review_20260921 --out-dir audit_output_real_final/source97_resolution_20260921
```

For another run choose fresh output directories: the scripts reject overwrite.
The second command intentionally exits 1 while the two pool ambiguities remain;
its failures list is empty and all protected input hashes are unchanged.
