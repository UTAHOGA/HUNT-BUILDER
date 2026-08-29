"""Audit canonical draw-truth source labels against retained parent sources.

This is a lineage audit, not a data rewrite. A canonical source scope can be
reported as linked only when it has either an exact retained parent filename,
one unambiguous source-title-backed parent report, or endpoint evidence named
explicitly by the retained 2026 hunt/residency/point audit. Multi-parent cases
remain review records instead of being guessed into a link.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from urllib.parse import parse_qsl, unquote_plus, urlparse


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DIR = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
ARCHIVE_CATALOG = ROOT / "data_truth" / "draw_results_truth" / "raw_inventory" / "official_draw_source_retention_2017_2026.csv"
PDF_PARITY_AUDIT = ROOT / "data_truth" / "draw_results_truth" / "validation" / "draw_2026_pdf_rows_vs_utahdraws_snapshot.csv"
LIVE_ENDPOINT_AUDIT = ROOT / "data_truth" / "draw_results_truth" / "validation" / "draw_2026_live_endpoint_rows.csv"
PLANNER_MATRIX_DIR = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "_staging" / "huntplanner_full_matrix_20260826_204000"
PLANNER_MATRIX_MANIFEST = PLANNER_MATRIX_DIR / "dwr_huntboundary_full_matrix_manifest.csv"
PLANNER_POPUP_DIR = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "_staging" / "huntplanner_popup_deep_20260826_205700"
PLANNER_POPUP_CSV = PLANNER_POPUP_DIR / "dwr_huntplanner_hanumber_2026.csv"
PLANNER_POPUP_RAW = PLANNER_POPUP_DIR / "dwr_huntplanner_hanumber_2026_raw_payloads.json"
OUT_DIR = ROOT / "data_truth" / "draw_results_truth" / "validation"
OUT_CSV = OUT_DIR / "canonical_parent_source_mapping_2018_2026.csv"
OUT_JSON = OUT_DIR / "canonical_parent_source_mapping_2018_2026.json"

FIELDS = [
    "draw_year", "canonical_source_label", "canonical_rows", "canonical_pdf_pages",
    "source_dataset_values", "source_scope_values", "mapping_status", "mapping_method",
    "scorable_rows", "certifiable_scorable_rows", "scorable_exclusions", "unscorable_structural_rows", "scoring_lineage_status",
    "parent_report_year", "parent_archive_paths", "parent_official_urls", "parent_sha256s", "notes",
]


def clean(value: object) -> str:
    return str(value or "").strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def source_label(value: str) -> str:
    text = clean(value)
    if not text:
        return ""
    # Canonicals contain both bare filenames and Windows absolute paths.
    return PureWindowsPath(text).name or Path(text).name


def norm(value: object) -> str:
    text = source_label(clean(value)).lower().replace("&amp;", "and")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalized_url(value: object) -> str:
    """Normalize DWR query URLs without changing their reported source text."""
    parsed = urlparse(clean(value))
    if not parsed.scheme or not parsed.netloc:
        return ""
    query = sorted(
        (clean(key).lower(), unquote_plus(clean(item)).lower())
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
    )
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path.lower()}?{query}"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def retained_planner_evidence() -> dict[str, dict[str, str]]:
    """Index the locally retained 2026 Planner matrix and popup evidence."""
    evidence: dict[str, dict[str, str]] = {}
    if PLANNER_MATRIX_MANIFEST.exists():
        for row in read_csv(PLANNER_MATRIX_MANIFEST):
            artifact = PLANNER_MATRIX_DIR / clean(row.get("file"))
            url = clean(row.get("url"))
            if clean(row.get("status")).lower() != "ok" or not artifact.exists() or not url:
                continue
            evidence[normalized_url(url)] = {
                "report_year": "2026",
                "durable_archive_path": artifact.relative_to(ROOT).as_posix(),
                "official_url": url,
                "sha256": sha256(artifact),
            }
    if PLANNER_POPUP_CSV.exists() and PLANNER_POPUP_RAW.exists():
        raw_hash = sha256(PLANNER_POPUP_RAW)
        raw_path = PLANNER_POPUP_RAW.relative_to(ROOT).as_posix()
        for row in read_csv(PLANNER_POPUP_CSV):
            url = clean(row.get("source_url"))
            if clean(row.get("fetch_status")) != "OK" or not url:
                continue
            evidence[normalized_url(url)] = {
                "report_year": "2026",
                "durable_archive_path": raw_path,
                "official_url": url,
                "sha256": raw_hash,
            }
    return evidence


def parent_candidates(
    label: str,
    sources: list[dict[str, str]],
    planner_evidence: dict[str, dict[str, str]],
) -> tuple[str, list[dict[str, str]], str]:
    """Return status, candidate sources, and a transparent matching method."""
    label_norm = norm(label)
    exact = [s for s in sources if source_label(s["durable_archive_path"]).lower() == source_label(label).lower()]
    if len(exact) == 1:
        return "LINKED", exact, "EXACT_ARCHIVED_FILENAME"
    planner = planner_evidence.get(normalized_url(label))
    if planner:
        return "LINKED_RETAINED_DWR_PLANNER_EVIDENCE", [planner], "EXACT_RETAINED_DWR_PLANNER_CAPTURE"
    if label.lower().startswith("utahdraws live drawoddsdata:"):
        return "ENDPOINT_GROUP_REVIEW", [], "2026_LIVE_ENDPOINT_GROUP_REQUIRES_HUNT_LEVEL_MATCH"
    if "2026_permits=2027_model" in label_norm or "2026 permits 2027 model" in label_norm:
        return "SOURCE_RECOVERY_REQUIRED", [], "2026_CANONICAL_PDF_PARENT_NOT_RETAINED"

    # These historic canonical labels were produced by splitting a single
    # retained DWR report into named species/program scopes. Match them to the
    # report's filename/title family, never by a generic fuzzy score.
    def by_archive_filename(fragment: str) -> list[dict[str, str]]:
        return [source for source in sources if fragment in source_label(source["durable_archive_path"]).lower()]

    if "cwmu big game" in label_norm or label_norm.endswith("big game draw results pdf"):
        candidates = by_archive_filename("bg-odds.pdf")
        if len(candidates) == 1:
            return "LINKED", candidates, "ARCHIVED_PARENT_BUNDLE_FILENAME:BIG_GAME"
    if "antlerless" in label_norm or "doe pronghorn" in label_norm or "ewe" in label_norm:
        candidates = by_archive_filename("antlerless_drawing_odds_report.pdf")
        if "youth" in label_norm:
            candidates = [source for source in candidates if "youth_" in source_label(source["durable_archive_path"]).lower()]
        else:
            candidates = [source for source in candidates if "youth_" not in source_label(source["durable_archive_path"]).lower()]
        if len(candidates) == 1:
            return "LINKED", candidates, "ARCHIVED_PARENT_BUNDLE_FILENAME:ANTLERLESS"
    if "turkey" in label_norm:
        fragment = "youth_turkey" if "youth" in label_norm else "turkey_bonus_points"
        candidates = by_archive_filename(fragment)
        if "youth" not in label_norm:
            candidates = [source for source in candidates if "youth_" not in source_label(source["durable_archive_path"]).lower()]
        if len(candidates) == 1:
            return "LINKED", candidates, "ARCHIVED_FILENAME_AND_OFFICIAL_TITLE:TURKEY"
    if "sportsman" in label_norm:
        candidates = by_archive_filename("sportsman_odds.pdf")
        if len(candidates) == 1:
            return "LINKED", candidates, "ARCHIVED_FILENAME_AND_OFFICIAL_TITLE:SPORTSMAN"
    if "youth" in label_norm and ("g s" in label_norm or "general season" in label_norm) and "deer" in label_norm:
        candidates = by_archive_filename("youth_deer.pdf")
        if len(candidates) == 1:
            return "LINKED", candidates, "ARCHIVED_FILENAME_AND_OFFICIAL_TITLE:YOUTH_GENERAL_DEER"
    if ("g s" in label_norm or "general season" in label_norm) and "deer" in label_norm:
        candidates = [source for source in by_archive_filename("deer_odds.pdf") if "youth_deer" not in source_label(source["durable_archive_path"]).lower()]
        if len(candidates) == 1:
            return "LINKED", candidates, "ARCHIVED_FILENAME_AND_OFFICIAL_TITLE:GENERAL_DEER"
    if "le deer draw results" in label_norm:
        candidates = by_archive_filename("bg-odds.pdf")
        if len(candidates) == 1:
            return "LINKED", candidates, "ARCHIVED_PARENT_BUNDLE_FILENAME:LIMITED_ENTRY_DEER"

    # Parent report titles are official page labels. Use deliberate, conservative
    # design-family anchors rather than filename similarity or a fuzzy score.
    rules: list[tuple[str, tuple[str, ...]]] = [
        ("sportsman", ("sportsman",)),
        ("youth_antlerless", ("youth", "antlerless")),
        ("antlerless", ("antlerless",)),
        ("youth_dedicated_hunter", ("youth", "dedicated hunter")),
        ("dedicated_hunter", ("dedicated hunter",)),
        ("lifetime_deer", ("lifetime", "deer")),
        ("youth_elk", ("youth", "elk")),
        ("youth_deer", ("youth", "deer")),
        ("general_deer", ("general", "deer")),
        ("le_oil_parent", ("limited", "entry")),
    ]
    category = ""
    if any(token in label_norm for token in ("black bear", "bear draw", "bear_")):
        category = "black_bear"
    elif "cougar" in label_norm:
        category = "cougar"
    elif "turkey" in label_norm:
        category = "turkey"
    elif "sportsman" in label_norm:
        category = "sportsman"
    elif "youth" in label_norm and "antlerless" in label_norm:
        category = "youth_antlerless"
    elif "antlerless" in label_norm or "doe" in label_norm or "ewe" in label_norm:
        category = "antlerless"
    elif ("dedicated" in label_norm or " d h " in f" {label_norm} ") and "youth" in label_norm:
        category = "youth_dedicated_hunter"
    elif "dedicated" in label_norm or " d h " in f" {label_norm} ":
        category = "dedicated_hunter"
    elif "lifetime" in label_norm:
        category = "lifetime_deer"
    elif "youth" in label_norm and ("elk" in label_norm or "bull" in label_norm):
        category = "youth_elk"
    elif "youth" in label_norm and "deer" in label_norm:
        category = "youth_deer"
    elif "general" in label_norm or "g s" in label_norm:
        category = "general_deer"
    elif any(token in label_norm for token in ("c w m u big game", "l e", "o i l", "once in a lifetime", "mountain goat", "bighorn", "bison")):
        category = "le_oil_parent"

    if category in {"black_bear", "cougar", "turkey"}:
        candidates = [source for source in sources if clean(source["source_family"]) == category]
        if len(candidates) == 1:
            return "LINKED", candidates, f"OFFICIAL_SOURCE_FAMILY:{category}"
        return ("AMBIGUOUS_PARENT" if candidates else "UNMAPPED", candidates, f"OFFICIAL_SOURCE_FAMILY:{category}")

    for rule_name, required in rules:
        if category != rule_name:
            continue
        candidates = [s for s in sources if all(token in clean(s["official_title"]).lower() for token in required)]
        if "youth" in label_norm:
            candidates = [s for s in candidates if "youth" in clean(s["official_title"]).lower()]
        else:
            candidates = [s for s in candidates if "youth" not in clean(s["official_title"]).lower()]
        if len(candidates) == 1:
            return "LINKED", candidates, f"OFFICIAL_TITLE_RULE:{rule_name}"
        return ("AMBIGUOUS_PARENT" if candidates else "UNMAPPED", candidates, f"OFFICIAL_TITLE_RULE:{rule_name}")
    return "UNMAPPED", [], "NO_CONSERVATIVE_PARENT_RULE"


def parity_by_source_label() -> dict[str, list[dict[str, str]]]:
    """Load the exact 2026 row-level outcome audits without changing truth."""
    grouped: dict[str, list[dict[str, str]]] = {}
    for path in (PDF_PARITY_AUDIT, LIVE_ENDPOINT_AUDIT):
        if not path.exists():
            continue
        for row in read_csv(path):
            grouped.setdefault(source_label(clean(row.get("canonical_source_file"))), []).append(row)
    return grouped


def endpoint_rows_by_source_label() -> dict[str, list[dict[str, str]]]:
    """Group retained 2026 endpoint-audit rows by canonical source label.

    The PDF-parity audit includes both scorable outcome rows and structural
    zero/N-A rows. The latter cannot certify probability, but an explicit
    `expected_snapshot_source_json_file` is still conclusive parent-source
    lineage. Do not discard that retained source merely because its row is
    intentionally unscorable.
    """
    grouped: dict[str, list[dict[str, str]]] = {}
    seen: set[tuple[str, str, str, str, str]] = set()
    for path in (PDF_PARITY_AUDIT, LIVE_ENDPOINT_AUDIT):
        if not path.exists():
            continue
        for row in read_csv(path):
            label = source_label(clean(row.get("canonical_source_file")))
            key = (
                label,
                clean(row.get("hunt_code")),
                clean(row.get("residency")),
                clean(row.get("points") or row.get("canonical_points")),
                clean(row.get("expected_snapshot_source_json_file")),
            )
            if key in seen:
                continue
            seen.add(key)
            grouped.setdefault(label, []).append(row)
    return grouped


def endpoint_parent_candidates(
    label: str,
    archive_sources: list[dict[str, str]],
    endpoint_rows_by_label: dict[str, list[dict[str, str]]],
) -> tuple[str, list[dict[str, str]], str] | None:
    """Resolve a 2026 display-family label through exact endpoint parity.

    The canonical label is an aggregate display family, not an endpoint name.
    The retained source packages are selected only from the hunt/residency/
    point-level audit, never from a loose family-name match.
    """
    rows = endpoint_rows_by_label.get(source_label(label), [])
    endpoint_names = {
        clean(row.get("expected_snapshot_source_json_file"))
        for row in rows
        if clean(row.get("expected_snapshot_source_json_file"))
    }
    parents = [
        source
        for source in archive_sources
        if source_label(source.get("durable_archive_path", "")) in endpoint_names
    ]
    if not rows or len(parents) != len(endpoint_names):
        return None
    if any(
        clean(row.get("certification_disposition"))
        == "EXCLUDE_FROM_CERTIFIABLE_SCORING_PENDING_SOURCE_RECONCILIATION"
        for row in rows
    ):
        status = "LINKED_RETAINED_2026_ENDPOINT_EVIDENCE_WITH_SCORABLE_EXCLUSIONS"
    elif any(clean(row.get("parity_status")).startswith("AMBIGUOUS_") for row in rows):
        status = "LINKED_RETAINED_2026_ENDPOINT_EVIDENCE_WITH_NONSCORING_AMBIGUITY"
    elif all(
        clean(row.get("certification_disposition")) == "UNSCORABLE_NO_APPLICANT_OR_SUCCESS"
        for row in rows
    ):
        status = "LINKED_RETAINED_2026_ENDPOINT_PARENT_NONSCORING"
    else:
        status = "LINKED_RETAINED_2026_ENDPOINT_EVIDENCE"
    return status, parents, "EXACT_RETAINED_ENDPOINT_PARENT_FROM_HUNT_RESIDENCY_POINT_AUDIT"


def scoring_lineage(rows: list[dict[str, str]]) -> tuple[str, str, str, str, str]:
    """Describe score eligibility separately from a physical PDF-parent link."""
    if not rows:
        return "", "", "", "", "NOT_APPLICABLE"
    scorable = [
        row
        for row in rows
        if (
            clean(row.get("canonical_is_scorable")).lower() == "true"
            or (
                "canonical_is_scorable" not in row
                and clean(row.get("certification_disposition")) != "UNSCORABLE_NO_APPLICANT_OR_SUCCESS"
            )
        )
    ]
    certifiable = [row for row in scorable if clean(row.get("certification_disposition")) == "CERTIFIABLE_SOURCE_VALUE_PARITY"]
    excluded = [row for row in scorable if clean(row.get("certification_disposition")) == "EXCLUDE_FROM_CERTIFIABLE_SCORING_PENDING_SOURCE_RECONCILIATION"]
    unscorable = [row for row in rows if clean(row.get("certification_disposition")) == "UNSCORABLE_NO_APPLICANT_OR_SUCCESS"]
    if not scorable:
        status = "NONSCORING_STRUCTURAL_ROWS_ONLY"
    elif not excluded:
        status = "VALUE_PARITY_FOR_ALL_SCORABLE_ROWS"
    else:
        status = "VALUE_PARITY_WITH_SCORABLE_EXCLUSIONS"
    return str(len(scorable)), str(len(certifiable)), str(len(excluded)), str(len(unscorable)), status


def main() -> None:
    archive_rows = read_csv(ARCHIVE_CATALOG)
    by_year: dict[int, list[dict[str, str]]] = {}
    for row in archive_rows:
        try:
            year = int(clean(row.get("report_year")))
        except ValueError:
            continue
        by_year.setdefault(year, []).append(row)
    row_level_parity = parity_by_source_label()
    endpoint_rows_by_label = endpoint_rows_by_source_label()
    planner_evidence = retained_planner_evidence()

    output: list[dict[str, str]] = []
    for canonical in sorted(CANONICAL_DIR.glob("draw_results_*_for_*_canonical_yearly_draw_results.csv")):
        match = re.search(r"draw_results_(20\d{2})_for_", canonical.name)
        if not match:
            continue
        year = int(match.group(1))
        groups: dict[str, list[dict[str, str]]] = {}
        for row in read_csv(canonical):
            label = clean(row.get("source_file"))
            if not label:
                label = "(blank source file)"
            groups.setdefault(label, []).append(row)
        for label, rows in sorted(groups.items()):
            endpoint_resolution = (
                endpoint_parent_candidates(label, by_year.get(year, []), endpoint_rows_by_label)
                if year == 2026
                else None
            )
            if endpoint_resolution:
                status, parents, method = endpoint_resolution
            else:
                status, parents, method = parent_candidates(
                    label, by_year.get(year, []), planner_evidence
                )
            scorable, certifiable, exclusions, unscorable, scoring_status = scoring_lineage(
                row_level_parity.get(source_label(label), []) if year == 2026 else []
            )
            output.append({
                "draw_year": str(year),
                "canonical_source_label": label,
                "canonical_rows": str(len(rows)),
                "canonical_pdf_pages": str(sum(1 for row in rows if clean(row.get("pdf_page")))),
                "source_dataset_values": " | ".join(sorted({clean(row.get("source_dataset")) for row in rows if clean(row.get("source_dataset"))})),
                "source_scope_values": " | ".join(sorted({clean(row.get("source_scope")) for row in rows if clean(row.get("source_scope"))}))[:2000],
                "mapping_status": status,
                "mapping_method": method,
                "scorable_rows": scorable,
                "certifiable_scorable_rows": certifiable,
                "scorable_exclusions": exclusions,
                "unscorable_structural_rows": unscorable,
                "scoring_lineage_status": scoring_status,
                "parent_report_year": " | ".join(sorted({clean(parent["report_year"]) for parent in parents})),
                "parent_archive_paths": " | ".join(parent["durable_archive_path"] for parent in parents),
                "parent_official_urls": " | ".join(parent["official_url"] for parent in parents),
                "parent_sha256s": " | ".join(parent["sha256"] for parent in parents),
                "notes": "The mapping points to a retained official source artifact: either an archived report, a raw UtahDraws endpoint package, or a raw DWR Planner capture. The 2026 scoring-lineage fields separately report exact outcome parity and exclusions; no canonical values are changed by this audit.",
            })

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(output)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Canonical source-label to archived-parent evidence audit; no canonical values were changed.",
        "source_scope_records": len(output),
        "rows_by_mapping_status": dict(sorted(Counter(row["mapping_status"] for row in output).items())),
        "rows_by_scoring_lineage_status": dict(sorted(Counter(row["scoring_lineage_status"] for row in output).items())),
        "canonical_rows_by_mapping_status": dict(sorted(Counter({status: sum(int(row["canonical_rows"]) for row in output if row["mapping_status"] == status) for status in {row["mapping_status"] for row in output}}).items())),
        "mapping_csv": OUT_CSV.relative_to(ROOT).as_posix(),
        "next_gate": "Physical archived-PDF links, retained raw UtahDraws endpoint links, and retained raw DWR Planner links are reported separately. For certification scoring, use only row-level VALUE_PARITY rows and exclude every remaining scorable source-dimension/value issue.",
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
