# BNK.RLVR.CAP.SUP.002.BEN — backend — Terraform root (dev).
#
# Calls banking-tech modules ONLY. Module sources are resolved via the
# `tech` CLI; this file lists the platform capability surface the backend
# microservice depends on. Concrete `source = "git::ssh://..."` URLs are
# pending the escape-hatch issue (see README.md) — DO NOT improvise raw
# cloud resources.
#
# Platform capability dependency map for this component:
#   - BNK.TECH.CAP.DATA.003.DB            → per-L2 RDS Postgres (ADR-TECH-STRAT-004 Rule 2)
#   - BNK.TECH.CAP.RUNTIME.001.DEPLOY     → modular-monolith / workload runtime
#   - BNK.TECH.CAP.RUNTIME.002.API_INGRESS → ALB ingress group (URL contract)
#   - BNK.TECH.CAP.IDENTITY.001.WORKLOAD  → IRSA-backed ServiceAccount
#   - BNK.TECH.CAP.IDENTITY.001.SECRETS   → ExternalSecrets bindings
#                                           (broker creds + db DSN)
#   - BNK.TECH.CAP.DELIVERY.001.REGISTRY  → ECR image pull only (no module call)
#   - BNK.TECH.CAP.DATA.001.BROKER        → platform-scope (NOT provisioned here;
#                                           the platform broker is shared)
#
# Strategic anchors:
#   - ADR-TECH-STRAT-002  — EKS, modular-monolith packaging per zone
#   - ADR-TECH-STRAT-003  — API URL contract https://k8s.<base>/{env}/<CAP>/api/
#   - ADR-TECH-STRAT-004  — Per-L2 RDS Postgres (Rule 2)
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
  k8s_namespace      = "reliever-sup-${var.environment}"
  k8s_serviceaccount = "sup-002-ben-backend"
  tags               = var.tags
}

# ── Per-L2 Postgres database (ADR-TECH-STRAT-004 Rule 2) ────────────────────
# Per BNK.TECH.CAP.DATA.003.DB — per-L2 RDS Postgres for the operational
# anchor store. The DSN materialises into the External Secret
# `sup-002-ben-backend-db` consumed by k8s/overlay/dev/externalsecret.yaml.
module "db" {
  # source = "git::ssh://git@github.com/Banking-PapeeteConsulting/banking-tech.git//source/data/db?ref=<tech_pack_ref>"
  source = "../../../../../../../externals-template/banking-tech/data/db"

  project_name   = var.project_name
  environment    = var.environment
  tenant         = var.tenant
  capability_id  = var.capability_id
  engine         = "postgres"
  engine_version = "16"
  db_name        = "beneficiary_anchor"
  db_user        = "reliever"
  # Sized for the dev environment — the train-release process bumps these
  # for staging/prod via per-environment tfvars.
  instance_class = "db.t4g.small"
  multi_az       = false
  allocated_gb   = 20
  tags           = var.tags
}

# ── Secrets binding (broker credentials + db DSN) ───────────────────────────
# Per BNK.TECH.CAP.IDENTITY.001.SECRETS.
module "secrets_binding" {
  # source = "git::ssh://git@github.com/Banking-PapeeteConsulting/banking-tech.git//source/identity/secrets?ref=<tech_pack_ref>"
  source = "../../../../../../../externals-template/banking-tech/identity/secrets"

  project_name  = var.project_name
  environment   = var.environment
  tenant        = var.tenant
  capability_id = var.capability_id
  secret_paths = [
    "dev/reliever/sup/002/ben/backend/broker",
    "dev/reliever/sup/002/ben/backend/db",
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
