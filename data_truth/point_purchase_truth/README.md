# Statewide Point-Purchase Truth

This folder retains source-backed statewide point-purchase distributions as a
separate input class. They are **not** hunt-level draw outcomes and must never
be appended to a yearly draw-result canonical or scored as actual draw odds.

`black_bear_limited_entry_bonus_point_purchases_2018_2025.csv` is generated
locally from the retained official DWR Black Bear drawing-odds PDFs by
`scripts/extract_black_bear_point_purchase_truth.py`. Every output row carries
the parent PDF path, SHA-256, page number and a reconciliation status. The CSV
is intentionally local/generated under the repository's large-data policy;
the extractor and source PDFs are the reproducible record.

## 2017 boundary

The official [DWR drawing-odds archive](https://wildlife.utah.gov/odds)
retains two Black Bear reports for 2017: a hunt-level drawing-odds PDF and a
hunt-level bonus-point-results PDF. It does **not** retain a separate statewide
limited-entry Bear point-purchase report for that year. The verified 2017
hunt-level Bear ladder can therefore support a source-only historical audit,
but it must not be relabeled as statewide point-purchase evidence or used to
create a returning-applicant profile that the official record does not support.

The input represents people who purchased a statewide Black Bear limited-entry
bonus point, grouped by residency and point level. It does not identify a
future hunt choice. It may support a separately validated, source-only
returning/high-point-applicant model, but cannot on its own create a
hunt-specific probability or quota.
