import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BIBLE_ROOT = Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES")
OUT_DIR = ROOT / "processed_data" / "audits"
PLAN_CSV = OUT_DIR / "bible_hunt_code_file_name_normalization_plan.csv"
SUMMARY_JSON = OUT_DIR / "bible_hunt_code_file_name_normalization_summary.json"

TARGET_CATEGORIES = {
    "ANTLERLESS DRAW RESULTS",
    "BEAR DRAW RESULTS",
    "COUGAR DRAW RESULTS",
    "D.H. DEER DRAW RESULTS",
    "G.S. BUCK DEER DRAW RESULTS",
    "L.E. BIG GAME DRAW RESULTS",
    "L.E. DEER DRAW RESULTS",
    "L.E. ELK DRAW RESULTS",
    "L.E. PRONGHORN DRAW RESULTS",
    "LIFETIME G.S. DEER DRAW RESULTS",
    "O.I.L. BISON DRAW RESULTS",
    "O.I.L. BULL MOOSE DRAW RESULTS",
    "O.I.L. DESERT BIGHORN SHEEP DRAW RESULTS",
    "O.I.L. MTN GOAT DRAW RESULTS",
    "O.I.L. ROCKY MTN SHEEP DRAW RESULTS",
    "SPORTSMAN DRAW RESULTS",
    "TURKEY DRAW RESULTS",
    "YOUTH ANTLERLESS DRAW RESULTS",
    "YOUTH D.H. DEER DRAW RESULTS",
    "YOUTH ELK DRAW RESULTS",
    "YOUTH G.S. DEER DRAW RESULTS",
    "YOUTH TURKEY DRAW RESULTS",
    "HUNT EXPO DRAW RESULTS",
}


FIELDNAMES = [
    "year_folder",
    "draw_results_year",
    "model_year",
    "old_path",
    "old_name",
    "new_path",
    "new_name",
    "extension",
    "status",
    "action_taken",
    "category",
    "reason",
]


def norm_text(value: str) -> str:
    return re.sub(r"\s+", " ", unquote(value or "").replace("_", " ").replace("-", " ")).strip()


def norm_key(value: str) -> str:
    value = norm_text(value).upper()
    value = re.sub(r"\bOIL\b", "O.I.L.", value)
    value = re.sub(r"\bL E\b", "L.E.", value)
    value = re.sub(r"\bLE\b", "L.E.", value)
    value = re.sub(r"\bGS\b", "G.S.", value)
    value = re.sub(r"\bDH\b", "D.H.", value)
    value = value.replace("MTN.", "MTN")
    value = value.replace("MOUNTAIN", "MTN")
    value = value.replace("ROCKY MOUNTAIN", "ROCKY MTN")
    value = value.replace("BIGHORN", "BIGHORN")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def prefix(year: str) -> str:
    return f"{year}_PERMITS={int(year) + 1}_MODEL__"


def canonical_name(year: str, category: str, suffix: str) -> str:
    return f"{prefix(year)}{category}{suffix}"


def has_canonical_prefix(name: str, year: str) -> bool:
    return name.upper().startswith(prefix(year).upper())


def strip_canonical_prefix(name: str, year: str) -> str:
    stem = Path(name).stem
    if has_canonical_prefix(name, year):
        return stem[len(prefix(year)) :]
    return stem


def infer_category(path: Path, year: str) -> tuple[str, str]:
    name = path.name
    suffix = path.suffix.lower()
    key = norm_key(strip_canonical_prefix(name, year))
    raw_key = norm_key(Path(name).stem)

    if suffix == ".zip":
        if "NORMALIZED TO 2025 STYLE" in key or "NORMALIZED TO 2025 STYLE" in raw_key:
            return "NORMALIZED_TO_2025_STYLE", "normalized zip archive"
        if raw_key == year:
            return "", "plain year zip needs review"
        return "", "zip archive not normalized by this pass"
    if suffix not in {".pdf", ".csv", ".xlsx", ".md"}:
        return "", "extension not in normalization scope"

    exact_cleanup = {
        "L.E. DEER": "L.E. DEER DRAW RESULTS",
        "L.E. ELK": "L.E. ELK DRAW RESULTS",
        "L.E. PRONGHORN": "L.E. PRONGHORN DRAW RESULTS",
        "O.I.L. BISON": "O.I.L. BISON DRAW RESULTS",
        "O.I.L. BULL MOOSE": "O.I.L. BULL MOOSE DRAW RESULTS",
        "O.I.L. DESERT BIGHORN SHEEP": "O.I.L. DESERT BIGHORN SHEEP DRAW RESULTS",
        "O.I.L. MTN GOAT": "O.I.L. MTN GOAT DRAW RESULTS",
        "O.I.L. ROCKY MTN SHEEP": "O.I.L. ROCKY MTN SHEEP DRAW RESULTS",
        "YOUTH ELK DRAW RESULTS": "YOUTH ELK DRAW RESULTS",
        "YOUTH ELK": "YOUTH ELK DRAW RESULTS",
        "YOUTH G.S. DEER": "YOUTH G.S. DEER DRAW RESULTS",
        "YOUTH D.H. DEER": "YOUTH D.H. DEER DRAW RESULTS",
    }
    if key in exact_cleanup:
        return exact_cleanup[key], "canonical category cleanup"
    if key in {"FILE MANIFEST", "FILE NOTES"}:
        return key, "already canonical sidecar"
    if "FILE MANIFEST" in key:
        return "FILE MANIFEST", "manifest sidecar"
    if "FILE NOTES" in key:
        return "FILE NOTES", "notes sidecar"
    if has_canonical_prefix(name, year) and key.endswith("DRAW RESULTS"):
        return key, "already normalized naming structure with non-reference category"
    if key in TARGET_CATEGORIES:
        return key, "already canonical category"

    exact_legacy_names = {
        "19_DRAWING_ODDS": "BEAR DRAW RESULTS",
        "19 DRAWING ODDS": "BEAR DRAW RESULTS",
    }
    if raw_key in exact_legacy_names:
        return exact_legacy_names[raw_key], "exact legacy filename mapping"

    old_name_map = [
        (r"YOUTH.*ANTLERLESS", "YOUTH ANTLERLESS DRAW RESULTS"),
        (r"YOUTH.*BULL.*ELK|YOUTH.*ELK", "YOUTH ELK DRAW RESULTS"),
        (r"YOUTH.*D\.H\.|YOUTH.*DEDICATED.*HUNTER|YOUTH.*DH", "YOUTH D.H. DEER DRAW RESULTS"),
        (r"YOUTH.*TURKEY", "YOUTH TURKEY DRAW RESULTS"),
        (r"YOUTH.*DEER|YOUTH.*G\.S\.", "YOUTH G.S. DEER DRAW RESULTS"),
        (r"ANTLERLESS.*(ODDS|RESULT)", "ANTLERLESS DRAW RESULTS"),
        (r"BEAR|BLACK BEAR", "BEAR DRAW RESULTS"),
        (r"COUGAR", "COUGAR DRAW RESULTS"),
        (r"SPORTSMAN", "SPORTSMAN DRAW RESULTS"),
        (r"TURKEY", "TURKEY DRAW RESULTS"),
        (r"LIFETIME.*DEER", "LIFETIME G.S. DEER DRAW RESULTS"),
        (r"D\.H\.|DEDICATED.*HUNTER|DH ODDS", "D.H. DEER DRAW RESULTS"),
        (r"DEER ODDS|BUCK DEER|GENERAL.*SEASON.*DEER|G\.S\.", "G.S. BUCK DEER DRAW RESULTS"),
        (r"BG ODDS|BIG GAME|DRAWING ODDS", "L.E. BIG GAME DRAW RESULTS"),
    ]
    for pattern, category in old_name_map:
        if re.search(pattern, key) or re.search(pattern, raw_key):
            return category, "legacy name mapping"
    return "", "no category rule matched"


def target_for(path: Path, year: str) -> tuple[Path | None, str, str]:
    if "%" in path.name:
        decoded_name = unquote(path.name)
        if decoded_name != path.name and has_canonical_prefix(decoded_name, year):
            return path.with_name(decoded_name), "", "percent-encoded canonical filename cleanup"
    category, reason = infer_category(path, year)
    suffix = path.suffix
    if not category:
        return None, category, reason
    if reason == "already normalized naming structure with non-reference category":
        return path, category, reason
    if category == "NORMALIZED_TO_2025_STYLE":
        target = path.with_name(f"{prefix(year)}NORMALIZED_TO_2025_STYLE{suffix}")
    elif category in {"FILE MANIFEST", "FILE NOTES"}:
        target = path.with_name(canonical_name(year, category, suffix))
    else:
        target = path.with_name(canonical_name(year, category, suffix))
    return target, category, reason


def build_plan(bible_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for year_dir in sorted(p for p in bible_root.iterdir() if p.is_dir() and re.fullmatch(r"\d{4}", p.name)):
        year = year_dir.name
        for path in sorted(p for p in year_dir.iterdir() if p.is_file()):
            target, category, reason = target_for(path, year)
            model_year = str(int(year) + 1)
            if target is None:
                status = "REVIEW"
                action = "NO_ACTION"
                new_path = ""
                new_name = ""
            elif target.name == path.name:
                status = "ALREADY_NORMALIZED"
                action = "NO_ACTION"
                new_path = str(target)
                new_name = target.name
            elif target.exists():
                status = "REVIEW_TARGET_EXISTS"
                action = "NO_ACTION"
                new_path = str(target)
                new_name = target.name
            else:
                status = "READY_TO_RENAME"
                action = "PENDING"
                new_path = str(target)
                new_name = target.name
            rows.append(
                {
                    "year_folder": year,
                    "draw_results_year": year,
                    "model_year": model_year,
                    "old_path": str(path),
                    "old_name": path.name,
                    "new_path": new_path,
                    "new_name": new_name,
                    "extension": path.suffix.lower(),
                    "status": status,
                    "action_taken": action,
                    "category": category,
                    "reason": reason,
                }
            )
    target_counts = Counter(row["new_path"] for row in rows if row["status"] == "READY_TO_RENAME" and row["new_path"])
    for row in rows:
        if row["status"] == "READY_TO_RENAME" and target_counts[row["new_path"]] > 1:
            row["status"] = "REVIEW_DUPLICATE_TARGET_IN_PLAN"
            row["action_taken"] = "NO_ACTION"
            row["reason"] = f"{row['reason']}; duplicate target in rename plan"
    return rows


def apply_plan(rows: list[dict[str, str]], bible_root: Path) -> None:
    root_resolved = bible_root.resolve()
    for row in rows:
        if row["status"] != "READY_TO_RENAME":
            continue
        old_path = Path(row["old_path"]).resolve()
        new_path = Path(row["new_path"]).resolve()
        if root_resolved not in old_path.parents or root_resolved not in new_path.parents:
            row["action_taken"] = "BLOCKED_OUTSIDE_ROOT"
            continue
        if not old_path.exists():
            row["action_taken"] = "BLOCKED_OLD_MISSING"
            continue
        if new_path.exists():
            row["action_taken"] = "BLOCKED_TARGET_EXISTS"
            continue
        old_path.rename(new_path)
        row["action_taken"] = "RENAMED"


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize BIBLE HUNT CODES filenames to 2025-style names.")
    parser.add_argument("--bible-root", default=str(DEFAULT_BIBLE_ROOT))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--plan-csv", default=str(PLAN_CSV))
    parser.add_argument("--summary-json", default=str(SUMMARY_JSON))
    args = parser.parse_args()

    bible_root = Path(args.bible_root)
    rows = build_plan(bible_root)
    if args.apply:
        apply_plan(rows, bible_root)

    write_csv(Path(args.plan_csv), rows)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bible_root": str(bible_root),
        "apply": args.apply,
        "total_files_reviewed": len(rows),
        "status_counts": dict(sorted(Counter(row["status"] for row in rows).items())),
        "action_counts": dict(sorted(Counter(row["action_taken"] for row in rows).items())),
        "year_counts": dict(sorted(Counter(row["year_folder"] for row in rows).items())),
        "category_counts": dict(sorted(Counter(row["category"] for row in rows if row["category"]).items())),
        "outputs": {
            "plan_csv": str(Path(args.plan_csv).relative_to(ROOT)).replace("\\", "/") if Path(args.plan_csv).is_relative_to(ROOT) else args.plan_csv,
        },
    }
    Path(args.summary_json).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
