# Source mapping and hunt crosswalk review

This is a local source review, not a canonical rewrite or engine certification.
The owning implementation is
`engine/utah/quality/build_source_mapping_and_hunt_crosswalk.py`.

## Requested current-code exports

`engine/utah/quality/audit_database_vs_canonical.py` produced:

- `processed_data/current_but_uncanonicalized_171.json`: the 171 measured
  Planner-2026 codes missing from the named current canonical, not retired.
- `processed_data/canonical_without_confirmation_33.json`: the 33 original
  matrix-unconfirmed canonical codes, with the separately retained PB5329
  direct confirmation. The remaining review population is 32.
- `processed_data/hunt_crosswalk_with_evidence.json`: current catalog union,
  membership flags, every indexed PDF code/page/hash occurrence, and 415
  DATABASE-only unresolved-lineage codes. `numeric_match` remains false because
  presence in this code-level crosswalk is not a row-level numeric assertion.

The numbers in these requested filenames identify this snapshot; they are not
forced totals. Tests use different-sized fixtures and verify dynamic counts.
DATABASE supplies no current code authority or historical probability truth.
The separate set-difference diagnostic does not delete or mark any code retired.

See `CURRENT_CANONICAL_PLANNER_REVIEW_20260921.md` for the completed fresh
Planner comparison, including species scope and retained response locations.

## Full source mapping

The initial requested command completed and retained its outputs in
`processed_data/`. The evidence-enriched follow-up is separately retained under
`audit_output_phase1_candidate/source_mapping_crosswalk_20260921_v3/`.

The v3 report supersedes v1/v2 endpoint comparisons: a missing adult/youth
designation now remains `ENDPOINT_SOURCE_DIMENSION_UNRESOLVED`, even if only one
raw endpoint candidate exists. In particular, v1/v2's 13 apparent Turkey value
disagreements involved unspecified canonical youth dimensions; they are not
established numeric transcription defects. No canonical values were changed.

Outputs include:

- `source_mapping_2017_2026.json`: every PDF path, measured hash, real page count,
  all detected codes and pages, extraction errors, and current canonical overlap.
- `hunt_crosswalk_2017_2026.json`: current canonical membership, all PDF providers
  without a five-document cap, historical canonical years, and DATABASE permit
  reference fields only.
- `historical_canonical_source_links_2017_2026.json`: physical-year/source/hunt
  groups with original labels, parent files, pages, lane/youth metadata, prior
  hash-verified mappings, and separately labeled numeric-review status.
- `endpoint_row_source_review.csv`: each checked 2026 endpoint row's exact
  hunt/residency/point/youth identity, parent path, compared-field count and
  unresolved/error reason.
- `source_mapping_normalized_differences.csv`: original differences retained
  with additional review classifications; original audit remains untouched.
- `existing_crosswalk_guidebook_review.json`: earlier crosswalk rows and
  guidebook code/page evidence, without silently approving their relationships.
- `source_mapping_closure_review.json`: computed counts, source hashes,
  unresolved scopes, input-change checks and final gate result.

All 675 inspected PDF paths (458 distinct hashes) were readable. The audit spans
all ten physical canonical years, 338,574 rows, 1,544 historical codes and 15,266
year/source/hunt groups. Historical-only records remain separate from the current
master; none are inserted into the current canonical.

The 705 ratio-whitespace differences normalize without changing numeric values.
The 1,243 extra 2017 hunt totals are classified as aggregate totals, not missing
point rungs, and must not be added to rung awards. The 14 documented 2020 printed
carryover differences remain preserved. No hardcoded source counts or synthetic
fallback totals are used.

## Earlier crosswalks and regulations

The follow-up retains 6,701 records from five existing crosswalk files, including
Bear, the six no-exact-history additions, current-to-historical references,
adjacent-year transitions and the LE/EB candidate crosswalk. The two existing
canonical parent-source mapping files are reused as leads with fresh hash checks.

Seventy-one guidebook PDFs are indexed; all six cited first-listing pages in the
additions crosswalk contain the cited code. The 2026 Bear guidebook, physical
pages 73-75, explicitly labels Dolores Triangle BR7021/BR7126/BR7238 as new.
Page 73 was also visually reviewed. Field regulations and application hunt
tables have different purposes: lack of a hunt-code hit in field regulations
does not prove discontinuation. A named hunt and code in an application table
prove listing, not a predecessor's applicant-demand equivalence.

Earlier labels such as `PROMOTED_PREFIX_SWAP_CANDIDATE` are retained as historical
claims, not converted into newly approved public-draw identity mappings.

## What this does not close

The gate remains BLOCKED while exact source dimensions, historical total/Sportsman
layouts, and non-draw reference scope reviews remain unresolved. Code/page
presence does not close these numeric checks. Group-level numeric statuses are
conservative: one unresolved row keeps its whole source/hunt group unresolved,
so their row counts are not directly comparable to the earlier individual-cell
audit's 309,644 matched rows.

No canonical, long truth, DATABASE, resolver, forecast, certification registry or
website artifact was modified. Original reports and both intermediate runs remain
retained. The separate project-memory DATABASE hash/stale-build failures remain
unwaived; no authority hash was changed merely to pass validation.
