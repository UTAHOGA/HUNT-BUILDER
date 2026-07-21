#!/usr/bin/env python3
"""Normalize active CWMU draw-odds PDFs into the CWMU folder.

The page-role audit can surface CWMU pages that were split out of broader
non-CWMU source PDFs. This script moves unique CWMU child PDFs into the CWMU
folder, moves fully redundant outside-CWMU children into an ignored evidence
folder, and creates unique-page repair PDFs for partial duplicates.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import fitz


REPO = Path(__file__).resolve().parents[1]
AUDIT_ROOT = REPO / "audits" / "draw_odds_cwmu_source_repair"


def is_cwmu_hunt_type(hunt_type: str) -> bool:
    return hunt_type.startswith("CWMU_")


def in_cwmu_folder(relative_path: str) -> bool:
    return "\\CWMU\\" in relative_path.upper()


def cwmu_target_folder(source: Path, hunt_type: str) -> Path:
    parts = list(source.parts)
    draw_index = next(i for i, part in enumerate(parts) if part.lower() == "draw_odds")
    draw_root = Path(*parts[: draw_index + 1])
    if hunt_type.startswith("CWMU_ANTLERLESS_") or hunt_type.startswith("CWMU_YOUTH_ANTLERLESS_"):
        return draw_root / "CWMU" / "ANTLERLESS CWMU"
    return draw_root / "CWMU" / "BIG GAME CWMU"


def inactive_target_folder(source: Path) -> Path:
    return source.parent / "Duplicate Active Sources"


def unique_target(path: Path) -> Path:
    if not path.exists():
        return path
    index = 2
    while True:
        candidate = path.with_name(f"{path.stem}__DUPLICATE_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def write_page_subset(source: Path, target: Path, page_numbers: list[int]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(source) as src:
        out = fitz.open()
        for page_number in page_numbers:
            page_index = page_number - 1
            out.insert_pdf(src, from_page=page_index, to_page=page_index)
        tmp = target.with_suffix(target.suffix + ".tmp")
        out.save(tmp)
        out.close()
    tmp.replace(target)


def parse_years(value: str) -> set[str]:
    years: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = [int(piece) for piece in part.split("-", 1)]
            years.extend(range(start, end + 1))
        else:
            years.append(int(part))
    return {str(year) for year in years}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page-audit", type=Path, required=True)
    parser.add_argument("--years", default="2017-2026")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    years = parse_years(args.years)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    output_dir = args.output_dir or AUDIT_ROOT / stamp
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = list(csv.DictReader(args.page_audit.open(newline="", encoding="utf-8")))
    folder_keys: dict[str, set[tuple[str, str]]] = defaultdict(set)
    outside_by_file: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)

    for row in rows:
        year = row["year"]
        if year not in years:
            continue
        hunt_type = row["hunt_type"]
        hunt_code = row["hunt_code"]
        if not hunt_code or not is_cwmu_hunt_type(hunt_type):
            continue
        key = (hunt_type, hunt_code)
        if in_cwmu_folder(row["source_pdf_relative"]):
            folder_keys[year].add(key)
        else:
            outside_by_file[(year, row["source_pdf"])].append(row)

    actions: list[dict[str, object]] = []
    for (year, source_pdf), file_rows in sorted(outside_by_file.items()):
        source = Path(source_pdf)
        if not source.exists():
            actions.append(
                {
                    "year": year,
                    "source_pdf": source_pdf,
                    "action": "SKIPPED_SOURCE_MISSING",
                    "reason": "SOURCE_FILE_NOT_FOUND",
                }
            )
            continue
        keys_by_row = {
            (row["hunt_type"], row["hunt_code"], int(row["page_number"])): row for row in file_rows
        }
        keys = {(hunt_type, hunt_code) for hunt_type, hunt_code, _page in keys_by_row}
        duplicated = keys & folder_keys[year]
        unique = keys - folder_keys[year]
        first_hunt_type = file_rows[0]["hunt_type"]

        if keys and not unique:
            target = unique_target(inactive_target_folder(source) / source.name)
            action = "WOULD_MOVE_FULL_DUPLICATE"
            if args.apply:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(target))
                action = "MOVED_FULL_DUPLICATE"
            actions.append(
                {
                    "year": year,
                    "source_pdf": source_pdf,
                    "target_pdf": str(target),
                    "action": action,
                    "cwmu_keys": len(keys),
                    "duplicated_keys": len(duplicated),
                    "unique_keys": 0,
                }
            )
            continue

        if not duplicated:
            target = unique_target(cwmu_target_folder(source, first_hunt_type) / source.name)
            action = "WOULD_MOVE_UNIQUE_TO_CWMU"
            if args.apply:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(target))
                action = "MOVED_UNIQUE_TO_CWMU"
            actions.append(
                {
                    "year": year,
                    "source_pdf": source_pdf,
                    "target_pdf": str(target),
                    "action": action,
                    "cwmu_keys": len(keys),
                    "duplicated_keys": 0,
                    "unique_keys": len(unique),
                }
            )
            continue

        unique_page_numbers = sorted(
            int(row["page_number"])
            for row in file_rows
            if (row["hunt_type"], row["hunt_code"]) in unique
        )
        target_name = f"{source.stem}__CWMU_UNIQUE_PAGES{source.suffix}"
        target = unique_target(cwmu_target_folder(source, first_hunt_type) / target_name)
        inactive_target = unique_target(inactive_target_folder(source) / source.name)
        action = "WOULD_REPAIR_UNIQUE_PAGES_AND_MOVE_ORIGINAL"
        if args.apply:
            write_page_subset(source, target, unique_page_numbers)
            inactive_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(inactive_target))
            action = "REPAIRED_UNIQUE_PAGES_AND_MOVED_ORIGINAL"
        actions.append(
            {
                "year": year,
                "source_pdf": source_pdf,
                "target_pdf": str(target),
                "inactive_original_pdf": str(inactive_target),
                "action": action,
                "cwmu_keys": len(keys),
                "duplicated_keys": len(duplicated),
                "unique_keys": len(unique),
                "unique_page_numbers": ",".join(str(page) for page in unique_page_numbers),
            }
        )

    fields = [
        "year",
        "source_pdf",
        "target_pdf",
        "inactive_original_pdf",
        "action",
        "reason",
        "cwmu_keys",
        "duplicated_keys",
        "unique_keys",
        "unique_page_numbers",
    ]
    with (output_dir / "cwmu_source_repair_actions.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(actions)

    status = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "apply": bool(args.apply),
        "actions": len(actions),
        "action_counts": dict(sorted({action["action"]: 0 for action in actions}.items())),
        "output_dir": str(output_dir),
    }
    counts: dict[str, int] = defaultdict(int)
    for action in actions:
        counts[str(action["action"])] += 1
    status["action_counts"] = dict(sorted(counts.items()))
    (output_dir / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(status, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
