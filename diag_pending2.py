import csv, pathlib
path = pathlib.Path("processed_data/bear_predictions_2026.csv")
rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
from collections import Counter
c = Counter(r.get("algorithm_status") for r in rows)
print(c)
# reasons
from collections import defaultdict
reasons = defaultdict(int)
for r in rows:
    if r.get("algorithm_status")!="MODELED_BONUS":
        reasons[r.get("data_quality_flags","")[:120]]+=1
for k,v in list(reasons.items())[:20]:
    print(v, k)

# Show one pending LE row detail
for r in rows:
    if r.get("bear_draw_subtype")=="LIMITED_ENTRY_BEAR_HUNT" and r.get("algorithm_status")!="MODELED_BONUS":
        print(r.get("hunt_code"), r.get("algorithm_status"), r.get("data_quality_flags"), r.get("public_permits_2026"), r.get("history_hunt_code"), r.get("crosswalk_status"))
        break
