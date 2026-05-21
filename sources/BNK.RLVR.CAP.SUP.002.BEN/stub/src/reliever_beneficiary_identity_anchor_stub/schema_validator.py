"""JSON Schema validation — loads schemas from process/ (read-only) and
validates every outgoing payload (bus and HTTP) before emission.

Fail-fast on contract drift: any validation error raises, the caller is
expected to abort the publish / response (or refuse to start, for fixtures).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


class SchemaValidationError(Exception):
    """Raised when a payload fails JSON Schema validation."""

    def __init__(self, schema_id: str, errors: list[str]) -> None:
        super().__init__(f"Payload violates {schema_id}: {errors}")
        self.schema_id = schema_id
        self.errors = errors


@lru_cache(maxsize=16)
def load_validator(schema_path: str) -> Draft202012Validator:
    """Load and compile a JSON Schema once; cached by absolute path."""
    p = Path(schema_path)
    if not p.is_file():
        raise FileNotFoundError(f"Schema not found: {schema_path}")
    with p.open("r", encoding="utf-8") as fh:
        schema = json.load(fh)
    return Draft202012Validator(schema)


def validate(payload: Any, schema_path: str | Path, *, schema_id: str | None = None) -> None:
    """Validate a payload against a JSON Schema; raise SchemaValidationError on failure."""
    validator = load_validator(str(schema_path))
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.absolute_path))
    if errors:
        rendered = [
            f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in errors
        ]
        raise SchemaValidationError(schema_id or str(schema_path), rendered)
