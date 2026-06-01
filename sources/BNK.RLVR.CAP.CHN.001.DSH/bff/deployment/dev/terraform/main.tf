# Deployment contract — dev Terraform root (CLAUDE.md § "Deployment contract").
#
# Calls banking-tech modules ONLY. Module sources are resolved via the `tech`
# CLI; this file lists the platform capability surface the BFF depends on.
# Concrete `source = "git::ssh://..."` URLs are pending escape-hatch issue
# (see README.md) — DO NOT improvise raw cloud resources.
#
# Platform capability dependency map for this component:
#   - BNK.TECH.CAP.RUNTIME.001.DEPLOY     → modular-monolith / workload runtime
#   - BNK.TECH.CAP.RUNTIME.002.API_INGRESS → ALB ingress group (URL contract)
#   - BNK.TECH.CAP.IDENTITY.001.WORKLOAD  → IRSA-backed ServiceAccount
#   - BNK.TECH.CAP.IDENTITY.001.SECRETS   → ExternalSecrets binding (broker creds)
#   - BNK.TECH.CAP.DELIVERY.001.REGISTRY  → ECR image pull policy
#   - BNK.TECH.CAP.DATA.001.BROKER        → consumed by host-side platform; this
#                                            component only consumes credentials.
#
# Strategic anchors:
#   - ADR-TECH-STRAT-002  — EKS, modular-monolith packaging per zone
#   - ADR-TECH-STRAT-003  — API URL contract https://k8s.<base>/{env}/<CAP>/api/
#   - ADR-TECH-STRAT-006  — train-release model

# ── Workload Identity (IRSA) ────────────────────────────────────────────────
# Per BNK.TECH.CAP.IDENTITY.001.WORKLOAD.
module "workload_identity" {
  # source = "git::ssh://git@github.com/Banking-PapeeteConsulting/banking-tech.git//source/identity/workload?ref=<tech_pack_ref>"
  source = "../../../../../../../externals-template/banking-tech/identity/workload"

  project_name       = var.project_name
  environment        = var.environment
  tenant             = var.tenant
  capability_id      = var.capability_id
  k8s_namespace      = "reliever-chn-${var.environment}"
  k8s_serviceaccount = "chn-001-dsh-bff"
  tags               = var.tags
}

# ── Secrets binding (broker credentials) ────────────────────────────────────
# Per BNK.TECH.CAP.IDENTITY.001.SECRETS.
module "secrets_binding" {
  # source = "git::ssh://git@github.com/Banking-PapeeteConsulting/banking-tech.git//source/identity/secrets?ref=<tech_pack_ref>"
  source = "../../../../../../../externals-template/banking-tech/identity/secrets"

  project_name  = var.project_name
  environment   = var.environment
  tenant        = var.tenant
  capability_id = var.capability_id
  secret_paths = [
    "dev/reliever/chn/001/dsh/bff/broker",
  ]
  consuming_role_arn = module.workload_identity.role_arn
  tags               = var.tags
}

# ── API ingress registration ────────────────────────────────────────────────
# Per BNK.TECH.CAP.RUNTIME.002.API_INGRESS + ADR-TECH-STRAT-003 URL contract.
module "api_ingress" {
  # source = "git::ssh://git@github.com/Banking-PapeeteConsulting/banking-tech.git//source/runtime/api_ingress?ref=<tech_pack_ref>"
  source = "../../../../../../../externals-template/banking-tech/runtime/api_ingress"

  project_name  = var.project_name
  environment   = var.environment
  tenant        = var.tenant
  capability_id = var.capability_id
  alb_group     = "reliever-${var.environment}"
  url_prefix    = "/${var.environment}/${var.capability_id}/api/"
  tags          = var.tags
}
