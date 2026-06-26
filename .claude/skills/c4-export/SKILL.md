---
name: c4-export
description: >
  Renders the product business-capability tree as a set of Structurizr DSL
  files under docs/c4/. Three levels: enterprise (docs/c4/enterprise/workspace.dsl
  — the product as a system, zones as containers, every L2 as a component),
  zone (docs/c4/enterprise/zone-<zone>.dsl — one per zone, every L2 in that
  zone as a container, cross-cap event flows), and per-L2 capability
  (docs/c4/<CAP_L2>/workspace.dsl — implementation artifacts as containers,
  DDD elements from the process model (consumed via `kpack process <CAP>`)
  as components, ADR refs as properties pointing at the product knowledge
  repo). Every DSL file
  carries tags reflecting the on-disk implementation status (mode-a / stub /
  bff / frontend / not-scaffolded), with corresponding colors in the styles
  block so the rendered views show "where we stand". Reads upstream knowledge
  exclusively via `kpack` — never opens /bcm/, /adr/, /func-adr/, /tech-adr/,
  /domain-vision/, /business-vision/, /tech-vision/ directly. Idempotent —
  re-runs overwrite the same files in place.
  Trigger on: "c4-export", "/c4-export", "structurizr export", "render c4",
  "c4 model", "draw the c4 diagram", "export the c4 model", "update c4",
  "regenerate c4", "c4 dsl", "c4 for CAP.…".
---

# /c4-export — Structurizr C4 export from BCM + on-disk implementation

Renders the product business-capability tree as Structurizr DSL files. One
file per L2 leaf capability, one file per zone, one file for the enterprise
landscape. The DSL is intentionally rendered offline — view the result with

> `<PRODUCT_CTX>` is this enterprise's product capability-map context, resolved
> from the repo's `.kpack.yaml` and the governance `contexts:` registry — never
> hardcoded.

[Structurizr Lite](https://structurizr.com/help/lite),
[Structurizr CLI](https://github.com/structurizr/cli), or paste into
[structurizr.com](https://structurizr.com).

## Position in the pipeline

`/c4-export` is a read-mostly skill — it does NOT participate in the implementation
pipeline (no zone routing, no agent dispatch, no test loop). It composes:

- the **business-capability model** (upstream, in the product knowledge repo,
  consumed via `kpack pack`),
- the **process model** (aggregates, commands, policies, read-models, bus —
  authored upstream in the product knowledge repo and consumed read-only via
  `kpack process <CAP>`),
- the **on-disk implementation overlay** (`sources/<CAP>/{backend,stub,bff,frontend}`),

into Structurizr DSL files under `docs/c4/`. The process model does not live in
this repo — there is no local `process/` lane to read from or write to.

## Layout produced

```
docs/c4/
  enterprise/
    workspace.dsl              one Software Landscape — the product as a system,
                               zones as containers, every L2 as a component
    zone-bsp.dsl               per-zone Container view
    zone-sup.dsl
    zone-ref.dsl
    zone-chn.dsl
    zone-b2b.dsl
    zone-dat.dsl
    zone-str.dsl
  CAP.<ZONE>.<NNN>.<SUB>/
    workspace.dsl              per-L2 detail — implementation artifacts as
                               containers, DDD elements as components, ADR
                               refs as properties
```

## C4 mapping

### Per-L2 file (`docs/c4/<CAP_L2>/workspace.dsl`)

| C4 element | What it represents |
|---|---|
| Software System | The L2 capability itself — named by its BCM `name` (e.g. `Tier Management`), described by its BCM `description`, with the dotted `capability-id` (e.g. `<PRODUCT_CTX>.CAP.BSP.001.TIE`) stored as a property |
| Container | An implementation artifact: backend microservice (Mode A), contract stub (Mode B), BFF, frontend, or a `not-scaffolded` placeholder |
| Component | A DDD element mined from the process model (via `kpack process <CAP>`) — aggregates, read-models, policies, business-event publishers. Display labels strip the namespace prefix and turn `_` into spaces (e.g. `<PRODUCT_CTX>.EVT.BSP.001.TIER_UPGRADED` → `TIER UPGRADED`); the full ID is preserved on the `id` property |

Upstream capabilities (other L2s that emit business events this capability
subscribes to) appear as `external-capability` Software Systems named after
their BCM `name` (e.g. `Behavioural Scoring`), with the dotted capability id
as a property. Relationships are wired exclusively from the business-layer
items of `consumed_events` (`select(.layer=="business")` → `subscribed_event`)
— resource-event subscriptions (`RVT.*` / `consumed_events` items with
`.layer=="resource"`) are intentionally hidden from the C4 view because they
are a bus-rail implementation detail.
The downstream side is summarised as a "Downstream consumers" Software
System listing the emitted **business** event display labels.

### Per-zone file (`docs/c4/enterprise/zone-<abbrev>.dsl`)

| C4 element | What it represents |
|---|---|
| Software System | The zone, named by its pretty form (e.g. `Business Service Production`) with the raw code stored as the `zone-code` property |
| Container | An L2 capability in that zone — named by its BCM `name`, described by its BCM `description`, tagged with its current implementation status, and carrying `capability-id` / `parent` / `detail-view` properties |

Cross-capability flows are drawn from the business-layer items of
`consumed_events` (`select(.layer=="business")`) only.
Each relationship is labelled with the comma-separated list of cleaned
business-event display labels (e.g. `SCORE THRESHOLD REACHED,
OVERRIDE REQUESTED`) and tagged with `"Business event subscription"` as
its technology. The source side is rendered as an `external-capability`
Software System if the emitter lives in another zone — named after its
BCM `name`, with the dotted capability id as a property.

### Enterprise file (`docs/c4/enterprise/workspace.dsl`)

| C4 element | What it represents |
|---|---|
| Person | Beneficiary, Prescriber, Regulator |
| External Software System | Partner bank |
| Software System | The product (the whole programme) |
| Container | A zone of the product — display name is the pretty zone form (e.g. `Business Service Production`); raw code on `zone-code` property |
| Component | An L2 capability inside a zone — named by its BCM `name`, described by its BCM `description`; raw `capability-id` on a property |

A System Landscape view and per-zone Component views are emitted so you can
both zoom out (the product in its environment) and zoom in (every L2 in each
zone). Zone-to-zone edges are derived from cross-zone business-layer items of
`consumed_events` (`select(.layer=="business")`) only and carry
`"Business events"` as their label.

## Implementation overlay — tags and colors

| Tag | Meaning | Style |
|---|---|---|
| `implemented:mode-a` | `sources/<CAP>/backend/` present | green |
| `implemented:stub` | `sources/<CAP>/stub/` present | yellow |
| `implemented:bff` | `sources/<CAP>/bff/` present | blue |
| `implemented:frontend` | `sources/<CAP>/frontend/` present | violet |
| `not-scaffolded` | None of the above | grey, dashed border |

Plus zone tags (`zone:BSP`, `zone:SUP`, …), level tags (`level:L1`, `level:L2`),
domain classification (`domain:core` etc.), and tech tags (`tech:python`,
`tech:dotnet`). The styles block in every DSL file maps these consistently so
a quick glance at any view tells you where each capability stands.

## ADR references

Every L2 file carries `properties` of the form:

```dsl
"adr:ADR-BCM-FUNC-0005" "<PRODUCT_KNOWLEDGE_REPO_URL>/blob/main/func-adr/ADR-BCM-FUNC-0005-...md"
"adr:ADR-TECH-TACT-003" "<PRODUCT_KNOWLEDGE_REPO_URL>/blob/main/tech-adr/ADR-TECH-TACT-003-...md"
"adr:ADR-BCM-URBA-0009" "<PRODUCT_KNOWLEDGE_REPO_URL>/blob/main/adr/ADR-BCM-URBA-0009-...md"
```

ADR IDs and their on-disk paths are extracted from the `files` slice of
`kpack pack <CAP_ID> --deep --compact` — never from a direct read of
the product knowledge repo. The GitHub blob base URL is derived from the
product map's repo in the contexts registry, not hardcoded.

## Step 0 — Prerequisites

This skill is a thin wrapper over the **`kproj-c4`** CLI, shipped by the
`papeete-consulting/projectors` package (backbone #5 — the projector no longer
lives in this repo). Ensure both `kpack` and `kproj-c4` are on PATH:

```bash
command -v kpack    || { echo "kpack MISSING — install it; the skill cannot proceed"; exit 1; }
command -v kproj-c4 || pip install "git+https://github.com/papeete-consulting/projectors.git@v0.1.0"
```

`kpack` is mandatory and has no fallback. `kproj-c4` reads upstream knowledge
exclusively through `kpack` (it never opens `/bcm`, `/adr`, … directly) — the BCM
corpus is fetched **remotely** by `kpack` via the governance registry, so no
`--repo-root` is needed here.

The product context + GitHub blob bases are still supplied by the environment, as
before — `C4_PRODUCT_CTX` (the kpack context), `C4_KNOWLEDGE_BLOB`,
`C4_SOURCE_BLOB`, `C4_PRODUCT_NAME` (resolve from `.kpack.yaml` / the contexts
registry; never hardcode).

## Step 1 — Parse arguments

| Form | Behavior |
|---|---|
| `/c4-export` | Re-render everything: every per-L2 file, every zone file, the enterprise file |
| `/c4-export CAP.<…>` | Re-render only the per-L2 file for that capability. Enterprise / zone files are NOT regenerated (re-run without an argument to refresh those) |
| `/c4-export --enterprise-only` | Re-render only the enterprise + zone files |
| `/c4-export --dry-run` | Print what would be written, change nothing on disk |

## Step 2 — Run the CLI

`C4_PRODUCT_CTX` supplies the context; write the DSL under this repo's `docs/c4`:

```bash
kproj-c4 --out docs/c4 [--cap CAP.<…>] [--enterprise-only] [--dry-run]
```

(`--context <PRODUCT_CTX>` may be passed explicitly instead of relying on
`$C4_PRODUCT_CTX`. `--out docs/c4` is required so the files land in this repo, not
beside the installed package.)

The CLI:

1. Calls `kpack list --context <PRODUCT_CTX>` to enumerate every capability.
2. Filters to L2 leaves (L1 parents are surfaced inside per-L2 files via the
   `parent` property, and at the enterprise view as a zone grouping).
3. For each L2 in scope, calls `kpack pack <CAP> --deep --compact` to fetch
   the full slice set.
4. Inspects `sources/<CAP>/{backend,stub,bff,frontend}` to set the
   implementation overlay tag.
5. Optionally fetches the process model via `kpack process <CAP>`
   (aggregates / read-models / policies / bus) to add DDD components.
6. Builds GitHub URLs for every referenced ADR from the `files` slice
   (product knowledge repo, `main` branch).
7. Emits the per-L2, per-zone, and enterprise DSL files under `docs/c4/`.
8. Logs each write to stdout.

Pass the script's stdout straight to the user — it is the canonical run report.

## Step 3 — Surface the result

After the script returns:

- Confirm the file count and the layout (`docs/c4/`).
- Suggest how to render: Structurizr Lite via docker, Structurizr CLI, or
  copy-paste at https://structurizr.com.
  Sample one-liner:

  ```bash
  docker run -it --rm -p 8080:8080 -v "$(pwd)/docs/c4/enterprise:/usr/local/structurizr" structurizr/lite
  ```

- If a capability was renamed or removed in the product knowledge repo since the
  last run, stale `docs/c4/<old-id>/` folders may remain. The script does not
  delete them — `git status docs/c4` to inspect, then remove by hand.

## Boundaries

This skill MUST NOT:

- Treat the process model as a local writable lane. It is authored by `/process`
  in the product knowledge repo and consumed read-only via `kpack process` — there
  is no `process/` folder in this repo to read from or write to.
- Open `/bcm/`, `/adr/`, `/func-adr/`, `/tech-adr/`, `/domain-vision/`,
  `/business-vision/`, `/tech-vision/` directly. All upstream knowledge flows
  through `kpack`.
- Modify `sources/`, `src/`, `tasks/`, `roadmap/`. Implementation status is
  detected, not changed.
- Spawn agents. C4 export is pure rendering.

## Design notes

**Why Structurizr DSL and not JSON or PlantUML?** DSL is the canonical
Structurizr authoring format — diffable, reviewable in PRs, renderable by
both Structurizr Lite and the Structurizr CLI without conversion. JSON is
secondary, machine-only. PlantUML loses the model/view separation that
makes Structurizr useful here.

**Why ADRs as `properties` and not `!docs`?** `!docs` requires the actual
markdown files to be reachable from the DSL workspace. We deliberately do
NOT clone the product knowledge repo into this repo — `kpack` is the only access
point. Properties pointing at GitHub URLs preserve traceability without
breaking the read-only contract.

**Why detect implementation from the filesystem instead of asking
`kpack`?** `kpack` describes the business model, which is repo-agnostic.
The point of the implementation overlay is to show how far THIS working tree
has gotten — that signal lives in `sources/` and `src/`, nowhere else.

**Why no auto-render?** Rendering Structurizr Lite requires Docker (or Java
+ the CLI jar). The skill stays declarative and stack-independent; the user
picks whichever viewer they prefer. Add `--serve` later if the manual
docker-run step turns out to be a recurring friction point.
