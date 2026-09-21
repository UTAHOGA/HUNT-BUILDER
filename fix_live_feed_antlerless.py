import json, pathlib
root=pathlib.Path(r"C:\Users\tyler\GitHub\HUNT-BUILDER\processed_data\hunt_research_2026_split\hunts")
roots=[root]
pages=pathlib.Path(r"C:\Users\tyler\GitHub\HUNT-BUILDER\pages-dist\processed_data\hunt_research_2026_split\hunts")
if pages.exists(): roots.append(pages)
def load(p): return json.loads(pathlib.Path(p).read_text(encoding='utf-8'))
patched=0
for rp in roots:
 for fp in rp.glob("*.json"):
  try:
   data=load(fp); name=str(data.get('hunt_name','')).lower()
   is_target=False
   if 'antlerless' in name and ('deer' in name or 'elk' in name): is_target=True
   if 'doe' in name and 'pronghorn' in name: is_target=True
   if 'turkey' in name: is_target=True
   if not is_target: continue
   rows=data.get('research_summary_rows',[])
   if not rows: continue
   point_rows=[]; total_rows=[]
   for r in rows:
    is_total=r.get('is_hunt_total_row') or str(r.get('point_level','')).upper() in ('TOTAL','')
    if is_total or r.get('point_level') in (None,''): total_rows.append(r)
    else: point_rows.append(r)
   if not point_rows: continue
   correct_total=0
   for r in point_rows:
    try: correct_total+=int(r.get('regular_permits') or r.get('total_permits') or r.get('permits') or 0)
    except: pass
   if correct_total==0:
    try: correct_total=int(data.get('permits_total',0))
    except: correct_total=0
   data['permits_total']=correct_total
   data['quota_source_status']='PREFERENCE_FIXED_NO_DOUBLE_COUNT'
   data['data_quality_flags']='PREFERENCE_FIXED|NO_DOUBLE_COUNT|ANTLERLESS_CORRECTED'
   data['scoring_notes']=f'Fixed double-count: point sum={correct_total}, hunt_total excluded. {data.get("scoring_notes","")}'
   for r in total_rows:
    r['algorithm_status']='HUNT_TOTAL_ROW_EXCLUDED_FROM_QUOTA_SUM'
    r['is_hunt_total_row']=True
   fp.write_text(json.dumps(data, indent=2), encoding='utf-8')
   patched+=1
   print(f"Patched {fp.name}: total={correct_total}")
  except Exception as e: print(f"Failed {fp}: {e}")
print(f"\nDone! Patched {patched} live (expected ~87)")
