# Hunt Builder Live Boundary Runtime Verification

Generated: `2026-06-05T08:24:59.547888+00:00`
Status: `PASS_WITH_NOTE`

## Summary
- Live site: `https://huntbuilder.uoga.org`
- Boundary index records: `1471`
- Startup lite boundary features: `683`
- Selected hunts passed: `7`
- Selected hunts failed: `0`

## Selected Hunt Checks
| Hunt code | Boundary ID | Index | Startup layer | Direct GeoJSON | Features | Boundary ID match | Result | Notes |
| --- | ---: | --- | --- | --- | ---: | --- | --- | --- |
| `DA1051` | `955` | `True` | `False` | `200` | `1` | `True` | `PASS_WITH_NOTE` | Direct per-hunt GeoJSON returns 200 with matching boundary ID and geometry; not present in startup lite layer because this is a tiny inter-city boundary. |
| `EA1295` | `224` | `True` | `True` | `200` | `1` | `True` | `PASS` | Boundary index, startup layer, and direct GeoJSON all verified. |
| `EA1299` | `845` | `True` | `True` | `200` | `1` | `True` | `PASS` | Boundary index, startup layer, and direct GeoJSON all verified. |
| `EA1300` | `845` | `True` | `True` | `200` | `1` | `True` | `PASS` | Boundary index, startup layer, and direct GeoJSON all verified. |
| `DB1208` | `874` | `True` | `True` | `200` | `1` | `True` | `PASS` | Map boundary passes; KMZ download path did not return 200. |
| `EA1261` | `874` | `True` | `True` | `200` | `1` | `True` | `PASS` | Map boundary passes; KMZ download path did not return 200. |
| `EB3504` | `874` | `True` | `True` | `200` | `1` | `True` | `PASS` | Map boundary passes; KMZ download path did not return 200. |

## Runtime URL Checks
| Label | Method | Status | OK | Content length | URL |
| --- | --- | ---: | --- | ---: | --- |
| `live_home` | `GET` | `200` | `True` | `28107` | `https://huntbuilder.uoga.org/` |
| `live_config` | `GET` | `200` | `True` | `24804` | `https://huntbuilder.uoga.org/config.js` |
| `live_app_js` | `HEAD` | `200` | `True` | `258790` | `https://huntbuilder.uoga.org/app.js` |
| `live_boundary_lite` | `GET` | `200` | `True` | `4281467` | `https://huntbuilder.uoga.org/data/hunt-boundaries-lite.geojson` |
| `live_boundary_full_local` | `HEAD` | `200` | `True` | `4281467` | `https://huntbuilder.uoga.org/data/hunt_boundaries.geojson` |
| `r2_display_boundary_index` | `GET` | `200` | `True` | `917330` | `https://json.uoga.workers.dev/processed_data/display-boundary-index-2026.json` |
| `r2_composite_boundary_fallback` | `HEAD` | `200` | `True` | `87146863` | `https://json.uoga.workers.dev/processed_data/statewide_composite_boundaries_2026.geojson` |

## Follow-up Interpretation

DA1051 is a very small inter-city hunt. The direct R2 per-hunt GeoJSON is valid and the hunt-code search path maps it, but the smaller startup lite GeoJSON does not contain boundary ID `955`. This is not treated as a selected-hunt boundary failure because direct per-hunt rendering succeeds.
