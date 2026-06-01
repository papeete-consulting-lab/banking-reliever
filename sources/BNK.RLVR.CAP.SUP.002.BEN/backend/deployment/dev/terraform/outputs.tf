# BNK.RLVR.CAP.SUP.002.BEN — backend — Terraform outputs.

output "irsa_role_arn" {
  description = "IAM role ARN for the IRSA-bound ServiceAccount."
  value       = try(module.workload_identity.role_arn, null)
}

output "db_endpoint" {
  description = "RDS Postgres endpoint (host:port) — sourced via External Secret in dev."
  value       = try(module.db.endpoint, null)
}

output "api_ingress_url" {
  description = "Public URL contract per ADR-TECH-STRAT-003."
  value       = try(module.api_ingress.url, null)
}
