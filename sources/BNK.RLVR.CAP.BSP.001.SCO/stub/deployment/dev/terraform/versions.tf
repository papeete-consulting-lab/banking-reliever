# BNK.RLVR.CAP.BSP.001.SCO contract+stub — Terraform versions/providers.
#
# Minimal — the stub owns NO platform resources. Per the Deployment contract
# in CLAUDE.md ("Dev environment / Terraform"), this root only invokes
# banking-tech modules; the stub has none to invoke (see README.md). The
# providers block stays empty so `terraform init` succeeds (Terraform >=1.5
# tolerates an empty `required_providers`).

terraform {
  required_version = ">= 1.5.0"
  required_providers {}
}
