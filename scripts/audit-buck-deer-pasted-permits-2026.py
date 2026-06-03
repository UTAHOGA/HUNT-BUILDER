from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(
    r"C:\Users\tyler\.codex\attachments\9d5d717a-a40c-4dc6-8c2b-94070eebffce\pasted-text.txt"
)
HANUMBER = ROOT / "processed_data/dwr_huntplanner_hanumber_2026.csv"
HUNTTABLE = ROOT / "data_truth/crosswalk_truth/validation/live_dwr_permit_numbers_comprehensive_vs_DATABASE_2026.csv"
UTAHDRAWS = ROOT / "processed_data/audits/dwr_2026_draw_results_vs_database_allotments.csv"
OUT_CSV = ROOT / "processed_data/audits/buck_deer_pasted_permit_source_2026.csv"
SUMMARY_JSON = ROOT / "processed_data/audits/buck_deer_pasted_permit_source_2026_summary.json"


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def int_text(value: object) -> str:
    text = clean(value).replace(",", "")
    if text in {"", "-", "nan", "None"}:
        return ""
    try:
        number = float(text)
    except ValueError:
        return ""
    return str(int(number)) if number.is_integer() else str(number)


def permit_total(res: object, nr: object, total: object) -> str:
    res_text = int_text(res)
    nr_text = int_text(nr)
    total_text = int_text(total)
    if total_text not in {"", "0"}:
        return total_text
    if res_text not in {"", "0"} or nr_text not in {"", "0"}:
        return str(int(res_text or 0) + int(nr_text or 0))
    return ""


def triple(res: object, nr: object, total: object) -> tuple[str, str, str]:
    return int_text(res), int_text(nr), permit_total(res, nr, total)


def has_value(values: tuple[str, str, str]) -> bool:
    return any(value not in {"", "0"} for value in values)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{key: clean(value) for key, value in row.items()} for row in csv.DictReader(handle)]


def parse_pasted_source() -> list[dict[str, str]]:
    text = SOURCE.read_text(encoding="utf-8-sig")
    rows: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")
        parts = line.split("\t")
        if len(parts) > 1 and re.fullmatch(r"[A-Z]{2}\d{4}", parts[1].strip()):
            current = {
                "hunt_name": clean(parts[0]),
                "hunt_code": clean(parts[1]).upper(),
                "sex_type": clean(parts[2]) if len(parts) > 2 else "",
                "species": clean(parts[3]) if len(parts) > 3 else "",
                "weapon": clean(parts[4]) if len(parts) > 4 else "",
                "hunt_type": clean(parts[5]) if len(parts) > 5 else "",
                "season": clean(parts[6]) if len(parts) > 6 else "",
                "pasted_res": "",
                "pasted_nr": "",
                "pasted_total_printed": "",
            }
            permit_cell = clean(parts[7]) if len(parts) > 7 else ""
            res_match = re.search(r"\bRes:\s*([0-9,]+)", permit_cell, re.I)
            nr_match = re.search(r"\bNonRes:\s*([0-9,]+)", permit_cell, re.I)
            total_match = re.search(r"\bTotal:\s*([0-9,]+)", permit_cell, re.I)
            if res_match:
                current["pasted_res"] = int_text(res_match.group(1))
            if nr_match:
                current["pasted_nr"] = int_text(nr_match.group(1))
            if total_match:
                current["pasted_total_printed"] = int_text(total_match.group(1))
            rows.append(current)
            continue
        if current is not None:
            nr_match = re.search(r"\bNonRes:\s*([0-9,]+)", line, re.I)
            total_match = re.search(r"\bTotal:\s*([0-9,]+)", line, re.I)
            if nr_match:
                current["pasted_nr"] = int_text(nr_match.group(1))
            if total_match:
                current["pasted_total_printed"] = int_text(total_match.group(1))
    for row in rows:
        row["pasted_total"] = permit_total(row["pasted_res"], row["pasted_nr"], row["pasted_total_printed"])
        if row["pasted_res"] or row["pasted_nr"]:
            row["pasted_permit_shape"] = "RES_NR_SPLIT_TOTAL_COMPUTED"
        elif row["pasted_total"]:
            row["pasted_permit_shape"] = "TOTAL_ONLY_PRINTED"
        else:
            row["pasted_permit_shape"] = "NO_PERMIT_NUMBER_IN_PASTE"
    return rows


def source_maps() -> tuple[dict[str, tuple[str, str, str]], dict[str, tuple[str, str, str]], dict[str, tuple[str, str, str]]]:
    hanumber = {
        row["hunt_code"]: triple(row.get("permits_2026_res"), row.get("permits_2026_nr"), row.get("permits_2026_total"))
        for row in read_csv(HANUMBER)
        if row.get("hunt_code")
    }
    hunttable = {
        row["hunt_code"]: triple(row.get("live_res"), row.get("live_nr"), row.get("live_total"))
        for row in read_csv(HUNTTABLE)
        if row.get("hunt_code") and row.get("presence_status") != "DATABASE_ONLY"
    }
    utahdraws = {
        row["hunt_code"]: triple(row.get("source_res"), row.get("source_nr"), row.get("source_total"))
        for row in read_csv(UTAHDRAWS)
        if row.get("hunt_code") and row.get("source_presence") == "SOURCE_AND_DATABASE"
    }
    return hanumber, hunttable, utahdraws


def agreement_status(
    pasted: tuple[str, str, str],
    hanumber: tuple[str, str, str],
    hunttable: tuple[str, str, str],
    utahdraws: tuple[str, str, str],
) -> tuple[str, str, str, str]:
    matches = []
    total_matches = []
    for name, values in [
        ("HANUMBER", hanumber),
        ("HUNTTABLE", hunttable),
        ("UTAHDRAWS", utahdraws),
    ]:
        if has_value(values) and pasted == values:
            matches.append(name)
        elif pasted[2] and values[2] and pasted[2] == values[2]:
            total_matches.append(name)
    if len(matches) == 3:
        return "PASTED_MATCHES_ALL_3_EXACT", pasted[0], pasted[1], pasted[2]
    if matches:
        return "PASTED_MATCHES_" + "_AND_".join(matches) + "_EXACT", pasted[0], pasted[1], pasted[2]
    if total_matches:
        return "PASTED_TOTAL_MATCHES_" + "_AND_".join(total_matches), "", "", pasted[2]
    if has_value(pasted):
        return "PASTED_VALUE_UNCONFIRMED_OR_CONFLICTS", pasted[0], pasted[1], pasted[2]
    return "NO_PASTED_PERMIT_NUMBER", "", "", ""


def main() -> int:
    rows = parse_pasted_source()
    hanumber, hunttable, utahdraws = source_maps()
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    out_rows: list[dict[str, str]] = []
    for row in rows:
        code = row["hunt_code"]
        pasted = triple(row["pasted_res"], row["pasted_nr"], row["pasted_total"])
        hn = hanumber.get(code, ("", "", ""))
        ht = hunttable.get(code, ("", "", ""))
        ud = utahdraws.get(code, ("", "", ""))
        status, rec_res, rec_nr, rec_total = agreement_status(pasted, hn, ht, ud)
        if status.startswith("PASTED_MATCHES"):
            action = "RESOLVES_OR_CONFIRMS_CURRENT_PERMITS"
        elif status.startswith("PASTED_TOTAL_MATCHES"):
            action = "CONFIRMS_TOTAL_SPLIT_NEEDS_REVIEW"
        elif status == "PASTED_VALUE_UNCONFIRMED_OR_CONFLICTS":
            action = "REVIEW_PASTED_VALUE_AGAINST_OTHER_SOURCES"
        else:
            action = "NO_PERMIT_VALUE_TO_PROMOTE"
        out_rows.append(
            {
                "hunt_code": code,
                "hunt_name": row["hunt_name"],
                "sex_type": row["sex_type"],
                "species": row["species"],
                "weapon": row["weapon"],
                "hunt_type": row["hunt_type"],
                "season": row["season"],
                "pasted_res": pasted[0],
                "pasted_nr": pasted[1],
                "pasted_total": pasted[2],
                "pasted_total_printed": row["pasted_total_printed"],
                "pasted_permit_shape": row["pasted_permit_shape"],
                "hanumber_res": hn[0],
                "hanumber_nr": hn[1],
                "hanumber_total": hn[2],
                "hunttable_res": ht[0],
                "hunttable_nr": ht[1],
                "hunttable_total": ht[2],
                "utahdraws_res": ud[0],
                "utahdraws_nr": ud[1],
                "utahdraws_total": ud[2],
                "agreement_status": status,
                "recommended_current_res": rec_res,
                "recommended_current_nr": rec_nr,
                "recommended_current_total": rec_total,
                "recommended_action": action,
                "source_file": str(SOURCE),
                "source_sha256": source_hash,
            }
        )
    fields = [
        "hunt_code",
        "hunt_name",
        "sex_type",
        "species",
        "weapon",
        "hunt_type",
        "season",
        "pasted_res",
        "pasted_nr",
        "pasted_total",
        "pasted_total_printed",
        "pasted_permit_shape",
        "hanumber_res",
        "hanumber_nr",
        "hanumber_total",
        "hunttable_res",
        "hunttable_nr",
        "hunttable_total",
        "utahdraws_res",
        "utahdraws_nr",
        "utahdraws_total",
        "agreement_status",
        "recommended_current_res",
        "recommended_current_nr",
        "recommended_current_total",
        "recommended_action",
        "source_file",
        "source_sha256",
    ]
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out_rows)
    summary = {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_file": str(SOURCE),
        "source_sha256": source_hash,
        "rows_parsed": len(rows),
        "unique_hunt_codes": len({row["hunt_code"] for row in rows}),
        "permit_shape_counts": dict(Counter(row["pasted_permit_shape"] for row in out_rows)),
        "agreement_status_counts": dict(Counter(row["agreement_status"] for row in out_rows)),
        "recommended_action_counts": dict(Counter(row["recommended_action"] for row in out_rows)),
        "outputs": {"csv": OUT_CSV.relative_to(ROOT).as_posix(), "summary_json": SUMMARY_JSON.relative_to(ROOT).as_posix()},
        "notes": [
            "Rows with Res/NonRes but no printed total compute total as Res + NonRes.",
            "Rows with printed Total only preserve total and leave resident/nonresident blank unless another source supplies split.",
            "DATABASE.csv is not used as a winner source in this audit.",
        ],
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
