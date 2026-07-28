# v3 decisions

Every decision carries **the reasoning that produced it and the alternatives that were
rejected**, not just the answer. That is a product requirement for the tool we are building, so
this document is held to it: a session resuming cold must inherit the argument, not only the
conclusion, or it can neither defend a decision nor safely reopen one.

Decided by the owner unless marked **my call**. Marked calls are made rather than stalled on,
and are flagged so they can be overturned cheaply.

Supersedes the stale `DECISIONS.md` written in `PlanTool_v3` on 2026-07-27, whose first
decision the owner reversed the same day and whose third was written in retired vocabulary.

---

## D1 — The finding that drives everything: the build phase had no plan

**What was found.** The frozen v2 spec holds 68 contracts, 15 components and 80 requirements.
Its package manifest table is **empty**, and there are no task rows and no sub-task rows for the
v2 build anywhere. What actually drove the build was four milestone documents written by the
assistant. So it is not that the structure was ignored — **the tool never produced a build
plan, and the vacuum was filled by whoever was standing there.**

Everything measured follows from that: about 8 bytes of specification per line of code
delivered, and 79 recorded moments where the executor had to invent something the plan should
have decided.

**Two mechanisms are missing, and only one of them is a data structure.** First, the plan never
descends to the level a builder needs — a contract is an architecture artefact, and nothing
turned 68 of them into the few hundred fully-specified tasks a builder should receive. Second,
nothing served a task and nothing prevented reading everything else; the whole spec, the
milestone documents and the entire codebase were open. **Self-contained tasks are not achieved
by writing self-contained tasks. They are achieved when the tool is the only input a builder
has.**

**Why this is stated as a decision and not a defect:** it sets the acceptance test for v3. A
change that leaves either mechanism absent has not fixed anything, however much schema moves.

---

## D2 — v3 is a targeted fix of v2, on a branch of this repo

**Decided.** The work happens in `D:\PythonProjects\PlanTool`, on a branch off `main`, with
`main` tagged `v2-final` first. Everything in v2 carries over unless the fix requires changing
it, and a change needs a reason recorded against one of the four scope items.

**Reasoning.** The owner gives the fix a high chance of failing and wants going back to be
trivial. A tag makes the fallback a name rather than a commit hunt, and keeping one repository
means the fallback is a checkout instead of a migration.

**Rejected: a rebuild in a separate repository** (`PlanTool_v3`, set up 2026-07-27 and
abandoned 2026-07-28). The owner's words: thinking about building v3 as a separate entity was a
mistake. The reasoning under the original decision is *not* withdrawn — v2's frozen-plan-plus-
deviations arrangement still cannot be re-cut — but it changed status: that is now a constraint
the fix must satisfy, not a reason to start from nothing. Separate-entity work also loses the
one thing that makes the fallback real, which is a shared history.

---

## D3 — The plan is finalized once, before any real building starts

**Decided.** No part of the plan is released for building early.

**Reasoning, in the owner's words:** you would only want that for proof of concept, and the
exception for that is already provided by test and validate. The rule exists to ensure all
relevant information is available before rushing into building.

**Rejected: finalizing in slices**, so a thin vertical slice could be specified, built and
learned from while the rest was still being elicited. It was proposed to fix the deepest
structural defect in v2 — the build graph derives only at finalization, so nothing can start
until everything is planned, which is waterfall expressed as a data dependency, and is why all
51 defects were found after freezing when the only remedy left was an annotation beside the
plan. The owner reversed it the same day it was proposed. The counter-argument that carried:
partial finalization buys early learning at the cost of the completeness that makes
specification dense, and density is the actual product.

**What still has to answer the defect this rejected option was aimed at:** the cold read (D14),
which proves a specification sufficient *before* code exists rather than after.

---

## D4 — Developmental experiments during planning, approved case by case

**Decided.** Experiments may be run during the planning stage as analysis and validation of
approach. When the assistant judges one is needed, it is **discussed with and approved by the
owner** before it is run.

**Reasoning.** This is the escape valve that makes D3 tolerable: the objection to finalizing
once is that you learn nothing until the end, and a throwaway experiment buys the learning
without releasing anything for building. Owner approval keeps it from becoming a back door
through which building starts early under another name.

**Related, already built and unused in v2:** the technical-claims machinery. Any statement about
the behaviour of something we do not control — a library, the OS, the filesystem, a protocol —
should require one of cited documentation, a probe that was run, or the owner's recorded
acceptance of the risk. The tables exist; the rule making it non-optional does not.

---

## D5 — The levels are plan → task → behaviour

**Decided.** Three levels where v2 had four. Only plan and task are levels work is assigned at;
nobody is ever handed a behaviour.

Full reasoning, including v2's own evidence that the sub-task level failed at both of its jobs,
is in `VOCABULARY.md`. In short: a v2 sub-task was one contract, which was neither a servable
size (hence a whole splitting mechanism to compensate) nor a working accounting denominator
(the split's coverage check passed unconditionally, and **obligations** had to be invented
underneath it mid-build). Behaviour is that level, renamed.

**Rejected: keeping sub-task as the servable unit.** It would preserve the splitting mechanism,
which exists only because the unit is an architecture artefact. Fix the unit and there is
nothing to split.

**Rejected: a fifth level below behaviour.** Considered in v2 and rejected there for a reason
that still holds: two breakdowns of one thing invites "3 of 4 done" to be read as progress on
work that is still worth zero.

---

## D6 — A task is one externally-callable function plus the private helpers that serve only it

**Decided**, refining the owner's own earlier proposal of "one function" rather than replacing
it.

**Measured first.** v2's engine holds 464 functions, median 12 lines, only three over 100 — so
"one function" is the right order of magnitude, nothing like v2's build unit at 90 to over
1,000 lines. But **209 of those 464 are private helpers serving exactly one caller.**

**Reasoning.** If a task is literally one function, a private helper is either its own task —
which means specifying the interface between a function and its own helper, manufacturing
exactly the seam where invention creeps in — or it is unowned, which is worse. And most helpers
are not visible until the pseudocode is written, so they are an output of design rather than an
input to it. For v2's engine this rule would have produced about 255 tasks averaging thirty-odd
lines.

**The sizing test, and why it matters more than the definition:** list the task's behaviours; if
any one of them cannot be verified without reaching into another task, the boundary is wrong.
That is checkable at planning time, which is the only place we can afford to find out. "One
function" gives no such test.

**Rejected: one contract per task** (v2's rule). It produced units of uniform shape and wildly
varying size, and nothing in the design bounded them.

---

## D7 — Package is removed entirely

**Decided.** The word, the table, the ids, the level.

**Reasoning.** The level had no established job. Its two stated jobs were grouping for
navigation and scoping context. Navigation is a **view** problem — views overlap freely and are
declared whenever the owner likes, whereas a build grouping must own each item exactly once, so
those are two mechanisms wearing one name. Context scoping belongs to the architecture. The
word also named two different id spaces, one of them dead. The owner's judgement: attaching
tasks and requirements to a specific package of work has obvious limitations and is not going
to work.

**What takes over each job:** filtering and review → **labels** (D12); ordering →
**dependencies**; the end-to-end checkpoint → **derived from the graph** (D8).

**Rejected: keeping packages purely as a build grouping.** Once filtering, ordering and gating
are all served elsewhere, nothing remains for it to own, and a level that owns nothing still
costs a mandatory membership rule, a finalization refusal and an id space.

---

## D8 — The end-to-end checkpoint is derived from the dependency graph

**Decided.** When a task completes and every task some externally-callable entry point depends
on is now done, that entry point has become exercisable end to end, and the tool demands it be
exercised — both its scenarios (D13) and the unscripted drive (D15).

**Reasoning.** This was the one job that looked like it needed packages, and it is worth
keeping: driving the system end to end after each v2 build package caught something *every
time*. But it needs a trigger, not a grouping, and the graph already knows when a subgraph
closes. Nothing is declared, nothing owns anything, and it fires at the real moments instead of
at boundaries someone drew by hand. It also matches the engine's existing "derive rather than
store" rule.

**Rejected: a declared grouping whose completion triggers the checkpoint.** That is a package
under another name, and it reintroduces exactly the hand-drawn boundary D7 removed.

**Rejected: labels as the trigger.** Labels overlap freely and own nothing, so they cannot
gate — a gate needs a set with a definite boundary.

---

## D9 — Pseudocode for every task, before any coding starts

**Decided by the owner**, explicitly and unambiguously.

**Reasoning.** This is the spine of the fix and the answer to the density finding in D1. If
detailed planning produces pseudocode per task, the plan contains a pseudocode-level design of
the whole system before any real code is written. Three things fall out of it at once: the
specification reaches the depth a builder needs; the catalogue (D10) is populated naturally,
because every name the pseudocode uses is a name the plan has committed to; and duplication is
caught at the only point where it is cheap to catch.

**The accepted cost, stated plainly:** the planning phase becomes much heavier and the plan
becomes comparable in size to the code. That is the trade the whole product is making. It is
affordable at build time precisely because a builder is served one task's worth, not the whole
plan.

**Open — my call, flagged:** exactly how deep the pseudocode goes before a task counts as
specified. Too shallow and it decides nothing; too deep and it is code written twice.

---

## D10 — A catalogue of every object, method and function the plan intends to exist

**Decided.** Each entry has one owning task and a statement of the concept it owns. Before a new
entry is accepted, near matches already catalogued are each dismissed **with a written reason**.

**Reasoning.** Duplicated and hard-to-maintain code arises because the plan does not track what
it has already decided should exist. Written dismissal is the mechanism: a rule that merely says
"check for duplicates" is an intention, and this project's repeated lesson is that a rule in a
document is not a mechanism.

**Timing is the load-bearing part:** the catalogue is populated **at the detailed planning stage,
from the pseudocode** (D9), so that code never has to be rewritten in the build phase.

**Open — the exact shape.** The owner is flexible on mechanism and stated the goal as avoiding
duplicated, hard-to-maintain code. Designing it is mine to do and then put to him. It is also a
dependency of the cold read (D14), because the reader must be told what it may call.

---

## D11 — A decision is stored with its context, in a separate field

**Decided.** A separate field holding the reasoning, what was rejected, and on what grounds —
not prose folded into the description.

**Reasoning.** Logged as a real defect from the GUI dogfood: a session resumed cold, read back a
decision about dragging references between panels, and could recover the answer but not the
argument. Nothing recorded why that shape was chosen or that the alternative had been considered
and rejected, so the resuming session could neither defend the decision nor avoid reopening a
settled question. A separate field rather than a convention because a convention is not
checkable and cannot be required.

**Open:** whether it is required at write time or prompted for, which row types must carry it,
and how it interacts with supersession.

---

## D12 — Labels sit outside the breakdown and are governed by the glossary machinery

**Decided.** A label is a word attached to any row for filtering and review — "GUI", "database",
"engine". A row may carry none or several, they overlap freely, and they **never** affect build
order, completion, ownership or what a builder is served. The tool proposes labels from a
generic starter list and adds to it when nothing fits; the owner changes them at will.

**Reasoning.** This is the owner's scope item: he needs to filter references and tasks for later
review. Giving the tool proposal rights is safe **because** labels affect nothing in the build —
the blast radius of a bad label is a slightly worse filter, and the owner can overturn it.

**The guard, and it needs no new mechanism:** labels are governed by the glossary — the tool
proposes, the owner settles, and a near-duplicate is refused exactly as a near-duplicate term
is. The owner's stated risk is too many specific labels and near-duplicate names, which is the
same failure the glossary already exists to prevent.

**Rejected: labels as a free-text field.** A free-text grouping key is what "milestone" was in
v2, and it silently yields nothing on a typo.

**Open:** whether the tool proposing labels under glossary rules is the right level of control.

---

## D13 — The test regime takes its denominator from the requirements, not the code

**Decided.** Every use case, every step and every extension gets a **scenario** that drives the
system through its exposed surface, the way a real client does. Scenarios are **tasks**, in the
graph, with specifications and dependencies like anything else; a scenario's dependencies are
the tasks it exercises. A scenario's specification is **frozen before its implementation
exists.** Behaviour-level verification stays as it is, one per behaviour, mechanically counted.

**Measured.** v2 has 542 tests in 31 files, one file per engine module. **Fewer than 80 enter
through the surface a real client uses**; the rest call a service class directly, behind the
door. The frozen plan meanwhile holds 12 use cases, 40 steps and 50 extensions — 90 named things
the system is supposed to do — and not one test file is organised around any of them. There are
also 10 state machines with 187 cells, systematically untested. **The suite mirrors the code,
not the requirements**, and no artefact anywhere says "this use case works."

**What it cost:** the transport every client hits first crashed on the first real call, and 518
green tests did not notice, because none of them came in through that door.

**Why the freeze-before-implementation clause is the important one.** A unit test written by
whoever just wrote the unit, minutes after writing it, inherits that person's misunderstanding —
it can only confirm the code does what its author thought it did. A scenario specified from the
use case at planning time cannot, because there is no implementation yet to be wrong about. The
owner's observation that unit testing is done well and complex validation neglected is accurate,
and the cause is that nothing ever **asked** for the second kind.

**Accepted cost:** a scenario written before the code sometimes turns out to be wrong about
reality. That is a supersession with recorded reasoning, and finding it is itself useful signal.

**Rejected: making complex validation a stronger instruction.** It has no denominator, so it
cannot be counted, gated or noticed when absent — the same reason the split-coverage check
failed silently in v2.

---

## D14 — The cold read proves a specification sufficient, before any code exists

**Decided** during v3 planning and carried forward. When a task's specification is declared
finished, a session holding **only** that specification, the catalogue entries it may call, and
the glossary — with no access to the conversation that produced it — lists **every** decision it
would have to make to implement the task, including the obvious ones, and cites against each the
row that answers it. **An uncited decision is a hole.**

**Reasoning.** Inventions happen at design time, so the test needs no code and costs no build
effort. Citing rows turns the result into a claim that can be checked mechanically rather than a
self-assessment, which is what makes it resistant to a reader that bluffs.

**Rejected: asking the reader to "name the holes".** It rewards silence — a reader that notices
nothing scores perfectly.

**Calibrate before it gates anything.** The 79 recorded inventions are a labelled test set:
reconstruct the specification that preceded a sample of them, run the cold read blind, count what
it catches. That gives a hit rate rather than an assurance.

**Accepted limitations.** It is non-deterministic, so run it more than once and take the union.
It depends on the catalogue existing (D10). It is weaker than actually building; the residue is
caught by the loop that returns a builder's invention to the plan.

**Staleness:** a result is stamped against the rows it read and marked stale when one is
superseded. Nothing re-runs automatically; stale tasks get one re-read before finalization, when
the plan has stopped moving.

---

## D15 — The unscripted drive stays, as planned and recorded work

**Decided.** Driving the system by hand, unscripted, as a real client would — triggered by the
derived checkpoint (D8), with findings filed in the tool as its output.

**Reasoning.** The worst v2 defects were not caught by the test suite; they were caught by this,
and it caught something every single time. Scripted scenarios cannot replace it, because what it
finds is the things nobody thought to specify. Making it planned work with a recorded output is
what stops it being a good intention.

---

## D16 — `stage` and `component` are un-retired; `package`, `sub-task`, `obligation` are retired

**Decided** (`component` is **my call**, flagged). Full argument in `VOCABULARY.md`.

**The reasoning is one argument applied twice.** Both words were retired because they had been
collapsed onto something else — the interview's steps *were* the standard package set; a task
*was* a component, one per component. Under the new model neither collapse holds: the build
grouping is gone, and a component now holds many tasks. Two genuinely different things need two
words. Retiring them was right under the old model and is wrong under this one.

**Recorded because it reverses an explicit owner ruling.** On 2026-07-21 the owner personally
withdrew the carve-out keeping `stage` for the methodology, on the grounds that a live technical
word pollutes reasoning later no matter how narrowly its scope is documented. That rule is not
withdrawn — it still forbids carve-outs. What changed is the model underneath it.

---

## Still open, and where

Carried forward so nothing is lost. Each is scheduled, not merely noted.

- **What "return to the fundamental concept of the MCP" commits to in mechanism.** My reading,
  to be designed against and confirmed: v2 drifted into being a plan database with CRUD tools
  hung off an MCP surface; the fundamental concept is the opposite — **the surface serves exactly
  the specification for one task and nothing else, so the tool call *is* the context boundary
  rather than a query interface.** If that is right, this is largely a redesign of the tool
  surface and of what a task hands over, and it is the same work as the interview design, because
  you cannot serve density you never elicited. *Next document.*
- **The catalogue's exact shape** (D10). *Next document but one.*
- **The interview design** — how the tool elicits a specification deep enough to build from.
  Nothing has been written on it, and it is where the density problem is won or lost.
- **How deep the pseudocode goes** before a task counts as specified (D9).
- **The starter label list** (D12), and whether tool-proposal under glossary rules is the right
  level of control.
- **Whether v2 is used to plan v3.** Held for the end-of-planning checkpoint. For: it would
  exercise the execution half on real work for the first time. Against: that half has never run,
  it puts an unproven mechanism on the critical path of its own replacement, and v2's own plan
  lives in a v1-format database so it cannot serve briefs about itself without an unscheduled
  migration.
- **The plan itself** — what v3 does, what it stores, what it exposes, and its build packages in
  order.

**The written record is known to be incomplete.** The duplication requirement behind D10 appeared
in neither the charter nor the analysis; the owner raised it as a standing request that had been
missed. Ask rather than assume.
