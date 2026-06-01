# Deployment contract — dev Terraform root (CLAUDE.md § "Deployment contract").
#
# Calls banking-tech modules ONLY. Module sources are resolved via the `tech`
# CLI; this file lists the platform capability surface the frontend depends
# on. Concrete `source = "git::ssh://..."` URLs are pending escape-hatch
# issue (see README.md) — DO NOT improvise raw cloud resources.
#
# Platform capability dependency map for this component:
#   - BNK.TECH.CAP.RUNTIME.002.STATIC_HOSTING → S3 bucket-per-env + CloudFront
#                                               facade + cache-invalidation
#                                               primitives. Carries the
#                                               BNK.TECH.OBJ.RUNTIME.002.STATIC_BUNDLE
#                                               object.
#   - BNK.TECH.CAP.RUNTIME.001.DEPLOY        → modular-monolith / workload runtime
#                                               (for the in-cluster nginx variant
#                                               kept as fallback path).
#   - BNK.TECH.CAP.RUNTIME.002.API_INGRESS   → ALB ingress group (URL contract).
#   - BNK.TECH.CAP.IDENTITY.001.WORKLOAD     → IRSA-backed ServiceAccount.
#   - BNK.TECH.CAP.DELIVERY.001.REGISTRY     → ECR image pull policy.
#
# Strategic anchors:
#   - ADR-PCM-FUNC-0006   — RUNTIME.002 L2 decomposition (static_hosting
#                           variant carries the SPA distribution role).
#   - ADR-TECH-STRAT-002  — EKS, modular-monolith packaging per zone.
#   - ADR-TECH-STRAT-003  — URL contract:
#       https://<base>/{env}/{consumer_cap_id}/spa/    ← static_hosting variant
#       https://k8s.<base>/{env}/<CAP>/                ← in-cluster nginx variant
#   - ADR-TECH-STRAT-006  — train-release model.

# ── Static-bundle distribution (S3 + CloudFront) ────────────────────────────
# Per BNK.TECH.CAP.RUNTIME.002.STATIC_HOSTING and ADR-PCM-FUNC-0006.
# Carries the BNK.TECH.OBJ.RUNTIME.002.STATIC_BUNDLE object.
module "static_hosting" {
  # source = "git::ssh://git@github.com/Banking-PapeeteConsulting/banking-tech.git//source/runtime/static_hosting?ref=<tech_pack_ref>"
  source = "../../../../../../../externals-template/banking-tech/runtime/static_hosting"

  project_name     = var.project_name
  environment      = var.environment
  tenant           = var.tenant
  consumer_cap_id  = var.capability_id
  # The bundle_digest is supplied at release time by the train-release pipeline
  # (delivery/registry) — left empty here so `terraform plan` is clean.
  bundle_digest    = ""
  tags             = var.tags
}

# ── Workload Identity (IRSA) ────────────────────────────────────────────────
# Per BNK.TECH.CAP.IDENTITY.001.WORKLOAD. The frontend pod itself does not
# call AWS APIs, but the SA exists for zero-trust attribution.
module "workload_identity" {
  # source = "git::ssh://git@github.com/Banking-PapeeteConsulting/banking-tech.git//source/identity/workload?ref=<tech_pack_ref>"
  source = "../../../../../../../externals-template/banking-tech/identity/workload"

  project_name       = var.project_name
  environment        = var.environment
  tenant             = var.tenant
  capability_id      = var.capability_id
  k8s_namespace      = "reliever-chn-${var.environment}"
  k8s_serviceaccount = "chn-001-dsh-frontend"
  tags               = var.tags
}

# ── API ingress registration (SPA root) ─────────────────────────────────────
# Per BNK.TECH.CAP.RUNTIME.002.API_INGRESS + ADR-TECH-STRAT-003 URL contract.
# The SPA root sits at `/${env}/${capability_id}/`; the sibling BFF
# (TASK-007) registers `/${env}/${capability_id}/api/` on the same ALB group.
module "api_ingress" {
  # source = "git::ssh://git@github.com/Banking-PapeeteConsulting/banking-tech.git//source/runtime/api_ingress?ref=<tech_pack_ref>"
  source = "../../../../../../../externals-template/banking-tech/runtime/api_ingress"

  project_name  = var.project_name
  environment   = var.environment
  tenant        = var.tenant
  capability_id = var.capability_id
  alb_group     = "reliever-${var.environment}"
  url_prefix    = "/${var.environment}/${var.capability_id}/"
  tags          = var.tags
}
