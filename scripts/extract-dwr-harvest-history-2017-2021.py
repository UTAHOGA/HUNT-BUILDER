"""Extract and normalize official Utah DWR harvest history for 2017-2021.

The 2017-2020 source PDFs use three stable table families:

* general-season buck deer;
* limited-entry and once-in-a-lifetime species; and
* antlerless big game.

The 2021 source package is already parsed and hunt-code aggregated. This script
maps its year-specific feature columns into the canonical harvest schema.

All output rows are harvest-quality features only. They must never be used as
draw-permit quota or direct draw-probability truth.
"""

from __future__ import annotations

import csv
import hashlib
import itertools
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import pdfplumber


ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "pipeline" / "RAW" / "hunt_unit_database"
OUT_ROOT = ROOT / "data_truth" / "harvest_results_truth" / "sources"
OUT_LONG = OUT_ROOT / "dwr_official_harvest_history_2017_2020_long.csv"
OUT_NORMALIZED = OUT_ROOT / "dwr_official_harvest_history_2017_2021_normalized.csv"
OUT_SUMMARY = OUT_ROOT / "dwr_official_harvest_history_2017_2021_summary.json"

PACKAGE_2021 = (
    ROOT
    / "data_model"
    / "harvest_quality"
    / "raw_packages"
    / "2021_for_2022_harvest_results_2021_for_2022_database"
    / "harvest_quality_features_by_hunt_code_2021_for_2022.csv"
)

PDF_SOURCES = {
    2017: {
        "general": RAW_ROOT / "2017/pdf/harvest_report/35263124__General-season buck deer.pdf",
        "limited": RAW_ROOT / "2017/pdf/harvest_report/c1e4809e__Limited-entry and once-in-a-lifetime species.pdf",
        "antlerless": RAW_ROOT / "2017/pdf/harvest_report/bc5511e8__Antlerless big game.pdf",
    },
    2018: {
        "general": RAW_ROOT / "2018/pdf/harvest_report/2251affc__harvest_report.pdf",
        "limited": RAW_ROOT / "2018/pdf/harvest_report/f0bc038b__harvest_report.pdf",
        "antlerless": RAW_ROOT / "2018/pdf/harvest_report/3605c429__harvest_report.pdf",
    },
    2019: {
        "general": RAW_ROOT / "2019/pdf/harvest_report/3707480f__General-season buck deer.pdf",
        "limited": RAW_ROOT / "2019/pdf/harvest_report/e764d19f__Limited-entry and once-in-a-lifetime species.pdf",
        "antlerless": RAW_ROOT / "2019/pdf/harvest_report/50b32b02__Antlerless big game.pdf",
    },
    2020: {
        "general": RAW_ROOT / "2020/pdf/harvest_report/e38eeb18__General-season buck deer.pdf",
        "limited": RAW_ROOT / "2020/pdf/harvest_report/0b5ca51c__Limited-entry and once-in-a-lifetime species.pdf",
        "antlerless": RAW_ROOT / "2020/pdf/harvest_report/4275246d__Antlerless big game.pdf",
    },
}

CANONICAL_FIELDS = [
    "reported_hunt_year",
    "model_target_year",
    "hunt_code",
    "species",
    "sex_type",
    "hunt_name",
    "hunt_type",
    "weapon",
    "permits",
    "hunters_afield",
    "harvest_total",
    "harvest_male",
    "harvest_female",
    "harvest_young",
    "harvest_unknown",
    "percent_success",
    "average_days",
    "hunter_satisfaction",
    "average_age",
    "average_age_3yr_reported",
    "average_age_source_file",
    "average_age_source_page",
    "average_age_source_table_title",
    "average_age_crosswalk_confidence",
    "average_age_mapping_status",
    "male_harvest",
    "female_harvest",
    "harvest_objective",
    "source_file",
    "source_page",
    "source_container",
    "source_member",
    "source_kind",
    "source_priority",
    "source_status",
    "parse_status",
    "do_not_use_for_permit_quota",
    "do_not_use_directly_for_p_draw",
    "trend_feature_eligible",
    "data_quality_flags",
    "recommended_use",
]

LONG_FIELDS = CANONICAL_FIELDS + ["source_sha256", "source_table_family", "raw_line"]
HUNT_CODE_RE = re.compile(r"\b[A-Z]{2}\d{4}\b")
VALUE = r"(?:--|[-–—�]|\d[\d,]*(?:\.\d+)?)"

SPECIES_BY_PREFIX = {
    "BI": "Bison",
    "DA": "Deer",
    "DB": "Deer",
    "DS": "Desert Bighorn Sheep",
    "EA": "Elk",
    "EB": "Elk",
    "GO": "Mountain Goat",
    "MA": "Moose",
    "MB": "Moose",
    "PB": "Pronghorn",
    "PD": "Pronghorn",
    "RS": "Rocky Mountain Bighorn Sheep",
}

GENERAL_SUFFIXES = [
    ("Dedicated Hunter", "Dedicated Hunter", "Multiple"),
    ("General Season Youth** Early Any Legal Weapon", "General Season Early Youth", "Any Legal Weapon"),
    ("General Season Youth** Early Any Weapon", "General Season Early Youth", "Any Weapon"),
    ("General Season Early Any Legal Weapon", "General Season Early", "Any Legal Weapon"),
    ("General Season Early Any Weapon", "General Season Early", "Any Weapon"),
    ("Early Any Weapon (youth)**", "General Season Early Youth", "Any Weapon"),
    ("Early Any Legal Weapon (youth)**", "General Season Early Youth", "Any Legal Weapon"),
    ("Any Weapon (youth)**", "General Season Youth", "Any Weapon"),
    ("Any Legal Weapon (youth)**", "General Season Youth", "Any Legal Weapon"),
    ("General Season Youth** Any Legal Weapon", "General Season Youth", "Any Legal Weapon"),
    ("General Season Youth** Any Weapon", "General Season Youth", "Any Weapon"),
    ("General Season Any Legal Weapon", "General Season", "Any Legal Weapon"),
    ("General Season Any Weapon", "General Season", "Any Weapon"),
    ("General Season Muzzleloader", "General Season", "Muzzleloader"),
    ("General Season Archery", "General Season", "Archery"),
    ("Early Any Legal Weapon", "General Season Early", "Any Legal Weapon"),
    ("Early Any Weapon", "General Season Early", "Any Weapon"),
    ("Muzzleloader", "General Season", "Muzzleloader"),
    ("Any Legal Weapon", "General Season", "Any Legal Weapon"),
    ("Any Weapon", "General Season", "Any Weapon"),
    ("Archery", "General Season", "Archery"),
]

LIMITED_SUFFIXES = [
    "Sportsman/Conservation",
    "Management Buck",
    "Cactus Buck",
    "Premium Limited Entry",
    "Limited Entry",
    "Multi-season",
    "Muzzleloader Management",
    "Any Weapon Management",
    "Any weapon Management",
    "Archery Management",
    "Muzzleloader",
    "Any Legal Weapon",
    "Any Weapon",
    "Any weapon",
    "Archery",
    "Management",
    "Conservation",
    "Sportsman",
    "CWMU",
    "OIAL",
]


def clean_number(value: str | None) -> str:
    text = str(value or "").strip().replace(",", "")
    if not text or text in {"--", "-", "–", "—", "�"}:
        return ""
    try:
        number = float(text)
    except ValueError:
        return ""
    if number.is_integer():
        return str(int(number))
    return f"{number:.4f}".rstrip("0").rstrip(".")


def mean(values: list[str]) -> str:
    numbers = [float(value) for value in values if value != ""]
    if not numbers:
        return ""
    return f"{sum(numbers) / len(numbers):.4f}".rstrip("0").rstrip(".")


def total(values: list[str]) -> str:
    numbers = [float(value) for value in values if value != ""]
    if not numbers:
        return ""
    summed = sum(numbers)
    return str(int(summed)) if summed.is_integer() else f"{summed:.4f}".rstrip("0").rstrip(".")


def species_for_code(code: str) -> str:
    prefix = code[:2].upper()
    if prefix not in SPECIES_BY_PREFIX:
        raise ValueError(f"Unknown harvest hunt-code prefix: {code}")
    return SPECIES_BY_PREFIX[prefix]


def sex_type_for_code(code: str) -> str:
    return "Antlerless" if code[:2].upper() in {"DA", "EA", "MA", "PD"} else ""


@lru_cache(maxsize=None)
def file_sha256(source: Path) -> str:
    return hashlib.sha256(source.read_bytes()).hexdigest()


def split_tail(line: str, count: int) -> tuple[str, list[str]] | None:
    pattern = re.compile(rf"^(?P<body>.*?)\s+(?P<tail>{VALUE}(?:\s+{VALUE}){{{count - 1}}})\s*$")
    match = pattern.match(line.strip())
    if not match:
        return None
    return match.group("body").strip(), match.group("tail").split()


def limited_metric_score(values: list[str], sex_breakdown: bool) -> float:
    cleaned = [clean_number(value) for value in values]
    if any(value == "" for value in cleaned):
        return -1_000_000
    numbers = [float(value) for value in cleaned]
    permits, hunters, harvest = numbers[:3]
    average_days, success, satisfaction = numbers[-3:]
    if not (0 <= average_days <= 60 and 0 <= success <= 100 and 0 <= satisfaction <= 5):
        return -1_000_000
    score = 0.0
    if hunters <= permits:
        score += 20
    if harvest <= hunters:
        score += 10
    if hunters > 0:
        score -= abs(success - (100 * harvest / hunters))
    if sex_breakdown:
        male, female = numbers[3:5]
        score -= abs(harvest - (male + female))
    return score


def split_limited_tail(line: str, count: int, sex_breakdown: bool) -> tuple[str, list[str]] | None:
    tokens = line.strip().split()
    numeric_start = len(tokens)
    while numeric_start > 0 and re.fullmatch(VALUE, tokens[numeric_start - 1]):
        numeric_start -= 1
    body_tokens = tokens[:numeric_start]
    numeric_tokens = tokens[numeric_start:]
    if len(numeric_tokens) < count:
        return None
    if len(numeric_tokens) == count:
        return " ".join(body_tokens), numeric_tokens

    extras = len(numeric_tokens) - count
    if extras > 3:
        return None
    if extras == 1:
        for index in range(len(numeric_tokens) - 1):
            left = numeric_tokens[index]
            right = numeric_tokens[index + 1]
            if "." in left and len(right) == 1 and left.endswith(right):
                candidate = numeric_tokens[: index + 1] + numeric_tokens[index + 2 :]
                if limited_metric_score(candidate, sex_breakdown) > -1_000_000:
                    return " ".join(body_tokens), candidate
    candidates: list[tuple[float, list[str]]] = []
    for remove_indexes in itertools.combinations(range(len(numeric_tokens)), extras):
        kept = [value for index, value in enumerate(numeric_tokens) if index not in remove_indexes]
        score = limited_metric_score(kept, sex_breakdown)
        candidates.append((score, kept))
    score, best = max(candidates, key=lambda item: item[0])
    if score <= -1_000_000:
        return None
    return " ".join(body_tokens), best


def strip_general_identity(body: str, year: int) -> tuple[str, str, str]:
    if year <= 2020:
        body = re.sub(r"\s+(?:\d+[A-Z]?(?:/\d+[A-Z]?)*|ALL)$", "", body, flags=re.IGNORECASE).strip()
    folded = body.casefold()
    for suffix, hunt_type, weapon in GENERAL_SUFFIXES:
        if folded.endswith(suffix.casefold()):
            name = body[: -len(suffix)].strip()
            return name, hunt_type, weapon
    raise ValueError(f"Unrecognized general-season identity suffix: {body}")


def strip_limited_identity(body: str) -> tuple[str, str]:
    body = re.sub(r"\bA\s+ny\b", "Any", body, flags=re.IGNORECASE)
    folded = body.casefold()
    for suffix in LIMITED_SUFFIXES:
        if folded.endswith(suffix.casefold()):
            return body[: -len(suffix)].strip(), suffix.replace("weapon", "Weapon")
    raise ValueError(f"Unrecognized limited-entry identity suffix: {body}")


def base_row(year: int, code: str, source: Path, page: int, family: str, raw_line: str) -> dict[str, str]:
    row = {field: "" for field in LONG_FIELDS}
    row.update(
        {
            "reported_hunt_year": str(year),
            "model_target_year": str(year + 1),
            "hunt_code": code,
            "species": species_for_code(code),
            "sex_type": sex_type_for_code(code),
            "source_file": source.name,
            "source_page": str(page),
            "source_container": str(source.relative_to(ROOT)),
            "source_kind": "official_dwr_harvest_pdf_text_extract",
            "source_priority": "115",
            "source_status": "official_dwr_pdf_current_hash_verified_2026_09_06",
            "parse_status": "OFFICIAL_PDF_SCHEMA_PARSED",
            "do_not_use_for_permit_quota": "True",
            "do_not_use_directly_for_p_draw": "True",
            "trend_feature_eligible": "True",
            "data_quality_flags": "OFFICIAL_DWR_PDF|HUNT_CODE_ROW_EXTRACTED|SOURCE_LINE_PRESERVED",
            "recommended_use": "harvest quality, demand-signal, and backcheck features only; do not use as permit quota or direct draw probability",
            "source_sha256": file_sha256(source),
            "source_table_family": family,
            "raw_line": raw_line.strip(),
        }
    )
    return row


def parse_data_line(year: int, family: str, source: Path, page_number: int, page_text: str, line: str) -> dict[str, str] | None:
    code_match = HUNT_CODE_RE.search(line)
    if not code_match:
        return None
    code = code_match.group(0).upper()
    after_code = line[code_match.end() :].strip()
    after_code = re.sub(r"(?<=\d)\s+\.(?=\d)", ".", after_code)
    row = base_row(year, code, source, page_number, family, line)

    if "no data" in after_code.casefold() or "data not yet available" in after_code.casefold():
        match = re.match(
            rf"^(?P<body>.*?)\s+(?P<permits>{VALUE})\s+(?:No data|Late hunt\s+-\s+data not yet available)\s*$",
            after_code,
            re.IGNORECASE,
        )
        if not match:
            return None
        identity = match.group("body").strip()
        row["permits"] = clean_number(match.group("permits"))
        row["parse_status"] = "OFFICIAL_PDF_NO_DATA_ROW"
        row["data_quality_flags"] += "|SOURCE_REPORTED_NO_DATA"
        if family == "general":
            row["hunt_name"], row["hunt_type"], row["weapon"] = strip_general_identity(identity, year)
        elif family == "limited":
            row["hunt_name"], row["hunt_type"] = strip_limited_identity(identity)
        else:
            row["hunt_name"] = re.sub(r"\s+CWMU$", "", identity, flags=re.IGNORECASE).strip()
            row["hunt_type"] = "CWMU" if identity.casefold().endswith(" cwmu") else "Antlerless"
        return row

    if family == "general":
        split = split_tail(after_code, 5)
        if not split:
            return None
        identity, values = split
        row["hunt_name"], row["hunt_type"], row["weapon"] = strip_general_identity(identity, year)
        row["permits"], row["hunters_afield"], row["harvest_total"], row["percent_success"], row["hunter_satisfaction"] = map(clean_number, values)
        return row

    if family == "antlerless":
        split = split_tail(after_code, 5)
        if not split:
            short = split_tail(after_code, 2)
            if not short:
                return None
            identity, values = short
            row["hunt_name"] = re.sub(r"\s+CWMU$", "", identity, flags=re.IGNORECASE).strip()
            row["hunt_type"] = "CWMU" if identity.casefold().endswith(" cwmu") else "Antlerless"
            row["permits"], row["hunters_afield"] = map(clean_number, values)
            row["parse_status"] = "OFFICIAL_PDF_ZERO_HUNTERS_ROW"
            row["data_quality_flags"] += "|SOURCE_REPORTED_ZERO_HUNTERS_NO_HARVEST_METRICS"
            return row
        identity, values = split
        row["hunt_name"] = re.sub(r"\s+CWMU$", "", identity, flags=re.IGNORECASE).strip()
        row["hunt_type"] = "CWMU" if identity.casefold().endswith(" cwmu") else "Antlerless"
        row["permits"], row["hunters_afield"], row["harvest_total"], row["average_days"], row["percent_success"] = map(clean_number, values)
        return row

    header_text = " ".join(page_text.splitlines()[:5]).casefold()
    sex_breakdown = "male" in header_text and "female" in header_text
    split = split_limited_tail(after_code, 8 if sex_breakdown else 6, sex_breakdown)
    if not split:
        return None
    identity, values = split
    row["hunt_name"], row["hunt_type"] = strip_limited_identity(identity)
    if sex_breakdown:
        (
            row["permits"],
            row["hunters_afield"],
            row["harvest_total"],
            row["harvest_male"],
            row["harvest_female"],
            row["average_days"],
            row["percent_success"],
            row["hunter_satisfaction"],
        ) = map(clean_number, values)
    else:
        (
            row["permits"],
            row["hunters_afield"],
            row["harvest_total"],
            row["average_days"],
            row["percent_success"],
            row["hunter_satisfaction"],
        ) = map(clean_number, values)
    return row


def parse_pdf(year: int, family: str, source: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with pdfplumber.open(source) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            for line in page_text.splitlines():
                parsed = parse_data_line(year, family, source, page_number, page_text, line)
                if parsed:
                    rows.append(parsed)
    if not rows:
        raise RuntimeError(f"No harvest rows parsed from {source}")
    return rows


def aggregate_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[(row["reported_hunt_year"], row["hunt_code"])].append(row)

    output: list[dict[str, str]] = []
    for key in sorted(groups):
        items = groups[key]
        names = {item["hunt_name"].casefold(): item["hunt_name"] for item in items if item["hunt_name"]}
        if len(names) > 1:
            raise ValueError(f"Conflicting hunt names for {key}: {sorted(names.values())}")
        species = {item["species"] for item in items}
        if len(species) != 1:
            raise ValueError(f"Conflicting species for {key}: {sorted(species)}")

        row = {field: "" for field in CANONICAL_FIELDS}
        row.update(
            {
                "reported_hunt_year": key[0],
                "model_target_year": str(int(key[0]) + 1),
                "hunt_code": key[1],
                "species": next(iter(species)),
                "sex_type": next((item["sex_type"] for item in items if item["sex_type"]), ""),
                "hunt_name": next(iter(names.values()), ""),
                "hunt_type": "|".join(sorted({item["hunt_type"] for item in items if item["hunt_type"]})),
                "weapon": "|".join(sorted({item["weapon"] for item in items if item["weapon"]})),
                "permits": total([item["permits"] for item in items]),
                "hunters_afield": total([item["hunters_afield"] for item in items]),
                "harvest_total": total([item["harvest_total"] for item in items]),
                "harvest_male": total([item["harvest_male"] for item in items]),
                "harvest_female": total([item["harvest_female"] for item in items]),
                "percent_success": mean([item["percent_success"] for item in items]),
                "average_days": mean([item["average_days"] for item in items]),
                "hunter_satisfaction": mean([item["hunter_satisfaction"] for item in items]),
                "source_file": "|".join(sorted({item["source_file"] for item in items})),
                "source_page": "|".join(sorted({item["source_page"] for item in items}, key=int)),
                "source_container": "|".join(sorted({item["source_container"] for item in items})),
                "source_kind": "official_dwr_harvest_pdf_hunt_code_aggregate",
                "source_priority": "115",
                "source_status": "official_dwr_pdf_current_hash_verified_2026_09_06",
                "parse_status": "OFFICIAL_PDF_HUNT_CODE_AGGREGATED",
                "do_not_use_for_permit_quota": "True",
                "do_not_use_directly_for_p_draw": "True",
                "trend_feature_eligible": "True",
                "data_quality_flags": "OFFICIAL_DWR_PDF|HUNT_CODE_AGGREGATED|REPORT_SUBROWS_SUMMED|RATE_AND_EFFORT_FIELDS_MEAN",
                "recommended_use": "harvest quality, demand-signal, and backcheck features only; do not use as permit quota or direct draw probability",
            }
        )
        output.append(row)
    return output


def load_2021_repairs() -> list[dict[str, str]]:
    with PACKAGE_2021.open(newline="", encoding="utf-8-sig") as handle:
        source_rows = list(csv.DictReader(handle))
    output: list[dict[str, str]] = []
    for source in source_rows:
        row = {field: "" for field in CANONICAL_FIELDS}
        row.update(
            {
                "reported_hunt_year": "2021",
                "model_target_year": "2022",
                "hunt_code": source["hunt_code"].strip().upper(),
                "species": source["species"].strip(),
                "hunt_name": source["hunt_name"].strip(),
                "permits": clean_number(source.get("harvest_permits_2021_sum")),
                "hunters_afield": clean_number(source.get("harvest_hunters_afield_2021_sum")),
                "harvest_total": clean_number(source.get("harvest_2021_sum")),
                "percent_success": clean_number(source.get("harvest_success_percent_2021_mean")),
                "average_days": clean_number(source.get("harvest_average_days_2021_mean")),
                "source_file": source.get("harvest_source_files_2021", "").strip(),
                "source_container": str(PACKAGE_2021.relative_to(ROOT)),
                "source_kind": "official_dwr_2021_package_mapping_repair",
                "source_priority": "115",
                "source_status": "official_dwr_annual_report_package",
                "parse_status": "YEAR_SPECIFIC_FEATURE_COLUMNS_MAPPED",
                "do_not_use_for_permit_quota": "True",
                "do_not_use_directly_for_p_draw": "True",
                "trend_feature_eligible": "True",
                "data_quality_flags": source.get("harvest_quality_flags_2021", "").strip()
                + "|CANONICAL_2021_FIELD_MAPPING_REPAIRED",
                "recommended_use": "harvest quality, demand-signal, and backcheck features only; do not use as permit quota or direct draw probability",
            }
        )
        output.append(row)
    return output


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    required = [path for sources in PDF_SOURCES.values() for path in sources.values()] + [PACKAGE_2021]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required harvest sources: {missing}")

    long_rows: list[dict[str, str]] = []
    source_counts: dict[str, dict[str, int]] = {}
    for year, sources in PDF_SOURCES.items():
        source_counts[str(year)] = {}
        for family, source in sources.items():
            parsed = parse_pdf(year, family, source)
            long_rows.extend(parsed)
            source_counts[str(year)][family] = len(parsed)

    normalized_rows = aggregate_rows(long_rows)
    repairs_2021 = load_2021_repairs()
    normalized_rows.extend(repairs_2021)
    normalized_rows.sort(key=lambda row: (row["reported_hunt_year"], row["hunt_code"]))

    write_csv(OUT_LONG, long_rows, LONG_FIELDS)
    write_csv(OUT_NORMALIZED, normalized_rows, CANONICAL_FIELDS)

    year_rows = defaultdict(list)
    for row in normalized_rows:
        year_rows[row["reported_hunt_year"]].append(row)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "official Utah DWR big-game harvest history for 2017-2021",
        "source_pdf_count_2017_2020": sum(len(sources) for sources in PDF_SOURCES.values()),
        "source_pdf_sha256": {
            str(path.relative_to(ROOT)): file_sha256(path)
            for sources in PDF_SOURCES.values()
            for path in sources.values()
        },
        "source_line_rows_by_year_and_family": source_counts,
        "source_line_rows_2017_2020": len(long_rows),
        "normalized_hunt_code_rows_by_year": {year: len(rows) for year, rows in sorted(year_rows.items())},
        "metric_nonblank_by_year": {
            year: {
                field: sum(bool(row[field]) for row in rows)
                for field in ("permits", "hunters_afield", "harvest_total", "percent_success", "average_days", "hunter_satisfaction")
            }
            for year, rows in sorted(year_rows.items())
        },
        "guardrails": {
            "do_not_use_for_permit_quota": all(row["do_not_use_for_permit_quota"] == "True" for row in normalized_rows),
            "do_not_use_directly_for_p_draw": all(row["do_not_use_directly_for_p_draw"] == "True" for row in normalized_rows),
        },
        "outputs": {
            "long_rows": str(OUT_LONG.relative_to(ROOT)),
            "normalized_rows": str(OUT_NORMALIZED.relative_to(ROOT)),
        },
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
