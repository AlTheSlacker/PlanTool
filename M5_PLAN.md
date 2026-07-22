# M5 — Execution Module: design and build plan

Written 2026-07-20, at the end of the design session that un-deferred `task-graph`.
This document is the resume point for the build. It is **self-sufficient after a context
clear**: read this and `V2_BUILD_PLAN.md`, and you have what you need.

Status: **designed, not started.** No code written. Branch is `m5-execution-module`.

---

## 0. The outstanding-problem rule (governs this whole build)

Owner rule, 2026-07-20. Applies to the build process now; its product form is an open
question (§4a).

- **Resolved problems are metric-only.** They live in DEFECTS.md as the execution-sufficiency
  measure; they are never surfaced as pending work. The active surface is outstanding-only.
- **Every outstanding problem is either fixed immediately or bound to a named resolve-by
  gate.** No floating "deferred to build". Deferral is legitimate *only* against a gate.
- **Hard lock, both directions.** A gate cannot pass while a problem allocated to it is open;
  and a problem with *no* allocated gate locks *every* gate until one is assigned. The second
  clause removes the escape hatch of never allocating.

Current outstanding items and their gates (updated 2026-07-21, end of the M5b vocabulary
session):

| Problem | Resolve-by gate |
|---|---|
| ~~F15 — undefined package-7 fix contracts~~ | **RESOLVED 2026-07-21** at the audit; hard lock lifted. The mechanisms all exist — see DEFECTS.md F15 |
| ~~F18 — `deps_satisfied`/`serve_brief` have no firing contract~~ | **RESOLVED** in M5a |
| ~~F19 — `rework_flagged` trap + early-banked verdict~~ | **RESOLVED** in M5a |
| ~~F22 — narrowing an attachment was a silent no-op~~ | **RESOLVED** in M5a |
| ~~F23 — `PartsDontCover` can never fire~~ | **RESOLVED** in M5b — obligation surface built |
| ~~F24 — task membership lost in the package-6 flattening~~ | **RESOLVED** in M5b — `belongs_to`, plus live `packages`/`tasks` |
| ~~F25 — "supersedes the original in the graph" has no mechanism~~ | **RESOLVED** in M5b |
| ~~F26 — `audit_brief`'s denominator is re-derived at read time~~ | **RESOLVED** in M5b — closure frozen into the brief |
| ~~**v1 foreign-key sweep**~~ | **RESOLVED 2026-07-21** in M6 — swept; six more mandatory relations were missing, all repaired as `belongs_to`. See DEFECTS.md **F28** |
| **`spikes` row-level provenance** — v1's nullable `spike_id` on ten row tables ("this row is provisional pending spike N") survives only as `claim_tracks.spike_id`. Not F28's class (it was nullable), but the same loss | **M7 gate** |
| **When does contract ownership bite?** — the other six containment relations are enforced at submission; `contracts`→`components` is enforced at finalization (F24). One relation, two moments. Owner's call, not a side effect | **M7 gate** |
| **Methodology rev 3, second half** — rev 3 carries v2's vocabulary but still names v1's tool surface (`submit_use_cases`, …) | **M6 gate** |
| F17 — prose row citations break on supersession | M6 gate |
| ~~§4 Q1 — mandate/script by value or reference~~ | **DECIDED 2026-07-22** as **D17** — by reference; the digest names the fetching call and carries no text |
| ~~§4 Q2 — digest names what to fetch~~ | **DECIDED 2026-07-22** as **D17** — every count names its fetching call, and the digest closes by stating the next action |
| ~~D9 — gates hard-lock on outstanding problems (product form)~~ | **DECIDED 2026-07-21** as **D15** — a gate locks on what was allocated to it; `resolve_by` required at creation. Build outstanding in M6 |
| **D16 — assumptions attacked on arrival** — a world-assumption cannot be filed without a spike registered atomically; accepted risk admissible only after a concluded spike | **M6 gate** |
| **Glossary delivery to the writer** — F27: a plan's vocabulary is enforced at the moment of writing or not at all. How does a plan's own glossary reach the code engine, and should `compose_brief` carry it as a first-class section rather than as a row that can be omitted? | **M6 gate** |

Nothing is unallocated, so no global lock is in force. **The M5b gate is clear**: F23–F26 were
all fixed while building `brief-composer`, as their binding required. Everything still open is
bound to the M6 gate.

**The pre-build audit is now three checks, not two** (added by F23, amended by F26):

1. Every state-machine event has a contract that fires it.
2. Every outcome a contract's signature offers is reachable from the states the entity can be in.
3. For every coverage/accounting/completeness check: **name the set, say where it comes from,
   and say at what moment it is fixed.** A denominator re-derived at read time measures against
   a moving target — that is F26, caught by this check on its first use.

A fifth, from **F27** and applying to our own prose rather than the plan's: **a rule stated in
a document is not a mechanism.** When this build writes a rule for itself — a naming
convention, an invariant, a discipline — the same question gets asked of it that gets asked of
the frozen plan: *what fires this, and what fails when it is broken?* The glossary spent eight
defect entries diagnosing exactly this pattern in the frozen plan and then reproduced it in
itself within a day.

A fourth is worth considering after F25: a contract that says it *supersedes*, *replaces* or
*supplants* something in the execution layer must say what that does to the thing's edges and
its lifecycle. Plan-row supersession (`requirements:61`) is a defined primitive and reading it
as transferable to a graph node is what F25 is.

---

## 1. What changed in this session, and why

### 1.1 A memory error nearly built the wrong thing

The session opened intending to build `task-graph` + `brief-composer`, on the strength of a
memory that said M5 was those two components. `V2_BUILD_PLAN.md` §7 says M5 is Surface, and
§3/§9 defer the execution module entire, pending a design discussion the owner explicitly
reserved. The memory had reasoned from component *numbering* (9 and 10 are done, so 11 and 12
are next) rather than from the build-package table. Corrected in memory; recorded here because the
failure mode is instructive — **`V2_BUILD_PLAN.md` §7 is the authority on build-package order, not
component numbering.**

### 1.2 The deferral removed the only path out of `draft`

Pre-build audit finding. `finalize_plan` (`contracts:35`) is the sole contract firing the
`finalize` event (`sm_cells:1`) of `state_machines:1`, and it lives on `task-graph`
(`components:11`), line 821 of the frozen plan. Nothing in the built engine writes
`finalized`; `engine/schema.py:18` defaults plans to `'draft'` and no code path moves them.

Three consequences:

1. **`plan_status` drift flags are dead on arrival.** `requirements:73` captures the workspace
   fingerprint baseline "when the plan is finalized or a brief is issued" — finalization is
   task-graph, brief issue is brief-composer. Both were deferred, so no baseline would ever be
   written and the flags could only report "no baseline".
2. **`contracts:61` does not exist.** It is cited as the fix for `findings:10` (workspace
   drift) and appears *exactly once* in the whole plan — inside findings:10's own fix note.
   Compare `contracts:62/65/66/67/68`, which all have real definitions. Drift has a
   requirement (`requirements:73`) and a fix-note but no contract row.
3. **`revision-service` was unreachable.** `open_revision` refuses draft plans. With no
   finalize path, the revision loop could not be exercised at all — falsifying
   `V2_BUILD_PLAN.md` §4.1's assertion that it "is independently useful with no execution
   layer".

### 1.3 The owner un-deferred `task-graph`

Decided 2026-07-20: the execution module comes into scope now, because plan-time context
allocation (§2) and the task graph are too tightly integrated to design separately.

**This removes the need for the carved minimal `finalize_plan`** that was proposed while
task-graph was still deferred. With task-graph in scope, `finalize_plan` is built whole,
returning its `TaskGraph` as `contracts:35` specifies. One fewer deviation.

---

## 2. The design: allocation is a planning-time act

> **Vocabulary superseded 2026-07-21.** This section was written with the three-level
> `project / milestone / packet` scheme. The binding vocabulary is now
> **plan / package / task / sub-task** — see `GLOSSARY.md` and DEVIATIONS.md **D13**, which
> records why three levels were not enough and why the three original names were each wrong.
> The names below have been updated in place; the arguments are unchanged and still hold.

### 2.1 The principle

**Context allocation happens once, at plan time, as a recorded judgment — not at retrieval
time as a computed heuristic.**

When the master plan is built, the planning session looks at the big picture, the data, and
the deliverable, and decides the base reference set for every part of the plan. Execution then
serves what was allocated. Findings that arise *during* execution are placed once, carefully,
at the right scope level, and are thereafter in the right places for the rest of the plan.

Deliberately: ramp up initial cost to control execution cost.

### 2.2 Why this shape and not a read-time heuristic

An earlier proposal in this session had `plan_status` compute a "current working set" at read
time from the open items across gaps/warnings/findings/conflicts. It was rejected, correctly.

A read-time relevance heuristic is **the tool exercising judgment**, which violates the design
spine (`decisions:12` and throughout: the tool records judgment, it never exercises it). The
allocation model has a session make the call, on the record, and the tool serves it. This is
not a stylistic preference — a relevance heuristic is the seed from which "the tool has
opinions" grows.

### 2.3 Scope levels

Attachments carry a scope level: **plan / package / task / sub-task**.

(A `session` level was in the owner's original phrasing and was dropped on review: the other
levels are plan structure, whereas a session is an episode of work — and session-scoped
attachment is what the journal already is. Settled 2026-07-20, do not reopen.)

A sub-task's context is the union of its own attachments and those of every enclosing scope.

This **dissolves the unbounded-journal problem** rather than answering it. `requirements:58`
requires resume to present "accumulated learnings", and nothing in the frozen plan bounds that
accumulation — so as specified, resume cost eventually scales with total session history,
worse than the plan-size scaling `requirements:62` exists to kill. Every candidate bound
(last N, since-last-gate) is arbitrary invention. Under scope levels, resume serves
plan ∪ current-package ∪ current-task ∪ current-sub-task, and the bound is structural rather than a
number someone picked.

### 2.4 Allocations must key on lineage root, not row id

`decisions:3` makes the plan a living source of truth; rows are superseded and revisions
rewrite them. An allocation keyed on row id silently detaches the moment its target is
superseded.

This is exactly `findings:16` / `requirements:78`, where gap dismissals had the identical
problem and the answer was to key on target-row **lineage root**, supersession-stable by
construction. Allocations take the same keying. This is the second application of that
primitive in the plan, which is mild evidence it is the right one.

### 2.5 The risk, and the countermeasure

The scheme concentrates risk in a single judgment per finding: which level to attach at.

- **Too low** — the sub-task that needed it does not get it. Silent, discovered at execution:
  precisely the failure this tool exists to prevent.
- **Too high** — a plan-level attachment is in every sub-task forever. Context bloat returns
  through the ceiling instead of the floor, and nobody notices a cost spread evenly.

Two countermeasures:

1. **Asymmetric friction.** Promoting an attachment to a broader scope requires a recorded
   reason the owner sees; narrowing is free. Same shape as `requirements:79` — gaming the
   accounting should require lying in a log the owner reads.
2. **A review surface (GUI).** The owner reviews level choices and promotes information where
   they see fit. The GUI is not built here, but the framework is, because retrofitting a scope
   column means back-filling a level for every attachment ever made — a judgment nobody will
   be positioned to make retroactively. Same argument the charter already accepted for §4.2
   (pluggable surface) and §5 (citation invariant).

The too-low direction already has its instrument: **`decisions:14`, execution sufficiency —
zero sub-tasks blocked by missing plan information — *is* the allocation miss rate.** The
design ships with its own metric already specified.

### 2.6 Sub-task boundaries: lowest-coupling, not smallest

The owner's instinct was to minimise sub-task size — smallest self-contained sub-tasks need the
least information, moving power to the planner and risk away from the executor. The direction
is right; the target is not size.

**Below a certain size, smaller sub-tasks cost more context, not less:**

- Every sub-task pays fixed overhead — `decisions:16` gives each sub-task its linked rows *plus
  the governing big-picture rows*. Halving sub-task size doubles how often that is paid.
- **Self-contained fights small.** Cut finer and a unit's meaning starts depending on its
  neighbours, so keeping it self-contained means re-importing them. Total context is
  (per-sub-task × count); its minimum sits at the natural coupling seams, not at the floor.
- More sub-tasks means more allocation decisions, multiplying the §2.5 level-placement judgment.

**The plan already settled granularity: `decisions:63` — one SubTask = one contract
implementation unit; edges map from `contract_deps`; `split_subtask` (`contracts:40`) divides
along the contract's param/error surface.** That was the fix to `findings:11`. Contracts are
the seam *because* `contract_deps` already encodes the coupling. `split_subtask` is the
escape hatch for a contract that is genuinely too big.

Supporting evidence from this build, not theory: M1–M4 each bundled 2–3 components, and nearly
every defect caught was an **interaction** bug — F11's intra-batch links, F14's `impact()`
excluding its roots, M3's plan-wide warning scoping. Those are exactly the defects a too-small
sub-task hides: each unit passes alone and the bug lives in the seam. Cutting below the coupling
boundary relocates the risk somewhere nobody is looking.

**Design rule: maximise crispness of the boundary, not minimise size.** A small sub-task with a
vague interface is worse than a large one with a sharp contract. "Power to the planner" means
the planner spends effort on the cut *lines*, not on cutting more often.

### 2.7 Session-boundary advisory (the "/clear prompt")

The owner wants the tool to prompt for a fresh session between sub-tasks, since humans
forget.

**Constraint:** `decisions:4` / `requirements:74` require the surface to be strictly
MCP-protocol-clean, with no Claude Code-specific calls or configuration. `/clear` is a Claude
Code command; the tool must not invoke it and should not name it.

**Design:** on sub-task completion the surface returns a session-boundary advisory in its
`ToolResult` content — "sub-task complete; recommend a fresh session before the next" — which is
protocol-clean and works on any engine. Engine-specific phrasing stays outside the engine.
This pairs naturally with `set_next_action` (`contracts:49`): the advisory is only safe to
give when a resume point has been durably checkpointed, so the advisory should be *conditional
on* a next-action being set, and should say so when it is not.

---

## 3. Build-package recut

Task-graph coming into scope makes the old M5 (surface) dependency-wrong: `plan_status`'s
digest depends on the scope-attachment bounds (§2.3) and its drift flags depend on a
finalization baseline. Surface should follow the execution module, not precede it.

Approved by the owner 2026-07-20, including the 5a/5b split. `V2_BUILD_PLAN.md` §3/§7/§9/§10
have been updated to match — the two documents now tell the same story.

| M | Was | Now |
|---|---|---|
| 5a | Surface | **Execution module I**: scope-attachment framework, `finalize_plan`, `task-graph` |
| 5b | — | **Execution module II**: `brief-composer` + plan-time allocation |
| 6 | revision-service | **Surface**: `session-service`, `mcp-surface` on the §4.2 seam, + methodology rev 3 |
| 7 | Dogfood | `revision-service`, reduced form (§4.1) |
| 8 | — | Dogfood: plan the GUI using v2 |

Dependency order within M5: scope-attachment schema → `finalize_plan` → `task-graph` →
`brief-composer` + allocation. The schema piece is first because nothing may write an
attachment before the scope column exists. **Start 5a with the `state_machines:9` audit (§5),
not with code.**

---

## 4. Open questions — each bound to a resolve-by gate

Per the outstanding-problem rule (§0): an open question is a problem; it is fixed now or
bound to a named gate it must be resolved by, and that gate cannot pass while it is open.
Both below are `plan_status`-shaped, so their gate is **M6** (surface). Neither blocks M5.

1. **[resolve-by: M6 gate] Mandate and package script: by value or by reference in the resume
   digest?** `requirements:10` says return them on session open; they are the biggest single
   chunk, bounded by methodology size rather than plan size. Serving by reference contradicts
   `requirements:10`'s plain reading; by value makes the digest permanently fat. A
   first-call-by-value/thereafter-by-reference scheme works but makes `plan_status` stateful
   within a session — the same call returning different things is a debugging hazard.

2. **[resolve-by: M6 gate] Does the digest name what to fetch?** If it serves counts and ids,
   a resuming model may simply not fetch and proceed confidently on the digest alone —
   silent, same class as F14. Countermeasure is the digest naming its own next action, which
   is `requirements:58` doing real work.

3. ~~Scope-level vocabulary.~~ **Settled 2026-07-20**: three levels, `session` dropped. See
   §2.3.

## 4a. Settled — the §0 hard-lock IS a product requirement (build at M6)

**Decided by owner 2026-07-20: yes.** The §0 rule is not only build-process discipline; it
is a v2 product requirement, logged as **DEVIATIONS.md D9** and built in M6 (gate-engine).
M6 cannot pass with D9 unbuilt (it is D9's own resolve-by gate).

It contradicts the gate-engine as designed — v2's gates **warn, they don't block**
(`decisions:31` keep-pushing; D7), and the only hard block today is `requirements:32`
(unresolved findings block `finalize_plan`, at finalization alone). D9 generalises that to
every gate.

The load-bearing design work is left to M6 and must not be pre-empted here: **the lock class
must be narrow.** Advisory warnings (open gaps, coverage) stay warn-don't-block, or D9
resurrects the cry-wolf failure D7 fixed; the hard-lock binds outstanding *findings* and — to
be settled in M6 — possibly conflicts and open assumptions. Full statement and the open
sub-questions are in D9.

---

## 5. Pre-build audit — DONE 2026-07-21, results below (do not redo)

**The `state_machines:9` audit is complete.** Results, superseding the "not yet audited"
text that follows:

- **F15 was a false alarm.** All four cited-but-undefined contracts have live successors:
  `contracts:52`→`63`, `contracts:56`→`68`, `contracts:59`→`62`, `contracts:61` subsumed
  into `contracts:64`. `contracts:60` was never missing. The `in_progress → done` path is
  fully specified. The generalised real defect is **F17** (prose citations dangle on
  supersession), bound to M6.
- **Check 1 found two genuine holes → F18.** `deps_satisfied` and `serve_brief` appear
  nowhere in the plan outside the state-machine table. `report_status` must *not* be made
  to fire them (`crud_grid:35` splits system-readiness from engine-report; collapsing them
  lets the engine assert its own readiness).
- **Check 2 found two more → F19.** `rework_flagged` is a trap under edge-triggered
  readiness, and `verify_completion` has no state precondition, so a passing verdict can be
  banked before the work is served — re-opening `findings:9` through a side door.

**Build order consequence:** F18 and F19 are fixed *as part of* building `task-graph`, and
they share a root decision — **readiness is a level-triggered predicate, not an edge
event**. Settle that first; it resolves F19(a) structurally and shapes F18's readiness
contract. It is a deviation (the plan makes no such decision) and needs a DEVIATIONS entry.

### Original §5 text (kept for the record)

Per `v2-build-conventions`, two mechanical checks before building anything with a state
machine.

- **`state_machines:9` (SubTask)** — states pending, ready, in_progress, blocked, done,
  rework_flagged; events deps_satisfied, serve_brief, complete, block, unblock, flag_rework.
  This lands in M5 and **has not yet been audited**. Do this first.
  - Check 1: every event needs a named contract that fires it.
  - Check 2: every outcome a contract's signature offers must be reachable from the states
    the entity can actually be in (F13's class).
  - Known relevant: `contracts:59` (verify delivery) and `contracts:60` (refuse `done`
    without verification) are cited as the fix for `findings:9` — **neither appears to have a
    definition row in the frozen plan** (same absence as `contracts:61`, §1.2). Confirm and
    log; the `in_progress → done` transition's only stated enabler may be missing.
- **`state_machines:1` (Plan)** — audited this session, see §1.2.

### Contract rows cited as package-7 fixes but never defined

`contracts:52`, `contracts:56`, `contracts:59`, `contracts:61`. Verified absent by grepping
for the definition form `` `contracts:N` `` — each appears only inside a findings fix-note.
(Contracts 3, 4, 16, 36, 39, 47 are also absent, but those are the *superseded originals*,
correctly dropped from a live-rows export.) This is a new instance of the characteristic
pattern F2/F4/F7/F9/F12 — behaviour named in prose without the mechanism — and the first where
the missing thing is the *fix for a package-7 finding*. **Log as a defect before building.**

---

## 6. Logged (done 2026-07-20)

All of this session's findings are recorded; nothing is parked in this doc awaiting a write.

- **DEFECTS.md F15** (OPEN) — package-7 fix rows cited but never defined
  (`contracts:52/56/59/61`). Resolution is build-time: the `state_machines:9` audit at the
  top of M5a confirms each absence against the built engine and, per row, writes it (as F12
  did for the spike events) or finds it subsumed. **This is the one live to-do.**
- **DEFECTS.md F16** (resolved) — "current working set" (`requirements:62`) and "accumulated
  learnings" (`requirements:58`) undefined; resolved by the §2 allocation design.
- **DEVIATIONS.md D1** — amended: the execution-module deferral was reversed; only the
  `revision-service` reduction remains a deviation.
- **DEVIATIONS.md D8** — scope-attachment framework + plan-time allocation.
- **`V2_BUILD_PLAN.md`** — §3 (15 components, module in scope), §7 (5a/5b/6/7/8), §9 (module
  closed, GUI reframed), §10 (allocation model). Charter, this doc, and build memory agree.

---

## 7. How to run things

Tests: `.venv\Scripts\python.exe -m pytest -q` from repo root (205 passing at M4).

Driver scripts: scratchpad `.py` files, run with
`$env:PYTHONIOENCODING='utf-8'; $env:PYTHONPATH='D:\PythonProjects\PlanTool'; & .venv\Scripts\python.exe <path>`.
Inline `python -c` gets classifier-blocked and the cp1252 console chokes on em dashes.

**Drive the engine end-to-end after each build package and read the output.** It has caught
something the test suite could not across all four build packages so far. A test written from a
specification inherits that specification's blind spots.

Branch + PR; the owner merges; no self-merges.
