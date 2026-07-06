# CWMU Prediction Scoring Policy

Status: active policy after the CWMU source-bucket audit.

Use the yearly CWMU folders under `data_truth/draw_results_truth/raw_pdfs/*_PERMITS=*_MODEL/CWMU/` as the source-evidence bucket for CWMU draw-result documents.

## Scoreable

CWMU rows are prediction-required when all of these are true:

- the row is present in the yearly canonical draw-results file
- the row is a point-level draw-result row
- the row has a published probability field, including zero probability
- the target actual year is released and inside the certification window

These rows should feed the applicable bonus, preference, turkey, or youth family according to the normal engine key.

## Not Scoreable

Keep these rows out of prediction accuracy scoring:

- CWMU contact-operator rows
- quota-only rows
- allocation-only rows
- boundary/reference-only rows
- conservation, expo, landowner, private, mitigation, and similar overlay rows
- forward-year rows where actual draw odds have not been released

These rows may remain useful for lookup, boundary, permit reconciliation, public display context, or source traceability, but they must not inflate public draw odds quotas or accuracy denominators.

## Certification Notes

The CWMU source-bucket audit at `audits/cwmu_modeled_draw_results_source_bucket/20260705_184028/` certified the folder policy with zero CWMU missing blockers using the ordered surgical certification at `audits/engine_certified_prediction_truth/20260705_cwmu_surgical_certification_ordered/`.

`Once-in-a-Lifetime` / O.I.L. is a draw family label, not a lifetime-license reference bucket. Do not classify O.I.L. rows as `GUARANTEED_OR_LIFETIME_REFERENCE_ONLY` unless the row is actually a lifetime-license or guaranteed-permit reference row.
