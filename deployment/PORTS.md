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
hash collision, the agent re-hashes with salt `:1`, `:2`, … and records
the salt used.

## Format

```
<capability_id>:<kind>  →  <port>   [salt=<n>] (added by TASK-NNN, YYYY-MM-DD)
```

## Ledger

| Capability                        | Kind | Port  | Salt | Added by         | Date       |
|-----------------------------------|------|-------|------|------------------|------------|
| BNK.RLVR.CAP.SUP.002.BEN          | api  | 26835 | —    | TASK-007         | 2026-06-01 |
