# AGENTS.md

## Project Memory Contract

The repository is the durable memory for this project. Before inspecting or changing Hunt Research, prediction-engine, truth, runtime, build, or deployment behavior:

1. Read `docs/CURRENT_STATE.md`.
2. Read `governance/engine-authority.json`.
3. Read `docs/UTAH_DRAW_DESIGN_BASELINE.md` for prediction, routing, quota, residency, bear, or applicant-behavior work.
4. Read the applicable accepted records in `docs/decisions/`.
5. Run `npm run validate:project-memory` before editing and again before finishing.

`governance/engine-authority.json` is the machine-readable statement of the active architecture and current promotion state. `docs/CURRENT_STATE.md` is its human-readable briefing. Accepted decision records explain why the architecture exists. `WORK_LOG.md` is historical evidence only and must not override the current-state or authority contracts.

Do not create a new prediction-engine stack, parallel Research runtime, alternate truth authority, or replacement probability contract unless Tyler explicitly approves that architectural change. Improve the declared owning module instead. If implementation and the memory contract disagree, report the conflict and update the contract in the same approved change; do not silently select a different architecture. A requested architecture change must add or supersede an ADR and update `governance/engine-authority.json`.

## General Project Rules

Read this file before every task. Tyler's explicit instruction controls the task scope: if Tyler tells you to edit website, deploy, UI, production, engine, data, or truth files, then that file class is in scope for that task. Do not add extra restrictions that block the requested work.

Before starting, check `git status --short` and `git diff --cached --name-status`; if anything is unexpectedly staged, stop and ask.

Do not stage or commit large generated data files: files over 100 MB are prohibited from Git, files over 50 MB require review, and large generated JSON/CSV/GeoJSON/SQLite/runtime outputs belong in Cloudflare R2, not Git. Do not use Git LFS unless Tyler explicitly requests it. Never upload or commit `.git`, `.wrangler/state`, `node_modules`, cache blobs, or local generated audit junk.

Vercel deploys from `pages-dist` because `vercel.json` uses `buildCommand: npm run build` and `outputDirectory: pages-dist`; do not delete `pages-dist`. `pages-dist` may be edited or rebuilt when Tyler asks for website/deploy/build/live work. For data-engine/audit/model work, avoid unrelated website/deploy changes unless Tyler asks for them. For website/deploy/build/live work, edit the necessary website files directly and rebuild `pages-dist` as required. `scripts/build-pages-dist.js` should avoid duplicating huge runtime data into `pages-dist`; files over 100 MB should be R2-backed or skipped with a small manifest when possible.

Prediction-engine work should follow the simple loop: feed official scorable truth rows, generate predictions, compare against following-year official actual truth, identify error patterns, edit engine logic, and rerun. Ignore unscorable rows for accuracy work and never fabricate probability from permit totals, quota rows, CWMU contact-operator rows, guidebook rows, allocation-only rows, or reference rows. Sportsman permits are `SPORTSMAN_RANDOM_ONLY`; youth rows must be source-classified and not guessed; guaranteed/lifetime/general guaranteed-tag rows are not prediction rows; CWMU Contact Operator rows with blank permit numbers are `CWMU_CONTACT_OPERATOR_REFERENCE_ONLY`; allocation/reference-only rows are not probability rows.

Before finishing any task, run `git diff --cached --name-status` and `git status --short`, report whether anything is staged, and do not leave large generated files staged.
