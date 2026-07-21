#!/usr/bin/env python3
"""Split mixed hunt-type draw-odds fragments into active single-hunt-type PDFs."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import fitz


REPO = Path(__file__).resolve().parents[1]
AUDIT_ROOT = REPO / "audits" / "draw_odds_pdf_page_role_audit"


def safe_repo_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = REPO / path
    resolved = path.resolve()
    resolved.relative_to(REPO.resolve())
    return resolved


def draw_odds_root(path: Path) -> Path:
    parts = list(path.parts)
    lowered = [part.lower() for part in parts]
    for index in range(len(lowered) - 1):
        if lowered[index] == "draw_odds":
            return Path(*parts[: index + 1])
    raise ValueError(f"Cannot find draw_odds root for {path}")


def active_hunt_types(hunt_type_counts_json: str) -> list[str]:
    counts = json.loads(hunt_type_counts_json or "{}")
    return [hunt_type for hunt_type in counts if hunt_type != "UNKNOWN"]


def clean_stem(stem: str) -> str:
    stem = re.sub(r"__([A-Z0-9_]+)$", "", stem)
    stem = stem.replace("__CWMU_DEDUPED", "").replace("__CWMU_UNIQUE_PAGES", "")
    return stem


def target_for(source: Path, hunt_type: str) -> Path:
    root = draw_odds_root(source)
    stem = clean_stem(source.stem)
    return root / "Split By Hunt Type" / hunt_type / f"{stem}__{hunt_type}.pdf"


def write_page_subset(source: Path, target: Path, page_indexes: list[int]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    with fitz.open(source) as src:
        out = fitz.open()
        for page_index in page_indexes:
            out.insert_pdf(src, from_page=page_index, to_page=page_index)
        out.save(tmp)
        out.close()
    tmp.replace(target)


def append_pdf(source: Path, target: Path) -> None:
    tmp = target.with_suffix(target.suffix + ".tmp")
    with fitz.open(target) as target_doc:
        with fitz.open(source) as source_doc:
            target_doc.insert_pdf(source_doc)
        target_doc.save(tmp)
    tmp.replace(target)


def page_groups(audit_dir: Path) -> dict[str, dict[str, list[int]]]:
    groups: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    with (audit_dir / "page_role_audit.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            hunt_type = row["hunt_type"]
            if hunt_type == "UNKNOWN":
                continue
            source = str(safe_repo_path(row["source_pdf"]))
            groups[source][hunt_type].append(int(row["page_number"]) - 1)
    return groups


def hunt_codes_by_pdf(audit_dir: Path) -> dict[str, set[str]]:
    by_pdf: dict[str, set[str]] = defaultdict(set)
    with (audit_dir / "page_role_audit.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            hunt_code = (row.get("hunt_code") or "").strip()
            if hunt_code:
                by_pdf[str(safe_repo_path(row["source_pdf"]))].add(hunt_code)
    return by_pdf


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    audit_dir = args.audit_dir
    if not audit_dir.is_absolute():
        audit_dir = REPO / audit_dir
    file_audit = audit_dir / "file_role_audit.csv"

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    groups_by_pdf = page_groups(audit_dir)
    codes_by_pdf = hunt_codes_by_pdf(audit_dir)
    backup_dir = AUDIT_ROOT / f"mixed_hunt_type_fragment_merge_backups_{stamp}"

    rows: list[dict[str, object]] = []
    with file_audit.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            hunt_types = active_hunt_types(row["hunt_type_counts_json"])
            if len(hunt_types) <= 1:
                continue
            source = safe_repo_path(row["source_pdf"])
            for hunt_type in hunt_types:
                target = target_for(source, hunt_type)
                subset = target.with_suffix(target.suffix + f".{hunt_type}.fragment.tmp.pdf")
                source_codes = codes_by_pdf.get(str(source), set())
                target_is_source = target == source
                target_codes = set() if target_is_source else codes_by_pdf.get(str(target), set())
                overlap = [] if target_is_source else sorted(source_codes & target_codes)
                rows.append(
                    {
                        "year": row["year"],
                        "action": "DRY_RUN",
                        "source_pdf": str(source),
                        "hunt_type": hunt_type,
                        "target_pdf": str(target),
                        "page_count": len(groups_by_pdf[str(source)][hunt_type]),
                        "target_exists": target.exists() and not target_is_source,
                        "target_is_source": target_is_source,
                        "overlap_hunt_codes": ",".join(overlap),
                        "target_backup_pdf": str(backup_dir / target.relative_to(REPO)),
                        "fragment_tmp_pdf": str(subset),
                    }
                )

    if args.apply:
        sources_to_move: set[Path] = set()
        self_target_rows: list[dict[str, object]] = []
        for row in rows:
            if row["overlap_hunt_codes"]:
                row["action"] = "SKIPPED_HUNT_CODE_OVERLAP"
                continue
            source = Path(str(row["source_pdf"]))
            target = Path(str(row["target_pdf"]))
            hunt_type = str(row["hunt_type"])
            page_indexes = groups_by_pdf[str(source)][hunt_type]
            fragment = Path(str(row["fragment_tmp_pdf"]))
            write_page_subset(source, fragment, page_indexes)
            if row["target_is_source"]:
                self_target_rows.append(row)
                row["action"] = "PENDING_REWRITE_SELF_TARGET"
                sources_to_move.add(source)
                continue
            if target.exists():
                backup = Path(str(row["target_backup_pdf"]))
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
                append_pdf(fragment, target)
                fragment.unlink()
                row["action"] = "MERGED_INTO_TARGET"
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                fragment.replace(target)
                row["action"] = "WROTE_TARGET"
            sources_to_move.add(source)

        for source in sorted(sources_to_move):
            if not source.exists():
                continue
            inactive = source.parent / "Parent Bundles" / source.name
            inactive.parent.mkdir(parents=True, exist_ok=True)
            if inactive.exists():
                inactive = source.parent / "Parent Bundles" / f"{source.stem}.mixed_hunt_type_parent_{stamp}{source.suffix}"
            source.replace(inactive)

        for row in self_target_rows:
            target = Path(str(row["target_pdf"]))
            fragment = Path(str(row["fragment_tmp_pdf"]))
            if not fragment.exists():
                row["action"] = "SKIPPED_FRAGMENT_MISSING"
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            fragment.replace(target)
            row["action"] = "WROTE_SELF_TARGET"

    output = AUDIT_ROOT / f"mixed_hunt_type_fragment_repair_{stamp}.csv"
    fields = [
        "year",
        "action",
        "source_pdf",
        "hunt_type",
        "target_pdf",
        "page_count",
        "target_exists",
        "target_is_source",
        "overlap_hunt_codes",
        "target_backup_pdf",
        "fragment_tmp_pdf",
    ]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    print(json.dumps({"apply": args.apply, "actions": len(rows), "output": str(output)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
