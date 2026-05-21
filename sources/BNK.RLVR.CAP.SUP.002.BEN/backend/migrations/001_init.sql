-- 001_init.sql — Foundation schema for BNK.RLVR.CAP.SUP.002.BEN (TASK-002).
--
-- Tables:
--   anchor                — write-side aggregate state (AGG.IDENTITY_ANCHOR)
--   outbox                — transactional outbox (ADR-TECH-STRAT-001 Rule 3)
--   anchor_directory      — PRJ.SUP.002.BEN.ANCHOR_DIRECTORY (read-side projection)
--   idempotency_keys      — MINT idempotency (30-day window on client_request_id)
--   outbox_relay_state    — relay offset / leader-election placeholder (single instance)
--
-- The pgcrypto / Vault-transit envelope work lands at TASK-005;
-- columns here store PII as plain text so TASK-002 stays focused on
-- the MINT + GET path. The encryption migration will alter these columns
-- (or add sibling encrypted columns) in a later migration.

BEGIN;

-- The write-side aggregate row.
CREATE TABLE IF NOT EXISTS anchor (
    internal_id                      UUID         PRIMARY KEY,
    last_name                        TEXT,
    first_name                       TEXT,
    date_of_birth                    DATE,
    contact_details                  JSONB,
    anchor_status                    TEXT         NOT NULL CHECK (anchor_status IN ('ACTIVE', 'ARCHIVED', 'PSEUDONYMISED')),
    creation_date                    DATE         NOT NULL,
    pseudonymized_at                 TIMESTAMPTZ,
    revision                         INTEGER      NOT NULL CHECK (revision >= 1),
    last_processed_command_id        UUID,
    last_processed_client_request_id UUID,
    created_at                       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at                       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- The transactional outbox. Each row is one pending RVT publication.
-- Written in the SAME transaction as the anchor row to preserve
-- atomicity (ADR-TECH-STRAT-001 Rule 3).
CREATE TABLE IF NOT EXISTS outbox (
    id              BIGSERIAL    PRIMARY KEY,
    message_id      UUID         NOT NULL UNIQUE,
    correlation_id  UUID         NOT NULL,
    causation_id    UUID,
    routing_key     TEXT         NOT NULL,
    exchange        TEXT         NOT NULL,
    payload         JSONB        NOT NULL,
    schema_id       TEXT         NOT NULL,
    schema_version  TEXT         NOT NULL,
    occurred_at     TIMESTAMPTZ  NOT NULL,
    actor           JSONB        NOT NULL,
    status          TEXT         NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'PUBLISHED', 'FAILED')),
    attempts        INTEGER      NOT NULL DEFAULT 0,
    last_error      TEXT,
    published_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_outbox_status_id ON outbox (status, id);

-- Idempotency keys — unified table covering MINT (key = client_request_id)
-- and the future lifecycle commands (key = command_id). Scope discriminates.
CREATE TABLE IF NOT EXISTS idempotency_keys (
    scope         TEXT         NOT NULL,
    key           UUID         NOT NULL,
    internal_id   UUID         NOT NULL,
    response_body JSONB        NOT NULL,
    response_code INTEGER      NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    PRIMARY KEY (scope, key)
);

CREATE INDEX IF NOT EXISTS idx_idempotency_created_at ON idempotency_keys (created_at);

-- Read-side projection PRJ.SUP.002.BEN.ANCHOR_DIRECTORY. Fed by
-- BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED with last-write-wins on revision.
CREATE TABLE IF NOT EXISTS anchor_directory (
    internal_id      UUID         PRIMARY KEY,
    last_name        TEXT,
    first_name       TEXT,
    date_of_birth    DATE,
    contact_details  JSONB,
    anchor_status    TEXT         NOT NULL CHECK (anchor_status IN ('ACTIVE', 'ARCHIVED', 'PSEUDONYMISED')),
    creation_date    DATE         NOT NULL,
    pseudonymized_at TIMESTAMPTZ,
    revision         INTEGER      NOT NULL CHECK (revision >= 1),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    etag             TEXT         NOT NULL
);

-- Outbox relay state — placeholder for a single-instance relay. A real
-- multi-instance deployment would use an advisory lock or a leader election;
-- TASK-002 keeps this minimal.
CREATE TABLE IF NOT EXISTS outbox_relay_state (
    id              INTEGER      PRIMARY KEY DEFAULT 1,
    last_polled_at  TIMESTAMPTZ,
    CHECK (id = 1)
);

INSERT INTO outbox_relay_state (id) VALUES (1) ON CONFLICT DO NOTHING;

COMMIT;
