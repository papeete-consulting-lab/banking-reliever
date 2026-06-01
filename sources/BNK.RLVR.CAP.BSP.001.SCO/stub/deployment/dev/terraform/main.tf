# BNK.RLVR.CAP.BSP.001.SCO contract+stub — Terraform root (dev).
#
# DERIVATION CHAIN (per CLAUDE.md § "Deployment contract"):
#
#   rlv-knowledge pack BNK.RLVR.CAP.BSP.001.SCO --deep
#     → tactical_stack[0].tags = [python, fastapi, postgresql, kafka,
#       rabbitmq, aws-eks, train-release, ...]
#     → BUT: this stub is Mode-B (publisher only). It does NOT yet
#       provision the postgresql / kafka / kubernetes resources that
#       the FUTURE backend will need; those land in TASK-NNN of the
#       Mode-A migration.
#
#   tech pack BNK.TECH.CAP.DATA.001.BROKER
#     → RabbitMQ lives at PLATFORM scope, not per-L2. Stub merely
#       consumes the broker URL via External Secrets (handled in k8s
#       overlay, no Terraform).
#
#   tech pack BNK.TECH.CAP.IDENTITY.001.WORKLOAD
#     → IRSA role is per-L2. The banking-tech module that codifies
#       "one IRSA role per ServiceAccount" is referenced abstractly
#       in ADR-PCM-FUNC-IDENTITY-001 but the concrete Terraform
#       module path is not surfaced by the `tech` CLI today. See
#       README.md for the escape-hatch decision.
#
# As a result, this root provisions NOTHING for the stub stage. The k8s
# overlay's ServiceAccount carries a placeholder IRSA ARN that the
# platform team fills out-of-band; once the backend lands (Mode A) and
# its real terraform needs are derived (DB, Kafka topic, blob storage),
# THIS root becomes the home of the matching banking-tech module calls.
#
# Intentionally empty — terraform plan emits "No changes."
