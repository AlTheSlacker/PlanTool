# v3 vocabulary

**Status: a transitional document, and it stays one.** It is read by people and by sessions
writing v3; **no v3 code reads it, and none ever will** — v3's only glossary is the `terms`
table. `GLOSSARY.md` has the same status: it is still parsed today by a test that fails the
suite on any identifier holding a retired word, and change 1's first task deletes that test
(`builds/01-vocabulary-and-levels.md` task 1A.0, and `builds/04-glossary-and-labels.md` §4.1
for why). After that, nothing here or there is mechanically enforced, deliberately.

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

**Open — the owner has not ruled on this one.** It is my call, flagged for overturning. Change 3
is evidence for keeping it: it gives `component` a job nothing else can do — an object's owner.

### Object
A class the plan intends to exist. It is a **catalogue entry** whose owner is a component, and it
is the **container** the method entries belonging to it name.

**This word was load-bearing before it was defined, which is how it got missed.** Change 3 made
`object` half of the catalogue's `kind` column and rested a whole argument on it — v2's engine
holds 204 objects, they collide 11 times where the 431 functions collide never, and the objects
are therefore the half that catches anything. A word carrying a schema value and a measurement,
with no entry here, is the exact failure this document exists to prevent. Added 2026-07-29.

**Object and component are two words, and the test is whether each has a job the other cannot
do.** A component carries contracts and exists from stage 6, before any catalogue; an object is a
container that a method entry can name and a participant in name-collision refusal, from stage 8.
Neither can stand in for the other. The counts agree: about 30 components against 204 objects.

**They are often 1:1, and that is not the collapse that retired `component` in v2.** A component
whose whole responsibility is one class gives one component and one object. So does a task and its
externally-callable function, and nobody reads *that* as one thing with two names. The disease is
two words with one job, not two words with one instance.

### Label
A word attached to any row for filtering and review later — "GUI", "database", "engine".

Labels sit **outside the breakdown entirely.** A row may carry none or several, they overlap
freely, and they never affect build order, completion, ownership or what a builder is served.
That is what makes them safe to let the tool propose.

**Labels are governed by the glossary's rules**, not by a second mechanism of their own: the tool
proposes a label with a definition, the owner settles it, and a near-duplicate is refused. That is
the guard against a hundred nearly-identical labels, which is the failure mode the owner named.

**This entry said the near-duplicate was "refused exactly as a near-duplicate term is", and no such
refusal existed anywhere.** `define_term` refuses only an exact match. Corrected in D12 on
2026-07-29; **change 4 builds the refusal, for labels and for the glossary both**, over the same
ranking the catalogue uses. Labels get their own table rather than glossary rows, because
`idx_terms_live` allows one live row per word and a word can legitimately be both a term and a
label — "engine" is both in this plan.

**The starter list — ten, deliberately.** Every one names a *place in the system* rather than a
kind of work, because "refactor", "bugfix" and "cleanup" describe an activity that is over once
it is done, and a label has to stay true for the life of the row.

`engine` · `surface` · `storage` · `schema` · `methodology` · `interview` · `execution` ·
`tests` · `docs` · `gui`

Ten because the failure mode is too many, not too few, and the tool adds one only when nothing
fits — which is a proposal the guard can refuse. The list is deliberately coarse: a label's
job is to shrink a review list from everything to something a person can read, not to classify.
If a filter on `engine` returns too much, the answer is a dependency query or a search, not a
finer label.

**Change 4 tried to replace this list with cross-cutting concerns and the measurement refused.**
The argument was that a place-name duplicates a filter the plan's own structure already gives you,
through the component a row belongs to. Measured against the frozen v2 plan: **53 of 687 live rows
carry a component and 4 more link to one — 92% of a plan has no path to a component at all.**
Requirements, decisions, entities, use cases, steps, extensions, state-machine cells and the CRUD
grid are most of a plan and none of them belongs anywhere. The place-name is the only filter they
will ever have. See `builds/04-labels.md` §3.2.

### Catalogue entry
One object, method or function the plan intends to exist, with **one owner** and a statement of
the concept it owns. A function's owner is a **task**; an object's owner is a **component**.

Identified by name and container — never by location, because a row identified by location reads
a file reorganisation as deletion plus addition and destroys the history the catalogue is
accumulating.

Populated from the pseudocode as the detailed specification is written, so duplication is caught
at the point it is designed rather than the point it is coded. Before a new entry is accepted,
**the highest-ranked near match must be adjudicated with a written reason**; the rest are shown
and not required.

**Both halves of that were different when this entry was first written, and change 3 measured its
way out of them.** The design said every entry has one owning *task* — but a service class carries
the entry points of twenty tasks, so no task owns it, which is what gives `component` its job. And
it said near matches are **each** dismissed: applied to v2's 635 entries that is 2,475 written
sentences, against 561 for the highest-ranked alone. The strict form is this project's own
unaffordable-rule failure rebuilt one level down — a good rule whose cost means the cheapest path
is always to skip it. Corrected 2026-07-29; the argument is in `builds/03-catalogue.md`.

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

## What changed in code — built 2026-07-31, change 1

- Constants are `PLAN`, `TASK` and the behaviour kinds. `PACKAGE` and `SUBTASK` are gone, and
  `attachments.py` **refuses** either rather than widening a caller who passes one.
- Columns: `task_id`, `behaviour_id`. `package_id` and `subtask_id` are gone — including the
  two nobody had listed, `briefs.subtask_id` and `workspace_fingerprints.subtask_id`.
- The eight methodology assets are renamed `stage1_context.md` … `stage8_finalization.md` in
  **revision 4**, minted rather than edited in place. rev3 joins rev2 as frozen provenance and
  is deliberately not loadable: it is keyed `packages:` and its stage-6 script names three
  tools that no longer exist.
- **There is no enforcement test.** This section used to specify its new banned list. The
  owner ruled that `GLOSSARY.md` is a transitional document and that v3 code reads only the
  `terms` table, so the check that parsed a markdown ban list is deleted rather than
  rewritten (`builds/04-glossary-and-labels.md` §4.1). Nothing mechanical enforces v3's own
  identifier naming, and that is the decision rather than an oversight — the failure the
  discipline exists to prevent is a synonym sharing no letters with the word it duplicates,
  which no scan of any kind sees.

  The three findings that check's own cold read produced are kept in
  `builds/01-vocabulary-and-levels.md` §9, because each is a live trap for the next
  mechanical check this project writes — chiefly that `sub_task` could never have been
  banned, since the check tokenised and `task` has to stay legal.
- Both standing vocabulary exceptions are gone with the file that held them. One had been
  protecting `PartsDontCover`, which is not an identifier anywhere in the repository — it
  appears only inside a docstring quoting the frozen plan's name for an error whose class was
  called something else. An exception protecting a symbol that does not exist had been
  counted as live for as long as it was recorded.
- Retired words survive **only** as quotations inside `spec/v2/`, `engine/methodology/rev2/`
  and now `engine/methodology/rev3/`, all read-only.

It was a large mechanical rename touching most of the engine, with a migration under it —
six commits, one pull request, 533 tests green at the end and green nowhere in the middle.
