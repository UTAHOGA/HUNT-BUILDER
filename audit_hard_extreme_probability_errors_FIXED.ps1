<# 
FIXED HARD EXTREME PROBABILITY AUDIT

Run from repo root:
  powershell -ExecutionPolicy Bypass -File .\audit_hard_extreme_probability_errors_FIXED.ps1

This is audit-only. It does not change predictions, draw design, taxonomy, model routing, or engine files.
#>

$ErrorActionPreference = "Stop"
$RepoRoot = "C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER"
Set-Location $RepoRoot
$Py = Join-Path $RepoRoot "scripts\audit_hard_extreme_probability_errors.py"

@'
from pathlib import Path
import pandas as pd
import json

REPO = Path(r"C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER")
DIAG = REPO / "audits" / "prediction_blind_backtests" / "2025_to_2026" / "diagnostic_phase"

INPUT = DIAG / "high_error_rows_abs_gt_0_25.csv"
OUT_DIR = DIAG / "hard_extreme_probability_audit"
OUT_DIR.mkdir(parents=True, exist_ok=True)

if not INPUT.exists():
    raise SystemExit(f"Missing input: {INPUT}")

df = pd.read_csv(INPUT, low_memory=False)
df.columns = [str(c).strip() for c in df.columns]

def first_existing(names):
    for n in names:
        if n in df.columns:
            return n
    return None

pred_col = first_existing(["predicted_probability", "prediction_probability", "p_pred", "predicted_p_draw", "p_draw_pred"])
actual_col = first_existing(["actual_probability", "actual_p_draw", "p_actual", "p_draw_actual", "probability"])
abs_col = first_existing(["abs_error", "absolute_error", "_abs"])
err_col = first_existing(["error", "signed_error", "_err"])

missing = []
if pred_col is None:
    missing.append("predicted_probability equivalent")
if actual_col is None:
    missing.append("actual_probability equivalent")
if abs_col is None:
    missing.append("abs_error / absolute_error / _abs equivalent")

if missing:
    raise SystemExit(f"Missing expected columns: {missing}. Columns: {list(df.columns)}")

df["_predicted_probability_num"] = pd.to_numeric(df[pred_col], errors="coerce")
df["_actual_probability_num"] = pd.to_numeric(df[actual_col], errors="coerce")
df["_abs_error_num"] = pd.to_numeric(df[abs_col], errors="coerce")

if err_col is not None:
    df["_signed_error_num"] = pd.to_numeric(df[err_col], errors="coerce")
else:
    df["_signed_error_num"] = df["_predicted_probability_num"] - df["_actual_probability_num"]

hard = df[df["_predicted_probability_num"].isin([0.0, 1.0])].copy()
hard["hard_extreme_type"] = hard["_predicted_probability_num"].map({
    0.0: "PREDICTED_ZERO",
    1.0: "PREDICTED_ONE",
})

hard["predicted_probability_normalized"] = hard["_predicted_probability_num"]
hard["actual_probability_normalized"] = hard["_actual_probability_num"]
hard["abs_error_normalized"] = hard["_abs_error_num"]

hard.to_csv(OUT_DIR / "hard_0_or_1_high_error_rows.csv", index=False)

group_sets = [
    ["hard_extreme_type"],
    ["draw_system_type"],
    ["species"],
    ["residency"],
    ["draw_system_type", "species"],
    ["draw_system_type", "species", "residency"],
    ["points"],
    ["draw_system_type", "points"],
    ["hunt_code", "residency"],
]

outputs = {}
for cols in group_sets:
    cols = [c for c in cols if c in hard.columns]
    if not cols:
        continue

    out = (
        hard.groupby(cols, dropna=False)
        .agg(
            rows=("_abs_error_num", "size"),
            mae=("_abs_error_num", "mean"),
            rmse=("_abs_error_num", lambda x: float((x.pow(2).mean()) ** 0.5)),
            bias=("_signed_error_num", "mean"),
            median_abs_error=("_abs_error_num", "median"),
            p90_abs_error=("_abs_error_num", lambda x: float(x.quantile(0.90))),
            max_abs_error=("_abs_error_num", "max"),
            avg_predicted_probability=("_predicted_probability_num", "mean"),
            avg_actual_probability=("_actual_probability_num", "mean"),
        )
        .reset_index()
        .sort_values(["rows", "mae"], ascending=[False, False])
    )

    name = "hard_extreme_summary_by_" + "_".join(cols) + ".csv"
    out.to_csv(OUT_DIR / name, index=False)
    outputs[name] = str(OUT_DIR / name)

top = hard.sort_values("_abs_error_num", ascending=False).head(300)
top.to_csv(OUT_DIR / "top_300_hard_extreme_errors.csv", index=False)

summary = {
    "status": "DONE",
    "input": str(INPUT),
    "all_high_error_rows": int(len(df)),
    "hard_extreme_rows": int(len(hard)),
    "hard_extreme_share_of_high_error_rows": float(len(hard) / len(df)) if len(df) else None,
    "predicted_zero_rows": int((hard["_predicted_probability_num"] == 0).sum()),
    "predicted_one_rows": int((hard["_predicted_probability_num"] == 1).sum()),
    "column_mapping": {
        "predicted_probability": pred_col,
        "actual_probability": actual_col,
        "abs_error": abs_col,
        "signed_error": err_col,
    },
    "outputs": outputs,
    "top_300": str(OUT_DIR / "top_300_hard_extreme_errors.csv"),
}

(OUT_DIR / "hard_extreme_probability_audit_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

md = []
md.append("# Hard Extreme Probability Audit")
md.append("")
md.append("Audit-only. No model redesign, taxonomy changes, draw-design changes, or prediction rewrites.")
md.append("")
md.append(f"- Input high-error rows: {len(df)}")
md.append(f"- Hard 0/1 high-error rows: {len(hard)}")
md.append(f"- Share of high-error tail: {summary['hard_extreme_share_of_high_error_rows']}")
md.append(f"- Predicted-zero rows: {summary['predicted_zero_rows']}")
md.append(f"- Predicted-one rows: {summary['predicted_one_rows']}")
md.append("")
md.append("## Column mapping")
for k, v in summary["column_mapping"].items():
    md.append(f"- {k}: `{v}`")
md.append("")
md.append("## Outputs")
for k, v in outputs.items():
    md.append(f"- {k}: `{v}`")
md.append(f"- top_300: `{summary['top_300']}`")
(OUT_DIR / "hard_extreme_probability_audit_summary.md").write_text("\n".join(md), encoding="utf-8")

print(json.dumps(summary, indent=2))
'@ | Set-Content -Encoding UTF8 $Py

Write-Host "Running fixed hard-extreme probability audit..."
python $Py

Write-Host ""
Write-Host "Hard-extreme audit outputs:"
Get-ChildItem "audits\prediction_blind_backtests\2025_to_2026\diagnostic_phase\hard_extreme_probability_audit" -File |
  Select-Object Name,Length,LastWriteTime |
  Sort-Object LastWriteTime -Descending |
  Format-Table -AutoSize

Write-Host ""
Write-Host "Summary by hard extreme type:"
Import-Csv "audits\prediction_blind_backtests\2025_to_2026\diagnostic_phase\hard_extreme_probability_audit\hard_extreme_summary_by_hard_extreme_type.csv" |
  Format-Table -AutoSize

Write-Host ""
Write-Host "Summary by draw system / species / residency:"
Import-Csv "audits\prediction_blind_backtests\2025_to_2026\diagnostic_phase\hard_extreme_probability_audit\hard_extreme_summary_by_draw_system_type_species_residency.csv" |
  Select-Object -First 40 |
  Format-Table -AutoSize

Write-Host ""
Write-Host "Top hard-extreme errors:"
Import-Csv "audits\prediction_blind_backtests\2025_to_2026\diagnostic_phase\hard_extreme_probability_audit\top_300_hard_extreme_errors.csv" |
  Select-Object -First 75 hunt_code,residency,points,draw_system_type,species,hunt_name,predicted_probability_normalized,actual_probability_normalized,abs_error_normalized |
  Format-Table -AutoSize
