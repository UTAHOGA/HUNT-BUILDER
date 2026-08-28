"""Audit canonical draw-truth source labels against retained parent sources.

This is a lineage audit, not a data rewrite.  A canonical source scope can be
reported as linked only when it has either an exact retained parent filename or
one unambiguous, source-title-backed parent report.  Multi-parent and 2026
endpoint cases remain review records instead of being guessed into a link.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DIR = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
ARCHIVE_CATALOG = ROOT / "data_truth" / "draw_results_truth" / "raw_inventory" / "official_draw_source_retention_2017_2026.csv"
OUT_DIR = ROOT / "data_truth" / "draw_results_truth" / "validation"
OUT_CSV = OUT_DIR / "canonical_parent_source_mapping_2018_2026.csv"
OUT_JSON = OUT_DIR / "canonical_parent_source_mapping_2018_2026.json"

FIELDS = [
    "draw_year", "canonical_source_label", "canonical_rows", "canonical_pdf_pages",
    "source_dataset_values", "source_scope_values", "mapping_status", "mapping_method",
    "parent_report_year", "parent_archive_paths", "parent_official_urls", "parent_sha256s", "notes",
]


def clean(value: object) -> str:
    return str(value or "").strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def source_label(value: str) -> str:
    text = clean(value)
    if not text:
        return ""
    # Canonicals contain both bare filenames and Windows absolute paths.
    return PureWindowsPath(text).name or Path(text).name


def norm(value: object) -> str:
    text = source_label(clean(value)).lower().replace("&amp;", "and")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parent_candidates(label: str, sources: list[dict[str, str]]) -> tuple[str, list[dict[str, str]], str]:
    """Return status, candidate sources, and a transparent matching method."""
    label_norm = norm(label)
    exact = [s for s in sources if source_label(s["durable_archive_path"]).lower() == source_label(label).lower()]
    if len(exact) == 1:
        return "LINKED", exact, "EXACT_ARCHIVED_FILENAME"
    if label.lower().startswith("utahdraws live drawoddsdata:"):
        return "ENDPOINT_GROUP_REVIEW", [], "2026_LIVE_ENDPOINT_GROUP_REQUIRES_HUNT_LEVEL_MATCH"
    if "2026_permits=2027_model" in label_norm or "2026 permits 2027 model" in label_norm:
        return "SOURCE_RECOVERY_REQUIRED", [], "2026_CANONICAL_PDF_PARENT_NOT_RETAINED"

    # Parent report titles are official page labels. Use deliberate, conservative
    # design-family anchors rather than filename similarity or a fuzzy score.
    rules: list[tuple[str, tuple[str, ...]]] = [
        ("sportsman", ("sportsman",)),
        ("youth_antlerless", ("youth", "antlerless")),
        ("antlerless", ("antlerless",)),
        ("youth_dedicated_hunter", ("youth", "dedicated hunter")),
        ("dedicated_hunter", ("dedicated hunter",)),
        ("lifetime_deer", ("lifetime", "deer")),
        ("youth_elk", ("youth", "elk")),
        ("youth_deer", ("youth", "deer")),
        ("general_deer", ("general", "deer")),
        ("le_oil_parent", ("limited", "entry")),
    ]
    category = ""
    if any(token in label_norm for token in ("black bear", "bear draw", "bear_")):
        category = "black_bear"
    elif "cougar" in label_norm:
        category = "cougar"
    elif "turkey" in label_norm:
        category = "turkey"
    elif "sportsman" in label_norm:
        category = "sportsman"
    elif "youth" in label_norm and "antlerless" in label_norm:
        category = "youth_antlerless"
    elif "antlerless" in label_norm or "doe" in label_norm or "ewe" in label_norm:
        category = "antlerless"
    elif ("dedicated" in label_norm or " d h " in f" {label_norm} ") and "youth" in label_norm:
        category = "youth_dedicated_hunter"
    elif "dedicated" in label_norm or " d h " in f" {label_norm} ":
        category = "dedicated_hunter"
    elif "lifetime" in label_norm:
        category = "lifetime_deer"
    elif "youth" in label_norm and ("elk" in label_norm or "bull" in label_norm):
        category = "youth_elk"
    elif "youth" in label_norm and "deer" in label_norm:
        category = "youth_deer"
    elif "general" in label_norm or "g s" in label_norm:
        category = "general_deer"
    elif any(token in label_norm for token in ("c w m u big game", "l e", "o i l", "once in a lifetime", "mountain goat", "bighorn", "bison")):
        category = "le_oil_parent"

    if category in {"black_bear", "cougar", "turkey"}:
        candidates = [source for source in sources if clean(source["source_family"]) == category]
        if len(candidates) == 1:
            return "LINKED", candidates, f"OFFICIAL_SOURCE_FAMILY:{category}"
        return ("AMBIGUOUS_PARENT" if candidates else "UNMAPPED", candidates, f"OFFICIAL_SOURCE_FAMILY:{category}")

    for rule_name, required in rules:
        if category != rule_name:
            continue
        candidates = [s for s in sources if all(token in clean(s["official_title"]).lower() for token in required)]
        if "youth" in label_norm:
            candidates = [s for s in candidates if "youth" in clean(s["official_title"]).lower()]
        else:
            candidates = [s for s in candidates if "youth" not in clean(s["official_title"]).lower()]
        if len(candidates) == 1:
            return "LINKED", candidates, f"OFFICIAL_TITLE_RULE:{rule_name}"
        return ("AMBIGUOUS_PARENT" if candidates else "UNMAPPED", candidates, f"OFFICIAL_TITLE_RULE:{rule_name}")
    return "UNMAPPED", [], "NO_CONSERVATIVE_PARENT_RULE"


def main() -> None:
    archive_rows = read_csv(ARCHIVE_CATALOG)
    by_year: dict[int, list[dict[str, str]]] = {}
    for row in archive_rows:
        try:
            year = int(clean(row.get("report_year")))
        except ValueError:
            continue
        by_year.setdefault(year, []).append(row)

    output: list[dict[str, str]] = []
    for canonical in sorted(CANONICAL_DIR.glob("draw_results_*_for_*_canonical_yearly_draw_results.csv")):
        match = re.search(r"draw_results_(20\d{2})_for_", canonical.name)
        if not match:
            continue
        year = int(match.group(1))
        groups: dict[str, list[dict[str, str]]] = {}
        for row in read_csv(canonical):
            label = clean(row.get("source_file"))
            if not label:
                label = "(blank source file)"
            groups.setdefault(label, []).append(row)
        for label, rows in sorted(groups.items()):
            status, parents, method = parent_candidates(label, by_year.get(year, []))
            output.append({
                "draw_year": str(year),
                "canonical_source_label": label,
                "canonical_rows": str(len(rows)),
                "canonical_pdf_pages": str(sum(1 for row in rows if clean(row.get("pdf_page")))),
                "source_dataset_values": " | ".join(sorted({clean(row.get("source_dataset")) for row in rows if clean(row.get("source_dataset"))})),
                "source_scope_values": " | ".join(sorted({clean(row.get("source_scope")) for row in rows if clean(row.get("source_scope"))}))[:2000],
                "mapping_status": status,
                "mapping_method": method,
                "parent_report_year": " | ".join(sorted({clean(parent["report_year"]) for parent in parents})),
                "parent_archive_paths": " | ".join(parent["durable_archive_path"] for parent in parents),
                "parent_official_urls": " | ".join(parent["official_url"] for parent in parents),
                "parent_sha256s": " | ".join(parent["sha256"] for parent in parents),
                "notes": "Parent link is evidence only; value-level PDF/endpoint parity remains a separate validation.",
            })

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(output)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Canonical source-label to archived-parent evidence audit; no canonical values were changed.",
        "source_scope_records": len(output),
        "rows_by_mapping_status": dict(sorted(Counter(row["mapping_status"] for row in output).items())),
        "canonical_rows_by_mapping_status": dict(sorted(Counter({status: sum(int(row["canonical_rows"]) for row in output if row["mapping_status"] == status) for status in {row["mapping_status"] for row in output}}).items())),
        "mapping_csv": OUT_CSV.relative_to(ROOT).as_posix(),
        "next_gate": "Only LINKED source scopes may be marked parent-source reproducible. AMBIGUOUS_PARENT, ENDPOINT_GROUP_REVIEW, SOURCE_RECOVERY_REQUIRED, and UNMAPPED require resolution.",
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
