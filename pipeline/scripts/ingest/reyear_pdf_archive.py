import csv
import hashlib
import re
import shutil
from pathlib import Path


def _repo_root() -> Path:
    repo_root = Path(__file__).resolve()
    while repo_root.name != "HUNT-BUILDER" and repo_root.parent != repo_root:
        repo_root = repo_root.parent
    if repo_root.name != "HUNT-BUILDER":
        raise RuntimeError("Could not locate HUNT-BUILDER repo root")
    return repo_root


REPO = Path(str(_repo_root()))
RAW_ROOT = REPO / "pipeline" / "RAW" / "hunt_unit_database"
MANIFEST_DIR = REPO / "pipeline" / "manifests"
OUT_MANIFEST = MANIFEST_DIR / "pdf_reyear_manifest.csv"
OUT_AMBIG = MANIFEST_DIR / "pdf_reyear_ambiguous.csv"


DOC_KEYWORDS = {
    "draw_odds": ["draw", "odds", "draw-results", "draw results"],
    "harvest_report": ["harvest", r"\bhr\b", "hunter success", "annual report"],
    "regulation": ["proclamation", "regulation", "rule", "bag limit", "season dates", "legal weapon"],
}


def sha1(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def strip_hash_prefix(name: str) -> str:
    return re.sub(r"^[0-9a-f]{8}__", "", name, flags=re.IGNORECASE)


def classify(doc_path: Path) -> str:
    parts = [p.lower() for p in doc_path.parts]
    joined = " ".join(parts)
    # Folder hints first
    if any(x in parts for x in ["draw_odds", "odds"]):
        return "draw_odds"
    if any(x in parts for x in ["harvest", "harvest_report"]):
        return "harvest_report"
    if "regulation" in parts:
        return "regulation"
    # Fallback by keywords
    for doc_type, keys in DOC_KEYWORDS.items():
        for k in keys:
            if re.search(k, joined):
                return doc_type
    return "other_hunt"


def extract_year_candidates(text: str) -> list[int]:
    years = [int(m.group(1)) for m in re.finditer(r"(20\d{2})", text)]
    return [y for y in years if 2000 <= y <= 2035]


def determine_publish_year(doc_path: Path, doc_type: str) -> tuple[str, str]:
    # High-confidence: year in original filename
    original_name = strip_hash_prefix(doc_path.name)
    y_file = extract_year_candidates(original_name)
    if y_file:
        return str(max(y_file)), "filename_year"

    # Medium-confidence: year in full source-like path
    y_path = extract_year_candidates(str(doc_path))
    if y_path:
        return str(max(y_path)), "path_year"

    # Low-confidence fallback for legacy harvest placement:
    # historical ingest placed harvest in previous-year folder.
    year_folder = doc_path.parts[-4] if len(doc_path.parts) >= 4 else "unknown"
    if year_folder.isdigit():
        yf = int(year_folder)
        if doc_type == "harvest_report":
            return str(yf + 1), "legacy_harvest_folder_plus_one"
        return str(yf), "folder_year_fallback"

    return "unknown", "no_year_signal"


def model_target_year(publish_year: str, doc_type: str) -> tuple[str, str]:
    if not publish_year.isdigit():
        return "unknown", "unknown_publish_year"
    y = int(publish_year)
    if doc_type == "draw_odds":
        return str(y + 1), "draw_results_to_next_year"
    if doc_type == "harvest_report":
        return str(y), "harvest_hr_applies_to_report_year"
    if doc_type == "regulation":
        return str(y), "regulation_same_year"
    return str(y), "default_same_year"


def main() -> None:
    pdfs = [
        p
        for p in RAW_ROOT.rglob("*.pdf")
        if "_staging" not in p.parts and "_quarantine" not in p.parts
    ]

    hash_index: dict[str, Path] = {}
    for p in pdfs:
        try:
            hash_index.setdefault(sha1(p), p)
        except Exception:
            continue

    move_rows: list[dict[str, str]] = []
    ambiguous_rows: list[dict[str, str]] = []

    moved = 0
    dup_removed = 0
    unchanged = 0

    for p in sorted(pdfs):
        doc_type = classify(p)
        publish_year, year_method = determine_publish_year(p, doc_type)
        target_year, target_rule = model_target_year(publish_year, doc_type)

        confidence = "high" if year_method == "filename_year" else "medium" if year_method == "path_year" else "low"
        if publish_year == "unknown":
            confidence = "unknown"

        dest_year = publish_year if publish_year.isdigit() else "unknown"
        dest_dir = RAW_ROOT / dest_year / "pdf" / doc_type
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / p.name

        action = "unchanged"
        duplicate_of = ""

        if p.resolve() != dest_path.resolve():
            try:
                src_hash = sha1(p)
                existing_same_hash = hash_index.get(src_hash)
                if existing_same_hash and existing_same_hash.resolve() != p.resolve() and existing_same_hash.resolve() == dest_path.resolve():
                    p.unlink(missing_ok=True)
                    action = "removed_duplicate"
                    duplicate_of = str(dest_path)
                    dup_removed += 1
                elif dest_path.exists():
                    try:
                        dst_hash = sha1(dest_path)
                    except Exception:
                        dst_hash = ""
                    if src_hash and dst_hash and src_hash == dst_hash:
                        p.unlink(missing_ok=True)
                        action = "removed_duplicate"
                        duplicate_of = str(dest_path)
                        dup_removed += 1
                    else:
                        alt_path = dest_dir / f"{p.stem}__reyear{p.suffix}"
                        shutil.move(str(p), str(alt_path))
                        action = "moved_renamed"
                        dest_path = alt_path
                        moved += 1
                else:
                    shutil.move(str(p), str(dest_path))
                    action = "moved"
                    moved += 1
            except Exception:
                action = "error"
        else:
            unchanged += 1

        row = {
            "original_path": str(p),
            "final_path": str(dest_path),
            "doc_type": doc_type,
            "publish_year": publish_year,
            "model_target_year": target_year,
            "year_method": year_method,
            "model_target_rule": target_rule,
            "confidence": confidence,
            "action": action,
            "duplicate_of": duplicate_of,
        }
        move_rows.append(row)
        if confidence in {"low", "unknown"}:
            ambiguous_rows.append(row)

    with OUT_MANIFEST.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "original_path",
                "final_path",
                "doc_type",
                "publish_year",
                "model_target_year",
                "year_method",
                "model_target_rule",
                "confidence",
                "action",
                "duplicate_of",
            ],
        )
        w.writeheader()
        w.writerows(move_rows)

    with OUT_AMBIG.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "original_path",
                "final_path",
                "doc_type",
                "publish_year",
                "model_target_year",
                "year_method",
                "model_target_rule",
                "confidence",
                "action",
                "duplicate_of",
            ],
        )
        w.writeheader()
        w.writerows(ambiguous_rows)

    print(f"TOTAL={len(move_rows)}")
    print(f"MOVED={moved}")
    print(f"DUP_REMOVED={dup_removed}")
    print(f"UNCHANGED={unchanged}")
    print(f"AMBIGUOUS={len(ambiguous_rows)}")
    print(f"MANIFEST={OUT_MANIFEST}")
    print(f"AMBIG={OUT_AMBIG}")


if __name__ == "__main__":
    main()
