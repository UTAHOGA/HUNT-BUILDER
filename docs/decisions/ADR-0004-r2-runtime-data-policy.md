# ADR-0004: R2 Runtime Data Policy

- Status: Accepted
- Date: 2026-08-26

## Decision

Large generated runtime and audit artifacts remain repo-external and are delivered through Cloudflare R2. Git stores source code, compact authority records, schemas, small manifests, and reproducible instructions.

Missing R2-backed files do not authorize redesign. A task that needs them must restore or regenerate the declared artifacts. Files over 100 MB are not committed; files over 50 MB require review.

## Reason

The prediction and ladder artifacts are too large for a safe normal Git workflow, but their absence from a clone previously looked like an unfinished design rather than an external-data policy.

## Consequences

`governance/engine-authority.json` records both logical paths and external URLs. Code-only validation may pass with documented external artifacts absent; prediction rebuild and promotion validation may not.
