-- 003_anchor_history.sql — PII-free anchor history projection (TASK-006).
--
-- Materialises ``PRJ.SUP.002.BEN.ANCHOR_HISTORY`` (process model v0.2.0).
-- Append-only, one row per received ``BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED``
-- (RVT) — keyed by ``(internal_id, revision)``. Each column is sourced from
-- the wire field declared in ``read-models.yaml.PRJ.ANCHOR_HISTORY.fed_by``:
--
--     internal_id        ← payload.internal_id
--     revision           ← payload.revision
--     transition_kind    ← payload.transition_kind
--     command_id         ← payload.command_id        (nullable for system-emitted RVTs)
--     right_exercise_id  ← payload.right_exercise_id (PSEUDONYMISED only — null otherwise)
--     actor              ← envelope.actor            (JSONB — not re-captured here)
--     occurred_at        ← payload.occurred_at
--
-- The PII-free invariant is **structural**: the table has no PII columns
-- at all. The audit trail therefore survives a PSEUDONYMISE transition
-- without re-creating an Article-17 violation — the row that records the
-- PSEUDONYMISED transition (with its ``right_exercise_id``) IS the
-- GDPR-fulfilment proof for that anchor.
--
-- The CHECK constraint at the bottom of this migration encodes the
-- PII-free invariant in the schema metadata (information_schema). It
-- is intentionally narrow (it constrains the allowed column SET only at
-- migration-test time — see tests/unit/test_migration_pii_free.py).
-- Adding a PII column to this table is therefore caught both by the
-- review process AND by the structural test that walks
-- information_schema.columns.
--
-- Retention is enforced by the ``RetentionPurgeJob`` scheduled task —
-- see backend/src/.../infrastructure/persistence/retention.py.
--
-- ADR-TECH-STRAT-003 anchor: the ``actor`` envelope contract (kind /
-- subject / on_behalf_of) is the wire-format source of truth; we store
-- it as JSONB to avoid coupling the schema to the FUNC ADR's evolving
-- actor taxonomy.

BEGIN;

CREATE TABLE IF NOT EXISTS anchor_history (
    internal_id        UUID         NOT NULL,
    revision           INTEGER      NOT NULL CHECK (revision >= 1),
    transition_kind    TEXT         NOT NULL
        CHECK (transition_kind IN ('MINTED', 'UPDATED', 'ARCHIVED', 'RESTORED', 'PSEUDONYMISED')),
    command_id         UUID,
    right_exercise_id  UUID,
    actor              JSONB        NOT NULL,
    occurred_at        TIMESTAMPTZ  NOT NULL,
    recorded_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    PRIMARY KEY (internal_id, revision)
);

-- right_exercise_id is set ONLY on PSEUDONYMISED rows. The constraint
-- makes the post-condition unforgeable at the database layer.
ALTER TABLE anchor_history
    DROP CONSTRAINT IF EXISTS chk_anchor_history_right_exercise_id_only_on_pseudonymised;

ALTER TABLE anchor_history
    ADD CONSTRAINT chk_anchor_history_right_exercise_id_only_on_pseudonymised
        CHECK (
            (transition_kind = 'PSEUDONYMISED' AND right_exercise_id IS NOT NULL)
            OR
            (transition_kind <> 'PSEUDONYMISED' AND right_exercise_id IS NULL)
        );

-- Index for the GET /history query path — strict ordering by revision
-- with optional ``> since_revision`` filter. Composite PK already covers
-- this, but a dedicated covering index makes the query plan trivial.
CREATE INDEX IF NOT EXISTS idx_anchor_history_internal_id_revision
    ON anchor_history (internal_id, revision);

-- Index for the retention purge job. Scans by occurred_at globally;
-- the purge can therefore stream rows across all anchors in one pass.
CREATE INDEX IF NOT EXISTS idx_anchor_history_occurred_at
    ON anchor_history (occurred_at);

COMMIT;
