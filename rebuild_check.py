import pathlib
from engine.utah_draw_predictive.bear import build_bear_reports
# Build to temp
out = build_bear_reports(write=False)  # or however builder returns rows
print(f"Fresh BR rows: {len([r for r in out if 'BR' in r.get('hunt_code','')])}")
for r in out:
    if 'BR' in r.get('hunt_code',''):
        print(r.get('hunt_code'), r.get('residency'), r.get('program'), r.get('species'), r.get('hunt_name'))
