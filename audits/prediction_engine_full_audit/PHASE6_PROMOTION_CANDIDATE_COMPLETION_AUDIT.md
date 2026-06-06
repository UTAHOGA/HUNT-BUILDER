# Promotion Candidate Completion Audit

## Recommendation Summary

### point_ladder
- Best current candidate: `data_model/runtime_drafts/point_ladder_view_v3.csv`
- Status: PASS
- Rows: 78162
- Columns: 28
- Score: 192
- Missing expected terms: prob

### draw_reality
- Best current candidate: `processed_data/draw_reality_engine_v2.csv`
- Status: PASS
- Rows: 176753
- Columns: 24
- Score: 154
- Missing expected terms: odds

### predictions
- Best current candidate: `processed_data/ml_draw_predictions_v1.csv`
- Status: PASS
- Rows: 27940
- Columns: 180
- Score: 124
- Missing expected terms: 

### library
- Best current candidate: `public/hard-copy/data/library_page_hunts.csv`
- Status: PASS
- Rows: 1471
- Columns: 22
- Score: 118
- Missing expected terms: 

### history
- Best current candidate: `processed_data/public_contracts/hunt_odds_history.csv`
- Status: PASS
- Rows: 176753
- Columns: 21
- Score: 138
- Missing expected terms: odds

### truth_database
- Best current candidate: `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`
- Status: PASS
- Rows: 1471
- Columns: 41
- Score: 110
- Missing expected terms: unit

## Guardrails

- This audit did not promote, copy, upload, stage, or push files.
- Large tracked production feeders should not be rewritten unless selected as verified promotion outputs.
- Wrangler refresh should only upload selected runtime files after this audit is reviewed.
