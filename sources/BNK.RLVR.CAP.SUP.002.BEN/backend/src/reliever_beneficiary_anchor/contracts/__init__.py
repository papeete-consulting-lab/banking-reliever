"""Contract identifiers — mirror the process/BNK.RLVR.CAP.SUP.002.BEN/ contract.

The contract harness (sibling project added later by /harness-backend)
imports these constants when generating OpenAPI / AsyncAPI specs. Keep
the literals here aligned with process/ to avoid runtime drift.
"""

from __future__ import annotations

CAPABILITY_ID = "BNK.RLVR.CAP.SUP.002.BEN"

# Aggregate
AGG_IDENTITY_ANCHOR = "AGG.SUP.002.BEN.IDENTITY_ANCHOR"

# Commands (TASK-002 scope)
CMD_MINT_ANCHOR = "CMD.SUP.002.BEN.MINT_ANCHOR"

# Queries (TASK-002 scope)
QRY_GET_ANCHOR = "QRY.SUP.002.BEN.GET_ANCHOR"

# Projections (TASK-002 scope)
PRJ_ANCHOR_DIRECTORY = "PRJ.SUP.002.BEN.ANCHOR_DIRECTORY"

# Bus topology
EXCHANGE = "sup.002.ben-events"
BUSINESS_EVENT = "BNK.RLVR.EVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED"
RESOURCE_EVENT = "BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED"
ROUTING_KEY = f"{BUSINESS_EVENT}.{RESOURCE_EVENT}"

# Schemas (lookup by basename; resolution path = process/BNK.RLVR.CAP.SUP.002.BEN/schemas/)
SCHEMA_CMD_MINT_ANCHOR = "CMD.SUP.002.BEN.MINT_ANCHOR.schema.json"
SCHEMA_RVT_BENEFICIARY_ANCHOR_UPDATED = "BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.schema.json"

# Error codes (TASK-002 scope) — mirror commands.yaml.errors[].code
ERR_REQUEST_ALREADY_PROCESSED = "REQUEST_ALREADY_PROCESSED"
ERR_IDENTITY_FIELDS_MISSING = "IDENTITY_FIELDS_MISSING"
ERR_ANCHOR_NOT_FOUND = "ANCHOR_NOT_FOUND"
ERR_CALLER_SUPPLIED_INTERNAL_ID = "CALLER_SUPPLIED_INTERNAL_ID"
