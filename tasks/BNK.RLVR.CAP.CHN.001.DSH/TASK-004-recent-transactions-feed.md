---
task_id: TASK-004
capability_id: BNK.RLVR.CAP.CHN.001.DSH
bcm_ref: v1.0.0-1-gb06a4af
capability_name: Beneficiary Dashboard
epic: Epic 3 — Recent transactions feed (GET /transactions)
status: todo
priority: medium
depends_on: [TASK-003]
task_type: full-microservice
loop_count: 0
max_loops: 10
---

# TASK-004 — Recent transactions feed (GET /transactions)

## Context
This task adds the "recent activity" panel to the dashboard — a
bounded, most-recent-first list of envelope consumptions with category,
semantic merchant label, and amount, rendered in the French locale.
The aggregate already maintains the bounded `recent_transactions` list
(populated by TASK-002 via `INV.DSH.005`); this task adds the query
endpoint and the frontend rendering, both honouring the dignity rule
extension to declines: every entry that ever lands as "Refusé" carries
its reason.

The decline-reason field is **forward-compatible**: the upstream
`RVT.BSP.004.CONSUMPTION_RECORDED` does not currently carry a decline
reason (see Open Question OQ-3 in the roadmap). Epic 3 models authorised
consumptions only; the decline render path is wired but inert until the
upstream extends the RVT.

## Capability Reference
- Capability: Beneficiary Dashboard (BNK.RLVR.CAP.CHN.001.DSH)
- Zone: CHANNEL
- Governing FUNC ADR: ADR-BCM-FUNC-0009
- Strategic-tech anchors: ADR-TECH-STRAT-003 (ETag), ADR-TECH-STRAT-004
  (PII exclusion — no raw merchant name; semantic label only),
  ADR-TECH-STRAT-008
- Tactical stack: ADR-TECH-TACT-001 (.NET 10 BFF + vanilla
  HTML5/CSS3/JS frontend)

## What to Build
1. **Query handler — `QRY.LIST_RECENT_TRANSACTIONS`**: `GET
   /capabilities/chn/001/dsh/cases/{case_id}/transactions?limit=N` per
   `process/BNK.RLVR.CAP.CHN.001.DSH/api.yaml.listRecentTransactions`. Reads
   directly from the aggregate's `recent_transactions` snapshot field
   (already bounded by `INV.DSH.005`: 50 entries, 30 d, FIFO eviction
   on `recorded_at`). Returns the list most-recent-first.
   - `limit` query parameter: default 20, max 50; values > 50 are
     capped (not rejected) per the api.yaml contract.
   - ETag computed over the list; `Cache-Control: max-age=PT5S`;
     `If-None-Match` matching returns `304`.
   - `404` when no aggregate exists for `case_id`.
   - Response item shape: `transaction_id`, `envelope_id`, `category`,
     `amount`, `currency`, `merchant_label` (semantic only — never a
     raw merchant name), `recorded_at`. The `merchant_label` is the
     semantic categorisation from upstream (e.g. `GROCERY`,
     `PHARMACY`) — `INV.DSH.001` PII exclusion blocks any free-form
     merchant string from entering the aggregate or the response.
2. **Frontend rendering** — a new transactions panel appended to the
   dashboard, **below** the envelopes panel (which itself is below the
   progression panel per TASK-003's dignity rule). Each entry shows:
   - `category` (French label — translated from the semantic code via
     a local lookup table; e.g. `GROCERY` → "Alimentation")
   - `merchant_label` (semantic only, optional — rendered as a French
     label when present)
   - `amount` formatted using the French locale (`fr-FR`) with the
     currency from the entry
   - `recorded_at` formatted as a French relative time ("il y a 2
     heures") for entries within 24 h, then absolute date for older
     entries
3. **Decline-reason forward-compatibility** — the rendering code
   reads an optional `decline_reason` field from each entry. If
   present (today: never; future: when `CAP.BSP.004.ENV` extends its
   RVT or introduces `RVT.CONSUMPTION_DECLINED`), the entry is
   rendered as "Refusé" with the reason in French (e.g.
   "Enveloppe épuisée", "Catégorie non autorisée"). The decline path
   is exercised by an integration test that hand-crafts an aggregate
   state with a decline-reason entry — the live RVT never carries
   one today, but the render path is proven correct ahead of time.
4. **`INV.DSH.005` exercised end-to-end** — synthetic data drives
   100+ `RVT.CONSUMPTION_RECORDED` events for one `case_id`; the
   `GET /transactions` response never exceeds 50 entries; entries
   older than 30 d are pruned (verified by injecting a synthetic
   recorded_at in the past).
5. **OTel** — query handler traced; 304 ratio metric continues from
   TASK-003.

## Business Events to Produce
None — read-side only.

## Business Objects Involved
- `OBJ.BSP.004.ENVELOPE_CONSUMPTION` — projected (PII-free) into each
  `RecentTransactions` entry

## Event Subscriptions Required
None new — TASK-002's `POL.ON_ENVELOPE_CONSUMPTION_RECORDED` already
feeds `recent_transactions` in the aggregate.

## Definition of Done
- [ ] `GET /capabilities/chn/001/dsh/cases/{case_id}/transactions?limit=N`
      returns the bounded list per
      `process/BNK.RLVR.CAP.CHN.001.DSH/api.yaml.listRecentTransactions`
- [ ] `limit` defaults to 20, is capped at 50 (values > 50 are
      silently capped, NOT 400-rejected, per the api.yaml contract);
      response is most-recent-first by `recorded_at`
- [ ] ETag + `Cache-Control: max-age=PT5S`; `If-None-Match` matching
      returns `304`
- [ ] `404` when no aggregate exists for `case_id`
- [ ] **`INV.DSH.005` end-to-end test**: drive 100+
      `RVT.CONSUMPTION_RECORDED` events; the response never exceeds
      50 entries; entries with `recorded_at` older than 30 d are
      pruned (synthetic past timestamp injected to drive the case)
- [ ] **PII exclusion** at the response layer: `merchant_label` is a
      semantic label only (e.g. `GROCERY`, `PHARMACY`) — schema
      linter rejects any free-form-string field beyond the enumerated
      set; negative test injects a hand-crafted aggregate row with a
      raw merchant name in `merchant_label` and asserts the projector
      / response refuses to serve it
- [ ] **Frontend transactions panel** renders below the envelopes
      panel (still below the progression panel — dignity rule
      preserved); a Playwright test asserts the DOM order
      `#progression-section` → envelopes (`#restrictions-section`) →
      `#transactions-section`
- [ ] French locale on `amount` and `recorded_at` rendering;
      `category` strings translated via a local lookup table; no
      English UI string survives extraction
- [ ] **Decline-reason render path** wired but inert: the frontend
      reads an optional `decline_reason` field on each entry; a
      Playwright test injects a hand-crafted aggregate state with a
      decline-reason entry (e.g. via a BFF test endpoint or a
      mocked aggregate) and asserts the "Refusé" badge + French
      reason appear next to the amount
- [ ] Backwards-compat with TASK-003: the existing `GET /dashboard`
      endpoint is unchanged; the transactions panel is additive on
      the frontend
- [ ] OTel: query handler traced; 304 ratio metric continued
- [ ] If the TASK-001 stub is still running, its
      `GET /transactions` endpoint is now shadowed by the real one;
      decommissioning note updated
- [ ] No write to `process/BNK.RLVR.CAP.CHN.001.DSH/`

## Acceptance Criteria (Business)
A beneficiary scrolling the dashboard sees their recent envelope
consumptions in French, framed as accomplished events
("Alimentation — 24,50 €, il y a 2 heures"), never as restrictions.
The list is bounded so the screen stays readable; older entries fall
off automatically without operator intervention. No merchant name
ever appears — only the category and the semantic label the upstream
envelope engine has classified the transaction under. When the
upstream eventually carries decline reasons, the dignity rule
extension is already in place: every "Refusé" line will carry its
French-language reason next to the amount.

## Dependencies
- TASK-003 — the dashboard chrome, polling cadence, and ETag
  infrastructure are in place; this task adds a panel and a query
  endpoint to that foundation.

## Open Questions
- [ ] **OQ-3 (roadmap) — Decline-reason field in
      `RVT.CONSUMPTION_RECORDED`**. The upstream RVT does not
      currently carry a decline reason. This task ships the render
      path forward-compatibly (inert until upstream extends the
      RVT, exercised by a synthetic test). When `CAP.BSP.004.ENV`
      extends its RVT — or introduces a paired
      `RVT.CONSUMPTION_DECLINED` — revisit this task (or add an
      Epic 3.5) to wire the live decline-reason data path. Until
      then, the production system never renders a decline.
