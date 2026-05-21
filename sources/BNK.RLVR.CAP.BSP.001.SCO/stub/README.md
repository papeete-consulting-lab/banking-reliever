# BNK.RLVR.CAP.BSP.001.SCO — Development Stub (Python)

A minimal Python 3.12+ worker that publishes synthetic, contract-conforming
**resource events** for the Behavioural Scoring capability on the operational
RabbitMQ rail. Aligned with `ADR-TECH-TACT-003` (Python + RabbitMQ
operational rail).

This package is the **Mode-B (contract + stub)** deliverable for
`TASK-002` of `BNK.RLVR.CAP.BSP.001.SCO`. The TASK-001 .NET prototype has been
**retired in favour of this Python implementation** so that Epic 2 / Epic 3
do not have to re-platform mid-flight.

> Not the real microservice. The real capability ships when Epic 2 of
> `BNK.RLVR.CAP.BSP.001.SCO`'s roadmap delivers the scoring algorithm under
> `sources/BNK.RLVR.CAP.BSP.001.SCO/backend/`.

## What this stub publishes

Per `process/BNK.RLVR.CAP.BSP.001.SCO/bus.yaml` (v0.2.0), three RVT.* families are
emitted on the topic exchange `bsp.001.sco-events` (owned by
`BNK.RLVR.CAP.BSP.001.SCO`, durable, declared idempotently at startup):

| RVT identifier | Routing key | Schema (read-only, owned by `/process`) |
|---|---|---|
| `BNK.RLVR.RVT.BSP.001.ENTRY_SCORE_COMPUTED`     | `BNK.RLVR.EVT.BSP.001.SCORE_RECOMPUTED.BNK.RLVR.RVT.BSP.001.ENTRY_SCORE_COMPUTED`         | `process/BNK.RLVR.CAP.BSP.001.SCO/schemas/BNK.RLVR.RVT.BSP.001.ENTRY_SCORE_COMPUTED.schema.json` |
| `BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED` | `BNK.RLVR.EVT.BSP.001.SCORE_RECOMPUTED.BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED`     | `process/BNK.RLVR.CAP.BSP.001.SCO/schemas/BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED.schema.json` |
| `BNK.RLVR.RVT.BSP.001.SCORE_THRESHOLD_REACHED`  | `BNK.RLVR.EVT.BSP.001.SCORE_THRESHOLD_REACHED.BNK.RLVR.RVT.BSP.001.SCORE_THRESHOLD_REACHED` | `process/BNK.RLVR.CAP.BSP.001.SCO/schemas/BNK.RLVR.RVT.BSP.001.SCORE_THRESHOLD_REACHED.schema.json` |

**The schemas are read in place from `process/BNK.RLVR.CAP.BSP.001.SCO/schemas/` at
startup.** They are never copied into this folder — that contract is owned by
the `/process` skill and would drift on duplication.

## Bus topology — ADR-TECH-STRAT-001 compliance

| Property | Value | ADR rule |
|---|---|---|
| Broker | RabbitMQ (operational rail) | Rule 1 |
| Exchange (topic) | `bsp.001.sco-events` (owned by `BNK.RLVR.CAP.BSP.001.SCO`) | Rules 1, 5 |
| Routing key | `{BusinessEventName}.{ResourceEventName}` (three pairs above) | Rule 4 |
| Wire-level events | `RVT.*` only — no autonomous `EVT.*` message | Rule 2 |
| Payload form | Domain event DDD (transition data; not a snapshot, not a field patch) | Rule 3 |
| Schema source of truth | BCM → process model; runtime JSON Schema validates each payload | Rule 6 |
| Envelope ID kind | UUIDv7 (`message_id`, `correlation_id`, `causation_id`) | ADR-TECH-STRAT-007 Rule 4 |

### Atomicity (INV.SCO.003)

Whenever a synthetic recomputation crosses a tier threshold,
`BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED` and
`BNK.RLVR.RVT.BSP.001.SCORE_THRESHOLD_REACHED` are published in the **same emission
batch** and share:

- the same `evaluation_id`
- the same `case_id`
- the same `computation_timestamp`
- the same `trigger.event_id` (and therefore the same envelope `causation_id`)

This is exercised by `tests/test_atomicity.py` end-to-end (fixture builder
+ publisher with a mocked exchange).

## Run locally

```bash
# 1) RabbitMQ
docker compose up -d                               # ports 47656 / 47657

# 2) Install the stub (editable install — preferred for dev)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .                                   # exposes the bsp-sco-stub CLI

# 3) Run with publication ENABLED
STUB_ACTIVE=true python -m bsp_sco_stub
```

| Service | Local URL |
|---|---|
| RabbitMQ AMQP | `amqp://guest:guest@localhost:47656/` |
| RabbitMQ Management UI | http://localhost:47657 (guest / guest) |

To observe published messages, in the management UI bind a queue to
exchange `bsp.001.sco-events` with routing key `BNK.RLVR.EVT.BSP.001.SCORE_RECOMPUTED.#`
(catches ENTRY + CURRENT) or `BNK.RLVR.EVT.BSP.001.SCORE_THRESHOLD_REACHED.#`
(catches threshold crossings).

## Configuration — environment variables

| Env var | Default | Purpose |
|---|---|---|
| `STUB_ACTIVE` | `false` | Master switch. The exchange is still declared, but no events are published. **Inactive in production.** |
| `STUB_CADENCE_PER_MIN` | `6` | Combined cadence across all RVTs. Allowed range `[1, 10]`. |
| `STUB_CADENCE_OUT_OF_RANGE` | `false` | Set `true` to allow values outside `[1, 10]` — justify in deployment notes. |
| `STUB_THRESHOLD_PROBABILITY` | `0.1` | Probability that a recomputation also emits a threshold event when no natural crossing happened. Allowed range `[0, 1]`. |
| `STUB_ENTRY_RATIO` | `0.1` | Probability that an active tick prefers to emit an ENTRY for a still-baseline-less case rather than a recomputation. |
| `STUB_CASE_POOL_SIZE` | `8` | Number of synthetic UUIDv7 `case_id`s rotated through. |
| `STUB_MODEL_VERSION` | `0.2.0` | `model_version` written into every payload. Must be semver. |
| `STUB_SCHEMA_VERSION` | `0.2.0` | `envelope.schema_version` written into every payload. Must be semver. |
| `STUB_EXCHANGE_NAME` | `bsp.001.sco-events` | Owned topic exchange — override only for testing. |
| `STUB_SCHEMAS_DIR` | _(resolved relative to repo root)_ | Override location of canonical schemas (CI / container scenarios). |
| `STUB_LOG_LEVEL` | `INFO` | Python logging level. |
| `RABBITMQ_URL` | `amqp://guest:guest@localhost:47656/` | Broker URL. |

## Tests — offline, no broker

```bash
pip install -r requirements-test.txt
pytest -v
```

The suite (24 tests across four files) covers:

- **`test_payload_validation.py`** — 200 randomised payloads per RVT
  validate against the canonical schema in `process/.../schemas/`;
  deliberately corrupted payloads are correctly rejected.
- **`test_atomicity.py`** — INV.SCO.003 holds at the fixture level
  (paired emissions share `evaluation_id`, `trigger.event_id`,
  `computation_timestamp`) and at the publisher level (a recording
  stand-in exchange asserts the pair ships in one `publish_emissions`
  call). Schema rejection prevents publication.
- **`test_envelope.py`** — UUIDv7 helper produces RFC 9562-conformant
  identifiers; every emitted envelope carries the trio with the right
  semantic ties (`correlation_id == case_id`, `causation_id == trigger
  event_id`).
- **`test_config.py`** — env-var parsing, default safety, out-of-range
  guard, override flag.

`aio-pika` is NOT required to run the tests — the publisher's AMQP
import is lazy.

## Layout

```
sources/BNK.RLVR.CAP.BSP.001.SCO/stub/
├── README.md                       ← you are here
├── pyproject.toml                  ← package + pytest config
├── requirements.txt                ← runtime pins
├── requirements-test.txt           ← test pins
├── docker-compose.yml              ← RabbitMQ only (ports 47656 / 47657)
├── .gitignore
├── src/bsp_sco_stub/
│   ├── __init__.py
│   ├── __main__.py                 ← `python -m bsp_sco_stub` entry point
│   ├── config.py                   ← env-var loader + tier-threshold table
│   ├── envelope.py                 ← UUIDv7 + envelope builder
│   ├── schema_validator.py         ← loads RVT.* schemas from process/…
│   ├── fixtures.py                 ← synthetic payload factories + atomicity
│   └── publisher.py                ← aio-pika publisher (lazy import)
└── tests/
    ├── conftest.py
    ├── test_payload_validation.py
    ├── test_atomicity.py
    ├── test_envelope.py
    └── test_config.py
```

## Retirement plan

| Event | Retiring TASK | Epic |
|---|---|---|
| `BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED` | `TASK-003` | Epic 2 |
| `BNK.RLVR.RVT.BSP.001.SCORE_THRESHOLD_REACHED`  | `TASK-003` | Epic 2 |
| `BNK.RLVR.RVT.BSP.001.ENTRY_SCORE_COMPUTED`     | `TASK-004` | Epic 3 |

Once the real microservice (`sources/BNK.RLVR.CAP.BSP.001.SCO/backend/`) publishes a
given RVT family from its own aggregate, the corresponding emitter in this
stub is removed. The exchange / routing-key contract is preserved across
the transition so consumers (BNK.RLVR.CAP.BSP.001.ARB, BNK.RLVR.CAP.BSP.001.TIE,
BNK.RLVR.CAP.CHN.001.DSH, CAP.CHN.002.VUE) need no code change.

## Notes on the .NET → Python rewrite

`TASK-001` shipped the same contract from a .NET 10 worker stub. That
prototype was retired before merge: `ADR-TECH-TACT-003` mandates Python
for this capability, and rewriting at this scaffold stage is cheaper than
re-platforming when Epic 2 starts. The external bus contract
(exchange name, routing keys, payload schemas) is byte-for-byte
identical to what TASK-001 delivered, so any consumer already wired
against the prior stub continues to work.
