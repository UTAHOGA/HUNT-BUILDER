<#
PROMOTION READINESS MAJOR ISSUES AUDIT
Non-mutating audit script for HUNT-BUILDER.

Run from repo root:
  C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER

Command:
  powershell -ExecutionPolicy Bypass -File .\promotion_readiness_major_issues_audit.ps1

This script DOES NOT edit truth files, engine files, promote outputs, delete files, commit, push, or change Git history.
It only reads key files and writes a major-issues report under:
  audits\promotion_readiness_major_issues\
#>

$ErrorActionPreference = "Stop"

$RepoRoot = "C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER"
if (!(Test-Path $RepoRoot)) {
    throw "Repo root not found: $RepoRoot"
}

Set-Location $RepoRoot

$AuditDir = Join-Path $RepoRoot "audits\promotion_readiness_major_issues"
New-Item -ItemType Directory -Force -Path $AuditDir | Out-Null

$Py = Join-Path $RepoRoot "scripts\promotion_readiness_major_issues_audit.py"

@'
from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

import pandas as pd


REPO = Path(r"C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER")
AUDIT_DIR = REPO / "audits" / "promotion_readiness_major_issues"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

OUT_JSON = AUDIT_DIR / f"promotion_readiness_major_issues_{STAMP}.json"
OUT_MD = AUDIT_DIR / f"PROMOTION_READINESS_MAJOR_ISSUES_{STAMP}.md"
OUT_CSV = AUDIT_DIR / f"promotion_readiness_major_issues_{STAMP}.csv"

DRAW_RESULTS_LONG = REPO / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
CANONICAL_YEARLY = REPO / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"

LATEST_BLIND_BASE = REPO / "audits" / "prediction_blind_backtests" / "2025_to_2026"
COMPARISON_SUMMARY = LATEST_BLIND_BASE / "comparison_phase" / "comparison_summary.json"
BLIND_SUMMARY = LATEST_BLIND_BASE / "blind_backtest_summary.json"
DIAG_DIR = LATEST_BLIND_BASE / "diagnostic_phase"
HIGH_ERROR = DIAG_DIR / "high_error_rows_abs_gt_0_25.csv"
UNEXPECTED_UNMATCHED = DIAG_DIR / "unexpected_unmatched_actuals.csv"
SOURCE_GAPS = DIAG_DIR / "source_verified_prediction_gaps.csv"
HARD_EXTREME_DIR = DIAG_DIR / "hard_extreme_probability_audit"

PREDICTIVE_COVERAGE_JSON = REPO / "processed_data" / "predictive_coverage_report.json"
PREDICTIVE_COVERAGE_CSV = REPO / "processed_data" / "predictive_coverage_report.csv"
ML_REPORT = REPO / "processed_data" / "ml_draw_predictions_v1_report.json"
ML_PREDICTIONS = REPO / "processed_data" / "ml_draw_predictions_v1.csv"

MATERIALIZER_AUDIT = REPO / "data_model" / "runtime_drafts" / "predictive_bonus_engine_2026.audit.csv"
MATERIALIZED = REPO / "data_model" / "runtime_drafts" / "predictive_bonus_engine_2026.materialized.csv"
PREDICTIONS = REPO / "data_model" / "runtime_drafts" / "predictive_bonus_engine_2026.predictions.csv"

RUNTIME_OUTPUTS = [
    ML_PREDICTIONS,
    REPO / "processed_data" / "draw_reality_engine_predictive_v2.csv",
    REPO / "processed_data" / "draw_reality_engine_v2.csv",
    MATERIALIZED,
    PREDICTIONS,
]


def safe_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"__read_error__": str(e)}


def safe_csv(path: Path, nrows: int | None = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, low_memory=False, nrows=nrows)
    except Exception as e:
        return pd.DataFrame({"__read_error__": [str(e)]})


def run(cmd: list[str]) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, shell=False)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except Exception as e:
        return 999, "", str(e)


def add_issue(issues: list[dict], severity: str, area: str, issue: str, evidence: str, recommended_action: str) -> None:
    issues.append({
        "severity": severity,
        "area": area,
        "issue": issue,
        "evidence": evidence,
        "recommended_action": recommended_action,
    })


def path_info(path: Path) -> dict:
    if not path.exists():
        return {"exists": False, "path": str(path)}
    return {
        "exists": True,
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "size_mb": round(path.stat().st_size / 1024 / 1024, 3),
        "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
    }


def find_year_col(df: pd.DataFrame) -> str | None:
    for c in ["actual_draw_year", "draw_year", "year"]:
        if c in df.columns:
            return c
    return None


def main() -> None:
    issues: list[dict] = []
    facts: dict = {}

    # 1. Git status
    rc, stdout, stderr = run(["git", "status", "--short"])
    facts["git_status_rc"] = rc
    facts["git_status_short"] = stdout
    facts["git_status_stderr"] = stderr
    if rc != 0:
        add_issue(issues, "BLOCKER", "Git", "Could not read git status.", stderr or stdout, "Fix Git/repo state before promotion.")
    else:
        lines = [x for x in stdout.splitlines() if x.strip()]
        facts["git_status_changed_file_count"] = len(lines)
        if lines:
            add_issue(
                issues, "REVIEW", "Git",
                "Working tree has changed/untracked files.",
                f"{len(lines)} changed/untracked entries.",
                "Review each file. Commit only intended source/audit files. Do not commit large truth/runtime artifacts."
            )

    # 2. Truth source
    facts["draw_results_long"] = path_info(DRAW_RESULTS_LONG)
    if not DRAW_RESULTS_LONG.exists():
        add_issue(issues, "BLOCKER", "Truth source", "Shared canonical draw_results_long.csv is missing.", str(DRAW_RESULTS_LONG), "Restore/provide draw_results_long.csv before running engines.")
    else:
        if DRAW_RESULTS_LONG.stat().st_size > 100 * 1024 * 1024:
            add_issue(issues, "REVIEW", "Git/Large file", "draw_results_long.csv is larger than GitHub's normal file limit.", f"{DRAW_RESULTS_LONG.stat().st_size / 1024 / 1024:.2f} MB", "Keep this file out of Git; store/share via Cloudflare R2 or direct transfer.")
        df_truth = safe_csv(DRAW_RESULTS_LONG)
        if "__read_error__" in df_truth.columns:
            add_issue(issues, "BLOCKER", "Truth source", "Could not read draw_results_long.csv.", str(df_truth["__read_error__"].iloc[0]), "Fix the CSV before promotion.")
        else:
            facts["draw_results_long_rows"] = int(len(df_truth))
            facts["draw_results_long_columns"] = list(df_truth.columns)
            year_col = find_year_col(df_truth)
            facts["draw_results_long_year_col"] = year_col
            if year_col is None:
                add_issue(issues, "BLOCKER", "Truth source", "No recognized year column in draw_results_long.csv.", "Expected actual_draw_year, draw_year, or year.", "Fix schema/loader before promotion.")
            else:
                years = pd.to_numeric(df_truth[year_col], errors="coerce")
                counts = years.value_counts().sort_index()
                facts["draw_results_long_rows_by_year"] = {str(int(k)): int(v) for k, v in counts.items() if pd.notna(k)}
                if len(counts) < 3:
                    add_issue(issues, "BLOCKER", "Truth source", "draw_results_long.csv has too few years for blind backtesting.", str(facts["draw_results_long_rows_by_year"]), "Confirm canonical yearly files are imported into draw_results_long.csv.")

    # 3. Canonical yearly
    facts["canonical_yearly_dir"] = path_info(CANONICAL_YEARLY)
    if CANONICAL_YEARLY.exists():
        canonical_files = sorted(CANONICAL_YEARLY.glob("*draw_results_canonical*.csv"))
        facts["canonical_yearly_file_count"] = len(canonical_files)
        facts["canonical_yearly_files"] = [str(p) for p in canonical_files]
        if not canonical_files:
            add_issue(issues, "REVIEW", "Truth source", "No canonical yearly draw result files found.", str(CANONICAL_YEARLY), "Confirm canonical_yearly contains intended yearly truth files or document why draw_results_long is the only active truth file.")

    # 4. Blind backtest outputs
    comparison = safe_json(COMPARISON_SUMMARY)
    blind = safe_json(BLIND_SUMMARY)
    facts["comparison_summary_path"] = str(COMPARISON_SUMMARY)
    facts["blind_summary_path"] = str(BLIND_SUMMARY)
    facts["comparison_summary"] = comparison
    facts["blind_summary"] = blind

    if not COMPARISON_SUMMARY.exists():
        add_issue(issues, "BLOCKER", "Blind test", "2025->2026 comparison_summary.json is missing.", str(COMPARISON_SUMMARY), "Run strict blind backtest before promotion.")
    else:
        metrics = comparison.get("overall_metrics", {})
        facts["blind_overall_metrics"] = metrics
        if int(comparison.get("duplicate_prediction_key_groups", 0) or 0) > 0:
            add_issue(issues, "BLOCKER", "Blind test", "Duplicate prediction key groups exist.", f"duplicate_prediction_key_groups={comparison.get('duplicate_prediction_key_groups')}", "Fix duplicate prediction keys before promotion.")
        unexpected = int(comparison.get("unexpected_unmatched_actual_keys", 0) or 0)
        if unexpected > 0:
            add_issue(issues, "BLOCKER", "Coverage alignment", "Unexpected unmatched actual keys remain.", f"unexpected_unmatched_actual_keys={unexpected}", "Open unexpected_unmatched_actuals.csv and fix/justify every unexpected gap.")
        source_verified = int(comparison.get("source_verified_prediction_gap_actual_keys", 0) or 0)
        if source_verified > 0:
            add_issue(issues, "REVIEW", "Coverage alignment", "Source-verified prediction gaps remain.", f"source_verified_prediction_gap_actual_keys={source_verified}; dispositions={comparison.get('unmatched_actual_disposition_counts')}", "Keep as documented exceptions only if source-verified; otherwise repair exact-history/crosswalk/key coverage.")
        high = metrics.get("failure_abs_error_gt_0_25")
        if high is not None and int(high) > 0:
            add_issue(issues, "REVIEW", "Accuracy", "High-error tail remains.", f"failure_abs_error_gt_0_25={high}; MAE={metrics.get('mae')}; RMSE={metrics.get('rmse')}; bias={metrics.get('bias')}", "Use high_error_summary_by_* and top_500_high_error_rows.csv to identify family/point/pool failures.")
        bias = metrics.get("bias")
        if bias is not None and abs(float(bias)) > 0.05:
            add_issue(issues, "REVIEW", "Calibration", "Overall blind-test bias is materially off zero.", f"bias={bias}", "Audit by draw_system_type/species/points/residency before promotion.")

    # 5. Predictive coverage
    coverage = safe_json(PREDICTIVE_COVERAGE_JSON)
    facts["predictive_coverage_report"] = coverage
    if not PREDICTIVE_COVERAGE_JSON.exists():
        add_issue(issues, "BLOCKER", "Coverage", "predictive_coverage_report.json is missing.", str(PREDICTIVE_COVERAGE_JSON), "Run materialization/coverage audit before promotion.")
    else:
        if coverage.get("forecast_codes_match_active_eligible_universe") is False:
            add_issue(issues, "REVIEW", "Coverage", "Forecast universe does not match active eligible universe.", f"forecast_codes_outside_active_eligible_universe={coverage.get('forecast_codes_outside_active_eligible_universe')}; active_eligible_codes_missing_from_forecast={coverage.get('active_eligible_codes_missing_from_forecast')}", "Resolve outside-universe forecast codes or document as non-promoted diagnostic output.")
        missing_active = coverage.get("active_eligible_codes_missing_from_forecast")
        if missing_active not in [None, 0, "0"]:
            add_issue(issues, "BLOCKER", "Coverage", "Active eligible codes are missing from forecast.", f"active_eligible_codes_missing_from_forecast={missing_active}", "Repair missing active eligible forecast coverage before promotion.")

    # 6. Runtime outputs
    facts["runtime_outputs"] = {str(p): path_info(p) for p in RUNTIME_OUTPUTS}
    for p in RUNTIME_OUTPUTS:
        if not p.exists():
            add_issue(issues, "BLOCKER", "Runtime outputs", "Required runtime/prediction output is missing.", str(p), "Run corresponding materialization step or remove from promotion set.")

    # 7. Materializer audit suspect rows
    if MATERIALIZER_AUDIT.exists():
        df_audit = safe_csv(MATERIALIZER_AUDIT)
        facts["materializer_audit_rows"] = int(len(df_audit)) if "__read_error__" not in df_audit.columns else 0
        if "__read_error__" in df_audit.columns:
            add_issue(issues, "REVIEW", "Materializer", "Could not read predictive_bonus_engine_2026.audit.csv.", str(df_audit["__read_error__"].iloc[0]), "Fix/read audit before promotion.")
        else:
            text_cols = [c for c in df_audit.columns if df_audit[c].dtype == "object"]
            fail_mask = pd.Series(False, index=df_audit.index)
            for c in text_cols:
                fail_mask = fail_mask | df_audit[c].fillna("").astype(str).str.contains("FAIL|ERROR|WARN|REVIEW|INVALID|MISSING|LEAK|DUPLICATE", case=False, na=False)
            fail_rows = df_audit[fail_mask].copy()
            facts["materializer_audit_suspect_rows"] = int(len(fail_rows))
            if len(fail_rows):
                suspect_path = AUDIT_DIR / f"materializer_audit_suspect_rows_{STAMP}.csv"
                fail_rows.to_csv(suspect_path, index=False)
                add_issue(issues, "REVIEW", "Materializer", "Materializer audit has suspect rows.", f"{len(fail_rows)} suspect rows written to {suspect_path}", "Review suspect rows before promotion.")

    # 8. Hard 0/1 and high-error checks
    facts["diagnostic_files"] = {
        "high_error": path_info(HIGH_ERROR),
        "unexpected_unmatched": path_info(UNEXPECTED_UNMATCHED),
        "source_gaps": path_info(SOURCE_GAPS),
        "hard_extreme_dir": path_info(HARD_EXTREME_DIR),
    }

    if HIGH_ERROR.exists():
        high_df = safe_csv(HIGH_ERROR)
        if "__read_error__" not in high_df.columns:
            facts["high_error_rows_abs_gt_0_25_rows"] = int(len(high_df))
            pred_col = None
            for c in ["predicted_probability", "prediction_probability", "p_pred", "predicted_p_draw", "p_draw_pred"]:
                if c in high_df.columns:
                    pred_col = c
                    break
            if pred_col:
                pred = pd.to_numeric(high_df[pred_col], errors="coerce")
                hard_count = int(pred.isin([0, 1]).sum())
                facts["hard_0_or_1_high_error_rows_detected"] = hard_count
                if hard_count > 0:
                    add_issue(issues, "REVIEW", "Calibration", "Hard 0/1 predictions are present in the high-error tail.", f"{hard_count} high-error rows have predicted probability exactly 0 or 1.", "Run/fix hard-extreme probability audit and inspect false-zero/false-one rows before promotion.")

    hard_summary = HARD_EXTREME_DIR / "hard_extreme_probability_audit_summary.json"
    if hard_summary.exists():
        hs = safe_json(hard_summary)
        facts["hard_extreme_probability_audit_summary"] = hs
        if int(hs.get("hard_extreme_rows", 0) or 0) > 0:
            add_issue(issues, "REVIEW", "Calibration", "Hard-extreme probability audit found 0/1 high-error rows.", f"hard_extreme_rows={hs.get('hard_extreme_rows')}; predicted_zero_rows={hs.get('predicted_zero_rows')}; predicted_one_rows={hs.get('predicted_one_rows')}", "Add calibration/floor/ceiling/pool-allocation guardrails only after confirming mechanics by draw family.")

    # 9. Large files
    large_files = []
    for p in REPO.rglob("*"):
        try:
            if p.is_file() and ".git" not in p.parts and p.stat().st_size > 95 * 1024 * 1024:
                large_files.append({"path": str(p), "size_mb": round(p.stat().st_size / 1024 / 1024, 3)})
        except Exception:
            pass
    facts["large_files_over_95mb"] = large_files
    if large_files:
        add_issue(issues, "REVIEW", "Git/Large file", "Large files over 95 MB exist in repo working tree.", f"{len(large_files)} large files detected.", "Keep out of Git. Upload to Cloudflare/R2 or direct transfer. Confirm .gitignore and git rm --cached.")

    # Verdict
    severity_rank = {"BLOCKER": 3, "REVIEW": 2, "INFO": 1}
    blocker_count = sum(1 for i in issues if i["severity"] == "BLOCKER")
    review_count = sum(1 for i in issues if i["severity"] == "REVIEW")
    if blocker_count:
        verdict = "NOT_READY_BLOCKERS"
    elif review_count:
        verdict = "NOT_READY_REVIEW_REQUIRED"
    else:
        verdict = "READY_FOR_PROMOTION_REVIEW"

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "repo": str(REPO),
        "verdict": verdict,
        "blocker_count": blocker_count,
        "review_count": review_count,
        "issues": sorted(issues, key=lambda x: (-severity_rank.get(x["severity"], 0), x["area"], x["issue"])),
        "facts": facts,
    }

    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    pd.DataFrame(payload["issues"]).to_csv(OUT_CSV, index=False)

    md = []
    md.append("# Promotion Readiness Major Issues Audit")
    md.append("")
    md.append(f"Generated: `{payload['generated_at']}`")
    md.append(f"Repo: `{REPO}`")
    md.append("")
    md.append(f"## Verdict: `{verdict}`")
    md.append("")
    md.append(f"- Blockers: **{blocker_count}**")
    md.append(f"- Review items: **{review_count}**")
    md.append("")
    md.append("## Major Issues")
    if not payload["issues"]:
        md.append("")
        md.append("No major issues detected by this audit. Still perform manual review before promotion.")
    else:
        for idx, issue in enumerate(payload["issues"], start=1):
            md.append("")
            md.append(f"### {idx}. [{issue['severity']}] {issue['area']} — {issue['issue']}")
            md.append("")
            md.append(f"**Evidence:** {issue['evidence']}")
            md.append("")
            md.append(f"**Recommended action:** {issue['recommended_action']}")
    md.append("")
    md.append("## Key Files")
    for label, p in [
        ("draw_results_long", DRAW_RESULTS_LONG),
        ("comparison_summary", COMPARISON_SUMMARY),
        ("predictive_coverage_report", PREDICTIVE_COVERAGE_JSON),
        ("ml_predictions_report", ML_REPORT),
        ("materializer_audit", MATERIALIZER_AUDIT),
    ]:
        info = path_info(p)
        md.append(f"- {label}: `{p}` exists={info.get('exists')} size_mb={info.get('size_mb')}")
    md.append("")
    md.append("## Output Artifacts")
    md.append(f"- JSON: `{OUT_JSON}`")
    md.append(f"- CSV: `{OUT_CSV}`")
    md.append(f"- Markdown: `{OUT_MD}`")
    OUT_MD.write_text("\n".join(md), encoding="utf-8")

    print(json.dumps({
        "status": "DONE",
        "verdict": verdict,
        "blocker_count": blocker_count,
        "review_count": review_count,
        "report_md": str(OUT_MD),
        "report_json": str(OUT_JSON),
        "report_csv": str(OUT_CSV),
    }, indent=2))


if __name__ == "__main__":
    main()
'@ | Set-Content -Encoding UTF8 $Py

Write-Host "Running promotion readiness major issues audit..."
python $Py

Write-Host ""
Write-Host "Newest promotion readiness reports:"
Get-ChildItem "audits\promotion_readiness_major_issues" -File |
  Select-Object Name,Length,LastWriteTime |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 10 |
  Format-Table -AutoSize
