# ADR-0001: Repository Memory Authority

- Status: Accepted
- Date: 2026-08-26

## Decision

The repository, not conversational memory, is the durable authority for Hunt Builder architecture and current state.

Every related task must load `AGENTS.MD`, `docs/CURRENT_STATE.md`, `governance/engine-authority.json`, and the applicable accepted ADRs. `npm run validate:project-memory` enforces agreement between those records and the declared implementation.

## Reason

Conversational context can be unavailable or incomplete in a new task. The repository is versioned, reviewable, testable, and shared by every model and developer.

## Consequences

- `WORK_LOG.md` remains historical evidence only.
- Architecture changes update the authority JSON and add or supersede an ADR.
- Implementation conflicts are surfaced; they are not resolved by silently starting a replacement design.
