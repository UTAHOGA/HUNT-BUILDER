import csv
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from fix_2019_numeric_hunt_names_from_pdf_titles import build_title_map, clean


REPO = Path(__file__).resolve().parents[1]
TARGET = (
    REPO
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "draw_results_2019_for_2020_candidate_promotion_file_records.csv"
)
AUDIT_DIR = (
    REPO
    / "audits"
    / "truth_cross_year"
    / "final_yearly_canonical_audit"
    / "2019_for_2020"
    / "hunt_name_numeric_cleanup_feeder"
)
BACKUPS = AUDIT_DIR / "backups"


def is_numeric_text(value):
    text = clean(value)
    return bool(text) and text.isdigit()


def main():
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    BACKUPS.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    title_map, title_by_hunt_code, _, _ = build_title_map()

    with TARGET.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)

    backup = BACKUPS / f"feeder_cleanup_{timestamp}.csv"
    backup.write_bytes(TARGET.read_bytes())

    numeric_rows = 0
    changed_rows = 0
    counts_by_source = Counter()
    counts_by_code = Counter()
    samples = []

    for row in rows:
        source_file = clean(row.get("source_file"))
        hunt_code = clean(row.get("hunt_code"))
        hunt_name = clean(row.get("hunt_name"))

        if not is_numeric_text(hunt_name):
            continue

        numeric_rows += 1
        title = title_map.get((source_file, hunt_code)) or title_by_hunt_code.get(hunt_code)
        if not title:
            continue

        if title != hunt_name:
            row["hunt_name"] = title
            changed_rows += 1
            counts_by_source[source_file] += 1
            counts_by_code[hunt_code] += 1
            if len(samples) < 100:
                samples.append(
                    {
                        "source_file": source_file,
                        "hunt_code": hunt_code,
                        "old_hunt_name": hunt_name,
                        "new_hunt_name": title,
                    }
                )

    temp_target = TARGET.with_name(f"{TARGET.stem}.numeric_cleanup_{timestamp}.tmp")
    with temp_target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    shutil.move(str(temp_target), str(TARGET))

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "target": str(TARGET),
        "backup": str(backup),
        "numeric_rows_scanned": numeric_rows,
        "rows_changed": changed_rows,
        "changed_by_source_file": dict(sorted(counts_by_source.items())),
        "changed_by_hunt_code": dict(sorted(counts_by_code.items())),
        "sample_changes": samples,
        "status": "PASS" if changed_rows else "NO_CHANGES",
    }
    (AUDIT_DIR / "2019_numeric_hunt_name_cleanup_feeder_report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
