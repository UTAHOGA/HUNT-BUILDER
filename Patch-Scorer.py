
raise SystemExit("DISABLED_UNREVIEWED_REPAIR: Do not rewrite scoring contracts with string replacement. See docs/CORRECTIVE_RELEASE_20260921.md.")

import pathlib
p=pathlib.Path('tools/prediction_accuracy_backtest/score_full_engine_draw_line_aware.py')
t=p.read_text(encoding='utf-8')
t=t.replace(
    'PREDICTION_PROBABILITY_FIELDS = (\n    "p_draw_mean",\n    "p_draw",',
    'PREDICTION_PROBABILITY_FIELDS = (\n    "certified_p_draw",\n    "p_draw_mean",\n    "p_draw",'
)
t=t.replace(
    'for field in ("p_draw", "p_preference_draw", "p_sportsman_draw", "p_bonus_pool", "p_random_pool", "p_availability"):',
    'for field in ("certified_p_draw", "p_draw", "p_preference_draw", "p_sportsman_draw", "p_bonus_pool", "p_random_pool", "p_availability"):'
)
t=t.replace(
    'candidate_fields = [metric, "p_draw", "actual_probability"',
    'candidate_fields = [metric, "certified_p_draw", "p_draw", "actual_probability"'
)
t=t.replace('"certified_p_draw", "certified_p_draw",', '"certified_p_draw",')
p.write_text(t, encoding='utf-8')
print("Patched 3 locations - certified_p_draw now supported")
