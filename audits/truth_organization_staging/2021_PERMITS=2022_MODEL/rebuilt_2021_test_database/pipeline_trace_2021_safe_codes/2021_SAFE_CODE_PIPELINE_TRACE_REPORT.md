# 2021 Safe-Code Pipeline Trace Report

Generated: 2026-06-09T22:00:18

## Purpose

Trace the 298 safe/source-backed 2021 hunt codes to determine whether the 799-code forecast surface is missing them because of input-universe loss or builder/classifier/materializer loss.

## Counts

- Safe codes loaded: `298`
- Review holdout codes loaded: `86`
- CSVs scanned: `4018`
- CSVs with hunt-code-like columns recorded: `1792`
- Safe codes not found outside audit outputs: `0`
- Safe codes present in feeders but missing forecast: `0`

## Interpretation rule

- If most safe codes are not found outside audit/truth outputs, the forecast input universe is incomplete.
- If most safe codes are present in model/data feeders but absent from engine output, the builder/classifier/materializer is dropping them.
- Do not promote the 86 review-only 21_bg-odds codes during this pass.

## Key outputs

- `2021_SAFE_CODE_PIPELINE_TRACE_ALL_CSVS.csv`
- `2021_SAFE_CODE_PIPELINE_TRACE_NON_AUDIT_FILES.csv`
- `2021_SAFE_CODE_LIKELY_FEEDER_FILES.csv`
- `2021_SAFE_CODE_PRESENCE_BY_CODE.csv`
- `2021_SAFE_CODES_NOT_FOUND_OUTSIDE_AUDIT_OUTPUTS.csv`
- `2021_SAFE_CODES_PRESENT_IN_FEEDERS_BUT_MISSING_FORECAST.csv`
