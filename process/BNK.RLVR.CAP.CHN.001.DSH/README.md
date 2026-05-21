# Process Model — BNK.RLVR.CAP.CHN.001.DSH (Beneficiary Dashboard)

> **Layer**: Process Modelling (DDD tactical) — sits between Big-Picture Event
> Storming (banking-knowledge: BCM, FUNC ADR) and Software Design (this
> repo's `sources/`).
> **Source of truth for**: commands accepted by the dashboard BFF, aggregate
> boundary and invariants, reactive policies, read-model surface, bus topology,
> wire schemas of this capability.
> **NOT a plan**: this folder is durable across re-plans and re-implementations
> of the same FUNC ADR. The `plan/BNK.RLVR.CAP.CHN.001.DSH/` folder consumes it.
>
> **Zone**: CHANNEL — this capability is implemented as a Backend-For-Frontend
> (BFF) plus a vanilla-JS mobile frontend. Two agents materialise it from this
> model: `create-bff` (the .NET BFF) and `code-web-frontend` (the vanilla-JS
> view). Both consume `process/BNK.RLVR.CAP.CHN.001.DSH/` as a read-only contract.

## Upstream knowledge (consumed, not re-stated)

Fetched via `bcm-pack pack BNK.RLVR.CAP.CHN.001.DSH --deep`. Anything in those slices is
canonical and must NOT be duplicated here:

- `capabilities-reliever-L2.yaml` — capability definition, parent BNK.RLVR.CAP.CHN.001,
  zone CHANNEL, owner User Experience Directorate
- `func-adr/ADR-BCM-FUNC-0009` — L2 breakdown of BNK.RLVR.CAP.CHN.001 (Beneficiary
  Journey)
- `business-event-reliever.yaml` — `BNK.RLVR.EVT.CHN.001.DASHBOARD_VIEWED`
- `resource-event-reliever.yaml` — `BNK.RLVR.RVT.CHN.001.DASHBOARD_VIEWED`
- `business-object-reliever.yaml` — `BNK.RLVR.OBJ.BSP.002.PARTICIPATION` (carried by
  the emitted event; owned by BNK.RLVR.CAP.BSP.002.CYC)
- `resource-reliever.yaml` — `BNK.RLVR.RES.BSP.002.ACTIVE_CASE` (technical projection
  carried by the RVT)
- `business-subscription-reliever.yaml` — three upstream subscriptions
  (SCORE_RECOMPUTED, TIER_UPGRADED, ENVELOPE_CONSUMED)
- `resource-subscription-reliever.yaml` — three matching resource
  subscriptions (CURRENT_SCORE_RECOMPUTED, TIER_UPGRADE_RECORDED,
  CONSUMPTION_RECORDED)
- `tech-vision/adr/ADR-TECH-STRAT-001` — bus topology rules (NORMATIVE)
- `tech-vision/adr/ADR-TECH-STRAT-003` — REST/HTTP, BFF per channel, ETag
- `tech-adr/ADR-TECH-TACT-001` — tactical stack: vanilla-JS frontend, BFF,
  ETag, polling, local-storage, **PII exclusion**

## What this folder declares (Process Modelling output)

| File | Captures |
|---|---|
| `aggregates.yaml` | One aggregate (`AGG.BENEFICIARY_DASHBOARD`) — consistency boundary, invariants, accepted commands, emitted RVT |
| `commands.yaml` | Four CMDs — one HTTP-issued (`RECORD_DASHBOARD_VIEW`), three policy-issued (`SYNCHRONIZE_SCORE`, `SYNCHRONIZE_TIER`, `RECORD_ENVELOPE_CONSUMPTION`) |
| `policies.yaml` | Three POLs — one per upstream subscription (BSP.001.SCO, BSP.001.TIE, BSP.004.ENV) |
| `read-models.yaml` | Two projections + two queries (`GET_DASHBOARD`, `LIST_RECENT_TRANSACTIONS`) |
| `bus.yaml` | Exchange `chn.001.dsh-events`, one routing key, three subscription bindings |
| `api.yaml` | Derived REST surface: 1 POST (telemetry) + 2 GET (cached, ETag) |
| `schemas/` | JSON Schemas (Draft 2020-12) for the four CMD payloads + the one emitted RVT payload |

## Capability shape at a glance

```
┌────────────────────────────────────────────────────────────────┐
│                       BNK.RLVR.CAP.CHN.001.DSH                          │
│                  (Beneficiary Dashboard BFF)                   │
│                                                                │
│   ┌──────────────────────────────────────────────────────┐     │
│   │   AGG.BENEFICIARY_DASHBOARD  (one per case_id)       │     │
│   │     state: tier · score · open_envelopes ·           │     │
│   │            recent_transactions · last_viewed_at      │     │
│   │     invariants: PII-free · idempotent · monotonic    │     │
│   └──────────────────────────────────────────────────────┘     │
│      ▲ accepts                ▲ accepts        ▲ accepts       │
│      │                        │                │               │
│      │ CMD.RECORD_            │ CMD.SYNC_*     │ CMD.RECORD_   │
│      │   DASHBOARD_VIEW       │   (3 internal) │   ENVELOPE_   │
│      │                        │                │   CONSUMPTION │
│   POST /dashboard-views   POL.ON_SCORE_      POL.ON_ENVELOPE_  │
│      ▲                    RECOMPUTED         CONSUMPTION_      │
│      │                    POL.ON_TIER_        RECORDED         │
│      │                    UPGRADE_RECORDED                     │
│      │                        ▲                ▲               │
│      │                        │ subscribes     │ subscribes    │
│      │                        │ BNK.RLVR.RVT.BSP.001.*  │ BNK.RLVR.RVT.BSP.004.* │
│   [vanilla-JS frontend]                                        │
│                                                                │
│   emits ───► BNK.RLVR.RVT.CHN.001.DASHBOARD_VIEWED                      │
│              (telemetry; PII-free; debounced 30s)              │
└────────────────────────────────────────────────────────────────┘
```

## Scenario walkthroughs

Three flows together cover every behaviour of this capability:
**view telemetry**, **score / tier synchronisation**, and
**envelope consumption recording**.

### Flow A — Beneficiary opens the dashboard tab (telemetry)

```
[Vanilla-JS frontend, mobile]
        POST /cases/{case_id}/dashboard-views
            { client_request_id, viewed_at, client_context }
                │
                ▼
   CMD.CHN.001.DSH.RECORD_DASHBOARD_VIEW
                │
                ▼ handled by
   AGG.CHN.001.DSH.BENEFICIARY_DASHBOARD
                │
        ┌───────┴───────┐
        ▼               ▼
   (now - last_viewed_at) >= 30s ?
        │               │
        │ YES           │ NO
        ▼               ▼
   emits           ack as
   BNK.RLVR.RVT.CHN.001.    VIEW_DEBOUNCED
   DASHBOARD_      (HTTP 200,
   VIEWED          no event)
        │
        ▼ routing key
   BNK.RLVR.EVT.CHN.001.DASHBOARD_VIEWED.BNK.RLVR.RVT.CHN.001.DASHBOARD_VIEWED
        │
        ▼ consumed by
   [DATA_ANALYTIQUE — engagement metrics, future]
```

### Flow B — Upstream score / tier event arrives

```
[BNK.RLVR.CAP.BSP.001.SCO]                 [BNK.RLVR.CAP.BSP.001.TIE]
   BNK.RLVR.RVT.CURRENT_SCORE_RECOMPUTED      BNK.RLVR.RVT.TIER_UPGRADE_RECORDED
                │                                 │
                ▼                                 ▼
   POL.CHN.001.DSH.                  POL.CHN.001.DSH.
   ON_SCORE_RECOMPUTED               ON_TIER_UPGRADE_RECORDED
                │                                 │
                ▼ issues                          ▼ issues
   CMD.CHN.001.DSH.                  CMD.CHN.001.DSH.
   SYNCHRONIZE_SCORE                 SYNCHRONIZE_TIER
                │                                 │
                ▼ handled by                      ▼ handled by
   AGG.CHN.001.DSH.BENEFICIARY_DASHBOARD (same instance)
                │
        ┌───────┴───────┬───────┐
        ▼               ▼       ▼
   replay?         stale?       fresh
        │               │       │
        ack-and-drop    ack-and-drop   apply
        (idempotent)    (monotonic)    state mutation
                                       (no autonomous bus event)
                                              │
                                              ▼
                                       Next GET /dashboard
                                       reflects the new
                                       score / tier within
                                       one polling cycle.
```

### Flow C — Envelope consumption arrives

```
[BNK.RLVR.CAP.BSP.004.ENV]
   BNK.RLVR.RVT.CONSUMPTION_RECORDED { case_id, envelope_id, transaction_id, amount, ... }
                │
                ▼
   POL.CHN.001.DSH.ON_ENVELOPE_CONSUMPTION_RECORDED
                │
                ▼ issues
   CMD.CHN.001.DSH.RECORD_ENVELOPE_CONSUMPTION
                │
                ▼ handled by
   AGG.CHN.001.DSH.BENEFICIARY_DASHBOARD
                │
        ┌───────┴────────────┐
        ▼                    ▼
   open_envelopes         recent_transactions
   (replace matching      (insert at head;
    envelope_id row)       evict if > 50 entries
                           or > 30 days old)
        │
        ▼
   Next GET /transactions returns the
   updated bounded feed (most-recent-first).
```

## Open process-level questions (must be resolved before `/code`)

1. **Aggregate eager vs lazy creation.** The aggregate is materialised lazily
   on the first incoming event (INV.DSH.006). FUNC-0009 declares no
   subscription to a `BNK.RLVR.EVT.BSP.002.CASE_OPENED` (or similar) — without it, a
   freshly enrolled beneficiary will see a 404 on `GET /dashboard` until the
   first score / tier / envelope event lands. Two options:
   - Accept the 404 → frontend must render an empty-state page until the
     first event arrives. Simple, no upstream contract change. **Picked.**
   - Add a future subscription to a CYC case-opened event → eager
     materialisation with empty placeholders. Requires a new
     business-subscription in the BCM upstream.

2. **Tier downgrade propagation.** `policies.yaml` only listens to
   `BNK.RLVR.RVT.BSP.001.TIER_UPGRADE_RECORDED`; downgrades emitted by
   `AGG.BSP.001.TIE.TIER_OF_CASE` (`BNK.RLVR.RVT.TIER_DOWNGRADE_RECORDED`) are NOT
   subscribed-to. After a downgrade, the dashboard's `current_tier_code`
   silently drifts from reality until the next upgrade.
   - FUNC-0009 is explicit about the gamification stance ("encourage without
     patronising"); deliberately hiding downgrades may be an accepted UX
     decision.
   - Alternatively: add a fourth subscription + a fourth policy to keep the
     tier monotonically synchronised, and let the frontend choose whether to
     surface the downgrade.
   This sketch leaves the subscription absent, mirroring FUNC-0009 verbatim.
   Confirm with the UX directorate before `/code`.

3. **Envelope closure.** The aggregate accumulates `open_envelopes` from
   `BNK.RLVR.RVT.BSP.004.CONSUMPTION_RECORDED` but never prunes closed or archived
   envelopes — there is no closure subscription declared. This is acceptable
   for a remediation programme of bounded duration (envelopes live ~weeks
   to ~months) but should be revisited if BSP.004 introduces a closure
   event (`BNK.RLVR.RVT.BSP.004.ENVELOPE_CLOSED`?). Track upstream.

4. **`BNK.RLVR.RVT.BSP.004.CONSUMPTION_RECORDED` field set.** The mapping rule in
   `policies.yaml` and the schema `CMD.RECORD_ENVELOPE_CONSUMPTION` assume
   the upstream RVT carries: `envelope_id`, `transaction_id`, `amount`,
   `currency`, `category`, `merchant_label` (PII-free), and the post-
   consumption envelope snapshot (`allocated_amount`, `consumed_amount`,
   `available_amount`). When BNK.RLVR.CAP.BSP.004.ENV's process model lands,
   re-validate this mapping. If `merchant_label` is absent upstream, drop
   it from the dashboard surface (it is non-essential).

5. **Score progression percentage.** The dashboard renders a "progress bar"
   that requires translating the numerical score into a fraction of the
   current tier's range. Tier thresholds are owned by BNK.RLVR.CAP.REF.001.TIE.
   This sketch keeps the dashboard projection raw (`current_score` as a
   number) and delegates the rendering arithmetic to the **frontend**, which
   reads tier definitions via a separate REF API call. An alternative is to
   pre-compute `score_progression_pct` server-side; this would couple the
   BFF to REF and break the BFF's read-only-projection nature. Picked: keep
   it on the frontend.

6. **DASHBOARD_VIEWED downstream consumer.** No business-subscription is
   declared for `BNK.RLVR.EVT.CHN.001.DASHBOARD_VIEWED` in the BCM today. The
   intended consumer is a future DATA_ANALYTIQUE capability for engagement
   telemetry. Before the first non-test consumer appears, declare the
   business-subscription upstream and add it to `bus.yaml`'s `consumers`
   list.

## Governance

| ADR | Role |
|---|---|
| `ADR-BCM-FUNC-0009` | L2 breakdown of BNK.RLVR.CAP.CHN.001 — defines emitted/consumed events for the beneficiary journey |
| `ADR-BCM-FUNC-0016` | Relocated the beneficiary identity anchor from BNK.RLVR.CAP.REF.001 to BNK.RLVR.CAP.SUP.002 — every PII-resolution reference now points to BNK.RLVR.CAP.SUP.002.BEN |
| `ADR-BCM-URBA-0009` | Definition of an event-driven capability |
| `ADR-BCM-URBA-0010` | L2 capabilities as the urbanisation pivot |
| `ADR-TECH-STRAT-001` | Bus rules (exchange-per-L2, routing-key convention, design-time schema governance) — NORMATIVE |
| `ADR-TECH-STRAT-003` | API contract strategy (REST/HTTP, BFF per channel, ETag) |
| `ADR-TECH-STRAT-007` | Identifier strategy — UUIDv7, immutable anchors |
| `ADR-TECH-STRAT-008` | Capability as multi-faceted information producer |
| `ADR-TECH-TACT-001` | Tactical stack — vanilla-JS frontend, BFF, ETag, polling, local-storage, **PII exclusion** |
