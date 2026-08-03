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

~~**Open — my call, flagged:** exactly how deep the pseudocode goes before a task counts as
specified. Too shallow and it decides nothing; too deep and it is code written twice.~~

**Answered, and this flag was stale for weeks — corrected 2026-08-03 while specifying change 5,
the change that depends on it.** The answer is `INTERVIEW.md` §8 and it landed in PR #35:
**pseudocode is deep enough when every uncited decision a cold read returns is either a
convention or task-local.** The third category — a decision another task would have to agree
with — is the class the plan owes an answer to, and it is what "deep enough" means.

**It is a sorting rule, not a threshold, which is why it can be stated at all.** There is no
number to invent, and the calibration is what settled it: the proposal that a task is specified
when the cold read finds no holes was killed because a reader leaves a mean of 35 uncited
decisions per task, so that rule never terminates. The same sort takes those 35 down to 16
conventions, 12 task-local and 5–8 real holes.

**Left standing, this flag would have told change 5's author to go and decide something already
decided** — which is the defect D12 carried for weeks in the other direction, and the reason
`INTERVIEW.md` §8 exists at all.

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

## D12 — A label is a glossary term, attached to rows and tasks

**Decided.** A label is a word attached to any row or task for filtering and review — "GUI",
"database", "engine". A row may carry none or several, they overlap freely, and they **never**
affect build order, completion, ownership or what a builder is served. **The word must be a live
glossary term**, so `attach_label` looks it up and refuses if nothing holds it; `define_term`
mints one. The owner defines the contents and changes them at will.

**Reasoning.** This is the owner's scope item: he needs to filter references and tasks for later
review. It also replaces the declared build grouping D7 removed, and the replacement is better
shaped than the thing it replaces: a grouping was a *level*, so a row belonged to exactly one and
everything under it inherited it, while a label is an attachment, so a row carries as many as
make sense and none of them claims to be its home.

**Rewritten 2026-08-03 by change 4, and four things this decision used to say are now false.**
It said the tool proposes labels from a starter list and the owner settles them; that there is a
label vocabulary separate from the glossary; that a near-duplicate is refused; and that labels
get a table of their own. There is no proposal step, no separate vocabulary, no near-match guard
and no `labels` table — a label **is** a term, and `label_attachments` records only the
attachment.

**The near-match guard is refused deliberately, and this is the part a cold session will want to
re-add.** The failure the owner named is calling something a "part" one day and a "component" the
next, and `part` and `component` share no letters: every mechanism proposed against it — a banned
list, an allowlist over row names, near-match ranking — is lexical, and none of them can see a
synonym that shares no vocabulary. `terms.py` had admitted that in its own docstring since v2.
Measured before it was decided: an allowlist would have refused 78 of the frozen v2 plan's 115
named rows, and 64 of its last 100, so it does not decay. A ranking inside `define_term` would
also be the tool adjudicating the owner's own word at the moment he writes it, which is
`decisions:12` inverted.

**So the glossary's job is not to be scanned; it is to be in front of the writer at the moment of
naming.** It is loaded into a planning session at its start and never written back out. The owner
called that mechanism not robust and accepted it anyway, and the reason is the one above: the
alternative is not a better mechanism, it is a mechanism that cannot work.

**What the glossary keeps as its one mechanical role** is the lookup at `attach_label`. That is
also what stops the owner's stated risk — a hundred nearly-identical labels — from being free: a
label costs a definition, and a word listed with no meaning beside it is refused.

Full argument, the measurements behind it and the rejected alternatives:
`spec/v3/builds/04-glossary-and-labels.md` §1–§4.

**Also added in change 4: a label usage report.** Near-duplication is not the only way a label set
goes bad. A label on one row and a label on all of them are both useless for filtering, and both
are invisible unless something counts them. The report counts and shows; no threshold decides what
a bad label is, because a threshold is a judgment written as arithmetic so review cannot see it.

**Rejected: labels as a free-text field.** A free-text grouping key is what "milestone" was in
v2, and it silently yields nothing on a typo.

~~**Settled 2026-07-29, by the owner:** the tool proposes labels under glossary rules, the owner
adds and assigns freely and overturns anything. The control level stands as written; what was
wrong was the guard beneath it, not the level.~~

**He reversed that the next day, 2026-07-30, and change 4 built the reversal.** Kept here because
the 2026-07-29 ruling did happen and a reader meeting it elsewhere needs to know what became of
it. The control level is **not** tool-proposal: *"the user defines the contents"*, so there is no
proposal and nothing to settle. What went with it was not only the imaginary guard but the whole
scanning apparatus — and the reason is in D18: the failure is a synonym sharing no letters, and
every guard anyone proposed for it was lexical.

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

**Calibrated 2026-07-28 — `COLD_READ_CALIBRATION.md`.** It caught 11 of 12 sampled inventions
outright and 7 more incidentally, so the mechanism is kept. Two things it changed: the test set
is **37** pre-freeze specification holes, not 79 — the rest are build-time bugs, owner rulings
and duplicates — and the raw output is far too noisy to gate on, at a mean of 35 uncited
decisions per task. Stage 10 is therefore a triage surface, not a verdict. Do not quote the hit
rate as an assurance; the sample is twelve.

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

## D17 — v2 is not used to plan v3

**Decided by the owner, 2026-07-28**, in his words: it is unproven, and there is enough on
without bug-hunting that too.

**Reasoning.** Using v2 to plan v3 would put a mechanism that has never been driven for real onto
the critical path of its own replacement. The execution half — finalization, task-graph
derivation, brief composition, serving a builder — has tests but has never been run as a client
runs it, and D13 records exactly what that is worth: v2 has 542 tests of which fewer than 80
enter through the surface a real client uses, and the first real call to that surface crashed the
server. Every hour spent on a defect in the planning tool is an hour not spent on v3.

**Rejected: planning v3 with v2**, whose case was that it would exercise the execution half on
real work for the first time. That is a real benefit and it is being given up deliberately.

**One argument against it was found to be weaker than recorded, and is withdrawn.** The objection
that v2's own plan lives in a v1-format database, so it could not serve briefs about itself
without an unscheduled migration, is *true* — `spec/v2/plan.db` holds 22 typed row tables with no
`plan_rows`, `subtasks` or `briefs` — but it does not bear on this decision. Planning v3 would
have used a **fresh** database, needing no migration. The decision rests on the unproven-mechanism
argument alone.

**Two consequences, stated plainly because they are uncomfortable.**

- **v3's own plan is written by hand, in documents — the method D1 identifies as the failure.**
  This is the same vacuum: no task rows, no build plan the tool produced. It is tolerable only
  because v3's build is ten changes rather than a system, and because the documents are written
  and reviewed rather than improvised at build time. It is not a precedent, and if v3's own build
  starts inventing, that is the finding repeating itself and should be logged as one.
- **The execution half now goes into v3 having never been driven.** Work item 7 rebuilds brief
  derivation and the build surface on top of machinery whose real behaviour is unknown. That item
  should assume nothing about v2's brief composition working, and should be driven end to end
  early rather than at the end.

---

## D18 — The glossary is a table the owner owns, with one mechanical use

**Decided by the owner, 2026-07-30**, in his words:

> Glossary table exists, but the user defines the contents with prompting from you or asking to
> add to it, labels must exist in the glossary. You only use the glossary for a mechanical look
> up (assigning labels). At the start of each session you load the glossary as a memory (I know,
> this is not robust), this might help you use the right words, it might not. If the user want to
> update the glossary for your memory then they need to restart the session.

And, ruling out the machinery proposed around it: *"retire term is dead, banned is dead,
use_instead is pointless you will no longer be checking against the glossary or banned for that
purpose."*

**The failure this exists to prevent**, in his words, and it is the acceptance test for any
mechanism proposed here: *"you calling something a 'part' one day and a 'component' the next, or
me using the word 'part' and you assuming I mean something else without checking with me for a
description."* Two directions — the tool invents a second word for a thing that has one, and the
owner uses a word the tool does not hold and the tool assumes instead of asking.

**No scan catches it, and this is the finding everything else follows from.** `part` and
`component` share no letters. Every mechanism proposed before this decision — the banned list, an
allowlist over structural slots, near-match ranking — is **lexical**, and none of them can see a
synonym that shares no vocabulary. `terms.py` had said so in its own docstring since v2: *"it
matches words, so a new name invented for an existing concept, sharing no letters with it, goes
unseen. Nothing without judgment can catch that."*

**So the glossary's job is not to be scanned. It is to be in front of the writer at the moment of
naming**, which is what the session load is for, and it is why the owner accepted a mechanism he
himself called not robust: the alternative is not a better mechanism, it is a mechanism that
cannot work. **Persisting it is forbidden** — *"that needs a robust mechanism or you will just
accummulate mixed up glossarys in memory"* — because N stale copies consulted in preference to the
live table is the exact defect the glossary exists to prevent, committed by the thing meant to
prevent it.

**Rejected, with the measurement that killed it: an allowlist over row names.** The proposal was
to refuse a row write when the row's name contains a word not in the glossary. Measured against
the frozen v2 plan, walking named rows in id order: **78 of 115 rows would have been refused —
68%** — and 64 of the last 100, so it does not decay. Names are meant to be distinctive, so most
carry a word nothing else uses. A refusal firing on two thirds of writes forever is a worse
cry-wolf than the banned list it was meant to replace.

**Rejected: the banned list**, which is a denylist somebody hand-types, in an engine whose subject
is that a rule in a document is not a mechanism. The owner: *"I hate banned, it adds nothing except
supporting hand crafted bad words, but that does not automate well."* Nothing replaces it, because
nothing can.

**Rejected: `use_instead` as a stored column.** It held a replacement word forever, for a scan that
no longer exists. The same information is now a *parameter of `remove_term`* — supplied at the one
moment it is needed and consumed immediately, with no stored mirror to go stale.

**Rejected: a word-frequency rule**, on the owner's earlier ruling — *"are we going to make a
glossary entry for 'the'?"* That ruling was reused in this conversation to argue that checking
words against the glossary is unbounded, and **he rejected the equivalence**: measured over the
same plan, `the` appears in **zero** structural slots while `package` appears in them beside
`plan`, `contract`, `spike` and `finding`. A category, not a threshold. He predicted the size
unprompted: *"I'm expecting a typical project glossary to have <100 words."*

**Also rejected, and not to be re-proposed:** carrying the glossary in the stage-script payload
(offered as a fix for the restart limitation; he said no), and carrying it in the brief — *"the
brief idea is dumb, you don't build it until the plan is finished, but you need the glossary
context during the plan."* The brief is served after finalization and naming drift happens while
rows are being written, so it arrives after the damage.

**The one mechanical use is `attach_label`'s lookup** (D12). Nothing else scans the glossary,
counts it, gates on it or warns from it.

Built as change 4. Full argument and every measurement: `spec/v3/builds/04-glossary-and-labels.md`.

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
- ~~**How deep the pseudocode goes** before a task counts as specified (D9).~~ **Settled by
  `INTERVIEW.md` §8 (PR #35) and struck here 2026-08-03**: deep enough when every uncited
  decision left is a convention or task-local. It sat on this list after being answered, which
  is this document's recurring failure — nothing cold-reads it.
- ~~**The starter label list** (D12), and whether tool-proposal under glossary rules is the right
  level of control.~~ **Settled by change 4 and by D18.** There is no starter list and no
  tool-proposal: the owner defines the glossary's contents, and ten words written by the tool at
  plan creation would be the tool defining them. The ten in `VOCABULARY.md` stay there as a
  suggestion to a reader and are seeded nowhere.
- **Whether the tool must cost a fork before putting it to the owner** — see `INTERVIEW.md` §6.
  Written in 2026-07-28 as a standing owner requirement that had never reached these documents.

**The written record is known to be incomplete.** The duplication requirement behind D10 appeared
in neither the charter nor the analysis; the owner raised it as a standing request that had been
missed. Ask rather than assume.
