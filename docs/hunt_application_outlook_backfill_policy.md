# Hunt Application Outlook Backfill Policy

## Purpose
Define source-of-truth direction and safe backfill behavior for `hunt_application_outlook.json`.

## Canonical Direction

Canonical files:

- `processed_data/public_contracts/hunt_application_outlook.json`
- `processed_data/research_page/hunt_application_outlook.json`

Derived compatibility file:

- `data/hunt_application_outlook.json`

Rule:

1. `processed_data/public_contracts` and `processed_data/research_page` are canonical.
2. `data/hunt_application_outlook.json` is a derived compatibility mirror only.
3. Never hand-edit `data/hunt_application_outlook.json`.
4. Regenerate/backfill `data/hunt_application_outlook.json` from canonical source when stale.

## Backfill Source Selection Rule

For compatibility runtime copies, use:

- `processed_data/public_contracts/hunt_application_outlook.json`

Reason:

- It matches the 28-field public contract shape used by the existing `data/` compatibility surface.
- `processed_data/research_page/hunt_application_outlook.json` contains additional runtime metadata fields and should remain canonical for research runtime context, not as the compatibility mirror template.

## Validation Requirements

After backfill, confirm:

1. Row counts match canonical.
2. Field-set compatibility remains intact for active consumers of `data/hunt_application_outlook.json`.
3. Hash equality with selected canonical source is achieved.
4. `git diff --check` passes.

## Operational Note

If future runtime consumers need the expanded research schema, promote that change explicitly and version the consumer contract first. Do not silently widen the compatibility mirror schema.
