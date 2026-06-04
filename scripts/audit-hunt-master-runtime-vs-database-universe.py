from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
ACTIVE_RECON = ROOT / "processed_data" / "audits" / "current_2026_hunt_code_permit_reconciliation.csv"
RETIRED_CODES = ROOT / "processed_data" / "audits" / "reviewed_retired_hunt_codes_2026.csv"

SOURCE_FILES = [
    ("DATABASE.csv", DATABASE, "truth_current_database"),
    ("active_current_reconciliation", ACTIVE_RECON, "active_current_permit_union"),
    (
        "builder_runtime_foundation_json",
        ROOT / "data" / "hunt-master-canonical-2026-foundation.json",
        "active_builder_first_load",
    ),
    (
        "builder_runtime_source_of_truth_json",
        ROOT / "data" / "hunt-master-canonical-2026-source-of-truth.json",
        "builder_second_candidate_not_reached_if_foundation_loads",
    ),
    (
        "processed_source_of_truth_json",
        ROOT / "processed_data" / "hunt-master-canonical-2026-source-of-truth.json",
        "processed_reference",
    ),
    (
        "processed_source_of_truth_csv",
        ROOT / "processed_data" / "hunt-master-canonical-2026-source-of-truth.csv",
        "processed_reference",
    ),
    (
        "hard_copy_canonical_current_hunts",
        ROOT / "processed_data" / "library" / "canonical_current_hunts_2026.csv",
        "hard_copy_public_reference",
    ),
    (
        "hunt_research_summary_json",
        ROOT / "processed_data" / "hunt_research_2026_summary.json",
        "research_summary_contract",
    ),
    (
        "hunt_research_index_json",
        ROOT / "processed_data" / "hunt_research_2026_split" / "hunt_research_2026.index.json",
        "research_split_index",
    ),
    (
        "dwr_hanumber_pull",
        ROOT / "processed_data" / "dwr_huntplanner_hanumber_2026.csv",
        "dwr_popup_pull",
    ),
    (
        "live_hunttable_comparison",
        ROOT
        / "data_truth"
        / "crosswalk_truth"
        / "validation"
        / "live_dwr_permit_numbers_comprehensive_vs_DATABASE_2026.csv",
        "dwr_hunttable_pull",
    ),
]

OFFICIAL_BOUNDARY_TABLES = [
    ROOT / "data" / "bighorn_sheep_hunt_table_official.json",
    ROOT / "data" / "bison_hunt_table_official.json",
    ROOT / "data" / "black_bear_hunt_table_official.json",
    ROOT / "data" / "cougar_hunt_table_official.json",
    ROOT / "data" / "elk_antlerless_hunt_table_official.json",
    ROOT / "data" / "elk_hunt_table_official.json",
    ROOT / "data" / "moose_hunt_table_official.json",
    ROOT / "data" / "mountain_goat_hunt_table_official.json",
    ROOT / "data" / "pronghorn_hunt_table_official.json",
    ROOT / "data" / "turkey_hunt_table_official.json",
]

AUDIT_OUT = ROOT / "processed_data" / "audits" / "hunt_master_runtime_vs_database_universe_audit.csv"
SUMMARY_OUT = ROOT / "processed_data" / "audits" / "hunt_master_runtime_vs_database_universe_summary.json"
DOC_OUT = ROOT / "docs" / "hunt_master_runtime_vs_database_universe_audit.md"


CODE_RE = re.compile(r"^[A-Z]{1,4}\d{3,5}$")
CODE_KEYS = {
    "hunt_code",
    "huntcode",
    "hunt_nbr",
    "huntnumber",
    "hunt_number",
    "code",
    "hn",
}
NAME_KEYS = {
    "hunt_name",
    "huntname",
    "title",
    "hunttitle",
    "name",
    "hunt",
    "unitname",
    "unit_name",
}


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def normalize_code(value: Any) -> str:
    text = clean(value).upper()
    return text if CODE_RE.match(text) else ""


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{key: clean(value) for key, value in row.items()} for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def extract_from_dict(row: dict[str, Any]) -> tuple[str, str, str, str, str]:
    code = ""
    hunt_name = ""
    species = ""
    hunt_type = ""
    weapon = ""
    for key, value in row.items():
        norm = normalize_key(str(key))
        if not code and norm in CODE_KEYS:
            code = normalize_code(value)
        if not hunt_name and norm in NAME_KEYS:
            hunt_name = clean(value)
        if not species and norm in {"species", "speciesname"}:
            species = clean(value)
        if not hunt_type and norm in {"hunttype", "type", "huntclass", "category"}:
            hunt_type = clean(value)
        if not weapon and norm in {"weapon", "weapontype"}:
            weapon = clean(value)
    return code, hunt_name, species, hunt_type, weapon


def iter_json_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        records = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            attrs = item.get("attributes")
            records.append(attrs if isinstance(attrs, dict) else item)
        return records
    if not isinstance(payload, dict):
        return []
    for key in ("records", "hunts", "data", "items", "rows", "features"):
        value = payload.get(key)
        if isinstance(value, list):
            if key == "features":
                records = []
                for feature in value:
                    if not isinstance(feature, dict):
                        continue
                    props = feature.get("properties")
                    attrs = feature.get("attributes")
                    records.append(props if isinstance(props, dict) else (attrs if isinstance(attrs, dict) else feature))
                return records
            records = []
            for item in value:
                if not isinstance(item, dict):
                    continue
                attrs = item.get("attributes")
                records.append(attrs if isinstance(attrs, dict) else item)
            return records
    return [payload]


def load_source_codes(path: Path) -> tuple[list[dict[str, str]], str]:
    if not path.exists():
        return [], "MISSING"
    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except UnicodeDecodeError:
            payload = json.loads(path.read_text(encoding="utf-8"))
        records = iter_json_records(payload)
    elif path.suffix.lower() == ".csv":
        records = read_csv_rows(path)
    else:
        return [], "UNSUPPORTED"

    out: list[dict[str, str]] = []
    seen_rows = 0
    for record in records:
        code, hunt_name, species, hunt_type, weapon = extract_from_dict(record)
        if not code:
            continue
        seen_rows += 1
        out.append(
            {
                "hunt_code": code,
                "hunt_name": hunt_name,
                "species": species,
                "hunt_type": hunt_type,
                "weapon": weapon,
            }
        )
    return out, f"PARSED_{seen_rows}_CODE_ROWS"


def representative_by_code(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    reps: dict[str, dict[str, str]] = {}
    for row in rows:
        code = row["hunt_code"]
        if code not in reps:
            reps[code] = row
            continue
        current = reps[code]
        for field in ("hunt_name", "species", "hunt_type", "weapon"):
            if not current.get(field) and row.get(field):
                current[field] = row[field]
    return reps


def read_code_set(path: Path) -> set[str]:
    if not path.exists():
        return set()
    rows = read_csv_rows(path)
    out = set()
    for row in rows:
        code = normalize_code(row.get("hunt_code"))
        if code:
            out.add(code)
    return out


def summarize_source(
    label: str,
    role: str,
    path: Path,
    rows: list[dict[str, str]],
    parse_status: str,
    database_codes: set[str],
    active_codes: set[str],
    retired_codes: set[str],
) -> dict[str, Any]:
    codes = {row["hunt_code"] for row in rows}
    return {
        "label": label,
        "role": role,
        "path": str(path.relative_to(ROOT)) if path.exists() or path.is_absolute() else str(path),
        "exists": path.exists(),
        "parse_status": parse_status,
        "code_rows": len(rows),
        "unique_codes": len(codes),
        "codes_in_database": len(codes & database_codes),
        "codes_not_in_database": len(codes - database_codes),
        "codes_in_active_reconciliation": len(codes & active_codes),
        "codes_not_in_active_reconciliation": len(codes - active_codes),
        "active_codes_missing_from_source": len(active_codes - codes),
        "database_codes_missing_from_source": len(database_codes - codes),
        "retired_codes_present": len(codes & retired_codes),
    }


def main() -> int:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    database_rows, _ = load_source_codes(DATABASE)
    active_rows, _ = load_source_codes(ACTIVE_RECON)
    database_codes = {row["hunt_code"] for row in database_rows}
    active_codes = {row["hunt_code"] for row in active_rows}
    retired_codes = read_code_set(RETIRED_CODES)

    source_defs = list(SOURCE_FILES)
    for path in OFFICIAL_BOUNDARY_TABLES:
        source_defs.append((f"official_boundary_table_{path.stem}", path, "official_boundary_table"))

    all_audit_rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    source_reps: dict[str, dict[str, dict[str, str]]] = {}
    source_code_sets: dict[str, set[str]] = {}

    for label, path, role in source_defs:
        rows, parse_status = load_source_codes(path)
        reps = representative_by_code(rows)
        codes = set(reps)
        source_reps[label] = reps
        source_code_sets[label] = codes
        summaries.append(
            summarize_source(label, role, path, rows, parse_status, database_codes, active_codes, retired_codes)
        )
        full_universe_source = role not in {"official_boundary_table"}
        comparable_codes = codes | active_codes if full_universe_source else codes
        for code in sorted(comparable_codes):
            if code in codes:
                representative = reps.get(code, {})
                if code in active_codes and code in database_codes:
                    status = "MATCHES_ACTIVE_DATABASE"
                elif code in retired_codes:
                    status = "RETIRED_REFERENCE_PRESENT"
                elif code not in database_codes:
                    status = "SOURCE_EXTRA_NOT_DATABASE"
                elif code not in active_codes:
                    status = "SOURCE_PRESENT_DATABASE_NOT_ACTIVE"
                else:
                    status = "SOURCE_PRESENT_REVIEW"
            else:
                representative = {}
                status = "ACTIVE_CODE_MISSING_FROM_SOURCE"
            all_audit_rows.append(
                {
                    "source_label": label,
                    "source_role": role,
                    "source_path": str(path.relative_to(ROOT)) if path.exists() else str(path),
                    "hunt_code": code,
                    "hunt_name": representative.get("hunt_name", ""),
                    "species": representative.get("species", ""),
                    "hunt_type": representative.get("hunt_type", ""),
                    "weapon": representative.get("weapon", ""),
                    "in_source": code in codes,
                    "in_database": code in database_codes,
                    "in_active_reconciliation": code in active_codes,
                    "in_retired_ledger": code in retired_codes,
                    "status": status,
                }
            )

    status_counts = Counter(row["status"] for row in all_audit_rows)
    summary_payload = {
        "generated_at_utc": timestamp,
        "database_unique_codes": len(database_codes),
        "active_reconciliation_unique_codes": len(active_codes),
        "retired_codes": sorted(retired_codes),
        "status_counts": dict(sorted(status_counts.items())),
        "sources": summaries,
        "active_builder_runtime_note": (
            "config.js loads data/hunt-master-canonical-2026-foundation.json before "
            "data/hunt-master-canonical-2026-source-of-truth.json; data.js stops at the "
            "first authoritative source that parses with records."
        ),
    }

    write_csv(
        AUDIT_OUT,
        all_audit_rows,
        [
            "source_label",
            "source_role",
            "source_path",
            "hunt_code",
            "hunt_name",
            "species",
            "hunt_type",
            "weapon",
            "in_source",
            "in_database",
            "in_active_reconciliation",
            "in_retired_ledger",
            "status",
        ],
    )
    SUMMARY_OUT.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_OUT.write_text(json.dumps(summary_payload, indent=2) + "\n", encoding="utf-8")

    by_label = {item["label"]: item for item in summaries}
    builder = by_label.get("builder_runtime_foundation_json", {})
    source_truth = by_label.get("builder_runtime_source_of_truth_json", {})
    builder_missing = sorted(active_codes - source_code_sets.get("builder_runtime_foundation_json", set()))
    research_index_extra = sorted(source_code_sets.get("hunt_research_index_json", set()) - database_codes)
    source_truth_extra = sorted(source_code_sets.get("builder_runtime_source_of_truth_json", set()) - database_codes)

    def family_counts(codes: list[str]) -> str:
        counts = Counter(code[:2] for code in codes)
        if not counts:
            return "none"
        return ", ".join(f"`{family}` {count}" for family, count in counts.most_common())

    def code_list(codes: list[str], limit: int = 80) -> str:
        if not codes:
            return "`none`"
        shown = ", ".join(f"`{code}`" for code in codes[:limit])
        if len(codes) > limit:
            shown += f", ... plus {len(codes) - limit} more"
        return shown

    doc = [
        "# Hunt Master Runtime vs DATABASE Universe Audit",
        "",
        f"Generated: `{timestamp}`",
        "",
        "## Current read path",
        "",
        "`config.js` points the Builder entry-page hunt loader at `data/hunt-master-canonical-2026-foundation.json` first. "
        "`data.js` treats that source as authoritative and stops before the second source-of-truth candidate when the foundation file loads.",
        "",
        "## Key counts",
        "",
        f"- `DATABASE.csv` unique hunt codes: `{len(database_codes)}`",
        f"- Active current reconciliation unique hunt codes: `{len(active_codes)}`",
        f"- Builder first-load foundation unique hunt codes: `{builder.get('unique_codes', 'NA')}`",
        f"- Builder second-candidate source-of-truth unique hunt codes: `{source_truth.get('unique_codes', 'NA')}`",
        f"- Retired ledger codes considered: `{len(retired_codes)}`",
        f"- Active codes missing from Builder first-load foundation: `{len(builder_missing)}`",
        f"- Research split-index extra codes not in DATABASE: `{len(research_index_extra)}`",
        "",
        "## Source summaries",
        "",
        "| Source | Role | Unique codes | Extra not in DATABASE | Active codes missing from source | Retired present |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for item in summaries:
        active_missing_display = (
            "scoped-table" if item["role"] == "official_boundary_table" else str(item["active_codes_missing_from_source"])
        )
        doc.append(
            f"| {item['label']} | {item['role']} | {item['unique_codes']} | {item['codes_not_in_database']} | {active_missing_display} | {item['retired_codes_present']} |"
        )
    doc.extend(
        [
            "",
            "## Active Builder foundation gaps",
            "",
            f"Family breakdown for the `{len(builder_missing)}` active reconciliation codes missing from `data/hunt-master-canonical-2026-foundation.json`: {family_counts(builder_missing)}.",
            "",
            f"Codes: {code_list(builder_missing)}",
            "",
            "## Oversized Research split-index extras",
            "",
            f"`processed_data/hunt_research_2026_split/hunt_research_2026.index.json` contains `{len(research_index_extra)}` codes not in `DATABASE.csv`.",
            f"Family breakdown: {family_counts(research_index_extra)}.",
            "",
            f"First examples: {code_list(research_index_extra, 60)}",
            "",
            "## Builder fallback source-of-truth extras",
            "",
            f"`data/hunt-master-canonical-2026-source-of-truth.json` contains `{len(source_truth_extra)}` code(s) not in `DATABASE.csv`: {code_list(source_truth_extra)}.",
            "",
            "## Interpretation",
            "",
            "- If the online Builder appears to load a different universe than `DATABASE.csv`, the first file to check is `data/hunt-master-canonical-2026-foundation.json`, because that is the active first-load Builder master.",
            "- `data/hunt-master-canonical-2026-source-of-truth.json` may be more current, but it is currently a fallback and is not reached when the foundation file succeeds.",
            "- Extra source rows are not automatically current truth. They need to be checked against the active reconciliation, retired ledger, and current DWR pulls before promotion.",
            "",
            "## Outputs",
            "",
            f"- Audit CSV: `{AUDIT_OUT.relative_to(ROOT)}`",
            f"- Summary JSON: `{SUMMARY_OUT.relative_to(ROOT)}`",
        ]
    )
    DOC_OUT.parent.mkdir(parents=True, exist_ok=True)
    DOC_OUT.write_text("\n".join(doc) + "\n", encoding="utf-8")

    print(json.dumps(summary_payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
