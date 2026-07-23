# Methodology defects

The v2 build's success metric is **execution sufficiency**: every time the build hits
missing or ambiguous information in the frozen plan and must ask the owner or invent
something, that is a defect and is logged here.

A low count validates the planning method. A high count is the finding, and is equally
valuable. Do not paper over defects to keep the count down.

Format: what was insufficient · what was needed · how it was resolved.

---

## F1 — Architecture frozen with no extension seam

**Row:** `decisions:50` (architecture shape), and the "consumed by: components:15" line
on nearly every contract.

**Insufficient:** the plan specifies a modular monolith whose only consumer is
`mcp-surface`. It contains no story for a second consumer, and no seam at which one could
be added. A GUI was a known future intention at planning time and is not addressed
anywhere in the frozen plan.

**Needed:** a service layer boundary distinct from the surface adapter.

**Resolved:** invented — see DEVIATIONS.md D2. Owner concurred 2026-07-20 ("we should have
better planned for this").

**Class:** the planning method did not prompt for extension points or future consumers.
Worth a gap-engine or guidance rule in v2: *what will consume this, other than the thing
you are building now?*

---

## F2 — Scientific claim justification has nowhere to live

**Rows:** `contracts:31` (`file_claim`), `contracts:32` (`record_claim_outcome`),
`dep_failure_modes:20` (partial literature coverage).

**Insufficient:** `file_claim(kind='scientific')` routes to "research + owner/domain-expert
adjudication", and `record_claim_outcome` accepts the result as `evidence: str`. The plan
therefore mandates research without specifying any structure to hold it. Related:
`dep_failure_modes:20` requires that "partial literature coverage is recorded with explicit
coverage limits", which is not measurable when sources are prose in a free string.

**Needed:** a first-class representation for sources and their extracts.

**Resolved:** invented — see DEVIATIONS.md D3. Owner requirement 2026-07-20.

**Class:** the plan specified a *routing* decision without following through to the data
it produces. Worth a validation rule in v2: *a contract that routes work somewhere must
name where the result is stored.*

---

## F3 — Named parameter types have no specified shape

**Rows:** `contracts:2` (`WriteBatch`), `contracts:10` (`RowSelector`, `RowPage`),
`contracts:14` (`TraversalSpec`, `Closure`), `contracts:58` (`GraphScope`).

**Insufficient:** the contracts name these types and, for `RowSelector`, list its
dimensions in prose — "by ids | table | package | provenance | liveness |
link-neighborhood; paginated" — but no row anywhere defines their fields, so two
implementers would produce two incompatible interfaces.

**Needed:** field-level definitions, or an explicit statement that shapes are the
implementer's choice.

**Resolved:** invented in `engine/models.py` and `engine/storage.py`, following the
prose closely where it exists.

**Class:** the domain model (Package 4) covers *entities* thoroughly but not the
*parameter and return types* that appear in contract signatures. Those types are the
actual interface. Worth a gate rule in v2: *every type named in a contract signature
must be defined somewhere.*

---

## F4 — Contradiction is mandated but never defined

**Row:** `contracts:9` (`submit_rows`), error `ConflictRequired`; `requirements:27`.

**Insufficient:** "a submitted row contradicts a stored row; nothing is filed until a
conflict is raised" — but nothing in the plan says how contradiction is *determined*.
It cannot be a string comparison, and the tool holds no LLM (`decisions:12`), so it
cannot be a judgment the engine makes.

**Needed:** either a detection rule, or an explicit statement that the calling session
supplies the judgment and the tool only enforces the consequence.

**Resolved:** invented — `RowService` takes a pluggable `ContradictionDetector` that
defaults to detecting nothing, so `ConflictRequired` is unreachable until
conflict-service supplies a real detector in M3. The likely correct answer is the
second option (the session judges, the tool enforces), which is consistent with
`decisions:12`, but the plan does not say so.

**Class:** same shape as F2 — an error condition specified without the mechanism that
raises it. This is the second instance, which makes it a pattern worth a gate rule:
*every error a contract can raise must have a stated trigger.*

---

## F5 — No way for a row to link to a sibling in the same batch

**Rows:** `contracts:9` (`submit_rows`), `crud_grid:57`, `entities:15`.

**Insufficient:** links are "created by the LLM agent as part of row submission" and
submission is batched, but refs are only assigned at write time. A batch containing a
use case and the requirement that links to it therefore cannot be expressed: the
requirement has no ref to point at. The plan never addresses this, despite batched
submission with links being the primary interview path.

**Needed:** a within-batch reference form.

**Resolved:** invented — `LinkSpec.target` accepts an int index into the batch being
submitted, resolved to a ref after assignment. A row whose sibling target was rejected
is itself rejected rather than filed with the link silently dropped.

**Discovered by:** driving the engine end-to-end, not by the test suite — the tests had
encoded the same blind spot as the plan, submitting rows in dependency order across
separate batches. Worth remembering as a methodology point in its own right: a test
written from a specification inherits the specification's gaps.

---

## F6 — `gap_id: int` cannot exist

**Rows:** `contracts:66` (`dismiss_gap(gap_id: int, ...)`), `contracts:67`
(`reopen_gap(gap_id: int, ...)`), against `crud_grid:9` and `requirements:78`.

**Insufficient:** these two contracts take an integer gap id, but `crud_grid:9` makes
gaps *computed* from plan state rather than stored, and `requirements:78` requires their
overlay to be keyed by "gap-type plus the lineage root of the target row". An integer id
is incompatible with both: there is no stored row to autoincrement from, and any id
assigned at derivation time would change on the next derivation — exactly the
re-surfacing and silent-detaching that requirements:78 exists to prevent.

**Needed:** the parameter type should be the stable composite identity requirements:78
already specifies.

**Resolved:** invented — gaps carry a string key of `rule_id|lineage_root|discriminator`,
and `dismiss_gap`/`reopen_gap` take that. The signature deviates from the contract; the
behaviour matches requirements:78, which is the stronger row.

**Class:** a signature written before the identity design landed, and never revisited
when requirements:78 was added to fix findings:16. Worth a gate rule: *when a
requirement changes an entity's identity, every contract signature naming that entity is
a hole until re-checked.*

---

## F7 — Nothing defines the current package

**Rows:** `contracts:19` (`next_gaps`), `requirements:12`, `entities:1`.

**Insufficient:** `next_gaps` returns gaps for "the current package" and requirements:12
recommends the gate "while the current package has no open gaps", but nothing in the plan
says how the current package is determined. `entities:1` carries package on the Plan and
`crud_grid:3` says "System: package advances" without stating the advance condition —
whether it is gate-pass, owner instruction, or derived from content.

**Needed:** a stated rule for what the current package is and when it advances.

**Resolved:** invented — the lowest package with any open gap, else the highest package. This
is a guess. It happens to make submits-for-any-package work naturally (v1's stated
behaviour: "submits for any package are always accepted; next_gap prefers package order but
follows the conversation"), but the plan does not say so.

**Class:** same family as F2 and F4 — behaviour named in prose without the mechanism that
produces it. Third instance, which strengthens the case for the gate rule proposed in F4.

---

## F8 — Gate criteria exist only as v1 code

**Rows:** `contracts:22` (`run_gate`), `requirements:20`, `requirements:71`.

**Insufficient:** `run_gate` returns "row-level holes (each naming table, row, problem,
and fix)" and `requirements:20` says gates evaluate "only mechanical criteria" — but no
row anywhere in the frozen plan states what any package's criteria *are*. The plan
specifies the shape of the answer and never the question. `requirements:71` does require
the criteria to ship as a versioned content asset, which at least says where they live.

**Needed:** the per-package criteria themselves, as content.

**Resolved:** vendored, not invented — `engine/methodology/rev2/gate_criteria.yaml`
transcribes v1's `archive/v1/engine/gates.py` into declarative rules, per `decisions:61`
and `findings:4`. v1 wrote one hand-coded SQL function per package; the v2 asset expresses
the same criteria as nine declarative types the gate-engine interprets.

**Class:** distinct from F2/F4/F7 — this is not a missing mechanism but missing
*content*, and the plan knew it (requirements:71 exists precisely because the
methodology is the product's IP). Worth noting that the vendoring instruction is what
made this recoverable: without decisions:61 an executor would have invented eight packages
of gate criteria at build time, which findings:4 identifies as the failure mode the tool
exists to prevent.

---

## F9 — Nothing raises a warning

**Rows:** `contracts:23`/`24`/`25` (`active_warnings`, `suppress_warning`,
`resolve_warning`), `requirements:21`, `decisions:31`, `state_machines:6`.

**Insufficient:** the Warning entity has a full lifecycle — a state machine, a
suppression path, a resurfacing rule, three contracts operating on `warning_id: int` —
and no contract that *creates* one. `requirements:21` says the gate "shall list each as
an explicit warning", which describes a report, not a write. Nothing states whether
warnings are stored rows or derived views, yet the int id demands the former (the same
tension F6 found in gaps, resolved the opposite way).

**Needed:** a raise contract, and a statement of whether warnings are stored or derived.

**Resolved:** invented — `WarningService.raise_warning`, idempotent on a stable
`warning_key`, backed by a `warnings` table. gate-engine calls it. A second invented
method, `settle_warning`, retires a warning whose condition cleared; `resolve_warning`
could not serve because contracts:25 types its cause as a RowRef and a gap that stopped
being derived has no such row.

**Class:** F2, F4, F7 and now F9 — behaviour named in prose without the mechanism that
produces it. **Fourth instance.** At four this is no longer a series of oversights but a
characteristic failure of the planning method: the method interrogates entities and
their lifecycles thoroughly, and does not interrogate *who performs each transition*.
The countermeasure proposed at F4 (every named error needs a stated trigger) should be
widened: **every state-machine event needs a named contract that fires it.** A state
machine whose events no contract raises is an unimplementable entity, and it is
mechanically checkable — which makes it a gate criterion, not just advice.

---

## F10 — "List each open gap as a warning" does not say which gaps

**Rows:** `requirements:21`, `contracts:22`, `decisions:31`.

**Insufficient:** "WHEN a gate passes while open gaps or unresolved assumptions exist,
the system shall list each as an explicit warning." Read literally, *each* means every
open gap in the plan. Built that way, the package-1 gate of a four-row plan reported
twelve warnings, ten of which said things like "No components yet" — true, and useless,
because the plan was five packages away from needing components.

**Needed:** the scope of "each" — plan-wide, or the package being gated.

**Resolved:** invented — raising is scoped to the gated package plus the package-agnostic
rules (assumptions, reference coverage). Warnings raised at their own package persist in
the ledger and keep re-presenting, so nothing is passed over silently.

**Discovered by:** driving the engine end-to-end. The test suite passed with the noisy
behaviour, because the tests asserted that warnings *appeared* — which is what the
requirement says — and no test could notice that the warnings were not worth reading.
Second occurrence of the F5 lesson.

**Class:** an unquantified "each". The same drive found the consequence compounding: an
open assumption was raised twice (once as a gap, once as an assumption), so the owner's
suppression silenced only one of the twins and the other kept nagging. A requirement
that does not bound a set produces duplicates as readily as noise.

---

## F11 — The vendored gap rules and gate criteria disagree about package 1

**Rows:** `requirements:71`, `decisions:61`; assets `gap_rules.yaml` (M2) and
`gate_criteria.yaml` (M3).

**Insufficient:** not the frozen plan this time — the *vendored methodology*. v1 recorded
goals, non-goals and target stack as `decisions` rows distinguished by a text prefix
("Goal:", "Non-goal:", "Stack:"), a convention its gate SQL matched with `LIKE 'goal:%'`.
v2's generic PlanRow store makes separate tables the natural encoding, and M2's
`gap_rules.yaml` had already half-adopted it (`goal_without_success_criteria` reads a
`goals` table) while `package1_not_started` still tested `decisions` for emptiness. The two
assets therefore disagreed about what package 1 even fills.

**Consequence:** a complete, passing package 1 was permanently accompanied by the warning
"Nothing recorded yet. Open the package-1 interview."

**Resolved:** `package1_not_started` now tests `goals`. Recorded here rather than silently
fixed because it is evidence about the *revision* path requirements:71 mandates: a
methodology revision that changes how content is encoded has to be applied to every
asset at once, and nothing checks that. M5 introduces rev 3 and will hit this again.

**Discovered by:** the end-to-end drive, third time. The unit tests could not catch it —
`tests/test_gaps.py` was written against `decisions` at M2 and so encoded the same
disagreement, and it passed.

**Class:** a cross-asset consistency hole. Worth a gate criterion in a future revision:
*every table named in one methodology asset is named in the others that cover the same
package.*

---

## F12 — Two spike events and one claim mechanism have no contract that fires them

**Rows:** `state_machines:5` (with `sm_cells:62`, `:65`, `:72`), `requirements:4`,
`requirements:41`.

**Insufficient:** the fifth instance of the F9 pattern, and the first one caught *before*
building rather than after — the pre-build state-machine audit the F9 countermeasure
mandates is what found it.

The Spike state machine has four events: start, block, unblock, conclude.
validation-service has exactly two contracts that touch a spike, `register_spike`
(contracts:29) and `record_spike_result` (contracts:30). `register_spike` creates the
spike in `registered`; `record_spike_result` fires `conclude` or `block`. **Nothing fires
`start`, and nothing fires `unblock`.** But `sm_cells:65` makes `registered --conclude->`
impossible — "no result without execution". So every spike the system can create is
trapped one transition away from every outcome except `blocked`: confirmed, refuted and
inconclusive are all unreachable, which is to say the entire mechanism
`requirements:25` describes could never run.

`sm_cells:72` (`blocked --unblock-> executing`) is the same hole on the recovery path: a
spike parked because its dependency was unreachable could never be resumed once the
dependency came back, only concluded from `blocked`.

Two smaller versions of the same thing sit in the claim mechanism. `requirements:41`
routes a `both`-kind claim down two tracks and says neither alone closes it, but names no
contract that records a track completing — so "both satisfied" is unrepresentable.
`requirements:4` says research red flags block dependent planning "until resolved or
fenced" and names no contract that fences one.

**Resolved:** added four contracts not in the frozen plan — `start_spike`,
`unblock_spike`, `satisfy_track`, `fence_claim` — each carrying a docstring pointing
here. The alternative for the spike was to have `record_spike_result` silently
auto-advance a `registered` spike through `start`, and that was rejected deliberately:
`sm_cells:65` is an integrity rule, not an oversight. "No result without execution" is
the thing that stops a spike being concluded by someone who never ran it, and
auto-starting would erase exactly that guarantee to save one call.

**Class:** F9's, unchanged and now five for five (F2, F4, F7, F9, F12) — behaviour named
in prose without the mechanism that produces it. What is new is the *detection*: the F9
countermeasure ("every state-machine event needs a named contract that fires it") was run
as a pre-build checklist and paid for itself immediately, catching in ten minutes what
had previously taken a full build-and-drive cycle to surface. Every remaining milestone
should keep running it. Note also its limit: it catches missing *events*, and the claim
half of this defect (a missing mechanism with no state machine attached) still needed
reading the requirement prose to spot.

---

## F13 — The `withdrawn` finding outcome is unreachable

**Rows:** `contracts:34`, `state_machines:7` (with `sm_cells:92`, `:97`).

**Insufficient:** found by the same pre-build audit as F12, in the same pass.
`contracts:34` offers three outcomes: `addressed`, `accepted_risk`, `withdrawn`.
`sm_cells:92` makes `filed --withdraw->` impossible — "no dispute open" — so `withdraw`
is legal only from `disputed`. And the Finding state machine's `dispute` and `uphold`
events have no contract that fires them, `file_finding` and `resolve_finding` being the
component's entire surface. A finding therefore can never be disputed, so it can never be
withdrawn, so one of the three outcomes the contract advertises can never be used.

**Resolved:** added `dispute_finding` and `uphold_finding`. The transition table is
implemented exactly as `sm_cells:90-109` specifies, including the two cells that look
like typos and are not: `disputed --withdraw-> addressed` (a withdrawn finding rests in
`addressed`, with `withdrawn` recorded as the outcome — so the state says "no longer
open" and the outcome says why), and `accepted_risk --dispute-> disputed`, which is what
keeps `requirements:33`'s "visible at handoff" from quietly meaning "settled".

**Class:** F9's again, with a sharper consequence than the others. F9 and F12 produce
entities that cannot move; this one produces a *contract that lies* — the signature
documents an outcome the state machine forbids. Worth adding to the pre-build checklist
as its own question, because it is mechanically checkable and distinct from the event
audit: **every outcome a contract's signature offers must be reachable from the states
the entity can actually be in.**

---

## F14 — Two bugs the tests could not see: whose dependents, and whose rejection

**Rows:** `requirements:43`, `requirements:25`, `contracts:11`.

**Insufficient:** not the plan this time, but the build — both found by the mandatory
end-to-end drive, and neither visible to the 203 tests that passed before it.

`requirements:43` says a failed validation raises conflicts on "every row that depends on
the failed claim", and the same sentence covers a refuted spike. It reads like one rule
and is two, because the two cases root at opposite ends of the link. A spike roots at the
*assumption*, which the spike resolves — so only the rows resting on it are contested. A
claim roots at the rows resting on the claim — so those rows are themselves what
`requirements:43` means. `LinkGraph.impact()` excludes its roots, so sharing one code
path silently contested a failed claim's grandchildren while leaving its children
untouched: the rows most obviously invalidated were the exact ones missed.

Second, `contracts:11` hardcodes the retirement reason "assumption rejected by the
owner". When validation-service closes a refuted world-assumption per
`requirements:25`, no owner is involved — the evidence closed it. The audit trail
recorded a decision nobody made. `resolve_assumption` now takes an optional
`retire_reason`.

**Resolved:** `_raise_dependent_conflicts` takes an explicit `include_roots`, set per
caller with the reasoning in its docstring; regression tests cover both directions,
including the mirror case (a refuted spike must *not* contest its own assumption).

**Discovered by:** the end-to-end drive, fourth milestone running, fourth time it has
caught something the suite could not. The mechanism is worth stating plainly now: the
first bug is invisible to a test written from `requirements:43` because the requirement's
own sentence conflates the two cases, and a test inherits that conflation — the same
blind-spot inheritance recorded at F5 and F11. The drive catches it because reading
"conflicts raised=(4,)" against a plan with two obviously-affected rows is a
*quantitative* check the spec cannot bias.

---

## F15 — Package-7 fixes cited as contract rows that were never written

**Status: RESOLVED at the M5a `state_machines:9` audit, 2026-07-21 — and the diagnosis
below was WRONG.** See **Resolved** at the end of this entry before reading the rest. The
original text is kept unedited because the error is the interesting part: a mechanical
check was run correctly and its *interpretation* was wrong, which no amount of re-running
the check would have caught. The hard lock on M5a is lifted.

First defect in this log recorded before its fix rather than after. The distinction is
deliberate: logging a defect is cheap and must never wait (the never-batch discipline of
`requirements:56/57/60`), but the *resolution* of these is a build-time decision — what
`contracts:59/60` must guard cannot be settled until the `state_machines:9` machine is
being built in M5a. Resolving now would be inventing in a vacuum. This entry gets its
**Resolved:** line at the M5a gate, which cannot be passed until it does.

**Rows:** `contracts:52`, `contracts:56`, `contracts:59`, `contracts:61` — and, in the
same class, the missing definition of `contracts:61` as the mechanism for `findings:10`
(workspace drift) and `contracts:59/60` for `findings:9` (delivery verification).

**Insufficient:** four contract ids are cited as the fixes for package-7 findings but have
no definition row anywhere in the frozen plan. Verified by grepping for the definition
form `` `contracts:N` · ``: `52`, `56`, `59`, `61` each appear *only* inside a findings
fix-note, never as a defined contract. (Contracts 3, 4, 16, 36, 39, 47 are also absent
but those are the *superseded originals*, correctly dropped from a live-rows export — a
different thing.)

Concretely, each missing row is load-bearing:

- `contracts:59`/`contracts:60` are cited (F9's fix, `findings:9`) as the owner of
  delivery verification and the sole enabler of the `in_progress → done` transition of
  `state_machines:9`. If truly absent, the SubTask machine has no legal path to `done` —
  the exact class as F12 (an event no contract fires), now on the entity M5 must build.
- `contracts:61` is cited (`findings:10`'s fix) as the mechanism computing workspace-drift
  flags from the `requirements:73` fingerprint. Without it `plan_status`'s drift flags
  have a requirement and a fix-note but no computation.
- `contracts:56` is cited (`findings:3`/`findings:18`) as the redesigned `compose_brief`
  carrying the candidate-accounting rule.
- `contracts:52` is cited (`findings:8`) in the lock-hardening set.

**Class:** F9's, the running pattern (F2, F4, F7, F9, F12) — behaviour named in prose
without the mechanism that produces it — now six for six. What is *new* and worth marking:
in every prior instance the missing mechanism was named by a requirement or a state
machine. Here the missing mechanism is named by a **package-7 finding's own fix note** — the
plan's adversarial pass asserted a fix ("Resolved: contracts:61 computes drift flags…")
whose contract was never actually written. The fix note is prose that reads as
resolution, which is a more camouflaged version of the pattern than any before it: the
row that was supposed to *close* a finding is itself an F9 instance. The `state_machines:9`
audit at the top of M5a must confirm each of these absences against the built engine and
decide, per row, whether it is genuinely missing (→ write it, as F12 did for the spike
events) or subsumed by an existing contract.

**Resolved (2026-07-21, M5a audit): every one of the four mechanisms exists. Nothing is
missing.** The per-row check the entry above demanded was run, and each cited id has a
live successor carrying the same behaviour and linking the same finding:

| Cited in fix-note | Live row | Evidence |
|---|---|---|
| `contracts:52` (lock hardening, `findings:8`) | **`contracts:63`** `acquire_writer_lock` | links `findings:8`, `decisions:58`; already built in M1 |
| `contracts:56` (redesigned `compose_brief`, `findings:3`/`findings:18`) | **`contracts:68`** `compose_brief` | links `findings:3` *and* `requirements:79` — the accounting rule F18's fix demanded |
| `contracts:59` (delivery verification, `findings:9`) | **`contracts:62`** `verify_completion` | links `findings:9`; "a pass is the sole enabler of the in_progress->done transition" |
| `contracts:61` (drift computation, `findings:10`) | **subsumed into `contracts:64`** `plan_status` | links `findings:10`, `requirements:73`; drift computation is stated inline in its signature |

`contracts:60` (`report_status`) was never missing at all — it is defined, live, and
already carries the `VerificationMissing` error the entry above worried was absent. The
`in_progress → done` path is fully specified: `contracts:62` verifies, `contracts:60`
refuses `done` without that verdict.

**So the real defect is a different and much narrower one:** the frozen plan is a
**live-rows export**, so superseded rows are dropped from it — but the *prose* of a
finding's fix-note is frozen at the moment it was written and keeps naming the row id as
it stood then. When that row is later superseded, the citation dangles. Four fix-notes
point at ids the export no longer contains. Nothing is unbuildable; four citations do not
resolve. Generalised and logged as **F17**, because the mechanism that produced it is a
v2 product defect, not a v1 wart.

**What the wrong diagnosis cost, and why it was wrong.** The grep was correct: those four
ids genuinely have no definition row. The inference — "not defined ⇒ never written ⇒
mechanism missing" — was not, and F15 even states the counter-case in its own text
("contracts 3, 4, 16, 36, 39, 47 are also absent but those are the *superseded
originals*… a different thing"). Having identified the exact alternative explanation, the
entry did not test the four rows against it. The test is cheap: look for a live contract
with the same behaviour linking the same finding. All four pass it in about five minutes.

This inverts the entry's own "six for six" claim. F15 is **not** an instance of the
F2/F4/F7/F9/F12 pattern; the running count of that pattern stands at five, not six, and
the claim that the adversarial pass asserted fixes it never wrote is withdrawn — package 7
wrote every one of them. **The pattern was over-fitted:** five prior confirmations made
the sixth reading feel like recognition rather than a hypothesis needing a test. Worth
carrying: a defect log that names a recurring class starts to *recruit* ambiguous
evidence into that class, and the pre-build audit's mechanical checks cannot detect that
failure because the check is not what went wrong.

---

## F16 — Resume cost is bounded by undefined terms

**Rows:** `requirements:62`, `requirements:58`.

**Insufficient:** both load-bearing terms in the cold-resume design name a quantity the
plan never defines.

`requirements:62` requires resume to serve "a compact digest plus targeted row reads, so
resume cost scales with the current working set rather than total plan size" — but no row
defines what the **current working set** is. Left undefined, "working set" is whatever the
implementer's heuristic decides, which is the tool exercising judgment about relevance —
the thing the design spine forbids.

`requirements:58` requires resume to present "accumulated learnings" and no row bounds the
**accumulation**. Unbounded, resume cost scales with total session history — strictly
worse than the plan-size scaling `requirements:62` exists to kill. Every arbitrary bound
(last N, since-last-gate) is invention.

**Resolved:** by the context-allocation design settled this session
(`V2_BUILD_PLAN.md` §10, `M5_PLAN.md` §2). The working set stops being a read-time
heuristic and becomes what plan-time allocation attached: a packet's context is the union
of its own attachments and those of its enclosing scopes (project / milestone / packet).
Accumulated learnings inherit the same bound — resume serves
project ∪ current-milestone ∪ current-packet — so the bound is structural rather than a
number someone picked. This is a **deviation** (the scope-attachment framework is not in
the frozen plan at all) as well as a defect resolution; logged in DEVIATIONS.md.

**Class:** not F9's. This is the other recurring shape — a requirement quantifying a cost
against a term the plan leaves undefined, so the requirement is unfalsifiable as written.
The resolution came from design discussion, not from a mechanical audit; worth noting that
the pre-build audit catches missing *events* cleanly but says nothing about undefined
*terms*, which still need reading the prose (the F12 limit, restated).

---

## F17 — Row citations inside prose are unvalidated and break silently on supersession

**Status: RESOLVED at M6 (2026-07-23).** Both halves are built. The *visibility* half (the
door resolving each cited address beside the untouched prose, and the render surfacing it in
a *cites* line) landed with the surface. The *what-to-do* half was the owner's call between
option 1 (resolve) and option 3 (flag), settled here: **resolve.** When prose cites a dead
row, `door.successor_lookup` walks the write-once supersession chain to its live head and the
annotation reads `contracts:59 — <name> (superseded), now contracts:62 — <name>`; when the
chain is closed — the head is itself retired, or the row was struck out with nothing put in
its place — it reads *no live successor* rather than repairing to a row that is not there.
The receipt the planner reads counts a closed chain as dead and a repaired one as live,
because a repaired citation now leads somewhere the reader can go. **The frozen prose is
never touched** — successor address and name travel in their own keys of the resolution, so a
brief's code-engine reader gets a machine-readable pointer, not a rewritten sentence. Chosen
over option 3 because the consumer of a brief cannot go and look: telling it a row was
superseded and stopping there strands it exactly where F15's wrong diagnosis stranded a
person. Following `superseded_by` is not the tool exercising judgment — it is resolving a
structural pointer, the same mechanical act as resolving a name.

**Original status: OPEN. Resolve-by gate: M6 (surface).** Chosen because the fix is a
read-time concern — how a row's text is served, and how an unresolvable prose ref is surfaced
— and M6 is where `plan_status` and the MCP surface are built. It did not block M5.

**Rows:** `findings:3`, `findings:8`, `findings:9`, `findings:10` (the four carrying
dangling citations); mechanism rows `requirements:61`, `decisions:42` (write-once
supersession), `contracts:14`/`contracts:15`/`contracts:58` (link-graph, which validates
the *other* kind of reference).

**Insufficient:** the plan enforces referential integrity on **structured links** — edges
are validated at write time and reads carry `DanglingRef` — but a row's free text is never
scanned. Row ids embedded in prose (`` `contracts:59` `` inside a fix-note, the
`(requirements:32)` parentheticals throughout every contract signature) are just
characters. Nothing validates them at write time and nothing re-checks them when the target
is superseded.

Supersession then breaks them silently, and by design: `decisions:42` makes `superseded_by`
write-once and frozen history immutable, so the *correct* behaviour is that old prose keeps
its old ids. A live-rows export drops the superseded target, and the citation now points at
nothing. F15 is the demonstration — four such citations in the frozen plan, and they cost a
wrong diagnosis that hard-locked a milestone.

**Why this matters more than a broken cross-reference.** This is the citation invariant of
the whole product (`V2_BUILD_PLAN.md` §5) leaking. v2's central mechanism is serving stored
row text **verbatim** into scoped briefs (`requirements:36`). A brief that cites
`contracts:59` serves prose naming a row the reader cannot fetch — and the reader's most
natural inference is the one F15 made: *it was never written*. That inference is wrong,
expensive, and points work at inventing a mechanism that already exists. F13 is the
comparison: both are silent, and both look like a specification hole from the reading end.

Note the interaction with the retired-assumption decision (2026-07-20): a retired row also
drops out of live reads while its dependents still link to it. That was accepted as a known
cost on the assumption that structured links carry the lineage. They do — prose does not.
This is a second mechanism producing the same "cited row is not there" symptom from a
different direction.

**What is needed:** a decision among these, to be made at M6 and not pre-empted here.

1. **Resolve at read time.** When serving row text, annotate prose ids through the
   supersession chain (`contracts:59` -> "superseded by `contracts:62`"). Preserves
   immutable stored text; the fix lives in the reader, exactly where the retired-assumption
   decision said such fixes belong. Cost: every text-serving path needs it, and the
   annotation must not corrupt the verbatim guarantee.
2. **Validate at write time.** Scan prose for row-id patterns and refuse unknown targets.
   Catches typos at the source but cannot help here — the ids were valid when written.
   Necessary, not sufficient.
3. **Accept and surface.** Leave text alone; have the reader flag unresolvable prose ids
   rather than repair them. Cheapest, keeps the tool out of rewriting recorded judgment, and
   would have been enough to prevent F15 — the flag says "superseded", not "missing".

(3) is the current lean: smallest change consistent with the design spine, and F15 shows the
flag alone carries the load-bearing information. But (1) and (3) differ on whether a brief
should *repair* a citation or merely *report* it, and briefs are consumed by a code engine
that cannot go and look — which is the argument for (1). Settle at M6.

**Class:** new. Not F9's (nothing is missing) and not F16's (nothing is undefined). This is
the first defect where the plan is *complete and correct* and still misleads its reader — an
artefact of how the plan is exported and read rather than of what it says. It could only
surface once enough rows had been superseded for frozen prose to fall out of step, which is
exactly the condition a long-lived plan is guaranteed to reach.

---

## F18 — Two `state_machines:9` events have no contract that fires them

**Status: OPEN. Resolve-by gate: M5a (this milestone) — fix before `task-graph` ships.**

**Rows:** `state_machines:9`, `sm_cells:130` (pending + deps_satisfied -> ready),
`sm_cells:137` (ready + serve_brief -> in_progress), `sm_cells:152` (blocked + unblock ->
ready), `sm_cells:160` (rework_flagged + deps_satisfied -> ready), `contracts:38`
(`graph_status`), `contracts:55` (`next_subtask`), `contracts:60` (`report_status`),
`contracts:68` (`compose_brief`), `crud_grid:35`.

**Insufficient:** check 1 of the pre-build audit — every state-machine event needs a named
contract that fires it. Two of the six do not have one. The strings `deps_satisfied` and
`serve_brief` appear **nowhere in the frozen plan except the state-machine table itself**
(verified by grep over the whole document).

- **`deps_satisfied`** — drives three transitions, including the only exit from
  `rework_flagged`. `task-graph`'s responsibility prose claims it "maintains build-state
  truth: readiness", but its only readiness contract is `graph_status` (`contracts:38`),
  which *reports* built/in-flight/blocked/stale and is a pure read. No contract transitions
  `pending -> ready`.
- **`serve_brief`** — the sole entry to `in_progress`. `next_subtask` (`contracts:55`)
  returns candidates plus closure and explicitly does *not* compose (composition is a
  separate second call, per `findings:3`'s fix), so it cannot be the firing contract: a
  sub-task may be offered as a candidate and never briefed. `compose_brief` (`contracts:68`)
  returns an immutable Brief and says nothing about sub-task state. Between them, nothing
  declares the sub-task started.

**`report_status` is not the answer, and this is the load-bearing part.** Its signature
accepts `status: SubTaskStatus (state_machines:9 events)` — nominally all six, so an
implementer could route both missing events through it. `crud_grid:35` forbids exactly that:
update responsibility is split, "**System** (graph/readiness) **and** code engine status
reports via tool API". Readiness is the system's judgment; the report is the engine's claim.
Collapsing them lets the code engine assert its own readiness, which voids `sm_cells:131`'s
entire purpose ("dependencies unfinished — unbuildable work is never served"). A gate the
graded party can open is not a gate. Same shape as `findings:9`, where `done` meaning "the
engine said so" was the defect.

**What is needed:** two contracts on `task-graph`, in the F12 pattern (write the missing
firing mechanism, do not repurpose an existing one) — a system-side readiness evaluation
firing `deps_satisfied`, and a serve/checkout step firing `serve_brief` at the moment a
brief is actually handed over. Their design interacts with F19; resolve together.

**Class:** F12's exactly — a state machine with events no contract fires — now the third
entity to have it (spikes at M4, findings at M4, SubTask here). Three for three on entities
audited *before* building. Note what this says about check 1's value: it has never once come
back clean, and it costs ten minutes.

---

## F19 — `rework_flagged` is a trap, and a verification verdict can be banked early

**Status: OPEN. Resolve-by gate: M5a (this milestone).**

**Rows:** `sm_cells:159`/`sm_cells:160`/`sm_cells:163`, `contracts:62` (`verify_completion`),
`contracts:60` (`report_status`), `requirements:52`.

Check 2 of the pre-build audit — every outcome a contract's signature offers must be
reachable from the states the entity can actually be in. Two findings, both traceable to one
underspecified thing: **whether readiness is edge-triggered or level-triggered.** The plan
never says, and each branch breaks something different.

**(a) `rework_flagged` may have no exit.** Its only transitions out are `deps_satisfied ->
ready` (`sm_cells:160`) and `block -> blocked` (`sm_cells:163`), and it is entered from
`done` (`sm_cells:159`) when a revision flags built work for rework (`requirements:52`). A
node that reached `done` had all its dependencies `done` already. If `deps_satisfied` is
**edge-triggered** — fired when a predecessor transitions to `done` — then for a
rework_flagged node that edge has already fired and will never fire again: its predecessors
are all terminal. The node is trapped, and the only escape is `block`, reaching the right
state via `blocked -> unblock -> ready` (`sm_cells:152`) by declaring a block that does not
exist. If readiness is instead a **level-triggered predicate** recomputed on demand, the
transition is immediate and correct. The plan supports either reading; only one works.

**(b) A passing verdict can be recorded before the work is served.** `verify_completion`
(`contracts:62`) declares no state precondition and no wrong-state error — its errors are
`SubTaskNotFound`, `EvidenceIncomplete`, `StorageUnavailable`. It therefore accepts a
sub-task in *any* state, including `pending`. Its verdict is recorded durably and is "the
sole enabler of the in_progress -> done transition". So the sequence `pending ->
verify_completion(pass) -> ... -> ready -> in_progress -> report_status(complete)` satisfies
`contracts:60`'s `VerificationMissing` guard with a verdict recorded before the brief was
ever served. The guard checks that a passing verdict *exists*, never that it postdates the
work — re-opening `findings:9`'s honour-system hole through a side door and defeating the
fix `findings:9` shipped.

**What is needed:**

- Decide readiness is a **level-triggered predicate** over dependency states, recomputed
  whenever the graph is read or a status is reported. This resolves (a) structurally rather
  than by adding a rework-specific edge, and it is what `graph_status` already implies by
  computing readiness on read. Record as a deviation — it is a decision the plan does not
  make.
- Give `verify_completion` a state precondition (`in_progress`, plausibly also
  `rework_flagged`) with its own error, **or** scope the verdict to the serving episode so a
  verdict predating the current `serve_brief` does not satisfy the guard. The second is
  stronger — it also invalidates a stale verdict after rework, which the first does not — and
  rework is precisely when a banked pass is most dangerous.

**Class:** F13's for (b) — a contract signature offering an outcome from states where it is
meaningless — and F14's for (a): silent, invisible to any test written from the
specification, discoverable only by walking the table and asking what actually fires each
edge. Both were invisible to check 1, which passes happily on events that *are* fired; these
are about *when*.

---

## F20 — `contract_deps` does not exist in v2, and the gate that guards it is imprecise

**Status: PARTLY RESOLVED at M5a (engine half, D11). Methodology half OPEN, resolve-by
gate: M6 (methodology rev 3, already scheduled in the milestone recut).**

**Rows:** `decisions:63`, `contracts:35` (`finalize_plan`), `requirements:34`,
`entities:15` (links), `findings:11` (whose fix decisions:63 is), `findings:17` (the
fossilization pre-mortem); vendored `gate_criteria.yaml` criterion `contract_has_consumer`
and `package6_architecture.md`.

**Insufficient:** `decisions:63` is the row that made task-graph derivation deterministic —
it was the fix for `findings:11` ("two implementers would derive incompatible graphs"). It
says: "dependency edges map directly from **contract_deps** (the sub-task implementing a
consumer depends on the sub-task implementing its provider contract)".

**There is no `contract_deps` in v2.** In v1 it was a first-class table with explicit
`provider_contract_id` and `consumer_component_id` columns and its own `submit_contract_deps`
tool (`archive/v1/engine/db.py`, `gaps.py`, `lineage.py`). The v2 redesign flattened every
relation into the generic `links` table (`entities:15`) — which carries an `edge_type`
column but no convention for using it, and every link written by the build so far uses the
default `'links'`. The provider/consumer *role* that v1 stored explicitly is simply not
recoverable: a contract's links point at its requirements, its decisions, its findings and
(perhaps) its providers, all indistinguishable.

So `decisions:63`'s derivation rule reads on a field that does not exist, and the row that
was supposed to make the graph deterministic leaves it underdetermined after all —
`findings:11` is not actually closed.

**Two knock-on defects in the vendored methodology, both real:**

1. **`package6_architecture.md` instructs the session to call `submit_contract_deps`** — a v1
   tool with no v2 equivalent. A session following the vendored script hits a tool that
   is not there. This is `findings:17`'s fossilization pre-mortem happening for real, and
   notably it is the *first* observed instance: rev 2 was vendored verbatim from v1
   including its tool names, and nothing checked that the tools still exist.
2. **`contract_has_consumer` is imprecise.** It is a `traced` criterion with
   `direction: in, to_tables: [components, contracts]` and **no `edge_type` filter**, so any
   incoming link from any contract or component satisfies it, whatever the link means. The
   criterion intends "someone consumes this contract" and actually tests "someone mentions
   this contract". It cannot distinguish invented scope from cited scope — which is exactly
   what it exists to catch.

**Engine half, resolved now:** see DEVIATIONS.md **D11** — the provider/consumer edge
becomes a typed link, `edge_type='depends_on'`, consumer → provider. The schema already
supports it (`links.edge_type`, `LinkSpec.edge_type`); nothing new is stored, and
`LinkGraph` already filters traversals by edge type. `finalize_plan` derives edges from
those links alone and from no others.

**Methodology half, bound to M6:** `package6_architecture.md` must stop naming
`submit_contract_deps` and instead instruct the session to record the dependency as a typed
link; `contract_has_consumer` must filter on `edge_type='depends_on'`. Both are edits to
vendored content, which under `decisions:61` means a new content revision with its own
stamp, not an in-place edit — and `requirements:71` requires a migration path from rev 2 to
rev 3. **Methodology rev 3 is already scheduled at M6** by the milestone recut, so this
lands there rather than being smuggled into M5a. Recorded here so it cannot be lost.

**Class:** new, and the third distinct class this milestone. Not F9's (missing mechanism),
not F17's (stale citation). This is **a primitive that lost its type information in a
redesign, silently invalidating a later row that depended on it.** `decisions:63` was
written at package 7 against a mental model of the v1 store; the v2 architecture that
flattened `contract_deps` into generic links was decided at package 6, *earlier*. Nothing
re-checked the package-7 fixes against the package-6 architecture, because the plan's own
review direction runs forward. Worth a v2 gate rule: **when a package-6 architecture decision
generalises or removes a primitive, every later row naming that primitive is a hole until
re-checked** — the same shape as F6's rule about identity changes, one level up.

---

## F21 — `allow_draft` cannot serve anything, because the graph is derived at finalization

**Status: RESOLVED at M7 (2026-07-23).** The reading that made the flag reachable is exactly
the affected-only freeze (`decisions:62`): while a revision is open the plan sits in `revising`
and has a graph, so `next_subtask` serves every sub-task *outside* the revision's frozen impact
set with no flag at all, and `allow_draft` + recorded consent becomes the override that serves a
*frozen* (affected) sub-task anyway, watermarked as a draft of the coming change — its `is_draft`
is true only in that case. The draft-plan branch still raises the honest `PlanNotFinalized`,
because a plan that never finalized genuinely has no graph. Built in `next_subtask`
(`_revision_frozen_refs` reads the open revision's repercussion rows straight from the store, so
the freeze and the enumeration cannot drift). See DEVIATIONS.md D25–D27.

**Was (M5a–M6): OPEN, resolve-by gate M7 (`revision-service`).** M5a shipped the honest error
instead of a silent empty result; M7 makes the flag do its real job.

**Rows:** `contracts:55` (`next_subtask`, error `PlanNotFinalized`), `requirements:40`,
`crud_grid:33`, `entities:9`, `findings:6` and its fix `decisions:62`/`sm_cells:186`/`187`.

**Insufficient:** `contracts:55` offers an escape hatch from its own refusal —
"`PlanNotFinalized`: refused unless `allow_draft` with recorded owner consent; draft briefs
carry an explicit watermark (`requirements:40`)". The flag has nothing to act on. SubTask is
"a node in the implementation task graph **derived at finalization**" (`entities:9`), and
`crud_grid:33` gives creation to "System: task-graph derivation at finalization and revision
regeneration". A plan that has never been finalized therefore has **zero sub-tasks**, so
`next_subtask(allow_draft=True)` has an empty graph to choose from no matter what consent is
recorded. `requirements:40`'s watermarked draft brief can never be issued.

**Discovered by driving, not by the audit.** This is check 2's exact shape — an outcome a
signature offers that is unreachable from the states the entity can be in — and the M5a
pre-build audit did not catch it, because the audit walks the *state machine's* table and
this unreachability comes from an entity-lifecycle row (`entities:9`) sitting outside it.
Worth recording as a limit of the two mechanical checks alongside F12's: **check 2 tests
contract outcomes against state-machine states, and misses outcomes made unreachable by
when the entity is created.**

**The one reading that makes the flag meaningful, and why it is M7's:** a plan can leave
`finalized` *after* it has a graph — `state_machines:1` moves it to `revising` when a
revision opens. Sub-tasks then exist while the plan is not finalized, and serving unaffected
ones is exactly what `findings:6` demanded and `decisions:62`/`sm_cells:186`/`187` granted
(affected-only freeze, so unaffected sub-tasks keep flowing). Under that reading
`allow_draft` is not about draft plans at all despite its name — it is the affected-only
freeze needing a way past a state check. That is `revision-service`'s design surface, so it
resolves at M7 rather than being guessed here.

**Built at M5a:** `next_subtask` raises `PlanNotFinalized` naming the real reason when
consent is given but no graph exists. The alternative — returning `AllBlockedReport` with an
empty blocking map — is what the code did before this was noticed, and it is the worse
failure: "everything is blocked" reported for a plan with nothing in it, indistinguishable
from a genuinely blocked build. Same silent-wrong-answer class as F14.

**Class:** F13's (unreachable advertised outcome), with F21's own wrinkle that the
unreachability is created by *lifecycle timing* rather than by the state machine. Third
instance of an escape hatch that cannot be taken; worth a gate rule: **a flag that bypasses
a precondition must name the state in which the bypass is reachable.**

---

## F22 — Narrowing an attachment did nothing, and the test asserted the wrong half

**Status: RESOLVED at M5a, 2026-07-21.** Found by driving the engine end-to-end, not by
the suite — the fifth milestone in a row where that step caught something the tests could
not.

**Rows:** `M5_PLAN.md` 2.5 (asymmetric friction), DEVIATIONS.md D8.

**The bug:** `AttachmentService.attach` inserted a new row for every placement and left the
previous one live. Promotion worked — the breadth comparison read the most recent row — but
**narrowing was a silent no-op**: attaching a project-scoped row down to a packet added a
packet row while the project row stayed live, so the target remained in the union for every
packet forever.

That inverts the design. `M5_PLAN.md` 2.5 makes promotion expensive (a recorded reason the
owner reads) and narrowing free, precisely because "too high" is the *silent* failure —
context bloat returns through the ceiling and nobody notices a cost spread evenly. The
implementation made the cheap corrective direction ineffective while leaving the expensive
one working, so the only reachable movement was upward. A ratchet, pointing the wrong way.

**Why the suite missed it, which is the interesting part.** There was a test for narrowing,
`test_narrowing_is_free`, and it passed throughout. It asserted `narrowed.promoted_from is
None` — that the operation was *classified* as a narrowing — and never asserted where the
row ended up. The assertion tested the bookkeeping the implementation had just written
rather than the behaviour the design asked for. The specification says "narrowing is free",
and "free" was read as "requires no reason" instead of "actually moves it".

This is the M1/M3 lesson (`F5`, `F11`) in a new position: there, tests inherited the
*specification's* blind spot. Here the test inherited the *implementation's* — written
alongside the code, from the same mental model, checking the field the code had in hand.
Both produce a green suite over a broken behaviour, and the driver caught both.

**Resolved:** a target now has exactly one **live** placement. Re-attaching stamps the
previous placement's `superseded_at` in the same atomic write. Superseded placements are
kept rather than deleted, because the promotion history is the owner's review surface
(`M5_PLAN.md` 2.5's second countermeasure) and deleting it would discard the log that makes
gaming visible. New tests assert the row's actual scope after narrowing, and that the
replaced placement survives as history.

**Class:** implementation, not plan insufficiency — the F14 shape. Carried here because the
methodology point is worth the entry: **a test written from the same mental model as the
code checks the code's bookkeeping, not the design's intent.** The countermeasure is the one
already in practice — drive it and read the output — and the sharper version is to assert on
the *observable consequence* (what does a packet actually receive?) rather than on the
record the operation just wrote.

---

## F23 — `PartsDontCover` can never fire: the split has no accounting denominator

**Status:** RESOLVED in M5b (2026-07-21) — the obligation surface (DEVIATIONS.md D12) is
built: `engine/obligations.py`, frozen at finalization, and `PartsDontCover` now fires
against it. Verification accounts per obligation, and a sub-task with no enumerated surface
refuses to be split or verified rather than passing vacuously.

**The third pre-build check it proposed is adopted, and has already paid** — it caught F26 on
its first use, one build package later. Amended by that catch to: *name the set, say where it
comes from, and say at what moment it is fixed.*

**Rows:** `contracts:40` (`split_subtask`), `requirements:37`, `decisions:63`,
`findings:11`.

**The defect.** `contracts:40` declares the error *"PartsDontCover: the parts do not
jointly cover the original sub-task's contracts"*. Under `decisions:63` a sub-task is the
implementation unit of **exactly one** contract, so every sub-task a split produces names
that same contract and the union of their contracts always equals the original's. **The
check is vacuous.** It can catch one that names an unrelated contract — a typo — and
nothing else.

The consequence is not cosmetic. `requirements:37` exists to say *"silent trimming of
relevant content is not a remedy"*, and `split_subtask` is the mechanism that is supposed
to enforce it. As specified, a too-large contract can be split into sub-tasks that between them
implement 60% of it and the split is well-formed. **The exact failure the requirement was
written to prevent passes the check that exists to prevent it.**

**Why it happened — a supersession fossil.** `contracts:40`'s plural ("the original
sub-task's contract*s*") is correct for the pre-`decisions:63` world, where a sub-task could
hold several contracts and joint coverage over a *set of contract refs* was a real check.
`findings:11` then fixed granularity to one-contract-one-sub-task at `decisions:63`, and the
fix never propagated back into the contract row whose error condition depended on it. This
is `F17`'s class — prose that dangles after the row it rests on is superseded — doing real
damage rather than merely confusing a reader.

**Class: plan insufficiency.** This is the sixth genuine instance of the characteristic
pattern F2/F4/F7/F9/F12 — behaviour named in prose without the mechanism that produces it.
The F15 countermeasure was applied before classifying it: a live row carrying the coverage
mechanism was searched for and does not exist.

What makes it worth its own entry is *what* is missing. The other five were missing
**triggers** — an event nothing fired. This one is a missing **denominator**: the plan
specifies an accounting check without ever specifying the set being accounted for. That is
a distinct sub-class and probably a more dangerous one, because a missing trigger yields an
unreachable code path (loud, and the mechanical audit finds it) while a missing denominator
yields a check that *runs, passes, and reports success* over an empty question. Neither
mechanical check in the pre-build audit detects it: every event has a contract, and every
outcome is reachable. The check is well-formed and means nothing.

**Countermeasure, proposed for the pre-build audit:** for every error condition phrased as
a coverage, accounting, or completeness check, name the set being covered and confirm the
plan says where that set comes from. If the denominator is not independently defined, the
check is decorative.

**Resolution:** DEVIATIONS.md D12 — a sub-task carries an explicit **obligation surface**,
enumerated by the planning session and frozen before any split, and coverage becomes an
invariant over obligations rather than a procedure over contract refs.

---

## F24 — Task membership was a v1 foreign key that the v2 flattening dropped

**Status:** RESOLVED in M5b (2026-07-21) — `edge_type='belongs_to'` is read at finalization
(`TaskGraphService._owning_task_id`), and `packages`/`tasks` are live: `declare_package`,
`assign_task`, and a finalization guard that refuses an unpackaged task. The generalised
v1-foreign-key sweep it implies remains bound to the **M6 gate**.

**Rows:** `entities:15` (Link), `components:*`, `contracts:*`; v1 `contracts.component_id`.

**The defect.** Which task a contract belongs to — in v1, `contracts.component_id`, a real
foreign key that `gaps.py` and `gates.py` join on throughout (`archive/v1/engine/gaps.py:196`,
`:204`) — has **no representation in v2**. The package-6 architecture flattened v1's typed
tables into the generic `plan_rows`/`links` pair, and the owning ref was not carried across.
In the frozen plan a contract's membership survives only as **markdown nesting** — the
`### brief-composer (components:12)` heading with its contracts printed beneath — which is
export rendering, not stored structure. v2 contract rows cite requirements, decisions and
findings; none cites its owning component. The `consumed by: components:N` annotation is the
*consumer* relation and is not ownership.

**Why it matters now.** Under the four-level model (D13) the **task** is the middle grouping
of the allocation hierarchy, and a task's sub-tasks are derived as the sub-tasks of the
contracts it owns. With no stored ownership the level is underived and unowned — the
`milestone` failure it was introduced to fix.

**Class: plan insufficiency, and the second instance of a distinct sub-class** — *information
that existed as a typed column in v1 and was silently lost when package 6 flattened the schema*.
`F20` (`contract_deps`) is the first. Two instances make it a characteristic risk of that
architectural move rather than an oversight: **the flattening preserved the rows and dropped
the relations between them**, because a generic row table makes rows the unit of migration
and edges invisible. Anything v1 expressed as a foreign key needs checking against v2 the
same way, and the remaining v1 FKs should be swept before M6 rather than found one at a time.

**Resolution:** DEVIATIONS.md D13 — membership is a typed link, `edge_type='belongs_to'`,
directed contract → task (member → owner; `components:N` is the frozen plan's read-only
spelling of task), exactly mirroring D11's treatment of the
dependency edge. Same argument: the column already exists, the direction is the one the
owning row can write, and typing it keeps traversal deterministic.

---

## F25 — "superseding the original in the graph" has no mechanism

**Status:** RESOLVED in M5b (2026-07-21) — `subtasks.superseded_by` is written by
`split_subtask` and read as a liveness filter by every graph read; dependants are repointed
from the original to its replacements, and serving/reporting/verifying a superseded node is refused
(`SubTaskSuperseded`).

**Rows:** `contracts:40` (`split_subtask`), `state_machines:9`, `requirements:37`.

**The defect.** `contracts:40` returns "list[SubTask] **superseding the original in the
graph**". Nothing in the plan says what supersession *does* to a graph node. `state_machines:9`
has no `split` event and no terminal state for a sub-task that was divided, so the original
does not leave the lifecycle by any transition the plan defines. Three concrete consequences
in the built engine, all silent:

1. `TaskGraphService._all()` is `SELECT * FROM subtasks` with no liveness filter, so a split
   original stays in `graph_status()` — in `in_flight` forever, since the state it was in when
   its brief proved too large is `in_progress`. It also trips the 24h staleness flag
   (`dep_failure_modes:6`) permanently.
2. `next_subtask` can serve it again. It is a candidate whenever `readiness_of` returns
   `ready`, and nothing knows it was replaced.
3. **Dependants deadlock.** `subtask_deps` edges point at the original's id. The original can
   never reach `done` — its work is carried by the sub-tasks that replaced it — so every consumer sits in
   `pending` behind a node that will never complete. `split_subtask` on a node with dependants
   silently bricks that branch of the graph.

The column exists — `subtasks.superseded_by`, added in M5a and annotated "split_subtask
lineage (M5b)" — and is written by nothing and read by nothing.

**Class: plan insufficiency** — the seventh instance of F2/F4/F7/F9/F12/F23, behaviour named
in prose without the mechanism. Closest to the *missing trigger* sub-class, but a variant
worth naming: the trigger is present (`split_subtask` fires) and the **effect** is
unspecified. "Supersedes in the graph" reads as though it means something because
supersession *is* a defined primitive elsewhere (`requirements:61`, for plan rows) — the
defect is assuming a plan-row primitive transfers to an execution-layer node with edges and a
lifecycle.

**Resolution:** built in M5b — supersession is a liveness filter on every graph read, and the
split rewires `subtask_deps` from the original to its replacements. Which one a dependant
should follow is not guessable in general, so the edge is redirected to *all* of them: the dependant
waits for all of them, which is the only reading that preserves "no sub-task precedes its
dependencies" (`requirements:34`) without the tool guessing.

---

## F26 — `audit_brief`'s denominator is not frozen with the brief

**Status:** RESOLVED in M5b (2026-07-21) — the closure is frozen into `brief_rows` at
composition; `audit_brief` accounts against it and reports drift as a separate, non-failing
number.

**Rows:** `contracts:41` (`audit_brief`), `contracts:68` (`compose_brief`),
`requirements:44`, `decisions:52`, `entities:13`.

**The defect.** Two contracts account the same brief against the same set at two different
times, and only one of them is anchored:

- `compose_brief` rejects with `IncompleteAccounting` when a candidate row is neither
  included nor recorded-omitted. Denominator: the link-graph closure, computed *now*.
- `audit_brief` compares "brief contents against the sub-task's link-graph closure" —
  computed *at audit time*, against a plan that has kept moving. `decisions:3` makes the plan
  a living source of truth; rows are added, superseded and revised throughout execution.

So a brief that passed 100% accounting at composition reports as incomplete later, purely
because the plan grew. `requirements:44`'s "100% accounting target" is the metric, and the
metric drifts on its own. Worse, the two failures are indistinguishable in the output: *the
composer skipped a row* and *the plan changed after composition* both surface as an
unaccounted ref, and the first is a defect while the second is normal life.

This also contradicts `entities:13`, which makes the brief immutable "so defect forensics can
always answer 'what exactly did the engine see'". A brief whose accounting is measured against
a set nobody recorded cannot answer that question: the closure the engine's brief was built
from is not stored anywhere.

**Class: missing denominator** — the second instance of F23's sub-class, and the **first catch
by the third pre-build check** F23 proposed ("for every coverage/accounting/completeness
check, name the set and confirm the plan says where it comes from"). Applied to
`audit_brief`, the check does not fail on *whether* the plan defines the set — it does,
`requirements:36`'s traversal — but on *when*, which is the same weakness one level down: an
accounting whose denominator is re-derived at read time is measured against a moving target.
**The check is hereby amended: name the set, say where it comes from, and say at what moment
it is fixed.**

**Resolution:** built in M5b — the closure is frozen into the brief at composition
(`brief_rows`, one row per candidate with its included/omitted disposition). `audit_brief`
accounts against the frozen closure, which is what `requirements:44` measures, and reports
plan drift since composition as a *separate*, non-failing observation. Two numbers, because
they are two different facts.

---

## F27 — The glossary was a rule with no mechanism, and broke the session after it was written

**Status:** RESOLVED 2026-07-21 — `tests/test_vocabulary.py` parses the banned list out of
`GLOSSARY.md` and fails the suite on any violating identifier. The check found 20 further
violations on its first run, in code the *previous* session's "full vocabulary sweep" had
already been through.

**Rows:** none — this is a defect in **this build's own process**, logged here because the
execution-sufficiency ledger is worth nothing if it only records the plan's failures and not
the builder's.

**The defect.** `GLOSSARY.md` was written on 2026-07-21, declared binding, and stated a
precise, mechanically checkable rule: *no identifier contains `packet`, `milestone`, `part`,
`project`, `stage`, `phase` or `session`.* The next build package (M5b, `brief-composer`)
shipped `parts=`, `part_ids`, `by_part`, `PartsExceedOriginal` and
`assign_task(component=...)`. The owner caught it by reading the code.

**Why it happened**, because "insufficient care" is not a cause anyone can act on:

1. **The read-only exception is also the primary input.** The glossary permits retired words
   in exactly one place — quotations from `spec/v2/plan.md` — and that file is *also* what is
   read immediately before writing each function. `contracts:40`'s signature is literally
   `parts: list[SubTaskSpec]` and it declares an error named `PartsDontCover`. The glossary was
   read once, at session start; the retired vocabulary was re-read, freshly and in the exact
   words of the thing about to be written, at every implementation step. **Ranked by proximity
   to the moment of typing, the exception beats the rule.**
2. **Naming happens at the point of least attention.** The thinking went into the obligation
   denominator and the dependant deadlock; the parameter name was incidental typing. The words
   that leak are precisely the ones nobody is thinking about, which is why care cannot be the
   countermeasure.
3. **There was no check.** Every other invariant in this build has a mechanical one — the
   pre-build audit, the test suite, the gates. Vocabulary had a well-argued document and zero
   enforcement.

**Class: plan insufficiency — the eighth instance of F2/F4/F7/F9/F12/F23/F25**, behaviour named
in prose without the mechanism that produces it, and the first where the prose is *ours*. The
glossary is exactly the artifact that has been diagnosing this pattern in the frozen plan for
eight entries, and it reproduced the pattern in itself within a day. That is the strongest
available evidence that the pattern is structural rather than a property of the v1 planning
session: **a rule and its enforcement are two different artifacts, and writing the first feels
like doing the second.**

**The 20 further violations are the load-bearing detail.** Commit `41184cd` was titled "Full
vocabulary sweep" and was done by reading. It left `current_stage`, `stage_range`,
`UnknownStage`, `StageScript`, `get_stage_script`, `next_stage`, `required_stages` and 13 test
names untouched. A sweep performed by attention misses at the same rate as the writing that
required it — so the check is not merely a guard against future drift, it was needed to
complete the sweep that was believed finished.

**Resolution.** `tests/test_vocabulary.py`:

- parses the banned words **out of `GLOSSARY.md`'s own rule** rather than carrying a copy — a
  second list drifts, and a vocabulary rule with two sources of truth is the bug it exists to
  prevent (the same argument D10 made for readiness);
- tokenises identifiers (`PartsDontCover` → parts/dont/cover) so `partial` and `third_party`
  are not false positives — a check that cries wolf gets disabled, which is D7's whole lesson;
- enforces the glossary's *stated* rule and not a stricter one — the rule deliberately omits
  `component`, `unit` and `chunk`, and inventing a harsher check would put the code and the
  document out of step, which is the same failure again;
- carries a test that the check **can** fail, written on day one, because a check that cannot
  fail is F23's disease;
- records every exception in `GLOSSARY.md` **with a reason**, so an exception is a visible act
  — the same friction shape as `requirements:79`'s waiver log and D8's promotion reason.

**One exception survived the day** (`writer_lease.session_id`, exempted by the rule's own
text) and it is gone too: the writer lock was removed on 2026-07-22 and took its only `session`
identifier with it, so the banned list now has no exceptions at all. Two more were proposed on
the day and the owner refused both, which is the part worth remembering:

- **`PartsDontCover`** was kept as a "quotation" of `contracts:40`'s declared error name,
  on the strength of `errors.py`'s convention that a contract's error name is the class name.
  Presented to the owner as an unresolved tension between two rules; it was not one. The
  convention is internal, has no consumer outside this repo, and the plan's spelling stays
  findable in a docstring — so the rename to `ObligationsNotCovered` cost nothing and the
  "tension" was a live retired word being defended by a rule that was never load-bearing.
  **The quotation rule covers prose, not identifiers.**
- **A local variable in `engine/gaps.py`** was listed as an exception "renamed on next touch
  of that file" — a carve-out wearing a schedule. Renamed on the spot.

The generalisable error in both: when a rule is broken and a fix is proposed, the proposal
inherits the same lack of enforcement. An exceptions list is where a retirement quietly
becomes a preference, and it needs the same scrutiny as the original rule.

**The generalised lesson, and it applies to the product and not only to this build:** a
vocabulary is enforced at the moment of *writing*, or it is not enforced. The three things
that would have prevented this, in order of strength, are (1) a check that runs on every
commit, (2) the glossary being present in the brief the writer is working from rather than
read once at session start, and (3) the writer's attention. Only the third one was in place.
See the open design question bound to the **M6 gate**: how a plan's own glossary reaches the
code engine that must comply with it.

---

## F28 — Six more v1 foreign keys were dropped by the flattening, and nothing missed them

**Found:** 2026-07-21, M6 gate item 2.1 — the sweep that existed to stop this being found a
third time by accident.

**The class.** v1's typed row tables carried mandatory (`NOT NULL`) foreign keys. Package 6
flattened them into generic `plan_rows` plus a `links` table, which preserved every row and
dropped every relation. F20 (`contract_deps`) and F24 (`contracts.component_id`) were each
found on their own, months apart, by tripping over the consequence rather than by looking.
Two instances made it a characteristic risk of that architectural move, so the sweep was bound
to this gate.

**The result.** `archive/v1/engine/schema.sql` declares **eight** mandatory relations that are
not `plan_id`. Two were already repaired. The other six were still missing:

| v1 relation | asserts | state before this fix |
|---|---|---|
| `uc_steps.use_case_id` | a step's owning use case | no edge, no check |
| `uc_extensions.step_id` | an extension's owning step | no edge, no check |
| `crud_grid.entity_id` | a CRUD row's entity | no edge, no check |
| `state_machines.entity_id` | a machine's entity | no edge, no check |
| `sm_cells.machine_id` | a cell's owning machine | no edge, no check |
| `dep_failure_modes.dep_id` | a failure mode's dependency | no edge, no check |

Confirmed mechanically: `machine_id`, `entity_id`, `use_case_id`, `step_id` and `dep_id`
appear in **zero** files under `engine/`.

**Why nothing noticed, which is the interesting half.** An orphan is not a broken row. A
`uc_steps` row with no use case is writable, readable, renderable and *gate-clean* — the
gap rules ask whether a step has extensions (`step_without_extensions`) and whether an actor
appears in a use case, and never whether a step has a parent, because in v1 the question was
unaskable. The constraint was deleted along with the column that carried it, and the check
that would have replaced it was never written because nobody was missing anything.

**A second, quieter instance of the same shape.** `links.edge_type` is
`TEXT NOT NULL DEFAULT 'links'` with no closed vocabulary: any string is a valid edge type.
A misspelled `belogns_to` therefore produces a real, durable edge that no traversal looks for
— F20's invisible relation arriving by typo instead of by omission, and silent in exactly the
same way.

**Resolution.**

- **`belongs_to` for all six**, not six new edge types. Every one asserts the same thing —
  *this row's owning parent* — and v1's seven differently-named parent columns were themselves
  seven names for one relation. The parent's row type disambiguates: `uc_steps:4 belongs_to
  use_cases:2` needs no second edge name.
- **The map is methodology data** (`rev3/manifest.yaml`'s `containment:` block), not engine
  knowledge. An engine that knows `uc_steps` has started to contain a methodology of its own,
  which is `findings:4`. The engine enforces whatever revision is loaded and knows none of the
  names.
- **Enforced at submission**, in `RowService._validate`'s neighbourhood: a child row must
  declare exactly one `belongs_to` link, to a row of the declared parent type. This is
  well-formedness rather than judgment — a step with no use case makes no claim, the same way
  a row with no provenance makes none — so **D7's warn-don't-block stance for advisory gate
  findings is untouched**. It restores precisely what `NOT NULL` used to do, at the same
  moment `NOT NULL` used to do it.
- **`EDGE_TYPES` closes the edge vocabulary** in `engine/models.py`, and an unknown type is
  rejected with the valid set named.
- `tests/test_containment.py`, including a test that the map loading **empty** would be
  caught: with `containment={}` an orphan must be accepted, or the rejection tests prove
  something other than the map (F23's disease).

**The eighth relation is deliberately excluded, and the reason is worth keeping.**
`contracts.component_id` was declared in the containment map on the first pass, on the
grounds that it is the same relation. It was not a repair: F24 already restored it, enforced
at **finalization** — a contract with no owner is reported there, never guessed. Adding it
here did not restore a lost constraint, it *moved an existing one earlier*, and **53 of the
57 resulting test failures came from that one line**. The failures were the mechanism
reporting a design change honestly, and taking them as fixture churn to be tidied away would
have converted an unargued change to when the tool interrupts the planner into a fait
accompli. The line was removed. Whether contract ownership should bite at submission like
the other six, or at finalization as it does now, is a real inconsistency and an owner
decision — **bound to the M7 gate**, not settled here by side effect.

**The fixtures were carrying the defect too, which is the best evidence it was invisible.**
Fixing the remaining four failures meant repairing real orphans in our own tests: `uc_steps`
rows with no use case at all, and — in `test_gates.py` — an `sm_cells` row linked to its
state machine by `LinkSpec(0)`, an **untyped** edge. That is precisely v1's NOT NULL
`machine_id` degraded into an optional association that nothing asserts and no traversal
requires. One of those fixtures had been asserting against a plan where *nothing had been
written*, and passed.

**What this does not fix, recorded rather than left implied.** v1's `spike_id` was a
*nullable* column on ten row tables meaning *this row is provisional pending spike N*. In v2
it survives only as `claim_tracks.spike_id`; the row-level relation is gone. It was nullable,
so it is not this class, but it is the same loss and it needs a decision rather than a
silence. **Bound to the M7 gate.**

**The lesson, which is F27's in a different register.** Both defects are a constraint that
existed, was deleted by a refactor, and left no trace of its own absence. A `NOT NULL` column
is a mechanism; the rows that survive it are not. When a migration changes the *shape* of the
store, the checklist is not "did every row arrive" — rows are easy to count and that is
exactly why counting them feels like verification. It is "did every constraint arrive", and
constraints are invisible once removed.

---

## F29 — Every idempotency key was built by hand, and every one defeated itself

**Found:** 2026-07-21, while fixing something else. The owner's framing is the finding:
*"DRY is basic compsci, and exactly the type of behaviour you are supposed to be enforcing.
This is a bigger fundamental problem than 21 tedious updates."*

**The promise.** `decisions:43` — a replayed idempotency key returns the original receipt and
never duplicates. That only works if the key answers the question it exists to answer: *is
this the same operation I already performed?*

**What was there instead.** Thirty-two call sites built their key by hand as an f-string, and
twenty-one of them appended `now()`. The timestamp was there to make the key unique — which
cancels the only thing the key does. **A key that is never equal to itself can never detect a
repeat.** `write_atomic`'s replay path was unreachable from most of the engine while appearing
to be in force.

**Why it survived a whole build: the clock hid it.** On Windows the system clock updates about
every 16ms. `now()` called 2000 times in a loop returns the *same* value 2000 times. So the
timestamp did not even deliver the uniqueness it was added for. Two operations inside one tick
produced an identical key, the second was treated as a replay, wrote nothing, and returned the
first one's receipt **reporting success** — a silent wrong answer, surfacing only as an
intermittent test failure that got *more* frequent as the code got faster. It was first seen
minutes after F28's fix removed a redundant write.

**The diagnosis that matters is not the timestamp.** Nobody copied a mistake: thirty-two
authors each independently did the obvious thing at the point of least attention. That is the
signature of a **missing owner**, and it is the same signature as eight spellings of
`created_at` (F27) and six differently-named foreign keys asserting one relation (F28).
Duplication first; the wrong idea second. Offering to correct twenty-one call sites was
offering to treat the symptom.

**Resolution.**

- **`engine/idempotency.py` is the only place a key is built.** `key(operation, *subjects)`
  names what the operation acts on and **refuses a timestamp outright** — a `datetime`, or a
  string the clock recognises as storage form.
- **It asks `engine/clock.py` whether a value is a timestamp** rather than carrying its own
  date-matching. A second copy of that knowledge would be this defect one level up.
- **All 32 sites converted, including the 11 that were already correct.** Leaving a correct
  hand-built key alive leaves the *pattern* alive, which is what produced the other 21.
- **`tests/test_idempotency.py` walks the AST of every engine module**, finds every
  `write_atomic` call and fails on a key that is a literal or an f-string. Extraction alone
  would not have stopped a thirty-third site. Honest limit, recorded in the test: it catches a
  key literal *at the call site*; a key assembled into a local first would pass, and `key()`'s
  runtime refusal is the second line.
- **`within(op, *subjects, seconds=N)`** is the deliberate fallback the owner proposed — "have
  I done this in the last second?" — with the window *in* the key, so choosing it is visible.
  The old code chose a window of zero by accident and believed it had chosen none.

**Two latent bugs became reachable the moment keys were stable**, and both are the same shape
as the defect: `compose_brief` and `attach` read a new record's id off the op they had just
executed. On a replay no op executes and the read fails. Neither path had ever run, because no
key had ever repeated. Both now read from the receipt — which `submit_rows` has always done,
with a comment explaining why, ten feet away.

**And the check caught the author.** The new module's parameters were first named `part` and
`parts` — a word retired the previous day, by me, in a session about retired words leaking in
at the point of least attention. `tests/test_vocabulary.py` failed the suite in 0.1s. The rule
was fully in mind and still broken; the mechanism is what held.

---

## F30 — Gate history has three readers and no writer

**Found:** 2026-07-22, at M6's pre-build audit, before `engine/resume.py` existed.

**The promise, made three times.** `uc_steps:5` — the tool returns "stage, gate history,
warnings, mandate, current script". `requirements:10` — a planner opening a workspace gets
back "current stage, gate history, outstanding warnings…". `contracts:64` — `plan_status`
serves a digest including "gate history". A resuming planner is owed the record of which
gates have been run and how they went.

**What was there instead.** `run_gate` evaluated the criteria, raised its warnings, built a
`GateResult` and returned it. Nothing stored it. No table, no column, no contract. The verdict
existed for the duration of one call and was then unrecoverable, so a planner resuming after a
context clear could not learn that package 3 had been gated at all, let alone that it had
failed twice on the same hole.

**Why the existing checks did not catch it.** The three pre-build checks look at the plan's
*contracts* — a state-machine event with no contract firing it, an outcome unreachable from
any state, an accounting with no denominator. This is none of those. Every contract here is
well-formed; the gap is between two of them, and it is directional: `contracts:64` consumes a
thing that `contracts:22` was never asked to produce. It is the mirror image of the
schema-only fix (a write path with no reader) recorded at M5a, and the two together suggest
the general question worth asking of any digest field: **which contract writes this, and does
its signature admit that it did?**

It was found by reading `contracts:64` field by field and asking where each one would come
from — which is what the audit is for, and it took about a minute once the question was posed
that way.

**Resolution.** A `gate_runs` table; `GateEngine._record_run` writes one row per run, keyed by
how many runs that package already has so that a re-run records a second verdict rather than
replaying the first. The *holes* are deliberately not stored: re-running the gate re-derives
them mechanically and deterministically (`requirements:46`), and history's job is to say what
happened, not to answer what is true now. `plan_status` shows the newest verdict per package
and counts the rest, naming `gate_runs()` — otherwise the history grows without bound and
breaks the compactness `requirements:62` requires, which is exactly what the driver showed on
its first run.

---

## F31 — Methodology rev 3 identified itself as rev 2

**Found:** 2026-07-22, by reading a line of driver output that said
`methodology plantool-rev2-2026-07-15` while the engine was loading `rev3/`.

**The promise.** `requirements:71` ships the methodology as versioned content assets carrying
a **content-revision stamp**, with an update path that migrates a plan from one revision to
the next. `decisions:61` vendors the content rather than inventing it, and the stamp is what
makes "which methodology produced this plan?" answerable at all. It was the red team's
pre-answer to the fossilization premortem in `findings:4`.

**What was there instead.** `rev3/manifest.yaml` was created by copying `rev2/manifest.yaml`,
and the copy included `revision: 2` and `revision_stamp: "plantool-rev2-2026-07-15"` — along
with a header paragraph explaining that this file was rev 2 and that rev 3 would come later.
The content diverged (the vocabulary sweep of D14 landed in rev 3 and not rev 2); the identity
did not. Every caller asking which revision was in force got the wrong answer, `load(3)` and
`load(2)` reported the same stamp, and the migration path `requirements:71` requires had no
way to tell the two apart.

**The shape, which is now familiar.** The stamp is a *denominator for identity*, and it was
derived from the thing it was supposed to distinguish. Nothing failed: every read succeeded,
every test passed, and the wrong answer was well-formed. This is the same silent-success class
as F23, F28 and F29 — and, like F29, it was produced by copying rather than by reasoning, at
the point of least attention.

**A test asserted the stamp, and asserted the wrong one.** My first write-up of this entry
said no test could have failed on it. That was wrong, and the truth is worse:
`tests/test_guidance.py` had a test called `test_script_carries_the_revision_stamp` whose body
was `assert script.revision_stamp == "plantool-rev2-2026-07-15"` — a **literal**, checked
against whatever revision happened to be default. When the default moved to rev 3 the test
kept passing, because rev 3 was answering with rev 2's string. The one test standing guard
over the identity mechanism had been handed the copy and told to confirm it.

That is the reusable lesson, and it is sharper than the defect: **a test that asserts a copied
literal cannot detect that the literal was copied.** Its replacement asserts the
*relationship* — the stamp of revision N contains `revN` — which no amount of copying can
satisfy accidentally. Fixing the manifest without fixing the test would have left the next
revision free to repeat this exactly.

**How it surfaced.** Not from the suite, which was green and complicit. `plan_status` prints
the revision in its digest, the driver printed the digest, and a person read the line. Third
consecutive build package where driving the engine end to end found what the tests could not,
and the first where the finding was in a *data* asset rather than in code.

**Resolution.** `rev3/manifest.yaml` now declares `revision: 3` and
`revision_stamp: "plantool-rev3-2026-07-21"`, and its header states that changing content
means changing the stamp. The drift baseline (`engine/fingerprint.py`) carries the stamp, so a
plan whose methodology changed under it is now visible as drift at resume — which was the
mechanism `requirements:71` intended and which could not have worked while every revision
answered with the same string.

---

## F32 — A row's name was guessed from free-form content, three times, and fell back to an address

**Found:** 2026-07-22, while building the naming design of `M6_PLAN.md` §6 — the owner had
asked for the rule after a session in which almost every sentence written to him was made of
bare addresses he could not read without going and fetching something.

**The promise.** Nothing states it, and that is the defect's first half: no row type in the
frozen plan carries a name, `plan_rows` had no name column, and `submit_rows` validated
content only as "a non-empty object". The tool nevertheless has to *say things about rows* —
gap asks, gate holes, task names, brief sections — and every one of those needs a handle.

**What was there instead.** Three separate implementations of the same guess, in two modules,
with two different key lists:

- `gaps.title_of` tried `title`, `name`, `text`, `quote`, `description`, truncated to 120
  characters, and returned `str(row.ref)` when none matched.
- `tasks.py` (task creation) tried `title`, `name`, and fell back to the ref.
- `tasks.py` (contract specs) tried `title`, `name`, and fell back to the ref.

`title_of`'s own docstring admitted the situation: *"there is no title column to read — this
is the agreed order of preference across every table."* An agreed order of preference over
free-form JSON is exactly what D12 refused for accounting denominators, and for the same
reason: `content` has no per-table schema, so nothing may be inferred from it.

**Why the fallback is the worse half.** A row whose content used none of the five keys got
announced to the reader as an address and nothing else. That is not hypothetical: `crud_grid`
rows carry `op` and `actor`, and `sm_cells` rows carry `state`, `event` and `transition_to`.
Both were served to the reader as `crud_grid:4` — the precise failure the owner had just
described, produced by the code rather than by the writer.

**The DRY reading.** Three copies of one decision, two of them already disagreeing about which
keys count, is the duplication this product exists to prevent, inside the engine that exists
to prevent it. The second occurrence was the moment to extract; there were three.

**Resolution.** `plan_rows.name` is a real column, `NOT NULL`, supplied at creation and
rejected pedagogically when missing. All three guesses are deleted; `gaps.name_of` is the
single owner and reads the column. A partial unique index makes two live rows in one table
unable to share a name, so a duplicate is a signal at the moment of typing rather than a
collision found a week later. `plan_rows.named_for` records the content fingerprint the name
was given for, so a name cannot silently survive a change of meaning. Tests in
`tests/test_naming.py`. The `{title}` placeholder in the methodology's gap rules and gate
criteria is now `{name}`, closing the second spelling of the same column role.

---

## F33 — Supersession was two transactions, so a crash between them orphaned the old row

**Found:** 2026-07-22, while adding the live-name uniqueness index — the index rejected a
replacement that legitimately kept its original's name, which exposed the write ordering.

**The promise.** `requirements:61` — the replacement is created with a `supersedes` pointer
and the old row is stamped once with `superseded_by` and a timestamp. `contracts:12` presents
this as one act, and liveness is "the single check that `superseded_by` is null".

**What was there instead.** `supersede_row` called `write_atomic` twice: once to insert the
replacement, then again, under a derived key, to stamp the old row. Between them the old row
was live, unstamped, and sitting beside its own replacement — both live, both claiming to be
current, with nothing recording the relationship. A crash in the gap left the plan in exactly
that state permanently, and the second call's derived idempotency key meant a retry could not
tell "never stamped" from "stamped already".

The atomicity work of M6b covered a row and its links, which was the instance found then. This
is the same class one call over, and it went unlooked-at because the two writes were separated
by a line that reads like a local variable assignment: the replacement's ref does not exist
until the insert has run.

**Resolution.** One `write_atomic` of three ops: the old row's state and `superseded_at` go
first, the replacement is inserted second, and the old row's `superseded_by` pointer is
written third via `FromOp`, which reads the ref back from the earlier op in the same batch.
The order is load-bearing for the naming index as well — a replacement may keep its
original's name, so the old row has to leave the live-name index before the replacement
enters it. Covered by `tests/test_naming.py::test_a_superseded_rows_name_is_free_for_its_replacement`
and the existing supersession tests in `tests/test_rows.py`.

---

## F34 — The mandate told every cold planner to resume from a call that does not exist

**Found:** 2026-07-22, by reading the surface's first end-to-end run — the same way F31 was
found, and again not by a test.

**The promise.** The engineer's mandate is the first thing a planner reads and the second
line of it says the database is the source of truth and "a new session resumes losslessly
from `plan_status()` + `next_gap()`". `requirements:71` ships the methodology as versioned
content assets so that a plan can be told which methodology it was built under.

**What was there instead.** There is no `next_gap`. The call is `next_gaps`, and has been for
the whole of v2. A resuming planner following the mandate literally gets `UnknownTool` on the
one instruction the mandate gives it for recovering, at the exact moment its context is
empty and it has nothing else to go on.

**Why nothing caught it.** The methodology is served verbatim, so the surface's own
call-name check exempts it — deliberately, because the alternative is the tool editing the
owner's methodology in flight. That exemption is correct and it is also a blind spot, and the
two facts are not in tension: an exemption at runtime is an obligation at build time.

**Three more of the same shape, larger.** `get_stage_prompt`, `get_plan_pack`, `export_plan`
and `freeze_plan` are named in rev 3's scripts and none has a v2 tool. The first two are
renames waiting to happen — one of them still carries a retired word in a shipped asset. The
last two are the *whole of package 8's procedure*, and no v2 contract exists for either, so
**the methodology's final package cannot currently be executed**. That is not a rename; it is
a missing pair of contracts, and it had been sitting behind a manifest comment saying the
scripts "still address v1's tool surface" — true, and not specific enough for anyone to
notice that one package had stopped working.

**Resolution.** `next_gaps` corrected in the mandate and the revision stamp moved with it, per
F31's rule that the stamp changes whenever the content does. The other four are bound to the
M6 gate with the rest of rev 3's outstanding half, and are now named individually in
`tests/test_surface.py` — each with its reason and where it is owed — by a test that parses
every call name out of rev 3 and resolves it against the tool registry. An undeclared one
fails the suite, and a declared one that quietly gets built also fails, so the list cannot rot
in either direction.

**The lesson, which generalises past this instance.** *Every exemption from a runtime check
is a debt owed to the test suite.* The verbatim exemption was designed carefully, argued for
correctly, and created a channel through which the tool told its reader to do something
impossible. When a check is deliberately not applied somewhere, the question that follows is
not "is the exemption right" — it is "then who checks that region, and when".

---

## F35 — The last package's script promised gate checks the gate does not have

**Found:** 2026-07-22, by reading the final planning package's script and its gate criteria
side by side while working out what F34's missing calls actually needed. Not by a test, and
no test could have found it — see below.

**The promise.** The eighth and final package of the planning interview ends the interview.
Its script tells the planner that running the final gate "folds in gates 1–7, open conflicts,
the `plan.md` render, and a lossless `plan.yaml` round-trip check." A planner reading that has
been told the export is mechanically verified before the plan closes, and that a render which
loses content will be caught.

**What is actually there.** That gate has two criteria: every earlier gate is green, and no
conflict is open (`engine/methodology/rev3/gate_criteria.yaml`, the package-8 block). There is
no render check and no round-trip check. Neither could exist, because no contract renders or
exports anything — which is F34's other half.

**Why it matters more than a stale sentence.** The round-trip check is the only thing in the
whole methodology that would confirm the exported plan is lossless, and losslessness is the
entire reason the structured export exists. A planner is told a safety net was tested when
nothing tested it, and the failure is silent in the direction that matters: the gate passes,
so the plan freezes with an unverified export behind it.

**Why no check can see this.** All three mechanical pre-build checks operate on contracts and
state machines. This is a script — vendored prose served verbatim to the planner — describing
a data file. Both are content assets, both are well-formed, and they disagree. The surface's
door resolves *call names* in outgoing text, which is why F34 was findable; it has no way to
resolve a claim about what a gate contains. **The class is new: a content asset describing
another content asset's contents, with nothing holding the two together.**

**Resolution.** Not fixed here. Bound to the M6 gate with the rest of rev 3's outstanding
half, because the honest fix depends on a decision that has not been made: if a render
contract is added, the script is right and the criteria are missing; if it is not, the script
is wrong and the sentence goes. Writing either one before the owner rules would be inventing
methodology (`findings:4`).

**Correction to F34, recorded here rather than by editing it.** F34 says `export_plan` and
`freeze_plan` are "a missing pair of contracts". Checking that claim is what turned this up,
and it is half wrong: **`freeze_plan` is v1's name for `finalize_plan` (`contracts:35`)**,
which exists and is the sole contract firing the `finalize` event. What is wrong there is not
a missing contract but the script's prose, which says the freeze sets the plan read-only and
that "there is no unfreeze" — v2 says the opposite, since `decisions:3` has the plan never
frozen and a finalized plan reopens through `request_revision`. Only `export_plan` is
genuinely absent, and it is absent because plan rendering was scoped out of the charter. The
lesson is F15's, again: **when a mechanical check reports an absence, look for a live
successor with the same behaviour under a different name before classifying it as missing.**

---

## F36 — The final gate's own criteria are resolved; the render check never was

**Found:** 2026-07-22, closing F35 out.

**Resolution of F35, recorded here rather than by editing it.** The owner ruled that the last
package keeps a human-readable render, so the script's sentence was the wrong half to keep.
The render exists now (`render_plan`, DEVIATIONS D21) and the script says what the gate
actually checks: prior gates green, no open conflicts, and *the render is not gated* — with
the reason stated to the planner, which is that whether the plan says what the owner meant is
a judgment and the gate only checks what a machine can check. The `plan.yaml` round-trip
check is gone entirely, because the round-trippable bundle it would have checked was never
built and is not going to be.

**What F35 got right and is worth keeping:** the class it named. A content asset describing
another content asset's contents, both well-formed, disagreeing, with nothing holding them
together. Nothing added here closes that class — this instance was fixed by hand, and the
next one will be found the same way.

---

## F37 — Eighteen v1 call names sat behind a check that could only see four

**Found:** 2026-07-22, by listing every backticked identifier in the rev-3 assets before
starting the renames, rather than by trusting the list of what needed renaming.

**What was believed.** F34 named four calls the scripts still addressed from v1's tool
surface — `next_gap`, `get_stage_prompt`, `get_plan_pack`, and the package-8 pair — and the
surface's registry test was written to hold them so they could not be lost. That test reads
the assets with the door's `CALL` pattern, which matches a name *written as a call*:
`next_gaps()`, `run_gate(8)`.

**What was actually there.** Eighteen more, every one written as a bare backticked identifier
and therefore invisible to that pattern: `submit_use_cases`, `submit_requirements`,
`submit_entities`, `submit_crud`, `submit_states`, `submit_state_cells`,
`submit_dependencies`, `submit_dep_failure_modes`, `submit_components`, `submit_contracts`,
`submit_contract_deps`, `submit_uc_extensions`, `record_decision`, `confirm_assumption`,
`file_question`, `resolve_question`, `get_rows`, `disposition_finding`. Six of the eight
package scripts told the planner to file rows through calls that do not exist. Package 1
could not be executed either, and nobody had noticed, because the check that was supposed to
be the mechanism for exactly this reported four.

**Why the check could not see them.** It was borrowed. `CALL` was written for the door, where
it scans *outgoing prose the tool composed* and where a narrow pattern is right — a false
rejection there fails a call that was working, so it deliberately does not match a name in
running text. Reused against the methodology it inherited that narrowness, and the methodology
is running text. The pattern was correct in both places and the reuse was still wrong.

**The general form, which is the point.** A check reused in a second context keeps the
tradeoffs of the first, and those tradeoffs are invisible at the new call site — the reader
sees a check named for what it finds, not for what it was tuned to ignore. The mechanism
existed, ran green, and was measuring something narrower than its name — which is the same
shape as F23 and F26's missing denominators, arriving through reuse instead of omission.

**Fixed.** All eighteen replaced with v2's calls: every `submit_*` is one `submit_rows` batch
whose rows name their table, `record_decision` is a `decisions` row, `confirm_assumption` is
`resolve_assumption`, `get_rows` is `read_rows`, `disposition_finding` is `resolve_finding`,
and `file_question`/`resolve_question` became the mandate's assumed-row-then-resolve loop,
which is how v2 already holds an open question. The new check reads the assets as text
against v1's surface taken from `archive/v1/`, and does not use `CALL`.

---

## F38 — Findings are two different things with one name, and the package-7 gate reads the empty one

**Found:** 2026-07-22, while replacing `disposition_finding` in the package-7 script.

**Not fixed.** Bound to the M6 gate.

**The two things.** `file_finding` (`contracts:33`) writes a row into the `findings` SQL
table, with `finding_refs` beside it — a service table with its own lifecycle. The frozen plan
also carries `findings:1` … `findings:13` as *plan rows*, addressed the way every plan row is
addressed, and the methodology's package-7 gate criteria read `table: findings` through
`read_rows`, which reads `plan_rows`.

**The consequence.** A planner that follows the red-team script exactly — file every issue
with `file_finding` — files them all into the service table, and then the package-7 gate looks
in `plan_rows`, finds nothing, and reports "no adversarial findings recorded". The gate is
unpassable by the route the methodology prescribes, and the second criterion is worse than
unpassable: it checks `disposition` and `disposition_rationale`, which are v1's field names
for what the service now calls `outcome` and `rationale`, so it would find nothing to check
even if the rows were in the right place.

**Why this is not F30 again, quite.** F30 was three readers and no writer. This is a writer
and a reader that both work, addressing two different stores that share a word. The gate is
well-formed, the contract is well-formed, and the disagreement is in the vocabulary — which is
what `GLOSSARY.md` exists to prevent and did not, because both uses predate it and neither
looks wrong on its own.

**What the fix needs, and why it is not made here.** It is a design decision, not a repair:
either findings are plan rows (and `file_finding` writes one, gaining names, provenance and
supersession, and losing its own lifecycle table), or they are service rows (and the package-7
gate criteria must read the finding service, which no criterion type currently can). Choosing
by which is easier to code would be choosing the vocabulary by accident, again.

---

## F38 — resolved

**Resolved 2026-07-22 by the owner's ruling, recorded as DEVIATIONS.md D22.** Findings keep
their own store; the gate learns to read it. The reasoning is in D22 and is not repeated
here — the short version is that a plan row is write-once and a finding moves through states,
so they are different kinds of object and the collision was in the vocabulary, not the
storage.

**What is worth carrying forward from it.** The fix that mattered least was the one asked
for. Changing the two gate criteria took an afternoon; what actually stopped F38 recurring
was reserving `findings` as a plan-row table name, because `plan_rows.table` is open by
design and a decision about which store owns a word is not a mechanism until something
refuses the other one. And what nearly got missed entirely was the door: findings are cited
by address in the owner's own prose, so leaving them out of the resolver would have made the
tool report the F17 damage it exists to detect, in every plan that ever mentions a finding.

**The general shape, worth the next audit's attention:** when a decision moves an object out
of a store, the checks that read it are the visible half. The *addresses* that reach it are
the half nobody lists, because addressing looks like a property of the store and is not.

---

## F39 — The mandatory grouping had no tool that could create one

**Found:** 2026-07-22, while adding the packaging step D13 asked the methodology for. The
step is one sentence in a script; writing it meant naming the calls a planner would make,
and the surface exposes none of them.

**What was there.** D13 makes package membership mandatory: every task belongs to exactly
one package, there is deliberately no catch-all bucket, and `finalize_plan` refuses a plan
with an unpackaged task. `declare_package` and `assign_task` are built, tested, and reachable
from Python. The surface — the only externally visible part of the tool — exposed neither,
and nothing read the cut back either, so package ids existed only in the return value of a
call nobody could make.

**The consequence, which is the whole entry.** Every plan authored through the surface
derives tasks from its `components` rows, and no plan authored through the surface could put
one in a package. So `finalize_plan` refused every such plan, permanently, on an invariant
the caller had no way to satisfy. Planning could be completed and never closed.

**Why no check saw it.** The coverage test reads the frozen plan and asks whether every
contract sent to `components:15` is exposed. `declare_package` and `assign_task` are *ours* —
D13 is a deviation, and the plan has no contract for them — so the denominator never
contained them and the accounting was correct and complete while the surface was unusable.
The door catches the neighbouring case, a call *named* in outgoing text that no tool exposes;
this one was never named anywhere, because the script that would have named it was the thing
still to be written. `UnpackagedTask`'s own message said "Declare a package and assign them"
in prose, which is a call name written so that nothing can resolve it — F37's lesson from the
other side.

**The general form, and it is a new one.** The three pre-build checks and the door all ask
whether something *named* can be reached. This is the reverse: an invariant that is
**enforceable but not satisfiable**, where the refusal is correct, the guard is correct, and
no route to compliance exists. A missing trigger fails loudly; a missing denominator reports
success; **a missing route reports a refusal that reads exactly like the caller's mistake** —
and it will be believed, because the message is accurate.

The question to add to the audit habit, beside F30's *which contract writes this field?*:
**for every invariant a guard enforces, which exposed call satisfies it?**

**Fixed here.** `declare_package`, `assign_task` and `packaging` are exposed, each in `ADDED`
with its reason. `packaging` is new — a read of the cut so far and the tasks still outside
it, because a declaration hands back an id once and a planner resuming cold otherwise cannot
get back to it, and a package is referenced by id and never by name. It shares its query with
the finalization guard, so what the planner is shown and what the guard refuses on cannot
drift. `Task.source_ref` and `TaskGraph.unenumerated` became `RowRef`s on the way out, which
is what makes them arrive named rather than as bare addresses.

---

## F40 — The planning method never asks what the words mean

**Found:** 2026-07-22, building the glossary. Verified in the frozen plan: **zero**
occurrences of glossary, terminology, vocabulary or "term", and none of its 16 row types is
a term type.

**What is there.** Eight packages that interview for context, use cases, entities,
requirements, dependencies, architecture, contracts, red-team findings and decisions. Every
one of them produces prose, every row is named, and nothing anywhere asks the owner *what do
you call this, and what does that word mean here?*

**Why it matters more than it looks.** This build is the evidence, twice over. F27 is a
vocabulary declared binding and broken the next build package. F23 is a coverage check whose
denominator existed under two spellings, one of which was never defined. F24 is a relation
that existed under one name and not another. Three defects in one build, all of them the same
disease, in a plan whose method has no step where the disease could have been caught.

**The general form.** A planning method that elicits *claims* but never elicits the
*language the claims are written in* leaves every later reader to infer the vocabulary from
usage — which is exactly how one word ends up meaning two things. It is not a missing
contract or a missing trigger; those are the shapes the three pre-build checks look for. It
is a missing **interview question**, and nothing mechanical was ever going to find it. It was
found by having to build the fix for F27 and noticing there was nowhere in the plan to put
it.

**Fixed here** as DEVIATIONS.md D23: `terms`, a real table, with the vocabulary published as
a manifest, carried into briefs as a constraint, and scanned for at submission and at the
gate. The missing interview question itself is **not** written into a package script — that
is methodology, and methodology is vendored, never invented (`findings:4`). The tool now has
somewhere to put an answer; whether the standard package set learns to ask the question is
the owner's call.

---

## F41 — The tool's own output was not valid input to the tool

**Found:** 2026-07-22, by writing a test that read a ref out of one call's payload and passed
it to the next.

**What was there.** D19 forbids an address from leaving without the name of what it
addresses, so every ref this surface prints comes out as `the widget settles (requirements:1)`
— the display form, and the *only* form a caller ever sees. Every tool taking a ref parsed
the storage form, `requirements:1`, and nothing else. So a planner doing the obvious thing —
copying the ref it was just handed — got `MalformedCall: names_ref must be malformed ref`.

**Why it is the same defect as the gap key.** The door already learned this once: annotation
that replaced a string with an object broke `dismiss_gap`, because a value read out of a
payload has to be handable back. This is that rule broken from the other end — not by
changing a value's shape on the way out, but by refusing the shape we chose on the way back
in. The naming design made display form the only visible form and then left the front door
accepting only the invisible one.

**Why nothing saw it.** The door's scan is one-directional by construction: it reads outgoing
payloads and knows nothing about arguments. The tests that pass refs pass them as literals,
because a test author knows the storage form — the tests inherit the implementation's
knowledge, which is F22's lesson wearing a different hat. Only a test that *reads a ref out
of a payload* can fail on this, and none did.

**Fixed here.** `as_ref` accepts either form, taking the address out of the trailing
brackets. The rule to hold on to: **whatever the tool emits, the tool accepts.** Any
transformation applied on the way out is owed the inverse on the way in — and the way to find
the next one is to write the test that feeds output back in, rather than the test that knows
what the storage form looks like.

---

## F42 — The world-assumption gate criterion read a backing link nothing writes

**Found:** 2026-07-23, driving D16 — file a world-assumption, register a *real* spike against
it (`register_spike`, the contracted mechanism), and run the package-6 gate. The assumption
still read as unbacked.

**What was there.** `world_assumption_backed` (`_c_unbacked_assumption`) decided whether an
assumption was backed by querying the `links` table for a source row whose table was `spikes`
or `accepted_risks`:

```sql
SELECT source_ref FROM links WHERE target_ref = ?   -- the assumption
-- "backed" iff any source_ref starts with "spikes:" or "accepted_risks:"
```

But a registered spike does not live in `plan_rows` and is not a link. It is a row in the
dedicated `spikes` table, addressed by an integer `id`, carrying the assumption ref in its
`assumption` column — no `links` row is ever written. Likewise an owner-accepted risk is a
`findings` row in state `accepted_risk`, reached through `finding_refs`, not a link. **No live
code path writes the thing the criterion reads.** The one test that passed it,
`test_a_spike_backs_a_world_assumption`, fabricated a plan-row in a table literally named
`"spikes"` with a hand-made `LinkSpec` — a shape nothing in the system produces. So the gate
was green against a fiction and red against every real spike.

**Why it is the F30 class.** A reader with no matching writer — the mirror of the gate-history
bug, where three readers were promised a record `run_gate` never stored. Here the criterion is
the reader; the writer it imagines (something that links a `spikes:`/`accepted_risks:` plan-row
to the assumption) does not exist. It could not be caught by the pre-build checks: every
contract is well-formed and the gap is *between* the criterion's SQL and the spike store's
schema, which no state-machine or contract audit inspects. It took **driving the real
mechanism and reading the result**, exactly the case [[v2-build-conventions]] keeps logging.

**Fixed here (with D16).** The criterion now reads the real stores: an assumption is backed
iff its spike has a **recorded outcome** in the `spikes` table (`outcome IS NOT NULL` — the
experiment was actually run) *and*, because the only outcomes that leave an assumption open
are `inconclusive` and `blocked`, an **owner-accepted-risk finding** covers it. `confirmed`
and `refuted` close the assumption, so it never reaches the criterion. This is only coherent
*because* of D16's filing lock: every world-assumption is now born with a registered spike, so
"no spike at all" is unrepresentable and the criterion stops policing existence and starts
policing conclusion — the backstop with nothing to find, exactly as the D16 writeup intended.

---

## F43 — Methodology rev 2 was unloadable, and failed as if it were a bug

**Found:** 2026-07-22, as the tail of F31 — while fixing rev 3's stolen identity it became
clear that `load(2)` did not merely return the wrong thing, it could not run at all. Owner
decided the resolution 2026-07-23.

**The promise.** `requirements:71` ships the methodology as versioned content assets and
provides "an update path that migrates a plan from one methodology revision to the next."
Two revisions are installed. Read at face value, the requirement implies both are loadable —
otherwise there is no revision to migrate *from*.

**What was there instead.** `load()` reads `manifest["packages"]`, but `rev2/manifest.yaml`
heads its list with `stages:` — v1's word, because rev 2 is the PlanTool v1 methodology
vendored verbatim (decisions:61, the answer to findings:4). So `load(2)` raised a raw
`KeyError('packages')`: not "revision 2 is frozen," but the traceback of a dictionary lookup
that missed, indistinguishable from a bug in the loader. The scripts inside rev 2 also name
v1's retired tools (`submit_use_cases`, `record_decision`, `submit_contract_deps`), so even
past the manifest nothing could be authored under it through the v2 surface. The defect was
latent only because `DEFAULT_REVISION = 3` and no live path ever calls `load(2)`.

**The fork, and the owner's decision.** Two honest ways out. (a) Teach `load()` to accept
`stages:` as an alias for `packages:` — rev 2 stays byte-faithful and *loads*, but into a
revision whose scripts still name absent tools, so it loads into something nothing can author
under: half a bridge. (b) Declare rev 2 intentionally non-loadable provenance — the findings:4
red-team artifact and the source text rev 3 was derived from — make the refusal honest, and
state that `requirements:71`'s migration path is forward-only with rev 3 as the earliest
loadable baseline. The owner chose **(b)** (2026-07-23). The reasoning that decided it: the
real revision→revision *migration mechanism* is the revision-service at M7 (F20/F21 already
bind there), so at M6 the honest job is to make the engine's state *truthful* about what rev 2
is, not to manufacture a loadable-but-useless rev 2 that implies a migration nobody has built.

**Fixed here.** `EARLIEST_LOADABLE_REVISION = 3`; `load()` guards any earlier revision and
raises `RevisionNotLoadable` — a distinct type (subclass of `MethodologyUnavailable`) carrying
a message that names rev 3 as the baseline and the migration path as forward-only. The type is
the point: a raw `KeyError` implied a bug and a plain "could not be read" would imply
corruption, but rev 2 is neither broken nor missing — it is deliberately frozen, and now says
so, to code as well as to a reader. `guidance.py` lets `RevisionNotLoadable` cross its boundary
unchanged rather than relabel it `GuidanceUnreadable`, which frames things as an integrity
failure. **rev 2's content was not touched** — option (b) refuses to load it, it does not
rewrite it; a test asserts the manifest still says `stages:` and never `packages:`, so the next
hand cannot quietly turn this into option (a). See DEVIATIONS.md D24 for the requirements:71
narrowing this records.

**Class.** F17's shape — surface the truth, do not fake the capability — applied to a data
asset rather than a citation. The pre-build checks could not have caught it: the manifest is
well-formed YAML and the mismatch is between one key name and the loader's expectation, which
no contract or state-machine audit inspects. Like F31 it lived in vendored content and was
found by reasoning about the migration path, not by a green suite.


## F44 — A second finding on the same rows was silently swallowed as a retry

**Found:** while building the gate hard-lock (D15), 2026-07-23. Fixed as its own job on the
same day.

**The promise.** A finding attacks the specific rows it is filed against (requirements:31),
and a row can be wrong in more than one way — nothing says a row carries at most one finding.
So filing two different findings against the same rows must produce two findings.

**What was there instead.** `file_finding` built its idempotency key from the attacked refs
alone: `key("file_finding", ",".join(refs))`. Two findings on the same rows therefore spelled
the *same* key, so the second call took the replay path — it wrote nothing and returned the
first finding's id, reporting success. The caller who filed a genuinely new problem was handed
the old one back with no sign anything had gone wrong: the silent-success failure this engine
exists to refuse. It was latent only because no live path and no test ever filed two distinct
findings on one row-set; the idempotency key was checking whether two operations touched the
same rows, when the question it exists to answer is whether they are the same operation.

**Fixed here.** The key now carries the finding's own substance beside its refs — the content
fingerprint of the fields the caller sets (name, description, severity, resolve_by), reusing
`models.content_fingerprint`. A byte-identical re-file still replays, so a dropped network
reply cannot double a finding; any changed input files a distinct finding rather than having
the change swallowed by a replay of the old one. `created_at` stays out of the key, which is
the whole point of the idempotency module (F29). Driven end to end through the tool surface:
two distinct findings on one row both land, an identical re-file returns the first.

**Class.** The mirror of F29. F29 keyed on *too much* — a timestamp, never equal to itself, so
a repeat was never detected and the replay path was unreachable. This keyed on *too little* —
refs only, so two different operations collapsed into one. Both are the key answering the wrong
question, which is exactly what `engine/idempotency.py`'s docstring warns against: name what the
operation acts on, and where a caller legitimately repeats with no natural discriminator, give
it one that means something.

**Two siblings carried the identical shape, and the owner had them fixed in the same change.**
`conflicts.py`'s `raise_conflict` keyed on `key("conflict", refs)` and `validation.py`'s
`file_claim` on `key("file_claim", refs)` — the same collapse, because the same rows can
contradict on more than one axis and a single row can rest on more than one technical claim.
Both now carry the content fingerprint of their own caller-set fields beside the refs
(`{description, recommendation}` for a conflict, `{text, kind, red_flag}` for a claim), and both
have the same paired regression: two distinct filings on one row-set both land, a byte-identical
re-file replays. Owner's call (2026-07-23) was to fold them into this fix rather than leave two
known-identical latent defects standing — the DRY reflex the engine exists to enforce, applied
to the engine itself.

---

## F45 — The frozen plan never says what a staged/applied revision change concretely does to a row

**Status: RESOLVED at M7 (2026-07-23) by owner decision — recorded here because the build had to
stop and ask, which is exactly what this ledger counts.**

**Rows:** `contracts:57` (`adjudicate_repercussion` → `StagedChange`), `contracts:45`
(`apply_revision`), `requirements:52` ("update the affected rows with provenance"),
`OwnerDecision (accept|modify|defer, with the owner's words)`.

**Insufficient.** The revision contracts specify the *process* in detail — snapshot, walk the
repercussions, adjudicate each, apply or abandon — but never pin down the concrete mutation an
adjudication produces. `requirements:52` says "update the affected rows with provenance"; the
tool's only provenance-preserving update is supersession (`contracts:12`, `requirements:61`). But
three things are left unstated: (1) where the *new content* of a changed row comes from — an
`OwnerDecision` is described only as "accept|modify|defer, with the owner's words," which is prose,
not a row; (2) what "accept" and "defer" do to a row concretely; and (3) what "checked for
conflict" means for a tool that records judgment and never exercises it, so cannot semantically
detect a contradiction. None of the three pre-build checks can see this — every contract is
well-formed and every state-machine event has a firing contract; the gap is in what the write
*means*, one level below the contract surface.

**Resolved (owner's decision, 2026-07-23), as built.** A `modify` carries a full replacement
`RowSubmission` (so the existing supersession machinery applies); the tool checks the affected
row for an **open conflict** and, if none is shown, supersedes it on the live plan immediately
(D25); `accept` and `defer` change no rows (a recorded judgment); "checked for conflict" is the
structural open-conflict gate, not a semantic check. Abandon rewinds to the opening snapshot
(D26). Full reasoning in DEVIATIONS.md D25/D26.

**Class.** New: **a contract that specifies a process in full while leaving the semantics of its
central write unstated.** Unlike F30's "which contract writes this field?" (a missing writer) or
F23's missing denominator, here the writer exists and is named — `apply_revision` "commits the
staged change-set" — but what committing *does* to a row was never decided, and could not be
inferred from the contracts alone. Worth an audit question for any state-changing contract: **when
it says it "updates" or "applies", is the concrete effect on the stored record specified, or only
the fact that an effect happens?**
