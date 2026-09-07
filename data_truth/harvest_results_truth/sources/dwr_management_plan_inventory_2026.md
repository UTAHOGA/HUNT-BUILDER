# Utah DWR Management Plan and Program Authority Inventory

Retrieved: `2026-09-07T05:07:55.666440+00:00`

These are the current plans linked by the Utah DWR publications, big-game, and species plan pages at retrieval time for species represented in Hunt Research. Statewide plans set strategy and management frameworks; unit plans provide local population, habitat, composition, and quality objectives where DWR publishes them. They are context for interpreting harvest and Hunt Planner metrics, not observed harvest rows, permit truth, or draw-probability truth.

## Coverage

| Species family | Statewide plans | Unit plans |
|---|---:|---:|
| Bighorn Sheep | 1 | 19 |
| Bison | 0 | 2 |
| Black Bear | 1 | 0 |
| Elk | 1 | 26 |
| Moose | 1 | 0 |
| Mountain Goat | 1 | 6 |
| Mule Deer | 1 | 29 |
| Pronghorn | 1 | 0 |
| Wild Turkey | 1 | 0 |

Total official plan PDFs: **90**.

## Added statewide objective measures

- **Black bear (2023-2035):** the population-management system uses three-year strategy bands for the percentage of sport-harvest bears that are adult males age 5, the female share of sport harvest, and DNA-study population growth rate. A current unit strategy is required before a strategy band can be presented as that unit's governing target.
- **Wild turkey (2023-2029):** quantified objectives include enhancing 100,000 acres of habitat statewide by 2029 and increasing statewide hunter participation by 10% by 2029. These are statewide program objectives, not hunt-unit harvest-quality objectives.

## Cougar program authority

- Authority status: `CURRENT_OPEN_SEASON_PROGRAM_AUTHORITY_NO_CURRENT_MANAGEMENT_PLAN_LISTED`.
- Current program source: https://wildlife.utah.gov/cougar/background
- Current regulatory model: year-round harvest with a hunting or combination license, no bag limit, and no additional cougar permit required; DWR identifies the governing change as beginning in 2023.
- Publications page lists a current cougar management-plan PDF: `false`.
- Historical plan reference: https://wildlife.utah.gov/pdf/cougars/cmgtplan.pdf (2015-2025; expired by its own term and not current objective authority).
- Historical-plan retrieval status: `official_urls_unavailable_at_retrieval_time`; no local copy was retained because both official URLs were unavailable. The original source URL is https://wildlife.utah.gov/pdf/cougars/cmgtplan.pdf.
- Research display rule: label this as an open-season program rather than a current management plan, use the current program page for qualitative management context, and leave the quantified objective blank until DWR publishes or confirms a current governing target.

## Data-use boundary

- Appropriate: management objectives, policy periods, herd/unit context, quality targets, habitat goals, and interpretation of observed harvest trends.
- Not appropriate: substituting an objective for an observed annual harvest value, using a plan value as a permit quota, or deriving `p_draw` directly from a plan.
- Current DWR listing status means only that the DWR linked the PDF as current/latest when this inventory was retrieved. Dates printed inside each PDF remain the document-level authority.
- Three current documents require the Wildlife Board evidence chain because DWR's main big-game/publications page still points to older copies: the 2025-reviewed mountain goat plan, the 2025-reviewed bighorn sheep plan, and the December 2025 Book Cliffs bison plan.

## How this connects to the existing data

| Source layer | What it supplies | Research use |
|---|---|---|
| Annual harvest reports/dashboard | Observed permits, hunters afield, harvest, success, effort, satisfaction and age where DWR reports it | Historical performance and quality evidence |
| Hunt Planner management statistics | Current population objective/estimate, composition objective/current value, age objective/current three-year age where exposed | Current unit context |
| Statewide and unit management plans | Policy period, goals, objective definitions, management direction and unit objective authority | Explanation and validation context; never an observed result |

The retained Hunt Planner unit snapshot has **227** deduplicated management-unit rows. Population objective/current estimate is populated for most species; age objective/current three-year age is concentrated in elk, moose and pronghorn. Deer instead exposes buck-to-doe objective/current three-year composition. The exact species counts are retained in the JSON inventory.

## Official index pages

- Big game: https://wildlife.utah.gov/biggame
- Publications: https://wildlife.utah.gov/publications
- Cougar program background: https://wildlife.utah.gov/cougar/background
- Deer unit plans: https://wildlife.utah.gov/deer/plans
- Elk unit plans: https://wildlife.utah.gov/elk/plans
- Mountain goat unit plans: https://wildlife.utah.gov/goat/plans
- Bighorn sheep unit plans: https://wildlife.utah.gov/sheep/plans

The JSON companion contains every URL, unit label, checksum, page count, and retained RAW path.
