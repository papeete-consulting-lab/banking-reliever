variable "project_name" {
  type        = string
  description = "Reliever project tag (carried into every resource tag set)."
  default     = "reliever"
}

variable "environment" {
  type        = string
  description = "Deployment environment slug (matches the namespace suffix in dev/k8s/overlay/dev/)."
  default     = "dev"
}

variable "tenant" {
  type        = string
  description = "Institutional client slug — ADR-TECH-STRAT-002 mandates per-client clusters."
}

variable "capability_id" {
  type    = string
  default = "BNK.RLVR.CAP.CHN.001.DSH"
}

variable "component_kind" {
  type    = string
  default = "bff"
}

variable "tags" {
  type = map(string)
  default = {
    "reliever.io/capability-id" = "BNK.RLVR.CAP.CHN.001.DSH"
    "reliever.io/zone"          = "CHANNEL"
    "reliever.io/kind"          = "bff"
    "reliever.io/managed-by"    = "deployment-contract"
  }
}
