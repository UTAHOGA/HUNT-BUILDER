# Site Map And Runtime Audit

Generated: 2026-06-01 (America/Denver)  
Audit scope: `https://huntbuilder.uoga.org` live deployment + repo runtime contract

## Deployment Contract
- Host: `huntbuilder.uoga.org`
- Edge/platform: **Vercel** (`Server: Vercel`, `X-Vercel-Id` confirmed)
- Build contract:
  - `vercel.json` -> `buildCommand: npm run build`
  - `outputDirectory: pages-dist`
  - Rewrite: `/hard-copy/:path*` -> `/public/hard-copy/:path*`
- Effective serving model:
  - Live assets/routes are served from the built `pages-dist` artifact.
  - Source-of-build comes from root files + copied `data/`, `processed_data/`, `assets/`, `public/hard-copy` via `scripts/build-pages-dist.js`.

## Parent Linkage
- `https://uoga.org` homepage HTML contains a link reference to `huntbuilder.uoga.org`.

## Primary vs Alternate Domain Parity
- Primary production domain: `https://huntbuilder.uoga.org/`
- Secondary/alternate domain under audit: `https://hunt-builder.uoga.org/`
- DNS/runtime result:
  - `huntbuilder.uoga.org` resolves and serves live pages.
  - `hunt-builder.uoga.org` currently returns **NXDOMAIN** (does not resolve).
- Parity implication:
  - Redirect parity: not testable (alternate domain does not resolve).
  - Page content parity: not testable.
  - Runtime asset/JSON parity: not testable.
  - Hard-copy/Builder parity: not testable.
  - Stale deployment/stale branch indicator: alternate domain appears unconfigured rather than stale.

## Reachable Live Routes
Routes discovered from root HTML inventory and live 200 checks:
- `/` (Builder)
- `/index.html` (Builder duplicate)
- `/builder.html` (Builder duplicate)
- `/research.html` (Hunt Research primary)
- `/hunt-research.html` (Hunt Research duplicate route)
- `/verify.html` (Outfitter directory primary)
- `/vetting.html` (Outfitter directory duplicate route)
- `/hard-copy.html` (Public document library)
- `/hard-data.html` (hard-data manifest view)
- `/coverage.html` (coverage diagnostics page)
- `/verify.htmlm` (legacy alias; returns 200 in curl, but browser treats as download/ERR in Playwright navigation)

## Active Navigation Experience
Top nav observed on live primary pages:
- `HOME` -> `./` (Builder)
- `HUNT RESEARCH` -> `./research.html`
- `OUTFITTERS` -> `./verify.html`
- `HUNTING BIBLE` -> `./hard-copy.html`

Primary production experience routes:
- `/` (Builder)
- `/research.html`
- `/verify.html`
- `/hard-copy.html`

Other reachable routes are secondary/legacy or diagnostics.

## Page-By-Page Runtime Audit
## Builder (`/`, `/index.html`, `/builder.html`)
- Purpose: hunt discovery/filter/map, selected hunt actions, outfitter matching.
- Linked from nav/buttons: **Yes** (root route is nav home).
- Live status: **200**
- Load health:
  - No 404 network errors in live page sweep.
  - Console error persists:
    - `processed_data/composite_hunt_unit_mapping_2026.geojson` parses as Git LFS pointer text (`Unexpected token 'v' ... "version ht"`).
  - App still loads due fallback source order.
- Required frontend assets:
  - `config.js`, `data.js`, `app.js`, `boundary-resolver.js`, `ui.js`, `style.css`, `google-basemap.js`, `header-layout.js`, `ownership-dock.js`
  - logos under `assets/logos/*`
- Runtime feeds (200 in live sweep):
  - `./data/hunt-master-canonical-2026-foundation.json`
  - `./data/conservation-permit-areas.json`
  - `./data/conservation-permit-hunt-table-2025-27.json`
  - `./processed_data/display-boundary-index-2026.json`
  - `./processed_data/statewide_composite_boundaries_2026_FINAL_LOCKED.geojson`
  - `./data/hunt_boundaries.geojson`
  - `./data/statewide-composite-members-2026-lite.geojson`
  - `./data/outfitters-public.json`
  - `./data/black_bear_hunt_table_official.json`
- Runtime feeds with non-fatal data-quality issue:
  - `./processed_data/composite_hunt_unit_mapping_2026.geojson` (200 response, invalid JSON payload due LFS pointer)
- Served path basis: root routes from `pages-dist`; assets/data copied into `pages-dist` by build script.

## Hunt Research (`/research.html`)
- Purpose: point ladder + draw outlook by hunt code/residency/points/draw pool.
- Linked from nav/buttons: **Yes**
- Live status: **200**
- Load health:
  - No 404s in live sweep.
  - Selected hunt context query tested and resolved correctly.
- Required frontend assets:
  - `hunt-research.js`, `assets/js/research-outlook-dashboard.js`, `config.js`, `ui.js`, `header-layout.js`, `style.css`
- Active runtime data source (observed live with query parameters):
  - **Cloudflare Worker domain** `https://json.uoga.workers.dev`:
    - `/processed_data/draw_reality_engine_v2.csv`
    - `/processed_data/point_ladder_view.csv`
    - `/processed_data/hunt_master_enriched.csv`
    - `/processed_data/hunt_unit_reference_linked.csv`
- Notes:
  - Research runtime remains Cloudflare-first for heavy CSV feeds.
  - Site domain itself is Vercel; data is mixed Vercel static + Cloudflare CSV.

## Hunt Research duplicate (`/hunt-research.html`)
- Purpose: duplicate route shell for Research.
- Linked from nav/buttons: **No** (not primary nav target).
- Live status: **200**
- Health: loads cleanly in sweep.
- Status: **Legacy/duplicate route**, still functional.

## Outfitter Directory (`/verify.html`)
- Purpose: public outfitter directory.
- Linked from nav/buttons: **Yes**
- Live status: **200**
- Load health: clean in sweep (no 404s/errors).
- Runtime feed:
  - `./processed_data/public_contracts/outfitters-public.json`
- Served basis: root + `processed_data/public_contracts` copied to `pages-dist`.

## Outfitter duplicate (`/vetting.html`)
- Purpose: duplicate/alternate entry for outfitter view.
- Linked from nav/buttons: **No**
- Live status: **200**
- Runtime feed observed:
  - `./processed_data/public_contracts/outfitters-public.json`
- Status: **Legacy/duplicate route**, functional.

## Hard-copy Library (`/hard-copy.html`)
- Purpose: curated public reference documents.
- Linked from nav/buttons: **Yes**
- Live status: **200**
- Functional status:
  - Folders render (8 folder cards observed).
- Runtime behavior:
  - Primary data works:
    - `/public/hard-copy/data/documents.json` (200)
    - `/hard-copy/data/documents.json` (200 via rewrite)
  - Fallback sources still 404 (non-fatal):
    - `/processed_data/hard_data_exports/library/public_library_allowlist.json`
    - `/public/hard-copy/DISPLAY DATA/data/documents.json`
    - `/hard-copy/documents.json`
- Status: **Functional with fallback noise**.

## Hard-data (`/hard-data.html`)
- Purpose: hard data manifest/library page.
- Linked from nav/buttons: **No**
- Live status: **200**
- Runtime feed:
  - `./processed_data/hard_data_exports/hard_data_manifest.web.json` (200)
- Status: secondary utility route, functional.

## Coverage (`/coverage.html`)
- Purpose: diagnostics/coverage page.
- Linked from nav/buttons: **No**
- Live status: **200**
- Runtime health:
  - 404 on `./processed_data/coverage-matrix.json`
  - Console error thrown by `coverage.js` load function
- Status: **Live but broken** (diagnostic route).

## Legacy alias (`/verify.htmlm`)
- Purpose: historical alias redirect/document.
- Live check:
  - curl returns 200
  - browser navigation reports download-start error
- Status: **Legacy/dead-path candidate** (REVIEW).

## Runtime Source Summary
- Vercel-served static (active):
  - HTML/CSS/JS shell routes and most Builder/verify/hard-copy data assets.
- Cloudflare-served runtime (active):
  - Research heavy CSV sources via `json.uoga.workers.dev`.
- Mixed model currently active:
  - Builder is now local/static-first under Vercel.
  - Research remains Cloudflare-first.

## Key Live Risks
1. Builder consumes a `.geojson` path that currently serves a Git LFS pointer payload (parsing error hidden by fallback).
2. Hard-copy has fallback URL 404 noise (functional but noisy).
3. Coverage route is broken due missing `processed_data/coverage-matrix.json`.
