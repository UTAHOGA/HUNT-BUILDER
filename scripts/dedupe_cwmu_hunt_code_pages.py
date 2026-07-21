#!/usr/bin/env python3
"""Deduplicate active CWMU pages by year, hunt_type, and hunt_code."""

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
AUDIT_ROOT = REPO / "audits" / "draw_odds_cwmu_hunt_code_dedupe"

BROAD_MARKERS = (
    "ANTLERLESS_DRAW_RESULTS",
    "YOUTH_ANTLERLESS_DRAW_RESULTS",
    "L.E._BIG_GAME_DRAW_RESULTS",
    "L.E. BIG GAME DRAW RESULTS",
    "O.I.L._DRAW_RESULTS",
    "O.I.L. DRAW RESULTS",
)


def is_cwmu_hunt_type(hunt_type: str) -> bool:
    return hunt_type.startswith("CWMU_")


def in_cwmu_folder(relative_path: str) -> bool:
    return "\\CWMU\\" in relative_path.upper()


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


def source_rank(row: dict[str, str]) -> tuple[int, int, int, int, str]:
    rel = row["source_pdf_relative"].upper()
    source_name = Path(row["source_pdf_relative"]).name.upper()
    hunt_type = row["hunt_type"].upper()
    in_cwmu = in_cwmu_folder(row["source_pdf_relative"])
    in_split = "SPLIT BY HUNT TYPE" in rel
    broad = any(marker in rel for marker in BROAD_MARKERS)
    type_hint = hunt_type in source_name
    return (
        0 if in_cwmu else 1,
        0 if not broad else 1,
        0 if not in_split else 1,
        0 if type_hint else 1,
        row["source_pdf_relative"],
    )


def unique_target(path: Path) -> Path:
    if not path.exists():
        return path
    index = 2
    while True:
        candidate = path.with_name(f"{path.stem}__DUPLICATE_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def inactive_target(source: Path) -> Path:
    return unique_target(source.parent / "Duplicate Active Sources" / source.name)


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

    rows = [
        row
        for row in csv.DictReader(args.page_audit.open(newline="", encoding="utf-8"))
        if row["year"] in years and row["hunt_code"] and is_cwmu_hunt_type(row["hunt_type"])
    ]

    by_key: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_key[(row["year"], row["hunt_type"], row["hunt_code"])].append(row)

    winning_page_ids: set[tuple[str, int]] = set()
    duplicate_keys = 0
    for key_rows in by_key.values():
        winner = sorted(key_rows, key=source_rank)[0]
        winning_page_ids.add((winner["source_pdf"], int(winner["page_number"])))
        if len(key_rows) > 1:
            duplicate_keys += 1

    by_source: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_source[row["source_pdf"]].append(row)

    actions: list[dict[str, object]] = []
    for source_pdf, source_rows in sorted(by_source.items()):
        source = Path(source_pdf)
        if not source.exists():
            continue
        all_pages = sorted({int(row["page_number"]) for row in source_rows})
        kept_pages = sorted(
            {
                int(row["page_number"])
                for row in source_rows
                if (row["source_pdf"], int(row["page_number"])) in winning_page_ids
            }
        )
        if kept_pages == all_pages:
            continue
        target = inactive_target(source)
        if not kept_pages:
            action = "WOULD_MOVE_ALL_DUPLICATE_CWMU_PAGES"
            if args.apply:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(target))
                action = "MOVED_ALL_DUPLICATE_CWMU_PAGES"
            actions.append(
                {
                    "source_pdf": source_pdf,
                    "target_pdf": str(target),
                    "action": action,
                    "source_cwmu_pages": len(all_pages),
                    "kept_cwmu_pages": 0,
                    "removed_cwmu_pages": len(all_pages),
                }
            )
            continue

        repaired = unique_target(source.with_name(f"{source.stem}__CWMU_DEDUPED{source.suffix}"))
        action = "WOULD_WRITE_DEDUPED_PDF_AND_MOVE_ORIGINAL"
        if args.apply:
            write_page_subset(source, repaired, kept_pages)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
            action = "WROTE_DEDUPED_PDF_AND_MOVED_ORIGINAL"
        actions.append(
            {
                "source_pdf": source_pdf,
                "target_pdf": str(repaired),
                "inactive_original_pdf": str(target),
                "action": action,
                "source_cwmu_pages": len(all_pages),
                "kept_cwmu_pages": len(kept_pages),
                "removed_cwmu_pages": len(all_pages) - len(kept_pages),
                "kept_page_numbers": ",".join(str(page) for page in kept_pages),
            }
        )

    fields = [
        "source_pdf",
        "target_pdf",
        "inactive_original_pdf",
        "action",
        "source_cwmu_pages",
        "kept_cwmu_pages",
        "removed_cwmu_pages",
        "kept_page_numbers",
    ]
    with (output_dir / "cwmu_hunt_code_dedupe_actions.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(actions)

    counts: dict[str, int] = defaultdict(int)
    for action in actions:
        counts[str(action["action"])] += 1
    status = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "apply": bool(args.apply),
        "cwmu_rows": len(rows),
        "cwmu_unique_keys": len(by_key),
        "duplicate_cwmu_keys": duplicate_keys,
        "actions": len(actions),
        "action_counts": dict(sorted(counts.items())),
        "output_dir": str(output_dir),
    }
    (output_dir / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(status, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
