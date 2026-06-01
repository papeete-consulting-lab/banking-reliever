# BNK.RLVR.CAP.SUP.002.BEN — backend — dev Terraform

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
       ADR-TECH-STRAT-004 DATA_PERSISTENCE   ← Rule 2: per-L2 RDS Postgres
       ADR-TECH-STRAT-005 OBSERVABILITY
       ADR-TECH-STRAT-006 DEPLOYMENT (train-release)
       ADR-TECH-STRAT-007 IDENTIFIER
       ADR-TECH-STRAT-008 INFORMATION_PUBLICATION

tech pack BNK.TECH.CAP.DATA.003.DB        → per-L2 Postgres provisioning
tech pack BNK.TECH.CAP.IDENTITY.001.WORKLOAD  → IRSA-backed SA
tech pack BNK.TECH.CAP.IDENTITY.001.SECRETS   → ExternalSecrets bindings
tech pack BNK.TECH.CAP.RUNTIME.001.DEPLOY     → Deployment/Service (k8s only)
tech pack BNK.TECH.CAP.RUNTIME.002.API_INGRESS → ALB ingress registration
tech pack BNK.TECH.CAP.DATA.001.BROKER         → platform-scope (NOT here)
tech pack BNK.TECH.CAP.DELIVERY.001.REGISTRY   → ECR pull policy (no module)
```

## Platform capability dependencies (modules called)

| Platform capability                       | Module slot                  | Purpose                                |
|-------------------------------------------|------------------------------|----------------------------------------|
| `BNK.TECH.CAP.DATA.003.DB`                | `module "db"`                | Per-L2 RDS Postgres (ADR-TECH-STRAT-004 Rule 2) |
| `BNK.TECH.CAP.IDENTITY.001.WORKLOAD`      | `module "workload_identity"` | IRSA role + binding                    |
| `BNK.TECH.CAP.IDENTITY.001.SECRETS`       | `module "secrets_binding"`   | Secret-store paths + read role         |
| `BNK.TECH.CAP.RUNTIME.002.API_INGRESS`    | `module "api_ingress"`       | ALB group + URL contract               |
| `BNK.TECH.CAP.RUNTIME.001.DEPLOY`         | governance anchor — no call  | Deployment + Service live in `dev/k8s/`, reconciled by GitOps per ADR-TECH-STRAT-006. |
| `BNK.TECH.CAP.DATA.001.BROKER`            | platform-scope — no call     | Operational broker is a platform-scope capability; this backend only consumes credentials. |
| `BNK.TECH.CAP.DELIVERY.001.REGISTRY`      | image pull only — no call    | Surfaces via the kustomize image transformer. |

## Escape-hatch — pending platform modules

`tech pack` v2.0.x surfaces the conceptual capabilities + ADR anchors but
does NOT yet expose the concrete Terraform module sources (`git::ssh://…`
URLs, inputs schema, outputs). Per the Deployment contract's escape hatch,
the gap is recorded as a `banking-tech` issue rather than improvised:

- **Issue**: https://github.com/Banking-PapeeteConsulting/banking-tech/issues/6
- **Title**: chore(reliever): platform module needed — runtime/bff Terraform root for BNK.RLVR.CAP.CHN.001.DSH
- **Coverage for THIS root**: the issue is generic ("the four `source/`
  modules surfaced by `tech pack` need to ship a stable `git::ssh://…`
  reference so per-component roots can stop using
  `externals-template/banking-tech/` placeholders"). It covers the four
  module slots in `main.tf` here (`workload_identity`, `db`,
  `secrets_binding`, `api_ingress`). No new issue raised — see CLAUDE.md §
  "Terraform escape hatch": "opens (or finds) a GitHub issue".

Until the issue is resolved, `main.tf` references symbolic module paths
(`../../../../../../../externals-template/banking-tech/...`) under
`externals-template/banking-tech/` so the file parses with `terraform init`
locally, but `terraform apply` against the real cloud must wait for the
canonical `git::ssh://…` sources.

## Files

| File                  | Purpose                                                |
|-----------------------|--------------------------------------------------------|
| `versions.tf`         | Terraform version constraint, empty providers block    |
| `variables.tf`        | Canonical inputs (`project_name`, `environment`, …)    |
| `main.tf`             | banking-tech module calls                              |
| `outputs.tf`          | IRSA role ARN, DB endpoint, ingress URL                |
| `terraform.tfvars.dev`| Dev environment values for the inputs above            |

## Usage (once modules land)

```bash
terraform init
terraform plan  -var-file=terraform.tfvars.dev
terraform apply -var-file=terraform.tfvars.dev
```
