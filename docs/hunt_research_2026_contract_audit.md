# hunt_research_2026.json Contract Audit

Generated: 2026-06-01 (America/Denver)

## 1. File purpose
- Audited `processed_data/hunt_research_2026.json` as candidate canonical Research page contract feed.
- Compared against current reference/truth surfaces and active Research runtime expectations.

## 2. Schema summary
- Parsed cleanly: yes
- Top-level type: list
- Total rows: 1117
- Distinct fields found: 37
- Runtime-expected fields (JS scan): 63; missing in JSON: 59
- Missing expected field examples: algorithm_status, applicants, average_harvest_age, data_quality_flags, delta_gap, display_2025_draw_results, display_2026_max_point_pool, display_2026_random_draw, display_odds_pct, draw_2026_system_type, draw_outlook, draw_pool, draw_system, draw_system_type, dwr_result_display, eligible_applicants, gap, guaranteed_at_2026, guaranteed_marker, guaranteed_probability, hunt_class, length, management_direction, management_objective_max, management_objective_min

## 3. Coverage summary
- Hunt codes in contract: 1117
- Hunt codes in DATABASE.csv: 1449
- Missing vs DATABASE: 337
- Missing hunt code examples: BI6530, BI6538, BI6539, BR1000, BR1001, BR1007, BR1008, BR1009, BR1010, BR1011, BR1012, BR1013, BR1015, BR1016, BR1017, BR1018, BR7000, BR7001, BR7003, BR7004, BR7005, BR7007, BR7008, BR7009, BR7010
- Extra codes not in DATABASE: 5
- Extra hunt code examples: BI0001, DB1774, EA2042, PB5343, PD1041

## 4. Null/missing summary
- Rows missing >=4 key contract fields (`hunt_code, species, residency, points, p_draw, guaranteed_at_2026, status, permits_2026_total`): 1117 (100.00%).
- Concept completeness:
  - hunt_code: PRESENT (1117/1117, 100.00%) [hunt_code]
  - species: PRESENT (1117/1117, 100.00%) [species]
  - residency: MISSING (0/1117, 0.00%) [no candidate fields found]
  - points: MISSING (0/1117, 0.00%) [no candidate fields found]
  - actual_or_prior_draw_odds: MISSING (0/1117, 0.00%) [no candidate fields found]
  - estimated_draw_odds_model_output: MISSING (0/1117, 0.00%) [no candidate fields found]
  - guaranteed_line_or_draw_line: MISSING (0/1117, 0.00%) [no candidate fields found]
  - point_creep: MISSING (0/1117, 0.00%) [no candidate fields found]
  - recommendation_in_reach_signal: MISSING (0/1117, 0.00%) [no candidate fields found]
  - permit_counts: MISSING (0/1117, 0.00%) [no candidate fields found]
  - harvest_success: MISSING (0/1117, 0.00%) [no candidate fields found]
  - average_harvest_age: MISSING (0/1117, 0.00%) [no candidate fields found]
  - avg_days_hunted: MISSING (0/1117, 0.00%) [no candidate fields found]
  - source_freshness: MISSING (0/1117, 0.00%) [no candidate fields found]
  - model_version_generated_timestamp: MISSING (0/1117, 0.00%) [no candidate fields found]

## 5. Alignment with DATABASE.csv and other reference files
- DATABASE.csv alignment: missing contract coverage for 337 hunt codes.
- point_ladder_view.csv distinct codes: 1449; contract codes missing in ladder: 5.
- draw_reality_engine.csv distinct codes: 1623; contract codes missing in draw engine: 7.
- hunt_master_enriched.csv source used for audit: cloudflare_runtime; distinct codes captured: 1449.
- contract codes missing in master_enriched: 5.

## 6. Alignment with Research page runtime expectations
- Active Research runtime (`research.html` + `hunt-research.js` + `assets/js/research-outlook-dashboard.js`) still loads multiple external feeds:
  - draw_reality_engine(.csv/.v2), point_ladder_view.csv, hunt_master_enriched.csv, hunt_unit_reference_linked.csv, and outlook/management context JSONs.
- `hunt_research_2026.json` is not currently the single-source contract used by page render logic.
- JS-expected fields missing from this JSON: 59 (examples above).

## 7. Blocker list
- Missing critical concept fields: residency, points, estimated_draw_odds_model_output, guaranteed_line_or_draw_line, recommendation_in_reach_signal, permit_counts
- Missing 337 DATABASE hunt codes
- 59 runtime-expected fields absent from contract rows
- No explicit average_harvest_age field family present
- No explicit point_creep field family present

## 8. Exact recommendation
**INCOMPLETE**

## 9. Exact next step required if not COMPLETE
1. Define and freeze a Research Contract v1 schema (required fields + field semantics + source/freshness metadata).
2. Regenerate `hunt_research_2026.json` to full 2026 hunt-code universe coverage from DATABASE truth crosswalk.
3. Add missing contract fields needed by runtime promises (especially point-creep, average-harvest-age, and explicit source/model freshness fields) or map UI expectations to existing stable fields.
4. Refactor Research runtime to consume this JSON as primary contract instead of depending on multiple parallel CSV feeds.
