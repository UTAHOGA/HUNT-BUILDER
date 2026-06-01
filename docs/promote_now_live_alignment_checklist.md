# Promote-Now Live Alignment Checklist

Date: 2026-06-01
Primary domain: `https://huntbuilder.uoga.org`

## Scope
Strict minimal list to align **live canonical** behavior with **repo canonical** head.

## REQUIRED_NOW

1. Deploy out-of-sync frontend/runtime payloads from repo head

- Type: `code` + `runtime asset`
- Paths:
  - `embed-mode.js`
  - `config.js`
  - `data.js`
  - `app.js`
  - `hunt-research.js`
  - `assets/js/research-outlook-dashboard.js`
  - `assets/css/hard-copy-public-library.css`
- Why required:
  - Live payloads are byte-different from repo head.
  - Repo canonical behavior (manifest-aware runtime routing, pointer-pruned fallback behavior, latest research/dashboard logic, canonical host safety redirect) is not fully active until these payloads are deployed.
- Live gap closed:
  - Eliminates code drift between production and repo head.

2. Promote runtime manifest to live static paths

- Type: `manifest`
- Paths:
  - `public/data/runtime-manifest.json`
  - `data/runtime-manifest.json`
- Why required:
  - Both endpoints currently return 404 in production.
  - Repo canonical runtime architecture expects this tracked manifest as canonical contract.
- Live gap closed:
  - Makes runtime contract discoverable in production and aligns with manifest-driven architecture.

3. Publish `hunt_research_2026.json` to at least one canonical runtime source that returns 200

- Type: `data` / `runtime asset`
- Path/key:
  - `processed_data/hunt_research_2026.json` (R2/Cloudflare canonical key)
  - optional local fallback path if intentionally retained in deploy package
- Why required:
  - It is missing from both expected live locations:
    - `https://json.uoga.workers.dev/processed_data/hunt_research_2026.json` -> 404
    - `https://huntbuilder.uoga.org/processed_data/hunt_research_2026.json` -> 404
- Live gap closed:
  - Restores the research summary contract source expected by runtime ordering.

## SHOULD_WAIT

1. Alternate domain parity validation (`hunt-builder.uoga.org`)

- Type: `infra/dns`
- Why wait:
  - Domain is DNS-unresolved right now.
  - Canonical production is on `huntbuilder.uoga.org`; parity testing cannot be completed until DNS is restored.

2. Google Earth iframe page (`hunt-builder-google-earth.html`)

- Type: `optional runtime asset`
- Why wait:
  - Current 3D runtime path is `gmp-map-3d` (not iframe mode).
  - This file is 404 live, but not required for current canonical earth-mode path unless iframe mode is re-enabled.

## NOT_REQUIRED

1. `assets/js/hard-copy-public-library.js`

- Status: live byte-equal with repo head.
- No promote action required now.

2. Outfitter and conservation JSON endpoints currently returning 200

- `data/outfitters-public.json`
- `data/conservation-permit-areas.json`
- `data/conservation-permit-hunt-table-2025-27.json`
- No immediate promote action required for live canonical alignment.

3. Alternate-domain redirect-rule code changes beyond current canonical-host policy

- Not required until DNS returns and parity can be validated.

## JS Payloads Out Of Sync (Live vs Repo Head)

- `embed-mode.js`
- `config.js`
- `data.js`
- `app.js`
- `hunt-research.js`
- `assets/js/research-outlook-dashboard.js`
- `assets/css/hard-copy-public-library.css`

## Runtime Manifest Decision

- Promote now: **YES**
- Reason:
  - It is part of repo canonical architecture and currently 404 live.

## `hunt_research_2026.json` Decision

- Generate/promote now: **YES**
- Reason:
  - Missing from both expected runtime locations and required by research runtime source ordering.

## Recommended First Promotion Sequence

1. Publish `processed_data/hunt_research_2026.json` to canonical R2/Cloudflare key and verify HTTP 200.
2. Deploy latest app bundle (the out-of-sync JS/CSS files plus manifest files).
3. Verify:
   - `https://huntbuilder.uoga.org/data/runtime-manifest.json` -> 200
   - `https://huntbuilder.uoga.org/public/data/runtime-manifest.json` -> 200
   - `https://json.uoga.workers.dev/processed_data/hunt_research_2026.json` -> 200
   - Builder/Research/Verify/Hard-copy load without runtime source regressions.

## One Deploy or Multiple?

- Can be aligned in **one coordinated release window** if:
  - R2 publish happens first, then Vercel deploy immediately after.
- Operationally it is **two promotion actions** (R2 publish + app deploy), but can be executed back-to-back as one release.
