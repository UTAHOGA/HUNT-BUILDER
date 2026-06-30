# Antlerless Preference Yearly Reconciliation

Source authority: `draw_results_long.csv` plus current `DATABASE.csv`.

- Canonical yearly files scanned: 9
- Years scanned: 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026
- Current antlerless preference target codes: 203
- Modeled from long + database: 142
- Held because no pre-2026 same-code ladder exists: 17
- Held because current DB has no positive 2026 permit authority: 44
- Held as CWMU/contact-operator: 0
- Review: history exists but guardrails rejected it: 0
- Canonical-vs-long yearly code conflicts: 0

Generated files:

- `processed_data/antlerless_preference_current_code_reconciliation_2026.csv`
- `processed_data/antlerless_preference_yearly_canonical_vs_long_reconciliation.csv`
- `processed_data/antlerless_preference_yearly_canonical_vs_long_conflicts.csv`
- `processed_data/antlerless_preference_yearly_reconciliation_summary.json`
