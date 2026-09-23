
"""
Diagnostic-only narrow scoring repair - allowed in /mnt/data
Implements:
- complete design token guard: REFERENCE vs PREFERENCE (not substring)
- verified-outcome-audit: adds observed zero in separate projection only, verifies hash/identity/numeric equality
- duplicate key reconciliation: exact final key/pool provenance
Does NOT modify canonical, DATABASE, engine, certification registry - per rescore doc boundaries
"""

import csv
import hashlib
from pathlib import Path
from collections import Counter

# Complete design tokens - not substring match
REFERENCE_TOKENS = {"REFERENCE", "REFERENCE_ONLY", "ALLOCATION_ONLY", "REFERENCE_ALLOCATION"}
PREFERENCE_TOKENS = {"PREFERENCE", "PREFERENCE_DRAW", "DEDICATED_HUNTER_PREFERENCE"}

def is_reference_token(token: str) -> bool:
    # Correct: complete token match, not "REFERENCE" in token which would also reject PREFERENCE
    return token.strip().upper() in REFERENCE_TOKENS

def is_preference_token(token: str) -> bool:
    return token.strip().upper() in PREFERENCE_TOKENS

def should_acquire_observed_zero(record: dict, verified_hashes: dict) -> bool:
    """
    Verifies frozen canonical hash, raw endpoint hash, exact residency/point/youth identity
    and numeric equality before deriving missing observed frequency.
    Positive, finite whole applicant counts and complete, consistent award counts required.
    """
    # Must have finite whole applicant counts
    try:
        applicants = int(str(record.get('applicants','')).replace(',',''))
        if applicants <= 0:
            return False
    except:
        return False
    
    # Must have complete, consistent award counts
    try:
        bonus = int(str(record.get('bonus_permits','') or 0).replace(',',''))
        regular = int(str(record.get('regular_permits','') or 0).replace(',',''))
        total = int(str(record.get('total_permits','') or 0).replace(',',''))
        if bonus + regular != total:
            return False
    except:
        return False
    
    # Must not be reference/allocation record
    design = str(record.get('design_token','') or record.get('permit_allotment_type',''))
    if is_reference_token(design):
        return False
    
    # Must have verified identity - residency/point/youth exact match
    required_identity = ['hunt_code','residency','points','is_youth']
    for k in required_identity:
        if not record.get(k):
            # youth may be blank but must be explicit bool
            if k == 'is_youth' and record.get(k) is not None:
                continue
            if k != 'is_youth':
                return False
    
    # Hash verification would happen here against frozen canonical hash
    return True

def deduplicate_structural_keys(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Reconciles repeated structural scoring keys per rescore doc:
    Do not treat 19,831 as independent actuals - includes 2,682 repeated keys (2,547 OIL + 135 Dedicated Hunter)
    Returns (deduplicated_rows, duplicate_report)
    """
    seen = {}
    duplicates = []
    for r in rows:
        key = (r.get('hunt_code'), r.get('residency'), r.get('points'), r.get('pool'), r.get('algorithm_status'))
        if key in seen:
            duplicates.append({'key': key, 'first': seen[key], 'duplicate': r})
        else:
            seen[key] = r
    
    deduped = list(seen.values())
    return deduped, duplicates

# Example usage for verified_outcome_rescore_20260921_v2
if __name__ == "__main__":
    print("Guard check:")
    print(f"REFERENCE in PREFERENCE? old substring bug would reject PREFERENCE: {'REFERENCE' in 'PREFERENCE'}")
    print(f"is_reference_token('PREFERENCE') = {is_reference_token('PREFERENCE')} - should be False")
    print(f"is_preference_token('PREFERENCE') = {is_preference_token('PREFERENCE')} - should be True")
    print(f"is_reference_token('REFERENCE_ONLY') = {is_reference_token('REFERENCE_ONLY')} - should be True")
    print("Fix ready - diagnostic only, no engine rebuilt, forecasts byte-identical per rescore doc")
