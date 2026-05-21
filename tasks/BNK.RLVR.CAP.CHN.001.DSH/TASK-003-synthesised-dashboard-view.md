---
task_id: TASK-003
capability_id: BNK.RLVR.CAP.CHN.001.DSH
bcm_ref: v1.0.0-1-gb06a4af
capability_name: Beneficiary Dashboard
epic: Epic 2 — Synthesised dashboard view with dignity-compliant layout
status: todo
priority: high
depends_on: [TASK-002]
task_type: full-microservice
loop_count: 0
max_loops: 10
---

# TASK-003 — Synthesised dashboard view (GET /dashboard) with dignity-compliant layout

## Context
This is the moment the dashboard becomes useful to a beneficiary.
TASK-002 already populates the aggregate from upstream events; this
task surfaces it as a synthesised, PII-free, French-language view at
`GET /capabilities/chn/001/dsh/cases/{case_id}/dashboard`, and renders
it in the frontend with the **dignity rule** materialised as testable
DOM constraints: the progression panel (tier + score) comes **before**
the restrictions panel (envelope balances) in the DOM order, every
envelope frames consumption positively ("Vous avez utilisé X — il
vous reste Y"), and every label uses the French vocabulary defined in
the product vision.

The dignity rule is not a CSS polish but a functional constraint of
`ADR-BCM-FUNC-0009` — Playwright tests in this task encode it as
machine-checkable assertions so it cannot silently regress.

## Capability Reference
- Capability: Beneficiary Dashboard (BNK.RLVR.CAP.CHN.001.DSH)
- Zone: CHANNEL
- Governing FUNC ADR: ADR-BCM-FUNC-0009 (dignity rule)
- Strategic-tech anchors: ADR-TECH-STRAT-003 (ETag / `Cache-Control:
  max-age=PT5S`), ADR-TECH-STRAT-004 (PII exclusion), ADR-TECH-STRAT-008
- Tactical stack: ADR-TECH-TACT-001 (.NET 10 BFF + vanilla
  HTML5/CSS3/JS frontend, 5 s polling, ETag)

## What to Build
Promote the empty-state shell delivered by TASK-002 into a real,
fully-rendered synthesised view.

1. **Query handler — `QRY.GET_DASHBOARD`**: `GET /capabilities/chn/001/dsh/cases/{case_id}/dashboard`
   per `process/BNK.RLVR.CAP.CHN.001.DSH/api.yaml.getDashboard`. Reads directly
   from the aggregate's snapshot fields (no separate projection — the
   aggregate IS the projection per the Framing Decisions in the
   roadmap). Returns a `DashboardView` shape with: `current_tier_code`,
   `tier_upgraded_at`, `current_score`, `score_recomputed_at`,
   `open_envelopes` (each with `envelope_id`, `category`,
   `allocated_amount`, `consumed_amount`, `available_amount`,
   `currency`, `last_updated_at`), and `last_synced_at`. ETag computed
   over the snapshot; `Cache-Control: max-age=PT5S`. Returns `304` on
   `If-None-Match` match.
2. **Empty-state behaviour preserved** — a `case_id` whose aggregate
   has been materialised but whose tier / score / envelopes are still
   null returns `200` with null fields (NOT `404`). Only the
   not-yet-materialised case returns `404`.
3. **PII exclusion at the response layer** — `INV.DSH.001` enforced at
   the HTTP boundary: the response body never carries
   `last_name` / `first_name` / `date_of_birth` / raw `contact_details`
   (the aggregate never holds them, but a schema linter on the
   `DashboardView` shape proves it for every build).
4. **Frontend rendering** — the vanilla-JS shell from TASK-002 is
   extended to render the synthesised view:
   - `#progression-section` (current tier + score progress bar)
     **precedes** `#restrictions-section` (envelope balances) in the
     DOM order (`INV` materialised as a Playwright assertion).
   - Each envelope rendered as a positive-frame card: "Vous avez
     utilisé X € — il vous reste Y €" (NOT "Vous ne pouvez pas
     dépenser Y €" or any restriction-first wording). Currency rendered
     using the French locale (`fr-FR`).
   - Tier-upgrade animation triggers when the frontend detects
     `current_tier_code` change between two consecutive polls;
     `tier_upgraded_at` drives the animation duration.
   - On `case_id` with no aggregate yet (`404`) or with a partially-
     materialised aggregate (`200` with null fields), the frontend
     shows "Première synchronisation en cours…" — never a raw `404`.
5. **Consent gate** — the frontend exits to an explanatory view if the
   bearer JWT does not carry an active consent claim. The actual
   `CAP.SUP.001.CON` integration is out of scope; this task reads
   the consent claim from the JWT only (claim shape: see OQ-2 below).
6. **JWT actor enforcement on the BFF** — per
   `ADR-TECH-STRAT-003` bi-layer security, the BFF rejects any
   request whose JWT subject does not match the path-parameter
   `case_id`'s owner (`403 Forbidden`). The owner mapping is sourced
   from the bearer claim in this task; full enforcement against a
   real `CAP.SUP.001.CON` lookup is Epic 5's hardening (TASK-006).
7. **OpenTelemetry** — the query handler is traced; metric counters
   expose 304 ratio (target: ≥ 80% at steady state — measured in
   TASK-006 but instrumented here).

## Business Events to Produce
None — read-side only.

## Business Objects Involved
- `OBJ.BSP.002.PARTICIPATION` — projected (PII-free) into the
  `DashboardView` shape

## Event Subscriptions Required
None new — TASK-002 owns the three subscriptions.

## Definition of Done
- [ ] `GET /capabilities/chn/001/dsh/cases/{case_id}/dashboard`
      returns the `DashboardView` shape per
      `process/BNK.RLVR.CAP.CHN.001.DSH/api.yaml.getDashboard`
- [ ] ETag computed deterministically over the snapshot fields;
      `Cache-Control: max-age=PT5S`; `If-None-Match` matching returns
      `304`; `304` rate verifiable in the OTel metrics
- [ ] Empty-state contract: aggregate materialised but with null
      tier / score / envelopes returns `200` with null fields, not
      `404`; not-yet-materialised case returns `404`
- [ ] PII exclusion enforced at the HTTP layer: schema-linter
      negative test asserts the response shape declares no PII field
      (`last_name` / `first_name` / `date_of_birth` / raw
      `contact_details`); positive test with synthetic upstream RVTs
      carrying no PII confirms PII never appears in the response body
- [ ] **DOM-order Playwright assertion**: `#progression-section`
      precedes `#restrictions-section` in the rendered DOM; the test
      fails if the order is reversed (dignity rule materialised as a
      machine-checkable constraint)
- [ ] **Positive-frame envelopes**: every envelope card renders
      "Vous avez utilisé X — il vous reste Y" in French (`fr-FR`
      locale); Playwright asserts the consumed-amount string precedes
      the available-amount string in the card's DOM
- [ ] **French vocabulary**: no English UI string survives a
      string-extraction scan of the rendered frontend; the test
      corpus enforces this across the dashboard view
- [ ] **Tier-upgrade animation** triggers when
      `current_tier_code` changes between two consecutive polls;
      Playwright test drives the change and asserts the animation
      element is present
- [ ] **JWT subject check** on the BFF: a request with a JWT whose
      `sub` does not match the path-parameter `case_id` returns
      `403`; integration test exercises the case
- [ ] **Consent gate** on the frontend: a JWT without an active
      consent claim routes the user to an explanatory view (NOT the
      dashboard); the claim shape is documented inline in the
      frontend code with a TODO referencing OQ-2 below
- [ ] OTel metric exposes 304 ratio on `GET /dashboard`; trace spans
      the query handler
- [ ] If the TASK-001 stub is still running, its HTTP endpoint for
      `GET /dashboard` is now shadowed by the real one — the stub's
      decommissioning note is updated to reflect this surface being
      real
- [ ] No write to `process/BNK.RLVR.CAP.CHN.001.DSH/`

## Acceptance Criteria (Business)
A beneficiary opening the dashboard sees their current autonomy tier
and behavioural score progression first, in French, then their
envelope balances framed positively. The DOM order matches the
dignity rule of `ADR-BCM-FUNC-0009` and is asserted by automated
tests. A first-time user with no upstream events yet sees a French
"first synchronisation in progress" message, never a raw 404.
Polling at 5 s intervals returns `304` after the first call until
the aggregate actually changes. PII never reaches the rendered UI.

## Dependencies
- TASK-002 — the aggregate must be materialised and populated by the
  three policies before there is anything to synthesise.

## Open Questions
- [ ] **OQ-2 (roadmap) — Consent integration shape**. The BFF reads
      the consent claim from the JWT; the canonical authority is
      `CAP.SUP.001.CON` (Consent Management). The claim shape
      (`consent.dashboard.read = true | false | revoked`?) is not
      specified in any ADR. Coordinate with the `CAP.SUP.001.CON`
      roadmap before Epic 5 (staging ship) — document the chosen
      shape inline as a TECH-TACT delta when this task lands.
