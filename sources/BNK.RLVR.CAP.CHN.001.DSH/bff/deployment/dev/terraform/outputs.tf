output "service_account_role_arn" {
  description = "IAM role ARN bound to the k8s ServiceAccount via IRSA."
  value       = module.workload_identity.role_arn
}

output "ingress_hostname" {
  description = "ALB hostname for the BFF (per ADR-TECH-STRAT-003 URL contract)."
  value       = module.api_ingress.hostname
}

output "ingress_url" {
  description = "Full URL contract path for this capability's API."
  value       = "https://${module.api_ingress.hostname}/${var.environment}/${var.capability_id}/api/"
}
