-- 002_pseudonymise.sql — GDPR Art. 17 crypto-shredding substrate (TASK-005).
--
-- Per ADR-TECH-TACT-002 the implementer chose a **per-anchor DEK** strategy:
--   - Every anchor row carries a foreign key to its own data-encryption-key
--     row in ``anchor_crypto_keys``.
--   - ``MINT_ANCHOR`` provisions the DEK alongside the anchor row in the
--     same transaction.
--   - ``PSEUDONYMISE_ANCHOR`` NULLs the four PII columns AND deletes the
--     DEK row in the same transaction. The dangling FK reference is
--     cleared (``crypto_key_id`` set to NULL on the anchor row); the DEK
--     is unrecoverable, so any at-rest ciphertext encoded under that DEK
--     is mathematically unrecoverable.
--
-- This migration adds the substrate. The wipe semantics are enforced by
-- the aggregate + the PostgresAnchorRepository (see backend/src/.../
-- infrastructure/persistence/unit_of_work.py).
--
-- Vault-transit integration is OUT OF SCOPE for the dev environment — a
-- real deployment swaps the in-postgres DEK table for a Vault transit
-- key path (see service README). The contract on the rest of the system
-- (the four PII columns become NULL, the FK becomes NULL) is unchanged.

BEGIN;

-- pgcrypto enables ``gen_random_bytes(32)`` for DEK provisioning. The
-- extension is shared across the cluster; ``CREATE EXTENSION IF NOT EXISTS``
-- is idempotent and safe to re-run.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Per-anchor data-encryption-key holder. Crypto-shredding = DELETE on this
-- row. The dek column stores the raw key material for the dev environment;
-- a real deployment encrypts each DEK under a Vault-transit master key
-- (envelope encryption) — that's a deployment concern, not a schema one.
CREATE TABLE IF NOT EXISTS anchor_crypto_keys (
    crypto_key_id  UUID         PRIMARY KEY,
    dek            BYTEA        NOT NULL,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- The anchor row gains a nullable FK reference to its DEK. NULL after
-- pseudonymisation. The ``ON DELETE SET NULL`` clause is the formal
-- declaration that deleting the DEK row severs the link — that single
-- atomic statement is what makes the at-rest ciphertext unrecoverable.
ALTER TABLE anchor
    ADD COLUMN IF NOT EXISTS crypto_key_id UUID
        REFERENCES anchor_crypto_keys(crypto_key_id) ON DELETE SET NULL;

-- For audit-friendliness: any anchor in PSEUDONYMISED status MUST have
-- its four PII fields wiped (NULL) AND its crypto_key_id severed. The
-- check is conservative — it makes the post-condition unforgeable at the
-- database layer even if a future bug skipped one of the wipes.
ALTER TABLE anchor
    DROP CONSTRAINT IF EXISTS chk_anchor_pseudonymised_pii_null;

ALTER TABLE anchor
    ADD CONSTRAINT chk_anchor_pseudonymised_pii_null
        CHECK (
            anchor_status <> 'PSEUDONYMISED'
            OR (
                last_name       IS NULL
                AND first_name  IS NULL
                AND date_of_birth IS NULL
                AND contact_details IS NULL
                AND crypto_key_id IS NULL
                AND pseudonymized_at IS NOT NULL
            )
        );

-- The projection has the same audit property; mirror the check there.
ALTER TABLE anchor_directory
    DROP CONSTRAINT IF EXISTS chk_anchor_directory_pseudonymised_pii_null;

ALTER TABLE anchor_directory
    ADD CONSTRAINT chk_anchor_directory_pseudonymised_pii_null
        CHECK (
            anchor_status <> 'PSEUDONYMISED'
            OR (
                last_name       IS NULL
                AND first_name  IS NULL
                AND date_of_birth IS NULL
                AND contact_details IS NULL
                AND pseudonymized_at IS NOT NULL
            )
        );

-- Index by deletion candidate so the relay can audit-trail purges.
CREATE INDEX IF NOT EXISTS idx_anchor_crypto_key_id ON anchor (crypto_key_id);

COMMIT;
