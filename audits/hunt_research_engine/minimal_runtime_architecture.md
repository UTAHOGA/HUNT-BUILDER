# Hunt Research Minimal Runtime Architecture

Generated: 2026-06-05T10:50:25Z

## Purpose

The Hunt Research page should not load the full 2026 research universe before a hunter selects a hunt. The production path is now:

1. Load the compact summary feed for page-level search and summary cards.
2. Load the split hunt-code index for the 2026 hunt universe.
3. Load compact selected-hunt detail from R2 when a hunt is opened.
4. Keep the full 306 MB canonical JSON only as a fallback.

## Minimal Feeder Set

| Role | Runtime file | Size | Status |
| --- | --- | ---: | --- |
| Initial summary | `processed_data/hunt_research_2026_summary.json` | 12,253,957 bytes | R2 verified 200 |
| Hunt-code index | `processed_data/hunt_research_2026_split/hunt_research_2026.index.json` | 998,277 bytes | R2 verified 200 |
| Compact selected-hunt details | `processed_data/hunt_research_2026_split/hunt_research_2026.details.json` | 33,963,444 bytes | R2 verified 200 |
| Full canonical fallback | `processed_data/hunt_research_2026.json` | 305,924,170 bytes | R2 verified 200 |
| Full ladder rollback only | `processed_data/hunt_research_2026_ladder.json` | 305,924,170 bytes | R2 verified 200 |

## Bundle Integrity

The compact details bundle was built from the existing split index and split detail files.

| Check | Result |
| --- | ---: |
| Indexed current hunt codes | 1,471 |
| Bundled hunt details | 1,471 |
| Missing detail files | 0 |
| Duplicate hunt codes in index | 0 |

## Runtime Behavior

The page now indexes only summary rows and split index rows during initial load. When a hunt code is selected, it tries to load the per-hunt detail path first. If individual detail files are not present on R2, the page loads the compact details bundle once and extracts the selected hunt from that bundle.

For bonus-point hunts, the selected-hunt detail is translated into the existing ladder row shape using the nested `bonus_draw` and `projected_bonus_draw` resident/nonresident arrays. The renderer is unchanged.

## Draw Model Display Contract

For `BONUS_POINT_SPLIT_DRAW` families, including Limited Entry, Premium Limited Entry, and Once-In-A-Lifetime:

| Concept | Website meaning |
| --- | --- |
| 2025 Draw Results | What actually happened in the prior reported draw year at each point row. |
| 2026 Max Point Draw | The high-point side of the split draw. Rows above the modeled draw line render `~1 in 1 or 99%`. |
| 2026 Random Draw | The weighted random side of the split draw. Rows below the draw line show modeled random odds. |
| Draw line | The modeled point level where max-point permits are expected to run out. |
| Random pool | Point rows below the draw line that still have a chance through weighted random selection. |

Permit split rule used for display explanation:

```text
if permits == 1:
  random_permits = 1
  max_point_permits = 0
else:
  permit 1 -> random
  permits 2 and 3 -> max point
  permit 4 -> random
  permit 5 -> max point
  continue alternating after that
```

## Weak Spots Still To Watch

- Individual per-hunt detail objects are not all verified as separate R2 URLs yet; the compact bundle is the current safe R2 path.
- Preference-point rows still need the same selected-hunt translation depth as bonus rows if the page must avoid loading family-level preference fallbacks forever.
- Full legacy CSV feeders remain available for rollback but should not be used as the normal production path.
- Harvest quality feeds explain hunter fit and sleeper potential; they should not directly change draw probability.
