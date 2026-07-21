# Glossary — the v2 structural vocabulary

**Binding.** These are the only names for these things. Every field, reference, table,
constant, variable and piece of prose written from 2026-07-21 onward complies. Deviation is
not a style problem: two names for one thing is what produced `F23` (a coverage check with no
denominator) and `F24` (a lost ownership relation), and it is what makes a reader six months
out reason confidently about the wrong entity.

Established by the owner, 2026-07-21. Recorded as DEVIATIONS.md **D13**.

---

## The hierarchy

```
Plan  →  Package  →  Task  →  Sub-task  →  Obligation
```

Exactly four structural levels, plus obligations inside a sub-task. **No nesting at any
level** — a package never contains a package. Depth is fixed so that the bound on assembled
context stays *structural* rather than an arbitrary depth limit, and so the GUI has a shape
it can draw.

| Level | Declared or derived | Cardinality |
|---|---|---|
| Plan | — (the root) | 1 per workspace |
| Package | **declared** | 1..n per plan |
| Task | derived | 1..n per package; exactly 1 package each |
| Sub-task | derived | 1..n per task |
| Obligation | enumerated once, frozen | 1..n per sub-task |

---

## Definitions

### Plan
The root. The entire body of recorded planning judgment for one endeavour: every row, link,
gate result, finding and journal entry in one workspace. One plan per workspace. Carries the
lifecycle `state_machines:1` (draft → finalized → implementing → revising → complete).

*The plan **is** the project's record — "project" is not a separate thing and is not a term
we use.*

### Package
A **declared**, named grouping of tasks: the level at which a human says "the GUI", "the
controller", "the persistence layer". The only level a person chooses rather than derives.

A package is a **row with an id**, owned and supersession-tracked like any other — never a
free-text label. A free-text grouping key silently yields an empty context set on a typo, and
the sub-task quietly missing its mid-level context is exactly the failure `decisions:14`
measures. This is the mistake `milestone` made and the reason it is retired.

**Every task belongs to exactly one package.** Membership is mandatory, and finalization
refuses a plan with an unpackaged task. There is deliberately **no auto-created catch-all**
package: a single-package plan is legitimate when someone declares it, whereas a default
bucket is an escape hatch that quietly reproduces a three-level model while appearing to
satisfy the invariant.

Packages do not nest.

### Task
The work of realising one **component**: a unit of the architecture with a single stateable
responsibility. Derived — one task per live component row, never hand-assigned.

**`components:N` is this entity's spelling in the frozen plan** (`spec/v2/plan.md`), which is
read-only and cannot be rewritten. Task and component are one entity with one id space; where
the frozen spec says "component", read "task". New code says task.

Task membership of a contract is a typed link, `edge_type='belongs_to'` (F24 / D13).

### Sub-task
The atomic unit of executable work, and the node of the task graph (`entities:9`,
`state_machines:9`). The thing a brief is composed for and a code engine executes.

Derived at finalization: **one sub-task per contract** (`decisions:63`). After a split
(`contracts:40`) a sub-task instead owns a *subset of one contract's obligations*, with the
original retained as its lineage parent.

*A sub-task is sub- to a **task**. Before 2026-07-21 there was no Task and the prefix meant
nothing.*

### Obligation
One dischargeable commitment of a contract: the primary behaviour of its signature, or one of
its enumerated error conditions. The unit a split redistributes and a completion verifies.

Enumerated by the planning session at finalization and **frozen before any split**, so the
denominator of a coverage check is never chosen by the party being measured. Full rationale
in DEVIATIONS.md **D12**; the defect it fixes is **F23**.

### Brief
The immutable composed context for one sub-task, including its waiver log (`entities:13`,
`requirements:79`). No lifecycle: regeneration creates a new brief that supersedes the old by
reference, and the old stays frozen for defect forensics.

---

## Not a level: unit of work

`requirements:56` / `requirements:60` — a **unit of work** is a journal-granularity event:
a row submission, a decision, a brief served, a sub-task status change, an informal learning.
It is what "durably recorded the moment it completes" applies to.

This is an *episode* vocabulary, not a *structure* vocabulary, and it does not belong on the
hierarchy above. Keep the two apart: a sub-task is a thing that exists; a unit of work is
something that happened.

---

## Retired terms — do not use

| Retired | Use instead | Why |
|---|---|---|
| **project** | plan | No `Project` entity ever existed; the root is `Plan`. |
| **milestone** | package | Appeared in the frozen plan **only** in the phrase "milestone-time re-planning" — borrowed from the *failure* vocabulary, never an entity. Shipped in M5a as a free-text column with no owner or creation mechanism. |
| **packet** | sub-task | **Zero** occurrences in the frozen plan; our own coinage in `M5_PLAN.md` §2.3. M5a's own schema comment gave the duplication away: `scope_key` was documented as "packet **subtask id**". |
| **part** | sub-task | A "part" of a split is a sub-task, distinguished by which obligations it owns, not by being a different kind of thing. Acceptable in prose as "a sub-task produced by a split"; never a field, type or table name. |
| **component** | task | One entity, two spellings. `components:N` persists as the frozen plan's read-only spelling only. |
| **work packet**, **chunk** | sub-task or package, per meaning | Informal synonyms that resolve to a defined level; pick the level. |

**One deliberate survival.** "Milestone" remains correct for **this build's own** milestones —
M0 … M8 in `V2_BUILD_PLAN.md` §7 — and for the frozen plan's phrase "milestone-time
re-planning" (`decisions:8`, `decisions:14`). That is the *build process* and the *failure
vocabulary*, a different universe from the tool's domain model. Do not "fix" those. The rule is
narrow and exact: **milestone is never a level, a column, or a scope key.**

---

## Scope levels for context allocation

The attachment scope levels (DEVIATIONS.md **D8**, revised by **D13**) are the four
structural levels, broad to narrow:

```
plan  >  package  >  task  >  subtask
```

A sub-task's context is the union of its own attachments and those of every enclosing level.
Broadening an attachment requires a recorded reason the owner sees; narrowing is free (D8
§2.5). Four levels means four rungs to misplace an attachment on — the review surface is what
that buys, and it is why the promotion history is kept rather than overwritten.

`scope_key` is `''` at plan level and the row id of the package, task or sub-task otherwise.
**Never a name.**

---

## Naming rules for code

- Constants: `PLAN`, `PACKAGE`, `TASK`, `SUBTASK`.
- Columns: `package_id`, `task_id`, `subtask_id` — ids, never names.
- `subtask` is one word in identifiers (`subtask_id`, `SubTask`), hyphenated in prose
  ("sub-task"). This is the existing convention in `engine/`; it stays.
- No identifier contains `packet`, `milestone`, `part` or `project`.

---

## The one place this vocabulary meets the design spine

Mandatory package membership means the tool must not let a task go unpackaged — but choosing
*which* package is a judgment, and **the tool records judgment, it never exercises it**
(`decisions:12`). The split is the same one brief composition already uses
(`decisions:52`/`decisions:60`):

- the **tool** enforces the invariant (every task has a package) and refuses finalization
  without it;
- the **methodology** — a vendored stage script, not generated text — instructs the driving
  session to propose a package cut and to lead the owner when none is offered;
- the **planning session** proposes; the **owner** decides.

A packaging heuristic inside the engine would be the tool having opinions about architecture,
which is the seed `M5_PLAN.md` §2.2 rejected a read-time relevance heuristic to avoid.

---

**Related:** DEVIATIONS.md D8, D12, D13; DEFECTS.md F23, F24; `decisions:63`, `findings:11`,
`requirements:79`.
