"""Run shadow-only zero-preserving calibration for Antlerless Deer predictions.

This tool never overwrites production prediction files. It reads a prediction
CSV, adds shadow-only calibration columns to an audit copy, and writes audit
summary artifacts.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from engine.utah_draw_predictive.calibration import (
    CALIBRATION_FAMILY,
    CALIBRATION_GUARDRAIL_VERSION,
    CALIBRATION_INTERCEPT,
    CALIBRATION_METHOD,
    CALIBRATION_SLOPE,
    build_shadow_calibration_audit,
    shadow_calibration_columns,
)


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _probability_column(fields: list[str], requested: str | None) -> str:
    if requested:
        if requested not in fields:
            raise SystemExit(f"Requested probability column not found: {requested}")
        return requested
    for candidate in ("p_draw", "p_draw_mean", "p_preference_draw"):
        if candidate in fields:
            return candidate
    raise SystemExit("No probability column found; expected one of p_draw, p_draw_mean, p_preference_draw")


def _key_columns(fields: list[str]) -> tuple[str, ...]:
    point_column = "point_value" if "point_value" in fields else "points"
    candidates = ["draw_year", "year", "target_year", "hunt_code", "residency", point_column, "draw_system_type"]
    selected: list[str] = []
    for column in candidates:
        if column in fields and column not in selected:
            selected.append(column)
    return tuple(selected)


def run_shadow_calibration(
    *,
    input_csv: Path,
    audit_dir: Path,
    enable_shadow_calibration: bool,
    calibration_mode: str,
    calibrate_family: str,
    probability_column: str | None = None,
) -> dict[str, Any]:
    if not enable_shadow_calibration:
        raise SystemExit("Shadow calibration is disabled. Pass --enable-shadow-calibration to run.")
    if calibration_mode != "shadow":
        raise SystemExit("This tool is shadow-only. Pass --calibration-mode shadow.")
    if calibrate_family != CALIBRATION_FAMILY:
        raise SystemExit(f"This tool only supports --calibrate-family {CALIBRATION_FAMILY}.")

    rows, fields = read_csv(input_csv)
    p_col = _probability_column(fields, probability_column)
    key_cols = _key_columns(fields)
    audit_dir.mkdir(parents=True, exist_ok=True)

    shadow_columns = [
        "p_draw_raw",
        "p_draw_shadow_calibrated",
        "calibration_family",
        "calibration_method",
        "calibration_applied",
        "calibration_zero_preserved",
        "calibration_intercept",
        "calibration_slope",
        "calibration_guardrail_version",
    ]

    output_rows: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    p_draw_preserved = True

    for row in rows:
        out = dict(row)
        original_p_draw = row.get("p_draw")
        out.update(
            shadow_calibration_columns(
                row,
                row.get(p_col),
                enabled=enable_shadow_calibration,
                mode=calibration_mode,
                calibrate_family=calibrate_family,
            )
        )
        if out.get("p_draw") != original_p_draw:
            p_draw_preserved = False
        output_rows.append(out)
        if str(row.get("draw_system_type") or "").strip().upper() == CALIBRATION_FAMILY:
            target_rows.append(out)

    output_fields = list(fields)
    for column in shadow_columns:
        if column not in output_fields:
            output_fields.append(column)

    all_rows_path = audit_dir / "shadow_family_predictions_with_antlerless_deer_calibration.csv"
    rows_path = audit_dir / "antlerless_deer_shadow_calibration_rows.csv"
    write_csv(all_rows_path, output_rows, output_fields)
    write_csv(rows_path, target_rows, output_fields)

    audit = build_shadow_calibration_audit(
        rows,
        enabled=enable_shadow_calibration,
        mode=calibration_mode,
        probability_column=p_col,
        key_columns=key_cols,
    )
    audit_dict = audit.as_dict()
    audit_dict.update(
        {
            "input_csv": str(input_csv),
            "audit_dir": str(audit_dir),
            "probability_column": p_col,
            "key_columns": list(key_cols),
            "all_rows_output_csv": str(all_rows_path),
            "target_family_rows_csv": str(rows_path),
            "p_draw_preserved": p_draw_preserved,
            "source_training_basis": {
                "training_years": "2019-2025",
                "training_rows": 1155,
                "training_hunt_codes": 46,
                "raw_mae": 0.09285318607320348,
                "zero_preserving_shadow_mae": 0.08290418748069789,
                "raw_bias": -0.029032867932943726,
                "zero_preserving_shadow_bias": -0.0070894447514193906,
            },
            "unpublished_actuals_guardrail": "2026 Antlerless Deer is prediction-only and is not scored against unpublished actual draw results.",
        }
    )

    json_path = audit_dir / "antlerless_deer_shadow_calibration_audit.json"
    json_path.write_text(json.dumps(audit_dict, indent=2), encoding="utf-8")

    md_lines = [
        "# Antlerless Deer Shadow Calibration Audit",
        "",
        f"Classification: `{CALIBRATION_METHOD}_SHADOW_ONLY_AUDIT`",
        "",
        "## Guardrails",
        f"- Family: `{CALIBRATION_FAMILY}`",
        f"- Enabled: `{str(enable_shadow_calibration).lower()}`",
        f"- Mode: `{calibration_mode}`",
        f"- Production applied: `false`",
        f"- p_draw preserved: `{str(p_draw_preserved).lower()}`",
        f"- Guardrail version: `{CALIBRATION_GUARDRAIL_VERSION}`",
        "",
        "## Parameters",
        f"- Intercept: `{CALIBRATION_INTERCEPT}`",
        f"- Slope: `{CALIBRATION_SLOPE}`",
        "",
        "## Counts",
        f"- Rows seen: `{audit.rows_seen}`",
        f"- Target rows shadow calibrated: `{audit.rows_shadow_calibrated}`",
        f"- Raw zero rows: `{audit.rows_raw_zero}`",
        f"- Zero rows preserved: `{audit.rows_zero_preserved}`",
        f"- Rows clipped to zero: `{audit.rows_clipped_to_zero}`",
        f"- Rows clipped to one: `{audit.rows_clipped_to_one}`",
        f"- Duplicate key rows: `{audit.duplicate_key_rows}`",
        "",
        "## Means",
        f"- Raw mean: `{audit.raw_mean}`",
        f"- Shadow mean: `{audit.shadow_mean}`",
        f"- Mean delta: `{audit.mean_delta}`",
        f"- Max delta: `{audit.max_delta}`",
        "",
        "## Outputs",
        f"- `{all_rows_path}`",
        f"- `{rows_path}`",
        f"- `{json_path}`",
        "",
        "2026 Antlerless Deer actual draw results are unpublished; this audit does not score 2026 Antlerless Deer as actual truth.",
    ]
    md_path = audit_dir / "antlerless_deer_shadow_calibration_summary.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    audit_dict["summary_md"] = str(md_path)
    return audit_dict


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--audit-dir", type=Path, default=REPO / "audits" / "antlerless_deer_shadow_calibration" / _timestamp())
    parser.add_argument("--probability-column")
    parser.add_argument("--enable-shadow-calibration", action="store_true")
    parser.add_argument("--calibration-mode", choices=["off", "shadow"], default="off")
    parser.add_argument("--calibrate-family", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_shadow_calibration(
        input_csv=args.input_csv,
        audit_dir=args.audit_dir,
        enable_shadow_calibration=args.enable_shadow_calibration,
        calibration_mode=args.calibration_mode,
        calibrate_family=args.calibrate_family,
        probability_column=args.probability_column,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
