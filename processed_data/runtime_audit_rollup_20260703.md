# Runtime Audit Rollup

Created: 2026-07-03T05:38:43

## Result

- Runtime safety audit: `PROMOTION_READY`, blockers `0`
- Key alignment/crosswalk audit: `PROMOTION_READY`, blockers `0`
- Scorable/max coverage: `17,072` scorable rows, `833` scorable hunt codes, `0` truth-to-feeder drops
- Year-to-year accuracy: `PASS_WITH_CAVEATS`, no duplicate prediction keys, no bad probability values
- Broad hardening audit: `FAIL_BLOCKED_BROAD_SCOPE` from legacy/broad-scan cleanup items

## Audit Folders

- Runtime safety: `audits/runtime_production_gate/20260703_050555`
- Key/crosswalk and scorable coverage: `audits/research_page_canonical_contract/20260703_runtime_audit`
- Targeted year-to-year accuracy: `audits/targeted_year_to_year_accuracy_20260703`
- Broad hardening cleanup list: `audits/engine_hardening_runtime_audit_20260703`

## Key Counts

- Canonical truth hunt codes: `1508`
- Reference database hunt codes: `1645`
- Engine feeder hunt codes: `1859`
- Runtime/public research hunt codes: `1472`
- Dropped truth-to-feeder hunt codes: `0`
- Dropped feeder-to-runtime hunt codes: `390`

## Accuracy Notes

- Scored target years: `2019-2026`
- Generated but not scored: `2026->2027`, because actuals are unreleased
- Joined rows: `34,149`
- Overall MAE: `0.37607231`
- Overall bias: `0.19328691`
- Caveat: older canonical truth rows were expanded from official resident/nonresident p-draw columns; no probabilities were fabricated from permit totals.

## Next Cleanup Only If Needed

- Broad hardening blockers are outside the newly wired artifact path and should be handled as full-cert/tree cleanup, not as a blocker to the current runtime path.
