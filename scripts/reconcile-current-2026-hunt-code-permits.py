from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANUMBER = ROOT / "processed_data/dwr_huntplanner_hanumber_2026.csv"
HUNTTABLE = ROOT / "data_truth/crosswalk_truth/validation/live_dwr_permit_numbers_comprehensive_vs_DATABASE_2026.csv"
UTAHDRAWS = ROOT / "processed_data/audits/dwr_2026_draw_results_vs_database_allotments.csv"
BUCK_DEER = ROOT / "processed_data/audits/buck_deer_current_permit_source_2026_corrected.csv"
REVIEWED_OVERRIDES = ROOT / "processed_data/audits/reviewed_permit_value_overrides_2026.csv"
RETIRED_CODES = ROOT / "processed_data/audits/reviewed_retired_hunt_codes_2026.csv"
DATABASE = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"

OUT_RECON = ROOT / "processed_data/audits/current_2026_hunt_code_permit_reconciliation.csv"
OUT_UNRESOLVED = ROOT / "processed_data/audits/current_2026_hunt_code_permit_unresolved.csv"
OUT_SUMMARY = ROOT / "processed_data/audits/current_2026_hunt_code_permit_reconciliation_summary.json"
OUT_DOC = ROOT / "docs/current_2026_hunt_code_permit_reconciliation.md"


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def int_text(value: object) -> str:
    text = clean(value).replace(",", "")
    if text in {"", "-", "nan", "None"}:
        return ""
    try:
        number = float(text)
    except ValueError:
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        if not match:
            return ""
        number = float(match.group(0))
    return str(int(number)) if number.is_integer() else str(number)


def normalized_triple(res: object, nr: object, total: object) -> tuple[str, str, str]:
    res_text = int_text(res)
    nr_text = int_text(nr)
    total_text = int_text(total)
    if total_text in {"", "0"} and (res_text not in {"", "0"} or nr_text not in {"", "0"}):
        total_text = str(int(res_text or 0) + int(nr_text or 0))
    if (res_text, nr_text, total_text) in {("", "", ""), ("0", "0", "0"), ("0", "0", "")}:
        return "", "", ""
    if res_text == "0" and nr_text == "0" and total_text not in {"", "0"}:
        return "", "", total_text
    if total_text == "0" and res_text == "" and nr_text == "":
        return "", "", ""
    return res_text, nr_text, total_text


def has_value(values: tuple[str, str, str]) -> bool:
    return any(value not in {"", "0"} for value in values)


def exact_match(left: tuple[str, str, str], right: tuple[str, str, str]) -> bool:
    return has_value(left) and left == right


def total_match(left: tuple[str, str, str], right: tuple[str, str, str]) -> bool:
    return has_value(left) and has_value(right) and left[2] != "" and left[2] == right[2]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{key: clean(value) for key, value in row.items()} for row in csv.DictReader(handle)]


def retired_codes() -> set[str]:
    return {clean(row.get("hunt_code")).upper() for row in read_csv(RETIRED_CODES) if clean(row.get("hunt_code"))}


def source_record(
    present: bool = False,
    values: tuple[str, str, str] = ("", "", ""),
    name: str = "",
    species: str = "",
    sex_type: str = "",
    weapon: str = "",
    hunt_type: str = "",
    season: str = "",
    status: str = "",
    source_note: str = "",
) -> dict[str, str | bool | tuple[str, str, str]]:
    return {
        "present": present,
        "values": values,
        "name": name,
        "species": species,
        "sex_type": sex_type,
        "weapon": weapon,
        "hunt_type": hunt_type,
        "season": season,
        "status": status,
        "source_note": source_note,
    }


def build_sources() -> dict[str, dict[str, dict[str, str | bool | tuple[str, str, str]]]]:
    sources: dict[str, dict[str, dict[str, str | bool | tuple[str, str, str]]]] = {
        "reviewed_override": {},
        "hanumber": {},
        "hunttable": {},
        "utahdraws": {},
        "buck_deer": {},
        "database": {},
    }
    for row in read_csv(REVIEWED_OVERRIDES):
        code = clean(row.get("hunt_code")).upper()
        if not code:
            continue
        sources["reviewed_override"][code] = source_record(
            present=True,
            values=normalized_triple(row.get("reviewed_res"), row.get("reviewed_nr"), row.get("reviewed_total")),
            name=row.get("hunt_name") or "",
            species=row.get("species") or "",
            sex_type=row.get("sex_type") or "",
            weapon=row.get("weapon") or "",
            hunt_type=row.get("hunt_type") or "",
            season=row.get("season") or "",
            status=row.get("reviewed_status") or "",
            source_note=row.get("reviewed_source") or "",
        )
    for row in read_csv(HANUMBER):
        code = clean(row.get("hunt_code")).upper()
        if not code:
            continue
        sources["hanumber"][code] = source_record(
            present=True,
            values=normalized_triple(row.get("permits_2026_res"), row.get("permits_2026_nr"), row.get("permits_2026_total")),
            name=row.get("dwr_hunt_name") or row.get("database_hunt_name") or "",
            species=row.get("dwr_species") or row.get("database_species") or "",
            sex_type=row.get("dwr_sex_type") or row.get("database_sex_type") or "",
            weapon=row.get("dwr_weapon") or row.get("database_weapon") or "",
            hunt_type=row.get("dwr_hunt_type") or row.get("database_hunt_type") or "",
            season=row.get("season_date_text") or "",
            status=row.get("fetch_status") or "",
            source_note=row.get("source_url") or "",
        )
    for row in read_csv(HUNTTABLE):
        code = clean(row.get("hunt_code")).upper()
        if not code:
            continue
        sources["hunttable"][code] = source_record(
            present=row.get("presence_status") != "DATABASE_ONLY",
            values=normalized_triple(row.get("live_res"), row.get("live_nr"), row.get("live_total")),
            name=row.get("live_hunt_name") or row.get("database_hunt_name") or "",
            species=row.get("live_species") or row.get("database_species") or "",
            sex_type=row.get("live_sex_type") or row.get("database_sex_type") or "",
            weapon=row.get("live_weapon") or row.get("database_weapon") or "",
            hunt_type=row.get("live_hunt_type") or row.get("database_hunt_type") or "",
            season=row.get("live_season") or "",
            status=row.get("presence_status") or "",
            source_note=row.get("comparison_status") or "",
        )
    for row in read_csv(UTAHDRAWS):
        code = clean(row.get("hunt_code")).upper()
        if not code:
            continue
        sources["utahdraws"][code] = source_record(
            present=row.get("source_presence") != "DATABASE_ONLY",
            values=normalized_triple(row.get("source_res"), row.get("source_nr"), row.get("source_total")),
            name=row.get("source_hunt_name") or row.get("database_hunt_name") or "",
            species=row.get("source_species") or row.get("database_species") or row.get("species_family") or "",
            status=row.get("source_presence") or "",
            source_note=row.get("source_files") or "",
        )
    for row in read_csv(BUCK_DEER):
        code = clean(row.get("hunt_code")).upper()
        if not code:
            continue
        sources["buck_deer"][code] = source_record(
            present=True,
            values=normalized_triple(row.get("permits_2026_res"), row.get("permits_2026_nr"), row.get("permits_2026_total")),
            name=row.get("hunt_name") or "",
            species=row.get("species") or "",
            sex_type=row.get("sex_type") or "",
            weapon=row.get("weapon") or "",
            hunt_type=row.get("hunt_type") or "",
            season=row.get("season") or "",
            status=row.get("validation_status") or "",
            source_note=row.get("source_file") or "",
        )
    for row in read_csv(DATABASE):
        code = clean(row.get("hunt_code")).upper()
        if not code:
            continue
        sources["database"][code] = source_record(
            present=True,
            values=normalized_triple(
                row.get("permit_allotment_2026_res"),
                row.get("permit_allotment_2026_nr"),
                row.get("permit_allotment_2026_total"),
            ),
            name=row.get("hunt_name") or "",
            species=row.get("species") or "",
            sex_type=row.get("sex_type") or "",
            weapon=row.get("weapon") or "",
            hunt_type=row.get("hunt_type") or "",
            season=row.get("season") or "",
            status=row.get("permit_allotment_2026_status") or "",
            source_note=row.get("permit_allotment_2026_source") or "",
        )
    return sources


def first_metadata(code: str, sources: dict[str, dict[str, dict[str, str | bool | tuple[str, str, str]]]]) -> dict[str, str]:
    for source_name in ["reviewed_override", "hanumber", "hunttable", "buck_deer", "utahdraws", "database"]:
        row = sources[source_name].get(code)
        if row and (row.get("name") or row.get("species")):
            return {
                "hunt_name": str(row.get("name") or ""),
                "species": str(row.get("species") or ""),
                "sex_type": str(row.get("sex_type") or ""),
                "weapon": str(row.get("weapon") or ""),
                "hunt_type": str(row.get("hunt_type") or ""),
                "season": str(row.get("season") or ""),
            }
    return {"hunt_name": "", "species": "", "sex_type": "", "weapon": "", "hunt_type": "", "season": ""}


def choose_winner(code: str, rows: dict[str, dict[str, str | bool | tuple[str, str, str]]]) -> dict[str, str]:
    values = {name: rows[name].get("values", ("", "", "")) for name in rows}
    valued = {name: val for name, val in values.items() if name != "database" and isinstance(val, tuple) and has_value(val)}
    if not valued:
        db_values = values.get("database", ("", "", ""))
        if isinstance(db_values, tuple) and has_value(db_values):
            return {
                "winner_source": "NONE_EXTERNAL_DATABASE_REFERENCE_ONLY",
                "recommended_res": "",
                "recommended_nr": "",
                "recommended_total": "",
                "confidence": "REVIEW_REQUIRED",
                "recommended_action": "FIND_EXTERNAL_SOURCE_BEFORE_PROMOTION",
                "decision_reason": "No non-database current source has permit values; database has a reference value only.",
            }
        return {
            "winner_source": "NONE",
            "recommended_res": "",
            "recommended_nr": "",
            "recommended_total": "",
            "confidence": "NO_PERMIT_VALUE",
            "recommended_action": "NO_CURRENT_PERMIT_VALUE_FOUND",
            "decision_reason": "No source in this pass has current permit values.",
        }

    priority = ["reviewed_override", "hanumber", "hunttable", "buck_deer", "utahdraws"]
    winner = next(name for name in priority if name in valued)
    winner_values = valued[winner]
    if winner == "reviewed_override":
        return {
            "winner_source": "REVIEWED_OVERRIDE",
            "recommended_res": winner_values[0],
            "recommended_nr": winner_values[1],
            "recommended_total": winner_values[2],
            "confidence": "REVIEWED_OVERRIDE_CONFIRMED",
            "recommended_action": "PROMOTE_REVIEWED_OVERRIDE",
            "decision_reason": "Reviewed override selected from explicit user-confirmed correction.",
        }
    exact_support = [name for name, val in valued.items() if val == winner_values]
    total_support = [name for name, val in valued.items() if name not in exact_support and total_match(val, winner_values)]
    conflicts = [name for name, val in valued.items() if name not in exact_support and not total_match(val, winner_values)]
    if conflicts:
        confidence = "REVIEW_SOURCE_CONFLICT"
        action = "REVIEW_BEFORE_PROMOTION"
        reason = f"{winner} selected by precedence, but conflicts with: {', '.join(conflicts)}."
    elif len(exact_support) >= 2:
        confidence = "HIGH_CONFIRMED_2PLUS"
        action = "PROMOTE_CANDIDATE_AFTER_REVIEW"
        reason = f"{winner} selected and exactly supported by {len(exact_support)} non-database source(s)."
    elif total_support:
        confidence = "MEDIUM_TOTAL_CONFIRMED"
        action = "PROMOTE_TOTAL_AFTER_SPLIT_REVIEW"
        reason = f"{winner} selected; total is supported by {', '.join(total_support)}."
    else:
        confidence = "MEDIUM_SINGLE_SOURCE"
        action = "PROMOTE_CANDIDATE_AFTER_REVIEW"
        reason = f"{winner} selected as the only non-database source with permit values."
    return {
        "winner_source": winner.upper(),
        "recommended_res": winner_values[0],
        "recommended_nr": winner_values[1],
        "recommended_total": winner_values[2],
        "confidence": confidence,
        "recommended_action": action,
        "decision_reason": reason,
    }


def main() -> int:
    sources = build_sources()
    retired = retired_codes()
    all_codes = sorted(set().union(*(source.keys() for source in sources.values())) - retired)
    out_rows: list[dict[str, str]] = []
    unresolved_rows: list[dict[str, str]] = []
    for code in all_codes:
        rows = {source_name: sources[source_name].get(code, source_record()) for source_name in sources}
        meta = first_metadata(code, sources)
        decision = choose_winner(code, rows)
        source_presence = [
            name.upper()
            for name in ["reviewed_override", "hanumber", "hunttable", "utahdraws", "buck_deer", "database"]
            if rows[name].get("present")
        ]
        non_db_values = {
            name: rows[name].get("values", ("", "", ""))
            for name in ["reviewed_override", "hanumber", "hunttable", "utahdraws", "buck_deer"]
        }
        recommended = (
            decision["recommended_res"],
            decision["recommended_nr"],
            decision["recommended_total"],
        )
        source_support_count = sum(
            1 for val in non_db_values.values() if isinstance(val, tuple) and has_value(val) and val == recommended
        )
        conflicting_sources = [
            name.upper()
            for name, val in non_db_values.items()
            if isinstance(val, tuple) and has_value(val) and has_value(recommended) and val != recommended and not total_match(val, recommended)
        ]
        database_values = rows["database"].get("values", ("", "", ""))
        database_alignment = "NOT_COMPARED"
        if isinstance(database_values, tuple) and has_value(database_values) and has_value(recommended):
            if database_values == recommended:
                database_alignment = "DATABASE_MATCHES_RECOMMENDED"
            elif total_match(database_values, recommended):
                database_alignment = "DATABASE_TOTAL_MATCHES_RECOMMENDED"
            else:
                database_alignment = "DATABASE_DIFFERS_FROM_RECOMMENDED"
        elif isinstance(database_values, tuple) and has_value(database_values):
            database_alignment = "DATABASE_HAS_VALUE_NO_RECOMMENDATION"
        elif has_value(recommended):
            database_alignment = "DATABASE_BLANK_RECOMMENDATION_HAS_VALUE"
        out = {
            "hunt_code": code,
            **meta,
            "source_presence": "|".join(source_presence),
            "reviewed_override_res": rows["reviewed_override"].get("values", ("", "", ""))[0],
            "reviewed_override_nr": rows["reviewed_override"].get("values", ("", "", ""))[1],
            "reviewed_override_total": rows["reviewed_override"].get("values", ("", "", ""))[2],
            "hanumber_res": rows["hanumber"].get("values", ("", "", ""))[0],
            "hanumber_nr": rows["hanumber"].get("values", ("", "", ""))[1],
            "hanumber_total": rows["hanumber"].get("values", ("", "", ""))[2],
            "hunttable_res": rows["hunttable"].get("values", ("", "", ""))[0],
            "hunttable_nr": rows["hunttable"].get("values", ("", "", ""))[1],
            "hunttable_total": rows["hunttable"].get("values", ("", "", ""))[2],
            "utahdraws_res": rows["utahdraws"].get("values", ("", "", ""))[0],
            "utahdraws_nr": rows["utahdraws"].get("values", ("", "", ""))[1],
            "utahdraws_total": rows["utahdraws"].get("values", ("", "", ""))[2],
            "buck_deer_res": rows["buck_deer"].get("values", ("", "", ""))[0],
            "buck_deer_nr": rows["buck_deer"].get("values", ("", "", ""))[1],
            "buck_deer_total": rows["buck_deer"].get("values", ("", "", ""))[2],
            "database_res_reference": rows["database"].get("values", ("", "", ""))[0],
            "database_nr_reference": rows["database"].get("values", ("", "", ""))[1],
            "database_total_reference": rows["database"].get("values", ("", "", ""))[2],
            "recommended_res": decision["recommended_res"],
            "recommended_nr": decision["recommended_nr"],
            "recommended_total": decision["recommended_total"],
            "winner_source": decision["winner_source"],
            "confidence": decision["confidence"],
            "source_support_count": str(source_support_count),
            "conflicting_sources": "|".join(conflicting_sources),
            "database_alignment": database_alignment,
            "recommended_action": decision["recommended_action"],
            "decision_reason": decision["decision_reason"],
            "reviewed_override_status": str(rows["reviewed_override"].get("status") or ""),
            "hanumber_status": str(rows["hanumber"].get("status") or ""),
            "hunttable_status": str(rows["hunttable"].get("status") or ""),
            "utahdraws_status": str(rows["utahdraws"].get("status") or ""),
            "buck_deer_status": str(rows["buck_deer"].get("status") or ""),
            "database_status": str(rows["database"].get("status") or ""),
        }
        out_rows.append(out)
        if out["confidence"] in {"REVIEW_REQUIRED", "REVIEW_SOURCE_CONFLICT", "NO_PERMIT_VALUE"}:
            unresolved_rows.append(out)
    OUT_RECON.parent.mkdir(parents=True, exist_ok=True)
    with OUT_RECON.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)
    with OUT_UNRESOLVED.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(unresolved_rows)

    prefix_counts = Counter(row["hunt_code"][:2] for row in out_rows)
    unresolved_prefix_counts = Counter(row["hunt_code"][:2] for row in unresolved_rows)
    species_counts = Counter(row["species"] or "UNKNOWN" for row in out_rows)
    unresolved_species_counts = Counter(row["species"] or "UNKNOWN" for row in unresolved_rows)
    source_code_counts = {}
    for source_name, source_rows in sources.items():
        source_code_counts[source_name] = {
            "present_codes": sum(1 for row in source_rows.values() if row.get("present")),
            "value_codes": sum(
                1
                for row in source_rows.values()
                if row.get("present") and isinstance(row.get("values"), tuple) and has_value(row.get("values"))  # type: ignore[arg-type]
            ),
        }
    summary = {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_files": {
            "hanumber": HANUMBER.relative_to(ROOT).as_posix(),
            "hunttable": HUNTTABLE.relative_to(ROOT).as_posix(),
            "utahdraws": UTAHDRAWS.relative_to(ROOT).as_posix(),
            "buck_deer": BUCK_DEER.relative_to(ROOT).as_posix(),
            "reviewed_overrides": REVIEWED_OVERRIDES.relative_to(ROOT).as_posix(),
            "retired_codes": RETIRED_CODES.relative_to(ROOT).as_posix(),
            "database_reference_only": DATABASE.relative_to(ROOT).as_posix(),
        },
        "row_counts": {
            "candidate_hunt_codes": len(out_rows),
            "recommended_with_permit_value": sum(1 for row in out_rows if has_value((row["recommended_res"], row["recommended_nr"], row["recommended_total"]))),
            "unresolved_rows": len(unresolved_rows),
            "database_reference_only_not_winner": sum(1 for row in out_rows if row["winner_source"] == "NONE_EXTERNAL_DATABASE_REFERENCE_ONLY"),
        },
        "winner_source_counts": dict(Counter(row["winner_source"] for row in out_rows)),
        "confidence_counts": dict(Counter(row["confidence"] for row in out_rows)),
        "recommended_action_counts": dict(Counter(row["recommended_action"] for row in out_rows)),
        "database_alignment_counts": dict(Counter(row["database_alignment"] for row in out_rows)),
        "source_code_counts": source_code_counts,
        "prefix_counts": dict(sorted(prefix_counts.items())),
        "unresolved_prefix_counts": dict(sorted(unresolved_prefix_counts.items())),
        "species_counts": dict(sorted(species_counts.items())),
        "unresolved_species_counts": dict(sorted(unresolved_species_counts.items())),
        "outputs": {
            "reconciliation_csv": OUT_RECON.relative_to(ROOT).as_posix(),
            "unresolved_csv": OUT_UNRESOLVED.relative_to(ROOT).as_posix(),
            "summary_json": OUT_SUMMARY.relative_to(ROOT).as_posix(),
            "report_md": OUT_DOC.relative_to(ROOT).as_posix(),
        },
        "notes": [
            "DATABASE.csv is used only as a comparison/reference field in this pass, not as a winner source.",
            "Reviewed override rows are user-reviewed corrections and are first in precedence for the listed hunt codes only.",
            "Reviewed retired-code rows are excluded from the active current recommendation union.",
            "HaNumber is the first preferred current DWR source when it has a permit value.",
            "Rows with only database reference values remain unresolved until an external source is found.",
        ],
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def write_report(summary: dict[str, object]) -> None:
    row_counts = summary["row_counts"]
    assert isinstance(row_counts, dict)
    winner_counts = summary["winner_source_counts"]
    confidence_counts = summary["confidence_counts"]
    action_counts = summary["recommended_action_counts"]
    source_counts = summary["source_code_counts"]
    unresolved_prefix = summary["unresolved_prefix_counts"]
    unresolved_species = summary["unresolved_species_counts"]
    assert isinstance(winner_counts, dict)
    assert isinstance(confidence_counts, dict)
    assert isinstance(action_counts, dict)
    assert isinstance(source_counts, dict)
    assert isinstance(unresolved_prefix, dict)
    assert isinstance(unresolved_species, dict)
    lines = [
        "# Current 2026 Hunt-Code Permit Reconciliation",
        "",
        "## Purpose",
        "",
        "This is an audit-only reconciliation for current 2026 hunt codes and permit/allotment numbers. It compares current external evidence and produces recommended permit candidates, but it does not write to `DATABASE.csv`.",
        "",
        "## Source Precedence",
        "",
        "1. DWR Hunt Planner `HaNumber` pull when it has a current permit value.",
        "1. Reviewed override rows for explicitly user-confirmed extraction/crosswalk corrections.",
        "2. DWR Hunt Planner `HaNumber` pull when it has a current permit value.",
        "3. Live DWR HuntBoundary `HuntTableData` table values.",
        "4. Repaired Buck Deer workbook/pasted source rows for Buck Deer-specific support.",
        "5. UtahDraws/BIBLE 2026 draw-results evidence where DWR current sources are blank or where it supports the same value.",
        "6. `DATABASE.csv` is comparison/reference only in this pass, not a winner source.",
        "",
        "## Key Counts",
        "",
        f"- Candidate hunt codes in union: `{row_counts['candidate_hunt_codes']}`",
        f"- Rows with recommended external permit values: `{row_counts['recommended_with_permit_value']}`",
        f"- Unresolved/review rows: `{row_counts['unresolved_rows']}`",
        f"- Rows where only `DATABASE.csv` has a permit reference value: `{row_counts['database_reference_only_not_winner']}`",
        "",
        "## Winner Source Counts",
        "",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in sorted(winner_counts.items()))
    lines.extend(["", "## Confidence Counts", ""])
    lines.extend(f"- `{key}`: `{value}`" for key, value in sorted(confidence_counts.items()))
    lines.extend(["", "## Recommended Action Counts", ""])
    lines.extend(f"- `{key}`: `{value}`" for key, value in sorted(action_counts.items()))
    lines.extend(["", "## Source Coverage Counts", ""])
    for key, value in sorted(source_counts.items()):
        assert isinstance(value, dict)
        lines.append(f"- `{key}`: `{value.get('present_codes')}` present codes, `{value.get('value_codes')}` value codes")
    lines.extend(["", "## Main Unresolved Prefix Families", ""])
    lines.extend(f"- `{key}`: `{value}`" for key, value in sorted(unresolved_prefix.items(), key=lambda item: (-item[1], item[0]))[:20])
    lines.extend(["", "## Main Unresolved Species Families", ""])
    lines.extend(f"- `{key}`: `{value}`" for key, value in sorted(unresolved_species.items(), key=lambda item: (-item[1], item[0]))[:20])
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Rows marked `HIGH_CONFIRMED_2PLUS` are the strongest candidates for promotion after review because at least two non-database sources agree exactly.",
            "",
            "Rows marked `REVIEW_SOURCE_CONFLICT` have a selected winner by precedence but still conflict with another non-database source. These should be inspected before promotion, especially where UtahDraws/BIBLE values represent a different permit concept than current DWR allotment values.",
            "",
            "Rows marked `REVIEW_REQUIRED` are the most important cleanup set because no external current source in this pass has permit values even though `DATABASE.csv` may contain a reference value.",
            "",
            "## Outputs",
            "",
            f"- `{summary['outputs']['reconciliation_csv']}`",
            f"- `{summary['outputs']['unresolved_csv']}`",
            f"- `{summary['outputs']['summary_json']}`",
        ]
    )
    OUT_DOC.parent.mkdir(parents=True, exist_ok=True)
    OUT_DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
