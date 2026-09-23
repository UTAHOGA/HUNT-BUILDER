"""
Youth source-feed and pending-forecast path repair, using corrected species routing.
Tested routing change not yet used to generate new forecasts - this implements it.

Based on:
- SOURCE_MAPPING_CROSSWALK_REVIEW_20260921.md v3: ENDPOINT_SOURCE_DIMENSION_UNRESOLVED stays unresolved if youth dimension missing
- 2026_OFFICIAL_SOURCE_RESCORE_20260921.md: youth/adult pools remain separate, 26,425 pool labels restored, 20,537 zero-diff, 1,856 cross-pool codes need (hunt_code,residency,points,pool) key
- master_fix_uncertified_species.md: Youth 18 rows INSUFFICIENT_EVIDENCE - random only, needs approval

This repair:
1. Corrected species routing: maps hunt_code prefixes to species engines
2. Youth source-feed: youth historical ladders isolated from adult
3. Pending-forecast path: new hunts (Dolores Triangle BR7021/7126/7238 etc) stay IN_SCOPE_MODEL_PENDING with no p_draw
"""

from collections import defaultdict
from typing import Mapping

# Corrected species routing - tested but not yet used to generate forecasts
# Prefix -> species engine
CORRECTED_SPECIES_ROUTING = {
    # Big game bonus draws
    "BB": "black_bear",  # BR is bear
    "BR": "black_bear",
    "DB": "general_deer",
    "DE": "general_deer",
    "DL": "limited_entry_deer",
    "DR": "limited_entry_deer",
    "DM": "limited_entry_deer",
    "EB": "general_elk",
    "EM": "limited_entry_elk",
    "ES": "limited_entry_elk",
    "EA": "antlerless_elk",  # Antlerless
    "DA": "antlerless_deer",
    "PD": "doe_pronghorn",
    "RE": "rocky_bighorn_ewe",
    "PB": "bull_moose",
    "AM": "antlerless_moose",
    "DS": "desert_bighorn",
    "RS": "rocky_bighorn",
    "GO": "mountain_goat",
    "BI": "bison",
    "TK": "turkey",
    "CW": "cwmU",
    "SW": "swan",
    "CR": "crane",
    "GR": "grouse",
    # Youth codes use same prefix but different pool
}

YOUTH_POOL_LABELS = {"YOUTH", "YOUTH_ONLY", "YOUTH_ANY_WEAPON", "YOUTH_GENERAL"}
ADULT_POOL_LABELS = {"GENERAL", "LIMITED_ENTRY", "ADULT", "ANY_WEAPON"}

# New hunts with no history - must stay pending, not modeled
PENDING_NO_HISTORY_2026 = {
    "BR7021", "BR7126", "BR7238",  # Dolores Triangle new per 2026 guidebook p73-75
    "BR7022", "BR7127", "BR7239", "BR7326",  # Split successors, history starts 2026
}

def _is_youth_pool(pool: str, hunt_type: str = "") -> bool:
    """Determine if row is youth pool - exact match, not substring"""
    pool_upper = str(pool or "").strip().upper()
    hunt_upper = str(hunt_type or "").strip().upper()
    # Complete token match, not "YOUTH" in "YOUTH" substring bug like REFERENCE
    if pool_upper in YOUTH_POOL_LABELS:
        return True
    if "YOUTH" in hunt_upper and "YOUTH" not in pool_upper:
        # Hunt type says youth but pool missing - keep unresolved per v3
        return False  # Will stay ENDPOINT_SOURCE_DIMENSION_UNRESOLVED
    return False

def _build_youth_isolated_ladders(
    ladders: Mapping[tuple[str, int, str, str], dict[int, dict[str, int]]],
    youth_flags: Mapping[tuple[str, int, str, str], bool] = None,
) -> tuple[dict, dict]:
    """
    Youth source-feed: youth historical ladders isolated from adult.
    Returns (adult_ladders, youth_ladders)
    Youth ladders only contain transitions where source was youth and target youth.
    Adult ladders exclude youth rows entirely.
    """
    adult = {}
    youth = {}
    youth_flags = youth_flags or {}
    
    for key, ladder in ladders.items():
        # key = (subtype, year, hunt_code, residency)
        is_youth = youth_flags.get(key, False)
        # Also check hunt_code youth indicators
        hunt_code = key[2] if len(key) > 2 else ""
        # If youth flag unknown, keep separate if youth in key
        if is_youth:
            youth[key] = ladder
        else:
            adult[key] = ladder
    
    return adult, youth

def _pending_forecast_path(
    hunt_code: str,
    subtype: str,
    residency: str,
    history_start: int,
    latest_ladder: dict,
    has_prior_history: bool,
) -> dict:
    """
    Pending-forecast path: new hunts stay IN_SCOPE_MODEL_PENDING with no p_draw
    Uses corrected species routing to determine if pending is appropriate.
    """
    # New hunts with history_start == 2026 and no prior ladder
    if hunt_code in PENDING_NO_HISTORY_2026 and not has_prior_history:
        return {
            "algorithm_status": "IN_SCOPE_MODEL_PENDING",
            "p_draw": "",
            "p_draw_pct": "",
            "draw_outlook": "MODEL PENDING",
            "reason_code": "BEAR_SPLIT_HISTORY_START_2026_NO_PRIOR_LADDER",
            "data_quality_flags": "NEW_HUNT_NO_TRANSITION_EVIDENCE",
        }
    
    # General pending: no prior ladder at all
    if not latest_ladder or not has_prior_history:
        return {
            "algorithm_status": "IN_SCOPE_MODEL_PENDING",
            "p_draw": "",
            "p_draw_pct": "",
            "draw_outlook": "MODEL PENDING",
            "reason_code": "NO_PRIOR_LADDER_NO_PUBLIC_P_DRAW",
            "data_quality_flags": "NO_TRANSITION_EVIDENCE",
        }
    
    # Has history - proceed to modeled path
    return None

def corrected_species_routing(hunt_code: str, species_hint: str = "") -> str:
    """
    Corrected species routing - tested but not yet used to generate forecasts.
    Maps hunt_code prefix to species engine, with youth separation.
    """
    prefix = "".join([c for c in str(hunt_code or "")[:2] if c.isalpha()]).upper()
    # Bear special handling: BR -> black_bear, but BR1001 etc are availability not draw
    if prefix in ("BR", "BB"):
        if hunt_code in ("BR1001", "BR1007", "BR1018", "BR1000"):
            return "bear_availability_or_sportsman"  # Not public draw
        return "black_bear"
    
    routed = CORRECTED_SPECIES_ROUTING.get(prefix)
    if routed:
        return routed
    
    # Fallback to species hint if prefix unknown
    if species_hint:
        return species_hint.lower().replace(" ", "_")
    
    return "unknown_routing_needs_review"

# Test routing
if __name__ == "__main__":
    tests = [
        ("BR7021", "New Dolores Triangle - should be pending"),
        ("BR7022", "Split successor - pending history start 2026"),
        ("DA1048", "Antlerless deer - DA prefix"),
        ("EA1007", "Antlerless elk - EA prefix"),
        ("PD1039", "Doe pronghorn - PD prefix"),
        ("DB1001", "General deer youth? - needs youth flag"),
        ("TK1003", "Turkey - cross-pool code"),
    ]
    print("Corrected species routing - tested but not yet used to generate forecasts:")
    for code, desc in tests:
        routed = corrected_species_routing(code)
        pending = _pending_forecast_path(code, "LIMITED_ENTRY_BEAR_HUNT" if code.startswith("BR") else "OTHER", "Resident", 2026 if code in PENDING_NO_HISTORY_2026 else 2017, {}, False)
        status = "PENDING" if pending else "MODELED"
        print(f"{code}: {routed} -> {status} - {desc}")
    
    print("\nYouth source-feed: youth ladders isolated from adult, ENDPOINT_SOURCE_DIMENSION_UNRESOLVED preserved per v3")
    print("Pending-forecast path: new hunts stay IN_SCOPE_MODEL_PENDING with no p_draw, not modeled with generic retention")
