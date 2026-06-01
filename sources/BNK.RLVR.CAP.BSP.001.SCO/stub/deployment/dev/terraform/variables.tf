# BNK.RLVR.CAP.BSP.001.SCO contract+stub — Terraform inputs.
#
# Per the Deployment contract: every root accepts the same canonical inputs
# so the CI can call them uniformly:
#   project_name | environment | tenant | tags

variable "project_name" {
  description = "Capability identifier used as the Terraform project key."
  type        = string
  default     = "bnk-rlvr-cap-bsp-001-sco-stub"
}

variable "environment" {
  description = "Target environment slug (dev|staging|prod)."
  type        = string
  default     = "dev"
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "tenant" {
  description = "Per-client cluster tenant slug (per ADR-TECH-STRAT-006)."
  type        = string
  default     = "reliever-dev"
}

variable "tags" {
  description = "Common tags applied to every resource (when there is one)."
  type        = map(string)
  default = {
    "bnk.bcm/capability-id" = "BNK.RLVR.CAP.BSP.001.SCO"
    "bnk.bcm/component"     = "stub"
    "bnk.bcm/component-kind" = "api"
    "bnk.bcm/zone"          = "BUSINESS_SERVICE_PRODUCTION"
    "bnk.bcm/owner"         = "Behavioural Scoring Pizza Team"
  }
}
