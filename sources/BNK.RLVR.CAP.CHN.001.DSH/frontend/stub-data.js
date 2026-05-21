/**
 * stub-data.js — Offline-fallback fixtures for BNK.RLVR.CAP.CHN.001.DSH frontend.
 *
 * Shape mirrors `PRJ.CHN.001.DSH.DASHBOARD_VIEW` declared in
 * process/BNK.RLVR.CAP.CHN.001.DSH/read-models.yaml. The frontend falls back to this
 * stub when the BFF has been unreachable / 5xx / 404 for more than
 * STUB_FALLBACK_AFTER_MS (default 30s). That keeps the shell demoable
 * during isolated dev (no upstream BFF running in the worktree) without
 * surfacing a raw error to the beneficiary.
 *
 * INV.DSH.001 (PII exclusion): zero PII fields. case_id is an opaque
 * participation identifier; tier/score/envelopes only.
 */

/**
 * Stub DashboardView shaped exactly like the BFF's 200 response body.
 * `last_synced_at` is regenerated at module load so each session shows a
 * fresh timestamp.
 */
export function buildStubDashboardView(caseId = 'CASE-STUB-0001') {
  const now = new Date();
  const iso = now.toISOString();
  const earlier = new Date(now.getTime() - 60_000).toISOString();
  return {
    case_id: caseId,
    current_tier_code: 'TIER-2',
    tier_upgraded_at: earlier,
    current_score: 380,
    score_recomputed_at: earlier,
    open_envelopes: [
      {
        envelope_id: 'ENV-STUB-001',
        category: 'GROCERY',
        allocated_amount: 300.0,
        consumed_amount: 156.5,
        available_amount: 143.5,
        currency: 'EUR',
        last_updated_at: earlier,
      },
      {
        envelope_id: 'ENV-STUB-002',
        category: 'TRANSPORT',
        allocated_amount: 120.0,
        consumed_amount: 42.0,
        available_amount: 78.0,
        currency: 'EUR',
        last_updated_at: earlier,
      },
    ],
    last_synced_at: iso,
  };
}

/**
 * Stub "empty" DashboardView — used when the test agent (or a dev) wants
 * to exercise the empty-state placeholder explicitly. All snapshot fields
 * are null per INV.DSH.006 (aggregate freshly materialised, nothing yet
 * applied).
 */
export function buildStubEmptyDashboardView(caseId = 'CASE-STUB-0001') {
  return {
    case_id: caseId,
    current_tier_code: null,
    tier_upgraded_at: null,
    current_score: null,
    score_recomputed_at: null,
    open_envelopes: [],
    last_synced_at: null,
  };
}
