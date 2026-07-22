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
Plan  →  Package  →  Task  →  Sub-task
```

Exactly four levels, with **obligations** as the accounting surface inside a sub-task — not a
fifth level. **No nesting at any level**: a package never contains a package. Depth is fixed
so the bound on assembled context stays *structural* rather than an arbitrary depth limit, and
so the GUI has a shape it can draw.

**There is one vocabulary, not two.** Planning work and build work are the same kinds of
chunk, stored in different tables. The methodology's ordered steps — what v1 and the frozen
plan call *stages* — are the **standard package set** for planning work: eight packages every
plan instantiates, versus build packages declared per plan. `stage` is retired as a word.

**A gate is named by its container**, never by a kind of its own: plan gate, package gate,
task gate, sub-task gate. A gate locks on the outstanding problems bound to *its own*
container, which is what makes D9's hard-lock generalise without special cases.

**Validation and gating happen at sub-task level only** (owner, 2026-07-21). A sub-task is
done when a passing `verify_completion` covers all its obligations — never on partial credit.
Sub-dividing a sub-task into smaller *work* items was considered and **rejected**: the frozen
plan's remedy for an over-large sub-task is `split_subtask`, which produces real sub-tasks with
their own briefs and their own verification, and obligations already subdivide a sub-task for
accounting. A second, ungated subdivision would give one thing two different breakdowns and
invite "3 of 4 done" to be read as progress on a sub-task that is still worth zero. If an
executor works through a sub-task in steps, nothing outside observes those steps and they need
no name from us.

| Level | Declared or derived | Cardinality | Stored in |
|---|---|---|---|
| Plan | — (the root) | 1 per workspace | — |
| Package | **declared** | 1..n per plan | `packages` |
| Task | derived | 1..n per package; exactly 1 package each | `tasks` |
| Sub-task | derived | 1..n per task | `subtasks` |
| Obligation | enumerated once, frozen | 1..n per sub-task | `obligations` |

### Two layers, and why only one of them is generic

- **Planning layer** — `plan_rows`, generic, JSON content. Every row type shares one table so
  supersession lineage, typed links and provenance work identically across twenty-odd types
  (DEVIATIONS.md **D3**).
- **Execution layer** — `packages`, `tasks`, `subtasks`: real tables, real foreign keys.

The split is deliberate, and F20 and F24 are the evidence for it: both are **relations that
vanished when v1's typed tables were flattened into generic rows**. A generic row table makes
rows the unit of migration and edges invisible. The planning layer earns its genericity and
its two known losses are repaired as typed links; the execution structures, which carry the
build's own relations, stay typed.

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

### `belongs_to` — one name for containment, everywhere
Every *this row's owning parent* relation is `edge_type='belongs_to'`, whatever the two row
types are. v1 spelled the same relation seven ways — `use_case_id`, `step_id`, `entity_id`,
`machine_id`, `dep_id`, `component_id`, `consumer_component_id` — which is this document's
subject matter in a different column. The parent's row type disambiguates, so a second edge
name buys nothing: `uc_steps:4 belongs_to use_cases:2` is unambiguous.

**The edge vocabulary is closed** — `engine/models.py`'s `EDGE_TYPES`, enforced at submission.
`links.edge_type` defaults to `'links'` and accepts any string, so before this a misspelled
edge type produced a durable relation that no traversal looked for (F28). Which child types
*require* a parent is methodology data (`rev3/manifest.yaml`), never engine knowledge.

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

## Not a level: journal entry

`requirements:56` / `requirements:60` — a **journal entry** is a journal-granularity event:
a row submission, a decision, a brief served, a sub-task status change, an informal learning.
It is what "durably recorded the moment it completes" applies to.

This is an *episode* vocabulary, not a *structure* vocabulary, and it does not belong on the
hierarchy above. Keep the two apart: a sub-task is a thing that exists; a journal entry is
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
| **stage** | package | The methodology's ordered steps are the standard package set for planning work — the same kind of chunk as a build package, in a different table. Retired 2026-07-21; methodology assets are `package1_context.md` … `package8_freeze.md` at **rev 3**. |
| **session** | (nothing) | Not an entity, and since 2026-07-22 not in the data either: its one occurrence was the writer lock's holder name, removed with the lock (see `engine/storage.py`). No table, no rows, no lifecycle, no exception. Where prose meant "the session decides", say **the planner** (the actor). |
| **phase** | package | Briefly proposed for this build's own units and rejected: it was a new word for something already defined. |
| **unit**, **unit of work** | journal entry, or sub-task | `requirements:56`/`60`'s "unit of work" is a *record of something that happened* — say **journal entry**. As a work chunk below sub-task, rejected outright (see above). |
| **work packet**, **chunk** | sub-task or package, per meaning | Informal synonyms that resolve to a defined level; pick the level. |

**Settled 2026-07-21, owner's decision: the retirement beats the quotation, even for a
contract's own error name.** `contracts:40` declares an error literally named
`PartsDontCover`, and `engine/errors.py`'s convention is that a contract's error name *is* the
class name. The class is `ObligationsNotCovered`. The convention is internal — no protocol, no
consumer outside the repo — so preserving the plan's spelling would have bought nothing and
cost a live retired word in the codebase, which is the carve-out this section already rejected
once. The frozen plan's name is recorded on the class docstring so a reader grepping the plan
still lands there. **The quotation rule covers prose, not identifiers.**

**Second instance, 2026-07-22: `components:14` is `session-service` in the frozen plan and
`engine/resume.py` here**, serving `ResumeService`. Same reasoning, applied to a component
name rather than an error name — `session` is retired as an identifier without exception, and
resuming is what the component is *for*. The plan's spelling heads the module docstring.

**No carve-outs.** An earlier draft kept "milestone" for this build's own M0–M8 and "stage" for
the methodology. Both exceptions were withdrawn by the owner on 2026-07-21, on the grounds that
a live technical word pollutes reasoning later no matter how narrowly its scope is documented.
**This build's own M0–M8 are build packages.** The only surviving occurrences of any retired
word are quotations inside `spec/v2/plan.md` and `engine/methodology/rev2/`, both read-only.

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
- No identifier contains `packet`, `milestone`, `part`, `project`, `stage`, `phase` or
  `session`.

### This rule is enforced, not merely stated

`tests/test_vocabulary.py` parses the banned list **out of the bullet above** and fails the
suite on any violating identifier in `engine/` or `tests/`. It reads this file rather than
carrying its own copy: a duplicated list drifts from the glossary, and a vocabulary rule with
two sources of truth is the bug it exists to prevent.

The check exists because the rule was broken the session after it was written (DEFECTS.md
**F27**), and the reason is worth keeping in view: **the read-only exception is also the
primary input.** `spec/v2/plan.md` is the one place retired words legitimately survive, and it
is also the document read immediately before writing every function — `contracts:40`'s own
signature is `parts: list[SubTaskSpec]`. Ranked by proximity to the moment of typing, the
exception beats the rule every time. A document cannot fix that; a check that runs on every
commit can.

Every exception is listed below **with its reason**, and adding one is a visible act — the
same friction shape as `requirements:79`'s waiver log and D8's promotion reason.

```vocabulary-exceptions
engine/briefs.py:PartsDontCover — contracts:40's declared error name, quoted; see the
    unresolved tension above. The only live `part` identifier in the codebase.
engine/gaps.py:parts — a local list of string fragments joined into a gap key; the English
    word, no relation to a split. Renamed on next touch of that file.
```
- `plan_rows.package` is the *planning* package ordinal (1..8, the standard set) and is a
  different table from `packages.id` (build packages) — the same concept in two layers.

---

## The one place this vocabulary meets the design spine

Mandatory package membership means the tool must not let a task go unpackaged — but choosing
*which* package is a judgment, and **the tool records judgment, it never exercises it**
(`decisions:12`). The split is the same one brief composition already uses
(`decisions:52`/`decisions:60`):

- the **tool** enforces the invariant (every task has a package) and refuses finalization
  without it;
- the **methodology** — a vendored package script, not generated text — instructs the driving
  session to propose a package cut and to lead the owner when none is offered;
- the **planning session** proposes; the **owner** decides.

A packaging heuristic inside the engine would be the tool having opinions about architecture,
which is the seed `M5_PLAN.md` §2.2 rejected a read-time relevance heuristic to avoid.

---

**Related:** DEVIATIONS.md D8, D12, D13; DEFECTS.md F23, F24; `decisions:63`, `findings:11`,
`requirements:79`.
