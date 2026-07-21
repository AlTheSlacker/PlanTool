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

## D5 — Writer lock is a database lease, not an O_EXCL lock file

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

**Resolves:** DEFECTS.md F23. Built in M5b.

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
methodology's package-7 script should ask for the obligation surface when a contract is
written. Sub-tasks derived before this lands have no obligations recorded; the graph treats
an empty obligation set as "not yet enumerated" and refuses to split such a node rather than
silently permitting an unaccountable split.

**Related:** DEFECTS.md F23, F17; `decisions:63`, `findings:11`, `findings:18`,
`requirements:37`, `requirements:79`; DEVIATIONS.md D8.

---

## D13 — Four structural levels: Plan → Package → Task → Sub-task

**Supersedes the three-level scheme in D8.** Resolves DEFECTS.md F24. Owner decision,
2026-07-21. The binding definitions live in `GLOSSARY.md`; this entry records why.

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
which is an M6 concern (`requirements:71`'s revision path covers shipping it). No user data
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
