---
name: sketch-miro
description: >
  Renders every process-modelled capability (enumerated via `kpack process
  <CAP_ID> --list`) as a single Event-Storming-style Miro board via Miro's official REST
  API. Idempotent — re-runs update the same widgets in place rather than
  producing duplicates. Aggregates (yellow), commands (blue), domain events
  (orange), policies (violet), read-models (green), and consumed upstream events
  (faded orange) are laid out as one frame per L2 capability, with connectors
  wiring policy → command → aggregate → event flows. Outputs the live board URL
  to a `reliever-miro.url` sidecar and a state file (`.reliever-miro.state.json`),
  both kept next to the bundled script, used as the idempotency ledger between
  process artifact identifiers and Miro widget IDs.
  Trigger on: "sketch-miro", "/sketch-miro", "draw the miro board", "miro board
  for process", "event storming board", "render process to miro", "update miro",
  "regenerate the miro board", "sync miro from process".
---

# /sketch-miro — Event Storming sketch on a real Miro board

Renders every process-modelled capability as a single Miro board, in the
Event Storming visual idiom. **Output is a live board on Miro.com**, not a
local `.rtb` file — see the design note at the bottom for why.

## Position in the pipeline

`/sketch-miro` consumes the process model read-only via `kpack process`
(authored by `/process` in the **reliever-knowledge** repo) and produces a
sharable Miro board. The process model does not live in this repo, so there is
nothing to write under `process/`. The only files the skill writes are two
sidecars kept **next to the bundled script**: `reliever-miro.url` (the board
URL, human readable) and `.reliever-miro.state.json` (the artifact→widget
identity map). No sentinel or guard is involved.

Re-runs are idempotent. The skill computes the target widget set from the
process model, compares it to the state file, and emits the minimum set of
CREATE / UPDATE / DELETE calls.

---

## Step 0 — Prerequisites

Verify the Miro access token is in the environment:

```bash
[ -n "$MIRO_ACCESS_TOKEN" ] && echo "token present" || echo "MISSING"
```

If absent, stop and tell the user:

> `MIRO_ACCESS_TOKEN` is not set. Create a Miro app at
> https://miro.com/app/settings/user-profile/apps , generate a developer
> token with `boards:read` and `boards:write` scopes, then export it:
>
>     export MIRO_ACCESS_TOKEN="..."
>
> Re-run `/sketch-miro` once the token is available.

Verify Python dependencies:

```bash
python3 -c "import yaml, requests" 2>&1
```

If `requests` is missing: `pip install requests pyyaml`.

---

## Step 1 — Parse arguments

The skill accepts:

| Form | Behavior |
|---|---|
| `/sketch-miro` | Sync ALL process-modelled capabilities (via `kpack process <CAP_ID> --list`) to the board |
| `/sketch-miro CAP.<…>` | Sync ONE capability only — touches that frame, leaves the rest of the board alone |
| `/sketch-miro --dry-run` | Print the change plan (CREATE / UPDATE / DELETE counts and a sample of each), make no API call |
| `/sketch-miro --rebuild` | Delete every widget in the state file and rebuild from scratch — costs API calls but heals drift |

`--rebuild` requires the user to confirm before proceeding (it is destructive on the board).

No sentinel or write-guard is involved: the process model is consumed read-only
via `kpack process` and the only files written are the two sidecars next to
the bundled script.

---

## Step 2 — Run the script

Delegate the heavy lifting to the bundled Python script. It handles
discovery (via `kpack process`), model parsing, API calls, rate-limit
retries, idempotency via the sidecar state file, and a final summary printed to
stdout.

```bash
python3 .claude/skills/sketch-miro/sketch_miro.py [--dry-run] [--cap CAP.<…>] [--rebuild]
```

The script:

1. Reads `MIRO_ACCESS_TOKEN` from the environment.
2. Loads `.reliever-miro.state.json` (next to the script, or starts fresh if absent).
3. If no `board_id` is in state, creates a new board named "Reliever — Event Storming (process layer)" and stores its id.
4. Enumerates capabilities via `kpack process <CAP_ID> --list` (the positional id only supplies the corpus context; or only the one passed via `--cap`).
5. For each capability, fetches its model with `kpack process <CAP> --compact` and reads the `aggregates`, `commands`, `policies`, `read-models`, `bus` slices.
6. Computes a deterministic widget set: one frame per capability, lanes per kind (event / command / aggregate / policy / read-model), and connectors derived from `accepted_by`, `issues`, `emits`, and the bus subscriptions.
7. Diffs against the state file:
   - artifact in target & in state → **PATCH**
   - artifact in target & not in state → **CREATE** (record the widget id)
   - artifact in state & not in target → **DELETE** (drop from state)
8. Persists `.reliever-miro.state.json` and `reliever-miro.url` next to the script.
9. Prints a summary: counts per kind, board URL, any rate-limit retries.

Pass the script's stdout straight to the user — it is the canonical run report.

---

## Step 3 — Validate the result

After the script returns, surface to the user:

- The board URL (from the `reliever-miro.url` sidecar next to the script).
- The CREATE / UPDATE / DELETE counts.
- Any warnings the script printed (a missing schema reference, a frame
  overflow, an upstream-event subscription with no matching local policy).

If the script aborted mid-run because of an HTTP error from Miro:

- 401 — token expired or wrong scopes. Suggest regeneration.
- 403 — token lacks `boards:write` scope, or the user's Miro plan does not
  permit the operation (free tier has board-creation limits).
- 429 — rate-limited. The script already retries with backoff; if it still
  failed, suggest re-running in a few seconds. State file is safe — partial
  runs are recoverable.

Never delete the state file or the URL file on error. They are the only way
to recover idempotency.

---

## Step 4 — Announce

No teardown is needed (no sentinel was posed). Announce:

> "Miro board synchronised — `<URL>`. Created `<n>`, updated `<m>`, deleted
> `<k>` widgets across `<c>` capabilities. State persisted in
> `.reliever-miro.state.json` next to the script."

---

## Layout convention

The script renders the Process Modelling layer in the Event Storming visual
vocabulary. One frame per L2 capability, arranged in a 2-column grid:

```
┌─────────────────────────────────────────────────────────────┐
│  CAP.<ID> — <name>   [L2 · <ZONE>]                          │
├─────────────────────────────────────────────────────────────┤
│ EVENTS   (orange)    RVT.* emitted by aggregates            │
│         (light-orange) RVT.* consumed (external)            │
├─────────────────────────────────────────────────────────────┤
│ COMMANDS (blue)      CMD.* accepted by aggregates           │
├─────────────────────────────────────────────────────────────┤
│ AGGREGATES (yellow)  AGG.* — one large sticky per aggregate │
├─────────────────────────────────────────────────────────────┤
│ POLICIES (violet)    POL.* — listens to events, issues CMD  │
├─────────────────────────────────────────────────────────────┤
│ READ MODELS (green)  PRJ.* + QRY.* — projections & queries  │
└─────────────────────────────────────────────────────────────┘
```

Connectors:

- POL → CMD (policy issues command, dashed line)
- CMD → AGG (command accepted by aggregate, solid)
- AGG → RVT (aggregate emits resource event, solid arrow)
- upstream-RVT (external lane) → POL (subscription, dashed)

Cross-capability connectors are drawn between frames when a `RVT.*` emitted
by one local frame is the `binding_pattern` of another frame's
subscription. This is the part that turns four isolated frames into a
single end-to-end Event Storming sketch.

---

## Design notes

**Why not produce a `reliever-miro.rtb` directly?** The `.rtb` format
is a ZIP archive whose internal JSON schema is proprietary, undocumented,
and recently encrypted on Miro's side. Hand-crafted `.rtb` files routinely
fail to import with "Something went wrong". The official, supported path is
the REST API, which produces a real shared board the team can open
immediately. The board URL is committed in the `reliever-miro.url` sidecar
next to the script so a teammate cloning the repo discovers it on first read.

**Why a sidecar state file?** Miro's REST API does not expose a
custom-metadata field on stickies that survives PATCH cleanly. The simplest
robust strategy is an external map: `.reliever-miro.state.json` (next to the
script) stores `{board_id, widgets: {<artifact_id>: <miro_widget_id>}}`. This
makes re-runs O(n) and avoids fragile content-prefix tagging.

**Why keep the sidecars next to the script?** The process model no longer
lives in this repo — it is served read-only by `kpack process` from
`reliever-knowledge`. So there is no `process/` folder to anchor the sidecars
to, and no write-guard to negotiate; the script's own directory is the natural,
stable home for its idempotency ledger and the board URL.
