# FIX PREFERENCE FAMILY - Antlerless Deer/Elk, Doe Pronghorn, Turkey, Dedicated Hunter
# Root cause per fix_other_engines_plan.md: Historical test adapter counted BOTH hunt_total_row + point_level_rows, doubling permit supply
# Fixed for general deer (Box Elder 225+20 not 450+40), NOT yet fixed for antlerless/turkey/DH
# MAE: Antlerless Deer 29.9, Antlerless Elk 33.15, Doe Pronghorn 26.55, Turkey 24.38, Dedicated Hunter 31.06 - all EXPERIMENTAL_NOT_CERTIFIED
# These are PREFERENCE family, not BONUS - old code applied bonus weighting incorrectly

def fix_preference_adapter_double_count(canonical_yearly_rows):
    """
    canonical_yearly_rows: list of dicts from data_truth/draw_results_truth/normalized/canonical_yearly/YEAR/*.csv
    Each has hunt_code, residency, point_level, regular_permits, bonus_permits, total_permits, is_hunt_total_row flag
    
    OLD BUG: adapter did sum(point_level_rows) + hunt_total_row = double count
    Example: Box Elder 225 resident + 20 nonresident became 450+40
    
    FIX: Use ONLY sum(point_level_rows.regular_permits) per hunt_code+residency
    """
    from collections import defaultdict
    
    grouped = defaultdict(list)
    for r in canonical_yearly_rows:
        key = (r["hunt_code"], r["residency"], r["year"])
        grouped[key].append(r)
    
    fixed = []
    for key, rows in grouped.items():
        hunt_code, residency, year = key
        
        # Separate hunt-total vs point-level
        hunt_total_rows = [r for r in rows if r.get("is_hunt_total_row") or r.get("point_level") == "TOTAL" or r.get("point_level") is None]
        point_level_rows = [r for r in rows if not r.get("is_hunt_total_row") and r.get("point_level") not in (None, "TOTAL", "")]
        
        if point_level_rows:
            # FIX: Use ONLY sum(point_level_rows.regular_permits), never add hunt_total
            total_regular = sum(int(r.get("regular_permits", 0) or 0) for r in point_level_rows)
            # Preserve separate R/NR regular-round allocations from canonicals even where Planner shows combined
            # Do NOT use DATABASE.csv combined total
            for r in point_level_rows:
                r["fixed_total_permits"] = total_regular if r["residency"] == residency else r.get("regular_permits")
                r["quota_source"] = "OFFICIAL_CANONICAL_POINT_LEVEL_SUM"
                r["quota_source_status"] = "PREFERENCE_FIXED_NO_DOUBLE_COUNT"
                fixed.append(r)
        else:
            # No point-level rows, use hunt-total if exists (rare for preference)
            for r in hunt_total_rows:
                r["quota_source"] = "OFFICIAL_CANONICAL_HUNT_TOTAL_ONLY"
                fixed.append(r)
    
    return fixed

def preference_probability_model(cutoff_point, applicants_at_cutoff, remaining_tags_at_cutoff, point_level):
    """
    Preference probability: p=1 above cutoff, p=0 below, p=remaining_tags_at_cutoff / applicants_at_cutoff at cutoff
    Do NOT forecast 100% at cutoff when official is fractional
    Do NOT model new entrants from statewide point-purchase totals - model from historical 0-point lane transitions in same hunt family only
    """
    if point_level > cutoff_point:
        return 1.0
    elif point_level < cutoff_point:
        return 0.0
    else:  # point_level == cutoff_point
        if applicants_at_cutoff == 0:
            return 0.0
        p = remaining_tags_at_cutoff / applicants_at_cutoff
        # Cap at 1.0, but do NOT force to 1.0 if official is fractional
        return min(p, 1.0)

# Specific fixes per family:

# 1. PREFERENCE_ANTLERLESS_DEER (977 rows, 29.9 MAE) - apply fix_preference_adapter_double_count
# 2. PREFERENCE_ANTLERLESS_ELK (4,396 rows, 33.15 MAE) - same + private-lands totals
#    Private-lands antlerless elk totals (5 private-lands totals per WORK_LOG 2026-09-06) must stay as non-current conservation reference, current public quota blank
#    Filter: if row contains "private land" or "private-land" and allocation_type == "PRIVATE_LANDS", set NO_ORIGINAL_DRAW_PROBABILITY for current, preserve historical

def is_private_lands_antlerless_elk(row):
    text = " ".join([str(row.get(k, "")) for k in ["hunt_name", "unit_name", "allocation_type"]]).lower()
    return "private" in text and "antlerless" in text and "elk" in text

# 3. PREFERENCE_DOE_PRONGHORN (1,059 rows, 26.55 MAE) - same double-count fix

# 4. BONUS_TURKEY (515 rows, 24.38 MAE) - Turkey is bonus but small sample, same double-count fix + bonus 50/50 logic not preference
#    Turkey uses bonus 50/50: 50% permits for max points, 50% random with bonus entries, same as LE
#    Fix quota source to OFFICIAL_CANONICAL_POINT_LEVEL_SUM, not hunt_total+point_level

# 5. PREFERENCE_DEDICATED_HUNTER_DEER (2,390 rows, 31.06 MAE) - choice between general vs DH, cannot earn points in both
#    Need attrition model: DH applicants who draw DH leave general deer ladder entirely
#    Current engine assumes they advance in general deer ladder - over-predicts general deer demand
#    Fix: In general deer engine, subtract DH winners from general deer applicant pool

def fix_dedicated_hunter_attrition(general_deer_applicants, dh_winners):
    """
    general_deer_applicants: dict point_level -> count for general deer
    dh_winners: dict point_level -> count of DH draw winners who were also in general deer pool
    
    DH winners leave general deer ladder entirely - they do NOT advance to point+1 in general deer
    """
    fixed = {}
    for pt, count in general_deer_applicants.items():
        winners_at_pt = dh_winners.get(pt, 0)
        fixed[pt] = max(0, count - winners_at_pt)  # DH winners removed from general pool
    return fixed

# Expected impact after fixes:
# - Antlerless Deer: 29.9 -> 7-8 MAE (double-count fix removes 100% over-supply error)
# - Antlerless Elk: 33.15 -> 8-9 MAE (double-count + private-lands filter)
# - Doe Pronghorn: 26.55 -> 7-8 MAE
# - Turkey: 24.38 -> 10-12 MAE (small sample, may still be EXPERIMENTAL)
# - Dedicated Hunter: 31.06 -> 15-18 MAE (attrition model helps but choice model complex)

# Verification per frozen gates:
# - MAE <=10, P90 <=30, tail <=10%, 0 false guarantees, 0 unresolved gaps
# - For PREFERENCE family, preference cutoff logic must be p=1 above, p=0 below, p=remaining/applicants at cutoff
# - No statewide point-purchase fabrication for new entrants
# - Protected files byte-identical, no deploy until passes
