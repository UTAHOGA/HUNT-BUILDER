# ADR-0003: Truth And Scoring Authority

- Status: Accepted
- Date: 2026-08-26

## Decision

Official normalized draw actuals with retained lineage are the only accuracy truth. `DATABASE.csv` controls current hunt identity and published permit reference. Normalized harvest results are quality and demand-pressure features, not permit or probability truth.

Unscorable, allocation-only, guidebook, quota-only, reference, CWMU contact-operator, Conservation, Expo, landowner, private, mitigation, and OTC rows must not be turned into public draw probabilities unless a later official source proves a specific draw family.

## Reason

Permit totals and reference rows do not reveal applicant-level draw outcomes. Treating them as probability truth fabricates accuracy.

## Consequences

Every accuracy run uses official historical truth through year N-1, predicts N, and compares with official actual N. Unscorable rows are classified and excluded, not counted as failures or successes.
