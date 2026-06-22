import csv
import hashlib
import json
import os
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly" / "draw_results_2026_for_2027_canonical_yearly_draw_results.csv"
LONG = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
AUDIT_DIR = ROOT / "audits" / "2026_live_source_comparison"


def clean(value):
    return " ".join(str(value or "").split())


def row_digest(row, fields):
    payload = "\x1f".join(clean(row.get(field)) for field in fields)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def load_rows(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def main():
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    canonical_fields, canonical_rows = load_rows(CANONICAL)
    with LONG.open(newline="", encoding="utf-8-sig") as f:
        long_reader = csv.DictReader(f)
        long_fields = long_reader.fieldnames
        old_2026 = []
        kept_count = 0
        tmp = LONG.with_suffix(".csv.tmp")
        with tmp.open("w", newline="", encoding="utf-8") as out:
            writer = csv.DictWriter(out, fieldnames=long_fields, lineterminator="\n")
            writer.writeheader()
            for row in long_reader:
                if clean(row.get("actual_draw_year")) == "2026":
                    old_2026.append(row)
                else:
                    writer.writerow(row)
                    kept_count += 1
            for row in canonical_rows:
                writer.writerow({field: row.get(field, "") for field in long_fields})

    common_fields = [field for field in canonical_fields if field in long_fields]
    old_counts = Counter(row_digest(row, common_fields) for row in old_2026)
    new_counts = Counter(row_digest(row, common_fields) for row in canonical_rows)
    extra_old = old_counts - new_counts
    missing_old = new_counts - old_counts

    extras_by_code = Counter()
    missing_by_code = Counter()
    digest_to_old = {}
    digest_to_new = {}
    for row in old_2026:
        digest_to_old.setdefault(row_digest(row, common_fields), row)
    for row in canonical_rows:
        digest_to_new.setdefault(row_digest(row, common_fields), row)
    for digest, count in extra_old.items():
        extras_by_code[clean(digest_to_old[digest].get("hunt_code"))] += count
    for digest, count in missing_old.items():
        missing_by_code[clean(digest_to_new[digest].get("hunt_code"))] += count

    os.replace(tmp, LONG)

    summary = {
        "long_rows_kept_non_2026": kept_count,
        "long_2026_rows_before": len(old_2026),
        "canonical_2026_rows": len(canonical_rows),
        "long_2026_rows_after": len(canonical_rows),
        "old_2026_exact_payload_extra_rows": sum(extra_old.values()),
        "old_2026_exact_payload_missing_rows": sum(missing_old.values()),
        "top_extra_old_hunt_codes": extras_by_code.most_common(25),
        "top_missing_old_hunt_codes": missing_by_code.most_common(25),
        "long_file_size_bytes_after": LONG.stat().st_size,
    }
    (AUDIT_DIR / "replace_draw_results_long_2026_slice_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
