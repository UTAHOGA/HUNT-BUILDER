import pathlib, sys
sys.path.insert(0, ".")
from engine.utah_draw_predictive import bear
import json, pathlib
# list LE codes bear thinks are pending
pending = [c for c in bear.BEAR_LE_CODES if bear.classify(c) != bear.ALGORITHM_STATUS_MODELED_BONUS]
print("PENDING LE:", pending[:50])
print("Total pending LE:", len(pending))
# show split codes
splits = ["BR7021","BR7022","BR7126","BR7127","BR7238","BR7239","BR7326"]
for code in splits:
    print(code, bear.classify(code))
