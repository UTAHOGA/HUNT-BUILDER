# Conservation Synthetic Display Code Policy

## Locked Rule

Sportsman permits and conservation permits are separate permit classes.

The current numbered Sportsman permit hunt codes are:

- `BI1000`: Sportsman Bison
- `BR1000`: Sportsman Black Bear
- `DB0007`: Sportsman Deer
- `DS1000`: Sportsman Desert Bighorn Sheep
- `EB1000`: Sportsman Elk
- `GO1000`: Sportsman Mountain Goat
- `MB1000`: Sportsman Moose
- `PB1000`: Sportsman Pronghorn
- `RS0001`: Sportsman Rocky Mtn Bighorn Sheep
- `TK0001`: Sportsman Bearded Turkey

Conservation permits must not be stored, rendered, or modeled as Sportsman permits merely because a Sportsman/statewide code was useful for map geometry.

## Synthetic Conservation Codes

When a conservation permit row needs a display/map identity and no official DWR conservation hunt code is available, use these UOGA synthetic display codes:

- `CBI1000`: Conservation Bison
- `CBB1000`: Conservation Black Bear
- `CD1000`: Conservation Deer
- `CDS1000`: Conservation Desert Bighorn Sheep
- `CE1000`: Conservation Elk
- `CMG1000`: Conservation Mountain Goat
- `CM1000`: Conservation Moose
- `CP1000`: Conservation Pronghorn
- `CRS1000`: Conservation Rocky Mountain Bighorn Sheep
- `CTK1000`: Conservation Turkey

## Required Field Semantics

- `display_hunt_code`: use the synthetic conservation code where needed.
- `official_hunt_code`: blank unless DWR assigns an official conservation hunt code.
- `geometry_source_hunt_code`: the existing hunt code used only to borrow map geometry.
- `permit_class`: `CONSERVATION`.
- `hunt_code_authority`: `UOGA_SYNTHETIC_DISPLAY_CODE`.
- `mapping_note`: state that the row is a synthetic conservation display code and not an official DWR hunt code.

## Guardrails

- Do not overwrite `DATABASE.csv` sportsman hunt-code rows with conservation permit totals.
- Do not treat synthetic conservation display codes as official DWR hunt codes.
- Do not use synthetic conservation display codes as draw-results truth.
- Keep conservation counts sourced from the conservation permit table.
- Keep Sportsman counts sourced from Sportsman draw/permit evidence.
