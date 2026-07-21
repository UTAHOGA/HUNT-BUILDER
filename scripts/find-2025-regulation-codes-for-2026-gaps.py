#!/usr/bin/env python3
"""Find 2025 Big Game Application Guidebook codes for 2026 code gaps.

This is source-evidence only. It extracts hunt-code lines from the 2025 Big
Game Application Guidebook and compares them to current 2026 codes that do not
have exact 2025 historical permit values.
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


def _repo_root() -> Path:
    repo_root = Path(__file__).resolve()
    while repo_root.name != "HUNT-BUILDER" and repo_root.parent != repo_root:
        repo_root = repo_root.parent
    if repo_root.name != "HUNT-BUILDER":
        raise RuntimeError("Could not locate HUNT-BUILDER repo root")
    return repo_root

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
HUNTS_ROOT = Path(str(_repo_root()))
GUIDEBOOK = HUNTS_ROOT / "pipeline/RAW/hunt_unit_database/2025/pdf/regulations/2025_REGULATIONS__BIGGAMEAPP.pdf"
COMPARISON = ROOT / "processed_data/hunt_code_comparison_2025_to_2026.csv"

OUTPUT = ROOT / "processed_data/guidebook_2025_codes_for_2026_gaps.csv"
GUIDEBOOK_CODES_OUTPUT = ROOT / "processed_data/guidebook_2025_extracted_hunt_codes.csv"
SUMMARY_JSON = ROOT / "processed_data/guidebook_2025_codes_for_2026_gaps_summary.json"
SUMMARY_MD = ROOT / "processed_data/guidebook_2025_codes_for_2026_gaps.md"
VALIDATION_JSON = (
    ROOT / "data_truth/comparison_outputs/validation/guidebook_2025_codes_for_2026_gaps_summary.json"
)

CODE_RE = re.compile(r"\b(?:DB|DA|EB|EL|EA|PB|PD|BI|BR|DS|RS|MB|GO|LO|TK|CG)\d{4}\b")

TEXT_REPLACEMENTS = {
    "\u00e2\u20ac\u201c": "-",  # mojibake for en dash
    "\u00e2\u20ac\u201d": "-",  # mojibake for em dash
    "\u00e2\u20ac\u2122": "'",
    "\u00e2\u20ac\u0153": '"',
    "\u00e2\u20ac\u009d": '"',
    "\u00e2\u20ac\u00a2": "",
    "\u00e2\u20ac\u00a0": "",
    "\u00e2\u20ac\u00a1": "",
    "\u2013": "-",
    "\u2014": "-",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2022": "",
    "\u2020": "",
    "\u2021": "",
    "\u00c2": " ",
    "\u00a0": " ",
}

PREFIX_SPECIES = {
    "BI": "Bison",
    "DB": "Deer",
    "DA": "Deer",
    "EB": "Elk",
    "EL": "Elk",
    "EA": "Elk",
    "PB": "Pronghorn",
    "PD": "Pronghorn",
    "MB": "Moose",
    "DS": "Desert Bighorn Sheep",
    "RS": "Rocky Mountain Bighorn Sheep",
    "GO": "Mountain Goat",
    "BR": "Black Bear",
    "TK": "Turkey",
    "CG": "Cougar",
}

PREFIX_SWAP = {
    "EL": "EB",
    "LD": "DB",
    "LP": "PB",
    "LO": "DB",
    "PD": "PB",
}

OUTPUT_FIELDS = [
    "current_hunt_code",
    "current_hunt_name",
    "current_species",
    "current_hunt_type",
    "current_weapon",
    "current_2026_total",
    "comparison_status",
    "guidebook_match_status",
    "guidebook_candidate_codes",
    "guidebook_candidate_pages",
    "guidebook_candidate_names",
    "guidebook_candidate_lines",
    "match_method",
    "review_priority",
    "review_reason",
]

GUIDEBOOK_CODE_FIELDS = [
    "guidebook_code",
    "guidebook_prefix",
    "guidebook_species_inferred",
    "guidebook_hunt_name_candidate",
    "guidebook_page",
    "guidebook_line",
]


def clean(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip().replace("\ufeff", "")
    return text


def ascii_clean(value: object) -> str:
    text = clean(value)
    for bad, good in TEXT_REPLACEMENTS.items():
        text = text.replace(bad, good)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", text).strip()


def normalize(value: object) -> str:
    text = ascii_clean(value)
    text = text.lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    stop = {"new", "formerly", "private", "land", "only", "cwmu", "unit", "units"}
    return " ".join(part for part in text.split() if part not in stop)


def species_for_code(code: str) -> str:
    return PREFIX_SPECIES.get(code[:2], "")


def extract_hunt_name_from_line(line: str, code: str) -> str:
    before = line.split(code, 1)[0]
    before = ascii_clean(before)
    before = re.sub(r"^[*\-\s]+", "", before)
    return before.strip(" *")


def extract_guidebook_codes() -> list[dict[str, str]]:
    reader = PdfReader(str(GUIDEBOOK))
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, int, str]] = set()
    for page_index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        for raw_line in text.splitlines():
            line = ascii_clean(raw_line)
            if not line:
                continue
            codes = CODE_RE.findall(line)
            for code in codes:
                key = (code, page_index, line)
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "guidebook_code": code,
                        "guidebook_prefix": code[:2],
                        "guidebook_species_inferred": species_for_code(code),
                        "guidebook_hunt_name_candidate": extract_hunt_name_from_line(line, code),
                        "guidebook_page": str(page_index),
                        "guidebook_line": line,
                    }
                )
    return rows


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{key: clean(value) for key, value in row.items()} for row in csv.DictReader(handle)]


def gap_rows() -> list[dict[str, str]]:
    statuses = {
        "CURRENT_2026_PERMIT_CODE_NO_2025_HISTORY",
        "HISTORICAL_2025_CODE_PRESENT_BUT_NO_2026_PERMIT_VALUE",
    }
    return [row for row in read_csv(COMPARISON) if row.get("comparison_status") in statuses]


def join_unique(values: list[str]) -> str:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = ascii_clean(value)
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return "|".join(output)


def candidate_payload(candidates: list[dict[str, str]]) -> dict[str, str]:
    return {
        "guidebook_candidate_codes": join_unique([row["guidebook_code"] for row in candidates]),
        "guidebook_candidate_pages": join_unique([row["guidebook_page"] for row in candidates]),
        "guidebook_candidate_names": join_unique([row["guidebook_hunt_name_candidate"] for row in candidates]),
        "guidebook_candidate_lines": join_unique([row["guidebook_line"] for row in candidates]),
    }


def match_row(
    gap: dict[str, str],
    guidebook_by_code: dict[str, list[dict[str, str]]],
    guidebook_by_species_name: dict[tuple[str, str], list[dict[str, str]]],
) -> dict[str, str]:
    code = clean(gap.get("hunt_code")).upper()
    species = clean(gap.get("species"))
    name = clean(gap.get("hunt_name"))
    normalized_name = normalize(name)

    candidates: list[dict[str, str]] = []
    match_status = "GUIDEBOOK_NO_CODE_FOUND"
    match_method = "none"
    priority = "HIGH"
    reason = "No code evidence found in the 2025 Big Game Application Guidebook."

    exact = guidebook_by_code.get(code, [])
    if exact:
        candidates = exact
        match_status = "EXACT_CURRENT_CODE_IN_2025_GUIDEBOOK"
        match_method = "exact_code"
        priority = "NONE"
        reason = "Current code appears exactly in the 2025 guidebook."
    else:
        swapped_code = ""
        if code[:2] in PREFIX_SWAP:
            swapped_code = PREFIX_SWAP[code[:2]] + code[2:]
        if swapped_code and swapped_code in guidebook_by_code:
            candidates = guidebook_by_code[swapped_code]
            match_status = "PREFIX_SWAP_CODE_IN_2025_GUIDEBOOK"
            match_method = f"{code[:2]}_to_{swapped_code[:2]}_same_number"
            priority = "MEDIUM"
            reason = "A same-number prefix-swap code appears in the 2025 guidebook; review before promotion."
        else:
            name_candidates = guidebook_by_species_name.get((species, normalized_name), [])
            if name_candidates:
                candidates = name_candidates
                match_status = "NAME_SPECIES_CANDIDATES_IN_2025_GUIDEBOOK"
                match_method = "same_species_normalized_name"
                priority = "MEDIUM"
                reason = "Same species and normalized hunt name found in the 2025 guidebook; candidate evidence only."

    payload = candidate_payload(candidates)
    return {
        "current_hunt_code": code,
        "current_hunt_name": name,
        "current_species": species,
        "current_hunt_type": clean(gap.get("hunt_type")),
        "current_weapon": clean(gap.get("weapon")),
        "current_2026_total": clean(gap.get("permits_2026_total")),
        "comparison_status": clean(gap.get("comparison_status")),
        "guidebook_match_status": match_status,
        "match_method": match_method,
        "review_priority": priority,
        "review_reason": reason,
        **payload,
    }


def build_matches() -> tuple[list[dict[str, str]], list[dict[str, str]], dict]:
    guidebook_codes = extract_guidebook_codes()
    guidebook_by_code: dict[str, list[dict[str, str]]] = defaultdict(list)
    guidebook_by_species_name: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in guidebook_codes:
        guidebook_by_code[row["guidebook_code"]].append(row)
        name_key = normalize(row["guidebook_hunt_name_candidate"])
        if row["guidebook_species_inferred"] and name_key:
            guidebook_by_species_name[(row["guidebook_species_inferred"], name_key)].append(row)

    gaps = gap_rows()
    rows = [match_row(row, guidebook_by_code, guidebook_by_species_name) for row in gaps]
    status_counts = Counter(row["guidebook_match_status"] for row in rows)
    comparison_counts = Counter(row["comparison_status"] for row in rows)
    priority_counts = Counter(row["review_priority"] for row in rows)
    species_status_counts: dict[str, dict[str, int]] = {}
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["current_species"]].append(row)
    for species, species_rows in grouped.items():
        species_status_counts[species] = dict(sorted(Counter(row["guidebook_match_status"] for row in species_rows).items()))

    summary = {
        "artifact": "guidebook_2025_codes_for_2026_gaps",
        "guidebook_file": str(GUIDEBOOK).replace("\\", "/"),
        "comparison_file": COMPARISON.relative_to(ROOT).as_posix(),
        "guidebook_code_line_rows": len(guidebook_codes),
        "guidebook_unique_codes": len({row["guidebook_code"] for row in guidebook_codes}),
        "gap_rows_checked": len(rows),
        "guidebook_match_status_counts": dict(sorted(status_counts.items())),
        "comparison_status_counts": dict(sorted(comparison_counts.items())),
        "review_priority_counts": dict(sorted(priority_counts.items())),
        "species_match_status_counts": dict(sorted(species_status_counts.items())),
        "guardrail": (
            "This is source evidence from the 2025 Big Game Application Guidebook only. Exact and prefix-swap "
            "guidebook hits can support crosswalk review; name-only candidates remain review evidence and must not "
            "be promoted without source-lineage validation."
        ),
        "outputs": {
            "matches_csv": OUTPUT.relative_to(ROOT).as_posix(),
            "guidebook_codes_csv": GUIDEBOOK_CODES_OUTPUT.relative_to(ROOT).as_posix(),
            "summary_json": SUMMARY_JSON.relative_to(ROOT).as_posix(),
            "summary_md": SUMMARY_MD.relative_to(ROOT).as_posix(),
            "validation_json": VALIDATION_JSON.relative_to(ROOT).as_posix(),
        },
    }
    return rows, guidebook_codes, summary


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: ascii_clean(row.get(field, "")) for field in fieldnames})


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(summary: dict) -> None:
    lines = [
        "# 2025 Guidebook Codes For 2026 Gaps",
        "",
        "Read-only evidence table for 2026 codes without exact populated 2025 permit history.",
        "",
        "## Summary",
        "",
        f"- Guidebook code-line rows: `{summary['guidebook_code_line_rows']}`",
        f"- Guidebook unique codes: `{summary['guidebook_unique_codes']}`",
        f"- Gap rows checked: `{summary['gap_rows_checked']}`",
        "",
        "## Guardrail",
        "",
        summary["guardrail"],
        "",
        "## Match Status Counts",
        "",
    ]
    for status, count in summary["guidebook_match_status_counts"].items():
        lines.append(f"- `{status}`: `{count}`")
    lines.extend(["", "## Review Priority Counts", ""])
    for priority, count in summary["review_priority_counts"].items():
        lines.append(f"- `{priority}`: `{count}`")
    SUMMARY_MD.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    rows, guidebook_codes, summary = build_matches()
    write_csv(OUTPUT, rows, OUTPUT_FIELDS)
    write_csv(GUIDEBOOK_CODES_OUTPUT, guidebook_codes, GUIDEBOOK_CODE_FIELDS)
    write_json(SUMMARY_JSON, summary)
    write_json(VALIDATION_JSON, summary)
    write_markdown(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
