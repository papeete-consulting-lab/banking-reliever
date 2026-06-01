# BNK.RLVR.CAP.BSP.001.TIE — Tier Management stub — dev Terraform root.
#
# Derivation per the Deployment contract (CLAUDE.md):
#   rlv-knowledge pack BNK.RLVR.CAP.BSP.001.TIE --deep  → what the component needs
#   tech list / tech pack <PLATFORM_CAP>                → how the platform provides it
#
# Resolved platform needs (Mode-B contract stub — no DB, no broker, no DR):
#   - DATA_PERSISTENCE      : none (stub has no domain state).
#   - EVENT_INFRASTRUCTURE  : platform RabbitMQ — BNK.TECH.CAP.DATA.001.BROKER.
#                             Not provisioned per-capability; reached cluster-side
#                             by service-name. Nothing to declare here.
#   - RUNTIME               : BNK.TECH.CAP.RUNTIME.001.DEPLOY drives the k8s
#                             Deployment/Service which live under
#                             deployment/dev/k8s/ (kustomize). No TF here.
#   - API_CONTRACT          : BNK.TECH.CAP.RUNTIME.002.API_INGRESS — Ingress
#                             rendered under deployment/dev/k8s/overlay/dev/.
#                             No TF here.
#   - DEPLOYMENT            : BNK.TECH.CAP.DELIVERY.002.GITOPS reconciles the
#                             k8s manifests; CI publishes the image to
#                             BNK.TECH.CAP.DELIVERY.001.REGISTRY.
#   - IDENTITY (IRSA)       : BNK.TECH.CAP.IDENTITY.001.WORKLOAD — workload
#                             role + ServiceAccount binding. **No upstream
#                             Terraform module exposed yet** → escape-hatch
#                             issue: https://github.com/Banking-PapeeteConsulting/banking-tech/issues/7
#
# This file therefore declares zero `module` blocks — every required dependency
# is either platform-shared (out of scope for this capability) or blocked on
# issue #7. The TF root is kept in place so the layout matches the contract
# and `terraform init` succeeds (no resources to plan).

# Intentionally empty — see header.
