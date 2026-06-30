import csv
import re
from pathlib import Path


def _repo_root() -> Path:
    repo_root = Path(__file__).resolve()
    while repo_root.name != "HUNT-BUILDER" and repo_root.parent != repo_root:
        repo_root = repo_root.parent
    if repo_root.name != "HUNT-BUILDER":
        raise RuntimeError("Could not locate HUNT-BUILDER repo root")
    return repo_root
import warnings

from pypdf import PdfReader


REPO_ROOT = Path(str(_repo_root()))
CURATED_MANIFEST = REPO_ROOT / "pipeline" / "manifests" / "pdf_ingest_manifest_curated.csv"
OUTPUT_INDEX = REPO_ROOT / "pipeline" / "manifests" / "pdf_search_index.csv"


TAGS = {
    "draw_odds": [
        "draw odds",
        "drawing odds",
        "bonus point",
        "preference point",
        "draw result",
    ],
    "harvest_report": [
        "harvest",
        "hunter success",
        "annual report",
        "hunt statistics",
        "survey",
    ],
    "regulation": [
        "proclamation",
        "regulation",
        "rule",
        "season dates",
        "legal weapon",
        "bag limit",
    ],
    "application_guide": [
        "application",
        "apply",
        "deadline",
        "how to apply",
        "guidebook",
        "instructions",
    ],
}


def read_sample_text(pdf_path: Path, max_pages: int = 2) -> tuple[str, str]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            reader = PdfReader(str(pdf_path), strict=False)
        text_chunks = []
        for i, page in enumerate(reader.pages):
            if i >= max_pages:
                break
            try:
                text_chunks.append(page.extract_text() or "")
            except Exception:
                text_chunks.append("")
        return " ".join(text_chunks), "ok"
    except Exception:
        return "", "parse_error"


def classify(text: str, file_hint: str) -> str:
    corpus = f"{file_hint} {text}".lower()
    if "draw" in corpus and "odds" in corpus:
        return "draw_odds"
    if "harvest" in corpus:
        return "harvest_report"

    scores = {k: 0 for k in TAGS}
    for tag, keys in TAGS.items():
        for key in keys:
            if key in corpus:
                scores[tag] += 1

    best_tag = max(scores, key=scores.get)
    if scores[best_tag] == 0:
        return "other_hunt"
    return best_tag


def detect_species(text: str, file_hint: str) -> str:
    species_terms = [
        "deer",
        "elk",
        "bison",
        "pronghorn",
        "moose",
        "goat",
        "sheep",
        "turkey",
        "bear",
        "cougar",
    ]
    corpus = f"{file_hint} {text}".lower()
    found = [s for s in species_terms if re.search(rf"\\b{s}\\b", corpus)]
    if not found:
        return ""
    return ",".join(sorted(set(found)))


def main() -> None:
    rows = []
    with CURATED_MANIFEST.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if r.get("decision") != "keep":
                continue
            final_path = Path(r["final_path"])
            if not final_path.exists():
                continue

            sample_text, extraction_status = read_sample_text(final_path, max_pages=2)
            filename = final_path.name
            tag = classify(sample_text, filename)
            species = detect_species(sample_text, filename)

            search_blob = " ".join(
                [
                    filename,
                    r.get("classification", ""),
                    r.get("target_year_curated", ""),
                    tag,
                    species,
                    sample_text[:1000].replace("\n", " ").replace("\r", " "),
                ]
            )

            rows.append(
                {
                    "filename": filename,
                    "final_path": str(final_path),
                    "source_path": r.get("source_path", ""),
                    "target_year": r.get("target_year_curated", ""),
                    "initial_classification": r.get("classification", ""),
                    "doc_type": tag,
                    "species_tags": species,
                    "extraction_status": extraction_status,
                    "search_text": search_blob,
                }
            )

    OUTPUT_INDEX.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_INDEX.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "filename",
            "final_path",
            "source_path",
            "target_year",
            "initial_classification",
            "doc_type",
            "species_tags",
            "extraction_status",
            "search_text",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    counts = {}
    for row in rows:
        counts[row["doc_type"]] = counts.get(row["doc_type"], 0) + 1

    print(f"Indexed {len(rows)} PDFs -> {OUTPUT_INDEX}")
    for k in sorted(counts):
        print(f"{k}: {counts[k]}")


if __name__ == "__main__":
    main()
