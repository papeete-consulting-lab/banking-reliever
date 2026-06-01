# Deployment contract — deterministic port ledger

Append-only audit ledger of `COMPONENT_PORT` assignments. Each row is the
SHA-256-derived port for one `(capability_id, kind)` tuple per the formula in
CLAUDE.md § "Deployment contract (local + dev)":

```
PORT = 20000 + ( int(sha256(f"{capability_id}:{kind}").hexdigest()[:8], 16) % 9000 )
kind ∈ { api, bff, frontend }    # range 20000–28999
```

Same capability + same kind → same port across every branch and every laptop.

## Collision protocol

Cross-capability hash collisions are resolved by re-hashing with salt suffixes:
`{capability_id}:{kind}:1`, `:2`, `:3`, … The first salt-free row wins; later
rows with the same value record the salt they used.

## Ledger

| capability_id | kind | port | salt | task |
|---|---|---|---|---|
| `BNK.RLVR.CAP.CHN.001.DSH` | `bff` | 22328 | — | TASK-007 |
| `BNK.RLVR.CAP.CHN.001.DSH` | `frontend` | 22695 | — | TASK-008 |
