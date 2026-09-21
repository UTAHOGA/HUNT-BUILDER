import pathlib
p=pathlib.Path('[STRIPPED 79 bytes].py')
txt=p.read_text(encoding='utf-8')
# backup
p.with_suffix('.py.orig').write_text(txt,encoding='utf-8')
# replace draw_year -> actual_draw_year (your truth file uses actual_draw_year)
txt=txt.replace('draw_year','actual_draw_year')
p.write_text(txt,encoding='utf-8')
print('patched builder: draw_year -> actual_draw_year')
