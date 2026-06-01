# BNK.RLVR.CAP.BSP.001.TIE — dev Terraform root

Per the Deployment contract (CLAUDE.md § *Deployment contract (local + dev)*),
this root calls **banking-tech modules only** — no raw cloud resources. When a
needed module is missing, the agent **stops** that resource and opens an
escape-hatch GitHub issue against `Banking-PapeeteConsulting/banking-tech`.

## Resolved platform capabilities

The Mode-B contract stub for `BNK.RLVR.CAP.BSP.001.TIE` has **no per-capability
infra to provision** in `dev`:

| `tech_domain`         | Platform capability                              | Provisioning location          |
|-----------------------|--------------------------------------------------|--------------------------------|
| EVENT_INFRASTRUCTURE  | `BNK.TECH.CAP.DATA.001.BROKER` (RabbitMQ)        | Platform — shared, not here     |
| DATA_PERSISTENCE      | none (stub has no domain state)                  | —                              |
| RUNTIME               | `BNK.TECH.CAP.RUNTIME.001.DEPLOY` (k8s pod)      | `deployment/dev/k8s/`          |
| API_CONTRACT          | `BNK.TECH.CAP.RUNTIME.002.API_INGRESS` (ALB)     | `deployment/dev/k8s/overlay/`  |
| DEPLOYMENT            | `BNK.TECH.CAP.DELIVERY.002.GITOPS`               | GitOps reconciler — not here    |
| IDENTITY (workload)   | `BNK.TECH.CAP.IDENTITY.001.WORKLOAD` (IRSA)      | **BLOCKED — see issue below**  |

## Open banking-tech escape-hatch issues

- `IDENTITY/workload` IRSA module not exposed by `banking-tech` v2.0.0
  (`tech list` / `tech pack` confirm no module reference) →
  https://github.com/Banking-PapeeteConsulting/banking-tech/issues/7

Until #7 lands, the ServiceAccount annotation `eks.amazonaws.com/role-arn`
is overlaid out-of-band by the dev cluster bootstrap (or manually).

## Why this root has no `module` blocks

Every resolved need above is either *shared at the platform layer* (the L2
capability cannot — and must not — duplicate it) or *blocked on a missing
upstream module*. The root is kept in place so:

- the directory contract is satisfied (`deployment/dev/terraform/` exists);
- `terraform init && terraform plan` succeeds cleanly (no resources to plan);
- the moment issue #7 lands, the module call slots in here without restructuring.

## Apply

```bash
cd sources/BNK.RLVR.CAP.BSP.001.TIE/stub/deployment/dev/terraform
terraform init
terraform plan -var-file=terraform.tfvars.dev -var "tenant=<tenant-slug>"
```

The plan should be empty until issue #7 is resolved.
