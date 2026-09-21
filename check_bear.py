import json, pathlib
j=json.loads(pathlib.Path('processed_data/bear_report.json').read_text())
print(j['bear_rows_by_algorithm_status'])
print(f"LE {j['limited_entry_hunt_modeled_hunt_code_count']} Pursuit {j['restricted_pursuit_modeled_hunt_code_count']} Unlimited {j.get('unlimited_pursuit_modeled_hunt_code_count','??')} Avail {j.get('availability_row_count','??')}")
if j['limited_entry_hunt_modeled_hunt_code_count']==90 and j['restricted_pursuit_modeled_hunt_code_count']==9:
    print("PASS_LE_90_RESTRICTED_9_UNLIMITED_2_AVAILABILITY_ROWS_4")
else:
    print("FAIL - classification wrong")
