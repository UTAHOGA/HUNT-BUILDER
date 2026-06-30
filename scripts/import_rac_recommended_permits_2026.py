import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def _repo_root() -> Path:
    repo_root = Path(__file__).resolve()
    while repo_root.name != "HUNT-BUILDER" and repo_root.parent != repo_root:
        repo_root = repo_root.parent
    if repo_root.name != "HUNT-BUILDER":
        raise RuntimeError("Could not locate HUNT-BUILDER repo root")
    return repo_root

import pdfplumber

REPO = Path(str(_repo_root()))
PDF_PATH = REPO / "pipeline/RAW/hunt_unit_database/2026/pdf/current_year_permit_numbers/Draw Odds/2026 rac recommended permits.pdf"
DB_PATH = REPO / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
OUT_DIR = REPO / "pipeline/RAW/hunt_unit_database/2026/csv/current_year_permit_numbers"
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_EXTRACTED = OUT_DIR / "2026_rac_recommended_permits_extracted_rows.csv"
OUT_DEDUPED = OUT_DIR / "2026_rac_recommended_permits_deduped.csv"
OUT_CANDIDATES = OUT_DIR / "2026_rac_recommended_permits_import_candidates.csv"
OUT_CONFLICTS = OUT_DIR / "2026_rac_recommended_permits_conflicts.csv"
OUT_REPORT = OUT_DIR / "2026_rac_recommended_permits_import_report.json"
OUT_DB_PATCH_PREVIEW = OUT_DIR / "DATABASE_after_rac_patch_preview.csv"

HUNT_CODE_RX = re.compile(r"^[A-Z]{2}\d{4}$")


def clean(v):
    return "" if v is None else str(v).strip()


def to_int_or_blank(v):
    t = clean(v).replace(",", "")
    if not t or t in {"-", "–", "—"}:
        return ""
    if t.lower() == "unlimited":
        return "UNLIMITED"
    try:
        return str(int(float(t)))
    except Exception:
        return ""


def normalize_name(v):
    t = clean(v).lower()
    t = t.replace("mtn.", "mtn").replace("mtns.", "mtns")
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    t = re.sub(r"\s+", " ", t)
    return t


def names_match(pdf_name, db_name):
    p = normalize_name(pdf_name)
    d = normalize_name(db_name)
    if not p or not d:
        return True
    if p == d:
        return True
    # Allow minor formatting variants while still requiring semantic alignment.
    if len(p) >= 8 and p in d:
        return True
    if len(d) >= 8 and d in p:
        return True
    return False


def sha256_file(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def header_index(header):
    norm = [clean(c).replace("\n", " ") for c in header]
    low = [c.lower() for c in norm]
    idx = {
        "hunt_number": -1,
        "hunt_name": -1,
        "weapon": -1,
        "sex_type": -1,
        "r2026": -1,
        "nr2026": -1,
        "t2026": -1,
        "t2026_only": -1,
    }
    # locate core identifiers
    for i, c in enumerate(low):
        if "hunt number" == c:
            idx["hunt_number"] = i
        if "hunt name" == c or c == "general season units":
            idx["hunt_name"] = i
        if c == "weapon":
            idx["weapon"] = i
        if "sex type" == c:
            idx["sex_type"] = i

    # Find 2026 split by last occurrence trio res/nonres/total
    res_positions = [i for i, c in enumerate(low) if c == "res"]
    nr_positions = [i for i, c in enumerate(low) if c in {"non res", "nonres", "non-res", "non resident", "nonresident"}]
    total_positions = [i for i, c in enumerate(low) if c == "total"]
    if len(res_positions) >= 2 and len(nr_positions) >= 2 and len(total_positions) >= 2:
        idx["r2026"] = res_positions[-1]
        idx["nr2026"] = nr_positions[-1]
        idx["t2026"] = total_positions[-1]
    elif len(res_positions) >= 1 and len(nr_positions) >= 1 and len(total_positions) >= 1 and "2026 permits" in " ".join(low):
        # single trio but table references 2026 permits nearby
        idx["r2026"] = res_positions[-1]
        idx["nr2026"] = nr_positions[-1]
        idx["t2026"] = total_positions[-1]

    # two-column totals table style: columns named 2025 / 2026
    c2026 = [i for i, c in enumerate(low) if c == "2026" or c == "2026 permits"]
    if c2026:
        idx["t2026_only"] = c2026[-1]

    return idx, norm


def extract_rows_from_pdf(pdf_path: Path):
    rows = []
    rejects = []
    pages_scanned = 0
    with pdfplumber.open(pdf_path) as pdf:
        pages_scanned = len(pdf.pages)
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables() or []
            for table_num, table in enumerate(tables, start=1):
                if not table:
                    continue
                header_row_idx = None
                idx = None
                norm_header = None
                for i, r in enumerate(table[:6]):
                    rr = [clean(c) for c in (r or [])]
                    if any(clean(c).lower() == "hunt number" for c in rr):
                        header_row_idx = i
                        idx, norm_header = header_index(rr)
                        break
                if header_row_idx is None:
                    continue

                for row_idx, raw in enumerate(table[header_row_idx + 1 :], start=header_row_idx + 2):
                    cells = [clean(c) for c in (raw or [])]
                    if not any(cells):
                        continue

                    # skip totals and section headers
                    joined = " ".join(cells).lower()
                    if "grand total" in joined:
                        continue
                    if "permits" in joined and "hunt number" in joined:
                        continue

                    hc = ""
                    if 0 <= idx["hunt_number"] < len(cells):
                        hc = clean(cells[idx["hunt_number"]]).upper()
                    if not HUNT_CODE_RX.match(hc):
                        rejects.append(
                            {
                                "source_page": page_num,
                                "source_table": table_num,
                                "source_row": row_idx,
                                "reject_reason": "NO_VALID_HUNT_CODE",
                                "raw": " | ".join(cells),
                            }
                        )
                        continue

                    hunt_name = clean(cells[idx["hunt_name"]]) if 0 <= idx["hunt_name"] < len(cells) else ""
                    weapon = clean(cells[idx["weapon"]]) if 0 <= idx["weapon"] < len(cells) else ""
                    sex_type = clean(cells[idx["sex_type"]]) if 0 <= idx["sex_type"] < len(cells) else ""

                    res_2026 = ""
                    nr_2026 = ""
                    total_2026 = ""
                    if idx["r2026"] >= 0 and idx["nr2026"] >= 0 and idx["t2026"] >= 0:
                        res_2026 = to_int_or_blank(cells[idx["r2026"]] if idx["r2026"] < len(cells) else "")
                        nr_2026 = to_int_or_blank(cells[idx["nr2026"]] if idx["nr2026"] < len(cells) else "")
                        total_2026 = to_int_or_blank(cells[idx["t2026"]] if idx["t2026"] < len(cells) else "")
                    elif idx["t2026_only"] >= 0:
                        total_2026 = to_int_or_blank(cells[idx["t2026_only"]] if idx["t2026_only"] < len(cells) else "")

                    if not any([res_2026, nr_2026, total_2026]):
                        rejects.append(
                            {
                                "source_page": page_num,
                                "source_table": table_num,
                                "source_row": row_idx,
                                "reject_reason": "NO_2026_PERMIT_VALUES",
                                "raw": " | ".join(cells),
                            }
                        )
                        continue

                    rows.append(
                        {
                            "hunt_code": hc,
                            "hunt_name_pdf": hunt_name,
                            "weapon_pdf": weapon,
                            "sex_type_pdf": sex_type,
                            "permits_2026_res_pdf": res_2026,
                            "permits_2026_nr_pdf": nr_2026,
                            "permits_2026_total_pdf": total_2026,
                            "source_page": page_num,
                            "source_table": table_num,
                            "source_row": row_idx,
                            "source_header": " | ".join(norm_header or []),
                            "source_file": str(pdf_path.relative_to(REPO)).replace("\\", "/"),
                        }
                    )
    return rows, rejects, pages_scanned


def dedupe_rows(rows):
    by_code = defaultdict(list)
    for r in rows:
        by_code[r["hunt_code"]].append(r)

    deduped = []
    row_conflicts = []
    for code, items in sorted(by_code.items()):
        # score rows by completeness
        def score(x):
            s = 0
            if x["permits_2026_res_pdf"] not in {"", "UNLIMITED"}:
                s += 3
            if x["permits_2026_nr_pdf"] not in {"", "UNLIMITED"}:
                s += 3
            if x["permits_2026_total_pdf"] not in {"", "UNLIMITED"}:
                s += 2
            if x["permits_2026_total_pdf"] == "UNLIMITED":
                s += 1
            if x["hunt_name_pdf"]:
                s += 1
            return s

        items_sorted = sorted(items, key=score, reverse=True)
        best = dict(items_sorted[0])

        # detect conflicting numeric values among candidates
        vals = defaultdict(set)
        for it in items:
            for f in ["permits_2026_res_pdf", "permits_2026_nr_pdf", "permits_2026_total_pdf"]:
                v = clean(it[f])
                if v:
                    vals[f].add(v)
        conflict_notes = []
        for f, s in vals.items():
            if len(s) > 1:
                conflict_notes.append(f"{f}:{sorted(s)}")

        best["dedupe_source_rows"] = len(items)
        best["dedupe_conflicts"] = "; ".join(conflict_notes)
        deduped.append(best)

        if conflict_notes:
            for it in items:
                row_conflicts.append(
                    {
                        "hunt_code": code,
                        "field_conflicts": "; ".join(conflict_notes),
                        "candidate_res": it["permits_2026_res_pdf"],
                        "candidate_nr": it["permits_2026_nr_pdf"],
                        "candidate_total": it["permits_2026_total_pdf"],
                        "source_page": it["source_page"],
                        "source_table": it["source_table"],
                        "source_row": it["source_row"],
                    }
                )

    return deduped, row_conflicts


def import_into_database(deduped_rows):
    with DB_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        db_headers = reader.fieldnames or []
        db_rows = list(reader)

    code_to_row = {}
    for r in db_rows:
        c = clean(r.get("hunt_code")).upper()
        if c:
            code_to_row[c] = r

    candidates = []
    conflicts = []
    updates = 0
    filled_res = 0
    filled_nr = 0
    filled_total = 0

    for src in deduped_rows:
        code = clean(src["hunt_code"]).upper()
        db_row = code_to_row.get(code)
        if not db_row:
            candidates.append({
                "hunt_code": code,
                "action": "NO_DATABASE_MATCH",
                "reason": "HUNT_CODE_NOT_IN_DATABASE",
                **src,
            })
            continue

        db_hunt_name = clean(db_row.get("hunt_name"))
        if not names_match(src.get("hunt_name_pdf"), db_hunt_name):
            conflicts.append(
                {
                    "hunt_code": code,
                    "field": "hunt_name",
                    "database_value": db_hunt_name,
                    "rac_value": clean(src.get("hunt_name_pdf")),
                    "conflict_type": "HUNT_NAME_MISMATCH_DATABASE_PRESERVED",
                    "source_page": src["source_page"],
                    "source_table": src["source_table"],
                    "source_row": src["source_row"],
                }
            )
            candidates.append(
                {
                    "hunt_code": code,
                    "action": "SKIPPED_NAME_MISMATCH",
                    "reason": "HUNT_CODE_MATCH_BUT_HUNT_NAME_MISMATCH",
                    "database_hunt_name": db_hunt_name,
                    **src,
                }
            )
            continue

        changed = False
        reason_parts = []
        for fld, ctr_name in [
            ("permits_2026_res", "filled_res"),
            ("permits_2026_nr", "filled_nr"),
            ("permits_2026_total", "filled_total"),
        ]:
            src_f = f"{fld}_pdf"
            sv = clean(src.get(src_f))
            dv = clean(db_row.get(fld))

            # unlimited is informational only here; do not write into numeric permit fields
            if sv == "UNLIMITED":
                reason_parts.append(f"{fld}:SOURCE_UNLIMITED_NOT_WRITTEN")
                continue
            if not sv:
                continue

            if not dv:
                db_row[fld] = sv
                changed = True
                if ctr_name == "filled_res":
                    filled_res += 1
                elif ctr_name == "filled_nr":
                    filled_nr += 1
                else:
                    filled_total += 1
                reason_parts.append(f"{fld}:FILLED_BLANK")
            elif dv != sv:
                conflicts.append(
                    {
                        "hunt_code": code,
                        "field": fld,
                        "database_value": dv,
                        "rac_value": sv,
                        "conflict_type": "VALUE_MISMATCH_DATABASE_PRESERVED",
                        "source_page": src["source_page"],
                        "source_table": src["source_table"],
                        "source_row": src["source_row"],
                    }
                )
                reason_parts.append(f"{fld}:CONFLICT_DB={dv}_RAC={sv}")

        # fill total from split if total still blank and both split numeric present in src
        if not clean(db_row.get("permits_2026_total")):
            r = clean(src.get("permits_2026_res_pdf"))
            n = clean(src.get("permits_2026_nr_pdf"))
            if r.isdigit() and n.isdigit():
                calc = str(int(r) + int(n))
                db_row["permits_2026_total"] = calc
                changed = True
                filled_total += 1
                reason_parts.append("permits_2026_total:CALCULATED_FROM_SPLIT")

        candidates.append(
            {
                "hunt_code": code,
                "action": "UPDATED" if changed else "NO_CHANGE",
                "reason": "; ".join(reason_parts) if reason_parts else "NO_IMPORTABLE_VALUES",
                "database_hunt_name": clean(db_row.get("hunt_name")),
                **src,
            }
        )
        if changed:
            updates += 1

    return {
        "candidates": candidates,
        "conflicts": conflicts,
        "updates": updates,
        "filled_res": filled_res,
        "filled_nr": filled_nr,
        "filled_total": filled_total,
        "database_row_count": len(db_rows),
        "database_headers": db_headers,
        "database_rows_after_patch": db_rows,
    }


def write_csv(path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    headers = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(rows)


def try_write_database(db_headers, db_rows):
    try:
        with DB_PATH.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=db_headers)
            w.writeheader()
            w.writerows(db_rows)
        return {"database_write_status": "UPDATED_DATABASE"}
    except PermissionError:
        with OUT_DB_PATCH_PREVIEW.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=db_headers)
            w.writeheader()
            w.writerows(db_rows)
        return {
            "database_write_status": "DATABASE_LOCKED_PATCH_PREVIEW_WRITTEN",
            "patch_preview": str(OUT_DB_PATCH_PREVIEW.relative_to(REPO)).replace("\\", "/"),
        }


def main():
    if not PDF_PATH.exists():
        raise FileNotFoundError(PDF_PATH)
    if not DB_PATH.exists():
        raise FileNotFoundError(DB_PATH)

    extracted, rejects, pages_scanned = extract_rows_from_pdf(PDF_PATH)
    deduped, internal_conflicts = dedupe_rows(extracted)
    db_sync = import_into_database(deduped)
    db_write = try_write_database(db_sync["database_headers"], db_sync["database_rows_after_patch"])

    write_csv(OUT_EXTRACTED, extracted)
    write_csv(OUT_DEDUPED, deduped)
    write_csv(OUT_CANDIDATES, db_sync["candidates"])

    all_conflicts = list(internal_conflicts) + list(db_sync["conflicts"])
    if all_conflicts:
        write_csv(OUT_CONFLICTS, all_conflicts)
    else:
        with OUT_CONFLICTS.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["note"])
            w.writeheader()
            w.writerow({"note": "NO_CONFLICTS"})

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_pdf": str(PDF_PATH.relative_to(REPO)).replace("\\", "/"),
        "source_sha256": sha256_file(PDF_PATH),
        "pages_scanned": pages_scanned,
        "extracted_rows_raw": len(extracted),
        "extracted_rows_deduped": len(deduped),
        "rejected_rows": len(rejects),
        "internal_extract_conflicts": len(internal_conflicts),
        "database_conflicts": len(db_sync["conflicts"]),
        "database_rows_updated": db_sync["updates"],
        "filled_permits_2026_res": db_sync["filled_res"],
        "filled_permits_2026_nr": db_sync["filled_nr"],
        "filled_permits_2026_total": db_sync["filled_total"],
        "database_write_status": db_write["database_write_status"],
        "notes": [
            "Import policy: fill DATABASE blanks from RAC source; preserve DATABASE on value conflict.",
            "UNLIMITED values are not written into numeric permit fields.",
        ],
        "outputs": {
            "extracted_rows": str(OUT_EXTRACTED.relative_to(REPO)).replace("\\", "/"),
            "deduped_rows": str(OUT_DEDUPED.relative_to(REPO)).replace("\\", "/"),
            "import_candidates": str(OUT_CANDIDATES.relative_to(REPO)).replace("\\", "/"),
            "conflicts": str(OUT_CONFLICTS.relative_to(REPO)).replace("\\", "/"),
            "database_patch_preview_if_locked": db_write.get("patch_preview", ""),
        },
    }
    OUT_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # rejects sidecar
    rej_path = OUT_DIR / "2026_rac_recommended_permits_rejects.csv"
    if rejects:
        write_csv(rej_path, rejects)
    else:
        with rej_path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["note"])
            w.writeheader()
            w.writerow({"note": "NO_REJECTS"})

    print(json.dumps({
        "extracted_raw": len(extracted),
        "deduped": len(deduped),
        "rejects": len(rejects),
        "internal_conflicts": len(internal_conflicts),
        "db_conflicts": len(db_sync["conflicts"]),
        "db_rows_updated": db_sync["updates"],
        "filled_res": db_sync["filled_res"],
        "filled_nr": db_sync["filled_nr"],
        "filled_total": db_sync["filled_total"],
    }, indent=2))


if __name__ == "__main__":
    main()
