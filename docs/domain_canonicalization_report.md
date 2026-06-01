# Domain Canonicalization Report

Generated: 2026-06-01 (America/Denver)

## Canonical Domain Policy
- Canonical production domain: `https://huntbuilder.uoga.org`
- Non-canonical domain: `https://hunt-builder.uoga.org`
- Operational rule:
  - Non-canonical host may exist only as a redirect source to canonical.
  - It must not be treated as a parallel active production surface.

## Audit Scope
- Searched repository for both domains:
  - `huntbuilder.uoga.org`
  - `hunt-builder.uoga.org`
- Classified references into:
  - `ACTIVE_RUNTIME`
  - `ACTIVE_DOCS`
  - `LEGACY_DOCS`
  - `CONFIG_ONLY`
  - `SAFE_TO_REMOVE` (none required in this pass)

Detailed row-by-row output is in:
- `processed_data/audits/domain_reference_audit.csv`

## Changes Applied
### Normalized to canonical domain
1. `AGENTS.MD`
   - Removed explicit alternate-domain production language.
   - Retained canonical-only policy plus redirect-only guidance for non-canonical hosts.
2. `hunt-master-canonical-2026.json`
   - `business_profile.website_domain` changed to `huntbuilder.uoga.org`.
3. `schemas/hunt-master-canonical-2026.schema (2).json`
   - `$id` host changed to canonical domain.
4. `scripts/audit-active-data-feeds.js`
   - Sandbox hostname changed to canonical domain.
5. `scripts/audit-site-performance-library-outfitters.js`
   - Sandbox hostname changed to canonical domain.
6. `processed_data/final_live_push_verification_report.json`
   - `production_live_url` changed to canonical domain.

### Intentionally retained non-canonical references
1. `vercel.json`
   - Keeps host-match redirect rule from non-canonical host to canonical host.
   - This is redirect policy only; it does not represent active parallel runtime.
2. `embed-mode.js`
   - Keeps non-canonical host detection to force redirect to canonical host.
   - Runtime behavior enforces canonical domain.
3. `processed_data/audits/promote_now_live_alignment.csv`
   - Historical audit artifact retained unchanged (legacy evidence).

## Validation Results
1. Active runtime/config now treats only `huntbuilder.uoga.org` as canonical.
2. Remaining `hunt-builder.uoga.org` references are redirect-only (`vercel.json`, `embed-mode.js`) plus one legacy audit artifact.
3. No active docs/config/runtime reference treats non-canonical host as a parallel production domain.

## Residual Legacy References
- `processed_data/audits/promote_now_live_alignment.csv` keeps historical text for prior audit chronology.
- This does not influence runtime behavior.

## Recommended Follow-Up
- If you want a strict zero-string policy (no raw `hunt-builder.uoga.org` text anywhere), remove or archive legacy audit artifacts and keep redirect handling in a dedicated config file outside archived reports.
