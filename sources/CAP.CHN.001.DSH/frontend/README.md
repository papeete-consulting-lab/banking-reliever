# CAP.CHN.001.DSH — Frontend shell (TASK-002)

Vanilla HTML5 / CSS3 / JS frontend shell for the **Beneficiary Dashboard**
capability. Pairs with the .NET 10 BFF under
sibling `bff/` folder under `sources/CAP.CHN.001.DSH/` (scaffolded in parallel by the `create-bff`
agent).

> **Scope of TASK-002:** the *shell only* — header, branch badge, French
> empty-state placeholder, two ordered sections (`#progression-section`
> then `#restrictions-section`), polling loop, ETag handling, JWT
> attachment, stub-data fallback. The synthesised dashboard view itself
> (tier card, envelope rows) lands in **TASK-003**.

## File tree

```
sources/CAP.CHN.001.DSH/frontend/
├── index.html        Entry — loads app.js as an ES module
├── dev.html          Dev harness — form to set case_id / JWT / consent / BFF base URL
├── app.css           Mobile-first styles (no preprocessor, no CSS framework)
├── app.js            Boot logic, DOM helpers, poll-event dispatcher
├── api.js            fetch wrapper + polling loop + stub fallback
├── i18n.js           French strings dictionary
├── stub-data.js      DashboardView fixtures for the offline fallback
└── README.md         This file
```

## Run locally

The frontend is a flat tree of static files — any static server works.
We standardise on Python 3's built-in:

```bash
cd sources/CAP.CHN.001.DSH/frontend
python -m http.server 7134
# then open http://localhost:7134/dev.html
```

The chosen port for this branch is **7134** — derived deterministically
from the branch slug (see "Branch-slug derivation policy" below).

## Query-string switches

| Param            | Example                | Effect                                                                 |
|------------------|------------------------|------------------------------------------------------------------------|
| `case_id`        | `CASE-DEV-0001`        | Drives `GET …/cases/{case_id}/dashboard`. Empty-state if omitted.      |
| `caseId`         | (alias)                | Same as `case_id`.                                                     |
| `beneficiaireId` | `BEN-001`              | Reserved for future use; recorded but not currently used by the shell. |
| `consentement`   | `refuse`               | Renders the consent-gate scaffold (DoD #5). Reload to dismiss.         |
| `debug`          | `1`                    | Reserved for future verbose-logging toggle.                            |

Examples:

```text
http://localhost:7134/index.html?case_id=CASE-DEV-0001
http://localhost:7134/index.html?case_id=CASE-DEV-0001&consentement=refuse
```

## JWT injection

Every poll attaches `Authorization: Bearer <token>`. The token is resolved
in this priority order:

1. `window.__JWT__` — set by a dev harness or by Playwright's
   `addInitScript()` in the test suite
2. `localStorage["jwt"]` — sticky between page reloads; the dev harness
   sets this when you submit the form
3. `null` — the BFF will respond `401`; the UI surfaces a friendly toast

In `dev.html`, type a JWT into the form and submit — it is written to
`localStorage["jwt"]` and the iframe boots `index.html`.

## BFF base URL

Defaults to **same-origin** (empty string), so paths like
`/capabilities/chn/001/dsh/cases/.../dashboard` hit whichever server is
serving the HTML. To point at a separate BFF host (typical dev setup),
either:

- Submit a value in the **BFF base URL** field on `dev.html` (it stashes
  the URL on `window.__BFF_BASE_URL__` before the iframe boots), or
- Inject `<script>window.__BFF_BASE_URL__ = 'http://localhost:5180';</script>`
  before `<script type="module" src="./app.js">` in `index.html`.

For full-fledged dev across worktrees we recommend running the BFF on the
branch-isolated BFF port (the create-bff agent prints it on startup) and
setting `window.__BFF_BASE_URL__` to that origin.

## Stub-fallback behaviour

If the BFF stays unreachable (network error / 5xx) for more than
**30 seconds** (configurable via `window.__STUB_FALLBACK_AFTER_MS__`), the
poll loop switches into **fallback mode**: it renders a stub
`DashboardView` (shape matches `PRJ.CHN.001.DSH.DASHBOARD_VIEW` from
`process/CAP.CHN.001.DSH/read-models.yaml`) and the footer indicator
turns amber ("Mode démonstration"). A toast informs the user that the
content is fictional during the outage.

Fallback is automatically cleared on the next successful `200`.

Note: a `404` is **not** a failure — it means the aggregate has not yet
been materialised, and the UI shows the empty-state placeholder. Only
*real* unhealth (network, 5xx, 401) triggers the fallback timer.

## Branch-slug derivation policy

The dev port and the branch badge are derived from the Git branch slug:

```bash
BRANCH=$(git branch --show-current \
  | tr '[:upper:]' '[:lower:]' \
  | sed 's/[^a-z0-9]/-/g' \
  | sed 's/-\+/-/g' \
  | sed 's/^-\|-$//g')
PORT=$(python3 -c "import hashlib; \
  h=int(hashlib.sha256('$BRANCH'.encode()).hexdigest(),16); \
  print(7080 + (h % 100))")
```

This places the port in the **7080–7179** range, which is high enough to
avoid system services and gives 100 simultaneous worktrees breathing
room. Collisions within a single 100-bucket window are unlikely (two
worktree branch names would have to hash to the same residue mod 100).

For this branch (`feat/TASK-002-bff-foundation-subscriptions-aggregate`):
- **slug:** `feat-task-002-bff-foundation-subscriptions-aggregate`
- **port:** `7134`

If you spot a collision, override on the command line:

```bash
python -m http.server 7180
```

## DOM contract (dignity rule)

The two dashboard sections appear in a fixed order, asserted in TASK-003:

```html
<div id="dashboard">
  <section id="progression-section" data-testid="progression-section">…</section>
  <section id="restrictions-section" data-testid="restrictions-section">…</section>
</div>
```

`#progression-section` MUST come first. This is the DOM encoding of
ADR-BCM-FUNC-0009's "progression before restrictions" dignity rule.

Both sections are intentionally empty in TASK-002 — TASK-003 populates
them. Do not reorder.

## Testability handles

| Element                           | Selector                                          |
|-----------------------------------|---------------------------------------------------|
| Branch badge                      | `#branch-badge`, `[data-testid=branch-badge]`     |
| Loading overlay                   | `#loading`, `[data-testid=loading-overlay]`       |
| Consent gate                      | `#consent-gate`, `[data-testid=consent-gate]`     |
| Empty-state placeholder           | `#empty-state`, `[data-testid=empty-state]`       |
| Dashboard body                    | `#dashboard`, `[data-testid=dashboard]`           |
| Progression section (dignity #1)  | `#progression-section`, `[data-testid=progression-section]` |
| Restrictions section (dignity #2) | `#restrictions-section`, `[data-testid=restrictions-section]` |
| Error toast                       | `#error-toast`, `[data-testid=error-toast]`       |
| Poll-status indicator             | `#poll-indicator`, `[data-testid=poll-indicator]` |

The polling API is reachable from the page context via
`window.BeneficiaryDashboardApi` (see `api.js`). The test agent can
override `fetchDashboard` to inject canned responses via Playwright's
`addInitScript`.

## What this shell does NOT do (yet)

Tracked for later tasks:

- Render the synthesised view (tier card, score, open envelopes)
  → **TASK-003**
- Render the recent-transactions feed → **TASK-004**
- POST `RECORD_DASHBOARD_VIEW` telemetry on visibility → **TASK-005**
- Real-core handoff and operability dashboards → **TASK-006**

## Invariants preserved by the shell

- **INV.DSH.001 (PII exclusion)** — the shell touches none of the
  forbidden fields; the stub fixtures contain only opaque codes, numeric
  amounts, and ISO timestamps.
- **ETag honoured** — `If-None-Match` is sent on every poll; the BFF
  responds `304` and the UI silently no-ops.
- **5 s cadence** — matches `cache.max_age: PT5S` in `api.yaml`.
- **404 never leaks** — both `404` and `200`-with-null-fields render the
  same French empty-state placeholder.
- **Branch isolation** — the dev port and the visible branch badge make
  side-by-side worktrees safe and identifiable.
