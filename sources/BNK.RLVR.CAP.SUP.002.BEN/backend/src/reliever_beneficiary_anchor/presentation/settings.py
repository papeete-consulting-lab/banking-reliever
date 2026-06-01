"""Runtime configuration — Pydantic settings sourced from env vars.

Env prefix: ``RELIEVER_``.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Path math:
#   settings.py = .../backend/src/reliever_beneficiary_anchor/presentation/settings.py
#   parents[0]=presentation parents[1]=reliever_beneficiary_anchor parents[2]=src
# JSON Schemas are a package-local *vendored* snapshot of the upstream contract
# (this service owns the snapshot it validates against). Refresh via
# `rlv-knowledge process BNK.RLVR.CAP.SUP.002.BEN` (`.schemas["<FILE>.schema.json"]`).
_PKG_ROOT = Path(__file__).resolve().parents[1]  # reliever_beneficiary_anchor/
_DEFAULT_SCHEMAS_DIR = (
    _PKG_ROOT / "infrastructure" / "schema_validation" / "schemas"
)
# Migrations live under .../backend/migrations.
_DEFAULT_MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RELIEVER_",
        case_sensitive=False,
        extra="ignore",
    )

    # HTTP
    http_host: str = "0.0.0.0"
    http_port: int = 8000

    # PostgreSQL
    pg_dsn: str = Field(
        default="postgresql://reliever:reliever@postgres:5432/beneficiary_anchor",
        description="Postgres DSN — psycopg-compatible.",
    )
    pg_min_pool: int = 1
    pg_max_pool: int = 10

    # RabbitMQ
    amqp_url: str = "amqp://admin:password@rabbitmq:5672/"
    exchange_name: str = "sup.002.ben-events"

    # Projection consumer
    projection_queue: str = "sup.002.ben.anchor-directory"
    routing_key: str = "BNK.RLVR.EVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED"

    # Outbox relay
    outbox_poll_interval_seconds: float = 0.5
    outbox_batch_size: int = 50

    # Schema / migrations location
    process_schemas_dir: Path = Field(default=_DEFAULT_SCHEMAS_DIR)
    migrations_dir: Path = Field(default=_DEFAULT_MIGRATIONS_DIR)

    # Anchor-history retention (TASK-006) — GDPR + AML 7-year floor.
    # Default = 2557 days (7 * 365 + 2 leap days), matching the
    # read-models.yaml retention contract.
    history_retention_days: int = 2557
    history_retention_purge_interval_seconds: float = 3600.0  # hourly

    # Toggles — useful for tests and remote-development deployments.
    run_outbox_relay: bool = True
    run_projection_consumer: bool = True
    run_retention_purge: bool = True
    run_migrations_on_startup: bool = True
