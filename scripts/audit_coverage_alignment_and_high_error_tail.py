from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

REPO = Path(r"C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER")
BASE = REPO / "audits" / "prediction_blind_backtests" / "2025_to_2026"
COMPARISON = BASE / "comparison_phase"
PREDICTION_PHASE = BASE / "prediction_phase"
OUT = BASE / "diagnostic_phase"
OUT.mkdir(parents=True, exist_ok=True)

SUMMARY_JSON = COMPARISON / "comparison_summary.json"
ROWLEVEL = COMPARISON / "prediction_2025_to_2026_vs_actual_2026_rowlevel.csv"
UNEXPECTED = COMPARISON / "unexpected_unmatched_2026_actuals.csv"
SOURCE_GAPS = COMPARISON / "source_verified_prediction_gaps_2026_actuals.csv"
UNMATCHED_ACTUALS = COMPARISON / "unmatched_2026_actuals.csv"
UNMATCHED_PREDICTIONS = COMPARISON / "unmatched_frozen_predictions.csv"
PREDICTIONS = PREDICTION_PHASE / "ml_draw_predictions_v1.csv"
COVERAGE_CSV = REPO / "processed_data" / "predictive_coverage_report.csv"
COVERAGE_JSON = REPO / "processed_data" / "predictive_coverage_report.json"
MATERIALIZER_AUDIT = REPO / "data_model" / "runtime_drafts" / "predictive_bonus_engine_2026.audit.csv"

required = [SUMMARY_JSON, ROWLEVEL, UNEXPECTED, SOURCE_GAPS, UNMATCHED_ACTUALS, UNMATCHED_PREDICTIONS, PREDICTIONS, COVERAGE_CSV, COVERAGE_JSON]
missing = [str(p) for p in required if not p.exists()]
if missing:
    print("MISSING REQUIRED INPUTS:")
    for m in missing:
        print("  " + m)
    raise SystemExit(2)

def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()

def write_csv(df: pd.DataFrame, name: str) -> str:
    path = OUT / name
    df.to_csv(path, index=False)
    return str(path)

def norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df

def first_existing(df: pd.DataFrame, names: list[str]) -> str | None:
    for n in names:
        if n in df.columns:
            return n
    return None

def num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")

summary = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))
coverage_summary = json.loads(COVERAGE_JSON.read_text(encoding="utf-8"))
row = norm_cols(read_csv(ROWLEVEL))
cov = norm_cols(read_csv(COVERAGE_CSV))
unexpected = norm_cols(read_csv(UNEXPECTED))
source_gaps = norm_cols(read_csv(SOURCE_GAPS))
unmatched_actuals = norm_cols(read_csv(UNMATCHED_ACTUALS))
unmatched_predictions = norm_cols(read_csv(UNMATCHED_PREDICTIONS))
preds = norm_cols(read_csv(PREDICTIONS))
mat_audit = norm_cols(read_csv(MATERIALIZER_AUDIT)) if MATERIALIZER_AUDIT.exists() else pd.DataFrame()

outputs = {}

# High-error tail
pred_col = first_existing(row, ["predicted_probability", "prediction_probability", "p_pred", "predicted_p_draw", "p_draw_pred", "prediction"])
actual_col = first_existing(row, ["actual_probability", "actual_p_draw", "p_actual", "p_draw_actual", "probability", "actual"])
abs_col = first_existing(row, ["abs_error", "absolute_error"])
err_col = first_existing(row, ["error", "signed_error"])

if abs_col is None and pred_col and actual_col:
    row["abs_error"] = (num(row[pred_col]) - num(row[actual_col])).abs()
    row["signed_error"] = num(row[pred_col]) - num(row[actual_col])
    abs_col = "abs_error"
    err_col = "signed_error"

if abs_col:
    row["_abs"] = num(row[abs_col])
    if err_col and err_col in row.columns:
        row["_err"] = num(row[err_col])
    elif pred_col and actual_col:
        row["_err"] = num(row[pred_col]) - num(row[actual_col])
    else:
        row["_err"] = pd.NA

    high = row[row["_abs"] > 0.25].copy().sort_values("_abs", ascending=False)
    outputs["high_error_rows_abs_gt_0_25"] = write_csv(high, "high_error_rows_abs_gt_0_25.csv")
    outputs["top_500_high_error_rows"] = write_csv(high.head(500), "top_500_high_error_rows.csv")

    for gc in ["hunt_draw_class", "draw_design", "draw_system_type", "species", "residency", "points", "hunt_code"]:
        if gc in row.columns:
            agg = (
                row.groupby(gc, dropna=False)
                .agg(
                    rows=("_abs", "size"),
                    mae=("_abs", "mean"),
                    rmse=("_abs", lambda x: float((x.pow(2).mean()) ** 0.5)),
                    bias=("_err", "mean"),
                    median_abs_error=("_abs", "median"),
                    p90_abs_error=("_abs", lambda x: float(x.quantile(0.90))),
                    failures_abs_gt_0_25=("_abs", lambda x: int((x > 0.25).sum())),
                    max_abs_error=("_abs", "max"),
                )
                .reset_index()
                .sort_values(["failures_abs_gt_0_25", "mae"], ascending=[False, False])
            )
            outputs[f"high_error_summary_by_{gc}"] = write_csv(agg, f"high_error_summary_by_{gc}.csv")
else:
    outputs["rowlevel_columns_no_abs_error_detected"] = write_csv(pd.DataFrame({"column": list(row.columns)}), "rowlevel_columns_no_abs_error_detected.csv")

# Coverage alignment
outputs["coverage_report_column_inventory"] = write_csv(pd.DataFrame({"column": list(cov.columns)}), "coverage_report_column_inventory.csv")
outputs["unexpected_unmatched_actuals"] = write_csv(unexpected, "unexpected_unmatched_actuals.csv")
outputs["source_verified_prediction_gaps"] = write_csv(source_gaps, "source_verified_prediction_gaps.csv")
outputs["unmatched_actuals"] = write_csv(unmatched_actuals, "unmatched_actuals.csv")
outputs["unmatched_predictions"] = write_csv(unmatched_predictions, "unmatched_predictions.csv")

disp_col = first_existing(source_gaps, ["disposition", "reason", "gap_disposition", "status"])
if disp_col:
    disp = source_gaps[disp_col].fillna("").astype(str).value_counts().rename_axis(disp_col).reset_index(name="count")
    outputs["source_gap_disposition_counts"] = write_csv(disp, "source_gap_disposition_counts.csv")

reason_cols = [c for c in cov.columns if c.lower() in {"reason", "status", "disposition"} or "reason" in c.lower()]
outside_cols = [c for c in cov.columns if "outside" in c.lower() or "active_eligible" in c.lower()]
outside_mask = pd.Series(False, index=cov.index)
for c in outside_cols:
    outside_mask = outside_mask | cov[c].fillna("").astype(str).str.lower().isin(["true", "1", "yes"])
for c in reason_cols:
    outside_mask = outside_mask | cov[c].fillna("").astype(str).str.contains("outside|active|eligible", case=False, na=False)
outside = cov[outside_mask].copy()
outputs["coverage_possible_outside_active_universe_rows"] = write_csv(outside, "coverage_possible_outside_active_universe_rows.csv")

if reason_cols:
    rc = reason_cols[0]
    counts = cov[rc].fillna("").astype(str).value_counts().rename_axis(rc).reset_index(name="count")
    outputs["coverage_reason_counts"] = write_csv(counts, "coverage_reason_counts.csv")

# Materializer validation diagnostics
if not mat_audit.empty:
    outputs["materializer_audit_column_inventory"] = write_csv(pd.DataFrame({"column": list(mat_audit.columns)}), "materializer_audit_column_inventory.csv")
    text_cols = [c for c in mat_audit.columns if mat_audit[c].dtype == "object"]
    fail_mask = pd.Series(False, index=mat_audit.index)
    for c in text_cols:
        fail_mask = fail_mask | mat_audit[c].fillna("").astype(str).str.contains("FAIL|ERROR|WARN|REVIEW|duplicate|collapse|missing|outside|invalid", case=False, na=False)
    outputs["materializer_audit_suspect_rows"] = write_csv(mat_audit[fail_mask].copy(), "materializer_audit_suspect_rows.csv")

final = {
    "audit_scope": "coverage universe alignment and high-error tail only; no model redesign",
    "comparison_summary": summary,
    "coverage_summary": coverage_summary,
    "key_findings": {
        "joined_keys": summary.get("joined_keys"),
        "overall_metrics": summary.get("overall_metrics"),
        "unmatched_actual_keys": summary.get("unmatched_actual_keys"),
        "source_verified_prediction_gap_actual_keys": summary.get("source_verified_prediction_gap_actual_keys"),
        "unexpected_unmatched_actual_keys": summary.get("unexpected_unmatched_actual_keys"),
        "unmatched_actual_disposition_counts": summary.get("unmatched_actual_disposition_counts"),
        "forecast_codes_match_active_eligible_universe": coverage_summary.get("forecast_codes_match_active_eligible_universe"),
        "active_eligible_codes_missing_from_forecast": coverage_summary.get("active_eligible_codes_missing_from_forecast"),
        "forecast_codes_outside_active_eligible_universe": coverage_summary.get("forecast_codes_outside_active_eligible_universe"),
    },
    "outputs": outputs,
}
summary_out = OUT / "coverage_alignment_and_high_error_tail_audit_summary.json"
summary_out.write_text(json.dumps(final, indent=2), encoding="utf-8")

md = []
md.append("# Coverage Alignment and High-Error Tail Audit")
md.append("")
md.append("Diagnostic audit only. No model redesign, no taxonomy changes, no prediction rewrites.")
md.append("")
md.append("## Key findings")
md.append(f"- Joined keys: {summary.get('joined_keys')}")
metrics = summary.get("overall_metrics", {})
md.append(f"- MAE: {metrics.get('mae')}")
md.append(f"- RMSE: {metrics.get('rmse')}")
md.append(f"- Bias: {metrics.get('bias')}")
md.append(f"- Median absolute error: {metrics.get('median_abs_error')}")
md.append(f"- P90 absolute error: {metrics.get('p90_abs_error')}")
md.append(f"- Abs error > 0.25 rows: {metrics.get('failure_abs_error_gt_0_25')}")
md.append(f"- Unmatched actual keys: {summary.get('unmatched_actual_keys')}")
md.append(f"- Source-verified prediction gaps: {summary.get('source_verified_prediction_gap_actual_keys')}")
md.append(f"- Unexpected unmatched actual keys: {summary.get('unexpected_unmatched_actual_keys')}")
md.append(f"- Forecast codes match active eligible universe: {coverage_summary.get('forecast_codes_match_active_eligible_universe')}")
md.append(f"- Active eligible codes missing from forecast: {coverage_summary.get('active_eligible_codes_missing_from_forecast')}")
md.append(f"- Forecast codes outside active eligible universe: {coverage_summary.get('forecast_codes_outside_active_eligible_universe')}")
md.append("")
md.append("## Outputs")
for k, v in outputs.items():
    md.append(f"- {k}: `{v}`")
md_out = OUT / "coverage_alignment_and_high_error_tail_audit_summary.md"
md_out.write_text("\n".join(md), encoding="utf-8")

print(json.dumps({
    "status": "DONE",
    "summary_json": str(summary_out),
    "summary_md": str(md_out),
    "outputs_written": outputs,
}, indent=2))
