# Current Repo And Prediction Engine Status

Generated: 2026-06-27
Repo: `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER`
Branch: `main`
Remote status at scan time: `main...origin/main`
Latest pushed commit: `622c35af Reconcile 2026 permit authority and prediction guards`

## Git / Working Tree

Staged files: none.

Current local dirty tree is intentionally separated from the committed database/engine set:

- `website_public_churn`: public library JSON/CSV/manifests, dashboard JS, one UI test.
- `website_hard_copy_deletions_review`: old tracked `public/hard-copy/DISPLAY DATA/...` and legacy hard-copy data/manifests marked deleted locally.
- `uploaded_r2_hard_copy_library_untracked`: new `public/hard-copy/HUNT LIBRARY/` folder, uploaded to Cloudflare R2 but still untracked locally.
- `generated_engine_audit_outputs_uploaded_or_review`: regenerated prediction/audit/report files under `processed_data/`.
- `legacy_output_deletions_review`: three old `outputs/2019 ...csv` files marked deleted locally.
- `untracked_scripts_review`: hard-copy/source-doc helper scripts not committed.
- `blind_tests_review`: untracked blind-test folder.

Large local files still present:

- `public/hard-copy/HUNT LIBRARY/`: about 137.28 MB, uploaded to R2.
- `processed_data/dwr_huntplanner_hanumber_2026_raw_payloads.json`: about 37.39 MB, uploaded to R2.

Cloudflare/R2 upload completed:

- Bucket: `uoga-data`
- Prefix: `hunt-builder/`
- Objects uploaded: 79
- Total uploaded: 174.68 MB
- Manifest: `audits/r2_large_file_handoff/20260627_005640/r2_upload_manifest.csv`
- Public base: `https://json.uoga.workers.dev/hunt-builder/...`

## Primary Prediction Build

Latest manifest:

- File: `processed_data/utah_bonus_predictive_manifest.json`
- Generated at: `2026-06-27T04:25:20.204938+00:00`
- Model version: `hybrid_ml_v2.1.0`
- Rule version: `utah_bonus_rules_v1.1.0`
- Forecast year: `2026`
- Historical source years: `2021,2022,2023,2024,2025`
- Command:

```powershell
python -m engine.utah_bonus_predictive.materialize --output-dir processed_data --forecast-year 2026 --history-years 2021,2022,2023,2024,2025
```

Latest generated prediction outputs:

- `processed_data/ml_draw_predictions_v1.csv`: 34,882 rows.
- `processed_data/draw_reality_engine_predictive_v2.csv`: 34,882 rows.
- `processed_data/backtest_utah_bonus_draw.csv`: 17,356 rows.
- `processed_data/draw_reality_engine_v2.csv`: 440,893 rows.

Manifest duplicate-key status:

- `ml_draw_predictions_v1.csv`: 0 duplicate contract keys.
- `draw_reality_engine_predictive_v2.csv`: 0 duplicate contract keys.

Important key-contract note:

- A plain key of `(hunt_code, residency, points)` produces 232 duplicates.
- All 232 are turkey adult/youth set-aside overlaps: `BONUS_TURKEY` plus `YOUTH_TURKEY_SET_ASIDE`.
- Adding `draw_system_type` resolves those duplicates to 0.
- Current safe prediction key should therefore be at least `(hunt_code, residency, points, draw_system_type)`.

Probability field status:

- Manifest `p_draw_non_null_count`: 34,654.
- Manifest `p_draw_pct_non_null_count`: 34,654.
- Direct latest CSV scan found 31,795 non-null `p_draw` and `p_draw_pct` after classifier/sanitizer fields; this difference is from materialized field variants and pending/availability rows.

## Source Files Used

Manifest-locked source files:

- `data_truth/draw_results_truth/normalized/draw_results_long.csv`
  - SHA256: `c63e9d11ab2d7846d73249889b2cf3aabd06d3f0eca10fc56c54c5d5395083a8`
- `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`
  - SHA256: `62b736733e6ad72358f6d9720db8675318faa2a8e8a9ba00d41a7aa5bdb25639`
- `processed_data/draw_reality_engine_v2.csv`
  - SHA256: `39d5dc047e32f09698afcaf9ad33c5f2a5e51255c8e8f8fbba866f8232c54283`
- `data_model/runtime_drafts/predictive_bonus_engine_2026.materialized.csv`
  - SHA256: `163c53182ef63293221a6f80aeb6409cedbb0899bf9ae04fc9b64a962be87d4a`
- `hunt-research.js`
  - SHA256: `136c178f03aede19b84e293ce7bee4e4dce4209c051a266ef8424ae52b1fee38`
- `config.js`
  - SHA256: `69c25ca5c79deeff23c4b316e39a14bb17437e2fb4680090687e4c78716c3b20`

Primary official current-year permit authority:

- `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`
- Runtime authority is `permits_2026_res`, `permits_2026_nr`, `permits_2026_total`.
- `permit_allotment_2026_*` is legacy compatibility/audit only and should not override published `permits_2026_*`.
- If DWR/Hunt Planner publishes only total, do not fabricate resident/nonresident split.
- If DWR/Hunt Planner publishes no permit number, leave permit columns blank and exclude public odds.

## Engine Families Currently In Scope

Latest `processed_data/ml_draw_predictions_v1.csv` row counts by `algorithm_status`:

- `MODELED_BONUS`: 28,027
- `MODELED_PREFERENCE`: 6,625
- `MODELED_AVAILABILITY`: 124
- `IN_SCOPE_MODEL_PENDING`: 100
- `EXCLUDED_NOT_PREDICTIVE_DRAW`: 4
- `MODELED_RANDOM_ONLY`: 2

Latest row counts by `draw_system_type`:

- `BONUS_LE_BIG_GAME`: 19,127
- `PREFERENCE_GENERAL_SEASON_BUCK_DEER`: 5,348
- `BEAR_DRAW`: 3,720
- `BONUS_OIL_BIG_GAME`: 3,704
- `PREFERENCE_DEDICATED_HUNTER_DEER`: 1,425
- `BONUS_PLE_BIG_GAME`: 814
- `BONUS_TURKEY`: 240
- `YOUTH_TURKEY_SET_ASIDE`: 232
- `MOUNTAIN_LION_DRAW`: 120
- `BONUS_ANTLERLESS_MOOSE`: 102
- `BONUS_EWE_BIGHORN`: 48
- `YOUTH_DRAW_ONLY_ELK`: 2

## Precise Engine Math

### Max / Weighted Split

Used for limited-entry, premium limited-entry, once-in-a-lifetime, antlerless moose, ewe bighorn, adult limited-entry turkey, bear draw rows, and special bonus families when source classification proves public draw status.

Quota input:

```text
Q = official current-year published quota for that hunt code and residency lane
```

Quota split:

```text
if Q <= 0:
    Q_max = 0
    Q_random = 0
elif Q == 1:
    Q_max = 0
    Q_random = 1
else:
    Q_max = ceil(Q / 2)
    Q_random = Q - Q_max
```

Applicant rollover:

```text
unsuccessful[p] = eligible[p] - bonus_permits[p] - regular_permits[p]
retained[p + 1] = round(unsuccessful[p] * retention_rate)
```

Cutoff structure detection:

```text
top_point = highest point row
mixed_cutoff_point = highest point row where unsuccessful[p] > 0

if no mixed cutoff:
    structure = ALL_APPLICANT_POINTS_GUARANTEED
elif mixed_cutoff_point == top_point:
    structure = TOP_POINT_MIXED
elif there are guaranteed rows above mixed_cutoff_point:
    structure = HAS_GUARANTEED_STACK_ABOVE_MIXED_CUTOFF
else:
    structure = MIXED_CUTOFF_WITH_NONCONTIGUOUS_TOP_PATTERN
```

Current retention priors:

```text
DEFAULT_RETENTION_PRIOR = 0.85
HAS_GUARANTEED_STACK_ABOVE_MIXED_CUTOFF = 0.8475305455097036
TOP_POINT_MIXED = 0.860091743119952
STRUCTURE_RETENTION_EVIDENCE_STRENGTH = 200
```

Evidence smoothing:

```text
evidence_weight = unsuccessful_total / (unsuccessful_total + 200)
retention_smoothed = evidence_weight * raw_rate + (1 - evidence_weight) * prior_rate
retention_smoothed is clamped to [0, 1.25]
```

Max-point pass:

```text
remaining = Q_max
for p from highest points down:
    winners = min(applicants[p], remaining)
    p_max[p] = winners / applicants[p]
    remaining -= winners
```

Weighted random pass:

```text
nonwinners[p] = applicants[p] * (1 - p_max[p])
ticket_share[p] = (p + 1) / sum(nonwinners[k] * (k + 1))
p_random[p] = 1 - (1 - ticket_share[p]) ^ Q_random
p_draw[p] = p_max[p] + (1 - p_max[p]) * p_random[p]
```

Demand uncertainty in the script:

```text
sampled_applicants[p] = round(max(0, Normal(base_applicants[p], sigma)))
sigma = max(1, sqrt(max(base_applicants[p], 1)) * 0.25)
```

The deterministic pool probabilities are the primary materialized values; Monte Carlo samples are retained for p10/p50/p90 uncertainty.

### Preference Draw

Used for general-season buck deer and Dedicated Hunter deer.

Preference applicant forecast:

```text
unsuccessful[p] = eligible[p] - drawn[p]
forecast[p + 1] = round(unsuccessful[p] * retention_by_point_band)
forecast[0] = round(latest_zero_point_applicants * zero_growth)
```

Default point-band retention fallback:

```text
0 points: 0.78
1 point: 0.82
2-3 points: 0.86
4-5 points: 0.90
6-9 points: 0.94
10+ points: 0.97
```

Preference probability:

```text
applicants_above[p] = sum(forecast[k] for k > p)
remaining = quota - applicants_above[p]

if quota <= 0 or applicants_at_level[p] <= 0:
    p_draw[p] = 0
elif remaining <= 0:
    p_draw[p] = 0
elif remaining >= applicants_at_level[p]:
    p_draw[p] = 1
else:
    p_draw[p] = remaining / applicants_at_level[p]
```

### Sportsman Random Only

Used for `SPORTSMAN_PERMIT`.

Rules:

- Utah resident only.
- One tag per species unless source says otherwise.
- No resident/nonresident split.
- No bonus points.
- No preference points.
- Not folded into public big-game max/weighted or preference pools.

Formula:

```text
p_draw = resident_quota / resident_applicants
```

Source report:

- `processed_data/sportsman_permit_report.json`
- Rows reviewed/modeled: 10
- Duplicate keys: 0
- Source files:
  - `data/utah/sportsman/sportsman_odds_2025.csv`
  - `pipeline/RAW/hunt_unit_database/2026/xlsx/24-25_sportsman_odds.xlsx`

### Youth General Any Bull Elk / EB1007

Current canonical family: `YOUTH_GENERAL_ANY_BULL_ELK`

This is separate from Sportsman and separate from Max/Weighted Split.

Rules:

- EB1007 is source-classified as draw-only youth general any-bull/hunter's-choice elk.
- EB1011 is general-season youth bull elk availability/purchase, not EB1007 draw modeling.
- Points are not used.
- Public-facing current output still displays `YOUTH_DRAW_ONLY_ELK` in `draw_system_type` for 2 modeled rows, but the engine code aliases this to the canonical `YOUTH_GENERAL_ANY_BULL_ELK` family.

Formula when official target-year draw results exist:

```text
p_draw = official_quota / official_eligible_applicants
```

Formula when forecasting from history:

```text
projected_applicants = latest_applicants + 0.25 * (latest_applicants - previous_applicants)
p_draw = forecast_quota / projected_applicants
```

### Youth Deer / Youth Antlerless Reserve

Current youth reserve formulas:

```text
youth_reserved = int(total_permits * 0.20)
main_draw = total_permits - youth_reserved
p_youth_total = p_youth_reserve + (1 - p_youth_reserve) * p_main_draw
```

These are preference-style youth reserve lanes, not EB1007 random-only.

### Youth Turkey

Current youth turkey family: `YOUTH_TURKEY_SET_ASIDE`.

Formula:

```text
youth_turkey_quota = round_or_source(0.15 * adult_turkey_quota)
then use turkey bonus/max-weighted style math inside youth turkey source-classified rows
```

Latest source report:

- `processed_data/youth_turkey_report.json`
- Data quality flags show 48 source-classified rows and 48 applications of the 15% youth turkey set-aside.

### Bear

Current bear family: `BEAR_DRAW`.

Public modeled subtypes:

- Limited-entry bear draw rows.
- Restricted pursuit rows when official draw odds prove actual draw status.

Excluded or non-public bear subtypes:

- Statewide bear permit/Sportsman-style row.
- Harvest objective availability rows.
- Remaining/OTC rows.
- Unlimited pursuit.
- Conservation/non-public rows.

Formula for modeled bear rows uses the same bonus/max-weighted mechanics:

```text
Q -> split into Q_max and Q_random
p_max from highest-point pass
p_random from weighted tickets
p_draw = p_max + (1 - p_max) * p_random
```

Latest bear reports:

- `processed_data/bear_draw_report.json`
- `processed_data/bear_report.json`
- Duplicate keys: 0
- Remaining flags include known zero nonresident quota lanes, low applicant counts, missing forecast quota/history rows, and first-choice-only modeling flags.

### Mountain Lion / Cougar

Current family: `MOUNTAIN_LION_DRAW` with `MODELED_AVAILABILITY`.

This is not public draw probability.

Current report:

- `processed_data/mountain_lion_availability_report.json`
- Rows: 120 availability/status rows.
- Probability model: `NONE`.

### Availability / Allocation / No Published Quota

Rules:

- O.T.C., capped availability, private-land-only, landowner, no-published-quota, CWMU contact-operator, CWMU quota-only, and CWMU reference rows do not receive public `p_draw`.
- Total-only permit rows render total only and do not fabricate resident/nonresident probabilities.
- Conservation, Expo, Sportsman, CWMU overlay/reference, landowner, mitigation, and private rows must not inflate public draw quotas.

## Known Corrections / Follow-Up

1. Website/hard-copy/library churn is uploaded to R2 but not reconciled into Git.
2. The old tracked `public/hard-copy/DISPLAY DATA/...` deletions need a separate website/library decision.
3. `processed_data` regenerated report churn is local and should be reviewed before committing or ignored/R2-only.
4. `processed_data/dwr_huntplanner_hanumber_2026_raw_payloads.json` is uploaded to R2 but remains locally modified.
5. The prediction key contract should be documented/enforced as `(hunt_code, residency, points, draw_system_type)` or wider because adult/youth turkey intentionally overlap on the simple three-field key.
6. The manifest still says zero duplicate contract keys, but direct CSV simple-key scans find the 232 adult/youth turkey overlaps. This is acceptable only if the frontend/runtime uses the wider key.
7. 2026 antlerless actual draw results remain pending; antlerless permit numbers can be known, but actual draw outcomes are not complete.
8. Bear rows with missing quota/history flags need a final pass now that the Hunt Planner and draw odds sources are considered available.
9. `docs/data_feed_contract.md` still contains older wording that says RAC/allotment is canonical; the current committed engine/database policy is that `permits_2026_*` is authority and allotment is legacy compatibility.
10. The hard-copy PDF design and website library page are a separate lane from database/engine truth.

## Current Operational Recommendation

Use the committed `DATABASE.csv` plus `draw_results_long.csv` as the active truth foundation for engine work.

Use `processed_data/ml_draw_predictions_v1.csv` and `processed_data/draw_reality_engine_predictive_v2.csv` as the latest generated prediction surfaces, but treat the current local regenerated outputs as not-yet-promoted until the dirty `processed_data` bucket is reviewed.

For engine calibration, continue the loop:

```text
official historical truth through N-1
-> generate prediction for N
-> compare against official actual N
-> classify errors by draw family / residency / point bucket / cutoff structure
-> patch only the family-specific engine that fails
```

Do not merge Sportsman, EB1007 youth elk, CWMU overlay/reference/contact/quota-only, Conservation, Expo, OTC, private-land/no-quota, or allocation/reference rows into public draw odds. CWMU point-level draw-result rows with published probabilities are scoreable under the CWMU policy.
