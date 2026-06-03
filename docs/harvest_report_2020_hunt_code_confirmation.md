# 2020 Harvest Report Hunt-Code Confirmation

## Purpose

This audit compares the independent 2020 BIBLE hunt-code year document against three selected 2020 harvest reports. It confirms code existence only; it does not promote harvest, draw, or permit values.

## Sources

- BIBLE year document: `processed_data/audits/bible_hunt_code_year_documents/bible_hunt_code_year_document_2020.csv`
- Harvest report: `pipeline/RAW/hunt_unit_database/2020/pdf/harvest_report/2020_le_oial_all.pdf`
- Harvest report: `pipeline/RAW/hunt_unit_database/2020/pdf/harvest_report/2020_antlerless_hr.pdf`
- Harvest report: `pipeline/RAW/hunt_unit_database/2020/pdf/harvest_report/General-season buck deer.pdf`

## Key Counts

- Raw harvest code hits: `976`
- Unique harvest-report codes: `939`
- Unique BIBLE 2020 codes: `1028`
- Unique codes compared: `1065`

## Confirmation Status Counts

- `BIBLE_ONLY_NOT_IN_SELECTED_HARVEST_REPORTS`: `126`
- `CONFIRMED_BY_2020_HARVEST_REPORT`: `902`
- `HARVEST_ONLY_NOT_IN_BIBLE_2020`: `37`

## Prefix Counts By Status

- `BIBLE_ONLY_NOT_IN_SELECTED_HARVEST_REPORTS`: BR=101, CG=15, TK=7, EB=1, MB=1, RE=1
- `CONFIRMED_BY_2020_HARVEST_REPORT`: DB=307, EB=191, EA=159, PB=82, PD=34, DA=28, MB=28, DS=18, GO=18, BI=17, RS=15, MA=5
- `HARVEST_ONLY_NOT_IN_BIBLE_2020`: EA=24, MB=10, DB=2, EB=1

## Harvest-Only Codes

These codes appear in the selected 2020 harvest reports but not in the 2020 BIBLE draw-result year document:

```text
DB0008
DB0009
EA1220
EA2001
EA2002
EA2003
EA2004
EA2005
EA2006
EA2008
EA2009
EA2010
EA2011
EA2012
EA2013
EA2014
EA2015
EA2016
EA2017
EA2018
EA2019
EA2020
EA2021
EA2026
EA2027
EA2028
EB3128
MB6200
MB6215
MB6216
MB6217
MB6220
MB6223
MB6259
MB6260
MB6261
MB6262
```

## Outputs

- `processed_data/audits/bible_hunt_code_year_documents/harvest_report_2020_hunt_code_source_hits.csv`
- `processed_data/audits/bible_hunt_code_year_documents/harvest_report_2020_hunt_code_confirmation.csv`
- `processed_data/audits/bible_hunt_code_year_documents/harvest_report_2020_hunt_code_confirmation_summary.json`
- `docs/harvest_report_2020_hunt_code_confirmation.md`

## Guardrail

Harvest reports are used here only as hunt-code existence confirmation evidence. This does not change DATABASE.csv, draw truth, permit truth, harvest values, or prediction inputs.
