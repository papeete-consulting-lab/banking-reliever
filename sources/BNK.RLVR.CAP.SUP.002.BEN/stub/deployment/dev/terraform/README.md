# BNK.RLVR.CAP.SUP.002.BEN — stub — dev Terraform

Per the Deployment contract (CLAUDE.md § "Deployment contract (local + dev)"),
this root calls **banking-tech modules only** — no raw cloud resources.
The chain is always **`rlv-knowledge pack` → `tech pack`**; this repo
never reads `banking-tech` directly.

## Derivation chain that produced this root

```text
rlv-knowledge pack BNK.RLVR.CAP.SUP.002.BEN --deep
  → slices.tactical_stack[0].id   = ADR-TECH-TACT-002
  → slices.tactical_stack[0].tags = [python, fastapi, postgresql, pgcrypto,
       vault-transit, crypto-shredding, uuidv7, gdpr-erasure,
       per-client-deployment, aws-eks, train-release, image-signing,
       disaster-recovery, demo-data-isolation]
  → governing_tech_strat:
       ADR-TECH-STRAT-001 EVENT_INFRASTRUCTURE
       ADR-TECH-STRAT-002 RUNTIME
       ADR-TECH-STRAT-003 API_CONTRACT
       ADR-TECH-STRAT-006 DEPLOYMENT (train-release)
       ADR-TECH-STRAT-007 IDENTIFIER
       ADR-TECH-STRAT-008 INFORMATION_PUBLICATION

tech pack BNK.TECH.CAP.IDENTITY.001.WORKLOAD  → IRSA-backed SA       (gap — see #7)
tech pack BNK.TECH.CAP.IDENTITY.001.SECRETS   → ExternalSecrets path (gap — see #7)
tech pack BNK.TECH.CAP.RUNTIME.001.DEPLOY     → Deployment/Service (k8s — no TF)
tech pack BNK.TECH.CAP.RUNTIME.002.API_INGRESS → ALB ingress (k8s — no TF)
tech pack BNK.TECH.CAP.DATA.001.BROKER         → platform-scope (NOT here)
tech pack BNK.TECH.CAP.DELIVERY.001.REGISTRY   → ECR pull (no TF)
tech pack BNK.TECH.CAP.DELIVERY.002.GITOPS     → GitOps reconciler (no TF)
```

## Mode-B stub specifics

Unlike the sibling **backend** (TASK-007) which provisions a per-L2 RDS
Postgres + ExternalSecret bindings for both broker creds **and** DB DSN,
the stub is **fixture-backed**:

- **No database** — canned fixtures live in the container image under
  `/app/fixtures/`. No `data/db` module to call.
- **Only a broker credential** is consumed (declared as an ExternalSecret
  in `../k8s/overlay/dev/externalsecret.yaml`, not provisioned here).
- **No outbox table, no projection consumer, no migrations**. The publisher
  loop in the stub emits synthetic events directly from the schema +
  fixture pool.

The stub will be decommissioned once the matching backend lifecycle tasks
ship; this TF root is intentionally minimal so removal is a clean delete.

## Escape-hatch — pending platform modules

`tech pack` v2.0.x surfaces the conceptual capabilities + ADR anchors but
does NOT yet expose the concrete Terraform module sources (`git::ssh://…`
URLs, inputs schema, outputs). Per the Deployment contract's escape hatch,
the gap is recorded as a `banking-tech` issue rather than improvised:

- **Issue**: https://github.com/Banking-PapeeteConsulting/banking-tech/issues/7
- **Coverage for THIS root**: the issue is generic ("the four `source/`
  modules surfaced by `tech pack` need to ship a stable `git::ssh://…`
  reference so per-component roots can stop using
  `externals-template/banking-tech/` placeholders"). It covers the two
  module slots this stub would call once they land
  (`workload_identity` and `secrets_binding`). No new issue raised — see
  CLAUDE.md § "Terraform escape hatch": "opens (or finds) a GitHub issue".

Until the issue is resolved, this root declares **zero `module` blocks**.
The directory contract is satisfied (`versions.tf`, `variables.tf`,
`main.tf`, `outputs.tf`, `terraform.tfvars.dev`) and `terraform init`
+ `terraform validate` succeed against an empty plan.

## Files

| File                  | Purpose                                                |
|-----------------------|--------------------------------------------------------|
| `versions.tf`         | Terraform version constraint + AWS provider            |
| `variables.tf`        | Canonical inputs (`project_name`, `environment`, …)    |
| `main.tf`             | (empty) — header documents the resolved dependencies   |
| `outputs.tf`          | (empty) — no resources to surface yet                  |
| `terraform.tfvars.dev`| Dev environment values for the inputs above            |

## Usage (once modules land)

```bash
terraform init
terraform plan  -var-file=terraform.tfvars.dev -var="tenant=demo-tenant"
terraform apply -var-file=terraform.tfvars.dev -var="tenant=demo-tenant"
```
