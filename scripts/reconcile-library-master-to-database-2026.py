#!/usr/bin/env python3
"""Reconcile the hard-copy library master against the 2026 DATABASE.csv truth source.

This does not promote the library master to truth. It writes a database-enriched
candidate and issue report so unmatched catalog rows stay visible.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path


def _repo_root() -> Path:
    repo_root = Path(__file__).resolve()
    while repo_root.name != "HUNT-BUILDER" and repo_root.parent != repo_root:
        repo_root = repo_root.parent
    if repo_root.name != "HUNT-BUILDER":
        raise RuntimeError("Could not locate HUNT-BUILDER repo root")
    return repo_root


ROOT = Path(__file__).resolve().parents[1]
TRUTH_DATABASE = Path(str(_repo_root() / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"))
LIBRARY_MASTER = ROOT / "pipeline/RAW/hunt_unit_database/library-master.csv"
LIBRARY_MASTER_JSON = ROOT / "pipeline/RAW/hunt_unit_database/library-master.json"
PUBLIC_DOCUMENTS = ROOT / "public/hard-copy/data/documents.json"
HARD_COPY_DIR = ROOT / "hard-copy"

OUT_CSV = ROOT / "processed_data/library_master_database_reconciliation.csv"
OUT_JSON = ROOT / "processed_data/library_master_database_reconciliation_summary.json"
OUT_MD = ROOT / "processed_data/library_master_database_reconciliation.md"
OUT_ENRICHED_CSV = ROOT / "pipeline/RAW/hunt_unit_database/library-master.reconciled.csv"
OUT_ENRICHED_JSON = ROOT / "pipeline/RAW/hunt_unit_database/library-master.reconciled.json"

RECON_FIELDS = [
    "record_id",
    "record_type",
    "library_title",
    "library_species",
    "library_category",
    "library_area",
    "library_condition",
    "library_source_pdf",
    "document_file_status",
    "database_match_status",
    "database_hunt_code",
    "database_hunt_name",
    "database_species",
    "database_hunt_type",
    "database_season",
    "database_permits_2026_res",
    "database_permits_2026_nr",
    "database_permits_2026_total",
    "database_permits_2026_source",
    "database_permit_allotment_2026_status",
    "reconciliation_issue",
]

DB_FIELDS = [
    "hunt_code",
    "hunt_name",
    "sex_type",
    "species",
    "weapon",
    "hunt_type",
    "season",
    "permits_2026_res",
    "permits_2026_nr",
    "permits_2026_total",
    "permits_2026_source",
    "permit_allotment_2026_res",
    "permit_allotment_2026_nr",
    "permit_allotment_2026_total",
    "permit_allotment_2026_source",
    "permit_allotment_2026_source_file",
    "permit_allotment_2026_status",
]


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [{k: (v or "").strip() for k, v in row.items()} for row in reader]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in fieldnames} for row in rows])


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize(value: str) -> str:
    text = value.lower().replace("&", " and ")
    text = re.sub(r"\b(mtns?|mountains?)\b", "mountain", text)
    text = re.sub(r"\bmt\b", "mountain", text)
    text = re.sub(r"\bcentral mtns\b", "central mountain", text)
    text = re.sub(r"\bsouth slope,\s*", "", text)
    text = re.sub(r"\bplateau,\s*", "", text)
    text = re.sub(r"\bprivate lands? only\b", "", text)
    text = re.sub(r"\bconservation\b", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def token_set(value: str) -> set[str]:
    stop = {"the", "and", "only", "permit", "permits", "multiseason", "limited", "entry"}
    return {token for token in normalize(value).split() if token and token not in stop}


def species_key(value: str) -> str:
    text = normalize(value)
    replacements = {
        "antlerless deer": "deer",
        "buck deer": "deer",
        "bull elk": "elk",
        "antlerless elk": "elk",
        "cow elk": "elk",
        "buck pronghorn": "pronghorn",
        "doe pronghorn": "pronghorn",
        "bull moose": "moose",
        "cow moose": "moose",
        "desert bighorn ram": "desert bighorn sheep",
        "rocky mountain bighorn ram": "rocky mountain bighorn sheep",
        "rocky mountain bighorn ewe": "rocky mountain bighorn sheep",
        "wild bearded turkey": "turkey",
        "wild turkey": "turkey",
    }
    return replacements.get(text, text)


def document_status(row: dict[str, str]) -> str:
    path_text = row.get("source_repo_path") or row.get("file_path") or ""
    if not path_text or path_text.startswith("TBD:"):
        return "MISSING_SOURCE_PATH"
    path = ROOT / path_text.lstrip("/")
    return "FOUND" if path.exists() else "MISSING_FILE"


def best_database_match(row: dict[str, str], db_rows: list[dict[str, str]]) -> tuple[str, dict[str, str] | None, str]:
    if row.get("record_type") == "document":
        return "DOCUMENT_ROW_NOT_HUNT_CODED", None, ""

    species = row.get("species", "")
    area = row.get("area", "")
    condition = row.get("condition", "")
    wanted_tokens = token_set(" ".join([area, condition]))
    candidates = [db for db in db_rows if species_key(db.get("species", "")) == species_key(species)]
    if row.get("category") == "Conservation Permits":
        conservation_candidates = [db for db in candidates if "conservation" in normalize(db.get("hunt_type", ""))]
        if conservation_candidates:
            candidates = conservation_candidates

    scored: list[tuple[float, dict[str, str]]] = []
    for db in candidates:
        candidate_tokens = token_set(" ".join([db.get("hunt_name", ""), db.get("hunt_type", ""), db.get("weapon", "")]))
        overlap = len(wanted_tokens & candidate_tokens)
        union = len(wanted_tokens | candidate_tokens) or 1
        score = overlap / union
        if overlap:
            scored.append((score, db))

    if not scored:
        return "NO_DATABASE_MATCH", None, "No same-species DATABASE.csv row shared area/condition tokens."

    scored.sort(key=lambda item: (-item[0], item[1].get("hunt_code", "")))
    best_score, best = scored[0]
    tied = [db for score, db in scored if score == best_score]
    if best_score >= 0.80 and len(tied) == 1:
        return "MATCH_HIGH", best, ""
    if best_score >= 0.45 and len(tied) == 1:
        return "MATCH_REVIEW", best, f"Fuzzy match score {best_score:.2f}; owner review required."
    return "AMBIGUOUS_DATABASE_MATCH", best, f"Best fuzzy match score {best_score:.2f}; tied/weak candidates require review."


def public_document_ids() -> set[str]:
    if not PUBLIC_DOCUMENTS.exists():
        return set()
    docs = json.loads(PUBLIC_DOCUMENTS.read_text(encoding="utf-8-sig"))
    if not isinstance(docs, list):
        return set()
    return {str(doc.get("databaseRecordId") or doc.get("id") or "") for doc in docs}


def main() -> None:
    if not TRUTH_DATABASE.exists():
        raise SystemExit(f"Missing truth database: {TRUTH_DATABASE}")
    library_headers, library_rows = read_csv(LIBRARY_MASTER)
    _, db_rows = read_csv(TRUTH_DATABASE)
    db_by_code = {row["hunt_code"]: row for row in db_rows if row.get("hunt_code")}
    if len(db_by_code) != len(db_rows):
        raise SystemExit("DATABASE.csv contains duplicate or blank hunt_code rows")

    public_ids = public_document_ids()
    recon_rows: list[dict[str, str]] = []
    enriched_rows: list[dict[str, str]] = []

    for row in library_rows:
        status, match, issue = best_database_match(row, db_rows)
        doc_status = document_status(row) if row.get("record_type") == "document" else ""
        if row.get("record_type") == "document" and row.get("public_visible").lower() == "true":
            rid = row.get("record_id", "")
            public_key = rid[4:].replace("_", "-") if rid.startswith("doc_") else rid
            if rid not in public_ids and public_key not in public_ids:
                issue = "Public document row is not present in public/hard-copy/data/documents.json"

        recon = {
            "record_id": row.get("record_id", ""),
            "record_type": row.get("record_type", ""),
            "library_title": row.get("title", ""),
            "library_species": row.get("species", ""),
            "library_category": row.get("category", ""),
            "library_area": row.get("area", ""),
            "library_condition": row.get("condition", ""),
            "library_source_pdf": row.get("source_pdf", ""),
            "document_file_status": doc_status,
            "database_match_status": status,
            "database_hunt_code": match.get("hunt_code", "") if match else "",
            "database_hunt_name": match.get("hunt_name", "") if match else "",
            "database_species": match.get("species", "") if match else "",
            "database_hunt_type": match.get("hunt_type", "") if match else "",
            "database_season": match.get("season", "") if match else "",
            "database_permits_2026_res": match.get("permits_2026_res", "") if match else "",
            "database_permits_2026_nr": match.get("permits_2026_nr", "") if match else "",
            "database_permits_2026_total": match.get("permits_2026_total", "") if match else "",
            "database_permits_2026_source": match.get("permits_2026_source", "") if match else "",
            "database_permit_allotment_2026_status": match.get("permit_allotment_2026_status", "") if match else "",
            "reconciliation_issue": issue,
        }
        recon_rows.append(recon)

        enriched = dict(row)
        for field in DB_FIELDS:
            enriched[f"database_{field}"] = match.get(field, "") if match else ""
        enriched["database_match_status"] = status
        enriched["document_file_status"] = doc_status
        enriched["reconciliation_issue"] = issue
        enriched_rows.append(enriched)

    enriched_headers = library_headers + [f"database_{field}" for field in DB_FIELDS] + [
        "database_match_status",
        "document_file_status",
        "reconciliation_issue",
    ]
    write_csv(OUT_CSV, RECON_FIELDS, recon_rows)
    write_csv(OUT_ENRICHED_CSV, enriched_headers, enriched_rows)

    json_payload = {
        "schema_version": "library_master_reconciled_v1",
        "source_library_master": "pipeline/RAW/hunt_unit_database/library-master.csv",
        "source_database_truth": str(TRUTH_DATABASE),
        "record_count": len(enriched_rows),
        "records": enriched_rows,
    }
    write_json(OUT_ENRICHED_JSON, json_payload)

    status_counts = Counter(row["database_match_status"] for row in recon_rows)
    type_counts = Counter(row["record_type"] for row in recon_rows)
    doc_status_counts = Counter(row["document_file_status"] for row in recon_rows if row["document_file_status"])
    blocker_statuses = {"NO_DATABASE_MATCH", "AMBIGUOUS_DATABASE_MATCH"}
    blocker_count = sum(count for status, count in status_counts.items() if status in blocker_statuses)
    missing_doc_count = sum(count for status, count in doc_status_counts.items() if status != "FOUND")

    summary = {
        "artifact": "library_master_database_reconciliation",
        "status": "REVIEW_REQUIRED" if blocker_count or missing_doc_count else "RECONCILED",
        "library_record_count": len(library_rows),
        "database_record_count": len(db_rows),
        "database_unique_hunt_codes": len(db_by_code),
        "record_type_counts": dict(sorted(type_counts.items())),
        "database_match_status_counts": dict(sorted(status_counts.items())),
        "document_file_status_counts": dict(sorted(doc_status_counts.items())),
        "database_match_blocker_count": blocker_count,
        "missing_document_file_count": missing_doc_count,
        "hard_copy_file_count": len(list(HARD_COPY_DIR.rglob("*"))) if HARD_COPY_DIR.exists() else 0,
        "outputs": {
            "reconciliation_csv": str(OUT_CSV.relative_to(ROOT)).replace("\\", "/"),
            "reconciled_library_csv": str(OUT_ENRICHED_CSV.relative_to(ROOT)).replace("\\", "/"),
            "reconciled_library_json": str(OUT_ENRICHED_JSON.relative_to(ROOT)).replace("\\", "/"),
        },
        "notes": [
            "DATABASE.csv is used as the current hunt-code and permit-allocation authority.",
            "library-master remains a candidate catalog until REVIEW_REQUIRED rows are resolved.",
            "Fuzzy database matches are intentionally not promoted without review.",
        ],
    }
    write_json(OUT_JSON, summary)

    lines = [
        "# Library Master vs 2026 DATABASE Reconciliation",
        "",
        f"- Status: `{summary['status']}`",
        f"- Library rows: `{summary['library_record_count']}`",
        f"- DATABASE rows: `{summary['database_record_count']}`",
        f"- DATABASE unique hunt codes: `{summary['database_unique_hunt_codes']}`",
        f"- Database match blockers: `{summary['database_match_blocker_count']}`",
        f"- Missing document file issues: `{summary['missing_document_file_count']}`",
        "",
        "## Match Status Counts",
        "",
    ]
    for status, count in sorted(status_counts.items()):
        lines.append(f"- `{status}`: `{count}`")
    lines.extend(["", "## Document File Status Counts", ""])
    for status, count in sorted(doc_status_counts.items()):
        lines.append(f"- `{status}`: `{count}`")
    lines.extend(["", "The reconciled library candidate is not promoted automatically; review-required rows remain flagged."])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
