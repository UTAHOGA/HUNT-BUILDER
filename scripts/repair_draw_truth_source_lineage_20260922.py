"""Repair verified draw-truth lineage without changing historical outcomes.

The historical repair only replaces stale audit-capture ``source_path`` values
with byte-identical PDFs retained in the pipeline.  The 2026 repair removes the
PDF-reproduction rows after proving that every scorable row is duplicated by
the retained UtahDraws endpoint package.  Zero-row presentation padding is
retained in the audit output, not promoted as independent official truth.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import shutil
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DIR = ROOT / "data_truth/draw_results_truth/normalized/canonical_yearly"
CANONICAL_2026 = CANONICAL_DIR / "draw_results_2026_for_2027_canonical_yearly_draw_results.csv"
LONG_FILE = ROOT / "data_truth/draw_results_truth/normalized/draw_results_long.csv"
PARITY_SCRIPT = ROOT / "scripts/audit_2026_pdf_rows_vs_utahdraws_snapshot.py"
PDF_DATASET = "OFFICIAL_DWR_2026_PDF_DRAW_RESULTS"

HISTORICAL_MAPPINGS = (
    (2017, "official_dwr_archive/cougar/2018_cougar_odds_report.pdf",
     "pipeline/RAW/hunt_unit_database/2018/pdf/draw_odds/official_dwr_archive/cougar/2018_cougar_odds_report.pdf",
     "5524ab92b48cecff6b2e5899fc8400df6e6d3484839bd8f7c1aed0b21c337f25"),
    (2017, "official_dwr_archive/big_game/2018_sportsman_odds.pdf",
     "pipeline/RAW/hunt_unit_database/2018/pdf/draw_odds/official_dwr_archive/big_game/2018_sportsman_odds.pdf",
     "1bac9d99a29668d54cee67db5603a028326e5b50afb81a769b74916b8b33323b"),
    (2018, "official_dwr_archive/cougar/2019_cougar_odds_report.pdf",
     "pipeline/RAW/hunt_unit_database/2019/pdf/draw_odds/official_dwr_archive/cougar/2019_cougar_odds_report.pdf",
     "b39e97b45e3fbc7f215b2c317ad4aa76064e2166d1a29e29de826090b1914189"),
    (2019, "official_dwr_archive/cougar/2020_cougar_odds_report.pdf",
     "pipeline/RAW/hunt_unit_database/2020/pdf/draw_odds/official_dwr_archive/cougar/2020_cougar_odds_report.pdf",
     "ef23cd88492b9f1093909f2e1b1df69d9c057bc175b3768c1aa9fc1f565715cd"),
    (2021, "official_dwr_archive/cougar/2022_cougar_odds_report.pdf",
     "pipeline/RAW/hunt_unit_database/2022/pdf/draw_odds/official_dwr_archive/cougar/2022_cougar_odds_report.pdf",
     "49e82f3c79146e1139ee44c8252210740d3961499f94bcbac8941651fa455e55"),
    (2022, "official_dwr_archive/cougar/2023_cougar_odds_report.pdf",
     "pipeline/RAW/hunt_unit_database/2023/pdf/draw_odds/official_dwr_archive/cougar/2023_cougar_odds_report.pdf",
     "b7296b69abc2622f8418ea97da29b80341117c62216b70f9b612fb74943f0807"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    temp = path.with_suffix(path.suffix + ".lineage-repair.tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)


def load_parity_module():
    spec = importlib.util.spec_from_file_location("source_parity_2026", PARITY_SCRIPT)
    if not spec or not spec.loader:
        raise RuntimeError(f"Cannot load {PARITY_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def integer(value: object) -> int | None:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return None
    return int(float(text))


def numeric_outcome_checks(canonical: dict[str, str], endpoint: dict[str, str]) -> list[dict[str, object]]:
    apps = integer(endpoint.get("ParticipantCount"))
    success = integer(endpoint.get("SuccessfulCount"))
    if apps is None or success is None:
        raise ValueError("Endpoint row lacks applicant/success counts")
    expected = {
        "eligible_applicants": apps,
        "successful_applicants": success,
        "unsuccessful_applicants": apps - success,
        "bonus_permits": integer(endpoint.get("SuccessfulByMaxPointRoundCount")) or 0,
        "regular_permits": integer(endpoint.get("SuccessfulByRegularRoundCount")) or 0,
        "total_permits": success,
    }
    checks: list[dict[str, object]] = []
    for field, value in expected.items():
        actual = integer(canonical.get(field))
        checks.append({"field": field, "canonical": actual, "endpoint": value,
                       "status": "MATCH" if actual == value else "VALUE_MISMATCH"})
    probability = success / apps if apps else 0.0
    for field, value, tolerance in (
        ("p_draw", probability, 1e-9),
        ("p_draw_percent", probability * 100.0, 1e-6),
    ):
        actual = float(canonical.get(field) or 0)
        checks.append({"field": field, "canonical": actual, "endpoint": value,
                       "status": "MATCH" if math.isclose(actual, value, abs_tol=tolerance) else "VALUE_MISMATCH"})
    expected_ratio = "N/A" if success == 0 else f"1 in {apps / success:.1f}"
    actual_ratio = str(canonical.get("success_ratio") or "").strip()
    checks.append({"field": "success_ratio", "canonical": actual_ratio, "endpoint": expected_ratio,
                   "status": "MATCH" if actual_ratio == expected_ratio else "VALUE_MISMATCH"})
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    out_dir = (ROOT / args.out_dir).resolve()
    allowed = (ROOT / "audit_output_real_final").resolve()
    if not out_dir.is_relative_to(allowed):
        parser.error("out-dir must be below audit_output_real_final")
    out_dir.mkdir(parents=True, exist_ok=False)

    parity = load_parity_module()
    _, snapshot_rows = read_csv(parity.SNAPSHOT)
    raw_index: dict[tuple[tuple[str, str, str], str], list[dict[str, str]]] = defaultdict(list)
    for row in snapshot_rows:
        key = parity.identity(row.get("HuntCode"), row.get("residency_label"), row.get("Point"))
        raw_index[(key, parity.clean(row.get("source_json_file")))].append(row)

    historical_plan: list[dict[str, object]] = []
    historical_updates: dict[Path, dict[str, str]] = defaultdict(dict)
    for year, source_file, retained, expected_hash in HISTORICAL_MAPPINGS:
        canonical = CANONICAL_DIR / f"draw_results_{year}_for_{year + 1}_canonical_yearly_draw_results.csv"
        retained_path = ROOT / retained
        if not retained_path.exists() or sha256(retained_path) != expected_hash:
            raise RuntimeError(f"Retained source hash mismatch: {retained}")
        _fields, rows = read_csv(canonical)
        matching = [row for row in rows if row.get("source_file") == source_file]
        if not matching:
            raise RuntimeError(f"No canonical rows for {year}:{source_file}")
        old_paths = {row.get("source_path", "") for row in matching}
        if len(old_paths) != 1:
            raise RuntimeError(f"Ambiguous old source paths for {year}:{source_file}")
        old_path_text = next(iter(old_paths))
        old_path = ROOT / old_path_text
        if not old_path.exists() or sha256(old_path) != expected_hash:
            raise RuntimeError(f"Old source is not byte-identical: {old_path_text}")
        historical_updates[canonical][old_path_text] = retained
        historical_plan.append({
            "year": year,
            "source_file": source_file,
            "canonical_rows": len(matching),
            "old_source_path": old_path_text,
            "new_source_path": retained,
            "sha256": expected_hash,
            "byte_identity": True,
        })

    fields_2026, rows_2026 = read_csv(CANONICAL_2026)
    endpoint_backed = [row for row in rows_2026 if row.get("source_file", "").startswith("UtahDraws live DrawOddsData:")]
    endpoint_canonical_index: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in endpoint_backed:
        key = parity.identity(row.get("hunt_code"), row.get("residency"), row.get("points"))
        endpoint_canonical_index[key + (str(row.get("source_is_youth") or "").lower(),)].append(row)

    removed: list[dict[str, str]] = []
    comparisons: list[dict[str, object]] = []
    blockers: list[dict[str, object]] = []
    retained_2026: list[dict[str, str]] = []
    for row in rows_2026:
        if row.get("source_dataset") != PDF_DATASET:
            retained_2026.append(row)
            continue
        identity = parity.identity(row.get("hunt_code"), row.get("residency"), row.get("points"))
        endpoint_file = parity.expected_endpoint(row)
        candidates = raw_index.get((identity, endpoint_file), [])
        candidates, dimension_reason = parity.source_dimension_candidates(row, candidates)
        matching = [candidate for candidate in candidates if parity.values_match(row, candidate)]
        apps = integer(row.get("eligible_applicants")) or 0
        success = integer(row.get("successful_applicants")) or 0
        scorable = bool(apps or success)
        disposition = ""
        if scorable:
            if len(matching) != 1:
                blockers.append({"hunt_code": identity[0], "residency": identity[1], "points": identity[2],
                                 "reason": "SCORABLE_ENDPOINT_MATCH_NOT_UNIQUE", "match_count": len(matching)})
            else:
                endpoint = matching[0]
                checks = numeric_outcome_checks(row, endpoint)
                for check in checks:
                    comparisons.append({"hunt_code": identity[0], "residency": identity[1],
                                        "points": identity[2], "endpoint_file": endpoint_file,
                                        "source_dimension_resolution": dimension_reason,
                                        **check})
                bad = [check for check in checks if check["status"] != "MATCH"]
                youth = str(endpoint.get("IsYouth") or "").lower()
                live = endpoint_canonical_index.get(identity + (youth,), [])
                live = [candidate for candidate in live if
                        integer(candidate.get("eligible_applicants")) == integer(endpoint.get("ParticipantCount")) and
                        integer(candidate.get("successful_applicants")) == integer(endpoint.get("SuccessfulCount"))]
                if bad:
                    blockers.append({"hunt_code": identity[0], "residency": identity[1], "points": identity[2],
                                     "reason": "SCORABLE_NUMERIC_CELL_MISMATCH", "fields": [b["field"] for b in bad]})
                elif not live:
                    blockers.append({"hunt_code": identity[0], "residency": identity[1], "points": identity[2],
                                     "reason": "NO_RETAINED_ENDPOINT_CANONICAL_REPLACEMENT", "endpoint": endpoint_file})
                else:
                    disposition = "DUPLICATE_SCORABLE_PDF_ROW_REPLACED_BY_RETAINED_ENDPOINT"
        elif len(matching) == 1:
            disposition = "DUPLICATE_ZERO_PDF_ROW_REPLACED_BY_RETAINED_ENDPOINT"
        elif candidates:
            disposition = "STALE_ZERO_PDF_ROW_REPLACED_BY_ENDPOINT"
        else:
            disposition = "PRESENTATION_EMPTY_RUNG_WITHOUT_ENDPOINT_RECORD"
        audit_row = dict(row)
        audit_row["lineage_repair_disposition"] = disposition or "BLOCKED"
        audit_row["expected_endpoint_file"] = endpoint_file
        audit_row["endpoint_candidate_count"] = str(len(candidates))
        audit_row["endpoint_value_match_count"] = str(len(matching))
        removed.append(audit_row)

    if any(item["status"] != "MATCH" for item in comparisons):
        raise RuntimeError("Internal mismatch accounting failure")
    if blockers:
        (out_dir / "blockers.json").write_text(json.dumps(blockers, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "BLOCKED", "blockers": len(blockers)}, indent=2))
        return 1

    backup_dir = out_dir / "backups"
    backup_dir.mkdir()
    affected = sorted(set(historical_updates) | {CANONICAL_2026})
    before_hashes = {}
    for path in affected + [LONG_FILE]:
        before_hashes[path.relative_to(ROOT).as_posix()] = sha256(path)
        shutil.copy2(path, backup_dir / path.name)

    with (out_dir / "historical_source_path_plan.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(historical_plan[0]))
        writer.writeheader()
        writer.writerows(historical_plan)
    removed_fields = fields_2026 + ["lineage_repair_disposition", "expected_endpoint_file",
                                    "endpoint_candidate_count", "endpoint_value_match_count"]
    with (out_dir / "removed_2026_pdf_reproduction_rows.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=removed_fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(removed)
    comparison_fields = list(comparisons[0]) if comparisons else []
    with (out_dir / "scorable_2026_numeric_cell_comparisons.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=comparison_fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(comparisons)

    if args.apply:
        for canonical, replacements in historical_updates.items():
            text = canonical.read_text(encoding="utf-8-sig")
            for old, new in replacements.items():
                count = text.count(old)
                if count == 0:
                    raise RuntimeError(f"Historical source path not found in {canonical}: {old}")
                text = text.replace(old, new)
            canonical.write_text(text, encoding="utf-8-sig", newline="")
        write_csv(CANONICAL_2026, fields_2026, retained_2026)

    after_hashes = {
        path.relative_to(ROOT).as_posix(): sha256(path)
        for path in affected + [LONG_FILE]
    }
    summary = {
        "status": "APPLIED_CANONICALS_READY_FOR_LONG_REBUILD" if args.apply else "DRY_RUN_PASS",
        "apply": args.apply,
        "historical_source_groups_remapped": len(historical_plan),
        "historical_rows_remapped": sum(int(item["canonical_rows"]) for item in historical_plan),
        "historical_pdf_hashes_preserved": True,
        "canonical_2026_rows_before": len(rows_2026),
        "canonical_2026_pdf_reproduction_rows_removed": len(removed),
        "canonical_2026_rows_after": len(retained_2026),
        "scorable_2026_pdf_rows_verified": sum(1 for row in removed if row["lineage_repair_disposition"].startswith("DUPLICATE_SCORABLE")),
        "scorable_numeric_cells_verified": len(comparisons),
        "numeric_cell_mismatches": 0,
        "removed_dispositions": dict(Counter(row["lineage_repair_disposition"] for row in removed)),
        "before_hashes": before_hashes,
        "after_hashes": after_hashes,
        "draw_results_long_rebuilt": False,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
