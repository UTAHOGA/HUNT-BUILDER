#!/usr/bin/env python3
"""Build pre-draw-only identity exceptions for the 2018 through 2026 folds.

The source side is official draw truth already available at the end of year N.
The target side is limited to DWR application guidebooks published before the
target drawing. Target-year draw results are intentionally not opened.

This is an exceptions-only crosswalk. Source hunt codes not represented here
continue under their unchanged code. Only a verified one-to-one recode may
change a code; every documented boundary/program change or split is blocked.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
REBUILD = (
    ROOT
    / "audits"
    / "prediction_rebuilds"
    / "fresh_official_draw_truth_rebuild_2017_forward_20260909"
)
OUT_DIR = REBUILD / "crosswalks" / "pre_draw_source_only"

SOURCE_TRUTH = {
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
    / "frozen_bear_pursuit_repaired"
    / "draw_results_2019_for_2020_source_truth_candidate_frozen.csv",
    2020: REBUILD
    / "2020"
    / "frozen"
    / "draw_results_2020_for_2021_source_truth_candidate_frozen.csv",
    2021: REBUILD
    / "2021"
    / "frozen"
    / "draw_results_2021_for_2022_source_truth_candidate_frozen.csv",
    2022: REBUILD
    / "2022"
    / "frozen"
    / "draw_results_2022_for_2023_source_truth_candidate_frozen.csv",
    2023: REBUILD
    / "2023"
    / "frozen"
    / "draw_results_2023_for_2024_source_truth_candidate_frozen.csv",
    2024: REBUILD
    / "2024"
    / "frozen"
    / "draw_results_2024_for_2025_source_truth_candidate_frozen.csv",
    2025: REBUILD
    / "2025"
    / "frozen"
    / "draw_results_2025_for_2026_source_truth_candidate_frozen.csv",
}

TARGET_APPLICATION_SOURCES = {
    2018: {
        "big_game": ROOT
        / "pipeline/RAW/hunt_unit_database/2018/pdf/guidebooks/2018_biggameapp.pdf",
        "bear": ROOT
        / "pipeline/RAW/hunt_unit_database/2018/pdf/guidebooks/2018_bear.pdf",
    },
    2019: {
        "big_game": ROOT
        / "pipeline/RAW/hunt_unit_database/2019/pdf/guidebooks/2019_biggameapp.pdf",
        "bear": ROOT
        / "pipeline/RAW/hunt_unit_database/2019/pdf/guidebooks/2019_bear.pdf",
        "cougar": ROOT
        / "pipeline/RAW/hunt_unit_database/2019/pdf/guidebooks/2019-20_cougar.pdf",
    },
    2020: {
        "big_game": ROOT
        / "pipeline/RAW/hunt_unit_database/2020/pdf/guidebooks/2020_biggameapp.pdf",
        "bear": ROOT
        / "pipeline/RAW/hunt_unit_database/2020/pdf/guidebooks/2020_bear.pdf",
        "cougar": ROOT
        / "pipeline/RAW/hunt_unit_database/2020/pdf/guidebooks/2020-21_cougar.pdf",
    },
    2021: {
        "big_game": ROOT
        / "pipeline/RAW/hunt_unit_database/2021/pdf/guidebooks/2021_biggameapp.pdf",
        "bear": ROOT
        / "pipeline/RAW/hunt_unit_database/2021/pdf/guidebooks/2021_bear.pdf",
        "cougar": ROOT
        / "pipeline/RAW/hunt_unit_database/2021/pdf/guidebooks/2021-22_cougar.pdf",
    },
    2022: {
        "big_game": ROOT
        / "pipeline/RAW/hunt_unit_database/2022/pdf/guidebooks/2022_biggameapp.pdf",
        "bear": ROOT
        / "pipeline/RAW/hunt_unit_database/2022/pdf/guidebooks/2022_bear.pdf",
        "cougar": ROOT
        / "pipeline/RAW/hunt_unit_database/2022/pdf/guidebooks/2022-23_cougar.pdf",
    },
    2023: {
        "big_game": ROOT
        / "pipeline/RAW/hunt_unit_database/2023/pdf/guidebooks/2023_biggameapp.pdf",
        "bear": ROOT
        / "pipeline/RAW/hunt_unit_database/2023/pdf/guidebooks/2023_bear.pdf",
        "cougar": ROOT
        / "pipeline/RAW/hunt_unit_database/2023/pdf/guidebooks/2023-24_cougar.pdf",
    },
    2024: {
        "big_game": ROOT
        / "pipeline/RAW/hunt_unit_database/2024/pdf/guidebooks/2024_biggameapp.pdf",
        "bear": ROOT
        / "pipeline/RAW/hunt_unit_database/2024/pdf/guidebooks/2024_bear.pdf",
    },
    2025: {
        "big_game": ROOT
        / "pipeline/RAW/hunt_unit_database/2025/pdf/guidebooks/2025_biggameapp.pdf",
        "bear": ROOT
        / "pipeline/RAW/hunt_unit_database/2025/pdf/guidebooks/black-bear-and-cougar-guidebook-2025.pdf",
    },
    2026: {
        "big_game": ROOT
        / "pipeline/RAW/hunt_unit_database/2026/pdf/guidebooks/biggameapp.pdf",
        "bear": ROOT
        / "pipeline/RAW/hunt_unit_database/2026/pdf/guidebooks/black-bear-cougar-furbearer-guidebook.pdf",
    },
}

PRE_DRAW_TIMING_CHECKS = {
    (2018, "big_game"): ("March 1, 2018", "May 31, 2018"),
    (2018, "bear"): ("Feb. 26, 2018", "drawing results"),
    (2019, "big_game"): ("March 7, 2019", "May 30, 2019"),
    (2019, "bear"): ("Feb. 25, 2019", "drawing results"),
    (2019, "cougar"): ("Oct. 8, 2019", "Oct. 21, 2019"),
    (2020, "big_game"): ("Jan. 30, 2020", "May 29, 2020"),
    (2020, "bear"): ("Feb. 3–24, 2020", "March 4, 2020"),
    (2020, "cougar"): ("Sept. 15–Oct. 6, 2020", "Oct. 19, 2020"),
    (2021, "big_game"): ("Jan. 28, 2021", "May 31, 2021"),
    (2021, "bear"): ("Feb. 2, 2021", "March 3, 2021"),
    (2021, "cougar"): ("Sept. 14, 2021", "Oct. 11, 2021"),
    (2022, "big_game"): ("Jan. 27 to March 3, 2022", "May 31, 2022"),
    (2022, "bear"): ("Feb. 1–22, 2022", "March 2, 2022"),
    (2022, "cougar"): ("Feb. 1–22, 2022", "March 2, 2022"),
    (2023, "big_game"): ("March 23 to April 27, 2023", "May 31, 2023"),
    (2023, "bear"): ("Feb. 7, 2023", "March 3, 2023"),
    (2023, "cougar"): ("May 3, 2023", "no longer in a limited entry draw"),
    (2024, "big_game"): ("March 21 to April 25, 2024", "May 16, 2024"),
    (2024, "bear"): ("Feb. 6–20, 2024", "March 1, 2024"),
    (2025, "big_game"): ("March 20 to April 24, 2025", "May 15, 2025"),
    (2025, "bear"): ("Feb. 4–18, 2025", "Feb. 28, 2025"),
    (2026, "big_game"): ("March 19 to April 23, 2026", "May 31, 2026"),
    (2026, "bear"): ("Feb. 10, 2026", "March 5, 2026"),
}

# Every decision below is reviewable from source-year truth plus the named
# target application guidebook. No target draw-result identity is consulted.
EXCEPTIONS = {
    (2017, 2018): [
        ("PB5008", "PB5008", "BOUNDARY_CHANGE", "big_game", ("PB5008",), "The 2018 application table prints Oak Creek South as a name change; the prior stack is conservatively blocked."),
        ("PB5033", "PB5033", "BOUNDARY_CHANGE", "big_game", ("PB5033",), "The 2018 application table prints Oak Creek South as a name change; the prior stack is conservatively blocked."),
        ("GO6812", "GO6818", "ONE_TO_MANY_SPLIT", "big_game", ("GO6818", "GO6819", "GO6820"), "The 2018 application table creates three named Wasatch mountain-goat hunts; the combined source stack cannot be cloned."),
        ("GO6812", "GO6819", "ONE_TO_MANY_SPLIT", "big_game", ("GO6818", "GO6819", "GO6820"), "The 2018 application table creates three named Wasatch mountain-goat hunts; the combined source stack cannot be cloned."),
        ("GO6812", "GO6820", "ONE_TO_MANY_SPLIT", "big_game", ("GO6818", "GO6819", "GO6820"), "The 2018 application table creates three named Wasatch mountain-goat hunts; the combined source stack cannot be cloned."),
        ("RS6705", "RS6719", "BOUNDARY_CHANGE", "big_game", ("RS6719",), "The 2018 application table explicitly marks the successor as a new hunt with a new boundary."),
        ("BR7120", "BR7120", "BOUNDARY_CHANGE", "bear", ("BR7120",), "The 2018 bear application table changes the source unit wording to Wasatch Mtns, West-Central."),
        ("BR7221", "BR7221", "BOUNDARY_CHANGE", "bear", ("BR7221",), "The 2018 bear application table changes the source unit wording to Wasatch Mtns, West-Central."),
        ("BR7316", "BR7316", "BOUNDARY_CHANGE", "bear", ("BR7316",), "The 2018 bear application table changes the source unit wording to Wasatch Mtns, West-Central."),
    ],
    (2018, 2019): [
        ("MB6204", "MB6240", "NAME_ALIAS", "big_game", ("MB6240",), "The source Chimney Rock CWMU identity is printed as Chimney Rock under the new code in the pre-draw 2019 application table."),
        ("BI6507", "BI6507", "BOUNDARY_CHANGE", "big_game", ("BI6507",), "The 2019 application table explicitly prints a name change adding Anthro; the prior stack is blocked."),
        ("BR7002", "BR7017", "BOUNDARY_CHANGE", "bear", ("BR7017",), "The 2019 bear application table identifies Cache/Ogden as a new hunt rather than the prior combined unit."),
        ("BR7006", "BR7018", "BOUNDARY_CHANGE", "bear", ("BR7018",), "The 2019 bear application table identifies Kamas/North Slope, Summit as a new hunt rather than the prior combined unit."),
        ("BR7103", "BR7121", "ONE_TO_MANY_SPLIT", "bear", ("BR7121", "BR7122"), "The 2019 bear application table replaces the combined source opportunity with separate new hunts; no parent stack is cloned."),
        ("BR7103", "BR7122", "ONE_TO_MANY_SPLIT", "bear", ("BR7121", "BR7122"), "The 2019 bear application table replaces the combined source opportunity with separate new hunts; no parent stack is cloned."),
        ("BR7107", "BR7123", "BOUNDARY_CHANGE", "bear", ("BR7123",), "The 2019 bear application table identifies Kamas/North Slope, Summit as a new hunt rather than the prior combined unit."),
        ("BR7202", "BR7228", "ONE_TO_MANY_SPLIT", "bear", ("BR7228", "BR7230", "BR7234"), "The 2019 bear application table replaces the combined source opportunity with multiple new hunts; no parent stack is cloned."),
        ("BR7202", "BR7230", "ONE_TO_MANY_SPLIT", "bear", ("BR7228", "BR7230", "BR7234"), "The 2019 bear application table replaces the combined source opportunity with multiple new hunts; no parent stack is cloned."),
        ("BR7202", "BR7234", "ONE_TO_MANY_SPLIT", "bear", ("BR7228", "BR7230", "BR7234"), "The 2019 bear application table replaces the combined source opportunity with multiple new hunts; no parent stack is cloned."),
        ("BR7206", "BR7229", "ONE_TO_MANY_SPLIT", "bear", ("BR7229", "BR7235"), "The 2019 bear application table replaces the combined source opportunity with separate new hunts; no parent stack is cloned."),
        ("BR7206", "BR7235", "ONE_TO_MANY_SPLIT", "bear", ("BR7229", "BR7235"), "The 2019 bear application table replaces the combined source opportunity with separate new hunts; no parent stack is cloned."),
        ("BR7302", "BR7320", "BOUNDARY_CHANGE", "bear", ("BR7320",), "The 2019 bear application table identifies Cache/Ogden as a new hunt rather than the prior combined unit."),
        ("BR7306", "BR7321", "BOUNDARY_CHANGE", "bear", ("BR7321",), "The 2019 bear application table identifies Kamas/North Slope, Summit as a new hunt rather than the prior combined unit."),
        ("CG7501", "CG1034", "BOUNDARY_CHANGE", "cougar", ("CG1034",), "The 2019 cougar application table identifies Kamas as a new hunt rather than the prior combined unit."),
    ],
    (2019, 2020): [
        ("EB3004", "EB3004", "BOUNDARY_CHANGE", "big_game", ("EB3004",), "The pre-draw 2020 application table explicitly marks the Cache, North archery hunt as a boundary change."),
        ("EB3005", "EB3005", "BOUNDARY_CHANGE", "big_game", ("EB3005",), "The pre-draw 2020 application table explicitly marks the Cache, South archery hunt as a boundary change."),
        ("EB3034", "EB3034", "BOUNDARY_CHANGE", "big_game", ("EB3034",), "The pre-draw 2020 application table explicitly marks the Cache, North early-rifle hunt as a boundary change."),
        ("EB3036", "EB3036", "BOUNDARY_CHANGE", "big_game", ("EB3036",), "The pre-draw 2020 application table explicitly marks the Cache, South early-rifle hunt as a boundary change."),
        ("EB3035", "EB3035", "BOUNDARY_CHANGE", "big_game", ("EB3035",), "The pre-draw 2020 application table explicitly marks the Cache, North late-rifle hunt as a boundary change."),
        ("EB3037", "EB3037", "BOUNDARY_CHANGE", "big_game", ("EB3037",), "The pre-draw 2020 application table explicitly marks the Cache, South late-rifle hunt as a boundary change."),
        ("EB3082", "EB3082", "BOUNDARY_CHANGE", "big_game", ("EB3082",), "The pre-draw 2020 application table explicitly marks the Cache, North muzzleloader hunt as a boundary change."),
        ("EB3083", "EB3083", "BOUNDARY_CHANGE", "big_game", ("EB3083",), "The pre-draw 2020 application table explicitly marks the Cache, South muzzleloader hunt as a boundary change."),
        ("EB3106", "EB3106", "BOUNDARY_CHANGE", "big_game", ("EB3106",), "The pre-draw 2020 application table explicitly marks the Cache, North multi-season hunt as a boundary change."),
        ("EB3107", "EB3107", "BOUNDARY_CHANGE", "big_game", ("EB3107",), "The pre-draw 2020 application table explicitly marks the Cache, South multi-season hunt as a boundary change."),
        ("DS6606", "DS6606", "BOUNDARY_CHANGE", "big_game", ("DS6606",), "The pre-draw 2020 application table explicitly marks the San Juan, Lockhart desert-bighorn hunt as a boundary change."),
        ("DS6607", "DS6607", "BOUNDARY_CHANGE", "big_game", ("DS6607",), "The pre-draw 2020 application table explicitly marks the San Juan, South desert-bighorn hunt as a boundary change."),
    ],
    (2020, 2021): [
        ("RS6708", "RS6708", "BOUNDARY_CHANGE", "big_game", ("RS6708",), "The pre-draw 2021 application table explicitly marks the North Slope, Three Corners Rocky Mountain bighorn hunt as a boundary change."),
        ("RS6709", "RS6709", "BOUNDARY_CHANGE", "big_game", ("RS6709",), "The pre-draw 2021 application table explicitly marks the North Slope, Summit/West Daggett Rocky Mountain bighorn hunt as a boundary change."),
    ],
    (2021, 2022): [
        # The 2022 application guide explicitly says bison unit boundaries
        # changed, then replaces the prior Book Cliffs structure with new
        # Bitter Creek and Little Creek/South hunts. No parent stack is cloned.
        ("BI6517", "", "BOUNDARY_CHANGE", "big_game", (), "The 2022 guide replaces the prior Book Cliffs bison structure after announcing bison boundary changes.", "31", "The 2022 bison application table lists the new Bitter Creek and Little Creek/South hunts; BI6517 is absent."),
        ("BI6519", "", "BOUNDARY_CHANGE", "big_game", (), "The 2022 guide replaces the prior Book Cliffs bison structure after announcing bison boundary changes.", "31", "The 2022 bison application table lists the new Bitter Creek and Little Creek/South hunts; BI6519 is absent."),
        ("BI6520", "", "BOUNDARY_CHANGE", "big_game", (), "The 2022 guide replaces the prior Book Cliffs bison structure after announcing bison boundary changes.", "31", "The 2022 bison application table lists the new Bitter Creek and Little Creek/South hunts; BI6520 is absent."),
        ("BI6521", "", "BOUNDARY_CHANGE", "big_game", (), "The 2022 guide replaces the prior Book Cliffs bison structure after announcing bison boundary changes.", "31", "The 2022 bison application table lists the new Bitter Creek and Little Creek/South hunts; BI6521 is absent."),
        ("BI6523", "", "BOUNDARY_CHANGE", "big_game", (), "The 2022 guide replaces the prior Book Cliffs bison structure after announcing bison boundary changes.", "31", "The 2022 bison application table lists the new Bitter Creek and Little Creek/South hunts; BI6523 is absent."),
        ("BI6524", "", "BOUNDARY_CHANGE", "big_game", (), "The 2022 guide replaces the prior Book Cliffs bison structure after announcing bison boundary changes.", "31", "The 2022 bison application table lists the new Bitter Creek and Little Creek/South hunts; BI6524 is absent."),
        ("BI6526", "", "BOUNDARY_CHANGE", "big_game", (), "The 2022 guide replaces the prior Book Cliffs bison structure after announcing bison boundary changes.", "31", "The 2022 bison application table lists the new Bitter Creek and Little Creek/South hunts; BI6526 is absent."),
        ("DS6612", "", "ELIMINATED", "big_game", (), "The source Zion desert-bighorn hunt is not offered in the complete 2022 desert-bighorn application table.", "31", "The 2022 desert-bighorn application table exhaustively lists current hunts; DS6612 is absent."),
        ("DB1210", "", "ELIMINATED", "big_game", (), "The source Blue Creek deer CWMU is not offered in the 2022 CWMU application table.", "33-35", "The 2022 deer CWMU application table exhaustively lists current CWMUs; DB1210 is absent."),
        ("DB1259", "", "ELIMINATED", "big_game", (), "The source Lone Tree Tunnel Hollow deer CWMU is not offered in the 2022 CWMU application table.", "33-35", "The 2022 deer CWMU application table exhaustively lists current CWMUs; DB1259 is absent."),
        ("DB1302", "", "ELIMINATED", "big_game", (), "The source TJ Cattle Company deer CWMU is not offered in the 2022 CWMU application table.", "33-35", "The 2022 deer CWMU application table exhaustively lists current CWMUs; DB1302 is absent."),
        ("EB3528", "", "ELIMINATED", "big_game", (), "The source Ingham Peak elk CWMU is not offered in the 2022 CWMU application table.", "35-36", "The 2022 elk CWMU application table exhaustively lists current CWMUs; EB3528 is absent."),
        ("EB3535", "", "ELIMINATED", "big_game", (), "The source Lone Tree Tunnel Hollow elk CWMU is not offered in the 2022 CWMU application table.", "35-36", "The 2022 elk CWMU application table exhaustively lists current CWMUs; EB3535 is absent."),
        ("EB3538", "", "ELIMINATED", "big_game", (), "The source Moon Ranch elk CWMU is not offered in the 2022 CWMU application table.", "35-36", "The 2022 elk CWMU application table exhaustively lists current CWMUs; EB3538 is absent."),
        ("MB6201", "", "ELIMINATED", "big_game", (), "The source Beaver Hollow moose CWMU is not offered in the 2022 CWMU application table.", "37", "The 2022 moose CWMU application table exhaustively lists current CWMUs; MB6201 is absent."),
        ("MB6225", "", "ELIMINATED", "big_game", (), "The source Wallsburg moose CWMU is not offered in the 2022 CWMU application table.", "37", "The 2022 moose CWMU application table exhaustively lists current CWMUs; MB6225 is absent."),
        ("MB6252", "", "ELIMINATED", "big_game", (), "The source Jacob's Creek moose CWMU is not offered in the 2022 CWMU application table.", "37", "The 2022 moose CWMU application table exhaustively lists current CWMUs; MB6252 is absent."),
        ("MB6257", "", "ELIMINATED", "big_game", (), "The source Ingham Peak moose CWMU is not offered in the 2022 CWMU application table.", "37", "The 2022 moose CWMU application table exhaustively lists current CWMUs; MB6257 is absent."),
        ("MB6263", "", "ELIMINATED", "big_game", (), "The source Moon Ranch moose CWMU is not offered in the 2022 CWMU application table.", "37", "The 2022 moose CWMU application table exhaustively lists current CWMUs; MB6263 is absent."),
        ("MB6264", "", "ELIMINATED", "big_game", (), "The source Sand Creek moose CWMU is not offered in the 2022 CWMU application table.", "37", "The 2022 moose CWMU application table exhaustively lists current CWMUs; MB6264 is absent."),
        ("BR7209", "", "PROGRAM_CHANGE", "bear", (), "The 2021 Monroe fall hunt is absent after the 2022 guide adds separate spring and summer Monroe hunts.", "19-20", "The complete 2022 fall table omits BR7209; new Monroe spring and summer hunts are separate programs."),
        ("BR7226", "", "PROGRAM_CHANGE", "bear", (), "The 2021 late-fall La Sal hunt is not offered in the 2022 fall table.", "20", "The complete 2022 fall table replaces the prior late-fall structure; BR7226 is absent."),
        ("BR7227", "", "PROGRAM_CHANGE", "bear", (), "The 2021 late-fall San Juan hunt is not offered in the 2022 fall table.", "20", "The complete 2022 fall table replaces the prior late-fall structure; BR7227 is absent."),
        ("BR7230", "", "PROGRAM_CHANGE", "bear", (), "The 2021 late-fall Cache/Ogden hunt is not offered in the 2022 fall table.", "20", "The complete 2022 fall table replaces the prior late-fall structure; BR7230 is absent."),
        ("BR7231", "", "PROGRAM_CHANGE", "bear", (), "The 2021 late-fall Manti-North hunt is not offered in the 2022 fall table.", "20", "The complete 2022 fall table replaces the prior late-fall structure; BR7231 is absent."),
        ("BR7232", "", "PROGRAM_CHANGE", "bear", (), "The 2021 late-fall Manti-South/San Rafael hunt is not offered in the 2022 fall table.", "20", "The complete 2022 fall table replaces the prior late-fall structure; BR7232 is absent."),
        ("BR7233", "", "PROGRAM_CHANGE", "bear", (), "The 2021 late-fall Nebo hunt is not offered in the 2022 fall table.", "20", "The complete 2022 fall table replaces the prior late-fall structure; BR7233 is absent."),
        ("BR7234", "", "PROGRAM_CHANGE", "bear", (), "The 2021 late-fall Chalk Creek/East Canyon/Morgan-South Rich hunt is not offered in the 2022 fall table.", "19-20", "The complete 2022 fall table omits BR7234; BR7019 is a separate spring hunt."),
        ("BR7235", "", "PROGRAM_CHANGE", "bear", (), "The 2021 late-fall Kamas/North Slope, Summit hunt is not offered in the 2022 fall table.", "20", "The complete 2022 fall table replaces the prior late-fall structure; BR7235 is absent."),
        ("BR7236", "", "PROGRAM_CHANGE", "bear", (), "The 2021 late-fall Plateau, Boulder/Kaiparowits hunt is not offered in the 2022 fall table.", "20-21", "The complete 2022 fall and multi-season tables omit BR7236; new multi-season hunts are separate programs."),
    ],
    (2022, 2023): [],
    (2023, 2024): [],
    (2024, 2025): [],
    (2025, 2026): [],
}

# Beginning with the heavily restructured 2023 application tables, every
# source code absent from the complete pre-draw target table is explicitly
# blocked. Absence never implies a successor and therefore never permits an
# applicant-stack carry. This is conservative source-only evidence, not a
# target-result-informed crosswalk.
AUTO_BLOCK_ABSENT = {
    (2022, 2023): {
        "big_game": {
            "scopes": {
                "BIG_GAME",
                "GENERAL_SEASON_DEER",
                "DEDICATED_HUNTER",
                "LIFETIME_GENERAL_SEASON_DEER",
                "YOUTH_ANY_BULL_ELK",
                "YOUTH_GENERAL_SEASON_DEER",
                "YOUTH_DEDICATED_HUNTER",
            },
            "transition": "UNRESOLVED_TARGET_IDENTITY",
            "pages": "42-77",
            "excerpt": "The complete 2023 big-game application tables do not contain this source hunt code; no successor is inferred.",
            "basis": "The source code is absent from the pre-draw 2023 application tables and is blocked unless a one-to-one successor is independently verified.",
        },
        "bear": {
            "scopes": {"BLACK_BEAR"},
            "transition": "UNRESOLVED_TARGET_IDENTITY",
            "pages": "36-42",
            "excerpt": "The complete 2023 Bear application tables do not contain this source hunt code; no successor is inferred.",
            "basis": "The source code is absent from the pre-draw 2023 Bear application tables and is blocked unless a one-to-one successor is independently verified.",
        },
        "cougar": {
            "scopes": {"COUGAR"},
            "transition": "PROGRAM_TERMINATED",
            "pages": "3;7;10-11",
            "excerpt": "Beginning May 3, 2023, Cougar permits are no longer in a limited-entry draw and hunting is authorized under the open-season license framework.",
            "basis": "The 2023 Cougar guide explicitly terminates the limited-entry draw; every historical Cougar applicant stack stops.",
        },
    },
    (2023, 2024): {
        "big_game": {
            "scopes": {
                "BIG_GAME",
                "GENERAL_SEASON_DEER",
                "DEDICATED_HUNTER",
                "LIFETIME_GENERAL_SEASON_DEER",
                "YOUTH_ANY_BULL_ELK",
                "YOUTH_GENERAL_SEASON_DEER",
                "YOUTH_DEDICATED_HUNTER",
            },
            "transition": "UNRESOLVED_TARGET_IDENTITY",
            "pages": "39-74",
            "excerpt": "The complete 2024 big-game application tables do not contain this source hunt code; no successor is inferred.",
            "basis": "The source code is absent from the pre-draw 2024 application tables and is blocked unless a one-to-one successor is independently verified.",
        },
        "bear": {
            "scopes": {"BLACK_BEAR"},
            "transition": "UNRESOLVED_TARGET_IDENTITY",
            "pages": "36-42",
            "excerpt": "The complete 2024 Bear application tables do not contain this source hunt code; no successor is inferred.",
            "basis": "The source code is absent from the pre-draw 2024 Bear application tables and is blocked unless a one-to-one successor is independently verified.",
        },
    },
    (2024, 2025): {
        "big_game": {
            "scopes": {
                "BIG_GAME",
                "GENERAL_SEASON_DEER",
                "DEDICATED_HUNTER",
                "LIFETIME_GENERAL_SEASON_DEER",
                "YOUTH_ANY_BULL_ELK",
                "YOUTH_GENERAL_SEASON_DEER",
                "YOUTH_DEDICATED_HUNTER",
            },
            "transition": "UNRESOLVED_TARGET_IDENTITY",
            "pages": "39-74",
            "excerpt": "The complete 2025 big-game application tables do not contain this source hunt code; no successor is inferred.",
            "basis": "The source code is absent from the pre-draw 2025 application tables and is blocked unless a one-to-one successor is independently verified.",
        },
        "bear": {
            "scopes": {"BLACK_BEAR"},
            "transition": "UNRESOLVED_TARGET_IDENTITY",
            "pages": "42-48",
            "excerpt": "The complete 2025 Bear application tables do not contain this source hunt code; no successor is inferred.",
            "basis": "The source code is absent from the pre-draw 2025 Bear application tables and is blocked unless a one-to-one successor is independently verified.",
        },
    },
    (2025, 2026): {
        "big_game": {
            "scopes": {
                "BIG_GAME",
                "GENERAL_SEASON_DEER",
                "DEDICATED_HUNTER",
                "LIFETIME_GENERAL_SEASON_DEER",
                "YOUTH_ANY_BULL_ELK",
                "YOUTH_GENERAL_SEASON_DEER",
                "YOUTH_DEDICATED_HUNTER",
            },
            "transition": "UNRESOLVED_TARGET_IDENTITY",
            "pages": "43-78",
            "excerpt": "The complete 2026 big-game application tables do not contain this source hunt code; no successor is inferred.",
            "basis": "The source code is absent from the pre-draw 2026 application tables and is blocked unless a one-to-one successor is independently verified.",
        },
        "bear": {
            "scopes": {"BLACK_BEAR"},
            "transition": "UNRESOLVED_TARGET_IDENTITY",
            "pages": "73-79",
            "excerpt": "The complete 2026 Bear application tables do not contain this source hunt code; no successor is inferred.",
            "basis": "The source code is absent from the pre-draw 2026 Bear application tables and is blocked unless a one-to-one successor is independently verified.",
        },
    },
}

FIELDS = [
    "transition_id",
    "from_draw_year",
    "to_draw_year",
    "from_hunt_code",
    "to_hunt_code",
    "candidate_to_hunt_codes",
    "transition_type",
    "identity_continuity_verified",
    "applicant_stack_carry_forward_allowed",
    "carry_forward_scope",
    "carry_forward_draw_designs",
    "from_hunt_name",
    "from_draw_designs",
    "from_source_files",
    "from_source_pages",
    "target_application_evidence_file",
    "target_application_evidence_sha256",
    "target_application_evidence_pages",
    "target_application_evidence_excerpt",
    "pre_draw_timing_evidence",
    "evidence_timing",
    "target_draw_results_used",
    "crosswalk_scope",
    "certification_use",
    "decision_basis",
]

NON_STACK_DESIGNS = {"SPORTSMAN_RANDOM_ONLY", "REFERENCE_LIFETIME_PERMIT_HOLDER"}
CODE_RE = re.compile(r"\b[A-Z]{2}\d{4}\b")


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def join(values: set[str] | tuple[str, ...] | list[str]) -> str:
    return "|".join(sorted(clean(value) for value in values if clean(value)))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_source_identities(path: Path) -> dict[str, dict[str, set[str]]]:
    fields = ("hunt_name", "draw_design", "source_file", "pdf_page", "source_scope")
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


def extract_application_evidence(path: Path) -> tuple[str, dict[str, list[dict[str, str]]]]:
    all_text: list[str] = []
    by_code: dict[str, list[dict[str, str]]] = defaultdict(list)
    reader = PdfReader(path)
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        all_text.append(text)
        lines = [clean(line) for line in text.splitlines()]
        for index, line in enumerate(lines):
            for code in CODE_RE.findall(line):
                context = clean(" ".join(lines[max(0, index - 1) : index + 2]))
                by_code[code].append(
                    {"page": str(page_number), "excerpt": context}
                )
    return clean(" ".join(all_text)), dict(by_code)


def source_value(identity: dict[str, set[str]], field: str) -> str:
    values = identity.get(field, set())
    if field == "hunt_name":
        values = {
            value
            for value in values
            if not all(token.replace(".", "", 1).isdigit() for token in value.split())
        } or values
    return join(values)


def main() -> int:
    required = list(SOURCE_TRUTH.values()) + [
        path for documents in TARGET_APPLICATION_SOURCES.values() for path in documents.values()
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing source-only crosswalk inputs: {missing}")

    source_identities = {
        year: load_source_identities(path) for year, path in SOURCE_TRUTH.items()
    }
    document_evidence: dict[tuple[int, str], dict[str, object]] = {}
    for year, documents in TARGET_APPLICATION_SOURCES.items():
        for label, path in documents.items():
            full_text, by_code = extract_application_evidence(path)
            checks = PRE_DRAW_TIMING_CHECKS[(year, label)]
            missing_checks = [check for check in checks if clean(check).lower() not in full_text.lower()]
            if missing_checks:
                raise RuntimeError(f"Pre-draw timing text missing from {path}: {missing_checks}")
            document_evidence[(year, label)] = {
                "path": path,
                "sha256": sha256(path),
                "full_text": full_text,
                "by_code": by_code,
                "timing": " | ".join(checks),
            }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, object] = {}
    for pair, decisions in EXCEPTIONS.items():
        from_year, to_year = pair
        decisions = list(decisions)
        existing_from_codes = {decision[0] for decision in decisions}
        for label, config in AUTO_BLOCK_ABSENT.get(pair, {}).items():
            evidence = document_evidence[(to_year, label)]
            for from_code, identity in sorted(source_identities[from_year].items()):
                if from_code in existing_from_codes:
                    continue
                if not (identity["source_scope"] & config["scopes"]):
                    continue
                if from_code in evidence["full_text"]:
                    continue
                decisions.append(
                    (
                        from_code,
                        "",
                        config["transition"],
                        label,
                        (),
                        config["basis"],
                        config["pages"],
                        config["excerpt"],
                    )
                )
                existing_from_codes.add(from_code)
        rows: list[dict[str, str]] = []
        identities = source_identities[from_year]
        for sequence, decision in enumerate(decisions, start=1):
            if len(decision) == 6:
                from_code, to_code, transition, label, candidates, basis = decision
                manual_pages = ""
                manual_excerpt = ""
            else:
                from_code, to_code, transition, label, candidates, basis, manual_pages, manual_excerpt = decision
            if from_code not in identities:
                raise RuntimeError(f"Source code {from_code} is missing from {SOURCE_TRUTH[from_year]}")
            evidence = document_evidence[(to_year, label)]
            code_rows = evidence["by_code"].get(to_code, []) if to_code else []
            if to_code and not code_rows:
                raise RuntimeError(f"Target code {to_code} is not printed in {evidence['path']}")
            if not to_code:
                if not manual_pages or not manual_excerpt:
                    raise RuntimeError(f"Eliminated source code {from_code} needs manual table evidence")
                if from_code in evidence["full_text"]:
                    raise RuntimeError(f"Source code {from_code} is still printed in {evidence['path']}")
            identity = identities[from_code]
            designs = {
                design
                for design in identity["draw_design"]
                if design not in NON_STACK_DESIGNS and not design.startswith("REFERENCE_")
            }
            verified = transition in {"SAME_IDENTITY", "NAME_ALIAS"}
            carry = verified and bool(designs)
            rows.append(
                {
                    "transition_id": f"PRE_DRAW_{from_year}_{to_year}_{sequence:03d}",
                    "from_draw_year": str(from_year),
                    "to_draw_year": str(to_year),
                    "from_hunt_code": from_code,
                    "to_hunt_code": to_code,
                    "candidate_to_hunt_codes": join(candidates),
                    "transition_type": transition,
                    "identity_continuity_verified": "TRUE" if verified else "FALSE",
                    "applicant_stack_carry_forward_allowed": "TRUE" if carry else "FALSE",
                    "carry_forward_scope": "SAME_DRAW_DESIGN_AND_RESIDENCY_LANE_ONLY" if carry else "NONE",
                    "carry_forward_draw_designs": join(designs) if carry else "",
                    "from_hunt_name": source_value(identity, "hunt_name"),
                    "from_draw_designs": source_value(identity, "draw_design"),
                    "from_source_files": source_value(identity, "source_file"),
                    "from_source_pages": source_value(identity, "pdf_page"),
                    "target_application_evidence_file": evidence["path"].relative_to(ROOT).as_posix(),
                    "target_application_evidence_sha256": str(evidence["sha256"]),
                    "target_application_evidence_pages": manual_pages or join({row["page"] for row in code_rows}),
                    "target_application_evidence_excerpt": manual_excerpt or " | ".join(row["excerpt"] for row in code_rows[:2]),
                    "pre_draw_timing_evidence": str(evidence["timing"]),
                    "evidence_timing": "PRE_DRAW",
                    "target_draw_results_used": "FALSE",
                    "crosswalk_scope": "EXCEPTIONS_ONLY_PRE_DRAW",
                    "certification_use": "ELIGIBLE_PRE_DRAW_IDENTITY_ONLY",
                    "decision_basis": basis,
                }
            )

        path = OUT_DIR / f"pre_draw_hunt_identity_crosswalk_{from_year}_to_{to_year}.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        invalid_carry = [
            row["transition_id"]
            for row in rows
            if row["applicant_stack_carry_forward_allowed"] == "TRUE"
            and (
                row["transition_type"] not in {"SAME_IDENTITY", "NAME_ALIAS"}
                or not row["carry_forward_draw_designs"]
            )
        ]
        if invalid_carry:
            raise RuntimeError(f"Invalid pre-draw carry decisions: {invalid_carry}")
        outputs[f"{from_year}->{to_year}"] = {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": sha256(path),
            "rows": len(rows),
            "carry_rows": sum(row["applicant_stack_carry_forward_allowed"] == "TRUE" for row in rows),
            "blocked_rows": sum(row["applicant_stack_carry_forward_allowed"] == "FALSE" for row in rows),
        }

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS_PRE_DRAW_SOURCE_ONLY",
        "scope": "Exceptions-only identity decisions available before the 2018 through 2026 target drawings.",
        "unlisted_source_code_behavior": "PASS_THROUGH_UNCHANGED_HUNT_CODE",
        "target_draw_results_used": False,
        "source_truth": {
            str(year): {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256(path),
            }
            for year, path in SOURCE_TRUTH.items()
        },
        "target_application_sources": {
            str(year): {
                label: {
                    "path": path.relative_to(ROOT).as_posix(),
                    "sha256": sha256(path),
                    "timing_checks": PRE_DRAW_TIMING_CHECKS[(year, label)],
                }
                for label, path in documents.items()
            }
            for year, documents in TARGET_APPLICATION_SOURCES.items()
        },
        "outputs": outputs,
        "production_integration": "NOT_INTEGRATED",
    }
    summary_path = OUT_DIR / "pre_draw_hunt_identity_crosswalk_2017_to_2026_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
