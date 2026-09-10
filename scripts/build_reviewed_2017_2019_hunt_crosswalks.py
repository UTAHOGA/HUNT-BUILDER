from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REBUILD = (
    ROOT
    / "audits"
    / "prediction_rebuilds"
    / "fresh_official_draw_truth_rebuild_2017_forward_20260909"
)
OUT_DIR = REBUILD / "crosswalks"

SOURCES = {
    2017: REBUILD
    / "2017"
    / "frozen_v3_complete_draw_year_rule"
    / "draw_results_2017_for_2018_source_truth_candidate_frozen.csv",
    2018: REBUILD
    / "2018"
    / "frozen_bear_pursuit_repaired"
    / "draw_results_2018_for_2019_source_truth_candidate_frozen.csv",
    2019: REBUILD
    / "2019"
    / "frozen"
    / "draw_results_2019_for_2020_source_truth_candidate_frozen.csv",
}

OUTPUTS = {
    (2017, 2018): OUT_DIR / "reviewed_hunt_identity_crosswalk_2017_to_2018.csv",
    (2018, 2019): OUT_DIR / "reviewed_hunt_identity_crosswalk_2018_to_2019.csv",
}
SUMMARY = OUT_DIR / "reviewed_hunt_identity_crosswalk_2017_to_2019_summary.json"

FIELDS = [
    "transition_id",
    "from_draw_year",
    "to_draw_year",
    "from_model_year",
    "to_model_year",
    "from_hunt_code",
    "to_hunt_code",
    "candidate_to_hunt_codes",
    "transition_type",
    "review_status",
    "identity_continuity_verified",
    "applicant_stack_carry_forward_allowed",
    "carry_forward_scope",
    "carry_forward_draw_designs",
    "from_only_draw_designs",
    "to_only_draw_designs",
    "from_hunt_name",
    "to_hunt_name",
    "from_species",
    "to_species",
    "from_sex_types",
    "to_sex_types",
    "from_hunt_types",
    "to_hunt_types",
    "from_weapons",
    "to_weapons",
    "from_draw_designs",
    "to_draw_designs",
    "from_source_files",
    "from_source_pages",
    "to_source_files",
    "to_source_pages",
    "regulation_evidence_files",
    "regulation_evidence_pages",
    "decision_basis",
]

NAME_ALIAS_EXACT = {
    (2017, 2018): {
        "BI6500",
        "BI6509",
        "BR7308",
        "CG7605",
        "CG7606",
        "DB1009",
        "DB1010",
        "DB1051",
        "DB1052",
        "DS1000",
        "GO6815",
        "MA1000",
        "MA1001",
        "MA1002",
        "MA1003",
    },
    (2018, 2019): {
        "BR7308",
        "CG7605",
        "CG7606",
        "DB1259",
        "EA1012",
        "EA1148",
        "EB3535",
        "MB6215",
        "PD1028",
        "PD1029",
    },
}

EXACT_BOUNDARY_CHANGE = {
    (2017, 2018): {
        "BR7120",
        "BR7221",
        "BR7316",
        "PB5008",
        "PB5033",
    },
    (2018, 2019): {"BI6507"},
}

EXACT_PROGRAM_CHANGE = {
    (2017, 2018): {
        "DA1011",
        "DA1018",
        "DA1019",
    },
    (2018, 2019): {"DA1029", "DA1030"},
}

SAFE_RECODE = {
    (2017, 2018): {
        ("DA1003", "DA1038"): "Exact official hunt name, species, weapon, and preference design continue under the target code.",
        ("EA1083", "EA1197"): "San Juan, North Elk Ridge continues as San Juan, Elk Ridge with the same species, weapon, and preference design.",
        ("RS1000", "RS0001"): "Sportsman Rocky Mountain bighorn retains the same random-only species identity under the target code; there is no applicant ladder to carry.",
        ("TK1000", "TK0001"): "Sportsman bearded turkey retains the same random-only species identity under the target code; there is no applicant ladder to carry.",
        ("DB1045", "DB0007"): "The 2017 Sportsman Deer row uses published code DB1045 while 2018 uses DB0007. This design-scoped alias is random-only and cannot carry an applicant ladder.",
    },
    (2018, 2019): {
        ("DA1037", "DA1016"): "Exact Plateau, East Angle antlerless-deer identity continues under the target code.",
        ("DA1038", "DA1003"): "Exact Monroe/Plateau, Sevier Valley antlerless-deer identity continues under the target code.",
        ("MB6204", "MB6240"): "Exact Chimney Rock CWMU bull-moose identity continues under the target code.",
    },
}

STRUCTURAL_LINKS = {
    (2017, 2018): {
        "GO6812": (
            "ONE_TO_MANY_SPLIT",
            ("GO6818", "GO6819", "GO6820"),
            "The combined Wasatch Mountains goat hunt split into Box Elder Peak, Lone Peak, and Timpanogos hunts.",
        ),
        "RS6705": (
            "BOUNDARY_CHANGE",
            ("RS6719",),
            "The successor removes the prior Wasatch Mountains West wording and is treated as a boundary change.",
        ),
    },
    (2018, 2019): {
        "BR7002": (
            "BOUNDARY_CHANGE",
            ("BR7017",),
            "The combined spring Cache/East Canyon/Morgan-South Rich/Ogden hunt narrows to Cache/Ogden.",
        ),
        "BR7006": (
            "BOUNDARY_CHANGE",
            ("BR7018",),
            "The combined spring Chalk Creek/Kamas/North Slope Summit hunt narrows to Kamas/North Slope Summit.",
        ),
        "BR7103": (
            "ONE_TO_MANY_SPLIT",
            ("BR7121", "BR7122"),
            "The combined summer Bear hunt split into Cache/Ogden and Chalk Creek/East Canyon/Morgan-South Rich hunts.",
        ),
        "BR7107": (
            "BOUNDARY_CHANGE",
            ("BR7123",),
            "The combined summer Chalk Creek/Kamas/North Slope Summit hunt narrows to Kamas/North Slope Summit.",
        ),
        "BR7202": (
            "ONE_TO_MANY_SPLIT",
            ("BR7228", "BR7230", "BR7234"),
            "The former combined fall Bear identity was restructured into multiple Cache/Ogden and Chalk Creek/East Canyon/Morgan-South Rich opportunities.",
        ),
        "BR7206": (
            "ONE_TO_MANY_SPLIT",
            ("BR7229", "BR7235"),
            "The former combined fall Bear identity was restructured into multiple Kamas/North Slope Summit opportunities.",
        ),
        "BR7302": (
            "BOUNDARY_CHANGE",
            ("BR7320",),
            "The combined multi-season Bear hunt narrows to Cache/Ogden.",
        ),
        "BR7306": (
            "BOUNDARY_CHANGE",
            ("BR7321",),
            "The combined multi-season Bear hunt narrows to Kamas/North Slope Summit.",
        ),
        "CG7501": (
            "BOUNDARY_CHANGE",
            ("CG1034",),
            "The former Chalk Creek/Kamas cougar identity changes to Kamas under a new code.",
        ),
        "PD1027": (
            "ONE_TO_MANY_SPLIT",
            ("PD1034", "PD1035"),
            "The Fillmore, Oak Creek South doe-pronghorn identity appears as two target codes; the parent stack cannot be duplicated.",
        ),
    },
}

UNRESOLVED_CANDIDATES = {
    (2017, 2018): {
        "CG7504": ("CG1029",),
        "CG7600": ("CG1030",),
        "DA1006": ("DA1032",),
        "DA1008": ("DA1032",),
        "DA1016": ("DA1037", "DA1038"),
    },
    (2018, 2019): {
        "DA1034": ("DA1043",),
    },
}

REGULATION_EVIDENCE = {
    (2017, 2018): (
        "pipeline/RAW/hunt_unit_database/2017/pdf/guidebooks/2017_field_regs.pdf|"
        "pipeline/RAW/hunt_unit_database/2018/pdf/guidebooks/2018_biggameapp.pdf|"
        "pipeline/RAW/hunt_unit_database/2018/pdf/guidebooks/2018_bear.pdf",
        "2017_field_regs:2-3|2018_biggameapp:20,27-30|2018_bear:2,17-20",
    ),
    (2018, 2019): (
        "pipeline/RAW/hunt_unit_database/2018/pdf/guidebooks/2018_biggameapp.pdf|"
        "pipeline/RAW/hunt_unit_database/2018/pdf/guidebooks/2018_bear.pdf|"
        "pipeline/RAW/hunt_unit_database/2019/pdf/guidebooks/2019_biggameapp.pdf|"
        "pipeline/RAW/hunt_unit_database/2019/pdf/guidebooks/2019_bear.pdf",
        "2018_biggameapp:20,27-30|2018_bear:17-20|2019_biggameapp:23,29-30|2019_bear:17,19-20",
    ),
}

NON_STACK_DESIGNS = {
    "SPORTSMAN_RANDOM_ONLY",
    "REFERENCE_LIFETIME_PERMIT_HOLDER",
}


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def normalize(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", clean(value).lower()).strip()


def join(values: set[str] | list[str] | tuple[str, ...]) -> str:
    return "|".join(sorted(clean(value) for value in values if clean(value)))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def malformed_name(value: str) -> bool:
    tokens = clean(value).split()
    return bool(tokens) and all(
        token == "N/A" or token.replace(".", "", 1).isdigit() for token in tokens
    )


def load_identities(path: Path) -> dict[str, dict[str, set[str]]]:
    fields = (
        "hunt_name",
        "species",
        "sex_type",
        "hunt_type",
        "weapon",
        "draw_design",
        "source_file",
        "pdf_page",
    )
    grouped: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: {field: set() for field in fields}
    )
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            code = clean(row.get("hunt_code")).upper()
            if not code:
                continue
            for field in fields:
                value = clean(row.get(field))
                if value:
                    grouped[code][field].add(value)
    return dict(grouped)


def primary_name(identity: dict[str, set[str]]) -> str:
    names = [name for name in identity.get("hunt_name", set()) if not malformed_name(name)]
    if not names:
        return join(identity.get("hunt_name", set()))
    non_sportsman = [name for name in names if not normalize(name).startswith("sportsman ")]
    candidates = non_sportsman or names
    return max(candidates, key=lambda value: (len(normalize(value).split()), len(value), value))


def get(identity: dict[str, set[str]] | None, field: str) -> str:
    if not identity:
        return ""
    if field == "hunt_name":
        return primary_name(identity)
    return join(identity.get(field, set()))


def common_designs(
    left: dict[str, set[str]] | None, right: dict[str, set[str]] | None
) -> set[str]:
    if not left or not right:
        return set()
    return left.get("draw_design", set()) & right.get("draw_design", set())


def stack_designs(designs: set[str]) -> set[str]:
    return {
        design
        for design in designs
        if design not in NON_STACK_DESIGNS and not design.startswith("REFERENCE_")
    }


def evidence(identity: dict[str, set[str]] | None, field: str) -> str:
    if not identity:
        return ""
    return join(identity.get(field, set()))


def make_row(
    pair: tuple[int, int],
    sequence: int,
    left_code: str,
    right_code: str,
    transition_type: str,
    left: dict[str, set[str]] | None,
    right: dict[str, set[str]] | None,
    decision_basis: str,
    *,
    candidate_codes: tuple[str, ...] = (),
    design_scope: set[str] | None = None,
) -> dict[str, object]:
    from_year, to_year = pair
    common = common_designs(left, right)
    if design_scope is not None:
        common &= design_scope
    eligible = stack_designs(common)
    identity_verified = transition_type in {"SAME_IDENTITY", "NAME_ALIAS"}
    carry = identity_verified and bool(eligible)
    from_designs = left.get("draw_design", set()) if left else set()
    to_designs = right.get("draw_design", set()) if right else set()
    regulations, pages = REGULATION_EVIDENCE[pair]
    return {
        "transition_id": f"{from_year}_{to_year}_{sequence:04d}",
        "from_draw_year": from_year,
        "to_draw_year": to_year,
        "from_model_year": from_year + 1,
        "to_model_year": to_year + 1,
        "from_hunt_code": left_code,
        "to_hunt_code": right_code,
        "candidate_to_hunt_codes": join(candidate_codes),
        "transition_type": transition_type,
        "review_status": (
            "REVIEWED_BLOCKED_UNRESOLVED"
            if transition_type == "UNRESOLVED"
            else "REVIEWED"
        ),
        "identity_continuity_verified": "TRUE" if identity_verified else "FALSE",
        "applicant_stack_carry_forward_allowed": "TRUE" if carry else "FALSE",
        "carry_forward_scope": (
            "SAME_DRAW_DESIGN_AND_RESIDENCY_LANE_ONLY" if carry else "NONE"
        ),
        "carry_forward_draw_designs": join(eligible),
        "from_only_draw_designs": join(from_designs - common),
        "to_only_draw_designs": join(to_designs - common),
        "from_hunt_name": get(left, "hunt_name"),
        "to_hunt_name": get(right, "hunt_name"),
        "from_species": get(left, "species"),
        "to_species": get(right, "species"),
        "from_sex_types": get(left, "sex_type"),
        "to_sex_types": get(right, "sex_type"),
        "from_hunt_types": get(left, "hunt_type"),
        "to_hunt_types": get(right, "hunt_type"),
        "from_weapons": get(left, "weapon"),
        "to_weapons": get(right, "weapon"),
        "from_draw_designs": join(from_designs),
        "to_draw_designs": join(to_designs),
        "from_source_files": evidence(left, "source_file"),
        "from_source_pages": evidence(left, "pdf_page"),
        "to_source_files": evidence(right, "source_file"),
        "to_source_pages": evidence(right, "pdf_page"),
        "regulation_evidence_files": regulations,
        "regulation_evidence_pages": pages,
        "decision_basis": decision_basis,
    }


def build_transition(
    pair: tuple[int, int],
    identities: dict[int, dict[str, dict[str, set[str]]]],
) -> list[dict[str, object]]:
    from_year, to_year = pair
    left_by_code = identities[from_year]
    right_by_code = identities[to_year]
    left_codes = set(left_by_code)
    right_codes = set(right_by_code)
    common_codes = left_codes & right_codes
    dropped = left_codes - right_codes
    added = right_codes - left_codes
    rows: list[dict[str, object]] = []
    sequence = 0

    def append(*args: object, **kwargs: object) -> None:
        nonlocal sequence
        sequence += 1
        rows.append(make_row(pair, sequence, *args, **kwargs))

    for code in sorted(common_codes):
        left = left_by_code[code]
        right = right_by_code[code]
        if code == "DB1045" and pair == (2017, 2018):
            append(
                code,
                code,
                "SAME_IDENTITY",
                left,
                right,
                "The Oak Creek limited-entry hunt retains exact-code identity. The separate 2017 Sportsman Deer use of DB1045 is handled in a design-scoped alias row.",
                design_scope={"BONUS_LE_BIG_GAME"},
            )
            continue
        if code in EXACT_PROGRAM_CHANGE[pair]:
            transition_type = "PROGRAM_CHANGE"
            basis = "Official source wording or draw-family evidence changes the program or permit entitlement; automatic carry-forward is blocked."
        elif code in EXACT_BOUNDARY_CHANGE[pair]:
            transition_type = "BOUNDARY_CHANGE"
            basis = "Official guidebook wording documents a substantive boundary/name change under the retained code; automatic carry-forward is blocked."
        elif code in NAME_ALIAS_EXACT[pair]:
            transition_type = "NAME_ALIAS"
            basis = "Official rows retain the same code, species, program, unit identity, and weapon; the printed difference is a reviewed naming or punctuation alias."
        elif common_designs(left, right):
            transition_type = "SAME_IDENTITY"
            basis = "Exact hunt code and at least one official draw-design lane continue with compatible species and hunt identity. Carry-forward is limited to draw designs present in both years."
        else:
            transition_type = "PROGRAM_CHANGE"
            basis = "Exact hunt code remains, but no official draw-design lane is common to both years; automatic carry-forward is blocked."
        append(code, code, transition_type, left, right, basis)

    consumed_sources: set[str] = set()
    consumed_targets: set[str] = set()
    for (source_code, target_code), basis in sorted(SAFE_RECODE[pair].items()):
        left = left_by_code[source_code]
        right = right_by_code[target_code]
        transition_type = "NAME_ALIAS" if source_code in {"RS1000", "TK1000", "DB1045"} else "SAME_IDENTITY"
        design_scope = {"SPORTSMAN_RANDOM_ONLY"} if source_code == "DB1045" else None
        append(
            source_code,
            target_code,
            transition_type,
            left,
            right,
            basis,
            design_scope=design_scope,
        )
        consumed_sources.add(source_code)
        consumed_targets.add(target_code)

    for source_code, (transition_type, target_codes, basis) in sorted(
        STRUCTURAL_LINKS[pair].items()
    ):
        for target_code in target_codes:
            append(
                source_code,
                target_code,
                transition_type,
                left_by_code[source_code],
                right_by_code[target_code],
                basis,
            )
            consumed_targets.add(target_code)
        consumed_sources.add(source_code)

    for source_code in sorted(dropped - consumed_sources):
        left = left_by_code[source_code]
        candidates = UNRESOLVED_CANDIDATES[pair].get(source_code, ())
        if candidates:
            append(
                source_code,
                "",
                "UNRESOLVED",
                left,
                None,
                "A plausible target-year identity exists, but official evidence does not support a verified one-to-one continuation. No applicant history may carry.",
                candidate_codes=candidates,
            )
        else:
            append(
                source_code,
                "",
                "ELIMINATED_HUNT",
                left,
                None,
                "The official source hunt has no verified target-year successor in the scorable truth population.",
            )

    for target_code in sorted(added - consumed_targets):
        right = right_by_code[target_code]
        special = ""
        if pair == (2017, 2018) and target_code == "BR7016":
            special = " DWR changed Wasatch Mountains West-Central spring Bear from harvest-objective opportunity to a limited-entry draw."
        append(
            "",
            target_code,
            "NEW_HUNT",
            None,
            right,
            "The official target hunt has no verified source-year predecessor and begins without an inherited applicant stack."
            + special,
        )

    return rows


def validate_rows(
    pair: tuple[int, int],
    rows: list[dict[str, object]],
    identities: dict[int, dict[str, dict[str, set[str]]]],
) -> dict[str, object]:
    from_year, to_year = pair
    source_codes = set(identities[from_year])
    target_codes = set(identities[to_year])
    represented_source = {str(row["from_hunt_code"]) for row in rows if row["from_hunt_code"]}
    represented_target = {str(row["to_hunt_code"]) for row in rows if row["to_hunt_code"]}
    transition_ids = [str(row["transition_id"]) for row in rows]
    bad_carry = [
        str(row["transition_id"])
        for row in rows
        if row["applicant_stack_carry_forward_allowed"] == "TRUE"
        and (
            row["transition_type"] not in {"SAME_IDENTITY", "NAME_ALIAS"}
            or not row["carry_forward_draw_designs"]
            or row["carry_forward_scope"]
            != "SAME_DRAW_DESIGN_AND_RESIDENCY_LANE_ONLY"
        )
    ]
    structural_carry = [
        str(row["transition_id"])
        for row in rows
        if row["transition_type"]
        in {
            "BOUNDARY_CHANGE",
            "PROGRAM_CHANGE",
            "ONE_TO_MANY_SPLIT",
            "NEW_HUNT",
            "ELIMINATED_HUNT",
            "UNRESOLVED",
        }
        and row["applicant_stack_carry_forward_allowed"] == "TRUE"
    ]
    result = {
        "from_draw_year": from_year,
        "to_draw_year": to_year,
        "source_hunt_codes": len(source_codes),
        "target_hunt_codes": len(target_codes),
        "crosswalk_rows": len(rows),
        "transition_type_counts": dict(
            sorted(Counter(str(row["transition_type"]) for row in rows).items())
        ),
        "carry_forward_rows": sum(
            row["applicant_stack_carry_forward_allowed"] == "TRUE" for row in rows
        ),
        "source_codes_missing_from_table": sorted(source_codes - represented_source),
        "target_codes_missing_from_table": sorted(target_codes - represented_target),
        "duplicate_transition_ids": sorted(
            key for key, count in Counter(transition_ids).items() if count > 1
        ),
        "invalid_carry_rows": bad_carry,
        "structural_rows_with_carry": structural_carry,
    }
    result["status"] = (
        "PASS"
        if not any(
            (
                result["source_codes_missing_from_table"],
                result["target_codes_missing_from_table"],
                result["duplicate_transition_ids"],
                result["invalid_carry_rows"],
                result["structural_rows_with_carry"],
            )
        )
        else "FAIL"
    )
    return result


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    missing = [str(path) for path in SOURCES.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing frozen source candidates: {missing}")
    identities = {year: load_identities(path) for year, path in SOURCES.items()}
    validations: dict[str, object] = {}
    for pair, output in OUTPUTS.items():
        rows = build_transition(pair, identities)
        validation = validate_rows(pair, rows, identities)
        if validation["status"] != "PASS":
            raise RuntimeError(json.dumps(validation, indent=2))
        write_csv(output, rows)
        validations[f"{pair[0]}->{pair[1]}"] = validation

    summary = {
        "status": "PASS",
        "scope": "Reviewed hunt-identity transitions for fresh official draw years 2017-2019. These files are audit-only and are not wired into the prediction engine.",
        "carry_forward_rule": "Only SAME_IDENTITY and NAME_ALIAS rows with a common forecastable draw design may carry applicants, and only within the same draw-design and residency lane.",
        "source_files": {
            str(year): {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256(path),
            }
            for year, path in SOURCES.items()
        },
        "outputs": {
            f"{pair[0]}->{pair[1]}": output.relative_to(ROOT).as_posix()
            for pair, output in OUTPUTS.items()
        },
        "validations": validations,
        "production_integration": "NOT_INTEGRATED",
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
