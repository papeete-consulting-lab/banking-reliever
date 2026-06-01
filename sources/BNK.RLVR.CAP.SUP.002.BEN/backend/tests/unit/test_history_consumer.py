"""Unit tests for the dual-write projection consumer (TASK-006).

Validates that:

  1. The consumer extracts the seven contracted fields (per
     read-models.yaml.PRJ.ANCHOR_HISTORY.fed_by) from the wire payload —
     six from ``payload``, ``actor`` from ``envelope``.
  2. PII fields present on a hand-crafted RVT NEVER reach the history
     writer — verifiable by inspecting the dict passed to ``append``.
  3. The PSEUDONYMISED branch propagates ``right_exercise_id``; the
     other transitions leave it None.
  4. Duplicate delivery (same internal_id + revision) is idempotent —
     the in-memory fake writer returns ``False`` on the second call and
     the consumer surfaces it via the structured log line, but does not
     crash.
  5. Missing ``envelope.actor`` is a contract violation (raises) —
     defensive against upstream bus-topology drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone

import pytest

from reliever_beneficiary_anchor.infrastructure.messaging.projection_consumer import (
    ProjectionConsumer,
)


@dataclass
class _DirectoryWriterFake:
    upserts: list[dict] = field(default_factory=list)

    async def upsert(self, projection_row: dict) -> bool:  # AnchorDirectoryWriter
        self.upserts.append(projection_row)
        return True


@dataclass
class _HistoryWriterFake:
    appends: list[dict] = field(default_factory=list)
    seen: set[tuple[str, int]] = field(default_factory=set)

    async def append(self, row: dict) -> bool:  # AnchorHistoryWriter
        self.appends.append(row)
        key = (row["internal_id"], row["revision"])
        if key in self.seen:
            return False
        self.seen.add(key)
        return True


class _ValidatorPassthrough:
    def validate_payload(self, payload: dict) -> None:
        return None


def _consumer(directory: _DirectoryWriterFake, history: _HistoryWriterFake) -> ProjectionConsumer:
    return ProjectionConsumer(
        connection=None,  # type: ignore[arg-type]  — _apply does not touch the connection
        exchange_name="sup.002.ben-events",
        routing_key="BNK.RLVR.EVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED",
        queue_name="sup.002.ben.anchor-directory",
        writer=directory,
        history_writer=history,
        validator=_ValidatorPassthrough(),
    )


def _minted_rvt(*, internal_id: str, revision: int) -> dict:
    """A canonical wire-format MINTED RVT — envelope + payload."""
    return {
        "envelope": {
            "message_id": "018f8e10-aaaa-7000-8000-000000000001",
            "schema_version": "0.1.0",
            "emitted_at": "2026-06-01T12:00:00+00:00",
            "emitting_capability": "BNK.RLVR.CAP.SUP.002.BEN",
            "correlation_id": internal_id,
            "causation_id": "018f8e10-cccc-7000-8000-000000000001",
            "actor": {
                "kind": "human",
                "subject": "018f8e10-2222-7000-8000-000000000001",
            },
        },
        "internal_id": internal_id,
        "last_name": "Dupont",
        "first_name": "Jean",
        "date_of_birth": "1980-01-01",
        "contact_details": {"email": "jean@example.com"},
        "anchor_status": "ACTIVE",
        "creation_date": "2026-06-01",
        "pseudonymized_at": None,
        "revision": revision,
        "transition_kind": "MINTED",
        "command_id": "018f8e10-cccc-7000-8000-000000000001",
        "right_exercise_id": None,
        "occurred_at": "2026-06-01T12:00:00+00:00",
    }


def _pseudonymised_rvt(*, internal_id: str, revision: int) -> dict:
    return {
        "envelope": {
            "message_id": "018f8e10-bbbb-7000-8000-000000000001",
            "schema_version": "0.1.0",
            "emitted_at": "2026-06-01T14:00:00+00:00",
            "emitting_capability": "BNK.RLVR.CAP.SUP.002.BEN",
            "correlation_id": internal_id,
            "causation_id": "018f8e10-dddd-7000-8000-000000000001",
            "actor": {
                "kind": "human",
                "subject": "018f8e10-3333-7000-8000-000000000001",
                "on_behalf_of": "018f8e10-4444-7000-8000-000000000001",
            },
        },
        "internal_id": internal_id,
        "last_name": None,
        "first_name": None,
        "date_of_birth": None,
        "contact_details": None,
        "anchor_status": "PSEUDONYMISED",
        "creation_date": "2026-06-01",
        "pseudonymized_at": "2026-06-01T14:00:00+00:00",
        "revision": revision,
        "transition_kind": "PSEUDONYMISED",
        "command_id": "018f8e10-dddd-7000-8000-000000000001",
        "right_exercise_id": "018f8e10-eeee-7000-8000-000000000001",
        "occurred_at": "2026-06-01T14:00:00+00:00",
    }


# ─── tests ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_history_writer_receives_only_seven_contracted_fields() -> None:
    """PII fields present in the RVT payload MUST NOT reach the history
    writer — verifies the PII-free invariant at the projection-extraction
    layer.
    """
    directory = _DirectoryWriterFake()
    history = _HistoryWriterFake()
    consumer = _consumer(directory, history)

    payload = _minted_rvt(internal_id="018f8e10-9999-7000-8000-000000000001", revision=1)
    await consumer._apply(payload)

    assert len(history.appends) == 1
    row = history.appends[0]
    # Exactly the seven contracted keys — no PII.
    assert set(row.keys()) == {
        "internal_id",
        "revision",
        "transition_kind",
        "command_id",
        "right_exercise_id",
        "actor",
        "occurred_at",
    }
    assert "last_name" not in row
    assert "first_name" not in row
    assert "date_of_birth" not in row
    assert "contact_details" not in row


@pytest.mark.asyncio
async def test_actor_sourced_from_envelope_not_payload() -> None:
    directory = _DirectoryWriterFake()
    history = _HistoryWriterFake()
    consumer = _consumer(directory, history)
    payload = _minted_rvt(internal_id="018f8e10-9999-7000-8000-000000000002", revision=1)
    await consumer._apply(payload)
    assert history.appends[0]["actor"] == {
        "kind": "human",
        "subject": "018f8e10-2222-7000-8000-000000000001",
    }


@pytest.mark.asyncio
async def test_pseudonymised_branch_propagates_right_exercise_id() -> None:
    directory = _DirectoryWriterFake()
    history = _HistoryWriterFake()
    consumer = _consumer(directory, history)
    payload = _pseudonymised_rvt(
        internal_id="018f8e10-9999-7000-8000-000000000003", revision=5
    )
    await consumer._apply(payload)
    assert history.appends[0]["transition_kind"] == "PSEUDONYMISED"
    assert history.appends[0]["right_exercise_id"] == (
        "018f8e10-eeee-7000-8000-000000000001"
    )


@pytest.mark.asyncio
async def test_minted_branch_has_null_right_exercise_id() -> None:
    directory = _DirectoryWriterFake()
    history = _HistoryWriterFake()
    consumer = _consumer(directory, history)
    payload = _minted_rvt(internal_id="018f8e10-9999-7000-8000-000000000004", revision=1)
    await consumer._apply(payload)
    assert history.appends[0]["right_exercise_id"] is None


@pytest.mark.asyncio
async def test_duplicate_delivery_is_idempotent_on_composite_key() -> None:
    """At-least-once delivery: applying the same RVT twice MUST yield one
    history row (the fake writer signals the conflict via False).
    """
    directory = _DirectoryWriterFake()
    history = _HistoryWriterFake()
    consumer = _consumer(directory, history)

    iid = "018f8e10-9999-7000-8000-000000000005"
    payload = _minted_rvt(internal_id=iid, revision=1)
    res1 = await consumer._apply(payload)
    res2 = await consumer._apply(payload)
    assert res1["history"] is True
    assert res2["history"] is False
    # Both writes were attempted (the fake records every call) — but only
    # one entry made it into the dedupe set.
    assert len(history.appends) == 2
    assert history.seen == {(iid, 1)}


@pytest.mark.asyncio
async def test_missing_envelope_actor_is_a_contract_violation() -> None:
    directory = _DirectoryWriterFake()
    history = _HistoryWriterFake()
    consumer = _consumer(directory, history)
    payload = _minted_rvt(internal_id="018f8e10-9999-7000-8000-000000000006", revision=1)
    payload["envelope"]["actor"] = None
    with pytest.raises(ValueError, match="envelope.actor"):
        await consumer._apply(payload)


@pytest.mark.asyncio
async def test_occurred_at_is_a_datetime_in_history_row() -> None:
    directory = _DirectoryWriterFake()
    history = _HistoryWriterFake()
    consumer = _consumer(directory, history)
    payload = _minted_rvt(internal_id="018f8e10-9999-7000-8000-000000000007", revision=1)
    await consumer._apply(payload)
    occ = history.appends[0]["occurred_at"]
    assert isinstance(occ, datetime)
    assert occ.tzinfo is not None  # timezone-aware
