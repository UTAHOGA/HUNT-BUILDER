import sys
sys.path.insert(0, ".")
import engine.utah_draw_predictive.bear as b
print(dir(b))
print("\n--- file top ---")
import pathlib
print(pathlib.Path('engine/utah_draw_predictive/bear.py').read_text(encoding='utf-8')[:2000])
