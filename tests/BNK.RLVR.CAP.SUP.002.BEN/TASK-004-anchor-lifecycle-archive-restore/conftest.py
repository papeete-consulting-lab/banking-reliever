"""Live-boundary fixtures for TASK-004 verification.

This corpus is INDEPENDENT of the in-tree suite under
sources/.../backend/tests/. It exercises the running FastAPI service over
HTTP (host port 9080), the RabbitMQ broker (host 9054 / mgmt 9055), and the
PostgreSQL store (host 9043) — so it can assert the criteria the in-process
suite cannot reach: actual RVT *publication* to the broker, DB-level outbox
row counts, and the PSEUDONYMISED state-machine guards (no HTTP path mints a
PSEUDONYMISED anchor in TASK-004 — that verb is TASK-005 — so the guard is
reached by seeding the store directly, which the DoD explicitly requires us
to validate behaviourally).
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

import pika
import psycopg
import pytest
import requests

LOCAL_PORT = int(os.environ.get("RELIEVER_TEST_HTTP_PORT", "9080"))
BASE = f"http://localhost:{LOCAL_PORT}"
PG_DSN = os.environ.get(
    "RELIEVER_TEST_PG_DSN",
    "postgresql://reliever:reliever@localhost:9043/beneficiary_anchor",
)
AMQP_HOST = os.environ.get("RELIEVER_TEST_AMQP_HOST", "localhost")
AMQP_PORT = int(os.environ.get("RELIEVER_TEST_AMQP_PORT", "9054"))
AMQP_USER = os.environ.get("RELIEVER_TEST_AMQP_USER", "admin")
AMQP_PASS = os.environ.get("RELIEVER_TEST_AMQP_PASS", "password")
EXCHANGE = "sup.002.ben-events"
ROUTING_KEY = (
    "BNK.RLVR.EVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED."
    "BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED"
)

# Vendored RVT schema location inside the artifact under test.
_SCHEMAS_DIR = (
    Path(__file__).resolve().parents[3]
    / "sources"
    / "BNK.RLVR.CAP.SUP.002.BEN"
    / "backend"
    / "src"
    / "reliever_beneficiary_anchor"
    / "infrastructure"
    / "schema_validation"
    / "schemas"
)


def uuidv7() -> str:
    return (
        f"018f8e10-aaaa-7{uuid.uuid4().hex[1:4]}-8{uuid.uuid4().hex[1:4]}-"
        f"{uuid.uuid4().hex[:12]}"
    )


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE


@pytest.fixture(scope="session")
def rest():
    s = requests.Session()
    yield s
    s.close()


@pytest.fixture(scope="session")
def rvt_schema() -> dict:
    return json.loads(
        (_SCHEMAS_DIR / "BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.schema.json").read_text()
    )


@pytest.fixture
def pg():
    conn = psycopg.connect(PG_DSN, autocommit=True)
    yield conn
    conn.close()


class _BusTap:
    """A temporary exclusive queue bound to the capability exchange that
    captures every RVT published while it lives."""

    def __init__(self) -> None:
        params = pika.ConnectionParameters(
            host=AMQP_HOST,
            port=AMQP_PORT,
            credentials=pika.PlainCredentials(AMQP_USER, AMQP_PASS),
        )
        self._conn = pika.BlockingConnection(params)
        self._ch = self._conn.channel()
        self._ch.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
        result = self._ch.queue_declare(queue="", exclusive=True)
        self._queue = result.method.queue
        self._ch.queue_bind(exchange=EXCHANGE, queue=self._queue, routing_key="#")

    def drain(self, want: int = 1, timeout: float = 8.0) -> list[dict]:
        msgs: list[dict] = []
        deadline = time.time() + timeout
        while time.time() < deadline and len(msgs) < want:
            method, props, body = self._ch.basic_get(self._queue, auto_ack=True)
            if method is None:
                time.sleep(0.1)
                continue
            msgs.append(
                {
                    "routing_key": method.routing_key,
                    "payload": json.loads(body),
                    "props": props,
                }
            )
        return msgs

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass


@pytest.fixture
def bus():
    tap = _BusTap()
    yield tap
    tap.close()


@pytest.fixture
def minted(rest):
    """Mint a fresh ACTIVE anchor over HTTP and return its internal_id."""
    body = {
        "client_request_id": uuidv7(),
        "last_name": "Okonkwo",
        "first_name": "Amara",
        "date_of_birth": "1990-03-11",
        "contact_details": {"email": "amara.okonkwo@example.org", "phone": "+234 800 000 0000"},
    }
    r = rest.post(f"{BASE}/anchors", json=body, timeout=10)
    assert r.status_code == 201, r.text
    return r.json()["internal_id"]
