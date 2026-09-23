# Reviewed corrective release — September 21, 2026

Scope: preserve the existing certified Research probability release, repair source
import/build safety, align the Research shell on both hosts, and restore retained
document/detail URLs. This is not a new model build or a certification decision.

The work is isolated in `C:/hb-corrective-20260921`, based on remote commit
`0b70665e96a84071d28258a3451e3ce9c3004404`. The original main checkout, pending
changes and unpushed commit are not included. The antlerless resolver is deferred
at Tyler's instruction and is not changed or executed by this release.

## Corrections

- Repair invalid Bear indentation and availability control flow. Restore the
  availability identity validator required by existing materializer imports.
  This does not rebuild or promote Bear probabilities.
- Disable eight identified direct source/artifact patchers before they can run.
  Their original bodies remain for inspection. In particular, no guessed cutoff,
  quota or certification flag may be stamped into saved predictions.
- Preserve source provenance and allocation metadata in the compact Builder
  catalog. All 1,848 current records are reconciled to DATABASE reference fields;
  existing numerical quotas are unchanged. The older page-contract catalog
  copies now contain the same current inventory.
- Preserve 1,867 deployed per-hunt Research details through hash-pinned hydration.
- Separate website packaging from existing explicit data-generation commands.
  Clean builds previously fell back to two fixture rows when large inputs were
  absent. Website packaging now retains verified deployed public data and restores
  missing URLs using a hash-pinned asset inventory. Large R2 files are not rebuilt.
- Add import, allocation-provenance and patcher-safety regression checks.

## Release evidence

Local evidence root: `C:/hb-release-evidence-20260921`.

- Cloudflare rollback: all 4,249 files from deployment
  `3c71b92f-c607-4539-a506-d316921c5918`, verified against the deployment inventory
  and retained with SHA-256 checksums.
- Vercel rollback: retain immutable deployment
  `dpl_4uTKeSGStQyhu1eRQ33yh3koRwGg`; a public build-inventory snapshot additionally
  retains 343 accessible files from the public domain. The other 3,924 probed URLs
  returned 404. This is a bounded public inventory, not an exhaustive API export
  of the old Git-sourced deployment.
- Reject the earlier `vercel-before` snapshot: its protected deployment URL
  redirected to login pages. It is not a usable website backup. The snapshot
  helper now rejects cross-origin redirects.
- Seven retained R2 objects match the previously recorded production hashes.
  This release does not upload new R2 objects or change their version token.
- Candidate V2 retains 4,249 Pages files and 4,250 Vercel files, including restored
  documents and direct Research details. Ten reviewed overlay files match between
  hosts. Four shared dependency differences were CRLF/LF only, verified before
  normalization. Other host-specific existing files are preserved.
- The temporary Vercel placeholder project accidentally created during preparation
  was removed after its upload was stopped. The retry explicitly pins the existing
  Hunt Builder project ID.

## Verification and limits

- `npm test`: project-memory 141 checks, canonical/page-contract checks and permit
  verification pass; ten optional local-hydration warnings are expected here.
- 61 core engine/scoring/quota/frontend tests and 15 import/availability/catalog
  safety tests pass. Research guidance checks pass.
- Local browser population: 1,255/1,255 pass; zero failed requests or console errors;
  actual fetched summary/index hashes match the frozen contract.
- A 19-case preview smoke invocation omitted the frozen coverage input and retained
  an obsolete expected probability for DB1106 Resident at 32 points. It reports
  18/19, with no request/console failure. The full preview run uses the unchanged
  frozen per-rung expectations, including intentional empty rungs.
- No fresh historical folds were generated. No family was newly certified. Existing
  noncertified families remain withheld. Historical truth and DATABASE are unchanged.
- Promoted Pages `094c2549-a0c3-450b-8fe9-c411c0d2e970` and Vercel
  `dpl_F3Zwa8DGDx19CP7HLdr73jRCo7PM`. All 4,249 Pages / 4,250 Vercel deployment
  objects match their candidate inventories. Fifty-six public readbacks pass.
  Pages preview and Vercel live each pass 1,255/1,255 browser scenarios; Pages
  production passes 19/19 smoke cases using frozen per-rung expectations.
  There are no failed requests or console errors in those passing runs.
- `governance/releases/20260921-corrective-release.json` is the authoritative
  release manifest containing exact per-file hashes, R2 object hashes, old/new
  deployment IDs, backup paths and verification-report hashes.
- The three fixture-derived outputs created by the rejected build were moved to
  the external evidence folder after exact-hash checks. Previously tracked
  generated contracts were restored; the rejected build was never published.

## Rollback

Rollback both hosts together: restore the prior Cloudflare production deployment
and promote Vercel's retained prior deployment. Seven R2 objects are unchanged, so
no data reversal is needed. The candidate release manifest holds exact old/new
file hashes and backup locations. Do not use the rejected login-page snapshot.
