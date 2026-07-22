# The function catalogue — design record, 2026-07-22

**Status: designed in conversation, not built, not scheduled.** This is a capture of a design
discussion so it can be picked up later. It is deliberately not attached to a build package — see
"Scope" at the end for why.

**Naming note.** `registry` was not available: `REGISTRY` in `engine/surface.py` is the tool
registry, referenced from the door and the MCP wire. This build has had three naming
collisions in a single sitting and built tests to stop a fourth, so this is the catalogue.

---

## 1. The problem it exists to solve

An agent designing a codebase across many sittings cannot see the codebase it is building,
because the codebase outgrows the window. Two failures follow from that single cause. The
agent writes a second copy of something that already exists, and it invents a second name for
something that already has one.

Both have happened here. Three naming collisions landed in one sitting, and a helper was
duplicated verbatim under a slightly longer name. Neither was a carelessness problem that more
attention would have fixed; the code that would have prevented them was simply not visible at
the moment of writing.

The owner's framing, which is the design's foundation: **catch this at a structural level in
the plan, so that code-writing never has to resolve it.** By the time a function is written,
the question of whether it should exist has already been asked and answered.

Three constraints shape every choice below. The tool has no model and never will, so it cannot
assess similarity of meaning. There is no embedding model, so retrieval is lexical or
structural, resting on SQL full-text search. And it must be language agnostic, so nothing may
require a parser per language.

## 2. The core loop

When the design calls for a function, the planner names it and writes a one-line purpose, then
searches the catalogue for anything of a similar name or description. If nothing comes back,
the function is approved and the row is written. If something does, the overlap is investigated
before anything is approved.

**Approval and registration are a single act.** If they are separate steps, some functions will
be approved and never registered, and the catalogue develops holes that nothing can detect.
There must be no state in which a function has been agreed and is not in the table.

## 3. What a row holds

- **name** and **container** — together these are the row's identity. A method is a function
  whose container is a class, which is what lets the procedural and object cases share one
  record shape.
- **purpose** — one line, and it carries the entire weight of the search (see the open
  questions).
- **path** — where the function lives. This is a pointer for a reader to follow, explicitly
  *not* part of the identity: if a row is identified by location, reorganising files reads as
  deletion plus addition and destroys the history the catalogue is accumulating.
- **landing commit** — the commit the function arrived in.
- **death-discovery commit** — the commit at which the function was found to be gone.

On that last field the owner's phrasing is deliberate and should be preserved. What the check
knows is where the absence was *discovered*, which may be well after the commit that removed
it. Recording what is actually known is honest, and the true removal point stays recoverable
from git if anyone needs it.

**Inputs and outputs were considered and rejected as a matching basis.** Parameter names are
arbitrary enough that matching on them would mostly generate noise. The consequence is that the
purpose line carries everything.

## 4. The search reads in both directions

One query answers two different questions, so it costs nothing to look for both.

- A close **description** under a different name suggests **duplication**, which is the case the
  catalogue is primarily aimed at.
- A close **name** with a different description is a **naming collision**, which is a separate
  defect and the one that actually bit this build three times in one sitting.

## 5. Overlap is judgement, invited rather than computed

At planning time no code exists, so nothing can measure how much implementation two functions
would share. The tool cannot do it either, having no model. So the assessment is made by the
planner reading both purposes, and the tool's job is to record it.

A rough estimate of how much functionality is shared is a good **trigger** — it decides whether
the question is worth pursuing — and a poor **record**, because overlap is asymmetric and a
single percentage hides the direction it runs in. A small function may sit entirely inside a
larger one, which is complete overlap of one and slight overlap of the other. What gets
recorded is therefore the relationship, because that is what a later planner can act on:

| relationship | what it means to do |
|---|---|
| the existing function contains the new one | use what exists |
| they partially overlap | extract the shared middle as a third function |
| they are the same | merge |
| unrelated | record the negative |

**The negatives have to be recorded too.** Most searches return a plausible candidate and most
answers are "different thing". If only merges are written down, the next planner runs the same
search, sees the same candidate, and decides again — possibly the other way. A recorded "these
are not the same, and here is why" is what stops the codebase drifting apart between planners, and
the plan already has the structure for it, since a decision row carries both its rationale and
the alternatives that were rejected.

## 6. What is not registered

Trivial members stay out: initialisers, accessors, one-line wrappers. Duplicating a one-line
accessor costs nothing, so nothing is lost.

**The exclusion rule must be about behaviour, not name prefixes.** This build's own surface is
the evidence against a prefix rule — reading the active warnings, reading the gate history,
fetching the mandate and fetching the package script are all real behaviour behind names that a
`get_` rule would have discarded. The rule is that a function which only reads or writes a field,
with no logic, does not get registered.

## 7. Validation is lazy and happens at the point of use

**Rejected: enumerating every function in the tree and comparing the whole set against the
catalogue.** That was the first design and it was wrong, because it drags language-specific
declaration-finding into the engine for a guarantee nobody needs.

**Adopted, on the owner's correction:** the catalogue only has to be true at the moment it is
used, and it is only used when a search returns a candidate and asserts that something already
exists. So the check is a single lookup confirming that the named function is really there,
performed on the handful of rows a search returns, at the only moment the answer matters.

This fails in the safe direction. A stale row is caught immediately before anyone could act on
it. A function that exists but was never registered stays invisible, which costs a missed
duplication rather than a confidently wrong instruction.

It also does useful work as a side effect. Finding a row dead is information, not merely an
error: the row is retired and the search continues with the remaining candidates. Finding a row
live is the natural moment to ask git which commit introduced the function and fill in the
landing commit, which solves the otherwise awkward problem that at registration time the commit
does not yet exist. The catalogue improves by being used rather than by anyone remembering to
maintain it.

*A concern raised and made moot.* It was argued that enforcement hooked to the agent's writing
would desynchronise on reverts, merges and branch switches, none of which are manual edits but
all of which change the tree. The owner's position is that this tool is only ever driven through
the agent. The lazy design settles the question either way, because it never asks how the files
got the way they are.

## 8. Lifecycle: a function added, removed, then reintroduced

**Dead rows are kept and their death marker is never nulled.** The fork here is less even than
it looks: a function written, removed, and written again is precisely the case that suggests
something was wrong with the original design, and nulling the death on reintroduction erases
that history at the moment it becomes interesting.

Not getting tangled in old rows is a question about what the search sees, and the codebase
already answers it — the frozen plan is a live-rows export, where superseded and retired rows
exist but never appear. The same applies here. **Only live rows are ever returned as candidates**,
because a dead function cannot be reused and offering it is exactly the confident wrong answer
this design is avoiding. Dead rows remain queryable deliberately.

**Dead rows are still consulted for the name check.** If a dead row carries the name and a
similar purpose of a function about to be registered, that is surfaced before approval, because
the thing about to be written may have been removed on purpose and the planner may be undoing
somebody's decision without knowing it.

Two mechanical details:

- **The death commit is the only field that decides liveness.** A row with one is dead, a row
  without one is live. No separate status column alongside it, because two fields that can
  disagree is where the tangle would come from.
- **A partial unique index on live rows** gives "at most one live function per name and
  container" while allowing any number of dead ones behind it. This is the index shape already
  used for plan row names.

**No edge type is added between a dead row and its reintroduction.** The lineage is derivable as
a query — every row with this name and container, ordered by landing commit — and the edge
vocabulary is deliberately closed so that a misspelled type cannot create an invisible relation.
Adding one should be a decision on its own merits, never a side effect of this.

**Known cost of the strict rule: the false death.** If validation fails to find a function that
was only moved, it stamps a death, and the next registration forks a new row for something that
never left. The history query makes this visible and recoverable rather than silent, which is an
acceptable price, but it argues for the check being confident before it stamps rather than
stamping on a first miss.

## 9. The cross-container report

Beyond function-to-function duplication, there is the question of whether several classes
carrying similar methods should have that behaviour pulled out into shared code.

This is a **different mechanism, not an extension of the search**. Searching before declaring
checks one new row against the catalogue, with a planner standing there about to write
something. Noticing that three containers each carry a similar method is an aggregate query
over the whole catalogue, and nobody is standing there when it becomes true. So it is a report
the planner reads periodically, in the same shape as the coverage meter: the tool computes and
shows, the planner decides.

**It needs a threshold and probably an exclusion for near-universal patterns**, because almost
every class has an initialiser, a validator and something that renders it as text. A report
flagging those on every run is the cry-wolf failure that gate warnings already had to be fixed
for once.

## 10. Why the plan glossary is load-bearing here

A keyword search only finds what someone thought to describe in those words, so two functions
doing the same job in different vocabulary will never match. The plan glossary — designed in
the current build package's plan and still unbuilt — is what constrains that vocabulary. Building the
two together is what makes this search work; the glossary stops being a tidiness feature and
becomes the thing this depends on.

## 11. Why each metadata field earns its place

Unread fields are a defect class this build has already been bitten by, so each field needs a
stated consumer.

- **Path** is what a planner follows to go and read the thing.
- **Landing commit** bears on the duplication question, because two functions that arrived in
  the same commit were probably written together and are more likely to be splittable.
- **Death-discovery commit**, together with the landing commit, gives **churn** — functions that
  were designed, registered, and dead within a handful of commits. That is a measurement of
  whether plan-time function design is actually any good.

The last one matters more than it first appears. The only thing that truly validates an
architecture is the feedback from building against it, and that loop lives in the deferred
execution work. Churn is a cheap fragment of exactly that loop, and it comes almost free with
the other two fields.

## 12. The two-patterns assumption

The design assumes all code is procedural or object-based, with functional styles excluded.
That holds, and the container field is what makes it hold: a method is a function whose
container is a class, so both worlds produce the same record shape and the search never needs to
know which one it is in.

The residue is state. A method can read and write its object rather than only its inputs and
outputs, so two methods duplicating state handling will look unrelated when the row describes
only purpose. This is a real gap and a narrow one, and it is accepted rather than complicating
the record.

## 13. Open questions

These are genuinely unresolved and should not be smoothed over when this is picked up.

1. **Granularity.** What counts as a registerable function. If accessors and trivial wrappers go
   in, the catalogue runs to thousands of rows and the search drowns. If the rule is left
   unstated, different planners register at different levels and the catalogue quietly becomes
   incoherent. The owner's estimate is that a real codebase has hundreds of unique functions, and
   that estimate is only true if this rule is right.
2. **The shape of a purpose line.** Since inputs and outputs were rejected as a matching basis,
   search quality rests entirely on the purpose. A constrained shape — verb, object, qualifier,
   as in "converts a stored timestamp into a display string" — probably belongs in the package
   script rather than being left to free prose, but it is not specified.
3. **The threshold on the cross-container report**, without which it fires on every initialiser.

## 14. Scope

**This is not work for the current build package.** The owner cut this topic from the build package's plan
on 2026-07-21, on the grounds that enforcing good coding practice through standing mechanical
checks is a large implementation topic in its own right, and that carrying half-designed checks
alongside the build work confuses both. That reasoning still holds, and the current build package
still has an open gate with named items on it.

The more interesting home for this is as **the first capability planned using the tool itself**.
That needs the revision path, which is not built yet.

Nothing here is scheduled. It is written down so it can be returned to.
