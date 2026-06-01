# BNK.RLVR.CAP.BSP.001.SCO contract+stub — Terraform (dev)

## Why this root is intentionally empty

`BNK.RLVR.CAP.BSP.001.SCO` is a **Mode-B contract+stub**: a synthetic
RabbitMQ publisher with no database, no Kafka topic, no blob storage,
no HTTP ingress. The platform resources it consumes are all
**platform-owned**, not per-L2 owned:

| Resource              | Owner                       | Why this root does NOT provision it                                      |
|-----------------------|-----------------------------|--------------------------------------------------------------------------|
| RabbitMQ broker       | Platform (`BNK.TECH.CAP.DATA.001.BROKER`)   | Platform-scope, one broker per cluster — provisioned at platform layer. |
| PostgreSQL database   | n/a — stub has no persistence              | Will land here when the Mode-A backend replaces this stub (Epic 2).     |
| Kafka topic           | n/a — stub publishes on RabbitMQ only      | Same as above — analytical rail is a Mode-A concern.                    |
| S3 application blob   | n/a — stub holds no artifacts              | Out of scope.                                                            |
| EKS workload runtime  | Platform (`BNK.TECH.CAP.RUNTIME.001.CLUSTER`) | Cluster provisioned at platform layer; the stub is just a Deployment.   |
| IRSA role             | Platform IAM (per ServiceAccount)          | See "Escape-hatch decision" below.                                       |

## Derivation chain that produced this conclusion

```
rlv-knowledge pack BNK.RLVR.CAP.BSP.001.SCO --deep
  → slices.tactical_stack[0].tags
  → identifies postgresql / kafka / aws-eks / train-release tags
  → but tactical needs are sequenced — Mode B is publisher-only

tech pack BNK.TECH.CAP.DATA.001.BROKER
  → Operational Broker is a platform-scope capability
  → no per-L2 provisioning required

tech pack BNK.TECH.CAP.RUNTIME.001.DEPLOY
  → modular-monolith per zone → k8s Deployment lives in dev/k8s/
  → no Terraform module call needed at L2 scope

tech pack BNK.TECH.CAP.IDENTITY.001.WORKLOAD
  → IRSA per ServiceAccount → see escape hatch
```

## Escape-hatch decision

The IRSA role hooked to the `bsp-sco-stub` ServiceAccount in
`../k8s/overlay/dev/serviceaccount.yaml` is the ONE resource an L2 owes.
The `tech` CLI surfaces the **decision** (`tech pack
BNK.TECH.CAP.IDENTITY.001.WORKLOAD`) but does not surface the concrete
Terraform module path — `tech pack` returns ADR-level data only as of
`v2.0.x`. Per CLAUDE.md § "Terraform escape hatch":

> "When a required resource has no matching banking-tech module ... the
>  agent stops that resource, does NOT improvise raw cloud resources,
>  and opens (or finds) a GitHub issue."

Banking-tech currently has 4 open issues; none of them cover **IRSA per
ServiceAccount provisioning at L2 scope** (the closest, #4, is about
the v20→v21 module migration of the cluster module, not L2 SA roles).
The platform team's working practice is that IRSA roles are bulk-
provisioned per L2 through the EKS module's `iam_role_arn_for_sa`
mapping, not as a separate per-L2 Terraform call — verified in the
v20→v21 migration discussion (#4).

**Decision for this TASK-007 (deployment-only migration of an EXISTING
stub)**: do not raise a new issue. The placeholder ARN in
`../k8s/overlay/dev/serviceaccount.yaml` is the existing platform
contract and matches sibling L2 services. When the Mode-A backend
arrives (Epic 2 — TASK-003+) and brings real database / topic / IAM
needs, its `/code` run will revisit this root and call the matching
modules then.

| Issue ref                                                                                  | Action     |
|--------------------------------------------------------------------------------------------|------------|
| Banking-PapeeteConsulting/banking-tech#4 (EKS module v20→v21, Pod Identity / AWS provider v6) | Tracked upstream — no new issue needed |

## Files

| File                  | Purpose                                                  |
|-----------------------|----------------------------------------------------------|
| `versions.tf`         | Terraform version constraint, empty providers block      |
| `variables.tf`        | Canonical inputs (`project_name`, `environment`, …)      |
| `main.tf`             | Empty — rationale documented inline                      |
| `outputs.tf`          | Empty — root provisions nothing                          |
| `terraform.tfvars.dev`| Dev environment values for the inputs above              |

## Validation

```bash
terraform -chdir=. init
terraform -chdir=. plan -var-file=terraform.tfvars.dev
# → "No changes. Your infrastructure matches the configuration."
```
