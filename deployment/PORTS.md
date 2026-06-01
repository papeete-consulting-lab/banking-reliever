# Deterministic component-port audit ledger

Per **CLAUDE.md § "Deployment contract (local + dev)" / "Local environment"**,
every component's local listen port is **deterministic** from its
capability_id and kind:

```python
PORT = 20000 + ( int(sha256(f"{capability_id}:{kind}").hexdigest()[:8], 16) % 9000 )
kind ∈ { api, bff, frontend }          # → range [20000, 28999]
```

Same capability + same kind → same port across every branch and every
laptop. The *one active task per capability* invariant guarantees no
intra-capability conflict.

This file is the **cross-capability collision detector**. Each Stage-4
agent that scaffolds a component appends its assigned port here. On a
hash collision (cross-capability — random) **or** an intra-capability
duplicate kind (e.g. both a Mode-A `backend/` and a Mode-B `stub/` claim
`kind=api` for the same capability), the agent re-hashes with salt `:1`,
`:2`, … and records the salt used.

## Format

```
<capability_id>:<kind>[:<salt>]  →  <port>   [salt=:<n>] (added by TASK-NNN, YYYY-MM-DD)
```

## Ledger

| Capability                          | Kind     | Salt | Port  | Added by          | Date       |
|-------------------------------------|----------|------|-------|-------------------|------------|
| BNK.RLVR.CAP.SUP.002.BEN (backend)  | api      | —    | 26835 | TASK-007 (PR #35) | 2026-06-01 |
| BNK.RLVR.CAP.SUP.002.BEN (stub)     | api      | `:1` | 21595 | TASK-008          | 2026-06-01 |
| BNK.RLVR.CAP.BSP.001.SCO (stub)     | api      | —    | 23074 | TASK-007 (PR #30) | 2026-06-01 |
| BNK.RLVR.CAP.BSP.001.TIE (stub)     | api      | —    | 20393 | TASK-002 (PR #32) | 2026-06-01 |
| BNK.RLVR.CAP.CHN.001.DSH            | bff      | —    | 22328 | TASK-007 (PR #31) | 2026-06-01 |
| BNK.RLVR.CAP.CHN.001.DSH            | frontend | —    | 22695 | TASK-008 (PR #34) | 2026-06-01 |

## Notes

- **TASK-007** (Mode-A backend microservice) takes the salt-free allocation
  `26835` for `BNK.RLVR.CAP.SUP.002.BEN:api`. Recorded here pre-emptively —
  TASK-007's PR #35 is in_review at the time TASK-008 lands but the row is
  anticipated so the audit ledger reflects reality once #35 merges.
- **TASK-008** (this row) re-hashes with salt `:1` because the salt-free
  port is taken by TASK-007 (same capability, same `kind=api` — Mode-A
  backend + Mode-B stub co-exist during the lifecycle-task migration
  window). Salt `:1` resolves to `21595` (no further collision detected
  in the ledger as of 2026-06-01).
