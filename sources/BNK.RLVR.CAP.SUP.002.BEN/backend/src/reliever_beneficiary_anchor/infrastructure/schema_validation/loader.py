"""Load JSON Schemas from the package-local *vendored* snapshot.

The schemas are vendored as a static snapshot under
``reliever_beneficiary_anchor/infrastructure/schema_validation/schemas/``
(this service owns the contract snapshot it validates against). Refresh via
``rlv-knowledge process BNK.RLVR.CAP.SUP.002.BEN`` (``.schemas["<FILE>.schema.json"]``).
Fail-fast at startup if any schema is missing or malformed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator

from ...application.ports import SchemaValidator


# Resolved at startup from settings.process_schemas_dir (vendored snapshot dir).
MINT_ANCHOR_SCHEMA_FILE = "CMD.SUP.002.BEN.MINT_ANCHOR.schema.json"
UPDATE_ANCHOR_SCHEMA_FILE = "CMD.SUP.002.BEN.UPDATE_ANCHOR.schema.json"
ARCHIVE_ANCHOR_SCHEMA_FILE = "CMD.SUP.002.BEN.ARCHIVE_ANCHOR.schema.json"
RESTORE_ANCHOR_SCHEMA_FILE = "CMD.SUP.002.BEN.RESTORE_ANCHOR.schema.json"
RVT_BENEFICIARY_ANCHOR_UPDATED_SCHEMA_FILE = "BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.schema.json"


class JsonSchemaValidator(SchemaValidator):
    def __init__(self, schema: dict[str, Any]) -> None:
        # Will raise SchemaError on a malformed schema — fail-fast.
        Draft202012Validator.check_schema(schema)
        self._validator = Draft202012Validator(
            schema,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        )

    def validate_payload(self, payload: dict[str, Any]) -> None:
        self._validator.validate(payload)


def load_schema(schemas_dir: Path, filename: str) -> dict[str, Any]:
    path = schemas_dir / filename
    if not path.is_file():
        raise FileNotFoundError(
            f"Required vendored schema not found: {path}. "
            "This service validates against its package-local vendored snapshot "
            "(infrastructure/schema_validation/schemas/); refresh via "
            "`rlv-knowledge process BNK.RLVR.CAP.SUP.002.BEN`."
        )
    with path.open() as f:
        return json.load(f)


@dataclass(frozen=True, slots=True)
class Validators:
    """Bundle of validators loaded at startup. Keeps the lifespan code
    explicit about which schemas are mounted.
    """

    mint: JsonSchemaValidator
    update: JsonSchemaValidator
    archive: JsonSchemaValidator
    restore: JsonSchemaValidator
    rvt: JsonSchemaValidator


def build_validators_bundle(schemas_dir: Path) -> Validators:
    """Return the full bundle. Fail-fast on any missing or malformed schema."""
    mint = load_schema(schemas_dir, MINT_ANCHOR_SCHEMA_FILE)
    update = load_schema(schemas_dir, UPDATE_ANCHOR_SCHEMA_FILE)
    archive = load_schema(schemas_dir, ARCHIVE_ANCHOR_SCHEMA_FILE)
    restore = load_schema(schemas_dir, RESTORE_ANCHOR_SCHEMA_FILE)
    rvt = load_schema(schemas_dir, RVT_BENEFICIARY_ANCHOR_UPDATED_SCHEMA_FILE)
    return Validators(
        mint=JsonSchemaValidator(mint),
        update=JsonSchemaValidator(update),
        archive=JsonSchemaValidator(archive),
        restore=JsonSchemaValidator(restore),
        rvt=JsonSchemaValidator(rvt),
    )


def build_validators(schemas_dir: Path) -> tuple[JsonSchemaValidator, JsonSchemaValidator]:
    """Legacy 2-tuple form retained for backward compatibility with the
    TASK-002 callers / tests. Returns ``(mint_cmd_validator, rvt_validator)``.
    """
    bundle = build_validators_bundle(schemas_dir)
    return bundle.mint, bundle.rvt


__all__ = [
    "JsonSchemaValidator",
    "Validators",
    "build_validators",
    "build_validators_bundle",
    "MINT_ANCHOR_SCHEMA_FILE",
    "UPDATE_ANCHOR_SCHEMA_FILE",
    "ARCHIVE_ANCHOR_SCHEMA_FILE",
    "RESTORE_ANCHOR_SCHEMA_FILE",
    "RVT_BENEFICIARY_ANCHOR_UPDATED_SCHEMA_FILE",
]
