"""BNK.RLVR.CAP.BSP.001.SCO development stub.

Publishes synthetic, contract-conforming resource events on the
operational RabbitMQ rail per ADR-TECH-STRAT-001. This package is the
Mode-B (contract+stub) deliverable for TASK-002; the real microservice
will replace it in Epic 2 / Epic 3 (TASK-003 → TASK-005).
"""

__all__ = [
    "config",
    "envelope",
    "fixtures",
    "publisher",
    "schema_validator",
]

__version__ = "0.2.0"
