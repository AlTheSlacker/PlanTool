# The catalogue — tracking what the plan intends to exist

**Status: planning artefact.** This is scope item 3, the DRY problem: duplicated and
hard-to-maintain code arises because the plan does not track what it has already decided should
exist.

**This is not a new design.** It was worked out with the owner on 2026-07-22 and written up in
`FUNCTION_CATALOGUE.md`, which is complete and self-contained and should be read as the source.
This document does three things and nothing else: it records the name decision, it states what
changes now that the catalogue is populated from pseudocode at planning time, and it settles two
of the three questions that document left open.

---

## 1. The name — I have been using the wrong word

I have called this "the register" throughout this conversation. **It should stay the
catalogue**, which is what the original design named it, and I was drifting.

`registry` was rejected in 2026-07-22 for a stated reason: `REGISTRY` in the surface module is
the **tool** registry, referenced from the door and the wire. `register` is worse still, because
`register_spike` is already an exposed call. Two near-identical words for two different things is
precisely the collision this catalogue exists to prevent, and this build has had three naming
collisions in a single sitting.

So: **catalogue**, and `register` is a word to avoid. Every other v3 document saying "register"
needs the sweep. Flagged rather than quietly fixed, because the owner used "register" too and
should know the word moved.

## 2. What changes: the catalogue is populated from pseudocode, at planning time

The original design had the catalogue filled as functions were designed, with validation against
the real tree at the point of use. That still holds. What is new is **when** the naming happens
and how complete the result is.

Under the pseudocode decision, **every name the pseudocode uses is a name the plan has committed
to.** Registration stops being a separate discipline someone has to remember and becomes a
by-product of writing the specification. The catalogue is therefore complete by construction for
everything the plan intends, rather than complete only where a planner remembered to search.

This is also what makes brief composition derivable rather than conversational: the catalogue
entries a task's pseudocode references *are* the set of things it may call, so the bundle served
to a builder can be computed instead of argued.

**Two consequences worth stating.**

The git fields — landing commit, death-discovery commit — are now clearly **build-time** fields
on a **planning-time** row. The original design already anticipated this: at registration the
commit does not exist, and it is filled in when a search validates the entry against the real
tree. Nothing changes except that the empty period is now the whole planning phase, which is
long. An entry with no landing commit means *designed, not yet built*, and that is a useful state
rather than a missing value.

The validation-at-point-of-use design **cannot run during planning**, because there is no tree to
check against. During planning the catalogue is self-consistent by construction; validation
begins when building does. This is fine, and it is worth being explicit that the safety property
of the original design — a stale entry is caught immediately before anyone acts on it — is
dormant until the build phase.

## 3. Granularity — the first open question, now settled

`FUNCTION_CATALOGUE.md` left this genuinely unresolved: what counts as a registerable function.
Too inclusive and the catalogue runs to thousands of rows and the search drowns; unstated and
different planners register at different levels and it quietly becomes incoherent.

**The task definition settles it, and settles it mechanically rather than by judgment.** A task is
one externally-callable function plus the private helpers that exist only to serve it. So there
are exactly two kinds of entry:

- **Public** — a task's entry point. Exactly one per task. It is what other tasks may call, and a
  task's pseudocode may only call something that is already a public entry.
- **Private** — a helper owned by one task. Registered so that duplication *between* tasks is
  visible, and never callable across the task boundary.

No planner has to decide whether something is worth registering: if the pseudocode names it, it is
in, and which of the two kinds it is follows from whether another task may call it.

**The size check.** For v2's engine this rule produces 464 entries — 255 public, 209 private. The
owner's estimate when this was designed was that a real codebase has hundreds of unique
functions, and the estimate holds. The search does not drown.

**The trivial-member exclusion survives unchanged and is now nearly moot.** A function that only
reads or writes a field, with no logic, does not get registered. That rule was about behaviour and
never about name prefixes, and the evidence against a prefix rule is still this build's own
surface, where reading the active warnings, reading the gate history, fetching the mandate and
fetching the stage script are all real behaviour behind names a `get_` rule would have thrown
away.

## 4. The purpose line — the second open question, now settled

Search quality rests entirely on the purpose line, because inputs and outputs were rejected as a
matching basis (parameter names are arbitrary enough that matching on them mostly generates
noise).

**Settled: a constrained shape — verb, object, qualifier.** "Converts a stored timestamp into a
display string." "Refuses a submission whose parent link is dead." The shape belongs in the stage
script that instructs the planner, not in engine code, so it is methodology rather than
enforcement.

**The glossary is what makes it work, and that dependency is now load-bearing rather than
incidental.** A keyword search only finds what someone thought to describe in those words, so two
functions doing the same job in different vocabulary never match. The glossary constrains the
vocabulary the purpose lines are written in. The two mechanisms are one mechanism: without the
glossary the catalogue's search is a lottery.

## 5. The cross-container report — the third open question, and I am not settling it with a number

The original design wanted a periodic report noticing that several containers each carry a similar
method, and flagged that it needs "a threshold and probably an exclusion for near-universal
patterns", or it fires on every initialiser.

**I am not proposing a threshold, and the reason is a standing ruling of the owner's.** A threshold
is a judgment written as arithmetic so that review cannot see it. He killed a word-frequency rule
in this project for exactly that — whether a word is load-bearing is a judgment, and a count is
that judgment in disguise. "Three or more containers share a similar method" is the same move: it
encodes an opinion about what similarity is worth acting on, as a number nobody will ever revisit.

**Proposed instead: the report ranks and never fires.** It is a query the planner runs, returning
clusters of catalogue entries sharing purpose vocabulary, ordered by how much they share, with no
cut-off and no notification. The tool computes and shows; the planner decides. That is the same
split the coverage meter already uses, and it is the split this engine uses everywhere: the tool
records judgment, it never exercises it.

The cost is honest: nobody is standing there when a duplication becomes true, so a ranked report
only helps if someone reads it. **Making that a scheduled act of the methodology — a stage step
that says read this report — is the mechanism**, and it is the right kind, because a rule in a
document is not a mechanism but a step in a script that the gate checks is.

**Still genuinely open:** whether that stage step is enough, or whether the report needs a place in
the digest a cold planner reads. I would rather put that to the owner than guess, because it is a
question about how much noise he is willing to carry, and that is his to answer.

## 6. What carries over untouched

Everything else in `FUNCTION_CATALOGUE.md` stands as written and should not be re-derived:

- **Approval and registration are a single act**, so there is no state in which a function has been
  agreed and is not in the table.
- **The search reads in both directions** — a close description under a different name is
  duplication; a close name with a different description is a naming collision. One query, two
  defects.
- **Overlap is recorded as a relationship, not a percentage** — contains, partially overlaps, same,
  unrelated — because overlap is asymmetric and a single number hides which way it runs.
- **The negatives are recorded too.** Most searches return a plausible candidate and most answers
  are "different thing"; if only merges are written down, the next planner runs the same search and
  decides again, possibly the other way.
- **Dead entries are kept, their death marker is never nulled, and only live entries are offered as
  candidates** — but dead entries are still consulted for the name check, because the thing about
  to be written may have been removed on purpose.
- **The death commit is the only field deciding liveness**, with a partial unique index giving at
  most one live entry per name and container.
- **Churn** — designed, registered, and dead within a handful of commits — is a cheap measurement
  of whether plan-time function design is any good, and it comes almost free with the other two
  fields.

## 7. Where it sits in the build

The catalogue is a dependency of two other things, which is why it cannot be deferred as it was in
v2:

- **Brief composition** (see the build-surface document) — the catalogue entries a task may call are
  a required part of what is served, and they are what replaces reading the codebase.
- **The cold read** — the reader must be told what it may call, or it cannot distinguish "this
  decision is unanswered" from "this decision is answered somewhere I cannot see".

Both of those are load-bearing for the density problem, so the catalogue moves from unscheduled to
early.
