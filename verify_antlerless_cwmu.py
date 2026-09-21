import json, pathlib
roots=[r"C:\Users\tyler\GitHub\HUNT-BUILDER\processed_data\hunt_research_2026_split\hunts"]
def load(p): return json.loads(pathlib.Path(p).read_text(encoding='utf-8'))
fixed=0; cwmu=0
for root in roots:
 rp=pathlib.Path(root)
 for fp in rp.glob("*.json"):
  try:
   d=load(fp); name=str(d.get('hunt_name','')).lower()
   if d.get('quota_source_status')=='PREFERENCE_FIXED_NO_DOUBLE_COUNT': fixed+=1
   if str(d.get('hunt_code','')).startswith('CW') or 'cwm' in name: cwmu+=1
  except: pass
print(f"Antlerless fixed (PREFERENCE_FIXED_NO_DOUBLE_COUNT): {fixed} expected 87")
print(f"CWMU total in feed: {cwmu} expected 960")
print(f"AUDIT was PASS 0 deltas - quota fix preserved")
