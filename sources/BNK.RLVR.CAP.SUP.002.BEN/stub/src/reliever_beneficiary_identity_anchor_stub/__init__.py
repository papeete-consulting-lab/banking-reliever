"""Beneficiary Identity Anchor — development stub (BNK.RLVR.CAP.SUP.002.BEN, TASK-001).

Mode B (contract + stub) per implement-capability-python.
- Publisher half: emits BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED on RabbitMQ topic
  exchange `sup.002.ben-events`, cycling all 5 transition kinds.
- Query half: serves GET /anchors/{internal_id} and
  GET /anchors/{internal_id}/history from canned fixtures.

Both halves validate every outgoing payload against the JSON Schemas owned by
/process — see ``process/BNK.RLVR.CAP.SUP.002.BEN/schemas/``.
"""

__version__ = "0.1.0"
