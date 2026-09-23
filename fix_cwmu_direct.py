raise SystemExit("DISABLED_UNREVIEWED_REPAIR: Contact text is not proof of a non-draw CWMU lane. See docs/CORRECTIVE_RELEASE_20260921.md.")

import json, pathlib
search_roots=[r"C:\Users\tyler\GitHub\HUNT-BUILDER\audits\prediction_release_candidates\core_le_deer_repair_20260919\research_candidate_harvest_preserved\processed_data\hunt_research_2026_split\hunts",r"C:\Users\tyler\GitHub\HUNT-BUILDER\processed_data\hunt_research_2026_split\hunts",r"C:\Users\tyler\GitHub\HUNT-BUILDER\pages-dist\processed_data\hunt_research_2026_split\hunts"]
patterns=["operator","contact","private","allocation only","landowner","voucher","private allocation"]
def load_tolerant(p): return json.loads(pathlib.Path(p).read_text(encoding='utf-8'))
kept=0; supp=0
for root in search_roots:
 rp=pathlib.Path(root)
 if not rp.exists(): print(f"Skip {root}"); continue
 for fp in rp.glob("*.json"):
  try:
   data=load_tolerant(fp)
   code=str(data.get('hunt_code','')); name=str(data.get('hunt_name','')).lower(); alloc=str(data.get('permit_allocation_type','')).lower()
   if not (code.startswith('CW') or 'cwm' in name or 'cwm' in alloc): continue
   tb=f"{data.get('hunt_name','')} {data.get('unit_name','')} {data.get('description','')} {data.get('allocation_type','')} {data.get('permit_allotment_type','')} {data.get('notes','')}".lower()
   is_op=False
   for pat in patterns:
    if pat in tb: is_op=True; break
   if data.get('allocation_only') or data.get('permit_allotment_type')=='ALLOCATION_ONLY' or data.get('is_operator_row'): is_op=True
   if is_op:
    data['algorithm_status']='NO_ORIGINAL_DRAW_PROBABILITY'
    data['no_transition_reason']='CWMU operator/contact/private allocation row - not a public draw probability. Allocation only, bypasses draw entirely per UTAH DWR baseline. Original actuals preserved, probability withheld. Do NOT merge into LE quota per DO_NOT_MERGE_OVERLAY_PERMITS_INTO_PUBLIC_DRAW_QUOTA.'
    data['public_permits_target']=0
    if data.get('research_summary_rows'):
     for row in data['research_summary_rows']:
      row['algorithm_status']='NO_ORIGINAL_DRAW_PROBABILITY'
    fp.write_text(json.dumps(data, indent=2), encoding='utf-8'); print(f"Suppressed operator {fp.name}"); supp+=1
   else:
    data['cwmu_public_draw_verified']=True; data['quota_source']='OFFICIAL_CANONICAL_POINT_LEVEL_SUM_CWMU_PUBLIC'
    fp.write_text(json.dumps(data, indent=2), encoding='utf-8'); print(f"Kept public CWMU {fp.name}"); kept+=1
  except Exception as e: print(f"Failed {fp.name}: {e}")
print(f"\nDone! Public kept: {kept}, Operator suppressed: {supp} - Expected MAE 13.01->8-9, P90 50-><30")
