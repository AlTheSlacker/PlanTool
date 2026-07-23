# Deviations from the frozen plan

The plan at `plan.md` is FROZEN (version 2, 2026-07-17) and cannot be amended. Every
place where the v2 build departs from it is recorded here, so plan and build never
silently disagree.

Format: what the plan says · what v2 does · why.

---

## D1 — revision-service reduced (execution-coupled clauses only)

> **History:** this deviation originally deferred `task-graph` and `brief-composer`
> entire. That deferral was **reversed on 2026-07-20** — the design discussion it was
> waiting on happened (see D8 and `M5_PLAN.md`), and the deferral was also found to be
> structurally unsound (it removed the only path out of `draft` — `M5_PLAN.md` §1.2, not
> a numbered defect; this line previously miscited DEFECTS.md F15, which is a different
> and since-withdrawn finding). Both
> components are now built at M5. What remains a deviation is only the reduction of
> `revision-service`, below.

**Plan:** `decisions:50` specifies fifteen components in four layers; `revision-service`
(`components:13`) carries a change-order loop with execution-coupled clauses.

**v2:** `revision-service` is built in reduced form — the change-order loop (snapshot,
version bump, impact walkthrough, per-item adjudication, atomic apply or clean rollback)
is in scope; its execution-coupled clauses are not:

- freezing in-flight sub-tasks (`open_revision`)
- regenerating affected briefs (`adjudicate_repercussion`)
- flagging already-built work as needing rework at apply time (`adjudicate_repercussion`)

**Why:** owner decision, 2026-07-20. These clauses couple to sub-task and brief state that
only comes alive once a plan is being driven; the change-order loop itself is independently
useful and stays in. (Note the earlier claim that the *whole* revision loop is useful with
no execution layer was false — `open_revision` refuses draft plans, so with no finalize
path nothing could open a revision at all; F15. That is why the execution module could not
in fact be deferred, only these specific clauses.)

---

## D2 — Pluggable surface

**Plan:** `mcp-surface` (`components:15`) is the sole consumer of every service contract;
of the 68 contracts, the great majority record "consumed by: components:15".

**v2:** a service layer sits beneath the surface, and MCP becomes the first adapter rather
than the assumed one.

**Why:** a GUI and the execution module are both known future consumers of the same
services. The frozen architecture has no seam for a second consumer. Inserting one now is
cheap; retrofitting it after every service is written against an MCP-shaped caller is not.

See DEFECTS.md F1 — this deviation exists because the plan has a gap, not because the
plan is being overridden on preference.

---

## D3 — References as first-class rows

**Plan:** `record_claim_outcome(claim_id, outcome, evidence: str)` (`contracts:32`)
reduces the justification for a scientific claim to a free string. `file_claim`
(`contracts:31`) routes `kind='scientific'` to "research + owner/domain-expert
adjudication" but specifies nowhere for the research to live.

**v2:** sources and extracts are first-class linked rows, with a machine-verified quote
invariant. Full design in `../../V2_BUILD_PLAN.md` §5.

**Why:** every other justification in the system is a linked row; citations were the sole
exception, which is an inconsistency rather than a decision. Owner requirement, 2026-07-20:
scientific papers must be usable as references without being embedded into every context,
and the referencing system must not be hallucinatable into error.

See DEFECTS.md F2.

---

## D4 — Ingestion pipeline stubbed

**Plan:** does not specify reference ingestion at all (consequence of D3).

**v2:** the reference *data model and verification rule* are built in M1. PDF parsing and
URL fetching are stubbed behind a manual path — the user points at a file or pastes text,
the session reads it, the tool records extracts with verified quotes.

**Why:** the invariant ("no extract without a verifying quote") must exist before any rows
do, because invariants cannot be retrofitted onto violating data. The pipeline is
dependency-heavy and of unproven value, and the manual path works on day one.

---

## D5 — There is no writer lock (superseded 2026-07-22)

**Superseding decision, owner's ruling 2026-07-22: the writer lock is removed entirely,
and this deviation is moot.** Both the plan's design and the one below argued about *how*
to lock; neither asked whether the tool needs locking. It does not. The owner plans in one
session and will never run two, so the lock protected against a situation that cannot
arise, at the cost of a `lease` parameter on nearly every write in the engine and a
ten-minute silence rule that let elapsed time decide who owned the data. SQLite locks the
file for the duration of a write regardless, so nothing guards against corruption that
was not already guarded.

`contracts:63`, `contracts:53`, `contracts:54`, `decisions:44` and `decisions:58` are
therefore **not implemented**, deliberately. `requirements:67`/`68` are moot: they
constrain how two simultaneous writers must be arbitrated, and there is only ever one.

**`requirements:70` and `findings:12` are moot for the same reason** — noticed at M6's
pre-build audit, 2026-07-22, and added here because the deletion swept the mechanism and left
this consequence unstated. `requirements:70` parks a checkpoint-class write in a spill journal
when the writer lock rejects it, and reconciles it on the next lock acquisition. With no lock
there is no contention, no rejection, and nothing to park; `findings:12`'s collision between
zero-loss checkpointing and single-writer rejection dissolved along with the lock that caused
it. The zero-loss guarantee itself (`requirements:56`/`60`) is untouched and is what
`session-service` builds: every checkpoint is written durably at the moment the unit
completes.

The original deviation is kept below because it records why the plan's file-based design
was rejected, which still holds if locking is ever genuinely needed.

---

### Original entry — writer lock as a database lease, not an O_EXCL lock file

**Plan:** `contracts:63` — the writer lock is "claimed via atomic O_EXCL create", with
`decisions:58` adding sharing-violation retries on network mounts, and
`dep_failure_modes:12` ruling out a background heartbeat.

**v2:** the lock is a row in a `writer_lease` table, claimed inside a `BEGIN IMMEDIATE`
transaction. Renewal updates that row; every write validates its lease in the same
transaction that applies it.

**Why:** two reasons, and the first is evidence from this project's own spike.

`spikes/001` found on real SMB that the file-based lock protocol fails: `os.replace`
onto the lock file raises `PermissionError 13` when a reader holds it open, which
silently killed the holder's heartbeat and let a live session's lock be stolen. The
frozen plan absorbed this as a retry (`decisions:58`) rather than as a reason to change
mechanism.

Second, `requirements:68` demands that a stale holder's write be "rejected inside the
same transaction that would apply it — no two sessions ever have writes applied under
simultaneously valid leases". A lock *file* cannot participate in the database
transaction that applies the write, so the file-based design cannot actually deliver the
atomicity the requirement asks for. The database lease can, and does.

This is a case where two rows of the frozen plan pull against each other and the
requirement is the stronger one. Not logged as a defect: the plan is internally
inconsistent rather than insufficient, and the resolution follows from its own
evidence.

---

## D6 — Contradiction is declared by the session, not detected by the tool

**Plan:** `contracts:9` raises `ConflictRequired` when "a submitted row contradicts a
stored row", and `requirements:27` requires the conflict be raised and presented before
the contradicting row can be filed. Neither says how contradiction is determined
(DEFECTS.md F4).

**v2:** the submitting session declares the contradiction by giving the row a
`contradicts` edge to the row it contests. The tool then enforces, mechanically, that a
conflict naming that contested row exists before the row may be filed. No conflict, no
write.

**Why:** the design spine — the tool records judgment, it never exercises it. Deciding
that two statements contradict each other *is* judgment, and `decisions:12`/
`requirements:75` put no model inside the tool that could exercise it. The alternatives
were both worse: a lexical heuristic would produce false positives on rows that merely
share vocabulary and false negatives on everything expressed differently, and it would
be exercising judgment badly rather than not at all.

What is preserved is the part that matters. requirements:27's guarantee is procedural —
that no contradicting row is filed until a conflict has been raised *and presented* —
and that is fully mechanical once the contradiction is declared. What the tool cannot
guarantee is that a session declares one. That is the same trust boundary as provenance:
nothing stops a session marking an assumption as decided either, and the plan accepts
that everywhere else.

Deliberately accepted, not resolved: a conflict raised and immediately resolved satisfies
the check. requirements:27 asks that the conflict be presented, and presentation happens
in the session, where the tool cannot observe it.

---

## D7 — Gate warnings are scoped to the package being gated

**Plan:** `requirements:21` — "WHEN a gate passes while open gaps or unresolved
assumptions exist, the system shall list each as an explicit warning."

**v2:** a gate *raises* warnings for open gaps in the package being gated, plus the
package-agnostic rules (open assumptions, reference coverage). Warnings already in the
ledger from earlier packages keep re-presenting until resolved or suppressed, so the
result of any gate still shows everything outstanding.

**Why:** the literal reading made the package-1 gate report "No components yet" on a plan
five packages from needing components — ten noise warnings out of twelve. `gap_rules.yaml`
states the principle being violated: "a meter that cries wolf stops being read".
decisions:31's keep-pushing policy depends entirely on warnings being read.

See DEFECTS.md F10.

---

## D8 — Plan-time context allocation with scope-attachment framework

**Plan:** the frozen plan has no concept of attaching a row, finding, or note to a scope.
Context for a sub-task's brief is computed at brief-composition time from the link-graph
closure (`requirements:36`), and "current working set" (`requirements:62`) / "accumulated
learnings" (`requirements:58`) are named but undefined (DEFECTS.md F16).

**v2:** context allocation is a **planning-time recorded judgment**. Attachments (base
references, findings, journal notes) carry a scope level — **project / milestone / packet**
— and a packet's context is the union of its own attachments and those of its enclosing
scopes. Allocations key on target-row **lineage root** (the `requirements:78` primitive),
so they survive supersession. An owner-facing review surface (the future GUI) can promote
or narrow attachments, with **asymmetric friction**: promoting to a broader scope records a
reason the owner sees, narrowing is free.

Full design: `V2_BUILD_PLAN.md` §10 and `M5_PLAN.md` §2. Built at M5 alongside the
execution module.

**Why:** three converging reasons. (1) It resolves F16 — "current working set" and
"accumulated learnings" become structural rather than heuristic or unbounded. (2) It keeps
relevance a *recorded* judgment rather than a read-time heuristic the tool computes, which
the design spine forbids (the tool records judgment, it never exercises it). (3) It bounds
resume cost by outstanding work rather than plan size, the property `requirements:62` asks
for. The framework is built now, not with the GUI, because retrofitting a scope column
means back-filling a level for every attachment ever made — a judgment nobody could make
retroactively. Same "bake in the invariant early" argument as D2 and the §5 citation rule.

**Risk carried:** the scheme concentrates relevance into one judgment per finding (which
level). Too-low is silent and surfaces at execution; too-high bloats every packet
invisibly. Instrumented by `decisions:14` (execution sufficiency = the allocation miss
rate) and mitigated by the asymmetric friction above. See `M5_PLAN.md` §2.5.

A `session` scope level was in the owner's original phrasing and dropped on review: the
other three are plan structure, whereas a session is an episode of work — and
session-scoped attachment is what the journal already is.

---

## D9 — Gates hard-lock on outstanding problems (owner requirement)

**Status: requirement logged 2026-07-20, built at M6.** Bound to the M6 gate under the
outstanding-problem rule — M6 cannot pass with D9 unbuilt.

**Plan:** gates in the frozen plan **warn, they do not block** — `decisions:31`'s
keep-pushing policy and D7. The single hard block is `requirements:32`: `UnresolvedFindings`
blocks `finalize_plan`, at finalization *alone*. Everywhere else, an outstanding problem can
be walked past.

**v2 (owner decision, 2026-07-20):** every outstanding problem is either resolved or bound
to a named **resolve-by gate**, and gate passage is hard-locked:

1. A gate cannot pass while a problem allocated to it remains unresolved.
2. A problem with **no** allocated resolve-by gate locks **every** gate until one is
   assigned. (Removes the escape hatch of never allocating so nothing ever blocks.)
3. Resolved problems are metric-only — never surfaced as pending work.

This generalises `requirements:32` from finalization-only to every gate, with an allocation
model attached.

**Why:** a keep-pushing *warning* is easy to walk past; "you cannot pass this gate until
this is resolved or explicitly re-scheduled to a later gate" is what makes an outstanding
problem impossible to lose. `decisions:14` (execution sufficiency: zero sub-tasks blocked by
missing plan information) is only credible if problems cannot silently survive to execution.

**The reconciliation M6 must build, not blur:** this must NOT resurrect the cry-wolf failure
D7 fixed. Advisory **warnings** (open gaps in a package, coverage meter) stay warn-don't-block
per `decisions:31` — they inform, they do not lock. The hard-lock binds a distinct,
higher-severity class: **outstanding findings** (`state_machines:7`) and, to be settled in
M6, whether unresolved **conflicts** (`state_machines:4`) and open **assumptions** join them.
The lock class must be genuinely narrow, or the tool becomes a nag that cannot be satisfied —
the exact failure `decisions:31` guards against. Getting the severity line right *is* the M6
design work; D9 fixes the requirement, not the entity list.

**Open sub-questions for M6 (each resolve-by the M6 gate):**
- which entity classes are lock-class vs advisory (findings yes; conflicts/assumptions TBD);
- where the resolve-by-gate allocation is stored (rides on the finding/conflict row, keyed on
  lineage root per `requirements:78`, like §D8 allocations);
- how the global lock (clause 2) surfaces — it must name the unallocated problem, or it is an
  opaque "everything is blocked" with no route out.

**Contradicts:** `decisions:31`, D7 — logged here rather than folded in silently, because
reopening the keep-pushing policy is a real design change and must read as one.

---

## D10 — SubTask readiness is a level-triggered predicate, not an edge-triggered event

**Status: decided 2026-07-21 (owner approved), built at M5a.** Resolves DEFECTS.md F19(a)
and sets the shape of F18's readiness contract.

**Plan:** `state_machines:9` models readiness as an **event**: `deps_satisfied` fires and
moves `pending → ready` (`sm_cells:130`), `rework_flagged → ready` (`sm_cells:160`). The
plan never says what fires it, and no contract does (F18) — so it never says whether the
event is raised once, when a predecessor transitions, or evaluated whenever asked.

**v2 does:** readiness is a **predicate over dependency state**, recomputed on demand —
whenever the graph is read, a status is reported, or a sub-task is requested. A sub-task is
`ready` exactly when it is not `done`/`in_progress`/`blocked` and every dependency is
`done`. `deps_satisfied` remains the named transition in the state machine (the recorded
history stays faithful to `sm_cells:130`/`160`), but it is *derived* — the system evaluates
the predicate and applies the transition; nothing external raises the event.

**Why:**

1. **The edge reading is broken, the level reading is not.** Under edge-triggering, a
   `rework_flagged` node is trapped: it is entered from `done`, so all its predecessors are
   already `done` and the `deps_satisfied` edge has fired for the last time. Its only other
   exit is `block`, which reaches `ready` via `blocked → unblock` — arriving at the correct
   state by declaring a block that does not exist. DEFECTS.md F19(a). Level-triggering makes
   the `rework_flagged → ready` transition immediate and correct with no special case.
2. **The alternative fix is worse.** The edge reading can be patched by adding a
   rework-specific re-arm, but that is a second readiness mechanism existing only to serve
   one state — and every future entry into `ready` from a non-`pending` state would need its
   own. The predicate has no such surface.
3. **`graph_status` already assumes it.** `contracts:38` returns "built, in-flight, blocked,
   and stale sub-tasks" as a pure read, computing status at call time. A stored,
   edge-maintained readiness flag would be a second source of truth for the same fact, and
   the two would drift exactly when the graph is revised — the moment they most need to
   agree.
4. **It keeps readiness on the system's side of `crud_grid:35`.** The predicate is evaluated
   from dependency states the system owns; nothing the code engine reports can assert
   readiness directly. This is the same boundary F18 turns on: a gate the graded party can
   open is not a gate.

**One place this changes an outcome the plan's table names, deliberately:** `sm_cells:152`
sends `blocked + unblock` straight to `ready`. Under the predicate, unblocking returns the
sub-task to `pending` and it is *presented* as ready only if its dependencies actually
allow. The table's version is safe only because it assumes the sub-task was servable when
it blocked; a sub-task blocked from `pending` with unfinished dependencies would be handed
back as ready and then served, which is `sm_cells:131` ("unbuildable work is never served")
violated by its own state machine. The predicate cannot produce that state. Recorded rather
than folded in silently, because it is a transition outcome differing from a named cell.

**Cost, accepted:** readiness is recomputed rather than cached, so a graph read is O(edges)
rather than O(1). At the scale the plan targets (one contract implementation unit per
sub-task, `decisions:63`) this is not worth caching, and caching is what would reintroduce
the drift in (3). If it ever matters, memoise per read — never persist.

**Related:** DEFECTS.md F18 (the readiness contract this shapes), F19 (both halves).

---

## D11 — The provider/consumer dependency edge is a typed link

**Status: decided 2026-07-21, built at M5a.** Resolves the engine half of DEFECTS.md F20;
the methodology half is bound to M6.

**Plan:** `decisions:63` derives task-graph edges "directly from **contract_deps**". No such
thing exists in v2 — it was a v1 table with explicit provider/consumer columns, flattened
into the generic `links` table (`entities:15`) by the package-6 architecture. See F20.

**v2 does:** the dependency is recorded as a **typed link**, `edge_type='depends_on'`,
directed **consumer contract → provider contract**. `finalize_plan` derives sub-task edges
from links of that type between two `contracts` rows, and from nothing else. Untyped
(`'links'`) edges are traceability and never imply a build dependency.

**Why:**

1. **The information has to be typed somewhere, and the column already exists.**
   `links.edge_type` is in the schema, `LinkSpec` takes it, `LinkGraph.closure` and
   `find_cycles` already filter traversals by it, and `conflicts.py` already uses a second
   type (`'contradicts'`) for exactly this reason — a different *kind* of relation that must
   not be walked as if it were traceability. This is the second instance of that pattern,
   not a new mechanism.
2. **Direction is consumer → provider so the edge is owned by the row that knows it.**
   Links are immutable and created with their source row (`entities:15`), so an edge can
   only be written by the row that owns it. A contract knows what it consumes at the moment
   it is written; a provider cannot know its future consumers without its links being
   mutable, which `entities:15` forbids. Note this inverts the frozen plan's *presentation*,
   which prints "consumed by:" on the provider — that is an export convenience, not a
   storable direction.
3. **It keeps derivation deterministic, which was `decisions:63`'s whole purpose.** Deriving
   from untyped links would make every citation a build dependency: a contract citing a
   requirement, a finding, or a sibling for context would acquire a spurious edge, and
   `finalize_plan`'s `CycleDetected` would fire on traceability loops that mean nothing.

**Cost, accepted:** rows already written by this build carry no `depends_on` edges, so a
graph derived from the current store is all-roots — every sub-task ready at once. That is
correct behaviour on data that declares no dependencies, not a silent failure, and
`finalize_plan` reports the edge count so an all-roots graph is visible rather than assumed.
Back-filling the edges for the dogfood plan is an M8 concern.

**Related:** DEFECTS.md F20, `decisions:63`, `findings:11`.

---

## D12 — A sub-task owns an explicit obligation surface; split redistributes it

**Resolves:** DEFECTS.md F23. **Built in M5b, 2026-07-21** — `engine/obligations.py`.

**The plan says:** a sub-task is the implementation unit of exactly one contract
(`decisions:63`), `split_subtask` "divides along the contract's param/error surface"
(`decisions:63`), and a split is rejected when "the parts do not jointly cover the original
sub-task's contracts" (`contracts:40`). The plan never says what the covered set *is*, and
under one-contract-one-sub-task the stated check is vacuous — see F23.

**v2 does:** a sub-task owns a set of **obligations**. An obligation is one discharge-able
commitment of its contract — the primary behaviour of the signature, and each enumerated
error condition. `split_subtask` **redistributes** the original's obligations among the
parts; it never invents or discards them. Coverage is enforced as a database invariant —
every obligation of a live sub-task is owned by exactly one live sub-task — rather than as a
procedural comparison of contract refs. `PartsDontCover` fires when the union of the parts'
obligations is a proper subset of the original's, and names exactly what was dropped.

**Where the obligation set comes from, which is the load-bearing part.** It is enumerated
**by the planning session** and frozen against the sub-task **at finalization** — before,
and independently of, any split that will later be measured against it.

Three ways to source it were considered and two rejected:

1. **The tool derives it** by parsing the contract row. Rejected on the design spine — the
   tool records judgment, it never exercises it — and on fact: `plan_rows.content` is
   free-form JSON with no per-table schema (`engine/schema.py:30`), so a contract's
   enumerated errors are a methodology convention, not a storage guarantee. Deriving would
   mean the tool inferring an accounting denominator from prose.
2. **The splitting session declares it at split time.** Rejected: it hands the denominator
   to the party being audited. That is precisely how `findings:18` was gamed — accounting
   satisfied by shrinking what counts — and `requirements:79` exists because of it.
3. **Enumerated at finalization, frozen thereafter.** Adopted. The session enumerates; the
   tool freezes and enforces. The denominator is fixed while nobody is under pressure to
   make a particular split pass.

Correcting a frozen enumeration later is legitimate but is a recorded, owner-visible act,
the same friction shape as `requirements:79`'s waiver log and D8's promotion reason: **the
accounting can be changed, but not silently.**

**What this buys beyond fixing F23:**

- `verify_completion` (`contracts:62`) resolves M5a's open hook. Evidence maps per
  *obligation*, not per contract, so a part cannot discharge its parent's whole contract by
  producing evidence for its own slice. `TaskGraphService._scope_contracts` returning a
  1-tuple was the placeholder for exactly this.
- The `subtasks.contract_ref UNIQUE` constraint is replaced by uniqueness over live
  obligation ownership. The constraint was never really about the contract; it was
  expressing "no journal entry is owned twice", which obligations state directly. Without
  this, `split_subtask` is unbuildable: every part carries the same `contract_ref` and the
  second insert is rejected.
- Split accounting and brief accounting become the same primitive at two altitudes — every
  closure row cited-or-waived (`requirements:79`), every obligation assigned-or-waived.

**Cost, accepted:** finalization gains an enumeration step that did not exist, and the
methodology must ask for the obligation surface when a contract is written. **Shipped
2026-07-22** in rev 3's architecture package — package 6, where contracts are authored, not
package 7 as this entry originally said. Until then the tool froze a denominator nothing had
asked anyone to declare, so every sub-task arrived unenumerated and therefore unsplittable. Sub-tasks derived before this lands have no obligations recorded; the graph treats
an empty obligation set as "not yet enumerated" and refuses to split such a node rather than
silently permitting an unaccountable split.

**Related:** DEFECTS.md F23, F17; `decisions:63`, `findings:11`, `findings:18`,
`requirements:37`, `requirements:79`; DEVIATIONS.md D8.

---

## D13 — Four structural levels: Plan → Package → Task → Sub-task

**Supersedes the three-level scheme in D8.** Resolves DEFECTS.md F24. Owner decision,
2026-07-21. **Built in M5b** — `declare_package`/`assign_task`, the `belongs_to` link read at
finalization, and a finalization guard that refuses an unpackaged task. The binding definitions live in `GLOSSARY.md`; this entry records why.

**The plan says:** nothing. There is no grouping level between the plan and its components,
and no vocabulary for one. `M5_PLAN.md` §2.3 invented three levels — project / milestone /
packet — and M5a shipped them.

**v2 does:** four levels — **plan → package → task → sub-task** — with obligations (D12)
inside a sub-task. Packages are declared; tasks and sub-tasks are derived. No level nests.

**Why a fourth level.** With three levels the middle one was the component, and on a large
plan a subsystem — "the GUI", "the controller" — is far larger than one component and far
smaller than the plan. Every subsystem-wide attachment is then forced up to plan scope, which
is D8 §2.5's "too high" failure: context bloat arriving through the ceiling, spread evenly so
nobody notices. Three levels made that failure *certain* on a large plan rather than merely
possible. The cost is real and worth stating: a fourth level is a fourth rung to misplace an
attachment on, and the silent direction gains a rung too. The countermeasures are unchanged
(recorded promotion reasons, retained promotion history as the owner's review surface), and
they are load-bearing rather than decorative now.

**Why the three original names were all wrong**, each in an instructive way:

- **packet** had *zero* occurrences in the frozen plan — pure coinage — and was a second name
  for sub-task. M5a's own schema comment betrayed it: `scope_key` documented as "packet
  **subtask id**".
- **milestone** appeared in the frozen plan only inside the phrase "milestone-time
  re-planning" (`decisions:8`/`decisions:14`) — a term borrowed from the *failure* vocabulary
  and mistaken for a domain entity. It shipped as a free-text column with no entity, no
  creation mechanism and no owner.
- **project** duplicated `Plan`, the actual root entity.

**Packages are declared; everything else is derived.** A package is the one level a human
chooses, so it is the one level that needs entity discipline: a row with an id, an owner and
supersession tracking, referenced by id and never by name. A free-text grouping key yields an
empty context set on a typo — the sub-task silently missing its mid-level context, which is
precisely what `decisions:14` measures. Tasks derive one-per-component and sub-tasks
one-per-contract, so neither can be misfiled.

**Membership is mandatory, with no default bucket.** Every task belongs to exactly one
package and finalization refuses an unpackaged task. An auto-created catch-all was rejected:
it satisfies the invariant while quietly restoring the three-level model, and a bucket nobody
chose is a grouping nobody reviews. A one-package plan is fine — declared, not defaulted.

**No nesting.** A `parent_id` would allow packages inside packages for free, and it was
refused on two grounds. It is confusing to users and awkward to draw, which is the owner's
call and sufficient on its own. It also reintroduces an arbitrary depth through the back
door: §2.3's argument for scope levels was that the bound on assembled context is
*structural*, not a number someone picked, and unbounded nesting makes context assembly a
tree walk of unknown cost. A package that wants sub-packages is evidence the plan wants
splitting — a signal worth keeping visible.

**Task membership is a typed link** (F24): `edge_type='belongs_to'`, directed contract →
component, member → owner. Identical reasoning to D11: the column already exists, an edge can
only be written by the row that owns it (`entities:15` — links are immutable and created with
their source), and typing it keeps traversal deterministic instead of making every citation a
membership claim.

**Leading the user without the tool judging.** Mandatory membership means someone must
propose a package cut when none is offered. That proposal is a judgment, and the tool records
judgment but never exercises it (`decisions:12`). The division is the one brief composition
already uses (`decisions:52`/`decisions:60`): the **tool** enforces the invariant and refuses
finalization without it; the **methodology** — a vendored package script, not generated text —
instructs the driving session to lead the owner to a cut; the **planning session** proposes
and the **owner** decides. A packaging heuristic inside the engine would be the tool holding
opinions about architecture, the same seed `M5_PLAN.md` §2.2 rejected a read-time relevance
heuristic to avoid.

**Cost, accepted:** M5a's scope-attachment code and schema carry the retired names and are
migrated as part of M5b. The methodology needs a packaging step at the architecture package,
which is an M6 concern (`requirements:71`'s revision path covers shipping it). **Shipped
2026-07-22** as rev 3's packaging round, and it took three new tools with it: neither
`declare_package` nor `assign_task` was exposed on the surface and nothing read the cut back,
so this entry's mandatory membership was enforceable and not satisfiable, and `finalize_plan`
refused every plan authored through the surface (DEFECTS.md **F39**). No user data
exists, so the migration is a rename rather than a back-fill.

**Related:** `GLOSSARY.md`; DEVIATIONS.md D8, D11, D12; DEFECTS.md F20, F23, F24;
`decisions:12`, `decisions:14`, `decisions:63`, `entities:15`.

---

## D14 — One vocabulary for work chunks; `stage` retired; methodology rev 3

**Extends D13.** Owner decisions, 2026-07-21. Binding definitions in `GLOSSARY.md`.

**The plan says:** the planning process has *stages* (1–8) with per-stage gates and per-stage
scripts, and the plan's content has components and sub-tasks. Two vocabularies for chunks of
work, and `plan_rows.stage` records which stage produced a row.

**v2 does:** one vocabulary. **Plan → Package → Task → Sub-task**, everywhere. The
methodology's ordered steps are the **standard package set** for planning work — eight
packages every plan instantiates — as against build packages, which are declared per plan.
Same concept, two layers, two tables. `stage` is retired as a word: `plan_rows.stage` becomes
`plan_rows.package`, per-stage gate criteria become per-package, and the vendored scripts are
`package1_context.md` … `package8_freeze.md`.

**Why one vocabulary rather than two.** An earlier draft of this argued for two universes —
structure ("things you can point at") versus process ("episodes that end") — and kept `stage`
on the process side. The owner rejected it, correctly: planning work *is* work, and a chunk of
it is the same kind of thing as a chunk of build work. The distinction that genuinely exists is
which **table** it lives in, not which word describes it. Keeping a second word for the same
concept is exactly the condition that produced F23 (two spellings of a coverage set, one of
them undefined) and F24 (a relation that existed under one name and not another).

**Three consequences that simplified the design rather than complicating it:**

1. **A gate is named by its container** — plan gate, package gate, task gate, sub-task gate —
   and locks on the outstanding problems bound to that container. D9's hard-lock generalises
   with no special cases; "stage gate" stops being a distinct kind of thing.
2. **`session` leaves the vocabulary entirely.** Its only appearance in the data is
   `writer_lease.session_id`, a string naming the current lease holder — no table, no rows, no
   lifecycle. Prose that said "the session decides" now says "the planner", which is the actual
   actor and was always what was meant.
3. **No work level below sub-task.** "Units" were considered and rejected: `split_subtask`
   already turns an over-large sub-task into real sub-tasks with their own briefs and
   verification, and obligations already subdivide a sub-task for *accounting*. A second,
   ungated subdivision gives one thing two breakdowns and lets "3 of 4 units done" read as
   progress on a sub-task worth zero. **Validation and gating happen at sub-task level only.**

**The rename lands as a methodology revision, not an edit.** `engine/methodology/rev2/` is a
faithful vendoring of PlanTool v1 (`decisions:61`, `findings:4` — never invent methodology),
so renaming inside it would destroy the provenance the vendoring exists to preserve. **rev 3**
is a copy carrying v2's vocabulary, `DEFAULT_REVISION` is now 3, and rev 2 stays on disk
unmodified as the v1 artifact. This is `requirements:71`'s revision path doing the job it was
specified for. Note it pulls part of the M6 work forward: rev 3 was scheduled to also update
v1's tool names (`submit_use_cases` → v2's surface), and that half remains outstanding and
bound to the M6 package gate.

**Also in this sweep:** `tasks` is now a real table (`source_ref`, `package_id NOT NULL`
referencing `packages`), `subtasks.task_id` is a foreign key to it, and `task_packages` is
gone — mandatory package membership is a database constraint rather than a check
`finalize_plan` must remember. `subtasks.task_id` is nullable *only* because a contract with no
`belongs_to` link has no derivable owner; that is reported, never guessed (F24), and full
enforcement lands when those links are written.

**Related:** `GLOSSARY.md`; DEVIATIONS.md D3, D9, D12, D13; DEFECTS.md F20, F23, F24;
`decisions:12`, `decisions:61`, `findings:4`, `requirements:56`, `requirements:71`.

---

## D15 — D9's product form: a gate locks on what was allocated to it

**Decided 2026-07-21 by the owner.** D9 established that gates hard-lock on outstanding
problems; it left the severity line open, and the M6 gate bound the decision here.

**The line proposed and rejected.** I proposed that only *findings* hard-lock, on the test
"does this class have a cheap, legitimate exit?" — findings have `resolve_finding`'s
`accepted_risk`, an open assumption has only an expensive spike, so blocking on assumptions
would resurrect the cry-wolf failure D7 fixed (`decisions:31`). The owner rejected it:
**"we should not be passing gates with unresolved issues logged for that gate."**

He was right, and the flaw in my test is worth recording because it is a general one. I read
the exit set as a fixed property of each class. **The outstanding-problem rule creates a
universal exit** — bind the item to a named later gate. That costs one call and a reason, for
every class. I drew a severity line using an exit set that the governing rule had already
widened.

**The rule, as the product form of `M5_PLAN.md` §0:**

- Every open item carries a `resolve_by` gate.
- A gate refuses while any open item is allocated to it.
- An item with no allocation locks *every* gate — the clause that stops "never allocate"
  being the escape hatch.
- Two exits, both one call: resolve it, or re-allocate to a later gate with a reason.

**`resolve_by` is required at creation and `NOT NULL` in the schema.** Unallocated is
unrepresentable rather than detected. F28 is the argument: a `NOT NULL` column is a mechanism,
and a runtime check for a condition the schema could forbid is a rule waiting to be forgotten.
The clause-3 lock stays as the backstop for rows arriving by migration or import, with a test
proving it can fire. The side effect is the valuable one: raising a finding forces "by when?"
while the context is live.

**Infinite deferral is not a risk, and the owner's argument is why:** *you cannot defer to a
gate that does not exist.* The gate list is finite and known, so the worst case is everything
piling up at freeze, at which point freeze blocks and the plan does not finish — the correct
outcome, reached automatically. No brake is built. `plan_status` reports the pile ("4 items
now due at freeze") as a **forecast**, so the pile-up is visible while there is room to act.

**Gaps are outside the scheme**, and the owner's criterion is better than the one it replaced.
I argued gaps are excluded because they are *derived, not durable* — a fact about storage. His
test is a fact about the work: **who can close it, and when?** A gap is closable by the agent
immediately, from what it already has. An assumption needs the owner or reality; a finding
needs a judgment. Deferring something you could do now is procrastination, and giving it a
`resolve_by` would dignify it. The discipline is authoring-time: analyse each step as it is
written and record the outcome either way.

That also justifies keeping gaps derived rather than stored. Closing one by writing rows has
repercussions — a new extension may need a requirement, or step on a decision — and because
gaps are recomputed on every call, those show up on the *next* call rather than needing a
checklist someone maintains. Stated with its limit: that is *mechanical* repercussion only
(traceability and coverage). The engine will not notice a new row contradicting
`decisions:12`; that is the conflict path and it needs the agent to read.

**Coverage still locks, through gate criteria.** `step_without_extensions` (gap rule) and
`step_has_extensions` (package-2 gate criterion) are the same rule at two moments: the gap
engine asks during the interview, the criterion decides at the gate. Gaps are the early-warning
system for a lock that already exists, not a second weaker lock.

**Related:** D7, D9, D10; DEFECTS.md F28; `decisions:31`, `requirements:32`, `requirements:79`.

### Built 2026-07-23

Findings gained `resolve_by` (`findings.resolve_by`, `NOT NULL`, schema 5, `engine/terms.py`
neighbourhood in `engine/findings.py`), the gate learned the lock, and the second exit got a
tool. What landed and where it departed from the writeup above:

- **`resolve_by` is a required argument to `file_finding`**, a deviation from `contracts:33`
  the same way `name` was (D22): the contract predates the rule, and the tool cannot choose a
  finding's gate for the same reason it cannot choose its name — that is the owner's judgment
  (`decisions:12`). It is validated against the loaded methodology's package range, so an
  allocation to a gate that does not exist is refused at filing, not discovered later.
- **The second exit is `reallocate_finding` (new tool, `DEVIATION`, in `ADDED`).** It moves an
  *open* finding to a *strictly later* gate and costs a reason, recorded in a new
  `finding_reallocations` table — the deferral history is the owner's review surface, the same
  friction shape as `obligation_amendments` and scope-promotion history. Deferring backward or
  deferring a closed finding is refused.
- **The lock is engine-level, beside the conflict block, not a `gate_criteria.yaml` entry.**
  The rule holds for every gate of every plan whatever methodology is loaded, so it cannot be a
  per-package methodology asset. It reports a *hole* (`criterion_id = "d15_resolve_by_lock"`, a
  word not a citation, the honesty the surface's `DEVIATION` sentinel makes visible) rather than
  raising, because the plan is readable — there is simply an outstanding item with this gate's
  name on it — so it composes with the package's other holes.
- **The lock stands aside where a `findings_resolved` criterion already runs** — the
  adversarial package (7) carries `findings_dispositioned`, which refuses *every* open finding
  regardless of allocation, so the lock there would only name the same finding twice. It is not
  the *terminal* gate that is special (an early misread I corrected while driving it): the
  catch-all lives at package 7, and package 8 re-runs it through `prior_gates_green`, so a
  finding allocated to any gate still cannot reach a frozen plan open. The two are not redundant
  elsewhere: this one fires at the earlier gate the finding was bound to, which is the
  pile-up-at-the-catch-all the scheme exists to break up.

**Where the implementation contradicts the writeup, on the record.** Above I wrote both that
"unallocated is unrepresentable" (`NOT NULL`, F28) *and* that "the clause-3 lock stays as the
backstop … with a test proving it can fire." Building it, those two cannot both hold: `NOT NULL`
plus range-validation at creation means a genuinely unallocated finding cannot be written through
the service at all, so there is no state for a clause-3 backstop to fire on and no way to write a
test that reaches it. The escape hatch clause 3 feared — "never allocate" — is closed at the
*front door* by F28 instead of at the gate. The rule's intent survives intact by a different
route: `findings_dispositioned` at finalization refuses any open finding whatever its allocation,
and finalization cannot be skipped, so no finding can reach a frozen plan unresolved. I did not
build a NULL-backstop that the schema makes untestable; that would be a mechanism dressed to look
like the writeup while checking nothing (the F23 shape). If the owner wants the backstop, it needs
`resolve_by` nullable, which reopens the front-door hole F28 closed — a real trade, his to make.

**Related implementation:** DEFECTS.md F28; schema version 5 and its 4 → 5 migration (which makes
every pre-D15 finding's implicit "resolve by finalization" explicit rather than inventing one).

---

## D16 — An assumption is attacked when it is made, not audited five packages later

**Decided 2026-07-21 by the owner:** *"assumptions are incredibly dangerous to any plan, there
really should be an attempt to always remove them by experimentation and validation as they
happen."*

**The hole that prompted it.** The only mechanism challenging an unbacked world-assumption is
`world_assumption_backed`, a **package-6** gate criterion. Package 1 is context and goals —
where the most load-bearing assumptions are made. An assumption filed in the first hour
therefore survives five packages, with requirements, a domain model, dependencies and an
architecture built on top of it, before anything mechanically asks whether it is true. If it
is false, all of that is rework: the milestone-time re-planning failure this tool exists to
prevent, reproduced inside the tool.

**Registration is separated from conclusion, and that is what makes "as they happen"
affordable.** Concluding a spike is expensive — the experiment has to run against the real
dependency, and often cannot run now. *Registering* one is cheap: the hypothesis, what would
confirm or refute it, and an `open` row.

- **A world-assumption cannot be filed without a spike registered against it, atomically, in
  the same act.** Unbacked becomes unrepresentable rather than detected later — the F28 move,
  where a constraint at the moment of writing beats a check someone must remember to run.
  `world_assumption_backed` stops being the first line of defence and becomes a backstop with
  nothing to find.
- **An intent-assumption goes to the owner in the same turn.** No engine mechanism can force
  the conversation, so this is methodology: the package script leads. The upgrade-in-place
  path already exists (`contracts:11`).

**The owner-accepted risk survives, gated behind the attempt.** `world_assumption_backed`
accepts `[spikes, accepted_risks]`, so accepting a risk already counts as backing — a fact I
asserted the opposite of in discussion, without reading the criterion. It is not deleted,
because a genuinely untestable assumption would otherwise wedge the plan forever. It becomes
**admissible only once a spike exists and has concluded**, including `inconclusive` and
`blocked`. The owner can always accept the risk; they cannot accept it *instead of looking*.

**Stated with its limit.** None of this catches an assumption nobody labelled as one. A row
filed `decided` that is really a guess is invisible to every mechanism here. That is what the
mandate's divergence rounds and the red-team package are for, and they are judgment, not
enforcement.

**Related:** D15; `requirements:5`, `requirements:26`, `contracts:11`, `contracts:30`,
`decisions:61`, `findings:4`.

**Built (2026-07-23).** Two coupled mechanisms.

*The filing lock.* `RowSubmission` gained a `spike` field. A world-assumption submission must
carry it; anything else must not (a spike resolves world-assumptions only, so one on a decided
row or an intent-assumption is a caller mistake worth naming, not dropping). `submit_rows`
enforces this per row and writes the spike into the `spikes` table in the **same** atomic
write, its `assumption` column borrowing the row ref via `FromOp`, exactly as a link does — so
the assumption and the experiment that will attack it commit together or not at all.
`supersede_row` carries the identical lock, because replacing a decided row with a
world-assumption is the second door that mints one; guarding only `submit_rows` would leave it
open (the F28 side-door lesson). `register_spike` survives as the *further* spike — the second
experiment after an inconclusive first — and now shares the op-builder, slug and directory
helpers with the atomic path (DRY), so the two writers cannot spell a spike differently.

*The backstop.* `world_assumption_backed` was rewired to read the real stores rather than a
`links` row nothing writes — that pre-existing hole is F42. Backed now means the spike has a
recorded outcome (it was run) **and** the owner has recorded acceptance of the residual risk.

*The owner's ruling on "backed" (2026-07-23), and the one place I extended it.* Al accepted
the recommendation — backed = the spike has a recorded outcome — and sharpened it:
**inconclusive is a very weak response; proceeding on it needs the owner's explicit sign-off.**
An accepted-risk finding on the assumption is that sign-off (`resolve_finding(..., accepted_risk,
rationale)`, whose rationale is the owner's recorded acceptance). Since `confirmed`/`refuted`
close the assumption, the only outcomes that reach the gate are `inconclusive` and `blocked` —
and I applied the sign-off requirement to **both**, not inconclusive alone. `blocked` means the
dependency could not even be reached (`requirements:26` keeps such an assumption visibly open
and unsettled); riding it into a frozen plan on silence is at least as weak as inconclusive, so
the same "look, then let the owner accept the risk" gate applies. Flagged here so the owner can
narrow it back to inconclusive-only if he disagrees.

*The escape hatch, honoured.* The design says the owner can always accept the risk but "cannot
accept it instead of looking". The two-part check enforces exactly that: an accepted risk with
no concluded spike does not pass (no recorded outcome → hole), and a concluded-but-weak spike
with no accepted risk does not pass either.

---

## D17 — The digest points at what it stands for; it never carries it

**Decided 2026-07-22 by the owner**, settling the two questions M6 was hard-locked on:
whether `plan_status` returns the mandate and package script by value or by reference, and
whether the digest names what to fetch.

**Plan:** `requirements:10` says a session opening in a workspace with a plan gets back "the
full plan state: current stage, gate history, outstanding warnings, the engineer's mandate,
the current stage script, and row contents on demand". Read plainly, the mandate and the
current script come back as text.

**v2:** `plan_status` names them and the calls that fetch them — `get_mandate`,
`get_package_script` — and carries neither. It carries no row content either. Every count it
reports is accompanied by the call that retrieves what the count stands for, and the digest
closes by stating the single next action in a sentence.

**Why, on the by-reference half.** The two documents total about 7 KB and change only when
the methodology revision changes. They need to reach a session **once**, and the only party
who knows whether they have already arrived is the caller. Attaching them to every call
spends that 7 KB on every mid-package status check, which is most calls.

The reasoning that produced the question is worth recording, because it was wrong in an
instructive way. Three options were weighed — by value, by reference, and by value on the
first call only — and all three assumed the *tool* had to work out when the documents were
needed. The third was an attempt to make the tool remember who had called it, which is
session state, the exact thing this build spent M6b deleting. The caller already holds the
knowledge. Nothing needs remembering, and the question dissolves rather than being traded off.

`requirements:62` is the row that agrees: rehydration is a compact digest plus targeted
reads, and a full dump is never the default path. `requirements:10`'s list is what a resuming
session must be able to *reach*, not what must arrive in one payload.

**Why, on the naming half — this is the part that does the safety work.** A count on its own
invites a session to reason about the number instead of reading what it counts: *only three
warnings, that's fine.* And a resuming session handed a tidy summary with no instruction
invents a plausible next step rather than asking for one. Both are the same failure — read
the digest, feel informed, fetch nothing, proceed on a summary — and it is F14's shape: a
check that ran, passed, and meant nothing. `requirements:58`'s "next intended action" stops
being a stored string and becomes the digest's closing sentence.

**The cost, stated.** By reference is one extra round trip at the start of every cold
session. That is the whole price, and it buys a status call that stays small for the life of
the plan.

---

## D18 — The surface exposes six calls the plan sends nowhere near it

**Decided 2026-07-22 by the owner** ("go with your best judgement"), building `mcp-surface`.

**Plan:** every contract that reaches the tool surface says so on itself, with a `consumed
by: components:15` line. Thirty-nine do. `get_mandate` (`contracts:17`),
`get_package_script` (`contracts:65`) and `active_warnings` (`contracts:23`) do not — they
are declared as consumed internally. `compose_brief` (`contracts:68`) names `contracts:55`
alone. `journal` and `gate_runs` are not contracts at all.

**v2:** all six are exposed as tools, making thirty-seven.

**Why.** `plan_status` closes by telling a resuming planner what to fetch, which is D17's
ruling and a good one. It names six calls. Before this build package, **one of them could be
reached** — the other five could not be called by the party being told to call them. A cold
planner was being handed instructions it had no way to follow.

There were two ways out. Reword the digest so it names only what happens to be exposed, or
expose what the digest names. The first lets the specification's internal bookkeeping decide
what a planner is allowed to know, which is backwards: `consumed by` records who the plan's
authors expected to call something, and that expectation was made before the resume digest
existed. The prose is the better witness — the plan's own text says composing a brief is "a
separate second call" made by the planning session, which reaches the tool only through this
surface, so `contracts:68`'s consumed-by line is simply wrong.

`journal` and `gate_runs` are ours, added while building session-service and while fixing
F30. They were named in output and specified nowhere, which is how a call gets into a message
without anyone deciding it should exist. They now have entries here and tools of their own.

**Why this is safe to widen and not a licence to keep widening.** Every one of the six is a
read. None of them writes, so the surface gains no authority it did not have; a planner can
learn more and change nothing. Widening the *write* surface beyond the plan's declarations
would be a different decision and is not made here.

**What stops it drifting.** The registry test parses the thirty-nine contracts out of the
frozen plan, subtracts the declared exclusions and deferrals, and fails on any shortfall — so
the widening is visible rather than absorbed. And the door now resolves every call name in
outgoing text against the registry, so if one of these six is ever dropped, the digest that
names it fails loudly instead of quietly lying to the next cold planner.

---

## D19 — Never emit an address without the name of what it addresses

**Owner's requirement, 2026-07-22**, designed alongside the row-naming work and built here
because the surface is where it can be a mechanism.

**Plan:** rows are addressed as `table:ordinal` (`requirements:61`). The plan says nothing
about how an address is presented, because it never occurred to it that an address might be
all a reader gets.

**v2:** an address never leaves the tool alone. Every one carries the name of the row it
addresses, in one form — `name (table:ordinal)` — and the surface refuses to return text
that breaks it.

**Why.** An address on its own makes the reader go and look it up. A person does not; a model
answers from what it can reconstruct, which is invention. The owner raised it after a session
of being handed bare addresses, and then explicitly declined a fix aimed at the way this
assistant writes prose, asking for one that works for any planner and any model. This is that
fix.

**The two layers, and which one does the work.** Rendering is the first: a stored address
cannot reach a payload without passing through a name lookup, so the code path that emits a
bare one no longer exists. The second is a scan of the finished payload, and it is the one
that holds — hand-assembled message strings are invisible to the type system, and
hand-assembled strings are where every instance so far has come from. Building it caught one
immediately: the gate's own unresolved-assumption warning named a row by address, which broke
the resume digest that carries it.

**The exemption, and why it is not a hole.** Stored prose is served exactly as written — a
brief serves the plan's own text, and text edited in flight is a far worse defect than a
lookup. So stored strings are annotated rather than rewritten: every address they cite is
resolved beside the payload. That is also where a dead citation becomes visible, resolving to
"no live row at this address" instead of dangling.

**Annotation never changes a value's shape**, which was learned by breaking it. The first
version replaced an annotated string with an object carrying the text and its citations. Gap
keys and warning keys are identifiers that happen to contain an address, so a caller who read
one could no longer hand it back to `dismiss_gap`. The tool had broken its own round-trip in
the course of making itself readable.

**What it does not catch,** stated so it is not oversold: a name that is present, unique,
fresh and useless; an address the owner types into his own content, which is input and is
annotated rather than refused; and prose that is hard to read for any other reason.

---

## D20 — Never name a call the surface does not expose

**2026-07-22**, the second half of the same door.

**Plan:** nothing. No row says that a message naming a call must be able to name a real one,
because no row anticipated the tool composing instructions for its reader.

**v2:** every call name in outgoing text is resolved against the tool registry, and one that
does not resolve fails the call.

**Why it is the same rule as D19 rather than a second one.** Both say: the tool never points
a reader at something the reader cannot get to. One pass over the payload, two lookups. It
is cheap, exercises no judgment, and it is what turns D18's widening from a decision that
must be remembered into one that cannot be undone by accident.

**Its known limit is real.** The vendored methodology is served verbatim and is therefore
exempt at runtime — the tool must not edit the owner's methodology in flight. So the check
for that content moved into the test suite, where it immediately found the mandate telling
every cold planner to resume from a call that does not exist.

---

## D21 — The plan is rendered to a document the owner reads, and only in that direction

**Owner's ruling, 2026-07-22.** Put to him as a question the last planning package could not
be executed without, and answered before any of it was built.

**Plan:** nothing. `V2_BUILD_PLAN.md` scoped plan extraction and rendering out of the build
entirely, so no contract renders anything and the frozen plan declares none.

**v2:** `render_plan` writes `plan.md` into the workspace from the live rows. There is no
import, no round-trippable bundle, and no way for anything on disk to become plan content.

**Why the charter is not reversed by this.** What the charter cut was a `plan.yaml` you could
edit outside the tool and read back in — a second write path into the plan, next to the one
that holds provenance, supersession, containment and naming. That is still cut and is the
part worth having cut. What is built is one direction: rows out, formatted, into a file. The
database remains the only source of truth and the file is a photograph of it.

**Why it had to exist at all.** The last package's procedure is: render, skim it with the
owner, gate, finalize, render again. The skim is the last cheap moment for "that is not what
I meant" — everything after it costs a revision — and it is not replaceable by reading rows
back through the tool. Nobody catches a contradiction between package 2 and package 6 by
paging through `read_rows`; that contradiction is only visible when the whole plan is in
front of one pair of eyes at once. Without the render the package could not be run, which is
where F34 and F35 both ended up.

**Two properties that fall out of the direction, and both are load-bearing.**

*The document goes to disk; the receipt comes back.* `requirements:62` says a full-plan dump
is never the rehydration path, and a tool that returned the whole rendered plan as a string
would be exactly that under a friendlier name. So the call returns where the file went and
what went into it. The owner opens the file; the planner keeps reading through `read_rows`.

*Addresses are annotated, never rewritten* — D19's rule, applied in the one artefact read end
to end. A row's prose citing `contracts:52` is the owner's text and is served as written; the
resolution goes in a line beneath the row. That is also where F17 becomes visible to the only
person who can act on it: a citation whose row was superseded resolves to a name and a state,
and one that reaches nothing says so.

**`get_auxiliary` is exposed in the same act, for the same reason.** The red-team script is a
content asset `requirements:71` ships, the guidance service could already serve it, and no
tool exposed it — so the red-team session, which is by design a fresh session that has been
told to fetch its own brief, could not fetch it. Same shape as D18's widening and the same
justification: it is a read, and the alternative was a methodology that names a document the
tool will not hand over.

**What stops this drifting.** Both tools carry `DEVIATION` in place of a contract address
rather than a plausible-looking `contracts:N`, and a test requires that every tool carrying it
appears in `ADDED` with its reason, and that every entry there is a tool that exists. The
coverage test reads plan → surface and would never have noticed a tool nothing asked for;
this reads the other way.

---

## D22 — Findings keep their own store, and the gate learns to read it

**Owner's ruling, 2026-07-22**, on DEFECTS.md F38: `findings` addressed two stores at once.
`file_finding` writes a service table; the package-7 gate criteria read `plan_rows`. A red
team following its own script filed every finding where the gate could not see it, and the
gate reported "no adversarial findings recorded" however many were filed.

**Plan:** ambiguous, which is how this happened. `contracts:33`/`34` give findings their own
service with a lifecycle (`state_machines:7`), while the frozen plan's *own* red-team results
are rendered `findings:1` … `findings:13` in the same `table:ordinal` form as every plan row.
Both readings are supported by the text.

**v2:** a finding is not a plan row. It keeps its own store, gains a `name`, and is addressed
`findings:N` by a resolver rather than by living in `plan_rows`.

**Why that way round.** Not because it is the smaller change, though it is. A plan row is
write-once — `requirements:61` says content is never edited and changing your mind writes a
successor with recorded lineage — and a finding *moves*: filed, then addressed or
accepted-as-risk or withdrawn, with a rationale attached at the transition. Forcing that into
`plan_rows` gives one of two bad outcomes: a supersession per disposition, so every finding
leaves a two-row lineage recording nothing but its own paperwork, or mutable columns on
`plan_rows`, which ends `requirements:61` for one table to spare a second table elsewhere. A
finding is also *about* the plan rather than part of it, and served through `read_rows` it
would reach every brief and every render as though it were plan content.

**The insight that made it cheap:** addressing was never a property of `plan_rows`.
`table:ordinal` is a naming scheme, and what it needs is somebody able to resolve it. So the
door's resolver takes a second lookup and two stores share one address space. Without it,
every `findings:3` in the owner's own prose came back as *no live row at this address* — the
tool reporting the F17 damage it exists to detect, where there was none.

**Three parts, because one would not have held.**
1. Two gate criterion types — `findings_exist`, `findings_resolved` — instead of a `table:`
   that might mean either store. A `table:` key accepting both would have left the same
   ambiguity in place with better manners. The type says where it looks. The old criteria
   also checked `disposition`/`disposition_rationale`, v1's names for `outcome`/`rationale`,
   so they would have found nothing to check even in the right store.
2. The door's resolver, above.
3. **`findings` is a reserved plan-row table name**, refused at submission with a message
   naming `file_finding`. `plan_rows.table` is deliberately open — a methodology declares its
   own row types and the engine knows none of them — but open means a name owned elsewhere
   can be claimed by accident, and this one already had been. Deciding which store owns the
   word is half a fix; without the refusal the collision returns as data the first time
   somebody submits the obvious-looking row. A rule with no mechanism is not a rule.

**`file_finding` gains a `name`, which changes a frozen contract's signature.** `contracts:33`
predates D19, and `findings:N` is an address that reaches gate holes, the resume digest and
the owner's prose — so it may not travel alone. The tool cannot supply the name: deriving one
from the description is exactly the guess D19 removed, and F32 found three copies of. A
session that has just written the description can write the six-word version. The one finding
the tool files itself — plan state unreadable — is named by the tool, because there the tool
is the author.

**Schema version 3, with no migration path and that is the honest answer.** `name` is NOT NULL
and cannot be backfilled, because inventing one from `description` is what the column exists
to prevent. No plan outside this repo's tests was ever written at version 2.

---

## D23 — The plan's glossary is a real table, and the tool publishes it

**Not in the frozen plan at all.** Verified: zero occurrences of glossary, terminology,
vocabulary or "term" in `spec/v2/plan.md`, and none of its 16 row types is a term type. The
eight planning packages interview for use cases, entities, contracts, decisions and failure
modes and never ask *what do you call things, and what do those words mean?* — logged as
DEFECTS.md **F40**, because that is a hole in the planning method and not only in this build.

**Why it exists.** F27: a binding vocabulary was written down and broken by the next build
package, in the same branch. The cause is not carelessness and it is what the design follows
from — the one document where retired words legitimately survive is also the document read
immediately before writing each function, so ranked by proximity to the moment of typing the
exception beats the rule; and naming happens at the point of *least* attention, because the
thinking goes into the algorithm and the name is incidental typing. A word in a document
cannot fix that.

**A real table, not a `plan_rows` row type** — the owner's call, against my argument for the
row type, and he was right on two counts I had missed.

1. **A term needs two relations the generic layer collapses into one.** *Redefinition* (same
   word, sharpened) and *replacement* (this word is out, say that one) are both
   `superseded_by` in `plan_rows`. One mechanism serving two relations is this document's
   own subject matter, inverted.
2. **D12's reasoning already forbids it.** An accounting denominator may never be inferred
   from `plan_rows.content`, which is free-form JSON with no per-table schema. The
   banned-word list *is* a denominator, so `ban_scope` has to be a column something can
   query. That is the same argument that made `obligations` a table.

It also corrects `GLOSSARY.md`'s two-layer rule, which said planning = generic and execution
= typed. `obligations` is enumerated by the planning session and is typed, so the line was in
the wrong place. The real one is **content vs structure**: a row that makes a claim about the
domain is generic and interchangeable; a thing that constrains or organises other rows gets a
real table.

**A definition is proposed by the planner and settled by the owner** (added on the owner's
instruction, 2026-07-22: *"what is a glossary without definitions?! They should be suggested
by you and approved or re-written by the user."*). `definition` is required — a glossary is
its definitions, and a list of approved words with no meanings is a spelling test. But a
definition the tool took from a planning session and filed as settled would be the tool
deciding what the owner's own words mean while looking like a record of him deciding, which
`decisions:12` forbids. So `define_term` *proposes*: the session writes the first draft,
because it has just read every row the word appears in and that is the cheap half.
`approve_term` is the owner accepting it or replacing it with his own wording, and a rewrite
**supersedes** the proposal rather than overwriting it — the difference between the two is the
most interesting line in a glossary's history, being exactly where the tool's reading of the
plan and the owner's diverged. A redefinition is proposed again, because approval that
survived the definition it approved would record the owner's assent to words he never saw.
The overhead is deliberate and small: a glossary is a handful of words, and the owner said so
when asking for this.

**The trap, and it is the whole reason this entry is long.** A retired word must stay in
**live reads**. Everywhere else in v2 retirement drops a row out of live reads (settled
2026-07-20 for spike-refuted assumptions); apply that here and the banned list goes *empty*,
so every check downstream runs, finds nothing to ban, and reports success. That is F23's
missing denominator, reappearing inside the mechanism built to prevent F27. So retirement is
`ban_scope IS NOT NULL` and liveness is `superseded_at IS NULL`, and a test asserts that the
list is empty only when nothing has been retired.

**Two departures from the sketched schema**, both for the same reason. `replaced_by` was to
be a `terms.id`; it is the replacement **word** (`use_instead`), because a retirement outlives
the entry it points at — the replacement will be redefined one day too — and the word is the
identity that survives that. And `superseded_by` is `superseded_at`: with the word as the
lineage key, ordering by id over one word *is* the lineage, and a pointer would have needed a
three-statement dance to write past the live-word index for no fact it does not already have.

**Delivery, in descending order of what each actually achieves** (M6_PLAN.md §3.3):

1. **`export_glossary` writes a manifest the codebase's own CI consumes.** The tool publishes
   the vocabulary; the codebase polices itself. This respects `decisions:12` completely — no
   judgment is exercised about anyone's code — works in any language, and is the mechanism
   already proven on ourselves, where a ten-line check found twenty violations a careful
   reading had declared clean.
2. **The glossary is a section of the brief, outside the 100% accounting.** Candidate rows
   are *context* and may be waived with a reason; a glossary is a *constraint on the output*
   and cannot be, or it is not a constraint. `compose_brief` treats every candidate as
   omittable, which is right for context and wrong for a constraint — a distinction the
   frozen plan never draws. It is attached live rather than frozen with the brief, which
   looks like F26's mistake and is its mirror: F26 froze a *denominator* because an
   accounting against a moving set is meaningless, and a constraint is the opposite case —
   it binds as it stands, and nothing counts it.
3. **Warn at submission, count at the gate.** The submission scan is the one that attacks
   F27's actual cause, because the moment of typing is the only moment at which saying so
   changes what gets written. The gate scan catches what submission cannot: the common case
   is that a word is retired *because* the plan has been using it two ways, so the rows
   carrying it are already filed. Both warn and neither blocks — a retired word inside a
   quotation of the owner is legitimate, and refusing one would have the tool editing his
   words.

**`terms` is a reserved plan-row table name**, refused with a message naming `define_term`.
F38's lesson applied before it cost anything: deciding which store owns a word is half a fix,
and `plan_rows.table` is open by design.

**Schema version 4, and this one migrates.** A plan written before the glossary existed has
an empty glossary, and empty is the truthful answer rather than an invented one — which is
exactly what distinguishes it from the 2 -> 3 bump, where a backfill would have had to invent
the names that column exists to prevent. It is also the first migration step this engine has
ever had, so `contracts:8`'s success path is reachable for the first time.

**What none of it catches, stated so it is not oversold.** A word invented for a concept
that already has one, where the two words share no letters — `packet` and `sub-task`, say.
Nothing without judgment can see that the two mean the same thing.

**The counting rule is dead, and what replaced it is better.** The design proposed counting
how often each word appeared across submitted rows and asking about any that recurred with no
definition. The owner killed it on sight — *"are we going to make a glossary entry for
'the'?"* — and the objection is not about the threshold, it is about the kind of thing being
decided: whether a word is load-bearing is a **judgment**, and no count is a proxy for one. It
is the same error the tool refuses everywhere else, wearing arithmetic as a disguise.

His replacement puts the judgment where every other judgment in this system lives — with the
planning session, recorded by the tool:

- **Mandate clause 7**, new: when a round leaves the planner leaning on a word, propose a
  definition for it; and ask the owner which words *they* want pinned down, the ones they
  would be annoyed to see used loosely.
- **`no_glossary`**, a gap at package 2: the plan has content and has agreed the meaning of
  nothing. It asks once, where a use-case round has just made the words matter, and it is
  dismissible — a plan whose vocabulary is genuinely uncontentious is a legitimate answer,
  recorded on the owner's say-so rather than by silence.
- **`unsettled_term`**, a gap per proposed definition. The same shape as an assumed-intent
  row and for the same reason: it carries the planner's best answer, it is visible as
  unsettled, and only the owner can close it. Keyed on the word, so a dismissal survives the
  entry being superseded.

Methodology revision stamp `plantool-rev3-2026-07-22d`, which is F31's rule — content changed,
so the stamp moves.

**What still nothing catches**, and now honestly: a word invented for a concept that already
has one, where the two share no letters — `packet` and `sub-task`. The mandate asks a planner
to notice; nothing mechanical does, and nothing mechanical could without judgment.

---

## D24 — The revision-migration path is forward-only, from rev 3

**The requirement, read strictly.** `requirements:71` provides "an update path that migrates a
plan from one methodology revision to the next." Two revisions are installed, and a plain
reading implies you can migrate *from* either. This deviation records that we do not: the path
is forward-only and rev 3 is its earliest endpoint.

**Why.** rev 2 is the PlanTool v1 methodology vendored verbatim (decisions:61 / findings:4) —
kept for provenance and byte-faithful on purpose, written in v1's vocabulary (`stages:`) and
naming v1's retired tools. It cannot be loaded without either editing it (forbidden) or teaching
the loader to read a revision nothing can author under (option (a) of the rev-2-unloadable fork,
which the owner declined — see DEFECTS.md F43). So there is no loadable revision behind rev 3 to
migrate a plan *up from*, and `load()` now refuses anything earlier with `RevisionNotLoadable`
rather than pretending otherwise.

**What this does not foreclose.** The migration *mechanism itself* — carrying a live plan across
a real revision boundary — is the revision-service's job at M7 (F20/F21 bind there). This
deviation narrows only the set of source revisions that mechanism will ever be asked to start
from: rev 3 onward. If a genuine need to load a v1-authored plan for migration ever appears, it
reopens as option (a); today nothing asks for it, and declaring the floor honestly beats leaving
`load(2)` to fail as if it were a bug.

## D25 — Revision changes apply live and conflict-checked, not deferred to a single apply

**The frozen text.** `contracts:57` reads: "nothing mutates plan rows until apply_revision
commits the entire staged change-set atomically (deferred application)." That wording was the
red team's fix for `findings:5` — you cannot un-supersede a row, so applying changes during the
walkthrough would make `abandon_revision`'s clean rollback impossible.

**What we built, and why.** The owner decided (2026-07-23) differently: when the owner supplies
new wording for a row, the tool runs it through the conflict check, and the moment it comes back
clean the row is **superseded on the live plan right then** — not held to a deferred apply. A
wording whose row is under an *open conflict* is not applied; the conflict is surfaced and the
change held until the owner resolves it. `apply_revision` is therefore the closing act (verify
every repercussion was adjudicated, move the plan `revising → finalized`), not the moment of
mutation.

**Why this is still consistent with write-once history.** Abandon does not try to un-supersede
anything — it rewinds the whole plan to the immutable snapshot taken when the revision opened
(D26). `findings:5`'s own text named "restore the pre-change snapshot" as the alternative to
deferred application, and this build takes it. The rewind is clean because the revision's
analysis record lives *outside* the plan-row snapshot (`requirements:72`), so restoring the plan
never destroys the record of what was tried.

**The conflict gate, concretely.** The tool records judgment and never exercises it, so "checked
for conflict" is not a semantic check the tool performs — it is structural: a row carrying an
open conflict (`conflict.state == open`) cannot be quietly reworded inside a revision. The
resolution of that conflict is the owner's to make. This is the reading of the owner's
instruction "checked for conflict and applied at the point that no conflict is shown."

## D26 — abandon_revision is a confirmed, two-step rewind

**The frozen signature.** `contracts:46` is `abandon_revision(revision_id: int) -> RollbackReport`.

**What we built, and why.** Because changes are live by the time an abandon is requested (D25),
abandoning silently would throw applied work away without warning. So `abandon_revision` takes a
`confirm` flag (not in the frozen signature — hence this deviation). The unconfirmed call is a
**pure read** that returns a `RewindPreview` naming exactly which applied changes a rewind would
revert; only `confirm=True` restores the opening snapshot and marks the revision abandoned. This
is the owner's instruction (2026-07-23): "warn the user of the abandon-by-rewind consequences —
tell them what will change — and allow them to re-approve or abandon the change."

## D27 — A Revision is born in `walkthrough`; `proposed` and `analyzing` are never persisted

**The state machine.** `state_machines:10` lists five states:
`proposed → analyzing → walkthrough → applied | abandoned`.

**What we built, and why.** The analysis a revision runs is `graph.impact` (`contracts:15`), a
synchronous pure read that finishes inside `open_revision`'s own call — there is no asynchronous
"analyzing" phase for anyone to observe or interrupt. So `open_revision` does the snapshot,
version bump and impact enumeration in one atomic act and returns a Revision already in
`walkthrough`. `proposed` and `analyzing` exist in the state machine but are passed through
inside that call and never written. This closes a hole cleanly: `apply_revision` is then always
reached from `walkthrough` (which the state machine makes mandatory before apply, `sm_cells:172`),
so it needs no error for "you have not walked the repercussions yet" — an error its frozen
contract does not offer. Opening a revision and immediately abandoning it remains possible
(abandon from `walkthrough`), so no capability is lost.
