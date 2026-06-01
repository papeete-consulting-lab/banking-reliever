# BNK.RLVR.CAP.SUP.002.BEN — backend — Terraform versions/providers.
#
# Per CLAUDE.md § "Deployment contract / Terraform", this root calls
# banking-tech modules ONLY — no raw cloud resources. Provider blocks
# are declared empty here; the banking-tech modules configure their
# own provider requirements internally.

terraform {
  required_version = ">= 1.5.0"
  required_providers {}
}
