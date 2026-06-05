# Harvest Draw Year Alignment Audit

This read-only audit tests whether harvest permit rows line up better with same-year draw results or prior-year draw results.

## Verdict

`USE_SAME_YEAR_REPORTED_HUNT_YEAR_AS_ACTUAL_HUNT_YEAR`

## Permit Match Counts

- `same_year`: `769`
- `prior_draw_year`: `376`
- `next_draw_year`: `695`

## Alignment Status Counts

### `same_year`
- `DRAW_BLANK_HARVEST_AVAILABLE`: `1308`
- `NO_VALUES`: `16`
- `PERMIT_CONFLICT`: `3058`
- `PERMIT_MATCH`: `769`

### `prior_draw_year`
- `DRAW_BLANK_HARVEST_AVAILABLE`: `2242`
- `NO_VALUES`: `16`
- `PERMIT_CONFLICT`: `2517`
- `PERMIT_MATCH`: `376`

### `next_draw_year`
- `DRAW_BLANK_HARVEST_AVAILABLE`: `1844`
- `NO_VALUES`: `16`
- `PERMIT_CONFLICT`: `2596`
- `PERMIT_MATCH`: `695`

## Interpretation

If prior_draw_year beats same_year, harvest reported_hunt_year is likely acting like publication/report year. If same_year beats prior_draw_year, harvest reported_hunt_year is likely actual hunt season year.

This audit only tests year alignment. It does not decide whether Expo, Conservation, CWMU, LOA or Sportsman overlays explain the remaining field-permit gap.
