import sys
sys.path.insert(0, ".")
import engine.utah_draw_predictive.bear as b
print("LIMITED_ENTRY_BEAR_HUNT:", len(getattr(b,'LIMITED_ENTRY_BEAR_HUNT',[])), getattr(b,'LIMITED_ENTRY_BEAR_HUNT',[])[:10])
print("RESTRICTED_BEAR_PURSUIT:", getattr(b,'RESTRICTED_BEAR_PURSUIT',[])[:20])
print("UNLIMITED_PURSUIT_PERMIT:", getattr(b,'UNLIMITED_PURSUIT_PERMIT',[]) )
print("official_bear_draw_odds_hunt_codes():", len(b.official_bear_draw_odds_hunt_codes()), list(b.official_bear_draw_odds_hunt_codes())[:10])
print("official_bear_pursuit_hunt_codes():", len(b.official_bear_pursuit_hunt_codes()), list(b.official_bear_pursuit_hunt_codes()))
# try classify
for code in ["BR7021","BR7022","BR7126","BR7127","BR7238","BR7239","BR7326","BR1007","BR1018","BR7000"]:
    try:
        print(code, b.classify_bear_subtype(code), b.classify_bear_subtype_before_source_correction(code) if hasattr(b,'classify_bear_subtype_before_source_correction') else "")
    except Exception as e:
        print(code, "ERR", e)
