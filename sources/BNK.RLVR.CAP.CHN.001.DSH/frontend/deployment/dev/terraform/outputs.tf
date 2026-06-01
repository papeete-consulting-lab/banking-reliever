output "service_account_role_arn" {
  description = "IAM role ARN bound to the k8s ServiceAccount via IRSA."
  value       = module.workload_identity.role_arn
}

output "ingress_hostname" {
  description = "ALB hostname for the SPA (per ADR-TECH-STRAT-003 URL contract)."
  value       = module.api_ingress.hostname
}

output "spa_root_url" {
  description = "Full URL contract path for this capability's SPA root (in-cluster nginx variant)."
  value       = "https://${module.api_ingress.hostname}/${var.environment}/${var.capability_id}/"
}

output "static_hosting_cdn_url" {
  description = "Full CloudFront URL of the static bundle (per ADR-TECH-STRAT-003 static_hosting variant)."
  value       = module.static_hosting.cdn_url
}
