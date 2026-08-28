# ADR-0006: Historical Blind Acceptance Thresholds

- Status: Accepted
- Date: 2026-08-28

## Decision

Prediction certification is decided independently for each declared Utah draw
design. A favorable aggregate may not override a failed design, a recurring
hunt-code error, an unclassified scoring gap, or a false guarantee.

The historical acceptance evidence is a source-only adjacent-year fold:

1. Freeze official source truth through draw year `N`.
2. Generate the forecast without reading draw year `N+1` actuals.
3. Score only official, lineage-retained public-draw point rows from draw year
   `N+1`.
4. Keep rows that cannot be scored explicitly classified and out of the
   probability score.

For a draw design to be accepted, all of the following must pass:

| Gate | Required result |
| --- | --- |
| Independent following-year folds | At least 2 |
| Joined, scorable rows | At least 400 |
| Mean absolute probability error | At most 10 percentage points |
| 90th-percentile absolute probability error | At most 30 percentage points |
| Rows with over-25-point absolute error | At most 10% |
| False guarantees | 0 |
| Non-joined official actuals | Every row source-classified; no unclassified gap |

`False guarantee` means the forecast gives a probability of at least
`0.999999` while the official following-year result is below that level.

## Historical Review Result

The first approved historical review uses the physically adjacent draws from
2017→2018 through 2024→2025. The final fold scores the **2025 drawing**;
its canonical key is `2026` because that is the next model-year label. No
2026 draw result and no 2025→2026 comparison is included in this review.

The generated audit is:

`audits/prediction_blind_year_to_year/historical_adjacent_full_engine_2018_2025_20260828_v4/acceptance_review/`

Its aggregate result is `NOT_ACCEPTED`: 82,684 joined rows, MAE 13.67 points,
90th-percentile error 50.0 points, 15.99% over-25-point errors, and 2,319
false guarantees. The per-design report is authoritative for repair order;
no design in this review is accepted for certification.

## Consequences

- The Research site may continue to show the already released, explicitly
  uncertified runtime. This decision does not authorize a new upload or
  promotion.
- Engine work must begin with the highest recurring false-guarantee and
  tail-error patterns in the per-hunt-code review, then re-run this same
  source-only review.
- A change in source lineage, classifier logic, or simulation mechanics
  requires a fresh frozen review. Old scores do not transfer automatically.
