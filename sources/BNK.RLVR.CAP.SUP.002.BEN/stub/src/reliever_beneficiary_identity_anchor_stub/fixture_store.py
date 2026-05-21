"""Fixture loader — loads canned BeneficiaryAnchor + AnchorHistory rows from
``fixtures/`` at startup.

The DoD requires ≥3 fixtures covering ACTIVE / ARCHIVED / PSEUDONYMISED;
they are addressable by stable UUIDv7 internal_ids defined in
``fixtures/anchors.json`` and ``fixtures/history.json``.

A weak ETag is computed from the JSON serialisation of each fixture so the
HTTP endpoints can honour the ETag/304 contract declared in
``process/BNK.RLVR.CAP.SUP.002.BEN/api.yaml``.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class FixtureNotFound(Exception):
    """Raised when a fixture for the requested internal_id is missing."""


def _etag_for(obj: Any) -> str:
    """Compute a weak ETag from a JSON-serialisable object — stable across
    Python restarts because we sort keys.
    """
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return 'W/"' + hashlib.sha256(raw).hexdigest()[:24] + '"'


class FixtureStore:
    """In-memory store of canned anchors + histories, addressable by ``internal_id``.

    Loaded once at startup; ``load`` raises if the fixture files are missing
    or malformed (fail-fast).
    """

    def __init__(self, anchors: dict[str, dict], histories: dict[str, dict]) -> None:
        self._anchors = anchors
        self._histories = histories
        self._anchor_etags = {k: _etag_for(v) for k, v in anchors.items()}
        self._history_etags = {k: _etag_for(v) for k, v in histories.items()}

    @classmethod
    def load(cls, fixtures_dir: Path) -> "FixtureStore":
        anchors_path = fixtures_dir / "anchors.json"
        histories_path = fixtures_dir / "history.json"
        if not anchors_path.is_file():
            raise FileNotFoundError(f"Missing fixture file: {anchors_path}")
        if not histories_path.is_file():
            raise FileNotFoundError(f"Missing fixture file: {histories_path}")
        with anchors_path.open("r", encoding="utf-8") as fh:
            anchors_raw = json.load(fh)
        with histories_path.open("r", encoding="utf-8") as fh:
            histories_raw = json.load(fh)

        anchors = {a["internal_id"]: a for a in anchors_raw.get("anchors", [])}
        histories = histories_raw.get("histories", {})

        if len(anchors) < 3:
            raise ValueError(f"DoD requires ≥3 anchor fixtures; found {len(anchors)}.")

        statuses = {a["anchor_status"] for a in anchors.values()}
        for required in ("ACTIVE", "ARCHIVED", "PSEUDONYMISED"):
            if required not in statuses:
                raise ValueError(
                    f"DoD requires a fixture in status {required}; statuses found: {sorted(statuses)}"
                )

        return cls(anchors=anchors, histories=histories)

    # ── lookups ────────────────────────────────────────────────────
    def has_anchor(self, internal_id: str) -> bool:
        return internal_id in self._anchors

    def get_anchor(self, internal_id: str) -> dict[str, Any]:
        try:
            return self._anchors[internal_id]
        except KeyError as exc:
            raise FixtureNotFound(internal_id) from exc

    def anchor_etag(self, internal_id: str) -> str:
        return self._anchor_etags[internal_id]

    def get_history(self, internal_id: str, since_revision: int | None = None) -> dict[str, Any]:
        if internal_id not in self._histories:
            raise FixtureNotFound(internal_id)
        history = self._histories[internal_id]
        if since_revision is None or since_revision <= 0:
            return history
        # Filter rows whose revision > since_revision; recompute ETag-less view.
        rows = [r for r in history["rows"] if r["revision"] > since_revision]
        return {"internal_id": history["internal_id"], "rows": rows}

    def history_etag(self, internal_id: str, since_revision: int | None = None) -> str:
        if since_revision is None or since_revision <= 0:
            return self._history_etags[internal_id]
        return _etag_for(self.get_history(internal_id, since_revision))

    # ── enumeration (test helpers) ────────────────────────────────
    def anchor_ids(self) -> list[str]:
        return list(self._anchors.keys())

    def anchors_by_status(self, status: str) -> list[dict[str, Any]]:
        return [a for a in self._anchors.values() if a["anchor_status"] == status]
