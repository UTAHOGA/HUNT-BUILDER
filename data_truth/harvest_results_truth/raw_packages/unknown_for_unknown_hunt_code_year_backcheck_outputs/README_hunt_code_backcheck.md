# Hunt Code / Species-Year Harvest Backcheck

Built from the harvest database artifacts currently available in this workspace.

## What this does

- Stacks available harvest-result tables from reported years 2021–2025.
- Normalizes species, hunt family, hunt code, hunt name, harvest, permit, hunter-effort, success-rate fields.
- Produces a species/year comparison.
- Produces a hunt-code/year presence ledger.
- Performs a backward crosscheck for 2025 harvest rows used as 2026 model-target quality features.

## Limits

This is a harvest-history crosscheck. It is not yet a full active-2026 permit/quota crosscheck unless the official 2026 permit-allotment file, master hunt database, and prediction outputs are joined in.

## Safeguards

All rows are treated as harvest-quality, trend, and demand-signal inputs only:
- do_not_use_for_permit_quota = true
- do_not_use_directly_for_p_draw = true
