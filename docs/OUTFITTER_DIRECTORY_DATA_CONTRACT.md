# Outfitter Directory Data Contract

## Authority and scope

`local_data/outfitters/outfitters-master.internal.json` is the local internal
hunting-outfitter directory. Its business identity, contact fields, review
status, and reported USFS/BLM permit areas are promoted from the reconciled
`Outfitters` workbook sheet.

The repository is public, so the full directory and its derivative evidence
files are Git-ignored. `data/outfitter-internal-master-manifest.json` records the
promotion inputs, counts, local artifact paths, and privacy boundary without
publishing the internal rows.

Fishing-only and unclassified businesses are excluded. A business marked for
both fishing and hunting remains in scope because it is a hunting outfitter.

`data/outfitters-public.json` remains the explicit public allowlist. A record in
the local internal master does not become public merely because it exists in the
working checkout.

The versioned `data/outfitters-master.json` and the root canonical outfitter
array are public-repository-safe projections containing only the nine unique
vetted hunting businesses represented by the 11-row public feed. Fishing-only
and unreviewed records are not retained in those tracked projections.

## Review-status mapping

The spreadsheet `REVIEW STATUS` is preserved exactly as `reviewStatus`:

| `reviewStatus` | Meaning |
|---|---|
| `Confirmed` | The reconciled spreadsheet supports the business identity and merged row. |
| `Needs Verification` | The record or one of its supporting values still requires direct verification. |
| `Spreadsheet Only` | The record is present in the spreadsheet but lacks repository corroboration. |

The legacy repository field `verificationStatus` remains independent:

| `verificationStatus` | Meaning |
|---|---|
| `Vetted` | The pre-existing public verification workflow approved the record. |
| `Unreviewed` | The repository verification workflow has not approved the record. |

There is no automatic conversion between the two fields. `Confirmed` does not
rewrite `verificationStatus`, and `Vetted` does not rewrite `reviewStatus`.
Permit confirmation is a third, independent evidence state and does not verify
contact details. Public contact details continue to come only from the explicit
vetted allowlist; a permit-confirmed but unvetted business may be published only
as a name-only coverage profile.

## Source precedence

The reconciled spreadsheet controls business names, owners, phone numbers,
websites, email addresses, locations, business-entity references, and
`reviewStatus`. Legacy repository contacts do not fill or overwrite those
fields. Existing repository enrichment may be preserved only after a unique
business-name or documented alias match.

An authoritative agency permit-holder source may augment the federal service
area without changing spreadsheet contact fields or `reviewStatus`. The source,
date, official permit-holder name, match, and permit scope must remain explicit.

## Federal service-area evidence

`local_data/outfitters/outfitter-federal-service-area-evidence.internal.json`
holds normalized USFS and BLM evidence separately from unit claims. It contains
80 hunting-outfitter records: 79 have spreadsheet-bearing federal areas and one
additional business is present only because of an official Fishlake roster
match. It retains the source, raw spreadsheet text, normalized identifiers,
review status, workbook row, and normalization issues.

`data/source-evidence/manti-la-sal-permitted-hunting-outfitters-2026.json`
records 19 hunting-master matches from the USDA Forest Service's Manti-La Sal
permit-holder list, last updated May 19, 2026. These matches add Manti-La Sal as
confirmed federal permit evidence only. They do not verify contact information.
The two unresolved source names remain unassigned rather than being merged by
guesswork. North Zone maps to the Ferron, Price, and Sanpete districts; South
Zone maps to the Moab and Monticello districts. An all-forest notation maps to
the whole Manti-La Sal forest only after the business identity is unique.

`data/source-evidence/fishlake-permitted-hunting-outfitters-2025.json` records
41 exact or clearly close business-name matches from the user-identified 2025
Fishlake hunting-outfitter roster image. Those businesses receive whole-Fishlake
scope. Chunky Trout has no close hunting-master business and remains unresolved.
Owner or contact values are not used to force a match.

`data/source-evidence/wild-eyez-confirmed-elk-service-area-2026.json` records
Tyler's operator confirmation that Wild Eyez holds outfitting-and-guiding
authorization for the entire Fishlake National Forest, the Manti-La Sal North
Zone, and the Uinta-Wasatch-Cache Spanish Fork Ranger District, and separately
records the six confirmed elk units offered. The service claims do not expand
the federal permit polygons.

The normalized USFS forest identifiers are `ashley`, `dixie`, `fishlake`,
`manti-la-sal`, and `uwc`. Ranger-district labels remain separate from their
parent forest. BLM labels use explicit `blm-*` identifiers. A misplaced or
unrecognized label remains evidence with `NEEDS_VERIFICATION`; it is not forced
into a federal district.

## DWR unit-service eligibility rule

`local_data/outfitters/outfitter-federal-unit-coverage-review.internal.json` is
a measured unit-by-species crosswalk. It uses the same USFS forest, USFS ranger
district, BLM administrative-unit, and BLM surface-management sources configured
on the Hunt Builder entry map, together with the full Utah DWR ArcGIS polygon
snapshot. The browser-light `data/hunt_units.geojson` remains an alias and display
source, not the measurement geometry.

Only federal service-area records whose independent `permitEvidenceStatus` is
`Confirmed` may create unit authorization. Spreadsheet `reviewStatus` controls
contact-record confidence, not permit eligibility: a `Needs Verification` or
`Spreadsheet Only` business matched to an official issued-authorization roster
is eligible for spatial coverage while its contact details remain withheld.
Federal-area spreadsheet entries without official permit confirmation remain
internal leads until repaired or confirmed.

For each confirmed outfitter and DWR unit polygon, the calculation unions the
outfitter's confirmed federal permit areas and measures their intersection. An
overlap of at least 0.1 acre is labeled
`FEDERAL_PERMIT_AREA_INTERSECTS_DWR_UNIT`; it establishes authorization only on
the permitted federal land inside the unit and populates the internal
`serviceArea.unitsServed` and `internal.unitServiceEligibility` fields. The same
species/unit coverage is used for every sex-specific and hunt-specific choice
that shares that DWR species/unit geometry. The tolerance excludes
boundary-touch artifacts. Overlap acres and the percentage of the complete DWR
unit are retained as descriptive fields. The former 75% threshold remains only
as a comparison field and is not an authorization gate.

USFS entries use mapped administrative-forest or ranger-district polygons; when
a district is known, its parent whole-forest polygon is not counted. Manti-La Sal
North Zone is represented by the Sanpete, Ferron, and Price ranger districts.
BLM entries use BLM-managed surface polygons within the recorded BLM
administrative unit so private and state land inside a broad administrative
outline do not count.

`CONFIRMED_OUTFITTER_SERVICE_CLAIM` is a separate, stronger statement that the
operator confirms offering that species in that unit. A geometric intersection
authorizes the applicable species/sex/hunt selections only on the permitted
federal portion; it does not expand authorization to non-federal land in the
unit. Neither status changes the independent spreadsheet or repository contact
review status. Rows without exact DWR geometry remain unclassified.

The current build evaluates 477 eligible unit/species rows: 464 have an exact
DWR boundary match and 13 lack an exact match. It produces 354 authorized
coverage rows and 7,639 outfitter/unit/species associations across 70
permit-confirmed outfitters, including six operator-confirmed Wild Eyez elk
service claims. The legacy 75% comparison would identify only 26 rows across 32
outfitters and does not control authorization.

The public-safe coverage contract publishes all 70 permit-confirmed business
names and their authorized species/unit intersections. It retains 11 existing
vetted contact rows and adds 63 permit-confirmed name-only profiles. The 63
name-only profiles contain no owner, phone, email, website, city, personal
address, or repository-only contact lead. Internal evidence, overlap metrics,
permit documents, and unresolved matches are not exposed.

## Rebuild commands

```powershell
python -m pip install -r scripts/requirements-outfitter-spatial.txt
python scripts/promote_outfitters_working_master.py --workbook <path-to-reviewed-workbook> --expected-sha256 <sha256>
python scripts/build_outfitter_unit_service_eligibility.py --refresh-boundaries --publish-public --hunt-units <full-dwr-arcgis-geojson> --hunt-unit-alias-source data/hunt_units.geojson --hunt-boundary-info processed_data/dwr_huntplanner_hanumber_2026.json
python -m unittest tests.test_outfitter_directory_promotion
```
