"""Compare 2026 PDF-derived canonical rows to retained UtahDraws raw records."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly" / "draw_results_2026_for_2027_canonical_yearly_draw_results.csv"
SNAPSHOT = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "json" / "draw_results" / "utahdraws_2026_20260826" / "utahdraws_2026" / "csv" / "2026_allowed_draw_odds_all_flat_rows.csv"
OUT_DIR = ROOT / "data_truth" / "draw_results_truth" / "validation"
OUT_CSV = OUT_DIR / "draw_2026_pdf_rows_vs_utahdraws_snapshot.csv"
OUT_JSON = OUT_DIR / "draw_2026_pdf_rows_vs_utahdraws_snapshot.json"


def clean(value: object) -> str:
    return str(value or "").strip()


def points(value: object) -> str:
    text = clean(value)
    try:
        return str(int(float(text)))
    except ValueError:
        return text


def key(code: object, residency: object, point: object) -> tuple[str, str, str]:
    return clean(code).upper(), clean(residency).lower(), points(point)


def integer(value: object) -> int | None:
    text = clean(value)
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    raw_index: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for raw in read_csv(SNAPSHOT):
        raw_index[key(raw.get("HuntCode"), raw.get("residency_label"), raw.get("Point"))].append(raw)

    output: list[dict[str, str]] = []
    for row in read_csv(CANONICAL):
        if clean(row.get("source_dataset")) != "OFFICIAL_DWR_2026_PDF_DRAW_RESULTS":
            continue
        row_key = key(row.get("hunt_code"), row.get("residency"), row.get("points"))
        matches = raw_index.get(row_key, [])
        result = {
            "hunt_code": row_key[0], "residency": clean(row.get("residency")), "points": row_key[2],
            "canonical_source_file": clean(row.get("source_file")), "canonical_pdf_page": clean(row.get("pdf_page")),
            "canonical_eligible_applicants": clean(row.get("eligible_applicants")),
            "canonical_successful_applicants": clean(row.get("successful_applicants")),
            "snapshot_matches": str(len(matches)), "snapshot_source_json_files": "",
            "snapshot_participant_count": "", "snapshot_successful_count": "", "parity_status": "", "notes": "",
        }
        if not matches:
            result["parity_status"] = "NO_SNAPSHOT_IDENTITY"
            result["notes"] = "Retained UtahDraws snapshot has no exact hunt/residency/point record. Original PDF recovery or another official source is required."
        elif len(matches) != 1:
            result["parity_status"] = "AMBIGUOUS_SNAPSHOT_IDENTITY"
            result["snapshot_source_json_files"] = " | ".join(sorted({clean(item.get("source_json_file")) for item in matches}))
            result["notes"] = "More than one retained endpoint row has the canonical identity; endpoint-level selection must be resolved."
        else:
            raw = matches[0]
            result["snapshot_source_json_files"] = clean(raw.get("source_json_file"))
            result["snapshot_participant_count"] = clean(raw.get("ParticipantCount"))
            result["snapshot_successful_count"] = clean(raw.get("SuccessfulCount"))
            expected_applicants = integer(row.get("eligible_applicants"))
            expected_successes = integer(row.get("successful_applicants"))
            actual_applicants = integer(raw.get("ParticipantCount"))
            actual_successes = integer(raw.get("SuccessfulCount"))
            comparable = [(expected_applicants, actual_applicants), (expected_successes, actual_successes)]
            filled = [(left, right) for left, right in comparable if left is not None]
            if not filled:
                result["parity_status"] = "IDENTITY_ONLY_NO_COMPARABLE_METRIC"
                result["notes"] = "Exact snapshot identity exists, but the canonical PDF row has no comparable applicant/success value."
            elif all(left == right for left, right in filled):
                result["parity_status"] = "VALUE_PARITY"
                result["notes"] = "Exact hunt/residency/point identity and every populated applicant/success metric match the retained official endpoint row."
            else:
                result["parity_status"] = "VALUE_MISMATCH"
                result["notes"] = "Exact identity exists, but one or more populated applicant/success metrics differ from the retained endpoint row."
        output.append(result)

    fields = list(output[0]) if output else []
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "canonical_pdf_rows": len(output),
        "status_counts": dict(sorted(Counter(row["parity_status"] for row in output).items())),
        "rows_with_exact_value_parity": sum(row["parity_status"] == "VALUE_PARITY" for row in output),
        "rows_requiring_source_recovery_or_review": sum(row["parity_status"] not in {"VALUE_PARITY", "IDENTITY_ONLY_NO_COMPARABLE_METRIC"} for row in output),
        "comparison_identity": "hunt_code + residency + points",
        "comparison_metrics": ["eligible_applicants == ParticipantCount", "successful_applicants == SuccessfulCount"],
        "output_csv": OUT_CSV.relative_to(ROOT).as_posix(),
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
