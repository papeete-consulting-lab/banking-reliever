"""Runtime JSON Schema validation.

Loads the canonical RVT.* schemas from process/BNK.RLVR.CAP.BSP.001.SCO/schemas/
at startup and exposes a `validate()` API that raises on any violation.
Per TASK-002 DoD, every emitted payload validates BEFORE publication.

The schemas live in the read-only process/ folder — they are owned by
the /process skill. We never copy them; we always read them in place.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError


# RVT identifier → schema file name (mirrors process/BNK.RLVR.CAP.BSP.001.SCO/bus.yaml).
SCHEMA_FILES: dict[str, str] = {
    "BNK.RLVR.RVT.BSP.001.ENTRY_SCORE_COMPUTED": "BNK.RLVR.RVT.BSP.001.ENTRY_SCORE_COMPUTED.schema.json",
    "BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED": "BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED.schema.json",
    "BNK.RLVR.RVT.BSP.001.SCORE_THRESHOLD_REACHED": "BNK.RLVR.RVT.BSP.001.SCORE_THRESHOLD_REACHED.schema.json",
}


@dataclass(frozen=True)
class LoadedSchema:
    rvt_id: str
    path: Path
    schema: dict[str, Any]
    validator: Draft202012Validator


class SchemaValidator:
    """Fail-fast schema loader + validator.

    The loader resolves the canonical RVT schemas under
    `process/BNK.RLVR.CAP.BSP.001.SCO/schemas/`. Missing files raise at
    construction time so the stub never starts in a broken state.
    """

    def __init__(self, schemas_dir: Path) -> None:
        self._schemas_dir = schemas_dir
        self._loaded: dict[str, LoadedSchema] = {}
        self._load_all()

    @property
    def schemas_dir(self) -> Path:
        return self._schemas_dir

    @property
    def loaded(self) -> dict[str, LoadedSchema]:
        return dict(self._loaded)

    def _load_all(self) -> None:
        if not self._schemas_dir.is_dir():
            raise FileNotFoundError(
                f"Canonical schemas dir not found: {self._schemas_dir}. "
                "The stub must read RVT.*.schema.json from "
                "process/BNK.RLVR.CAP.BSP.001.SCO/schemas/ (do not copy them)."
            )
        for rvt_id, filename in SCHEMA_FILES.items():
            path = self._schemas_dir / filename
            if not path.is_file():
                raise FileNotFoundError(
                    f"Missing canonical schema for {rvt_id}: {path}"
                )
            schema = json.loads(path.read_text(encoding="utf-8"))
            # FormatChecker enables 'uuid' and 'date-time' format assertions.
            validator = Draft202012Validator(
                schema=schema, format_checker=FormatChecker()
            )
            self._loaded[rvt_id] = LoadedSchema(
                rvt_id=rvt_id, path=path, schema=schema, validator=validator
            )

    def validate(self, rvt_id: str, payload: dict[str, Any]) -> None:
        """Validate `payload` against the schema for `rvt_id`.

        Raises ValidationError on any violation (which propagates and
        prevents publication).
        """
        if rvt_id not in self._loaded:
            raise KeyError(
                f"Unknown RVT id {rvt_id}. "
                f"Known: {sorted(self._loaded)}"
            )
        self._loaded[rvt_id].validator.validate(payload)

    def is_valid(self, rvt_id: str, payload: dict[str, Any]) -> bool:
        try:
            self.validate(rvt_id, payload)
            return True
        except ValidationError:
            return False
