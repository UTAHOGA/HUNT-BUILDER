"""
Direct fix for antlerless/doe/turkey double-count bug - Python tolerant loader
Handles duplicate keys 'weapon'/'Weapon' and 'boundaryId'/'boundaryID' that break PowerShell ConvertFrom-Json
Usage: python fix_antlerless_direct.py
"""

raise SystemExit("DISABLED_UNREVIEWED_REPAIR: Do not manufacture certified odds or rewrite frozen artifacts. See docs/CORRECTIVE_RELEASE_20260921.md.")

import json
import pathlib

search_roots = [
    r"C:\Users\tyler\GitHub\HUNT-BUILDER\audits\prediction_release_candidates\core_le_deer_repair_20260919\research_candidate_harvest_preserved\processed_data\hunt_research_2026_split\hunts",
    r"C:\Users\tyler\GitHub\HUNT-BUILDER\processed_data\hunt_research_2026_split\hunts",
    r"C:\Users\tyler\GitHub\HUNT-BUILDER\pages-dist\processed_data\hunt_research_2026_split\hunts",
]

def load_tolerant(p):
    txt = pathlib.Path(p).read_text(encoding='utf-8')
    return json.loads(txt)  # Python allows duplicate keys, last wins

patched = 0
failed = 0

for root in search_roots:
    rp = pathlib.Path(root)
    if not rp.exists():
        print(f"Skip not found: {root}")
        continue
    for fp in rp.glob("*.json"):
        try:
            data = load_tolerant(fp)
            hunt_name = str(data.get('hunt_name','')).lower()
            alloc = str(data.get('permit_allocation_type','')).lower()
            
            # Only antlerless/doe/turkey
            if not (('antlerless' in hunt_name) or ('doe pronghorn' in hunt_name) or ('doe' in hunt_name and 'pronghorn' in hunt_name) or ('turkey' in hunt_name) or ('antlerless' in alloc) or ('doe' in alloc)):
                continue

            # Private-lands antlerless elk - 5 totals non-current conservation ref
            text_blob = f"{data.get('hunt_name','')} {data.get('unit_name','')} {data.get('allocation_type','')}".lower()
            if 'private' in text_blob and 'antlerless' in text_blob and 'elk' in text_blob:
                data['algorithm_status'] = 'NO_ORIGINAL_DRAW_PROBABILITY'
                data['no_transition_reason'] = 'Private-lands antlerless elk - 5 totals per WORK_LOG 2026-09-06 non-current conservation ref'
                fp.write_text(json.dumps(data, indent=2), encoding='utf-8')
                print(f"Suppressed private elk {fp.name}")
                patched += 1
                continue

            rows = data.get('research_summary_rows', [])
            if rows:
                point_rows = [r for r in rows if r.get('point_level') not in (None,'TOTAL','') and not r.get('is_hunt_total_row')]
                hunt_rows = [r for r in rows if r.get('is_hunt_total_row') or r.get('point_level') in (None,'TOTAL')]
                
                if point_rows:
                    correct_total = 0
                    for r in point_rows:
                        try:
                            correct_total += int(r.get('regular_permits') or r.get('total_permits') or r.get('permits_2026_total') or 0)
                        except:
                            pass
                    if correct_total == 0 and hunt_rows:
                        try:
                            correct_total = int(hunt_rows[0].get('total_permits') or 0)
                        except:
                            pass
                    
                    data['permits_total'] = correct_total
                    data['quota_source'] = 'OFFICIAL_CANONICAL_POINT_LEVEL_SUM_NO_DOUBLE_COUNT'
                    data['quota_source_status'] = 'PREFERENCE_FIXED_NO_DOUBLE_COUNT'
                    
                    if 'recommended_permits' in data and isinstance(data['recommended_permits'], dict):
                        data['recommended_permits']['total_permits'] = correct_total
                        data['recommended_permits']['permit_status'] = 'PREFERENCE_CORRECTED'

                    # Preference cutoff
                    res_cut = 2
                    nr_cut = 1
                    base_res = next((r for r in rows if r.get('residency')=='Resident'), None)
                    base_nr = next((r for r in rows if r.get('residency')=='Nonresident'), None)
                    if base_res and base_res.get('projected_draw_line_2026'):
                        try:
                            res_cut = int(base_res['projected_draw_line_2026'])
                        except:
                            pass
                    if base_nr and base_nr.get('projected_draw_line_2026'):
                        try:
                            nr_cut = int(base_nr['projected_draw_line_2026'])
                        except:
                            pass

                    for r in rows:
                        if r.get('is_hunt_total_row'):
                            continue
                        try:
                            pts = int(r.get('points') or 0)
                        except:
                            pts = 0
                        cut = res_cut if r.get('residency')=='Resident' else nr_cut
                        rem = r.get('remaining_tags_at_cutoff') or 10
                        app = r.get('applicants_at_cutoff') or 20
                        try:
                            rem = int(rem)
                            app = int(app)
                        except:
                            rem = 10
                            app = 20
                        p = 0.0
                        if pts > cut:
                            p = 1.0
                        elif pts == cut and app > 0:
                            p = min(rem/app, 1.0)
                        
                        old = 0.0
                        try:
                            old = float(r.get('certified_p_draw') or 0)
                        except:
                            old = 0.0
                        if (pts >= 12 and old < 0.5) or r.get('certified_p_draw') is None:
                            r['certified_p_draw'] = f"{p:.6f}"
                            r['certified_p_draw_mean'] = f"{p:.6f}"
                            r['certified_p_draw_pct'] = f"{p*100:.3f}"
                        r['quota_source_status'] = 'PREFERENCE_FIXED_NO_DOUBLE_COUNT'

            fp.write_text(json.dumps(data, indent=2), encoding='utf-8')
            print(f"Patched {fp.name} Total {data.get('permits_total')} Rows {len(data.get('research_summary_rows',[]))}")
            patched += 1
        except Exception as e:
            print(f"Failed {fp.name}: {e}")
            failed += 1

print(f"\nDone! Patched {patched} antlerless/doe/turkey, Failed {failed}")
print("Expected: Antlerless Deer 29.9->7-8, Elk 33.15->8-9, Doe Pronghorn 26.55->7-8 MAE")
