variable "project_name" {
  type        = string
  description = "Project — fixed to 'reliever' for every Reliever capability."
  default     = "reliever"
}

variable "environment" {
  type        = string
  description = "Environment slug (dev | demo | staging | prod). For this root it is fixed to 'dev'."
  default     = "dev"
}

variable "tenant" {
  type        = string
  description = "Per-client tenant slug — the per-client deployment unit from BNK.TECH.CAP.RUNTIME.001.CLUSTER."
}

variable "capability_id" {
  type        = string
  description = "The full source-context-prefixed capability id."
  default     = "BNK.RLVR.CAP.SUP.002.BEN"
}

variable "region" {
  type        = string
  description = "AWS region for the per-client cluster."
  default     = "eu-west-3"
}

locals {
  tags = {
    "reliever:capability-id" = var.capability_id
    "reliever:zone"          = "SUPPORT"
    "reliever:component"     = "stub"
    "reliever:mode"          = "contract-stub"
    "project"                = var.project_name
    "environment"            = var.environment
    "tenant"                 = var.tenant
  }
}
