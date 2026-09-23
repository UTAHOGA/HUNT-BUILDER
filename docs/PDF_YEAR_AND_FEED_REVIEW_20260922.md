# Retained PDF years, antlerless truth feed and DB0008 routing

## Verified antlerless sources

Before Tyler's cleanup, the top-level 2025/pdf/draw_odds/2024 antlerless draw results.pdf was a
2024 Draw 7 report, 203 pages, SHA256
2b1b19782089732b9cacc2fd9ce00e60e1093acda6f3ed70d29e8d6e3ae83b08.
It is byte-identical to two copies already archived under 2024, including
official_dwr_archive/big_game_antlerless/24_antlerless_drawing_odds_report.pdf.
The old antlerless resolver explicitly labels its evidence 2024; this legacy
reference is not the source of 2025 historical draw truth. Tyler has now removed
that misplaced copy and added the correct 2025 adult/youth PDFs at the top
level. Do not restore the removed file. Fresh annual inventory and complete
2025 cell comparisons are recorded in `docs/PIPELINE_ANNUAL_SOURCE_AUDIT_20260922.md`.

### Important downstream qualification

The correct canonical year does NOT prove the old resolver is harmless.
Follow-up inspection confirmed that scripts/resolve-antlerless-hunt-codes-2026.py
reads the 2024 PDF and writes the local processed_data/draw_reality_engine_predictive_v2.csv.
Its retained September-21 promotion receipt and current CSV contain 159
ANTLERLESS_REFERENCE rows with source_years_used=2024;2026. They currently have
blank probability and applicant/award fields; current quota fields come from
DATABASE rather than the PDF. The resolver therefore affects reference coverage
inside a predictive artifact, not merely an archived PDF audit.

The mixed materializer reads that successor CSV. Its probability_model=NONE
guard suppresses final probability for these references, but artifact presence
is not evidence of a completed hunt forecast. The main family runner reads
draw_results_long.csv instead of this extraction. This establishes two paths;
it does NOT establish that all prior builds avoided the legacy path or that the
2024 source caused the measured probability errors. Next isolate the legacy
reference writer from normal forecast outputs and trace exact saved build inputs.

The actual 2025 reports are nested under
pipeline/RAW/hunt_unit_database/2025/pdf/draw_odds/official_dwr_archive/big_game_antlerless/:

| File | Printed draw year | Pages | Canonical point rows | Canonical total rows |
| --- | ---: | ---: | ---: | ---: |
| 25_antlerless_drawing_odds_report.pdf | 2025 | 222 | 4,340 | 217 |
| 25_youth_antlerless_drawing_odds_report.pdf | 2025 | 202 | 3,184 | 199 |

Hashes respectively:
c212777c5326dc1145d3941765b92dbda75a830a73a771c42c13ccd78c760cfd;
9c5a3883330a44d36dc1c151473f2028292c027b9834af835b2b74a8049da8f9.
All 7,940 records carry actual_draw_year=2025 in both the 2025 yearly canonical
and draw_results_long.csv. Totals are not added again to point-row awards.
This verifies source presence/year/reference counts, not every numeric cell or
successful delivery through every forecast code path.

## Bounded archive-year audit

scripts/audit_retained_pdf_draw_years.py scanned 255 locally present draw_odds
PDF paths (156 distinct measured hashes). Explicit first-three-page draw titles
match folder years for 170 paths, differ for two, and remain unrecognized for
83. No read errors or changed canonicals. This is not complete numeric parity
or proof that the 83 unrecognized-title files have correct years.
Evidence: audit_output_real_final/pdf_draw_year_audit_20260922_v1/report.json.

The second difference is a 2023 cougar filename/folder with a 2022 drawing
title. Its 198 canonical references correctly use 2022. Tyler explains the
historical fall draw preceding the hunting season; retain draw year and season
year separately. This is not evidence of a canonical year error or a current
cougar draw. No raw files were renamed, moved, deleted or re-downloaded.

## DB0008 partial routing repair

Removed the classifier's generic extended-archery-to-random branch. The existing
general-deer preference and separate youth routing now handle typed draw rows.
Retained 2026 Application guidebook pages 9/44 and the UtahDraws preference-point
endpoint support this; the live DWR extendedarchery page also identifies DB0008
as a permit obtained in the big-game drawing. Genuine reference rows remain
excluded. Tests verify adult/youth separation and no quota-only admission.

The 2026 canonical retains 11 correctly typed endpoint rows plus ten legacy
availability-labeled rows. Eight of the legacy rows have prior numeric parity;
their label recovery, redundant-copy accounting and canonical/long application
are NOT completed by the classifier change. No canonical or forecast changed.
The classifier implementation hash changed; old frozen scores do not certify
this revised implementation. No registry or release promotion.

## First failing-family feed triage

Read-only grouping of the latest independent saved eight-fold scores examined
41,348 keys and retained 7,029 over-25-point errors. 2025-to-2026 excluded.
Evidence: audit_output_real_final/failing_family_feed_triage_20260922_v1/.
All 21,107 scored public CWMU records use MODELED_SOURCE_BACKED_ROLL_FORWARD;
3,082 have zero forecast but positive observed outcome. Youth antlerless and
general-deer scored output also uses that fallback. Adult antlerless modeled
nonresident errors are materially higher than resident errors. These patterns
identify the next source-to-family feed audit, not proof of a demand-model fix.

Validation: 21 focused year/routing/reference tests pass. No engine probability
formula changed, no new frozen scoring run, no certification, staging or deploy.
