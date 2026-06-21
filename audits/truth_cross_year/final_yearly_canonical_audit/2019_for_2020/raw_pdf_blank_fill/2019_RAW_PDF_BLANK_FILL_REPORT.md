# 2019 Canonical Raw-PDF Blank Fill

Status: `PASS_RAW_PDF_BACKED_BLANK_FILL`
Target: `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\data_truth\draw_results_truth\normalized\canonical_yearly\draw_results_2019_for_2020_canonical_yearly_draw_results.csv`
Backup: `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\audits\truth_cross_year\final_yearly_canonical_audit\2019_for_2020\raw_pdf_blank_fill\backups\draw_results_2019_for_2020_canonical_yearly_draw_results.backup_before_raw_pdf_fill_20260619T233134Z.csv`

## Mutation Counts
- `draw_design`: 4658
- `permits_year_nr`: 56
- `permits_year_res`: 56
- `permits_year_total`: 56
- `success_ratio`: 47403
- `weapon`: 1008

## Held For Review
- `sex` / `sex_type` where the PDF title does not explicitly print the sex type.
- `boundary_id`, because draw-result PDFs do not print boundary IDs.
- `p_draw` and `p_draw_percent` for N/A rows, because those are not numeric probabilities.

Review rows: `225`
