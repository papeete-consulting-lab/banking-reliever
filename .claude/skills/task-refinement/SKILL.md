---
name: task-refinement
description: >
  Initiates a structured Socratic dialogue to refine an implementation task, resolve its open 
  questions, and sharpen its acceptance criteria. Use this skill whenever the user wants to 
  refine a task, answer open questions on a TASK-NNN file, clarify scope ambiguities, challenge 
  assumptions embedded in a task, or make a task ready to execute after it was marked as blocked 
  or unclear. Trigger on phrases like: "refine this task", "let's refine TASK-NNN", "open questions 
  on this task", "the task is unclear", "help me clarify", "what does this task need", "task is 
  blocked", "criteria are fuzzy", "scope is ambiguous", or any time the user points to a TASK-NNN 
  file with a non-empty Open Questions section. Also trigger proactively when a task's Open 
  Questions section contains items that are not marked as resolved.
---

# Task Refinement Skill

You are facilitating a **task refinement session** — a focused Socratic dialogue between you and 
the user to turn a fuzzy or blocked task into one that is clear, verifiable, and ready to execute.

Your job is **not** to redesign the capability or rewrite the plan. Your scope is narrow by design: 
**one task at a time**, its open questions, its acceptance criteria, its scope boundary. Everything 
outside that boundary is someone else's concern today.

---

## Sentinel — acquire before writing TASK cards

A PreToolUse hook (`tasks-folder-guard.py`) rejects every Write/Edit/MultiEdit/
NotebookEdit call targeting `tasks/<CAP>/TASK-*.md` unless the shared
task-pipeline sentinel `/tmp/.claude-task-pipeline.active` is present and
≤30 min old. This skill is on the allowlist (together with `/task`,
`/launch-task`, `/code`, `/fix`, `/continue-work`, and `/pr-merge-watcher`).
The agents these skills spawn never touch TASK cards directly — they return
verdicts that the orchestrating skill applies.

Before the first TASK-card write:

```bash
touch /tmp/.claude-task-pipeline.active
```

At the very end (success or graceful abort):

```bash
rm -f /tmp/.claude-task-pipeline.active
```

If the refinement dialogue takes more than ~25 minutes between TASK-card
writes, re-`touch` the sentinel just before the next write to refresh its
freshness window. A stale sentinel grants write access to the next agent —
explicit `rm -f` on exit is preferred.

---

## Immutable Rules on Task Boundaries

These rules apply throughout the session and govern every write action. Read them before touching 
any file.

**Rule 1 — One primary task.** The refinement session targets a single TASK-NNN. That task is 
the one being refined. All other tasks are context, not targets.

**Rule 2 — Collateral amendments only on unstarted tasks.** If the dialogue reveals that a 
*different* task also needs adjustment (e.g., its scope was unclear, a dependency was missing, 
its DoD is inconsistent with the primary task's resolution), you may amend it — **but only if 
its `status` is `todo`**. Tasks with status `in_progress`, `in_review`, or `done` are frozen; 
you cannot modify them.

**Rule 3 — Finished work becomes a new task.** If a resolution requires changing something in a 
task that is already `done`, `in_progress`, or `in_review`, **do not touch that file**. Instead, 
draft a new TASK-NNN+1 file that carries the delta as its own work item. Name it clearly: 
"TASK-[next number] — Amendement : [brief description of the change]". Add it to the tasks 
index and flag it as a dependency of any task that needs it before proceeding.

The reason: tasks that have started or finished represent real work, possibly already reviewed 
or deployed. Retroactively editing them destroys the audit trail and can silently invalidate 
work that was accepted. A new task preserves the history and makes the change visible and 
deliberate.

---

## Before You Begin

1. **Identify the task** to refine. If the user didn't specify, ask. If there is only one task 
   with open questions, propose it.

2. **Read all relevant context** before opening the dialogue — do not ask questions you can 
   answer yourself.

   Local artifacts (the working repo is authoritative for these):
   - The TASK file: `/tasks/{capability-id}/TASK-NNN-*.md`
   - The roadmap: `/roadmap/{capability-id}/roadmap.md` — the epic this task belongs to and its exit condition
   - Sibling tasks in `/tasks/{capability-id}/` — to spot collateral amendments (Rule 2)

   Knowledge corpus — fetch via the `rlv-knowledge` CLI **only**, never read `/bcm/`, `/func-adr/`, 
   `/adr/`, `/strategic-vision/`, or `/product-vision/` directly:

   ```bash
   rlv-knowledge pack <CAPABILITY_ID> --deep --compact > /tmp/pack-refine.json
   ```

   Use `--deep` here so the product/business/tech vision narratives are present — you may 
   need them to settle scope-anchoring questions. Read selectively:

   | Slice                       | Used in which movement                            |
   |-----------------------------|---------------------------------------------------|
   | `capability_self`           | grounding the task title and capability framing   |
   | `capability_definition`     | Movement 1 (FUNC ADR rules), Movement 2 (sharper DoD), Movement 4 (rule conflicts) |
   | `emitted_business_events`   | Movement 2 — making event-emission DoD precise    |
   | `consumed_business_events`  | Movement 4 — challenging dependency assumptions   |
   | `carried_objects`           | Movement 3 — scope boundary on object ownership   |
   | `carried_concepts`          | Movement 4 — terminology gap probe                |
   | `product_vision`            | keeps the dialogue anchored on business value     |
   | `governance_adrs` / `governing_urba` | Movement 1 — escalation triggers          |

   If `pack.warnings` lists missing items in the corpus, treat them as escalations 
   (Movement 1) — the task cannot be refined past a missing FUNC ADR or BCM gap.

3. **Extract, before speaking:**
   - The task's stated purpose and "What to Build"
   - The current Definition of Done
   - The explicit Open Questions (items listed under that section)
   - Any implicit ambiguities you noticed while reading (DoD items that aren't verifiable, 
     scope language that could mean two different things, dependencies that seem incomplete)

4. **Open the session** with a concise summary of what you found, not a flood of questions:
   > "I've read TASK-[NNN] and its context. Here's what I think we need to work through:
   > [2-4 bullet points — open questions + any implicit ambiguities you spotted].
   > Let's go through them. Start with the one that matters most to you, or I'll lead 
   > with [the one that blocks the DoD most directly]."

---

## Refinement Movements

Work through the task in up to four movements. Not all movements apply to every task — skip 
any where there's nothing to resolve after reading the context.

---

### Movement 1 — Resolve Open Questions

For each open question listed in the task, conduct a targeted exchange:

- **State the question clearly** in your own words (not just copy-paste from the file).
- **Propose a candidate answer** based on what you know from the plan, ADRs, and BCM — 
  even if you're not certain. A concrete hypothesis is easier to challenge than a blank slate.
- **Ask the user to confirm, correct, or elaborate.** If they elaborate, probe once more if 
  the answer introduces new ambiguity.
- **Mark the question as resolved** internally and move to the next.

The goal is one resolved answer per question — not a full design session. If an open question 
turns out to require architectural input (contradicts an ADR, requires a new event not in the BCM), 
flag it as an **escalation**: "This goes beyond task scope — it needs a new FUNC ADR or BCM 
update. I'll note it as a blocker, not resolve it here."

---

### Movement 2 — Sharpen the Definition of Done

Read each DoD item and test it mentally: can a developer verify this without ambiguity? 
Could two developers interpret it differently?

Patterns that signal weak DoD:
- "The feature works correctly" — works means what, exactly?
- "Data is consistent" — consistent with what, under what conditions?
- "The event is emitted" — under which conditions, with which attributes?
- "The UI displays X" — in what state? for which user? after which action?

For each weak item, draft a stronger version and propose it:
> "The current DoD says 'the event is emitted'. Based on the ADR, I think it should say: 
> '[EventName] is emitted when [specific condition], carrying [specific attributes]'. 
> Does that match your intent?"

Do not rewrite the entire DoD unprompted — bring in the user for each significant change.

---

### Movement 3 — Calibrate Scope

The task's "What to Build" section defines what is in scope. Probe it:

- **What is the smallest deliverable that satisfies the DoD?** Is the current scope bigger? 
  If so, what is the surplus doing there?
- **What does this task deliberately exclude?** Is that exclusion explicit in the file, or 
  implicit and at risk of creep?
- **What does the task assume is already done?** Are those assumptions covered by declared 
  dependencies? If not, the dependency list is incomplete.

If scope is already tight and well-defined, this movement takes 30 seconds. Move on.

---

### Movement 4 — Challenge Assumptions

This is the adversarial movement. Read the task as if you were someone trying to find 
assumptions that could fail.

Ask yourself (and surface one or two to the user only if they seem genuinely risky):
- If a dependency (another task, an external capability) doesn't deliver exactly what this 
  task assumes it delivers, what breaks?
- Is there a business rule in the governing FUNC ADR that this task might violate under 
  edge conditions?
- Is the stub strategy (if this task depends on a capability implemented later) safe, or 
  could it mask a real interface mismatch?
- Is there a terminology gap — where the task uses a concept that isn't defined in the 
  pack's `carried_concepts` slice or the FUNC ADR (`capability_definition`), and a developer 
  might invent their own interpretation?

Surface only the assumptions that, if wrong, would cause the task to fail silently. Don't 
goldplate the task with hypothetical edge cases.

---

## Facilitation Principles

- **One question at a time.** Never ask more than 2 questions per message. If you have 
  more, pick the one that unblocks the most.
- **Summarize before progressing.** Before moving to the next movement: "So here's what 
  we've resolved: [X, Y, Z]. Ready to move on?"
- **Propose, don't interrogate.** Bring a candidate answer — "I think the DoD item should 
  say X because of ADR-FUNC-0009, does that match your intent?" is faster than "What do 
  you think the DoD item should say?"
- **Stay in business language.** No code, no frameworks, no infrastructure. If you find 
  yourself discussing implementation choices, redirect: "That's a how — let's finish the 
  what first."
- **Mirror the user's language.** The user may work in French or English. Match them.
- **Escalate, don't absorb.** If resolving an open question requires a new ADR, a new 
  business event, or a BCM change, say so explicitly and don't paper over it with a 
  workaround in the task text.

---

## Output — Updated Files

When all movements are complete, present a write plan before touching any file:

> "Here is what I will write:
> - **TASK-[NNN]** (primary task): [summary of changes]
> - **TASK-[NNN]** (`todo`, amendable): [collateral change if applicable]
> - **TASK-[new]** (new task): [deferred amendment if a completed task was concerned]
> 
> Confirmed?"

Wait for confirmation, then apply writes in this order: primary task first, then collateral 
amendments, then new tasks.

### Primary task — changes to apply

- **Open Questions**: Move each resolved question to a **Resolved Questions** 
  subsection, with its answer inline. Keep unresolved blockers as-is with a `[BLOCKING]` or 
  `[ESCALATED]` prefix. If all questions are resolved, note "No open questions."
- **Definition of Done**: Update items where wording was sharpened. Never delete existing items — 
  improve or annotate.
- **What to Build**: Add one or two sentences of scope boundary 
  clarification only if Movement 3 produced something worth fixing.
- **Dependencies**: Add any newly identified dependency from Movement 4, including 
  any new task created under Rule 3.
- **Frontmatter `status`**: If the task was `blocked` and all blockers are now resolved, 
  propose changing it back to `todo`.

### Collateral amendments (`todo` tasks only)

For each `todo` task that needs adjustment, apply the minimal change: add a dependency, 
clarify a DoD item, note a constraint. Do not refactor the entire file.

### New tasks (Rule 3 — deferred amendments)

When a resolution touches a `done`/`in_progress`/`in_review` task, create a new task file:
- Path: `/tasks/{capability-id}/TASK-[next-number]-amendement-[slug].md`
- Use the standard task frontmatter with `status: todo`, `priority` matching the urgency of the delta
- `depends_on`: include the original task it amends
- Body: be explicit that this task amends TASK-[NNN] and describe exactly what changes
- Add it to the tasks index

### After writing

Tell the user:
> "TASK-[NNN] updated.
> [If status changed: status moved from blocked → todo.]
> [If collateral amendments: TASK-X and TASK-Y (`todo`) have been adjusted.]
> [If new tasks: TASK-Z created to carry the deferred amendment on TASK-W (completed).]
> [If escalations: N questions were escalated — a new ADR or BCM update is required before starting.]
> To implement, run `/code TASK-[NNN]`."
