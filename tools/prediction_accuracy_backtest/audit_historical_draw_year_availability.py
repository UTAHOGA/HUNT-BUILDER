#!/usr/bin/env python3
"""Audit early historical draw years for retrospective backtest readiness."""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = Path("audits/prediction_accuracy_backtest")
MAIN_DRAW_RESULTS = Path("data_truth/draw_results_truth/normalized/draw_results_long.csv")
EARLY_NORMALIZED_CANDIDATES = {
    2020: Path("data_truth/draw_results_truth/normalized/draw_results_2019_for_2020_candidate_promotion_file_records.csv"),
    2022: Path("data_truth/draw_results_truth/normalized/draw_results_2021_for_2022_candidate_promotion_file_records.csv"),
    2023: Path("data_truth/draw_results_truth/normalized/draw_results_2022_for_2023_candidate_promotion_file_records.csv"),
}
SOURCE_PARITY_FILES = {
    2021: [
        Path("data_truth/draw_results_truth/validation/draw_2020_for_2021_source_parity.csv"),
        Path("data_truth/draw_results_truth/validation/draw_2020_hashed_for_2021_source_parity.csv"),
    ],
}


def clean(value: object) -> str:
    return str(value or "").strip()


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    os.replace(tmp, path)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def parse_year(value: object) -> int | None:
    text = clean(value)
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def profile_csv(path: Path) -> dict[str, object]:
    if not path.exists():
        return {
            "exists": False,
            "path": str(path),
            "row_count": 0,
            "column_count": 0,
            "years": [],
            "unique_hunt_codes": 0,
            "rows_with_hunt_code": 0,
        }
    headers, rows = read_csv_rows(path)
    years = Counter()
    hunt_codes = set()
    rows_with_hunt_code = 0
    for row in rows:
        year = parse_year(row.get("year") or row.get("reported_draw_year") or row.get("draw_results_year"))
        if year is not None:
            years[str(year)] += 1
        code = clean(row.get("hunt_code") or row.get("candidate_hunt_code")).upper()
        if code:
            rows_with_hunt_code += 1
            hunt_codes.add(code)
    return {
        "exists": True,
        "path": str(path),
        "row_count": len(rows),
        "column_count": len(headers),
        "years": sorted(years),
        "year_row_counts": dict(sorted(years.items())),
        "unique_hunt_codes": len(hunt_codes),
        "rows_with_hunt_code": rows_with_hunt_code,
    }


def count_files(paths: list[Path], pattern: str) -> int:
    count = 0
    for base in paths:
        if not base.exists():
            continue
        count += sum(1 for path in base.rglob("*") if path.is_file() and path.match(pattern))
    return count


def find_source_files(root: Path, model_target_year: int) -> dict[str, object]:
    draw_year = model_target_year - 1
    repo_paths = [
        root / "pipeline" / "RAW" / "hunt_unit_database" / str(draw_year),
        root / "pipeline" / "RAW" / "hunt_unit_database" / str(model_target_year),
    ]
    bible_paths = [
        Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES") / str(draw_year),
        Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES") / str(model_target_year),
    ]
    filename_prefix = f"{draw_year}_PERMITS={model_target_year}_MODEL__*.pdf"
    repo_count = count_files(repo_paths, filename_prefix)
    bible_count = count_files(bible_paths, filename_prefix)
    return {
        "draw_year": draw_year,
        "model_target_year": model_target_year,
        "repo_source_file_count": repo_count,
        "bible_source_file_count": bible_count,
        "filename_pattern": filename_prefix,
        "repo_search_roots": ";".join(str(path) for path in repo_paths if path.exists()),
        "bible_search_roots": ";".join(str(path) for path in bible_paths if path.exists()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    root = (Path(args.root) if args.root else REPO_ROOT).resolve()
    out_dir = root / args.out_dir
    main_profile = profile_csv(root / MAIN_DRAW_RESULTS)

    main_year_counts = main_profile.get("year_row_counts", {}) if isinstance(main_profile.get("year_row_counts"), dict) else {}
    rows: list[dict[str, object]] = []
    for target_year in (2020, 2021, 2022):
        draw_year = target_year - 1
        source_profile = find_source_files(root, target_year)
        main_rows = int(main_year_counts.get(str(draw_year), 0))
        candidate_path = EARLY_NORMALIZED_CANDIDATES.get(target_year)
        candidate_profile = profile_csv(root / candidate_path) if candidate_path else profile_csv(root / "__missing__")
        parity_files = SOURCE_PARITY_FILES.get(target_year, [])
        parity_profiles = [profile_csv(root / path) for path in parity_files]
        parity_pass_rows = 0
        for profile, parity_path in zip(parity_profiles, parity_files):
            if not profile.get("exists"):
                continue
            _, parity_rows = read_csv_rows(root / parity_path)
            parity_pass_rows += sum(1 for row in parity_rows if clean(row.get("status")).upper() == "PASS")

        if main_rows > 0:
            readiness = "READY_IN_MAIN_NORMALIZED_SOURCE"
            materializer_status = "RUNNABLE"
            blocker = ""
        elif candidate_profile["exists"] and int(candidate_profile["rows_with_hunt_code"]) > 0:
            readiness = "READY_WITH_EXTRA_NORMALIZED_SOURCE"
            materializer_status = "RUNNABLE_WITH_EXTRA_SOURCE"
            blocker = ""
        elif int(source_profile["repo_source_file_count"]) + int(source_profile["bible_source_file_count"]) > 0 or parity_pass_rows > 0:
            readiness = "SOURCE_AVAILABLE_NOT_NORMALIZED"
            materializer_status = "BLOCKED_UNTIL_NORMALIZED"
            blocker = "source files/parity evidence exist, but no normalized row-level draw-result source is available to the materializer"
        else:
            readiness = "MISSING_SOURCE_AND_NORMALIZED_ROWS"
            materializer_status = "BLOCKED_MISSING_SOURCE"
            blocker = "no normalized row-level source and no matching local source files found"

        command = ""
        if readiness == "READY_IN_MAIN_NORMALIZED_SOURCE":
            history = ",".join(str(year) for year in range(2019, target_year) if int(main_year_counts.get(str(year), 0)) > 0)
            command = f"python tools/prediction_accuracy_backtest/build_retrospective_materialized_predictions.py --target-year {target_year} --history-years {history}"
        elif readiness == "READY_WITH_EXTRA_NORMALIZED_SOURCE" and candidate_path:
            command = (
                "python tools/prediction_accuracy_backtest/build_retrospective_materialized_predictions.py "
                f"--target-year {target_year} --history-years {draw_year} "
                f"--extra-source-draw-results {candidate_path.as_posix()}"
            )

        rows.append(
            {
                "target_year": target_year,
                "training_cutoff_year": draw_year,
                "draw_result_year_needed": draw_year,
                "main_draw_results_long_rows_for_needed_year": main_rows,
                "extra_normalized_source": str(candidate_path or ""),
                "extra_normalized_exists": candidate_profile["exists"],
                "extra_normalized_rows": candidate_profile["row_count"],
                "extra_normalized_rows_with_hunt_code": candidate_profile["rows_with_hunt_code"],
                "repo_source_file_count": source_profile["repo_source_file_count"],
                "bible_source_file_count": source_profile["bible_source_file_count"],
                "source_parity_pass_rows": parity_pass_rows,
                "readiness": readiness,
                "materializer_status": materializer_status,
                "blocked_reason": blocker,
                "recommended_command": command,
            }
        )

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "main_draw_results_long": main_profile,
        "target_years": rows,
        "production_truth_modified": False,
        "raw_sources_modified": False,
        "website_or_r2_modified": False,
    }

    csv_path = out_dir / "historical_draw_year_availability_audit.csv"
    json_path = out_dir / "historical_draw_year_availability_audit.json"
    md_path = out_dir / "historical_draw_year_availability_audit.md"
    fields = [
        "target_year",
        "training_cutoff_year",
        "draw_result_year_needed",
        "main_draw_results_long_rows_for_needed_year",
        "extra_normalized_source",
        "extra_normalized_exists",
        "extra_normalized_rows",
        "extra_normalized_rows_with_hunt_code",
        "repo_source_file_count",
        "bible_source_file_count",
        "source_parity_pass_rows",
        "readiness",
        "materializer_status",
        "blocked_reason",
        "recommended_command",
    ]
    write_csv(csv_path, fields, rows)
    write_json(json_path, summary)

    lines = [
        "# Historical Draw Year Availability Audit",
        "",
        "This audit is read-only against production truth and raw sources. It only reports whether early years can safely feed the retrospective materializer.",
        "",
        "## Results",
        "",
        "| Target year | Needed draw year | Readiness | Main normalized rows | Extra normalized rows | Source files | Blocker |",
        "| --- | ---: | --- | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        source_count = int(row["repo_source_file_count"]) + int(row["bible_source_file_count"])
        lines.append(
            f"| {row['target_year']} | {row['draw_result_year_needed']} | {row['readiness']} | "
            f"{row['main_draw_results_long_rows_for_needed_year']} | {row['extra_normalized_rows']} | {source_count} | {row['blocked_reason']} |"
        )
    lines.extend(
        [
            "",
            "## Safe Process Update",
            "",
            "- Target 2020 can run only by passing the 2019-for-2020 normalized candidate file as an extra retrospective source.",
            "- Target 2021 is blocked until 2020-for-2021 draw-result rows are normalized and promoted into a materializer-readable CSV.",
            "- Target 2022 is already covered by `draw_results_long.csv` year 2021 rows.",
            "",
            "No production feeder, raw source, website, manifest, R2, or normalized truth file was edited by this audit.",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
