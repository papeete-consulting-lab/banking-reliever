# BNK.RLVR.CAP.SUP.002.BEN — Beneficiary Identity Anchor stub — dev Terraform root.
#
# Derivation per the Deployment contract (CLAUDE.md):
#   rlv-knowledge pack BNK.RLVR.CAP.SUP.002.BEN --deep  → what the component needs
#   tech list / tech pack <PLATFORM_CAP>                → how the platform provides it
#
# Resolved platform needs (Mode-B contract+stub — fixture-backed, no DB):
#   - DATA_PERSISTENCE      : none (stub has no domain state; fixtures live
#                             in the image under /app/fixtures).
#   - EVENT_INFRASTRUCTURE  : platform RabbitMQ — BNK.TECH.CAP.DATA.001.BROKER.
#                             Not provisioned per-capability; reached cluster-side
#                             by service-name (`rabbitmq`). The dev credentials
#                             materialise via the ExternalSecret declared in
#                             deployment/dev/k8s/overlay/dev/externalsecret.yaml.
#                             Nothing to declare here.
#   - RUNTIME               : BNK.TECH.CAP.RUNTIME.001.DEPLOY drives the k8s
#                             Deployment/Service which live under
#                             deployment/dev/k8s/ (kustomize). No TF here.
#   - API_CONTRACT          : BNK.TECH.CAP.RUNTIME.002.API_INGRESS — Ingress
#                             rendered under deployment/dev/k8s/overlay/dev/
#                             (URL contract per ADR-TECH-STRAT-003,
#                             role-suffix `/stub/` to co-exist with the real
#                             backend's `/api/`). No TF here.
#   - DEPLOYMENT            : BNK.TECH.CAP.DELIVERY.002.GITOPS reconciles the
#                             k8s manifests; CI publishes the image to
#                             BNK.TECH.CAP.DELIVERY.001.REGISTRY.
#   - IDENTITY (IRSA)       : BNK.TECH.CAP.IDENTITY.001.WORKLOAD — workload
#                             role + ServiceAccount binding. **No upstream
#                             Terraform module exposed yet** → escape-hatch
#                             issue:
#                             https://github.com/Banking-PapeeteConsulting/banking-tech/issues/7
#   - IDENTITY (SECRETS)    : BNK.TECH.CAP.IDENTITY.001.SECRETS — secret-store
#                             paths + read role for the broker AMQP URL.
#                             Currently declared as an ExternalSecret consumer
#                             in k8s overlay; concrete TF module pending — same
#                             escape-hatch coverage (issue #7 — "the four
#                             `source/` modules surfaced by `tech pack` need
#                             to ship a stable `git::ssh://…` reference so
#                             per-component roots can stop using placeholders").
#
# Strategic anchors:
#   - ADR-TECH-STRAT-001  — Bus topology (exchange + routing key + queue naming)
#   - ADR-TECH-STRAT-002  — EKS, modular-monolith packaging per zone
#   - ADR-TECH-STRAT-003  — API URL contract https://k8s.<base>/{env}/<CAP>/...
#   - ADR-TECH-STRAT-006  — train-release model
#   - ADR-TECH-TACT-002   — stub tactical stack (python/fastapi/aio-pika/…)
#
# This file therefore declares zero `module` blocks — every required dependency
# is either platform-shared (out of scope for this capability) or blocked on
# the escape-hatch issue. The TF root is kept in place so the layout matches
# the contract and `terraform init` succeeds (no resources to plan).

# Intentionally empty — see header.
