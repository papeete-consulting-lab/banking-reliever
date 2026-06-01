# BNK.RLVR.CAP.CHN.001.DSH — BFF — dev Terraform

Per the Deployment contract (CLAUDE.md § "Deployment contract (local + dev)"),
this root calls **banking-tech modules only** — no raw cloud resources.
The chain is always **`rlv-knowledge pack` → `tech pack`**; this repo never
reads `banking-tech` directly.

## Platform capability dependencies

Resolved via `tech pack <PLATFORM_CAP_ID>`:

| Platform capability | Module slot |
|---|---|
| `BNK.TECH.CAP.IDENTITY.001.WORKLOAD` | `module "workload_identity"` |
| `BNK.TECH.CAP.IDENTITY.001.SECRETS`  | `module "secrets_binding"` |
| `BNK.TECH.CAP.RUNTIME.002.API_INGRESS` | `module "api_ingress"` |
| `BNK.TECH.CAP.RUNTIME.001.DEPLOY` | governance anchor — no module call (the Deployment + Service live in `dev/k8s/` reconciled by GitOps per ADR-TECH-STRAT-006). |
| `BNK.TECH.CAP.DELIVERY.001.REGISTRY` | image pull only (no module call). |

## Escape-hatch — pending platform modules

`tech pack` v2.0.0 surfaces the conceptual capabilities + ADR anchors but
does NOT yet expose the concrete Terraform module sources (`git::ssh://…`
URLs, inputs schema, outputs). Per the Deployment contract's escape hatch,
this gap is recorded as a `banking-tech` issue rather than improvised:

- **Issue**: https://github.com/Banking-PapeeteConsulting/banking-tech/issues/6
- **Title**: chore(reliever): platform module needed — runtime/bff Terraform root for BNK.RLVR.CAP.CHN.001.DSH

Until the issue is resolved, `main.tf` references symbolic module paths
(`../../../../../../../externals-template/banking-tech/...`) under
`externals-template/banking-tech/` so the file parses with `terraform init`
locally, but `terraform apply` against the real cloud must wait for the
canonical `git::ssh://…` sources.

## Usage (once modules land)

```bash
terraform init
terraform plan  -var-file=terraform.tfvars.dev
terraform apply -var-file=terraform.tfvars.dev
```

## Layout

```
deployment/dev/terraform/
├── README.md              ← this file (escape-hatch issue URL is here)
├── versions.tf            ← Terraform + provider pins
├── variables.tf           ← project_name / environment / tenant / tags
├── main.tf                ← banking-tech module calls
├── outputs.tf             ← IRSA role ARN + ingress hostname
└── terraform.tfvars.dev   ← dev environment values
```
