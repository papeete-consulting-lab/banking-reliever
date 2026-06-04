---
name: harness-backend
description: >
  Entry-point that adds (or refreshes) the **contract harness** of a backend
  microservice produced by either the `implement-capability` agent (.NET 10)
  or the `implement-capability-python` agent (Python 3.12+ / FastAPI).
  Resolves the capability, the active branch / worktree, detects the target
  stack from the TECH-TACT ADR (`tactical_stack[0].tags`) and the on-disk
  layout under `sources/{capability-name}/backend/`, then spawns the
  `harness-backend` agent (a senior contract / API engineer) to scaffold the
  stack-specific harness project (a `*.Contracts.Harness/` .NET project on
  .NET stacks, or a `{namespace}_{capability_module}_contracts_harness/`
  Python package on Python stacks), generate `openapi.yaml` (OpenAPI 3.1)
  and `asyncapi.yaml` (AsyncAPI 2.6) under `contracts/specs/`, and validate
  strict alignment between the specs, the Process Modelling layer consumed via
  `kpack process <CAP_ID>` (logically `process/{capability-id}/`:
  `commands.yaml`, `read-models.yaml`, `bus.yaml`, `api.yaml`,
  `schemas/*.schema.json`), and the BCM corpus
  consumed via `kpack pack <CAP_ID> --deep` (resources, resource events,
  business events, business / resource subscriptions, carried objects, FUNC
  / URBA / TECH-STRAT ADRs).

  The two generated spec files are stack-agnostic: regenerated from the
  same process + BCM inputs, they are byte-identical across .NET and Python
  implementations of the same capability (modulo the `servers.url` port and
  the `generated.at` timestamp). Only the harness tool itself, its build
  gate (MSBuild on .NET, pytest + `uv run` on Python), and the runtime
  endpoint glue (`/openapi.yaml`, `/asyncapi.yaml`, `/contracts/lineage`)
  are stack-specific.

  Both generated specs carry a top-level `x-lineage` block (capability +
  bcm + process + generated metadata) plus per-operation, per-message, and
  per-channel `x-lineage` extensions. Lineage is bidirectional — every
  operation traces back to a `process/` source AND a `kpack` source —
  so reviewers, consumers, observability tooling, and data-catalogue
  ingestion can resolve any spec entry to its definitional origin.

  The skill targets **non-CHANNEL zones only** (BUSINESS_SERVICE_PRODUCTION,
  SUPPORT, REFERENTIAL, EXCHANGE_B2B, DATA_ANALYTICS, STEERING). For
  CHANNEL-zone tasks (BFF + frontend), the BFF contract is already
  enforced by `create-bff`; a future `harness-bff` skill would extend the
  same lineage pattern there.

  Supports `--branch <slug>` or `--env <slug>` to operate in a specific
  worktree. Supports `--gen` (default — regenerate specs and validate) and
  `--validate` (no regeneration; only assert that the committed specs are
  in sync with the process model (via `kpack process`), kpack, and the
  running controller / consumer surface).

  Trigger this skill whenever the user says: "harness-backend", "harness for
  CAP.*", "regenerate the contracts for X", "regenerate openapi for X",
  "regenerate asyncapi for X", "refresh the api spec", "validate the
  contract harness", "lineage drift on X", "process changed — refresh the
  spec", or any phrasing requesting the contract surface of a backend
  microservice be re-derived or validated. Also trigger proactively after
  `implement-capability` finishes (Path A) — both `/code` (Step 2.5) and
  `/fix` (Step 3.5) invoke this skill automatically — and after `/process
  <CAP_ID>` evolves the model so the spec needs to follow.
---

# Harness-backend — Contract Harness Entry-Point

You are the entry-point that ensures a backend microservice produced by the
`implement-capability` agent (.NET) or `implement-capability-python` agent
(Python) has a fresh, lineage-rich, strictly-aligned contract surface
(OpenAPI 3.1 + AsyncAPI 2.6). You do not generate the specs yourself — you
resolve the context, detect the target stack, and dispatch the
`harness-backend` agent.

> **Process model — consumed read-only via `kpack process`.** The DDD
> process model (aggregates, commands, policies, read-models, bus topology,
> JSON Schemas) is authored by the `/process` skill in the **reliever-knowledge**
> repo and consumed here **read-only** via `kpack process <CAP_ID>` — exactly
> like the BCM corpus via `kpack pack`. It does not live in this repo, so
> there is nothing to guard locally and nothing to write under `process/`. If
> the model is wrong, stop and tell the user to run `/process <CAPABILITY_ID>`
> in the reliever-knowledge repo and merge its PR, then re-run this skill.

---

## Step 0 — Resolve the Input

The user gives a capability ID, a TASK, a branch, or none. Resolve in this
order, using the shape `/code` and `/test-business-capability` already
follow:

| Input form           | Example                               | What to extract                                                                                  |
|----------------------|---------------------------------------|--------------------------------------------------------------------------------------------------|
| Capability ID        | `/harness-backend BNK.RLVR.CAP.BSP.001.SCO`    | use the ID directly; resolve worktree from current branch (or `--branch`) |
| Task ID              | `/harness-backend TASK-003`           | read TASK frontmatter to get capability_id; resolve worktree from `feat/TASK-003-*` |
| Branch slug          | `/harness-backend --branch feat/TASK-003-bsp-sco` | derive TASK-003 → capability_id from the TASK file in that worktree |
| No argument          | `/harness-backend` after `/code`     | read the current working branch / worktree, locate the active TASK |

End Step 0 with these resolved values:

1. **`CAPABILITY_ID`** (e.g. `BNK.RLVR.CAP.BSP.001.SCO`).
2. **`CAPABILITY_NAME`** (kebab — derived from `kpack pack <CAP_ID>
   --compact | jq -r '.slices.capability_self[0].name'`).
3. **`WORKTREE_ROOT`** — the directory housing the .NET solution (either
   the main repo root, or `/tmp/kanban-worktrees/TASK-NNN-*/` when
   `--branch` is specified).
4. **`BACKEND_DIR`** — `${WORKTREE_ROOT}/sources/${CAPABILITY_NAME}/backend/`.
5. **`MODE`** — `gen` (default) or `validate` (from `--validate`).

---

## Step 1 — Verify Prerequisites (mandatory)

```bash
# 1. The process model must resolve for this capability (authored upstream in
#    reliever-knowledge, consumed read-only via `kpack process`).
if ! kpack process "${CAPABILITY_ID}" --compact >/tmp/process-model.json 2>/tmp/process-model.err; then
  echo "❌ No process model for ${CAPABILITY_ID} — run /process ${CAPABILITY_ID} in reliever-knowledge and merge its PR."
  cat /tmp/process-model.err
  exit 1
fi
# Required model slices (use .parsed, fallback .raw — commands/read-models are often parsed:null)
jq '{
  commands:     (.model.commands     != null),
  bus:          (.model.bus           != null),
  api:          (.model.api           != null),
  read_models:  (.model["read-models"] != null),
  schemas:      (.schemas | length)
}' /tmp/process-model.json

# 2. The microservice must already be scaffolded by implement-capability* —
#    detect the stack from on-disk layout
if   ls "${BACKEND_DIR}/"*.sln 2>/dev/null | grep -q .; then
  LANG=dotnet
  ls "${BACKEND_DIR}/src/"*.Presentation/Program.cs
elif test -f "${BACKEND_DIR}/pyproject.toml"; then
  LANG=python
  ls "${BACKEND_DIR}/src/"*/presentation/app.py
else
  echo "❌ No .NET solution or Python pyproject.toml under ${BACKEND_DIR} — run /code TASK-NNN first."
  exit 1
fi
echo "Detected stack: ${LANG}"

# 3. Cross-check with the TECH-TACT hint (advisory — disk wins, but a
#    contradiction means /code's language router has a bug worth surfacing)
kpack pack ${CAPABILITY_ID} --compact > /tmp/pack-harness.json
TACT_TAGS=$(jq -r '.slices.tactical_stack[0].tags // [] | join(",")' /tmp/pack-harness.json)
case "$TACT_TAGS" in
  *python*|*fastapi*|*starlette*)        HINT=python ;;
  *dotnet*|*.net*|*csharp*|*aspnet*)     HINT=dotnet ;;
  *)                                     HINT=unknown ;;
esac
if [ "$HINT" != "unknown" ] && [ "$HINT" != "$LANG" ]; then
  echo "⚠ TECH-TACT hint ($HINT) contradicts on-disk layout ($LANG) — likely a /code routing bug. Proceeding with $LANG."
fi

# 4. The capability must be non-CHANNEL
ZONE=$(jq -r '.slices.capability_self[0].zoning' /tmp/pack-harness.json)
case "$ZONE" in
  CHANNEL) echo "❌ harness-backend does not handle CHANNEL — use create-bff instead"; exit 1 ;;
  BUSINESS_SERVICE_PRODUCTION|SUPPORT|REFERENTIAL|EXCHANGE_B2B|DATA_ANALYTICS|STEERING) ;;
  *) echo "❌ unknown zone $ZONE"; exit 1 ;;
esac

# 5. kpack returns no warnings and the required slices are non-empty
jq '{
  warnings,
  emitted_resource_events:  ([.slices.emitted_events[]?  | select(.layer=="resource")] | length),
  consumed_resource_events: ([.slices.consumed_events[]?  | select(.layer=="resource")] | length),
  carried_objects:          (.slices.carried_objects       | length),
  emitted_business_events:  ([.slices.emitted_events[]?  | select(.layer=="business")] | length),
}' /tmp/pack-harness.json
```

If any prerequisite fails, stop and explain the gap clearly:

| Failure                                              | Resolution                                                        |
|------------------------------------------------------|-------------------------------------------------------------------|
| `kpack process <CAP>` does not resolve            | run `/process <CAPABILITY_ID>` in reliever-knowledge and merge its PR first |
| Neither `.sln` nor `pyproject.toml` under `BACKEND_DIR` | run `/code TASK-NNN` first (Path A scaffolds the microservice) |
| Zone is CHANNEL                                      | this skill is non-CHANNEL only — no action                        |
| `pack.warnings` non-empty / required slice empty     | fix the upstream BCM in `reliever-knowledge` (out of scope here)   |

---

## Step 2 — Diff the Process Model Against the Last Harness Run (idempotency)

If `${BACKEND_DIR}/contracts/specs/openapi.yaml` already exists, compare its
top-level `x-lineage.process.version` with the current process-model version
from the `kpack process <CAP_ID>` envelope (`.corpus.ref`):

- **Same version + `--validate` mode** → run the harness validator only,
  expect drift = 0.
- **Same version + default mode** → still re-run `gen` to refresh `generated.at`
  (cheap, idempotent). The diff should be limited to that timestamp.
- **Different version** → process model evolved since the last harness run.
  Tell the user: "Process model is at `vX.Y.Z`, last harness was at `vA.B.C`.
  Will regenerate." Proceed to Step 3.

If `--validate` is set and the version differs, **do not generate** — exit
with a clear error pointing the user at the default mode.

---

## Step 3 — Spawn the `harness-backend` Agent

Use the `Agent` tool. The agent is the senior engineer that owns the
contract harness. Pass the full resolved context as a self-contained
prompt:

```
Agent({
  subagent_type: "harness-backend",
  description: "Contract harness for ${CAPABILITY_NAME}",
  prompt: """
   Mode: ${MODE}        # gen | validate
   Stack:           ${LANG}              # dotnet | python — confirm on entry via §0.1
   Capability ID:   ${CAPABILITY_ID}
   Capability Name: ${CAPABILITY_NAME}
   Worktree root:   ${WORKTREE_ROOT}
   Backend dir:     ${BACKEND_DIR}

   Inputs you must read (read-only):
     - the process model via `kpack process ${CAPABILITY_ID} --compact`:
         .readme, .model.aggregates, .model.commands, .model.policies,
         .model["read-models"], .model.bus, .model.api (use .parsed, fallback
         .raw when null), and .schemas["*.schema.json"]. (Logically the
         process/${CAPABILITY_ID}/{README.md,*.yaml,schemas/*.schema.json}
         files, authored upstream in reliever-knowledge.)
     - kpack pack ${CAPABILITY_ID} --deep --compact

   Existing service under ${BACKEND_DIR}:
     - .NET stack (LANG=dotnet):
         ${Namespace}.${CapabilityName}.sln
         src/${Namespace}.${CapabilityName}.{Domain,Application,Infrastructure,
                                              Presentation,Contracts}/
     - Python stack (LANG=python):
         pyproject.toml + uv.lock
         src/{namespace}_{capability_module}/{domain,application,infrastructure,
                                                presentation,contracts}/

   Outputs you must produce (write):
     - .NET: src/${Namespace}.${CapabilityName}.Contracts.Harness/    (new project)
       Python: src/{namespace}_{capability_module}_contracts_harness/  (new package)
     - contracts/specs/openapi.yaml                            (OpenAPI 3.1 + x-lineage)
     - contracts/specs/asyncapi.yaml                           (AsyncAPI 2.6 + x-lineage)
     - contracts/specs/lineage.json                            (top-level lineage block)
     - contracts/specs/harness-report.md                       (validation verdict)

   Stack-specific wiring:
     - .NET:
         * dotnet sln add src/${Namespace}.${CapabilityName}.Contracts.Harness
         * Edit Presentation Program.cs to mount /openapi.yaml, /asyncapi.yaml,
           /contracts/lineage endpoints (do not rewrite the file).
         * Edit Presentation .csproj to copy contracts/specs/* into bin output.
         * Add an MSBuild target on the Presentation project that invokes the
           harness `validate` command BeforeTargets="Build", failing the
           build on drift.
     - Python:
         * Append the harness package to [tool.hatch.build.targets.wheel].packages
           in pyproject.toml.
         * Add a [project.scripts] entry for the harness CLI
           ({namespace}-{capability-kebab}-harness).
         * Add a [project.optional-dependencies] `harness` extra with
           PyYAML / jsonschema / openapi-spec-validator / deepdiff.
         * Edit src/{namespace}_{capability_module}/presentation/app.py to
           mount FastAPI routes for /openapi.yaml, /asyncapi.yaml,
           /contracts/lineage (do not rewrite the file).
         * Add tests/test_contracts_harness.py — a pytest gate that calls
           the harness `validate` subcommand and fails on drift (this is
           the Python equivalent of the MSBuild ContractsHarness target).
         * Edit Dockerfile to `COPY contracts/ ./contracts/`.

   Hard rules:
     - The process model is READ-ONLY and is fetched via `kpack process
       ${CAPABILITY_ID}` — authored upstream in reliever-knowledge, never on
       disk here. There is nothing to write under process/.
     - Lineage closure (process AND bcm) is non-negotiable: every operation
       in openapi.yaml AND every channel/message in asyncapi.yaml carries
       an x-lineage block resolving to a process source + a kpack source.
     - Spec ↔ runtime alignment: every controller action / consumer must
       map to an OpenAPI / AsyncAPI operation, and vice versa.
       (.NET: Assembly.LoadFrom + reflection. Python: import create_app()
       in a subprocess + walk app.routes / aio-pika queue declarations.)
     - Strict TECH-STRAT-001 conformance: routing keys are <EVT.…>.<RVT.…>,
       only RVT.* are autonomous bus messages, exchange-per-L2.
     - The two emitted spec files are stack-agnostic — same capability ↔
       byte-identical openapi.yaml / asyncapi.yaml across .NET and Python
       implementations (modulo the servers.url port and generated.at).

   Failure handling:
     - If a closure check fails, return a structured failure report listing
       the gap (dangling process_source, missing controller, BCM warning).
       Do not auto-fix the microservice — that's the implementation
       agent's remediation loop (implement-capability or
       implement-capability-python depending on stack).
     - If the on-disk stack contradicts the LANG hint above, abort and
       report — likely a /code routing bug.
     - You never write to the process model — it is served read-only by
       `kpack process` from reliever-knowledge. If you find yourself trying
       to write a process artifact, stop and report.

   Final output:
     - contracts/specs/{openapi.yaml,asyncapi.yaml,lineage.json,harness-report.md}
     - Tell the caller (this skill) the resolved stack, the per-source
       coverage counts, and the drift verdict.
  """
})
```

---

## Step 4 — Report to the User

Once the agent completes, summarise its report:

> "Contract harness for `<CAPABILITY_ID>` is in `<BACKEND_DIR>/contracts/specs/`:
> - `openapi.yaml` (OpenAPI 3.1) — N commands + M queries — full lineage ✅
> - `asyncapi.yaml` (AsyncAPI 2.6) — P publish + Q subscribe — full lineage ✅
> - `lineage.json` — top-level lineage block (capability + bcm + process)
> - `harness-report.md` — closure verdict
>
> Process closure: ✅ N/N items covered.
> BCM closure:     ✅ N/N items covered.
> Runtime alignment: ✅ N/N controllers + consumers reconciled.
> Drift vs committed: 0 lines.
>
> The running service serves its own specs at:
>   GET http://localhost:{COMPONENT_PORT}/openapi.yaml
>   GET http://localhost:{COMPONENT_PORT}/asyncapi.yaml
>   GET http://localhost:{COMPONENT_PORT}/contracts/lineage"
> (COMPONENT_PORT = deterministic, kind=api, per the Deployment contract in CLAUDE.md)

If the agent returned a failure report, surface the gap exactly as it came
back, and offer the right remediation:

| Gap reported                                       | Remediation                                                                                       |
|----------------------------------------------------|---------------------------------------------------------------------------------------------------|
| Dangling `x-lineage.process.*` reference           | re-run `/process <CAPABILITY_ID>` in reliever-knowledge to amend the model, then merge its PR      |
| Dangling `x-lineage.bcm.*` reference               | fix BCM upstream in `reliever-knowledge`                                                           |
| Missing HTTP route for an OpenAPI path             | re-run `/code TASK-NNN` — implement-capability(-python) missed a controller / FastAPI route       |
| Missing consumer for an AsyncAPI subscribe         | re-run `/code TASK-NNN` — bus subscription not wired (MassTransit on .NET / aio-pika on Python)   |
| Drift between generated and committed specs        | run `/harness-backend <CAPABILITY_ID>` (default mode) and commit the diff                          |
| `LANG` hint contradicts on-disk layout              | fix the TECH-TACT ADR or the `/code` language routing (`kpack` tactical_stack[0].tags)         |

---

## Operational Notes

- **Idempotent.** Re-running the skill with no process / bcm changes
  produces identical specs (modulo the `generated.at` timestamp).
- **Cheap to run.** The harness only reads files and shells out to
  `kpack`; it does not bring up MongoDB / RabbitMQ. Safe to call
  inside a build hook.
- **Branch-aware.** When invoked with `--branch <slug>`, the skill resolves
  artifacts from `/tmp/kanban-worktrees/TASK-NNN-{slug}/` so an in-flight
  PR's harness can be regenerated without checking out the branch in the
  main worktree.
- **CI-friendly.** In CI, run with `--validate`. The harness exits non-zero
  if any closure / runtime / drift check fails — the PR pipeline fails
  fast on contract regressions.
- **Composition.** `/code` (Path A) calls this skill automatically as the
  step right after `implement-capability` succeeds, so a fresh microservice
  is always shipped with its harness. Path C (contract-stub) also calls
  this skill since the stub publishes events whose payloads are wire
  contracts.
