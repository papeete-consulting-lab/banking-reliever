# Component port ledger

Audit log of every deterministic `COMPONENT_PORT` allocated per the
**Deployment contract** (CLAUDE.md § *Deployment contract (local + dev)*).

Formula:
```
PORT = 20000 + ( int(sha256(f"{capability_id}:{kind}").hexdigest()[:8], 16) % 9000 )
kind ∈ { api, bff, frontend }    # range 20000–28999
```

When a hash collision occurs across capabilities, the agent re-hashes with
salt `:1`, `:2`, … and records the salt in the row.

| Capability id                     | Kind | Salt | Port  | TASK     | Added on   |
|-----------------------------------|------|------|-------|----------|------------|
| BNK.RLVR.CAP.BSP.001.TIE          | api  | —    | 20393 | TASK-002 | 2026-06-01 |
