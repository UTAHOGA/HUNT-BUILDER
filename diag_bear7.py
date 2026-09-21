import pathlib, re
text = pathlib.Path('engine/utah_draw_predictive/bear.py').read_text()
# find where report json counts are built
for m in re.finditer(r'limited_entry_hunt_modeled_hunt_code_count|bear_rows_by_algorithm_status|official_draw_codes|BEAR_HISTORY_CODE_ALIASES', text):
    s = m.start()
    print(text[s-80:s+200].replace('\n',' | '))
    print('---')
