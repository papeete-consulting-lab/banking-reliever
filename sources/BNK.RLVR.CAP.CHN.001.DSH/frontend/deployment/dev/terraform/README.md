# BNK.RLVR.CAP.CHN.001.DSH — Frontend — dev Terraform

Per the Deployment contract (CLAUDE.md § "Deployment contract (local + dev)"),
this root calls **banking-tech modules only** — no raw cloud resources.
The chain is always **`rlv-knowledge pack` → `tech pack`**; this repo never
reads `banking-tech` directly.

## Platform capability dependencies

Resolved via `tech pack <PLATFORM_CAP_ID>`:

| Platform capability | Module slot |
|---|---|
| `BNK.TECH.CAP.RUNTIME.002.STATIC_HOSTING` | `module "static_hosting"` — S3 bucket-per-env + CloudFront facade + cache-invalidation primitives (carries `BNK.TECH.OBJ.RUNTIME.002.STATIC_BUNDLE`). |
| `BNK.TECH.CAP.IDENTITY.001.WORKLOAD` | `module "workload_identity"` — IRSA-backed ServiceAccount (frontend pod has no AWS calls; SA exists for zero-trust attribution). |
| `BNK.TECH.CAP.RUNTIME.002.API_INGRESS` | `module "api_ingress"` — ALB ingress group for the SPA root (`/{env}/<CAP_ID>/`). |
| `BNK.TECH.CAP.RUNTIME.001.DEPLOY` | governance anchor — no module call (the Deployment + Service live in `dev/k8s/` reconciled by GitOps per ADR-TECH-STRAT-006). |
| `BNK.TECH.CAP.DELIVERY.001.REGISTRY` | image pull only (no module call). |

## Distribution variants

ADR-TECH-STRAT-003 names two distribution variants for the SPA:

- **In-cluster nginx** — `https://k8s.<base>/{env}/<CAP_ID>/` served by the
  k8s Deployment in `dev/k8s/`. The ALB routes the SPA root to the frontend
  Service; the sibling BFF (TASK-007) registers the `/api/` sub-path on the
  same ALB group.
- **Static-bundle distribution** — `https://<base>/{env}/<CAP_ID>/spa/`
  served by S3 + CloudFront via the `static_hosting` module. Carries the
  `BNK.TECH.OBJ.RUNTIME.002.STATIC_BUNDLE` object.

The Terraform root provisions BOTH targets so the train-release pipeline can
flip between them per environment without re-shaping the dev tree.

## Escape-hatch — pending platform modules

`tech pack` v2.0.0 surfaces the conceptual capabilities + ADR anchors but
does NOT yet expose the concrete Terraform module sources (`git::ssh://…`
URLs, inputs schema, outputs) for `source/runtime/static_hosting`,
`source/identity/workload`, or `source/runtime/api_ingress`. Per the
Deployment contract's escape hatch, this gap is recorded as a `banking-tech`
issue rather than improvised:

- **Issue**: https://github.com/Banking-PapeeteConsulting/banking-tech/issues/8
- **Title**: chore(reliever): platform module needed — runtime/static_hosting + frontend Terraform root for BNK.RLVR.CAP.CHN.001.DSH

Sibling issue #6 covers the BFF Terraform root and shares the
`workload_identity` / `api_ingress` ask. They can land together.

Until the issues are resolved, `main.tf` references symbolic module paths
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
├── outputs.tf             ← IRSA role ARN + ingress hostname + CDN URL
└── terraform.tfvars.dev   ← dev environment values
```
