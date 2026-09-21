# Bear availability validation — 2026

Verified: 2026-09-19. Scope: local code repair, direct DWR PDF inspection and read-only artifact comparison. **Not a certification, regeneration of production data, or release.**

## Decision

**Four availability records are not four limited-entry Bear hunts.** The official 2026 guidebook lists **90 limited-entry hunting hunt codes** and **9 restricted-pursuit drawing codes**. Neither group belongs in `MODELED_AVAILABILITY`.

The current catalog has three non-draw product codes, representing four product/residency records: BR1001 Resident and Nonresident (harvest objective), BR1007 Resident (general pursuit), BR1018 Nonresident (general pursuit). Fresh local generation now produces those identities correctly. The three-code allowlist was **not expanded**.

The existing saved four-row count is invalid evidence: all four records in `processed_data/ml_draw_predictions_v1.csv` are named **Sportsman Bison**, identify the species as **Bison**, and use **Resident**. The two BR1001 rows duplicate the same residency. Saved production files were deliberately not repaired or replaced.

## Official sources and inspection

These exact official PDFs were downloaded and hashed, not inferred from search summaries. Page numbers below are one-based PDF pages and match the printed table-page numbers. Rendered table pages were visually inspected: 2024 pp. 36–44, 2025 pp. 42–49, and 2026 pp. 73–80.

| Year | Official PDF | SHA-256 | Draw tables | Harvest-objective tables |
|---|---|---|---|---|
| 2024 | [DWR guidebook](https://wildlife.utah.gov/guidebooks/2024_bear.pdf) | `0dd6ac7f752352fef15b4746a601b9c79fc81c0529c03b02900c7c369a13c5e7` | 36–42 | 43–44 |
| 2025 | [DWR guidebook](https://wildlife.utah.gov/guidebooks/black-bear-and-cougar-guidebook-2025.pdf) | `be5da034dd02a1453f5bc220101b9cf7b7ae8a5e6566043b3606fe3d72cda5ee` | 42–48 | 48–49 |
| 2026 | [DWR guidebook](https://wildlife.utah.gov/guidebooks/black-bear-cougar-furbearer-guidebook.pdf) | `fd1e698efb65fb21ed14221865ce2d762ee983af4c982be8972d907a736d53e8` | 73–79 | 79–80 |

Retained sources and all page images: [source evidence](../audits/bear_availability_validation_20260919/source_evidence/). Representative table screenshots:

- 2024: [spring p. 36](../audits/bear_availability_validation_20260919/source_evidence/2024_page-36.png), [restricted pursuit p. 42](../audits/bear_availability_validation_20260919/source_evidence/2024_page-42.png), [harvest objective p. 43](../audits/bear_availability_validation_20260919/source_evidence/2024_table-43.png).
- 2025: [spring p. 42](../audits/bear_availability_validation_20260919/source_evidence/2025_table-42.png), [restricted pursuit p. 47](../audits/bear_availability_validation_20260919/source_evidence/2025_table-47.png), [pursuit and harvest objective p. 48](../audits/bear_availability_validation_20260919/source_evidence/2025_page-48.png).
- 2026: [spring p. 73](../audits/bear_availability_validation_20260919/source_evidence/2026_page-73.png), [multiseason and restricted pursuit p. 78](../audits/bear_availability_validation_20260919/source_evidence/2026_page-78.png), [pursuit and harvest objective p. 79](../audits/bear_availability_validation_20260919/source_evidence/2026_page-79.png), [harvest objective p. 80](../audits/bear_availability_validation_20260919/source_evidence/2026_page-80.png).

Reproducible extraction: [audit script](../scripts/audit_bear_availability_regulations_2026.py). The final extraction is [inventory_v4/inventory.json](../audits/bear_availability_validation_20260919/inventory_v4/inventory.json); v1–v3 are superseded intermediate diagnostics. Separate CSV tables retain code, printed name, permit type, program, source page and source text for each year:

- [2024 draw codes](../audits/bear_availability_validation_20260919/inventory_v4/guidebook_bear_codes_2024.csv) and [harvest-objective units](../audits/bear_availability_validation_20260919/inventory_v4/guidebook_bear_harvest_objective_2024.csv).
- [2025 draw codes](../audits/bear_availability_validation_20260919/inventory_v4/guidebook_bear_codes_2025.csv) and [harvest-objective units](../audits/bear_availability_validation_20260919/inventory_v4/guidebook_bear_harvest_objective_2025.csv).
- [2026 draw codes](../audits/bear_availability_validation_20260919/inventory_v4/guidebook_bear_codes_2026.csv) and [harvest-objective units](../audits/bear_availability_validation_20260919/inventory_v4/guidebook_bear_harvest_objective_2026.csv).

The harvest-objective tables do **not** print hunt codes. Their code fields remain blank; no code was invented or assigned from a boundary. Printed harvest objectives are explicitly labeled **not draw quota** and are never fed into draw probability. Raw extracted names preserve PDF spelling/footnote glyphs; the screenshots are retained for review.

## Program and status definitions

| Program | Engine subtype | How obtained | Availability status? |
|---|---|---|---|
| Limited-entry hunting, including multiseason and spot-and-stalk | `LIMITED_ENTRY_BEAR_HUNT` | Bear drawing; hunting bonus-point program | No; only a source-supported draw model or honest pending/excluded disposition |
| Restricted pursuit | `RESTRICTED_BEAR_PURSUIT` | Separate pursuit bonus-point drawing; pursue, not kill | No; draw program remains separate from hunting and from general pursuit |
| Harvest objective | `HARVEST_OBJECTIVE_AVAILABILITY` | Purchased permit, subject to unit/season closures | Yes for the retained BR1001 product lanes; no draw odds |
| General pursuit | `UNLIMITED_PURSUIT_PERMIT` | Purchased pursuit permit; pursue, not kill | Yes for the retained BR1007/BR1018 product lanes; no draw odds |
| Sportsman Bear | Separate Sportsman owner, BR1000 | Sportsman drawing | Not Bear availability and not limited-entry Bear bonus modeling |

`MODELED_AVAILABILITY` is a shared algorithm/display classification, not a Bear subtype or proof of a modeled probability. `HARVEST_OBJECTIVE_AVAILABILITY` is a specific subtype. A generic `Pursuit`, `Pursuit Only`, or `O.T.C.` label alone must not turn a restricted-pursuit drawing into general-pursuit availability.

Official program references: 2024 pp. 18–19 and 42; 2025 pp. 19–20 and 47–49; 2026 pp. 20–22, 29–30 and 73–80. The 2026 guidebook explicitly distinguishes purchased general pursuit from drawn restricted pursuit. Its three spring restricted-pursuit hunts are **Nonresident-only drawing lanes**; residents can purchase general pursuit permits for those units' spring seasons. The six summer restricted-pursuit codes list both residency allocations.

General pursuit's existing `p_availability=1` is a permit-category signal, **not 100% draw success, unrestricted unit access, or a live eligibility determination**. Harvest-objective output remains `SOURCE MISSING`/`UNKNOWN` for live closure status; the annual guidebook cannot prove today's unit is open. No current closure status was invented.

## Four current non-draw records

| Catalog code | Expected name/species | Residency | Meaning | Fresh output |
|---|---|---|---|---|
| BR1001 | Harvest Objective Units / Black Bear | Resident | Purchased harvest-objective permit | Availability; all draw probabilities blank |
| BR1001 | Harvest Objective Units / Black Bear | Nonresident | Purchased harvest-objective permit | Availability; all draw probabilities blank |
| BR1007 | Pursuit / Black Bear | Resident | Purchased general pursuit | Availability; all draw probabilities blank |
| BR1018 | Pursuit / Black Bear | Nonresident | Purchased general pursuit | Availability; all draw probabilities blank |

**Evidence boundary:** BR1001, BR1007 and BR1018 are not printed in these guidebook hunt-code tables. Their exact IDs/names come from the retained current identity catalog and existing engine contract; the PDFs independently verify the non-draw permit categories and residency rules. This is not a claim that DWR's guidebook prints these three IDs or that Utah has only four limited-entry units.

A fresh invocation of the owning builder with the current three catalog records plus BI1000 as a preceding cross-species control produced exactly the four records above, without modifying the input records. No historical applicant or quota inference was involved in this availability-only check.

## Official table inventory by year

| Year | Spring hunting | Summer hunting | Fall hunting | Spot-and-stalk | Multiseason | Total hunting draw codes | Restricted-pursuit draw codes | Harvest-objective table rows / distinct names |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 2024 | 20 | 24 | 21 | 1 | 21 | 87 | 9 | 23 / 17 |
| 2025 | 19 | 24 | 22 | 1 | 22 | 88 | 9 | 27 / 21 |
| 2026 | 20 | 25 | 22 | 1 | 22 | 90 | 9 | 27 / 21 |

These are **hunt codes**, not unique geographic units, applicants, residency lanes, permits or predictions. Harvest-objective rows include repeated units across seasons. They cannot be compared directly with draw-code counts to assert that “most Bear hunts are OTC.”

### 2026 limited-entry hunting codes

All codes in the following five tables are hunting-draw inventory, never additions to the availability allowlist.

#### Spring — 20

| Hunt code | Printed unit name | PDF page |
|---|---|---:|
| BR7000 | Beaver | 73 |
| BR7001 | Book Cliffs, Bitter Creek/South | 73 |
| BR7224 | Book Cliffs, Little Creek Roadless | 73 |
| BR7012 | Boulder/Kaiparowits | 73 |
| BR7017 | Cache/Ogden | 73 |
| BR7015 | Diamond Mtn/Vernal/Bonanza | 73 |
| BR7021 | Dolores Triangle (new) | 73 |
| BR7007 | Fillmore, Pahvant | 73 |
| BR7013 | Fishlake/Thousand Lakes | 73 |
| BR7018 | Kamas/North Slope, Summit | 73 |
| BR7022 | La Sal Mtns | 73 |
| BR7003 | Manti, North | 73 |
| BR7004 | Manti, South/San Rafael, North | 73 |
| BR7020 | Monroe | 73 |
| BR7009 | Mt Dutton | 73 |
| BR7005 | Nebo | 73 |
| BR7010 | Panguitch Lake/Zion | 73 |
| BR7011 | Paunsaugunt | 73 |
| BR7014 | San Juan | 73 |
| BR7016 | Wasatch Mtns, West-Central | 73 |

#### Summer — 25

| Hunt code | Printed unit name | PDF page |
|---|---|---:|
| BR7100 | Beaver | 74 |
| BR7101 | Book Cliffs, Bitter Creek/South | 74 |
| BR7102 | Book Cliffs, Little Creek Roadless | 74 |
| BR7114 | Boulder/Kaiparowits | 74 |
| BR7121 | Cache/Ogden | 74 |
| BR7122 | Chalk Creek/East Canyon/ Morgan-South Rich | 74 |
| BR7117 | Diamond Mtn/Vernal/Bonanza | 74 |
| BR7126 | Dolores Triangle (new) | 74 |
| BR7124 | Fillmore, Pahvant | 74 |
| BR7115 | Fishlake/Thousand Lakes | 74 |
| BR7123 | Kamas/North Slope, Summit | 74 |
| BR7127 | La Sal Mtns | 74 |
| BR7104 | Manti, North | 74 |
| BR7105 | Manti, South/San Rafael, North | 74 |
| BR7125 | Monroe | 74 |
| BR7109 | Mt Dutton | 74 |
| BR7106 | Nebo | 74 |
| BR7110 | Nine Mile | 74 |
| BR7111 | North Slope, Three Corners/West Daggett | 74 |
| BR7112 | Panguitch Lake/Zion | 75 |
| BR7113 | Paunsaugunt | 75 |
| BR7116 | San Juan | 75 |
| BR7119 | Wasatch Mtns, Avintaquin/Currant Creek | 75 |
| BR7120 | Wasatch Mtns, West-Central | 75 |
| BR7118 | Yellowstone | 75 |

#### Fall — 22

| Hunt code | Printed unit name | PDF page |
|---|---|---:|
| BR7200 | Beaver | 75 |
| BR7201 | Book Cliffs, Bitter Creek/South | 75 |
| BR7215 | Boulder/Kaiparowits | 75 |
| BR7228 | Cache/Ogden | 75 |
| BR7218 | Diamond Mtn/Vernal/Bonanza | 75 |
| BR7238 | Dolores Triangle (new) | 75 |
| BR7207 | Fillmore, Pahvant | 75 |
| BR7216 | Fishlake/Thousand Lakes | 75 |
| BR7229 | Kamas/North Slope, Summit | 75 |
| BR7239 | La Sal Mtns | 76 |
| BR7203 | Manti, North | 76 |
| BR7204 | Manti, South/San Rafael, North | 76 |
| BR7210 | Mt Dutton | 76 |
| BR7205 | Nebo | 76 |
| BR7211 | Nine Mile | 76 |
| BR7212 | North Slope, Three Corners/ West Daggett | 76 |
| BR7213 | Panguitch Lake/Zion | 76 |
| BR7214 | Paunsaugunt | 76 |
| BR7217 | San Juan | 76 |
| BR7220 | Wasatch Mtns, Avintaquin/ Currant Creek | 76 |
| BR7221 | Wasatch Mtns, West-Central | 76 |
| BR7219 | Yellowstone | 76 |

#### Spot-and-stalk — 1

| Hunt code | Printed unit name | PDF page |
|---|---|---:|
| BR7225 | Book Cliffs, Little Creek Roadless | 77 |

#### Multiseason — 22

| Hunt code | Printed unit name | PDF page |
|---|---|---:|
| BR7318 | Beaver | 77 |
| BR7300 | Book Cliffs, Bitter Creek/South | 77 |
| BR7301 | Book Cliffs, Little Creek Roadless | 77 |
| BR7310 | Boulder/Kaiparowits | 77 |
| BR7320 | Cache/Ogden | 77 |
| BR7325 | Chalk Creek/East Canyon/ Morgan-South Rich | 77 |
| BR7313 | Diamond Mtn/Vernal/Bonanza | 77 |
| BR7311 | Fishlake/Thousand Lakes | 77 |
| BR7321 | Kamas/North Slope, Summit | 77 |
| BR7326 | La Sal Mtns | 77 |
| BR7303 | Manti, North | 77 |
| BR7304 | Manti, South/San Rafael, North | 77 |
| BR7322 | Mt Dutton | 78 |
| BR7305 | Nebo | 78 |
| BR7317 | Nine Mile | 78 |
| BR7308 | North Slope, Three Corners/West Daggett | 78 |
| BR7309 | Panguitch Lake/Zion | 78 |
| BR7323 | Paunsaugunt | 78 |
| BR7312 | San Juan | 78 |
| BR7315 | Wasatch Mtns, Avintaquin/ Currant Creek | 78 |
| BR7316 | Wasatch Mtns, West-Central | 78 |
| BR7314 | Yellowstone | 78 |

### 2026 restricted-pursuit codes — separate drawing

| Hunt code | Printed unit name | PDF page |
|---|---|---:|
| BR1015 | Book Cliffs | 78 |
| BR1017 | La Sal | 78 |
| BR1016 | San Juan | 78 |
| BR1008 | Book Cliffs | 79 |
| BR1009 | La Sal | 79 |
| BR1010 | San Juan | 79 |
| BR1011 | Book Cliffs | 79 |
| BR1012 | La Sal | 79 |
| BR1013 | San Juan | 79 |

Spring: BR1015/BR1017/BR1016, Nonresident drawing only. Early summer: BR1008/BR1009/BR1010. Late summer: BR1011/BR1012/BR1013. The same nine codes appear in the inspected 2024 and 2025 restricted-pursuit tables.

### 2026 harvest-objective units — not coded draw hunts

The 27 printed rows cover the following 21 names. Repeated seasonal rows remain distinct in the source CSV and must not be summed into a public draw quota.

| Printed unit name | Number of table rows | PDF page |
|---|---:|---|
| Beaver | 1 | 79 |
| Book Cliffs, Bitter Creek/South | 1 | 79 |
| Boulder/Kaiparowits | 1 | 79 |
| Cache/Ogden | 1 | 79 |
| Chalk Creek/East Canyon/Morgan-South Rich | 3 | 79 |
| Diamond Mtn/Vernal/Bonanza | 1 | 79 |
| Fillmore, Pahvant | 1 | 80 |
| Fishlake/Thousand Lakes | 1 | 80 |
| Kamas/North Slope, Summit | 1 | 80 |
| La Sal Mtns | 1 | 80 |
| Manti, North | 1 | 80 |
| Manti, South/San Rafael, North | 1 | 80 |
| Mt Dutton | 1 | 80 |
| Nebo | 1 | 80 |
| Nine Mile | 2 | 80 |
| North Slope, Three Corners/West Daggett | 2 | 80 |
| Panguitch Lake/Zion | 1 | 80 |
| San Juan | 1 | 80 |
| Wasatch Mtns, Avintaquin/Currant Creek | 2 | 80 |
| Wasatch Mtns, West-Central | 1 | 80 |
| Yellowstone | 2 | 80 |

## Historical versus current codes

All **99** 2026 guidebook drawing codes are present in the current identity catalog. That is identity coverage, not proof of forecast coverage or certification.

Seven codes appear in the 2026 tables but not the 2025 tables:

| Codes | 2026 identity | Pages |
|---|---|---|
| BR7021, BR7126, BR7238 | Dolores Triangle, spring/summer/fall | 73, 74, 75 |
| BR7022, BR7127, BR7239, BR7326 | La Sal Mtns, spring/summer/fall/multiseason | 73, 74, 76, 77 |

Five 2025 codes are absent from the 2026 regular drawing tables: BR7008, BR7108, BR7208, BR7307 (previous La Sal hunting codes) and BR7237 (Monroe fall, 2025 p. 45). Absence is **not** proof of permanent retirement, nor permission to transfer applicant stacks. Existing reviewed crosswalks remain separate evidence; this audit changes none.

The retained yearly canonical inventories contain 91/92/98/101/101/97/97/97/97 Bear-prefixed codes for 2017–2025 respectively. Their union contains these codes not printed in the 2026 regular Bear drawing tables:

`BR1000, BR7002, BR7006, BR7008, BR7019, BR7103, BR7107, BR7108, BR7202, BR7206, BR7208, BR7209, BR7222, BR7223, BR7226, BR7227, BR7230, BR7231, BR7232, BR7233, BR7234, BR7235, BR7236, BR7237, BR7302, BR7306, BR7307`.

BR1000 is a separate Sportsman program, not a demonstrated retired hunt. Keep all historical evidence; exclude unsupported current targets only through source classification, not bulk deletion or a boundary match.

## Discrepancies and repairs

1. **Import failure reproduced:** original `bear.py` failed compilation, causing 41 pytest collection errors. The saved-file coverage subset still passed 11 tests. The syntax/control-flow repair restores valid indentation and branch-local `continue` statements; it does not skip every actual drawing row or append a general-pursuit row twice.
2. **Counter-only filter:** the prior code appended availability rows and then merely changed whether the report counted them. The unchanged three-product allowlist now controls actual availability branches and the shared availability predicate. Unknown non-allowlisted pursuit/harvest-objective labels remain non-predictive, not promoted to availability or draw odds.
3. **Bison contamination proven in saved data:** the 708-row ML file contains four BR records and no BR1000. Each bad BR record matches the saved BI1000 Sportsman Bison record in every column except five: `hunt_code`, `bear_draw_subtype`, `availability_status`, `draw_system_type`, `algorithm_status`. Both BR1001 rows are Resident. The file's schema also lacks `p_draw`, so checking blank values with `.get()` did not validate schema integrity.
4. **Writer trace, without an invented cause:** Git commit `01e13ad0` introduced this saved ML file. The inspected owning Bear builder creates a fresh `_base_row` inside each Bear/residency iteration; the family materializer calls it separately and replaces the Bear family as a collection. No Bison-loop/base-dictionary leak was found in those current functions. The exact ad-hoc writer of the cloned saved file is not retained in the inspected source. The next commit, `a98642fe`, introduced the malformed indentation.
5. **New fail-closed identity gate:** the Bear builder and both final family output surfaces validate availability against the current Bear identity rows, allowed residency, correct subtype, duplicate keys and blank draw probabilities. A cross-species input is rejected, not renamed silently. The existing corrupt saved ML file fails this gate with `Bear availability identity mismatch: ('BR1001', 'Resident')`.
6. **Other saved snapshots disagree:** the two saved Bear prediction CSVs each retain 3,507 rows and 19 availability rows, including 15 restricted-pursuit residency records incorrectly labeled general pursuit. Their counts are not restored into the new engine. The saved Bear report says four availability, but its status counts also say 41 pending/61 excluded while separate totals say 2 pending/100 excluded. It reports zero restricted-pursuit modeled rows. Coverage phase 8 says restricted pursuit is modeled; phase 12 says it is not. These contradictions cannot be fixed by toggling a boolean or by passing the eleven saved-file checks.
7. **Authority drift remains a blocker:** the earlier local Bear foundation section claims canonical-award quota authority, but the current checkout's `_forecast_quota_for_residency` calls `target_residency_permit_allocation(db_row, ...)`. This narrow availability repair does not change quota/model logic or re-establish those earlier fold claims. Current-state documentation now distinguishes retained foundation evidence from the current implementation. Canonicals and unified draw truth remain authoritative for historical evaluation.

## Validation results

- `py -m py_compile engine/utah_draw_predictive/bear.py`: PASS, exit 0. The edited family materializer also compiles.
- Explicit `ast.parse` of `bear.py`: PASS.
- Requested saved coverage files: **11 passed**, but not sufficient alone.
- New live-generation/identity regressions: **11 passed**; combined focused run **22 passed**.
- Additional Bear materialization unit checks: **2 passed**, one broad end-to-end artifact-generation test deliberately deselected to avoid an unrelated whole-engine rebuild.
- Full requested predictive directory: **327 passed, 9 failed (336 tests)**. Before adding the 11 new regressions, the syntax-only repaired baseline was **316 passed, 9 failed (325 tests)**. The same nine test identities fail; no new failing test was introduced.
- The initial full run hit a Windows pytest temporary-directory cleanup permission error after execution. The final run used a fresh audit-local `--basetemp`, completed normally, and retained its actual failing-test exit code.
- Full result: [final_suite.xml](../audits/bear_availability_validation_20260919/final_suite.xml). Initial import errors: [baseline.xml](../audits/bear_availability_validation_20260919/baseline.xml). Syntax-only result: [post_syntax_repair.xml](../audits/bear_availability_validation_20260919/post_syntax_repair.xml).
- Project-memory validation: FAIL, the same two pre-existing DATABASE byte-hash/stale-build checks among 146 checks. The expected hash was not changed or waived.
- Public-manifest exposure guard and `git diff --check`: PASS.
- [Protected hash comparison](../audits/bear_availability_validation_20260919/protected_after.json): all 20 protected data/report/truth/registry files remain byte-identical. The 21st inventoried file, `bear.py`, is the intentionally edited engine source.

The requested **135/135 is not the size or result of this checkout's suite**. No assertion was weakened, saved report edited, test skipped inside the full suite, or data rewritten to manufacture a pass.

| Remaining full-suite failure | Evidence |
|---|---|
| Three BR1000 Sportsman/subtype tests | The saved ML file has no BR1000 records |
| Historical Bear subtype-lineage test | Expected retained-PDF label versus returned canonical-truth label |
| Modeled target-code coverage | Saved reports disagree: 791 versus 793 |
| Generated coverage report | Turkey modeled flag false, expected true |
| Out-of-scope runtime policy | Saved report says one row, ML file contains zero |
| Certification registry fixture | Expected 18,087 joined rows versus frozen 34,944 |
| Sportsman source-year contract | Expected 2017 Sportsman filename versus 2018 source filename |

The previously recorded **19 broader V3 repository failures** remain a separate retained record; this targeted run does not close or replace it.

## Reproduction and release boundary

Run from the repository root. Choose a **new** output/basetemp name for every rerun; do not point pytest at an existing evidence directory.

```powershell
py -m py_compile engine/utah_draw_predictive/bear.py
py -c "import ast; from pathlib import Path; ast.parse(Path('engine/utah_draw_predictive/bear.py').read_text(encoding='utf-8')); print('AST parse OK')"
py -m pytest tests/utah_draw_predictive/test_bear_availability_live_generation.py tests/utah_draw_predictive/test_modeled_availability_semantics.py tests/utah_draw_predictive/test_phase8_bear_coverage.py tests/utah_draw_predictive/test_phase12_bear_coverage.py -q
py -m pytest tests/utah_draw_predictive -q
py -X utf8 scripts/audit_bear_availability_regulations_2026.py --source-dir audits/bear_availability_validation_20260919/source_evidence --out-dir audits/bear_availability_validation_20260919/inventory_recheck
npm run validate:project-memory
npm run guard:public-manifests
```

**Do not promote these saved files.** A subsequent isolated materialization must regenerate consistent family artifacts and reports from verified source inputs, prove complete exact-identity coverage, preserve restricted pursuit as a separate drawing program, resolve the remaining failures, and pass the applicable certification/publication gates. Availability correctness is not Bear prediction accuracy certification.

No production CSV, saved report, draw canonical, unified draw truth, DATABASE, permit field, certification registry, website or deployed object was changed by this repair. Nothing staged, committed, pushed, uploaded or deployed.

## 2020-2025 PDF Validation

Verified 2026-09-20. Tyler requested a PDF-first, year-by-year Bear rebuild,
starting with 2020 and then extending through 2025. The independent extraction
contains **24,942 point/residency rows and 1,170 hunt/year/residency totals**.
Every printed lane total equals its point-ladder sum. All **195,840 numeric
canonical cells compared match**. The PDFs expose a separate 2023 canonical
name defect, described below. No protected canonical or production artifact
was repaired or replaced.

Evidence root:
`audits/prediction_release_candidates/bear_pdf_history_2020_2025_20260920/`.
Final assembled artifacts are in **`assembled_v4/`**. Each yearly directory
retains the freshly downloaded PDF, HTTP provenance, raw extracted page text
and tables, independent point and printed-total CSVs, frozen hashes, canonical
comparison, and representative full-page screenshots. Use `2021_v2/` for 2021
and `<year>_v1/` for the other five years. Earlier attempts remain retained,
not overwritten. The separate earlier 2020 pilot is not the final assembly.

### Per-year report coverage

PDF page numbers below are physical pages, not the restarted printed report
page numbers. Every year's first two pages explicitly identify **bonus point
purchases** and are excluded from hunt ladders. The 2023-2025 pages 3-4 are
**All Applicants** aggregates. Their sums also reconcile to the hunt pages,
but they are not added a second time. No statewide point purchasers were
assigned to a hunt. Blank counts are rejected, not converted into zero.

| Draw year | PDF pages | Hunt pages | Purchase pages excluded | Aggregate pages excluded | Hunting-draw codes | Restricted-pursuit codes | R/NR point rows | Canonical result |
|---|---:|---|---|---|---:|---:|---:|---|
| 2020 | 102 | 3-102 | 1-2 | None | 91 | 9 | 4,000 | Exact count/name/program/page parity |
| 2021 | 102 | 3-102 | 1-2 | None | 91 | 9 | 4,000 | Exact count/name/program/page parity |
| 2022 | 98 | 3-98 | 1-2 | None | 87 | 9 | 4,032 | Exact count/name/program/page parity |
| 2023 | 100 | 5-100 | 1-2 | 3-4 | 87 | 9 | 4,224 | Counts/programs/pages match; six wrong canonical names |
| 2024 | 100 | 5-100 | 1-2 | 3-4 | 87 | 9 | 4,224 | Exact count/name/program/page parity |
| 2025 | 101 | 5-101 | 1-2 | 3-4 | 88 | 9 | 4,462 | Count/program/page parity; extraction spacing variants retained |
| 2026 target guidebook | Separate source, not draw results | See inventory above | Not used | Not used | 90 | 9 | Not historical results | 99 codes / 198 residency combinations |

Report URLs are `https://wildlife.utah.gov/pdf/bear/YY_drawing_odds.pdf`,
linked directly from the official DWR drawing-odds page. All six fresh
downloads are byte-identical to their retained official archive copies.

| Year | PDF SHA-256 |
|---|---|
| 2020 | `6a9aadf664bc7383fbd8b371e280d895cadae32a8fd29dd6ee1e143222d89ea6` |
| 2021 | `286602b4504003ff871a9560092b94842e0df06f662c30bbeefc67db9149bc3b` |
| 2022 | `4d8c0ae1ee5bc644eb8433000fd5804c0acf6d24bae7a12eab3d093e5c1f7b6b` |
| 2023 | `9726e78747de7634cb3d4038c3daf3665e142285ef7ecbdd342d0ac929cb0de3` |
| 2024 | `7285646f7a11b529256c3040278a345f6b3df0613950570c0a9901e42e1ec8ea` |
| 2025 | `d18cf6df54d9e649ae945f43fe305bcad52410751bf2649f54713892483099e8` |

Representative hunt-table screenshots reviewed: 2020/2021 physical page 3,
2022 physical page 3, 2023/2024/2025 physical page 5. Full headers, both lanes,
point ranges and footers/totals were inspected. All six discrepant 2023 pages
were also rendered and visually checked. Poppler reported missing Symbol and
ArialUnicode display fonts for 2025; the inspected table's numbers, names,
residency headings and totals are legible. The 2022 extra empty extraction
column and 2023/2024 split permit cells have explicit fail-closed handling.

### Canonical mismatches and scope

The actual canonical layout is
`data_truth/draw_results_truth/normalized/canonical_yearly/draw_results_<year>_for_<year+1>_canonical_yearly_draw_results.csv`,
not `canonical_yearly/YEAR/bear_*.csv`. The independently extracted lanes were
frozen **before** reading those canonical contents. Residency lanes are never
merged for modeling; combined columns are recombined only to verify the
reversible canonical representation. Printed hunt totals stay in a separate
file and never become point zero.

2023 has **138 incorrect hunt-name fields**: six hunts, each with 22 combined
point rows and one combined total row. The PDF-derived candidate has the
correct names. All eight residency-specific count fields and all combined
count columns match, and none was changed.

| Code | Incorrect canonical name | Name on official PDF | Physical PDF page |
|---|---|---|---:|
| BR7000 | 1 in 19.0 | Beaver - Any Legal Weapon | 14 |
| BR7001 | 1 in 9.0 | Book Cliffs, Bitter Creek/south - Any Legal Weapon | 15 |
| BR7005 | N/A | Central Mtns, Nebo - Any Legal Weapon | 18 |
| BR7007 | N/A | Fillmore, Pahvant - Any Legal Weapon | 19 |
| BR7010 | N/A | Panguitch Lake/zion - Any Legal Weapon | 22 |
| BR7015 | 1 in 9.0 | South Slope, Bonanza/diamond Mtn/vernal - Any Legal Weapon | 27 |

Each canonical also contains a separate BR1000 Sportsman record, sourced from
its Sportsman PDF. It is explicitly outside this Bear bonus-ladder report
audit, not a missing LE hunt and not silently discarded. Sportsman numerical
truth is not revalidated by this six-report audit.

### Availability evidence and history sufficiency

BR1001, BR1007 and BR1018 are absent from **all six drawing-ladder reports**.
They must not be added to those ladders. The current catalog and fresh builder
produce four correct product/residency records with **blank draw probabilities**.
The two general-pursuit records retain the existing `p_availability=1` product
flag. BR1001's two harvest-objective records instead say **HARVEST OBJECTIVE
STATUS UNKNOWN** and have blank availability probabilities because current
closure/status evidence is missing. Four non-draw records do not mean four
LE hunts or four guaranteed permits.

No separately dated 2020-2025 catalog proving all four exact product/residency
identities was located in the checked data, truth or raw year directories.
The locked yearly reference appendices do not establish those identities.
`bear_availability_historical_evidence.csv` preserves all 24 requested
product/year records as **NOT_VERIFIED_NO_DATED_CATALOG_LOCATED**, not 100%.
Neither a current catalog nor absence from draw reports proves historical
availability or that a harvest-objective unit remained open.

**Six years are a usable baseline for developing a 2026 candidate, not six
completed certification folds.** The 2020-2025 window provides five adjacent
comparisons: 2020-to-2021 through 2024-to-2025. A sixth would require an
independently frozen 2025-to-2026 prediction and verified 2026 actual results.
No accuracy folds were executed in this source-validation task. Extending
back to 2017 provides eight comparisons through 2025, or nine if 2026 actuals
are included under the same source-only boundary. The 2017-2019 PDFs already
exist locally; they were not revalidated in this requested six-year pass.
ADR-0006 thresholds and the existing four-core certification are unchanged.

### Code lineage and point-transition evidence

`bear_code_lineage_2020_2026.csv` inventories all 115 observed historical/current
codes. Of the 99 current guidebook codes, 92 have exact-code history: 86 were
already present at the 2020 window start, five first appear in this window in
2022, and one in 2025. These are first appearances **within the reviewed
window**, not claims about the hunt's original establishment date.

Seven current codes have no exact-code history: BR7021, BR7126, BR7238 (Dolores
Triangle), and BR7022, BR7127, BR7239, BR7326 (La Sal Mtns). The existing
crosswalk's proposed La Sal parent mappings are retained as diagnostics, not
newly approved applicant-stack transfers. Sixteen historical codes are absent
from the 2026 guidebook, which is not proof of permanent retirement. Twenty-seven
historical codes have a published name change requiring identity review.
The audit never uses `boundary_id` and never approves a split, recode, name
change or boundary equivalence merely because counts match.

#### Seven new exact codes: four predecessors and three split-child hunts

The existing Bear crosswalk was found and read, not omitted:
`data_truth/crosswalk_truth/normalized/black_bear_BR_2024_2025_2026_crosswalk.csv`.
It labels the four La Sal recodes `HIGH` confidence. Their predecessor codes
are independently present in **all six reviewed 2020-2025 PDFs**:

| 2026 code | Hunt / season | Crosswalk predecessor | Historical evidence |
| --- | --- | --- | --- |
| BR7022 | La Sal Mtns / spring | BR7008 | 2020-2025; 2025 PDF p. 20 |
| BR7127 | La Sal Mtns / summer | BR7108 | 2020-2025; 2025 PDF p. 38 |
| BR7239 | La Sal Mtns / fall | BR7208 | 2020-2025; 2025 PDF p. 62 |
| BR7326 | La Sal Mtns / multiseason | BR7307 | 2020-2025; 2025 PDF p. 85; crosswalk flags old code reused for conservation |
| BR7021 | Dolores Triangle / spring | No one-to-one predecessor | Crosswalk marks current split child |
| BR7126 | Dolores Triangle / summer | No one-to-one predecessor | Crosswalk marks current split child |
| BR7238 | Dolores Triangle / fall | No one-to-one predecessor | Crosswalk marks current split child |

The official 2026 guidebook p. 4 explicitly states that Dolores Triangle was
separated from La Sal Mtns, with existing La Sal Mtns permit numbers maintained
and ten permits allocated to the new unit. Current codes and seasons appear
on pp. 73-77. This proves a boundary/program-context change, not seven wholly
history-free hunts. The same guidebook p. 10 says restricted La Sal pursuit
still includes both areas; do not apply the hunting split to pursuit identity.

For forecasts, preserve four linked predecessor histories separately from the
three new split-child records. A high-confidence code recode establishes
lineage, but it does not show how applicants will redistribute after the
boundary split. Do not duplicate the entire historical La Sal applicant stack
into both units or treat unchanged permit counts as unchanged demand. This
2026 crosswalk is current-target context, not source-time evidence for earlier
historical folds. The existing engine alias map remains unchanged in this task.

`bear_point_transition_evidence_2020_2025.csv` has 20,942 adjacent target-rung
diagnostics. It separates 13,871 `NO_TRANSITION_EVIDENCE`, 4,967 positive
unsuccessful-source-cohort rows, 970 zero-point entry rows requiring a separate
demand model, and 1,134 name/program-change review rows. Many are empty printed
rungs, not missing hunts. An unsuccessful source cohort is applicants minus
awards **within the same program and residency**. The public aggregate report
does not identify which people return or switch hunts; these are arithmetic
cohort candidates, not individual-person transition claims.

For the 2026 candidate, `current_2026_point_evidence_gate.csv` retains blank
`p_draw` and `certified_p_draw` throughout: 1,848 no-transition rows, 504 with
older aggregate demand evidence but no supported current returning cohort,
976 with a source cohort but no certification, 184 zero-point entry rows,
196 identity-transition review rows, plus the four non-draw products. The
separate raw engine diagnostic is explicitly **not a publishable forecast**.

### Fresh build, hashes and verification

There is no `build_bear_reports(write=False)` API. The existing owning
`build_bear_bonus_predictions(...)` returns rows and a report without writing
production files. This audit calls that owner with the fresh PDF point lanes
and current target context only after freezing the historical extract.

The first attempt found an unnecessary read of `sportsman_odds_2025.csv` during
Bear classification. The narrow owning-module repair now routes Bear's
explicit Sportsman/non-draw identities without that external-family count
file, and recognizes verified historical PDF program identity before consulting
the latest Bear PDF. Runtime audit hooks reject builder writes and hidden
CSV/JSON/PDF dependencies. The successful builder's only additional data read
is the retained, hash-matched 2025 Bear PDF. The quota accessor, probability
formula, alias maps and availability allowlist were not changed.

Fresh raw diagnostic: 3,712 rows, comprising 3,645 modeled point rows, 63
excluded/no-public-probability rows, and four availability records. All 198
current drawing code/residency combinations are represented, but representation
does not establish forecast sufficiency or certification. Existing alias and
demand-model assumptions still require the controlled historical evaluation.

- Consolidated audit: `assembled_v4/audit_bear_2020_2025.csv`, SHA-256 `6960e4db6ec5eadb8f1a8028ff80f19480c1b3b13dc71cb71e7c9c3970859826`.
- Independent point history: `assembled_v4/bear_pdf_history_2020_2025_point_lanes.csv`, SHA-256 `2c5dfebebe940ba1819eb3daf0663ea7df9a296bdc228f67ccf888b70d5a01ba`.
- Exact pre-intake-repair Bear source rollback: `assembled_v3/bear.before_pdf_intake_repair.py`, verified SHA-256 `1f2ad641afafb8664a8ac61fb25eb63d9a9aa14aeae162acc9e263e28d7def7a`.
- Compilation passes. Focused PDF/intake/availability/classification tests: **58 passed**.
- Full predictive tests: **333 passed, the same nine pre-existing failures**. New source-boundary tests add six passing cases. The prior 19 broader V3 failures are still a separate unresolved record.
- The CSV audit independently checks unique keys, column alignment, literal counts, missing versus zero, separate residency and exact source totals. No extra workbook was substituted for the requested CSV.
- All original **20 protected data/report/truth/registry files remain byte-identical**. The separate Bear source change is intentional. Nothing staged, committed, pushed, uploaded or deployed.
- The two pre-existing project-memory failures remain: DATABASE byte-hash mismatch and stale compact-build evidence. They are not waived or repaired by changing protected data.

Reproduction (use a new audit root):

```powershell
$bearAuditRoot = 'audits/prediction_release_candidates/bear_pdf_history_recheck'
foreach ($bearYear in 2020..2025) {
    $bearVersion = if ($bearYear -eq 2021) { 'v2' } else { 'v1' }
    py -X utf8 scripts/audit_bear_pdf_truth_year.py --year $bearYear --out-dir "$bearAuditRoot/${bearYear}_$bearVersion"
}
py -X utf8 scripts/build_bear_pdf_history_audit.py --year-audit-root $bearAuditRoot --out-dir "$bearAuditRoot/assembled_v1"
py -m py_compile engine/utah_draw_predictive/bear.py
py -m pytest tests/utah_draw_predictive/test_modeled_availability_semantics.py tests/utah_draw_predictive/test_phase8_bear_coverage.py tests/utah_draw_predictive/test_phase12_bear_coverage.py -q -v
```

The 2023 audit intentionally returns a review-required exit for the canonical
names; it still freezes the independently validated PDF counts and correct
names. The assembler permits name-only discrepancies, which were individually
reviewed in this run, and rejects count or missing-key errors. Final decision: **history prepared for
controlled evaluation; Bear remains uncertified; do not promote.**

## Post-split boundary and completed five-fold review — 2026-09-20

The next controlled phase has now been executed. See
`docs/bear_controlled_review_2026.md` for implementation, exact evidence paths,
per-fold accuracy, registry and release decision. Seven post-split hunting
codes use 2026-forward history only; predecessor mappings are reference only.
Restricted pursuit is separate. Current fresh generation still represents all
198 draw residency lanes plus four availability records, with all 14 split
lanes blank. The 138-cell name-only canonical candidate remains isolated.

All five comparisons through the final website probability calculation failed
Bear certification: hunting MAE 12.259 points and pursuit MAE 13.943 points;
both fail additional error gates. Pursuit has only 267 possible official
scorable results, below 400. All 291 missing/blank actual cases are explicitly
source-classified. The public-field gate correctly suppresses every candidate
Bear probability. No production data was replaced or deployed. Earlier text
saying no folds were run describes the preceding source-audit phase only.
