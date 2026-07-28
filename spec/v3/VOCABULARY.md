# v3 vocabulary

**Status: a planning artefact.** It specifies what `GLOSSARY.md` becomes; it is not itself
enforced yet. `GLOSSARY.md` is parsed by a test that fails the suite on any identifier
containing a retired word, so changing it changes what the *current* code is held to. That is
build work and waits for the freeze.

Settled with the owner 2026-07-28, except where marked **open**.

---

## The hierarchy

```
Plan  →  Task  →  Behaviour
```

Three levels where v2 had four, and only the first two are levels work is assigned at.
**Nobody is ever handed a behaviour.**

| Level | Declared or derived | What it is |
|---|---|---|
| Plan | — (the root) | The entire recorded planning judgment for one endeavour |
| Task | derived | One externally-callable function plus the private helpers that exist only to serve it |
| Behaviour | enumerated at specification, frozen | One thing that function commits to doing: its main effect, or one specific error it raises |

### Why the levels changed

**Package is dead** — the word, the table, the ids, the level. Its two stated jobs were
grouping for navigation and scoping context. Navigation is a *view* problem, and a view may
overlap and be declared whenever the owner likes, whereas a build grouping must own each item
exactly once; those are different mechanisms wearing one name. Context scoping belonged to the
architecture, not to a hand-drawn grouping. The word also named two different id spaces, one
of them dead. **Labels** take over filtering and review; **dependencies** take over ordering.

*The one job that looked like it needed a package* was the checkpoint that says "drive the
system end to end before moving on" — the practice that caught something every time it was
used in v2. It does not need a declared grouping: it is **derived from the dependency graph.**
When a task completes and every task an externally-callable entry point depends on is now
done, that entry point has become exercisable end to end, and the tool demands it. Nothing is
declared, nothing owns anything, and it fires at the real moments rather than at boundaries
someone drew by hand.

**Sub-task is dead**, and v2's own code is the evidence. A v2 sub-task was exactly one
contract, which gave it two jobs and it failed both:

- *Being a servable size.* It wasn't — which is why v2 carries a whole splitting mechanism to
  cut an oversized sub-task into pieces. That mechanism exists only to compensate for the level
  being an architecture artefact rather than a build unit. A task that is one function plus its
  helpers is servable by construction and there is nothing to split.
- *Being the accounting denominator.* The split check was meant to reject a split whose pieces
  did not jointly cover the original's contracts. But every sub-task has exactly one contract
  and every piece of a split names that same contract, so the check passed unconditionally — a
  check that runs, passes and means nothing, which is worse than no check because it reports
  success. The remedy, invented mid-build, was **obligations** underneath. So v2 had already
  discovered that the real denominator lived a level below sub-task.

That level is **behaviour**. The machinery exists and works; it is called *obligation* in the
code today and is renamed, because "obligation" is jargon that has to be taught and
"behaviour" is not.

### Measured, so the sizing is not a feel

v2's engine holds **464 functions, median 12 lines, 209 of them private helpers, only three
over 100 lines.** So "one function" is the right order of magnitude — nothing like v2's build
unit, which ran from 90 to over 1,000 lines. But 209 of those 464 exist to serve exactly one
caller. Making a private helper its own task means writing a specification for the interface
between a function and its own helper, manufacturing precisely the seam where invention creeps
in; and most helpers are not visible until the pseudocode is written, so they are an output of
design, not an input to it. Hence: **the entry point and its private helpers are one task.**
For v2's engine that is about 255 tasks averaging thirty-odd lines.

**The sizing test, checkable at planning time:** list the task's behaviours; if any one of them
cannot be verified without reaching into another task, the boundary is in the wrong place.

---

## Definitions

### Plan
The root. Every row, link, gate result, finding and journal entry for one endeavour, in one
workspace. One plan per workspace. *The plan **is** the project's record — "project" is not a
separate thing and is not a word we use.*

### Stage
One phase of the interview: the methodology's ordered steps that elicit the specification.
Eight of them, vendored as scripts, instantiated by every plan.

**`stage` is un-retired**, and the reversal is deliberate. It was retired on 2026-07-21, and
the owner personally withdrew the carve-out that had kept it for exactly this purpose, on the
grounds that a live technical word pollutes reasoning later no matter how narrowly its scope is
documented. *What has changed:* the reason for retiring it was that the methodology's steps and
a build package were **the same kind of thing in different tables** — v2's glossary says so in
as many words — so two names for one concept was the disease. That is no longer true. The
interview's phases sequence elicitation; the build grouping has been removed entirely. Two
genuinely different things now need two words, and only one of them still exists. Retiring
`stage` was right under the old model and is wrong under this one.

### Task
The unit of build work: **one externally-callable function together with the private helpers
that exist only to serve it.** The thing a specification is written for, a brief is composed
for, and a builder is handed. Derived, never hand-assigned.

A task is not necessarily one function and not necessarily one object — it is the smallest
thing that can be verified on its own. Its size is governed by the sizing test above, not by a
line count.

### Behaviour
One thing a task's function commits to doing: its main effect, or one specific error it raises.
Enumerated when the specification is written and **frozen before anything is measured against
it**, so the denominator of a coverage check is never chosen by the party being measured.

Not a level of the breakdown. It is what specification and verification are written against,
one at a time. *Renamed from **obligation**, which is the same thing.*

### Scenario
A test that drives the system the way a real client does — through the exposed surface, never
the service behind it — and validates one use case, one of its steps, or one of its extensions.

**A scenario is a task**, in the graph, with a specification and dependencies like any other.
Its dependencies are the tasks it exercises, so it becomes buildable exactly when the
functionality it validates is complete. Test-building is therefore controlled by the same
mechanism as code-building, rather than being something a builder does afterwards.

**A scenario's specification is frozen before its implementation exists.** This is the point of
it. A unit test written by whoever just wrote the unit inherits that person's misunderstanding
and can only confirm the code does what its author thought; a scenario specified from the use
case at planning time cannot, because there is no implementation yet to be wrong about.

### Component
A unit of the architecture with a single stateable responsibility — a module or service, the
thing tasks are grouped *by* in the design rather than in the build.

**`component` is un-retired**, by the same argument as `stage`. It was retired because v2
derived exactly one task per component, making them one entity with two spellings. Under the
new sizing a component holds many tasks, so they are two different things and need two words.

**Open — the owner has not ruled on this one.** It is my call, flagged for overturning.

### Label
A word attached to any row for filtering and review later — "GUI", "database", "engine".

Labels sit **outside the breakdown entirely.** A row may carry none or several, they overlap
freely, and they never affect build order, completion, ownership or what a builder is served.
That is what makes them safe to let the tool propose.

**Labels are governed by the glossary machinery**, not by a second mechanism of their own: the
tool proposes a label, the owner settles it, and a near-duplicate is refused exactly as a
near-duplicate term is. That is the guard against a hundred nearly-identical labels, which is
the failure mode the owner named.

**The starter list — ten, deliberately.** Every one names a *place in the system* rather than a
kind of work, because "refactor", "bugfix" and "cleanup" describe an activity that is over once
it is done, and a label has to stay true for the life of the row.

`engine` · `surface` · `storage` · `schema` · `methodology` · `interview` · `execution` ·
`tests` · `docs` · `gui`

Ten because the failure mode is too many, not too few, and the tool adds one only when nothing
fits — which is a proposal the glossary can refuse. The list is deliberately coarse: a label's
job is to shrink a review list from everything to something a person can read, not to classify.
If a filter on `engine` returns too much, the answer is a dependency query or a search, not a
finer label.

### Catalogue entry
One object, method or function the plan intends to exist, with **one owning task** and a
statement of the concept it owns.

Populated from the pseudocode as the detailed specification is written, so duplication is
caught at the point it is designed rather than the point it is coded. Before a new entry is
accepted, near matches already catalogued must each be dismissed **with a written reason**.

### Decision context
A separate field on a row recording **why** — the reasoning that produced the decision, what
was rejected, and on what grounds.

Not prose folded into the description. A session resuming cold otherwise inherits the answer
and not the argument, and can neither defend the decision nor safely reopen it. This is a
product requirement, and these documents hold themselves to it.

### Brief
The immutable composed context for one task, including its waiver log. No lifecycle:
regenerating creates a new brief that supersedes the old by reference, and the old stays frozen
for defect forensics.

---

## Retired — do not use

| Retired | Use instead | Why |
|---|---|---|
| **package** | (nothing) | The level is gone. Filtering is a **label**, ordering is a **dependency**, the end-to-end checkpoint is **derived from the graph**. Retired 2026-07-28. |
| **sub-task** | task | The level is gone. A v2 sub-task was one contract; the new task is finer than both v2's task and v2's sub-task. Retired 2026-07-28. |
| **obligation** | behaviour | One entity, two spellings. "Obligation" has to be taught; "behaviour" does not. Retired 2026-07-28. |
| **unit of work** | task | Stays retired, from v2. It was briefly the working name for the new build unit during v3 planning; that unit is a **task**. |
| **slice** | (nothing) | Coined during v3 planning for a partially finalizable plan, which was then rejected — the plan is finalized once. Retired before it reached any code. |
| **milestone** | (nothing) | Stays retired. Named this build's own M0–M8, which were exactly the self-invented build plan v3 exists to prevent. |
| **project** | plan | Stays retired. No `Project` entity ever existed. |
| **packet**, **part**, **phase**, **session** | see `GLOSSARY.md` | Stay retired, unchanged, with their original reasons. |

**Un-retired:** `stage` and `component`, each for the same reason — the two things the word had
been collapsed onto are now genuinely two things. Both reversals are recorded above with the
argument they replace, so nobody reopens them by reading the old ruling.

**No carve-outs.** The rule that killed the last two exceptions still holds: a live technical
word pollutes reasoning later no matter how narrowly its scope is documented.

---

## What changes in code at build time

- Constants become `PLAN`, `TASK`, `BEHAVIOUR`. `PACKAGE` and `SUBTASK` go.
- Columns: `task_id`, `behaviour_id`. `package_id` and `subtask_id` go.
- The eight methodology assets are renamed `stage1_context.md` … `stage8_finalization.md`,
  which is a methodology content change and therefore owes a **new revision stamp**.
- The enforcement test's banned list loses `stage`, and gains `package`, `subtask`,
  `sub_task`, `obligation`, `slice`.
- The two standing vocabulary exceptions in the current codebase (`PartsDontCover` in the brief
  composer, and a local `parts` variable in the gap engine) disappear with the code that holds
  them, so the exception block should empty.
- Retired words survive **only** as quotations inside `spec/v2/` and `engine/methodology/rev2/`,
  both read-only.

This is a large mechanical rename touching most of the engine. It is real build work with a
migration, not a find-and-replace, and it belongs to a build package of its own.
