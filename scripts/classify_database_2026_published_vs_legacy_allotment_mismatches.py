from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
OUT_CSV = ROOT / "processed_data" / "audits" / "database_2026_published_vs_legacy_allotment_actions.csv"
OUT_JSON = ROOT / "processed_data" / "audits" / "database_2026_published_vs_legacy_allotment_actions.json"
OUT_MD = ROOT / "processed_data" / "audits" / "database_2026_published_vs_legacy_allotment_actions.md"


PREFER_PUBLISHED_FAMILIES = {
    "BONUS_LE_BIG_GAME",
    "BONUS_OIL_BIG_GAME",
    "SPORTSMAN_PERMIT",
    "BEAR_DRAW",
}

REVIEW_FAMILIES = {
    "BONUS_CWMU_BIG_GAME",
}

TOTAL_ONLY_PROMOTE_FAMILIES = {
    "PRIVATE_LANDS_ONLY_ANTLERLESS_ELK",
}

PREFERENCE_RELATED_FAMILIES = {
    "Preference",
    "PREFERENCE_DEDICATED_HUNTER_DEER",
    "BONUS_EWE_BIGHORN",
}


@dataclass(frozen=True)
class PermitTriple:
    res: str
    nr: str
    total: str

    @property
    def any_value(self) -> bool:
        return any(v != "" for v in (self.res, self.nr, self.total))

    @property
    def has_split(self) -> bool:
        return self.res != "" or self.nr != ""

    @property
    def split_missing(self) -> bool:
        return self.res == "" and self.nr == ""

    @property
    def total_missing_or_zero(self) -> bool:
        return self.total in {"", "0"}

    @property
    def fully_blank_or_zero(self) -> bool:
        return all(v in {"", "0"} for v in (self.res, self.nr, self.total))


def clean(value: object) -> str:
    return str(value or "").strip()


def triple(row: dict[str, str], prefix: str) -> PermitTriple:
    return PermitTriple(
        clean(row.get(f"{prefix}_res")),
        clean(row.get(f"{prefix}_nr")),
        clean(row.get(f"{prefix}_total")),
    )


def family_for(row: dict[str, str]) -> str:
    return clean(row.get("draw_2026_system_type")) or clean(row.get("hunt_class")) or "UNKNOWN"


def mismatch(published: PermitTriple, legacy: PermitTriple) -> bool:
    return (
        published.any_value
        or legacy.any_value
    ) and (published.res, published.nr, published.total) != (legacy.res, legacy.nr, legacy.total)


def classify_action(row: dict[str, str], published: PermitTriple, legacy: PermitTriple) -> tuple[str, str]:
    family = family_for(row)
    published_missing = published.fully_blank_or_zero
    legacy_has_split = legacy.has_split
    legacy_total_only = legacy.total != "" and legacy.split_missing

    if family in PREFER_PUBLISHED_FAMILIES:
        return (
            "KEEP_PUBLISHED_MIRROR_LEGACY",
            "Published 2026 permit values remain authoritative for this family even when legacy allotment differs.",
        )

    if family in REVIEW_FAMILIES:
        return (
            "MANUAL_REVIEW_REQUIRED",
            "CWMU family remains legacy-compatible only; do not auto-promote or overwrite published fields.",
        )

    if family in TOTAL_ONLY_PROMOTE_FAMILIES:
        if published_missing and legacy_total_only:
            return (
                "PROMOTE_ALLOTMENT_TO_PUBLISHED_TOTAL_ONLY",
                "Published 2026 values are blank/zero and legacy carries only a total; safe total-only promotion candidate.",
            )
        return (
            "KEEP_PUBLISHED_MIRROR_LEGACY",
            "Published 2026 values already exist or legacy is not a clean total-only case; keep published authority.",
        )

    if family in PREFERENCE_RELATED_FAMILIES:
        if family == "PREFERENCE_DEDICATED_HUNTER_DEER":
            return (
                "KEEP_PUBLISHED_MIRROR_LEGACY",
                "Dedicated Hunter legacy totals appear semantic and must not override published values.",
            )
        if published_missing and legacy_has_split:
            return (
                "PROMOTE_ALLOTMENT_TO_PUBLISHED_SPLIT",
                "Published 2026 values are blank/zero and legacy carries split values; promote only as an explicit reviewed repair.",
            )
        if published_missing and legacy_total_only:
            return (
                "PROMOTE_ALLOTMENT_TO_PUBLISHED_TOTAL_ONLY",
                "Published 2026 values are blank/zero and legacy carries only total; promote only as an explicit reviewed repair.",
            )
        return (
            "KEEP_PUBLISHED_MIRROR_LEGACY",
            "Published 2026 values already exist; do not let legacy allotment take priority over published edits.",
        )

    if published_missing and legacy_has_split:
        return (
            "PROMOTE_ALLOTMENT_TO_PUBLISHED_SPLIT",
            "Published 2026 values are blank/zero and legacy carries split values; candidate for reviewed promotion.",
        )

    if published_missing and legacy_total_only:
        return (
            "PROMOTE_ALLOTMENT_TO_PUBLISHED_TOTAL_ONLY",
            "Published 2026 values are blank/zero and legacy carries only total; candidate for reviewed promotion.",
        )

    if published.any_value:
        return (
            "KEEP_PUBLISHED_MIRROR_LEGACY",
            "Published 2026 values already exist and remain authoritative; legacy should mirror down for compatibility only.",
        )

    return (
        "MANUAL_REVIEW_REQUIRED",
        "Mismatch did not fit a safe automatic bucket.",
    )


def recommended_legacy_status(action: str) -> str:
    if action == "KEEP_PUBLISHED_MIRROR_LEGACY":
        return "DERIVED_FROM_PUBLISHED_2026_PERMITS_COMPAT"
    if action == "PROMOTE_ALLOTMENT_TO_PUBLISHED_SPLIT":
        return "REVIEWED_PROMOTION_CANDIDATE_SPLIT_ONLY"
    if action == "PROMOTE_ALLOTMENT_TO_PUBLISHED_TOTAL_ONLY":
        return "REVIEWED_PROMOTION_CANDIDATE_TOTAL_ONLY"
    return "MANUAL_REVIEW_REQUIRED"


def read_database() -> list[dict[str, str]]:
    with DATABASE.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in rows:
        published = triple(row, "permits_2026")
        legacy = triple(row, "permit_allotment_2026")
        if not mismatch(published, legacy) or not legacy.any_value:
            continue
        action, rationale = classify_action(row, published, legacy)
        out.append(
            {
                "hunt_code": clean(row.get("hunt_code")),
                "hunt_name": clean(row.get("hunt_name")),
                "species": clean(row.get("species")),
                "weapon": clean(row.get("weapon")),
                "hunt_type": clean(row.get("hunt_type")),
                "hunt_class": clean(row.get("hunt_class")),
                "draw_2026_system_type": clean(row.get("draw_2026_system_type")),
                "permits_2026_res": published.res,
                "permits_2026_nr": published.nr,
                "permits_2026_total": published.total,
                "permits_2026_source": clean(row.get("permits_2026_source")),
                "permit_allotment_2026_res": legacy.res,
                "permit_allotment_2026_nr": legacy.nr,
                "permit_allotment_2026_total": legacy.total,
                "permit_allotment_2026_source": clean(row.get("permit_allotment_2026_source")),
                "permit_allotment_2026_status": clean(row.get("permit_allotment_2026_status")),
                "mismatch_action": action,
                "recommended_legacy_status": recommended_legacy_status(action),
                "published_missing_or_zero": "TRUE" if published.fully_blank_or_zero else "FALSE",
                "legacy_has_split": "TRUE" if legacy.has_split else "FALSE",
                "legacy_total_only": "TRUE" if legacy.total != "" and legacy.split_missing else "FALSE",
                "rationale": rationale,
            }
        )
    return out


def build_summary(rows: list[dict[str, str]]) -> dict[str, object]:
    by_action = Counter(row["mismatch_action"] for row in rows)
    by_family = Counter(row["draw_2026_system_type"] or row["hunt_class"] or "UNKNOWN" for row in rows)
    family_action: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        family = row["draw_2026_system_type"] or row["hunt_class"] or "UNKNOWN"
        family_action[family][row["mismatch_action"]] += 1

    return {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "database_file": str(DATABASE.relative_to(ROOT)).replace("\\", "/"),
        "hard_rules": {
            "published_runtime_authority": "permits_2026_res/nr/total",
            "legacy_compatibility_only": "permit_allotment_2026_*",
            "no_legacy_priority_over_published": True,
            "no_automatic_db_mutation": True,
        },
        "row_count": len(rows),
        "action_counts": dict(by_action),
        "family_counts": dict(by_family),
        "family_action_counts": {
            family: dict(counter)
            for family, counter in sorted(family_action.items())
        },
        "outputs": {
            "csv": str(OUT_CSV.relative_to(ROOT)).replace("\\", "/"),
            "json": str(OUT_JSON.relative_to(ROOT)).replace("\\", "/"),
            "md": str(OUT_MD.relative_to(ROOT)).replace("\\", "/"),
        },
    }


def write_md(path: Path, rows: list[dict[str, str]], summary: dict[str, object]) -> None:
    action_counts = summary["action_counts"]
    family_action_counts = summary["family_action_counts"]
    lines = [
        "# DATABASE 2026 Published vs Legacy Allotment Mismatch Actions",
        "",
        f"Generated: `{summary['generated_at_utc']}`",
        "",
        "## Hard Rules",
        "",
        "- `permits_2026_res/nr/total` is the only runtime authority.",
        "- `permit_allotment_2026_*` is legacy compatibility only.",
        "- Legacy allotment must never take priority over published 2026 permit edits.",
        "- This report classifies repair actions only. It does not mutate `DATABASE.csv`.",
        "",
        "## Action Counts",
        "",
    ]
    for action, count in sorted(action_counts.items()):
        lines.append(f"- `{action}`: `{count}`")
    lines.extend(
        [
            "",
            "## Family Action Counts",
            "",
            "| Family | KEEP | PROMOTE SPLIT | PROMOTE TOTAL ONLY | MANUAL |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for family, counts in sorted(family_action_counts.items()):
        lines.append(
            f"| `{family}` | {counts.get('KEEP_PUBLISHED_MIRROR_LEGACY', 0)} | "
            f"{counts.get('PROMOTE_ALLOTMENT_TO_PUBLISHED_SPLIT', 0)} | "
            f"{counts.get('PROMOTE_ALLOTMENT_TO_PUBLISHED_TOTAL_ONLY', 0)} | "
            f"{counts.get('MANUAL_REVIEW_REQUIRED', 0)} |"
        )
    lines.extend(
        [
            "",
            "## Sample Rows",
            "",
            "| Hunt | Family | Published | Legacy | Action |",
            "|---|---|---|---|---|",
        ]
    )
    for row in rows[:30]:
        lines.append(
            f"| `{row['hunt_code']}` {row['hunt_name']} | "
            f"`{row['draw_2026_system_type'] or row['hunt_class']}` | "
            f"`{row['permits_2026_res']}/{row['permits_2026_nr']}/{row['permits_2026_total']}` | "
            f"`{row['permit_allotment_2026_res']}/{row['permit_allotment_2026_nr']}/{row['permit_allotment_2026_total']}` | "
            f"`{row['mismatch_action']}` |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    rows = build_rows(read_database())
    summary = build_summary(rows)
    write_csv(OUT_CSV, rows)
    OUT_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_md(OUT_MD, rows, summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
