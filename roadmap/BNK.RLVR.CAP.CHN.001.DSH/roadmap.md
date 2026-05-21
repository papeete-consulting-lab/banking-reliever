# Roadmap — Beneficiary Dashboard (BNK.RLVR.CAP.CHN.001.DSH)

## Capability Summary

> Expose to the beneficiary a synthetic view of their financial situation adapted to their tier — available balance per envelope, current autonomy tier, recent transactions, and a gamified progression bar. The interface is calibrated to encourage without patronising: **dignity is a functional constraint** (`ADR-BCM-FUNC-0009`).

CHANNEL-zone capability — implemented as a **.NET 10 Backend-For-Frontend** plus a **vanilla HTML5 / CSS3 / JS mobile frontend** per `ADR-TECH-TACT-001`. Owns one aggregate (`AGG.BENEFICIARY_DASHBOARD`, one instance per `case_id`), four commands (1 HTTP-issued telemetry + 3 policy-issued sync commands), three reactive policies (one per upstream subscription), two PII-free projections, and two cached read endpoints. Emits exactly one event family (`BNK.RLVR.EVT.CHN.001.DASHBOARD_VIEWED`, scope: `internal`) which feeds engagement analytics on the analytical rail.

## Strategic Alignment

- **Service offer**: financially vulnerable beneficiaries regain progressive control of their daily financial lives through the autonomy-tier loop; the dashboard is the daily touch-point that makes that progression visible and dignified.
- **L1 strategic capability**: `CAP.CHN.001` — *Beneficiary Journey* (the L1 also covers purchase assistance `BNK.RLVR.CAP.CHN.001.PUR` and beneficiary notifications `BNK.RLVR.CAP.CHN.001.NOT`; the dashboard is the entry point of the journey).
- **BCM Zone**: `CHANNEL`.
- **Governing FUNC ADR**: `ADR-BCM-FUNC-0009` — *L2 Breakdown of CAP.CHN.001*.
- **Strategic-tech anchors**:
  - `ADR-TECH-STRAT-001` — Dual-rail event infrastructure (operational rail = RabbitMQ; the dashboard subscribes here. Analytical rail = Kafka, downstream of the BFF outbox via CDC for `BNK.RLVR.RVT.CHN.001.DASHBOARD_VIEWED`).
  - `ADR-TECH-STRAT-002` — Modular monolith per zone.
  - `ADR-TECH-STRAT-003` — REST/HTTP, **BFF per channel**, JWT-borne actor on every request, ETag on every query.
  - `ADR-TECH-STRAT-004` — PII governance — the dashboard is in the *low-PII* lane: it never stores names, addresses, raw merchant names; only semantic labels (`merchant_label = GROCERY`, etc.).
  - `ADR-TECH-STRAT-005` — Observability via OpenTelemetry, L2 as the primary unit (`environment` tag carries the branch slug per the worktree-isolation rule).
  - `ADR-TECH-STRAT-006` — Kubernetes hosting, 4 environments, Day-0 GitOps.
  - `ADR-TECH-STRAT-007` — Two-world identifier strategy — `case_id` (UUIDv7) is the public correlation key; resolution to canonical `BNK.RLVR.OBJ.SUP.002.BENEFICIARY_RECORD.internal_id` is delegated to `BNK.RLVR.CAP.SUP.002.BEN` and is **not** carried by this BFF (PII-exclusion lane).
  - `ADR-TECH-STRAT-008` — Capability as multi-faceted information producer (operational bus emission for telemetry + analytical CDC fan-out + REST read APIs to the frontend).
- **Tactical stack**: `ADR-TECH-TACT-001` — .NET 10 BFF, vanilla HTML5/CSS3/JS frontend, ETag, polling (5 s cadence — 304 most of the time, NOT WebSocket / SSE), `localStorage` for the frontend session cache, **PII exclusion** enforced by `INV.DSH.001`. Stage 4 routes to `create-bff` (BFF under `sources/BNK.RLVR.CAP.CHN.001.DSH/bff/`) ∥ `code-web-frontend` (frontend under `sources/BNK.RLVR.CAP.CHN.001.DSH/frontend/`).
- **Governing URBA**: `ADR-BCM-URBA-0003` (one capability = one responsibility), `0009` (event meta-model + capability event ownership), `0010` (L2 as urbanisation pivot).
- **Process Modelling layer** (read-only contract for this roadmap): `process/BNK.RLVR.CAP.CHN.001.DSH/` v0.2.0 across all files — 1 aggregate, 4 commands, 3 policies, 2 projections, 2 queries, 3 upstream subscriptions, 1 emitted RVT.

## Framing Decisions

- **Consumer-side ownership boundary.** Per `ADR-BCM-URBA-0009`, the wire contract of each upstream RVT is owned by its emitting capability, never by the consumer. The dashboard does NOT publish stubs for upstream events — the producer roadmaps do (`BNK.RLVR.CAP.BSP.001.SCO`, `BNK.RLVR.CAP.BSP.001.TIE`, `CAP.BSP.004.ENV`). This roadmap consumes those producer stubs (or real emitters) — never re-issues them.
- **One frontend, mobile-first.** The process model and `ADR-TECH-TACT-001` target a single vanilla-JS frontend optimised for the mobile micro-moments of "check before purchase". No separate web build, no React, no framework.
- **Polling, not push.** Per `ADR-TECH-TACT-001`, the frontend polls `GET /dashboard` and `GET /transactions` every 5 seconds; the BFF responds 304 most of the time thanks to ETag. WebSocket / SSE are explicitly out of scope (*simplicity-first*).
- **PII-free by design.** `INV.DSH.001` blocks any PII field from entering the projection or the emitted RVT. The dashboard knows `case_id` (UUIDv7) and semantic data only; canonical identity resolution is delegated to `BNK.RLVR.CAP.SUP.002.BEN`.
- **Dignity rule as a testable invariant.** `ADR-BCM-FUNC-0009` — "accomplished progression is displayed before restrictions, every decline is accompanied by an explanation". Materialised as DoD checkpoints on Epic 2 and Epic 3 (DOM order assertion in tests, decline-reason rendering check).
- **UUIDv7 envelope on the emitted RVT.** Per `ADR-TECH-STRAT-007` Rule 4, the one event this capability emits (`BNK.RLVR.RVT.CHN.001.DASHBOARD_VIEWED`) carries `message_id`, `correlation_id = case_id`, `causation_id = client_request_id`, `schema_version` as UUIDv7 / semver. Same outbox discipline as upstream producers.
- **Aggregate is the projection.** No separate read store. The BFF holds `AGG.BENEFICIARY_DASHBOARD` in-process and `QRY.GET_DASHBOARD` is a direct read of the aggregate's snapshot fields. Simplicity-first per the tactical stack.
- **Tier downgrades intentionally invisible.** `POL.ON_TIER_UPGRADE_RECORDED` subscribes only to `RVT.TIER_UPGRADE_RECORDED`, never to a downgrade event. After a downgrade the progress bar may drift from upstream truth for one cycle until the next sync. This matches the FUNC-0009 stance "encourage without patronising"; flagged in Open Questions for explicit confirmation.

---

## Implementation Epics

### Epic 1 — BFF foundation, subscription bindings, dashboard aggregate

**Goal**: Stand up the dashboard BFF + frontend shell and wire the three upstream subscriptions, so that every incoming RVT for a `case_id` materialises the aggregate and feeds the (yet-empty) frontend shell end-to-end on a developer's machine.

**Entry condition**:
- `process/BNK.RLVR.CAP.CHN.001.DSH/` v0.2.0 merged on `main` (already met).
- Upstream contract stubs available for the three subscriptions:
  - `BNK.RLVR.CAP.BSP.001.SCO` — stub publishing `RVT.CURRENT_SCORE_RECOMPUTED` (already merged: TASK-001 done via PR #2).
  - `BNK.RLVR.CAP.BSP.001.TIE` — stub publishing `RVT.TIER_UPGRADE_RECORDED` (already merged: TASK-001 of BNK.RLVR.CAP.BSP.001.TIE done via PR #1).
  - `CAP.BSP.004.ENV` — stub publishing `RVT.CONSUMPTION_RECORDED` (already merged: TASK-001 of `CAP.BSP.004.ENV` done via PR #6).

All three upstream contract stubs are merged on `main` as of 2026-05-16 — Epic 1's upstream-readiness gate is fully met today.

**Exit condition (DoD)**:
- The BFF (`sources/BNK.RLVR.CAP.CHN.001.DSH/bff/`) is runnable via `dotnet run`; it declares queues `chn.001.dsh.q.score-recomputed`, `chn.001.dsh.q.tier-upgrade-recorded`, `chn.001.dsh.q.envelope-consumption-recorded` bound to the three upstream topic exchanges with the routing-key patterns from `process/BNK.RLVR.CAP.CHN.001.DSH/bus.yaml`.
- The aggregate `AGG.BENEFICIARY_DASHBOARD` is materialised lazily on the first inbound RVT for a `case_id`. The three policy commands (`SYNCHRONIZE_SCORE`, `SYNCHRONIZE_TIER`, `RECORD_ENVELOPE_CONSUMPTION`) are wired and enforce `INV.DSH.002` (idempotency by `event_id`, 30-day window) and `INV.DSH.003` (monotonic timestamps — out-of-order RVTs are ack-and-dropped).
- The frontend shell (`sources/BNK.RLVR.CAP.CHN.001.DSH/frontend/`) loads, polls `GET /dashboard`, displays an empty-state placeholder, and falls back gracefully on `404` (aggregate not yet materialised).
- OpenTelemetry traces span the inbound RVT → policy → command → aggregate path with the `environment` tag carrying the branch slug.
- Branch isolation: RabbitMQ exchange / queue names and BFF port carry the branch slug, per the worktree-isolation invariant in `CLAUDE.md`.

**Complexity**: M

**Unlocks events**: none (no public event emitted yet).

**Dependencies**:
- Upstream contract stubs: `BNK.RLVR.CAP.BSP.001.SCO` (done), `BNK.RLVR.CAP.BSP.001.TIE` (done), `CAP.BSP.004.ENV` (pending).
- Process model `process/BNK.RLVR.CAP.CHN.001.DSH/` (done).

---

### Epic 2 — Synthesised dashboard view (`GET /dashboard`) with dignity-compliant layout

**Goal**: Render the central dashboard panel — current autonomy tier, latest behavioural score, open envelopes with available balances — with the dignity rule materialised as testable DOM constraints. After this epic, a beneficiary can open the app, see their current situation, and the progression-before-restriction principle holds.

**Entry condition**: Epic 1 delivered.

**Exit condition (DoD)**:
- `QRY.GET_DASHBOARD` (`GET /cases/{case_id}/dashboard`) serves the synthesised snapshot (tier + tier_upgraded_at + score + open envelopes + last_synced_at) with `ETag` and `max_age=PT5S`. Most polling responses are `304`.
- The frontend renders the progression bar (score progress, current → next tier) **above** the restriction panel (envelope balances, remaining limits). DOM order asserted in a Playwright test (`progression-section` precedes `restrictions-section`).
- Every envelope rendered carries its `available_amount` AND the accomplished consumption (`consumed_amount`), framed positively ("Vous avez utilisé X — il vous reste Y").
- French vocabulary throughout the frontend per the Reliever product vision (no English UI strings).
- A beneficiary with an uninitialised aggregate gets an explicit "Première synchronisation en cours…" empty state, never a raw 404.
- Tier-upgrade animation triggers when the frontend detects `current_tier_code` change between two consecutive polls (timestamp from `tier_upgraded_at` drives the animation duration).
- Consent gate: the frontend exits to an explanatory view if the JWT does not carry an active consent claim (per `ADR-TECH-STRAT-003` bi-layer security; the actual `CAP.SUP.001.CON` integration is out of scope here — the BFF reads the consent claim from the bearer token).
- PII exclusion verified in tests: the response body never contains `last_name` / `first_name` / `date_of_birth` / raw `contact_details`. Schema linter on `BNK.RLVR.RES.CHN.001.DASHBOARD_VIEW` rejects any PII-typed field.

**Complexity**: M

**Unlocks events**: none (read-side only).

**Dependencies**: Epic 1.

---

### Epic 3 — Recent transactions feed (`GET /transactions`)

**Goal**: Add the "recent activity" panel to the dashboard — a bounded, most-recent-first list of envelope consumptions with categories, amounts, and (when applicable) decline reasons. The dignity rule extends to declines: every entry rendered as "Refusé" carries its reason.

**Entry condition**: Epic 2 delivered (frontend chrome and polling cadence in place).

**Exit condition (DoD)**:
- `PRJ.RECENT_TRANSACTIONS` projection holds at most 50 entries per `case_id`, age-bounded to 30 days (`INV.DSH.005`). Eviction is FIFO on `recorded_at`.
- `QRY.LIST_RECENT_TRANSACTIONS` (`GET /cases/{case_id}/transactions?limit=N`) serves the list with ETag/304 and `max_age=PT5S`. `limit` defaults to 20, max 50.
- The frontend renders each entry with `category` + `merchant_label` (semantic only — never a raw merchant name) + `amount`. Currency is rendered using the French locale (`fr-FR`).
- For consumption RVTs that carry a decline reason (when `CAP.BSP.004.ENV` later extends its RVT to cover declines — see Open Question 3), the decline reason is rendered next to the amount. For Epic 3, only authorised consumptions are modelled; declines are a forward-compatible field.
- The aggregate's `recent_transactions` invariant (`INV.DSH.005`) is exercised: synthetic data drives 100+ consumption events, the list never exceeds 50, oldest entries past 30 days are pruned.
- Backwards-compat with Epic 2: the existing dashboard endpoint is unchanged; the transactions panel is additive.

**Complexity**: S

**Unlocks events**: none.

**Dependencies**: Epic 2; `CAP.BSP.004.ENV` stub continuing to emit `RVT.CONSUMPTION_RECORDED` (already a dependency of Epic 1).

---

### Epic 4 — View telemetry: `POST /dashboard-views` emits `BNK.RLVR.RVT.CHN.001.DASHBOARD_VIEWED`

**Goal**: Close the analytics loop — the frontend signals to the BFF every dashboard open / refresh, the BFF debounces and emits the capability's single domain event so the analytical rail (`CAP.DAT.001.ING` etc.) can build engagement reports.

**Entry condition**: Epic 2 delivered (something to view).

**Exit condition (DoD)**:
- `CMD.RECORD_DASHBOARD_VIEW` (`POST /cases/{case_id}/dashboard-views`) accepts a `client_request_id` (UUIDv7 idempotency key, 5-minute window).
- 30-second per-`case_id` debounce (`INV.DSH.004`): a second call within 30 s of the previous *accepted* view returns 200 `VIEW_DEBOUNCED` without emitting; outside the window returns 201 and emits.
- When an emission fires, `BNK.RLVR.RVT.CHN.001.DASHBOARD_VIEWED` is published onto exchange `chn.001.dsh-events` via the transactional outbox (`ADR-TECH-STRAT-001` Rule 3 — at-least-once).
- The emitted payload conforms to `process/BNK.RLVR.CAP.CHN.001.DSH/schemas/BNK.RLVR.RVT.CHN.001.DASHBOARD_VIEWED.schema.json`. Required fields: `event_id` (the resource event's own identifier — downstream idempotency anchor), `occurred_at` (server-side wall-clock when the BFF accepted the underlying `RECORD_DASHBOARD_VIEW` command), `case_id` (correlation key, opaque participation case identifier). Optional snapshot fields: `current_tier_code`, `current_score` (the values displayed at the moment of consultation — pseudonymous behavioural data, not PII; null when the aggregate has not yet received the corresponding upstream event). Optional `client_context` block: `app_version`, `device_class` (semantic labels only — no device fingerprint, no PII).
- The bus-message envelope around the payload carries the UUIDv7 IDs (`message_id`, `correlation_id = case_id`, `causation_id = client_request_id`, `schema_version`) per `ADR-TECH-STRAT-007` Rule 4.
- PII-exclusion (`INV.DSH.001`) verified at schema-validation time: the JSON Schema's `additionalProperties: false` plus the absence of any `last_name` / `first_name` / `date_of_birth` / raw contact-detail field guarantees the wire format stays PII-free. Identity resolution to `BNK.RLVR.OBJ.SUP.002.BENEFICIARY_RECORD.internal_id` remains delegated to consumers via `BNK.RLVR.CAP.SUP.002.BEN`.
- The frontend fires the call on first paint and on each manual pull-to-refresh; `localStorage` carries `client_request_id` across reloads so accidental retries are idempotent.
- An end-to-end test asserts that opening the dashboard once results in exactly one `RVT.DASHBOARD_VIEWED` on the bus; opening it twice within 5 s results in still exactly one.

**Complexity**: S

**Unlocks events**: `BNK.RLVR.EVT.CHN.001.DASHBOARD_VIEWED` (the only business event this capability emits; scope `internal` — for the analytical rail, not consumer-facing).

**Dependencies**: Epic 2.

---

### Epic 5 — Real-CORE handoff and operability hardening

**Goal**: Decommission upstream stubs in favour of real producers, harden observability and JWT actor enforcement, validate the polling/ETag economics under load. The dashboard ships to staging.

**Entry condition**:
- Epics 1–4 delivered.
- Real producer implementations live in the dev environment:
  - `BNK.RLVR.CAP.BSP.001.SCO` — Flow B (real recomputation) operational (Epic 2 of the SCO roadmap).
  - `BNK.RLVR.CAP.BSP.001.TIE` — real tier engine operational.
  - `CAP.BSP.004.ENV` — real envelope engine operational.

**Exit condition (DoD)**:
- Each producer stub is decommissioned and the dashboard binds to the real producer exchanges; no functional regression on the synthesised view, the transactions feed, or the telemetry emission.
- OpenTelemetry dashboards expose: subscription queue depth per upstream RVT, end-to-end latency (RVT received → aggregate updated → next `GET /dashboard` poll reflects), 304 ratio on the two GET endpoints (target: ≥ 80 % at steady state), `RVT.DASHBOARD_VIEWED` emission rate, debounce hit rate.
- JWT actor enforcement: `ADR-TECH-STRAT-003` bi-layer security materialised — the BFF rejects any request whose JWT subject does not match the `case_id` owner. Tested with a synthetic mismatched token.
- DLQ runbook covers the two policy error codes (`EVENT_ALREADY_PROCESSED` is silent, `STALE_EVENT` is silent; out-of-spec payloads land in DLQ with a documented investigation path).
- Polling-vs-push economics validated: at 5 s cadence with 304 ETag responses, the BFF carries ≥ 100 concurrent active dashboards on a single pod with < 50 % CPU. If not, escalate to either widen `max_age` or revisit the polling decision in a follow-up TECH-TACT delta.

**Complexity**: M

**Unlocks events**: none (handoff only).

**Dependencies**: Epics 1–4; upstream real implementations.

---

## Dependency Map

| Epic | Depends On | Type |
|------|-----------|------|
| Epic 1 | `process/BNK.RLVR.CAP.CHN.001.DSH/` v0.2.0 on main | Stage gate |
| Epic 1 | `BNK.RLVR.CAP.BSP.001.SCO` contract stub (TASK-001 done, PR #2) | Cross-capability (upstream) |
| Epic 1 | `BNK.RLVR.CAP.BSP.001.TIE` contract stub (TASK-001 done, PR #1) | Cross-capability (upstream) |
| Epic 1 | `CAP.BSP.004.ENV` contract stub (pending) | Cross-capability (upstream) |
| Epic 2 | Epic 1 | Sequential |
| Epic 3 | Epic 2 | Sequential |
| Epic 4 | Epic 2 | Sequential (Epic 3 not required — telemetry is independent of the transactions feed) |
| Epic 5 | Epics 1–4 + real upstream producers operational | Sequential — gates ship-to-staging |

**Cross-capability outbound impact (consumers of the one emitted event)**: `BNK.RLVR.EVT.CHN.001.DASHBOARD_VIEWED` is `scope: internal`. The only declared consumer is the analytical rail (`CAP.DAT.001.*`) downstream of CDC on the BFF outbox. No operational consumer subscribes today.

**No identity-resolution dependency.** Although `case_id` resolution to canonical `BNK.RLVR.OBJ.SUP.002.BENEFICIARY_RECORD.internal_id` lives in `BNK.RLVR.CAP.SUP.002.BEN`, the dashboard never needs PII and therefore never calls that lookup. Listed for completeness only.

---

## Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Upstream producer schemas drift** between contract stub and real emission, breaking the dashboard's policies. | M | M | Pin JSON Schema versions in `process/BNK.RLVR.CAP.CHN.001.DSH/schemas/` and validate every incoming RVT against the upstream's published schema in CI. Surface a `STALE_EVENT` / payload-mismatch counter in OTel. |
| **PII leaks into the projection** through a new upstream field (e.g. `CAP.BSP.004.ENV` later extends `RVT.CONSUMPTION_RECORDED` with a raw merchant name). `INV.DSH.001` is enforced at code-review time but easy to miss. | M | H | Schema-level guard in CI: every new field in incoming RVTs is tagged `pii_classification` in the producer's process model; the dashboard's projector refuses to ingest fields tagged `medium` / `high`. Code-review checklist for Epic 3 and Epic 5. |
| **Polling cadence does not scale** beyond a few hundred concurrent dashboards; ETag 304 ratio drops because every poll arrives just-after an inbound RVT. | M | M | Validate quantitatively in Epic 5 (Operability DoD). If not met, two escape hatches: widen `max_age` (cost: stale UX) or add Server-Sent Events as a TECH-TACT delta (cost: simplicity-first violation — requires `ADR-TECH-TACT-001` amendment). |
| **Dignity rule** is treated as nice-to-have UI polish and ends up encoded in CSS only, untested. | M | H | Make DOM-order and decline-reason assertions explicit Playwright tests in Epic 2 and Epic 3 DoDs. Owner: User Experience Directorate signs off on the test corpus. |
| **Tier-downgrade invisibility** (Open Question 1) silently lets the progress bar lie after a downgrade — beneficiaries see a higher tier than they actually have for up to one polling cycle, and possibly indefinitely if no other event flushes the cache. | L | M | Track explicitly; if confirmed problematic in user testing, add a downgrade subscription (`SUB.BUSINESS.CHN.001.004`) — requires a delta `/process` pass + a BCM extension. |
| **Consent gate** integration is mocked via JWT claim today; if `CAP.SUP.001.CON` lands later than expected, the dashboard ships with a permissive consent check. | L | M | Document the JWT-claim shape in Epic 2 DoD; coordinate with `CAP.SUP.001.CON` roadmap before Epic 5 (staging ship). |

---

## Recommended Sequencing

```
Epic 1 (foundation) ─────────────────────────────────►
       └─► Epic 2 (synth view) ──────────────────────►
                  ├─► Epic 3 (transactions feed) ────►
                  └─► Epic 4 (telemetry) ────────────►
                              └─► Epic 5 (real CORE) ►
                                  [gated by upstream]
```

**Critical path**: Epic 1 → Epic 2 → (Epic 3 ∥ Epic 4) → Epic 5. Epic 5's entry condition explicitly requires all of Epics 1–4 delivered, so the path through them is unavoidable; the parallelism between 3 and 4 is the only schedule compression available.

**Parallelisable**: Epics 3 and 4 are independent of each other and can run concurrently after Epic 2. Both are small (S) so the wave gain is modest, but parallelism is real.

**Epic 5** sits on the critical path **internally** (it consumes the outputs of all four prior epics) but is **externally gated** by upstream producers becoming real (SCO Flow B, real TIE engine, real ENV engine). The dashboard is functionally complete on stubs after Epic 4; Epic 5 is the production-readiness epic and cannot start before the upstream gate clears.

---

## Open Questions

- **OQ-1 — Tier-downgrade invisibility**. `POL.ON_TIER_UPGRADE_RECORDED` only listens to `RVT.TIER_UPGRADE_RECORDED`. After a downgrade emitted by `AGG.TIER_OF_CASE`, the dashboard's `current_tier_code` may drift higher than reality until something else triggers a refresh. FUNC-0009 leans "encourage without patronising" — silence on downgrades is defensible — but should be confirmed by the User Experience Directorate. If a downgrade subscription is required, it's a delta `/process` + a BCM extension request before Epic 1 ships, or a TECH-TACT delta later.
- **OQ-2 — Consent integration shape**. The BFF reads the consent claim from the JWT; the canonical authority is `CAP.SUP.001.CON` (Consent Management). The shape of the claim (`consent.dashboard.read = true | false | revoked`) is not yet specified in any ADR. Coordinate with the `CAP.SUP.001.CON` roadmap before Epic 5 ships.
- **OQ-3 — Decline-reason field in `RVT.CONSUMPTION_RECORDED`**. The dignity rule extends to declines (Epic 3 DoD), but the upstream RVT does not currently carry a decline reason. For Epic 3 we model authorised consumptions only and leave the decline render-path forward-compatible. When `CAP.BSP.004.ENV` extends its RVT (or introduces a paired `RVT.CONSUMPTION_DECLINED`), revisit Epic 3 or add an Epic 3.5.
- **OQ-4 — Mobile vs Web target.** Existing tasks (002–006) include a "web" build epic; the process model and `ADR-TECH-TACT-001` target a single mobile-first vanilla-JS frontend. This roadmap commits to *one* frontend, mobile-first. If a separate web build is genuinely needed, it becomes a future Epic 6 (with a corresponding `/process` extension to declare a second frontend variant) — not in scope of the current 5-epic plan.
- **OQ-5 — Polling 304 economics under real load.** The 5-second polling cadence is a `simplicity-first` choice; quantitative scaling is unmeasured. Epic 5 DoD validates it. If it fails (≤ 80 % 304 ratio at 100+ concurrent dashboards on one pod), the fix is a TECH-TACT amendment (widen `max_age` or introduce SSE) — not in scope of the current roadmap.

---

## Knowledge Source

- `bcm-pack` ref: `main` (default)
- Capability pack mode: `--deep --compact`
- Pack date: 2026-05-16
- Process model ref: `process/BNK.RLVR.CAP.CHN.001.DSH/` v0.2.0 on `main` (uniform across all 7 files).
- This roadmap supersedes the prior `roadmap/BNK.RLVR.CAP.CHN.001.DSH/roadmap.md` (May 14, pre-v0.2.0 BCM). Existing tasks `TASK-002` … `TASK-006` use the prior epic numbering and stale event terminology; they should be regenerated via `/task BNK.RLVR.CAP.CHN.001.DSH` against this fresh roadmap. A small housekeeping pass on the kanban and the existing task files is recommended before launching new `/code` cycles.
