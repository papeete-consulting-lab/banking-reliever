"""Schema validator unit tests — exercise the canonical schemas."""

from __future__ import annotations

import pytest
from jsonschema.exceptions import ValidationError

from reliever_beneficiary_anchor.infrastructure.schema_validation.loader import build_validators


def test_loads_both_schemas(schemas_dir):
    mint, rvt = build_validators(schemas_dir)
    # No exception → valid Draft 2020-12 schemas, files exist, are loadable.


def test_mint_schema_accepts_minimal_valid_payload(schemas_dir):
    mint, _ = build_validators(schemas_dir)
    mint.validate_payload({
        "client_request_id": "018f8e10-aaaa-7000-8000-000000000001",
        "last_name": "Doe",
        "first_name": "Jane",
        "date_of_birth": "1990-01-15",
    })


def test_mint_schema_rejects_caller_supplied_internal_id(schemas_dir):
    mint, _ = build_validators(schemas_dir)
    with pytest.raises(ValidationError):
        mint.validate_payload({
            "client_request_id": "018f8e10-aaaa-7000-8000-000000000001",
            "internal_id": "018f8e10-bbbb-7000-8000-000000000001",
            "last_name": "Doe",
            "first_name": "Jane",
            "date_of_birth": "1990-01-15",
        })


def test_mint_schema_rejects_missing_last_name(schemas_dir):
    mint, _ = build_validators(schemas_dir)
    with pytest.raises(ValidationError):
        mint.validate_payload({
            "client_request_id": "018f8e10-aaaa-7000-8000-000000000001",
            "first_name": "Jane",
            "date_of_birth": "1990-01-15",
        })


def test_mint_schema_rejects_non_uuidv7_client_request_id(schemas_dir):
    mint, _ = build_validators(schemas_dir)
    with pytest.raises(ValidationError):
        mint.validate_payload({
            "client_request_id": "not-a-uuid",
            "last_name": "Doe",
            "first_name": "Jane",
            "date_of_birth": "1990-01-15",
        })
