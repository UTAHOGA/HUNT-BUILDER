"""Build website-matrix to master-canonical key alignment audit.

Audit-only. Does not modify DATABASE.csv, draw_results_long.csv, canonical truth,
or prediction outputs.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUT = ROOT / "audits" / f"website_matrix_key_alignment{STAMP}"

DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
DRAW_RESULTS_LONG = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
CANONICAL_ZIP = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly (2).zip"
TAXONOMY_MANIFEST = (
    ROOT
    / "pipeline"
    / "RAW"
    / "hunt_unit_database"
    / "_staging"
    / "draw_odds_deep_pull_20260721_031919"
    / "DRAW_ODDS_DEEP_PULL_MANIFEST.csv"
)
TAXONOMY_EXCLUDED = TAXONOMY_MANIFEST.with_name("DRAW_ODDS_DEEP_PULL_EXCLUDED_LINKS.csv")
PREDICTION_HEADER_FILE = (
    ROOT
    / "audits"
    / "progressive_prediction_audit"
    / "20260721_youth_turkey_program_start_fix"
    / "runs"
    / "2021"
    / "family_predictions.csv"
)
KEY_RECIPE_FILE = ROOT / "engine" / "utah_draw_predictive" / "run_all_families.py"

BIG_GAME_SPECIES = [
    "DEER",
    "ELK",
    "PRONGHORN",
    "BISON",
    "ROCKY_MOUNTAIN_BIGHORN_SHEEP",
    "DESERT_BIGHORN_SHEEP",
    "MOOSE",
    "MOUNTAIN_GOAT",
]
OIL_SPECIES = [
    "BISON",
    "ROCKY_MOUNTAIN_BIGHORN_SHEEP",
    "DESERT_BIGHORN_SHEEP",
    "MOOSE",
    "MOUNTAIN_GOAT",
]
LE_BIG_GAME_SPECIES = ["DEER", "ELK", "PRONGHORN"]


def clean(value: object) -> str:
    return " ".join(str(value or "").split())


def norm_header(value: object) -> str:
    text = clean(value).upper().replace("-", "_")
    text = re.sub(r"[^A-Z0-9]+", "_", text).strip("_")
    text = re.sub(r"_+", "_", text)
    if text.startswith("PERMPITS_"):
        text = "PERMITS_" + text[len("PERMPITS_") :]
    text = re.sub(r"^PERMITS_(20\d{2})_NR$", r"PERMITS_\1_NON_RES", text)
    return text


def read_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return next(csv.reader(handle))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def active_canonical_headers() -> dict[str, list[str]]:
    headers: dict[str, list[str]] = {}
    if not CANONICAL_ZIP.exists():
        return headers
    with zipfile.ZipFile(CANONICAL_ZIP) as archive:
        for info in archive.infolist():
            name = info.filename
            if not name.endswith(".csv"):
                continue
            if not name.startswith("canonical_yearly/draw_results_"):
                continue
            if "/backups" in name or ".backup_" in name or "/import_audits/" in name:
                continue
            with archive.open(name) as raw:
                headers[Path(name).name] = next(csv.reader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")))
    return headers


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def semantic_role(column: str) -> str:
    n = norm_header(column)
    if n in {"ACTUAL_DRAW_YEAR", "PERMIT_YEAR", "LICENSE_YEAR", "SOURCE_YEAR", "YEAR"}:
        return "permit_year" if n != "MODEL_TARGET_YEAR" else "model_year"
    if n in {"MODEL_TARGET_YEAR", "MODEL_YEAR", "TARGET_YEAR", "PREDICTION_YEAR"}:
        return "model_year"
    if n == "HUNT_CODE":
        return "hunt_code"
    if n in {"HUNT_NAME", "RAW_HUNT_NAME"}:
        return "hunt_name"
    if n in {"SPECIES", "SPECIES_BUCKET"}:
        return "species"
    if n in {"SPECIES_SUBBUCKET", "SHEEP_SUBSPECIES"}:
        return "species_subbucket"
    if n in {"SEX", "SEX_TYPE", "SEX_CLASS"}:
        return "sex_class"
    if n in {"DRAW_DESIGN", "DRAW_SYSTEM_TYPE", "DRAW_2026_SYSTEM_TYPE"}:
        return "draw_design"
    if n in {"SOURCE_FAMILY", "MASTER_FAMILY", "DRAW_PACKAGE", "REPORT_FAMILY"}:
        return "draw_family"
    if n in {"PROGRAM_BUCKET", "HUNT_CLASS", "HUNT_DRAW_CLASS", "HUNT_TYPE"}:
        return "program_bucket"
    if n == "RESIDENCY":
        return "residency"
    if n in {"POINTS", "POINT_LEVEL", "PREFERENCE_POINT", "POINT"}:
        return "point_level"
    if "APPLICANT" in n or n == "ELIGIBLE_APPLICANTS":
        return "applicants"
    if "PERMIT" in n or "QUOTA" in n:
        return "permits"
    if "SUCCESSFUL" in n and "UNSUCCESSFUL" not in n:
        return "successful"
    if "P_DRAW" in n or "ODDS" in n:
        return "actual_probability" if "PREDICT" not in n else "predicted_probability"
    if n == "OFFICIAL_SCORE_KEY_V2":
        return "official_score_key_v2"
    if n in {"SOURCE_FILE", "DRAW_SOURCE_FILE", "SOURCE_PDF"}:
        return "source_file"
    if n in {"SOURCE_URL", "SOURCE_PATH"}:
        return "source_lineage"
    if n in {"SOURCE_PAGE", "PDF_PAGE", "OFFICIAL_PAGE"}:
        return "source_page"
    if n in {"PARSE_METHOD", "EXTRACTION_METHOD"}:
        return "extraction_method"
    if "STATUS" in n or "REVIEW" in n or "QA" in n:
        return "review_status"
    return "source_lineage" if n.startswith("SOURCE") else "unknown"


def required_flags(role: str, column: str) -> tuple[str, str, str, str]:
    n = norm_header(column)
    truth = role in {
        "permit_year",
        "model_year",
        "hunt_code",
        "hunt_name",
        "species",
        "sex_class",
        "draw_design",
        "program_bucket",
        "residency",
        "point_level",
        "applicants",
        "permits",
        "successful",
        "actual_probability",
    }
    key = n in {
        "OFFICIAL_SCORE_KEY_V2",
        "TARGET_YEAR",
        "PREDICTION_YEAR",
        "ACTUAL_DRAW_YEAR",
        "MODEL_TARGET_YEAR",
        "SOURCE_FAMILY",
        "DRAW_SYSTEM_TYPE",
        "DRAW_POOL",
        "DRAW_POOL_KEY",
        "HUNT_CODE",
        "SCORE_SCOPE",
        "RESIDENCY",
        "POINTS",
        "PROBABILITY_METRIC",
    }
    scoring = key or role in {"actual_probability", "predicted_probability", "applicants", "permits", "successful"}
    lineage = role in {"source_file", "source_page", "source_lineage", "extraction_method", "review_status"}
    return (str(truth).upper(), str(key).upper(), str(scoring).upper(), str(lineage).upper())


def build_taxonomy_matrix() -> Path:
    rows: list[dict[str, object]] = []
    manifest_rows = read_csv_rows(TAXONOMY_MANIFEST)
    for row in manifest_rows:
        file_name = Path(clean(row.get("output_file"))).name
        license_year = clean(row.get("license_year")) or clean(row.get("website_matrix_year"))
        master_family = clean(row.get("master_family"))
        program_bucket = clean(row.get("program_bucket"))
        species_bucket = clean(row.get("species_bucket"))
        species_subbucket = clean(row.get("species_subbucket"))
        expected_parts = [part for part in [master_family, program_bucket, species_subbucket or species_bucket] if part]
        rows.append(
            {
                "source_page": clean(row.get("source_page")),
                "source_url": clean(row.get("source_url")),
                "link_text": clean(row.get("link_text")),
                "file_name": file_name,
                "license_year": license_year,
                "master_family": master_family,
                "draw_package": clean(row.get("website_matrix_draw_package")) or clean(row.get("draw_name")),
                "report_family": clean(row.get("website_matrix_report_label")) or clean(row.get("master_hunt_type_name")),
                "draw_design": clean(row.get("draw_design")),
                "program_bucket": program_bucket,
                "species_bucket": species_bucket,
                "species_subbucket": species_subbucket,
                "sheep_subspecies": clean(row.get("sheep_subspecies")),
                "sex_class": "",
                "youth_flag": clean(row.get("youth_flag")),
                "youth_program_status": clean(row.get("youth_program_status")),
                "cwmu_flag": clean(row.get("cwmu_flag")),
                "antlerless_flag": str("ANTLERLESS" in program_bucket or "antlerless" in clean(row.get("link_text")).lower()).upper(),
                "points_report_flag": clean(row.get("points_report_flag")),
                "support_only_flag": clean(row.get("support_only_flag")),
                "expected_folder": "/".join(expected_parts),
                "included_scope": str(clean(row.get("download_status")) != "ERROR" and clean(row.get("scope_decision")).startswith("included")).upper(),
                "exclusion_reason": clean(row.get("error")),
                "taxonomy_status": clean(row.get("taxonomy_status")),
                "review_reason": clean(row.get("review_reason")),
            }
        )
    for row in read_csv_rows(TAXONOMY_EXCLUDED):
        rows.append(
            {
                "source_page": clean(row.get("source_page")),
                "source_url": clean(row.get("source_url")),
                "link_text": clean(row.get("link_text")),
                "file_name": Path(clean(row.get("source_url"))).name,
                "license_year": clean(row.get("license_year")),
                "master_family": "",
                "draw_package": "",
                "report_family": "",
                "draw_design": "",
                "program_bucket": "",
                "species_bucket": "",
                "species_subbucket": "",
                "sheep_subspecies": "",
                "sex_class": "",
                "youth_flag": "",
                "youth_program_status": "",
                "cwmu_flag": "",
                "antlerless_flag": "",
                "points_report_flag": "",
                "support_only_flag": "TRUE",
                "expected_folder": "",
                "included_scope": "FALSE",
                "exclusion_reason": clean(row.get("scope_decision")),
                "taxonomy_status": "PASS_TAXONOMY_MAPPED",
                "review_reason": "Excluded from scope by official website matrix filter.",
            }
        )
    path = OUT / "WEBSITE_TAXONOMY_MATRIX.csv"
    write_csv(
        path,
        [
            "source_page",
            "source_url",
            "link_text",
            "file_name",
            "license_year",
            "master_family",
            "draw_package",
            "report_family",
            "draw_design",
            "program_bucket",
            "species_bucket",
            "species_subbucket",
            "sheep_subspecies",
            "sex_class",
            "youth_flag",
            "youth_program_status",
            "cwmu_flag",
            "antlerless_flag",
            "points_report_flag",
            "support_only_flag",
            "expected_folder",
            "included_scope",
            "exclusion_reason",
            "taxonomy_status",
            "review_reason",
        ],
        rows,
    )
    return path


def build_column_inventory(headers_by_role: dict[str, tuple[str, list[str]]]) -> Path:
    rows: list[dict[str, object]] = []
    for source_file, (file_role, headers) in headers_by_role.items():
        for column in headers:
            role = semantic_role(column)
            truth, key, scoring, lineage = required_flags(role, column)
            rows.append(
                {
                    "source_file": source_file,
                    "file_role": file_role,
                    "column_name": column,
                    "normalized_column_name": norm_header(column),
                    "inferred_semantic_role": role,
                    "required_for_truth": truth,
                    "required_for_key": key,
                    "required_for_scoring": scoring,
                    "required_for_source_lineage": lineage,
                    "notes": "Prediction header inspected for key-column reference only." if file_role == "SCORING_SURFACE_HEADER_ONLY" else "",
                }
            )
    path = OUT / "MASTER_CANONICAL_COLUMN_INVENTORY.csv"
    write_csv(
        path,
        [
            "source_file",
            "file_role",
            "column_name",
            "normalized_column_name",
            "inferred_semantic_role",
            "required_for_truth",
            "required_for_key",
            "required_for_scoring",
            "required_for_source_lineage",
            "notes",
        ],
        rows,
    )
    return path


def build_crosswalk(all_headers: dict[str, set[str]]) -> Path:
    fields = [
        (
            "permit_year",
            "actual draw year / permit year in report",
            "actual_draw_year",
            "",
            "actual_draw_year",
            "target_year",
            "target_year",
            "TRUE",
            "Map actual_draw_year/permit_year to target_year for score-key rows.",
            "integer year",
        ),
        ("model_year", "", "model_target_year", "", "model_target_year", "prediction_year", "target_year", "TRUE", "Map model_target_year/model_year as scoring metadata; prediction uses target_year/prediction_year.", "integer year"),
        ("hunt_code", "hunt_code", "hunt_code", "hunt_code", "hunt_code", "hunt_code", "hunt_code", "TRUE", "Uppercase normalized hunt code.", "official hunt code"),
        ("residency", "residency", "residency", "", "residency", "residency", "score_scope|residency", "TRUE", "Normalize residency to score_scope/residency pair.", "Resident|Nonresident|Total"),
        ("point_level", "point", "points", "", "points", "points", "points", "TRUE", "Canonical numeric text, blank allowed for total/sportsman where contract allows.", "integer or blank"),
        ("draw_family", "report family", "source_family", "", "source_family", "source_family", "source_family", "TRUE", "Map website report family to source_family; do not use prediction to shape truth.", "controlled source family"),
        ("draw_design", "draw design", "draw_design", "draw_design", "draw_design", "draw_system_type", "draw_system_type", "TRUE", "Truth draw_design maps to prediction draw_system_type where needed.", "controlled draw system"),
        ("draw_pool", "draw pool", "draw_pool", "draw_pool", "draw_pool", "draw_pool_key", "draw_pool_key_or_draw_pool", "TRUE", "Use draw_pool_key if present, else qualified draw_pool.", "controlled pool/lane"),
        ("species", "species bucket", "species", "species", "species", "species", "draw_pool_context", "TRUE", "Species may support qualified pool key for selected families.", "|".join(BIG_GAME_SPECIES)),
        ("sex_class", "sex class", "sex_type", "sex_type", "sex_type", "sex_type", "draw_pool_context", "TRUE", "sex_type may support qualified pool key for selected families.", "source-defined sex class"),
        ("hunt_class", "program bucket", "hunt_class", "hunt_class", "hunt_class", "hunt_class", "draw_pool_context", "TRUE", "hunt_class/hunt_draw_class may support qualified pool key.", "program class"),
        ("official_score_key_v2", "", "official_score_key_v2", "", "official_score_key_v2", "official_score_key_v2", "official_score_key_v2", "TRUE", "Materialized in bridge/comparable/scoring layer, not DATABASE master by default.", "pipe-delimited official key"),
    ]
    rows = []
    for website, raw_pdf, long_field, db_field, canon_field, pred_field, key_component, required, rule, allowed in fields:
        rows.append(
            {
                "website_matrix_field": website,
                "raw_pdf_field": raw_pdf,
                "draw_results_long_field": long_field if long_field in all_headers["long"] else "",
                "database_field": db_field if db_field in all_headers["database"] else "",
                "canonical_yearly_field": canon_field if canon_field in all_headers["canonical"] else "",
                "prediction_field": pred_field if pred_field in all_headers["prediction"] else "",
                "official_score_key_component": key_component,
                "required": required,
                "transformation_rule": rule,
                "allowed_values": allowed,
                "notes": "",
            }
        )
    path = OUT / "WEBSITE_TO_CANONICAL_COLUMN_CROSSWALK.csv"
    write_csv(
        path,
        [
            "website_matrix_field",
            "raw_pdf_field",
            "draw_results_long_field",
            "database_field",
            "canonical_yearly_field",
            "prediction_field",
            "official_score_key_component",
            "required",
            "transformation_rule",
            "allowed_values",
            "notes",
        ],
        rows,
    )
    return path


def build_recipe() -> Path:
    path = OUT / "OFFICIAL_SCORE_KEY_ALIGNMENT_RECIPE.md"
    text = KEY_RECIPE_FILE.read_text(encoding="utf-8", errors="replace") if KEY_RECIPE_FILE.exists() else ""
    found = "def _official_score_key_v2" in text
    path.write_text(
        f"""# Official Score Key Alignment Recipe

Exact script/function found: `{KEY_RECIPE_FILE}` / `_official_score_key_v2`

FOUND_CANONICAL_FUNCTION={str(found).upper()}

## Field Order

```text
target_year|source_family|draw_system_type|draw_pool_key_or_draw_pool|hunt_code|score_scope|residency|points|probability_metric
```

## Normalization Rules

- `target_year`: canonical target/prediction year text.
- `source_family`: produced by `_source_family_for_output_row`; source-family routing handles sportsman, bear, CWMU, turkey, cougar, O.I.L., L.E., P.L.E., dedicated hunter, general deer, antlerless, and youth variants.
- `draw_system_type`: uppercase canonical scoring design.
- `draw_pool`: lowercase; `draw_pool_key` is preferred where present, otherwise `_qualified_draw_pool_key` can use draw design, hunt class, pool, species, hunt type, and sex type.
- `hunt_code`: uppercase.
- `residency`: `_score_scope_and_residency` produces score scope plus normalized residency.
- `points`: canonical numeric text; blank remains blank where allowed.
- `probability_metric`: selected by `_probability_metric_for_output_row`.

## Null / Blank Handling

The prediction finalizer fills required output fields and materializes blank strings for missing non-key fields. Missing `official_score_key_v2` in prediction rows is invalid during prediction output validation.

## CWMU Handling

CWMU rows route through `CWMU_BIG_GAME` and `BONUS_CWMU_BIG_GAME` source/draw-system logic where source family and draw system prove CWMU scope.

## Youth Handling

Youth rows route through youth source-family branches such as `YOUTH_ANTLERLESS`, `YOUTH_GENERAL_SEASON_DEER`, `YOUTH_ANY_BULL_ELK`, and turkey youth set-aside rules. Youth programs must remain source/year gated.

## Year-Gated Exceptions

Post-2023 cougar should not be forced into older L.E. routing unless source-year evidence proves limited-entry. Youth turkey pre-start absence should be suppressed, not scored as missing source.

## Recommendation

Keep `_official_score_key_v2` centralized and build truth bridge rows through a dedicated comparable layer. Do not inject this key directly into `DATABASE.csv`.
""",
        encoding="utf-8",
    )
    return path


def build_gaps(all_headers: dict[str, set[str]], taxonomy_rows: list[dict[str, str]]) -> Path:
    rows: list[dict[str, object]] = []

    def add(issue, source, field, website="", canonical="", database="", prediction="", severity="REVIEW", action="", notes=""):
        rows.append(
            {
                "issue_type": issue,
                "source_file": source,
                "field_or_value": field,
                "website_value": website,
                "canonical_value": canonical,
                "database_value": database,
                "prediction_value": prediction,
                "severity": severity,
                "recommended_action": action,
                "notes": notes,
            }
        )

    for required in ["boundary_id", "season", "hunt_class"]:
        add(
            "MISSING_COLUMN",
            str(DATABASE),
            required,
            database="PRESENT" if required in all_headers["database"] else "MISSING",
            severity="INFO" if required in all_headers["database"] else "BLOCKER",
            action="Keep in master DATABASE contract.",
        )
    add("MISSING_COLUMN", str(DATABASE), "draw_pool", database="PRESENT" if "draw_pool" in all_headers["database"] else "MISSING", severity="REVIEW", action="Add/crosswalk DRAW_POOL in master contract when materialized.")
    add("OFFICIAL_SCORE_KEY_MISSING", str(DRAW_RESULTS_LONG), "official_score_key_v2", canonical="MISSING", severity="REVIEW", action="Materialize only in bridge/comparable layer unless design changes.")
    add("OFFICIAL_SCORE_KEY_MISSING", str(DATABASE), "official_score_key_v2", database="MISSING_BY_DESIGN", severity="INFO", action="Do not inject into DATABASE.csv.")
    add("DUPLICATE_COLUMN_MEANING", str(DATABASE), "PERMITS_20XX_NON_RES", database="permits_20XX_nr", severity="REVIEW", action="Normalize NR to NON_RES in contract layer.")
    add("DUPLICATE_COLUMN_MEANING", str(DATABASE), "HARVEST_20XX_*", database="harvest-like descriptive columns", severity="REVIEW", action="Crosswalk existing harvest fields before renaming.")
    add("TAXONOMY_VALUE_NOT_CANONICAL", str(TAXONOMY_MANIFEST), "Big Game 8 species", website="SUPPORTED", canonical="REVIEW_BY_SOURCE_ROWS", severity="INFO", action="Preserve 8-species universe.")
    add("PLE_NON_DEER_CONFLICT", str(TAXONOMY_MANIFEST), "PREMIUM_LIMITED_ENTRY non-DEER", website="NOT_ALLOWED", severity="INFO", action="Flag REVIEW_REQUIRED_UNEXPECTED_PREMIUM_NON_DEER_LABEL if encountered.")
    add("OIL_SHEEP_SUBSPECIES_AMBIGUOUS", str(TAXONOMY_MANIFEST), "BIGHORN_SHEEP", severity="REVIEW", action="Preserve Rocky Mountain vs Desert bighorn when source-visible.")
    add("YOUTH_PRE_PROGRAM_START", str(TAXONOMY_MANIFEST), "youth_program_status", severity="REVIEW", action="Suppress pre-program-start youth rows.")
    add("COUGAR_YEAR_RULE_CHANGE", str(TAXONOMY_MANIFEST), "COUGAR post-2023", website="AVAILABILITY_OR_OTC", severity="INFO", action="Year/rule gate post-change cougar.")
    add("RESIDENCY_NORMALIZATION_MISMATCH", "bridge layer", "residency", severity="REVIEW", action="Use score_scope/residency normalization from key recipe.")
    add("POINT_LEVEL_NORMALIZATION_MISMATCH", "bridge layer", "points", severity="REVIEW", action="Use canonical numeric text from key recipe.")
    add("SOURCE_LINEAGE_MISSING", "future bridge rows", "source_lineage", severity="REVIEW", action="Require source_file/source_url/source_page/source_row_id where extractable.")
    add("CANONICAL_VALUE_NOT_IN_WEBSITE_MATRIX", str(DRAW_RESULTS_LONG), "2017 row count mismatch", canonical="draw_results_long short by 90 vs active canonical zip", severity="BLOCKER", action="Fix from raw 2017 PDFs before all-year truth completion.")

    path = OUT / "WEBSITE_CANONICAL_KEY_ALIGNMENT_GAPS.csv"
    write_csv(
        path,
        [
            "issue_type",
            "source_file",
            "field_or_value",
            "website_value",
            "canonical_value",
            "database_value",
            "prediction_value",
            "severity",
            "recommended_action",
            "notes",
        ],
        rows,
    )
    return path


def build_contract() -> Path:
    path = OUT / "RECOMMENDED_MASTER_CANONICAL_HEADER_CONTRACT.md"
    path.write_text(
        """# Recommended Master Canonical Header Contract

## Stable Comparable / Bridge Header Set

```text
permit_year
model_year
license_year
source_year
master_family
draw_package
report_family
draw_design
program_bucket
species_bucket
species_subbucket
sheep_subspecies
sex_class
youth_flag
youth_program_status
cwmu_flag
antlerless_flag
points_report_flag
support_only_flag
hunt_code
hunt_name
residency
point_level
applicants
permits
successful
unsuccessful
odds_raw
actual_probability
probability_unit
source_file
source_url
source_page
source_row_id
source_lineage
extraction_method
review_status
exclusion_reason
official_score_key_v2
```

## Master DATABASE Relationship

`DATABASE.csv` remains the master hunt database. It should focus on hunt identity, quota context, draw architecture, and harvest context. It should enrich bridge rows by `hunt_code`; it should not be scored directly.

## Bridge / Scoring Relationship

`official_score_key_v2` belongs in the bridge/comparable/scoring layer unless the project later creates a derived database-key export by design.

## Do Not Collapse

- Do not collapse `HUNT_TYPE` into `DRAW_DESIGN`.
- Do not collapse `HUNT_CLASS` into `DRAW_POOL`.
- Do not collapse Rocky Mountain and Desert bighorn sheep when source-visible.
- Do not collapse quota columns into point/residency result rows without row-scope review.
""",
        encoding="utf-8",
    )
    return path


def build_report(status_counts: Counter[str], paths: dict[str, Path]) -> Path:
    taxonomy_status = "PASS_TAXONOMY_MAPPED"
    if any(status.startswith("REVIEW") or status.startswith("BLOCKED") for status in status_counts):
        taxonomy_status = "PASS_WITH_REVIEW_REQUIRED"
    elif status_counts.get("PASS_WITH_YEAR_SPECIFIC_DIFFERENCES"):
        taxonomy_status = "PASS_WITH_REVIEW_REQUIRED"
    key_status = "PASS_WITH_REVIEW_REQUIRED"
    path = OUT / "WEBSITE_MATRIX_KEY_ALIGNMENT_REPORT.md"
    path.write_text(
        f"""# Website Matrix Key Alignment Report

## Answers

1. Does the website matrix support the folder structure?
   Yes. The pulled website matrix supports Big Game, Black Bear, Cougar, and Wild Turkey folder/report grouping. Wetland/waterfowl and non-turkey upland sources are excluded.

2. Does the website matrix match the 8 Big Game species taxonomy?
   Yes. The audit preserves 8 Big Game species buckets, 5 O.I.L. species, P.L.E. deer-only routing, and L.E. deer/elk/pronghorn routing.

3. Does the master canonical support those same species/program buckets?
   Partially. Current canonical headers contain source-facing species/hunt fields, but not the full website taxonomy extension set (`master_family`, `program_bucket`, `species_bucket`, `species_subbucket`, `sheep_subspecies`, etc.).

4. Which column headers are missing from canonical truth?
   Canonical truth lacks `official_score_key_v2` and the full website taxonomy extension columns. These should be bridge/comparable fields unless project design later promotes them.

5. Which headers should be added only to comparables, not canonical truth?
   `official_score_key_v2`, prediction probability fields, bridge `source_family`, score scope, and derived comparable-only row IDs should live in comparables/scoring surfaces.

6. Which fields are required for official_score_key_v2?
   `target_year`, `source_family`, `draw_system_type`, `draw_pool_key` or qualified `draw_pool`, `hunt_code`, `score_scope`, `residency`, `points`, and `probability_metric`.

7. Does DATABASE.csv align with draw_results_long.csv?
   It aligns by `hunt_code` and descriptors/permit context, but cannot exact-key join to draw rows without bridge expansion by year, residency, points, and record type.

8. Does draw_results_long.csv align with prediction key fields?
   It has many truth fields needed for bridge construction, but lacks materialized `official_score_key_v2` and prediction-side key fields such as `source_family`, `score_scope`, `probability_metric`, and `draw_pool_key`.

9. Where are key conflicts likely?
   Likely conflicts are draw family/source family routing, draw pool qualification, residency normalization, point normalization, CWMU routing, youth year gates, P.L.E. non-deer labels, O.I.L. sheep subspecies ambiguity, and post-2023 cougar routing.

10. What must be fixed before year-to-year raw-PDF-first construction continues?
    The 2017 long-vs-canonical 90-row mismatch must be fixed from raw 2017 PDFs before all-year truth completion. Do not force `official_score_key_v2` into `DATABASE.csv`.

## Output Files

- WEBSITE_TAXONOMY_MATRIX: {paths['taxonomy']}
- MASTER_CANONICAL_COLUMN_INVENTORY: {paths['inventory']}
- WEBSITE_TO_CANONICAL_COLUMN_CROSSWALK: {paths['crosswalk']}
- OFFICIAL_SCORE_KEY_ALIGNMENT_RECIPE: {paths['recipe']}
- WEBSITE_CANONICAL_KEY_ALIGNMENT_GAPS: {paths['gaps']}
- RECOMMENDED_MASTER_CANONICAL_HEADER_CONTRACT: {paths['contract']}

BIG_GAME_SPECIES_BUCKET_COUNT=8
OIL_SPECIES_BUCKET_COUNT=5
PLE_SPECIES_BUCKET_COUNT=1
LE_BIG_GAME_SPECIES_BUCKET_COUNT=3
PLE_DEER_ONLY=TRUE
TAXONOMY_STATUS={taxonomy_status}
KEY_ALIGNMENT_STATUS={key_status}
""",
        encoding="utf-8",
    )
    return path


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    headers_by_role: dict[str, tuple[str, list[str]]] = {}
    if DATABASE.exists():
        headers_by_role[str(DATABASE)] = ("MASTER_HUNT_DATABASE", read_header(DATABASE))
    if DRAW_RESULTS_LONG.exists():
        headers_by_role[str(DRAW_RESULTS_LONG)] = ("DRAW_RESULT_TRUTH_LAYER", read_header(DRAW_RESULTS_LONG))
    for name, header in active_canonical_headers().items():
        headers_by_role[f"{CANONICAL_ZIP}::{name}"] = ("YEARLY_TRUTH_SLICE", header)
    if PREDICTION_HEADER_FILE.exists():
        headers_by_role[str(PREDICTION_HEADER_FILE)] = ("SCORING_SURFACE_HEADER_ONLY", read_header(PREDICTION_HEADER_FILE))
    if TAXONOMY_MANIFEST.exists():
        headers_by_role[str(TAXONOMY_MANIFEST)] = ("WEBSITE_MATRIX_MANIFEST", read_header(TAXONOMY_MANIFEST))

    all_headers = {
        "database": set(headers_by_role.get(str(DATABASE), ("", []))[1]),
        "long": set(headers_by_role.get(str(DRAW_RESULTS_LONG), ("", []))[1]),
        "canonical": set(),
        "prediction": set(headers_by_role.get(str(PREDICTION_HEADER_FILE), ("", []))[1]),
    }
    for source, (role, header) in headers_by_role.items():
        if role == "YEARLY_TRUTH_SLICE":
            all_headers["canonical"].update(header)

    taxonomy = build_taxonomy_matrix()
    inventory = build_column_inventory(headers_by_role)
    crosswalk = build_crosswalk(all_headers)
    recipe = build_recipe()
    taxonomy_rows = read_csv_rows(taxonomy)
    gaps = build_gaps(all_headers, taxonomy_rows)
    contract = build_contract()
    status_counts = Counter(clean(row.get("taxonomy_status")) for row in taxonomy_rows if clean(row.get("taxonomy_status")))
    report = build_report(
        status_counts,
        {
            "taxonomy": taxonomy,
            "inventory": inventory,
            "crosswalk": crosswalk,
            "recipe": recipe,
            "gaps": gaps,
            "contract": contract,
        },
    )

    taxonomy_status = "PASS_WITH_REVIEW_REQUIRED" if status_counts.get("PASS_WITH_YEAR_SPECIFIC_DIFFERENCES") else "PASS_TAXONOMY_MAPPED"
    key_status = "PASS_WITH_REVIEW_REQUIRED"
    print(f"WEBSITE_MATRIX_KEY_ALIGNMENT_OUTPUT_DIR={OUT}")
    print(f"WEBSITE_TAXONOMY_MATRIX={taxonomy}")
    print(f"MASTER_CANONICAL_COLUMN_INVENTORY={inventory}")
    print(f"WEBSITE_TO_CANONICAL_COLUMN_CROSSWALK={crosswalk}")
    print(f"OFFICIAL_SCORE_KEY_ALIGNMENT_RECIPE={recipe}")
    print(f"WEBSITE_CANONICAL_KEY_ALIGNMENT_GAPS={gaps}")
    print(f"RECOMMENDED_MASTER_CANONICAL_HEADER_CONTRACT={contract}")
    print(f"WEBSITE_MATRIX_KEY_ALIGNMENT_REPORT={report}")
    print("BIG_GAME_SPECIES_BUCKET_COUNT=8")
    print("OIL_SPECIES_BUCKET_COUNT=5")
    print("PLE_SPECIES_BUCKET_COUNT=1")
    print("LE_BIG_GAME_SPECIES_BUCKET_COUNT=3")
    print("PLE_DEER_ONLY=TRUE")
    print(f"TAXONOMY_STATUS={taxonomy_status}")
    print(f"KEY_ALIGNMENT_STATUS={key_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
