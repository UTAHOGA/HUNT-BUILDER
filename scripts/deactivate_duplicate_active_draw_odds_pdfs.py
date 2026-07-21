#!/usr/bin/env python3
"""Move exact duplicate active draw-odds PDFs into an ignored evidence folder."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import fitz


REPO = Path(__file__).resolve().parents[1]
PIPELINE_ROOT = REPO / "pipeline" / "RAW" / "hunt_unit_database"
AUDIT_ROOT = REPO / "audits" / "draw_odds_duplicate_active_sources"


IGNORED_PARTS = {
    "backup",
    "duplicate active sources",
    "parent bundles",
    "summary pages",
}

BROAD_SOURCE_MARKERS = (
    "ANTLERLESS_DRAW_RESULTS",
    "YOUTH_ANTLERLESS_DRAW_RESULTS",
    "L.E._BIG_GAME_DRAW_RESULTS",
    "L.E. BIG GAME DRAW RESULTS",
    "L.E._DRAW_RESULTS",
    "O.I.L._DRAW_RESULTS",
    "O.I.L. DRAW RESULTS",
)


def draw_odds_roots_for_year(year: int) -> list[Path]:
    year_dir = PIPELINE_ROOT / str(year)
    return [path for path in [year_dir / "pdf" / "draw_odds", year_dir / "draw_odds"] if path.exists()]


def parse_years(value: str) -> list[int]:
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
    return sorted(set(years))


def is_active_pdf(path: Path) -> bool:
    if path.suffix.lower() != ".pdf":
        return False
    name = path.name.lower()
    parts = {part.lower() for part in path.parts}
    if ".tmp" in name or "backup" in name:
        return False
    return not any(part in parts for part in IGNORED_PARTS)


def text_hash(path: Path) -> tuple[str, int]:
    with fitz.open(path) as doc:
        texts = []
        for page in doc:
            texts.append(" ".join((page.get_text("text") or "").split()))
        digest = hashlib.sha256("\n---PAGE---\n".join(texts).encode("utf-8", "ignore")).hexdigest()
        return digest, doc.page_count


def keep_score(path: Path) -> tuple[int, int, int, str]:
    rel = str(path.relative_to(REPO)).upper()
    in_split = "SPLIT BY HUNT TYPE" in rel
    broad = any(marker in rel for marker in BROAD_SOURCE_MARKERS)
    # Prefer original child files over generated split files, then species/class-specific split files over broad-parent splits.
    return (
        0 if not in_split else 1,
        1 if broad else 0,
        len(path.parts),
        str(path),
    )


def unique_target(path: Path, target_dir: Path) -> Path:
    target = target_dir / path.name
    if not target.exists():
        return target
    stem = path.stem
    suffix = path.suffix
    index = 2
    while True:
        candidate = target_dir / f"{stem}__DUPLICATE_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", default="2017-2026")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--apply", action="store_true", help="Move redundant exact duplicates. Otherwise audit only.")
    args = parser.parse_args()

    years = parse_years(args.years)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    output_dir = args.output_dir or AUDIT_ROOT / stamp
    output_dir.mkdir(parents=True, exist_ok=True)

    inventory: list[dict[str, object]] = []
    for year in years:
        for root in draw_odds_roots_for_year(year):
            for path in sorted(root.rglob("*.pdf")):
                if not is_active_pdf(path):
                    continue
                digest, page_count = text_hash(path)
                inventory.append(
                    {
                        "year": year,
                        "text_sha256": digest,
                        "page_count": page_count,
                        "source_pdf": str(path),
                        "source_pdf_relative": str(path.relative_to(REPO)),
                    }
                )

    by_key: dict[tuple[int, str], list[dict[str, object]]] = defaultdict(list)
    for row in inventory:
        by_key[(int(row["year"]), str(row["text_sha256"]))].append(row)

    actions: list[dict[str, object]] = []
    for (year, digest), rows in sorted(by_key.items()):
        if len(rows) <= 1:
            continue
        ordered = sorted(rows, key=lambda row: keep_score(Path(str(row["source_pdf"]))))
        keep = ordered[0]
        for row in ordered[1:]:
            source = Path(str(row["source_pdf"]))
            target_dir = source.parent / "Duplicate Active Sources"
            target = unique_target(source, target_dir)
            action = {
                "year": year,
                "text_sha256": digest,
                "group_size": len(rows),
                "kept_pdf": keep["source_pdf"],
                "moved_pdf": str(source),
                "duplicate_target_pdf": str(target),
                "action": "WOULD_MOVE_DUPLICATE",
            }
            if args.apply:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(target))
                action["action"] = "MOVED_DUPLICATE"
            actions.append(action)

    fields = [
        "year",
        "text_sha256",
        "group_size",
        "kept_pdf",
        "moved_pdf",
        "duplicate_target_pdf",
        "action",
    ]
    with (output_dir / "duplicate_active_source_actions.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(actions)

    status = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "years": years,
        "apply": bool(args.apply),
        "active_pdfs_scanned": len(inventory),
        "duplicate_groups": sum(1 for rows in by_key.values() if len(rows) > 1),
        "duplicate_pdf_actions": len(actions),
        "output_dir": str(output_dir),
    }
    (output_dir / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(status, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
