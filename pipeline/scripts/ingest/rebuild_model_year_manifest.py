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


REPO = Path(str(_repo_root()))
RAW_ROOT = REPO / "pipeline" / "RAW" / "hunt_unit_database"
OUT = REPO / "pipeline" / "manifests" / "pdf_model_ready_manifest_with_target_year_v3.csv"


def infer_doc_type(path: Path) -> str:
    blob = f"{path.name} {path}".lower()
    if re.search(r"draw[-_ ]?odds|drawing[-_ ]?odds|draw[-_ ]?results?|\bodds\b|successful[_ -]?applicants", blob):
        return "draw_odds"
    if re.search(r"harvest|\bhr\b|hunter success", blob):
        return "harvest_report"
    if re.search(r"proclamation|regulation|bag limit|season dates|legal weapon|\brule\b", blob):
        return "regulation"
    return "other_hunt"


def infer_publish_year(path: Path) -> str:
    # source of truth is the year folder under pipeline/RAW/hunt_unit_database
    parts = path.parts
    try:
        i = parts.index("raw")
        y = parts[i + 1]
        if re.fullmatch(r"20\d{2}", y):
            return y
    except Exception:
        pass
    return "unknown"


def model_target_year(publish_year: str, doc_type: str) -> str:
    if not publish_year.isdigit():
        return "unknown"
    y = int(publish_year)
    if doc_type == "draw_odds":
        return str(y + 1)
    if doc_type == "harvest_report":
        return str(y)
    if doc_type == "regulation":
        return str(y)
    return str(y)


def main() -> None:
    files = [
        p
        for p in RAW_ROOT.rglob("*.pdf")
        if "_quarantine" not in p.parts and "_staging" not in p.parts
    ]
    rows = []
    for p in files:
        doc = infer_doc_type(p)
        if doc not in {"draw_odds", "harvest_report", "regulation"}:
            continue
        pub = infer_publish_year(p)
        target = model_target_year(pub, doc)
        rule = (
            "draw_results_to_next_year"
            if doc == "draw_odds"
            else "harvest_hr_applies_to_report_year"
            if doc == "harvest_report"
            else "regulation_same_year"
        )
        rows.append(
            {
                "filename": p.name,
                "final_path": str(p),
                "doc_type": doc,
                "publish_year": pub,
                "model_target_year": target,
                "target_year_rule": rule,
            }
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "filename",
                "final_path",
                "doc_type",
                "publish_year",
                "model_target_year",
                "target_year_rule",
            ],
        )
        w.writeheader()
        w.writerows(rows)

    print(f"ROWS={len(rows)}")
    print(f"OUT={OUT}")


if __name__ == "__main__":
    main()
