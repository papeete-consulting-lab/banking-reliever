# BNK.RLVR.CAP.SUP.002.BEN — backend — Terraform inputs.
#
# Canonical inputs every per-component Terraform root accepts so CI can
# call them uniformly.

variable "project_name" {
  description = "Capability identifier used as the Terraform project key."
  type        = string
  default     = "bnk-rlvr-cap-sup-002-ben-backend"
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

variable "capability_id" {
  description = "Source-context-prefixed capability identifier."
  type        = string
  default     = "BNK.RLVR.CAP.SUP.002.BEN"
}

variable "tags" {
  description = "Common tags applied to every resource."
  type        = map(string)
  default = {
    "reliever.bcm/capability-id"   = "BNK.RLVR.CAP.SUP.002.BEN"
    "reliever.bcm/component"       = "backend"
    "reliever.bcm/component-kind"  = "api"
    "reliever.bcm/zone"            = "SUPPORT"
    "reliever.bcm/owner"           = "IT Security / Identity & DPO"
  }
}
