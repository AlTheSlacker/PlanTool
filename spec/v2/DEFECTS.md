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

**Status: OPEN. Resolve-by gate: M6 (surface).** Chosen because the fix is a read-time
concern — how a row's text is served, and how an unresolvable prose ref is surfaced — and
M6 is where `plan_status` and the MCP surface are built. It does not block M5.

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

**Status: OPEN. Resolve-by gate: M7 (`revision-service`).** Bound there because the only
reading under which the flag becomes reachable is the revision case, which is M7's subject.
M5a ships the honest error instead of a silent empty result.

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

**Exactly one exception survives** (`writer_lease.session_id`, exempted by the rule's own
text). Two more were proposed on the day and the owner refused both, which is the part worth
remembering:

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
