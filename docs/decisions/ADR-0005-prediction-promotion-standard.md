# ADR-0005: Prediction Promotion Standard

- Status: Accepted
- Date: 2026-08-26

## Decision

A prediction build is promotion-ready only when all of the following are recorded and passing:

1. Source paths and hashes match the certified build manifest.
2. Forecast year, model version, rule version, row counts, and runtime contract agree.
3. Probability, quota, schema, leakage, duplicate-key, and false-guarantee gates pass.
4. Blind following-year scoring reports aggregate Brier score, MAE, calibration, bias, cutoff error, and false guarantees.
5. Results are broken down by family, species, residency, and point bucket.
6. Every dropped or unscorable row is classified.
7. The Research summary, index, ladder, details, and predictive runtime are generated from the certified build.
8. Tyler explicitly authorizes any upload, deploy, or production promotion.

## Reason

Populated metrics and passing synthetic fixtures prove that code executes; they do not by themselves prove real forecast accuracy or production lineage.

## Consequences

The current 2026 build remains `BLOCKED` until the recorded blockers in `governance/engine-authority.json` are cleared. A blocked build may be inspected and improved, but must not be represented as newly certified.
