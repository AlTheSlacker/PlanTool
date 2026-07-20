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
dimensions in prose — "by ids | table | stage | provenance | liveness |
link-neighborhood; paginated" — but no row anywhere defines their fields, so two
implementers would produce two incompatible interfaces.

**Needed:** field-level definitions, or an explicit statement that shapes are the
implementer's choice.

**Resolved:** invented in `engine/models.py` and `engine/storage.py`, following the
prose closely where it exists.

**Class:** the domain model (Stage 4) covers *entities* thoroughly but not the
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

## F7 — Nothing defines the current stage

**Rows:** `contracts:19` (`next_gaps`), `requirements:12`, `entities:1`.

**Insufficient:** `next_gaps` returns gaps for "the current stage" and requirements:12
recommends the gate "while the current stage has no open gaps", but nothing in the plan
says how the current stage is determined. `entities:1` carries stage on the Plan and
`crud_grid:3` says "System: stage advances" without stating the advance condition —
whether it is gate-pass, owner instruction, or derived from content.

**Needed:** a stated rule for what the current stage is and when it advances.

**Resolved:** invented — the lowest stage with any open gap, else the highest stage. This
is a guess. It happens to make submits-for-any-stage work naturally (v1's stated
behaviour: "submits for any stage are always accepted; next_gap prefers stage order but
follows the conversation"), but the plan does not say so.

**Class:** same family as F2 and F4 — behaviour named in prose without the mechanism that
produces it. Third instance, which strengthens the case for the gate rule proposed in F4.

---

## F8 — Gate criteria exist only as v1 code

**Rows:** `contracts:22` (`run_gate`), `requirements:20`, `requirements:71`.

**Insufficient:** `run_gate` returns "row-level holes (each naming table, row, problem,
and fix)" and `requirements:20` says gates evaluate "only mechanical criteria" — but no
row anywhere in the frozen plan states what any stage's criteria *are*. The plan
specifies the shape of the answer and never the question. `requirements:71` does require
the criteria to ship as a versioned content asset, which at least says where they live.

**Needed:** the per-stage criteria themselves, as content.

**Resolved:** vendored, not invented — `engine/methodology/rev2/gate_criteria.yaml`
transcribes v1's `archive/v1/engine/gates.py` into declarative rules, per `decisions:61`
and `findings:4`. v1 wrote one hand-coded SQL function per stage; the v2 asset expresses
the same criteria as nine declarative types the gate-engine interprets.

**Class:** distinct from F2/F4/F7 — this is not a missing mechanism but missing
*content*, and the plan knew it (requirements:71 exists precisely because the
methodology is the product's IP). Worth noting that the vendoring instruction is what
made this recoverable: without decisions:61 an executor would have invented eight stages
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
open gap in the plan. Built that way, the stage-1 gate of a four-row plan reported
twelve warnings, ten of which said things like "No components yet" — true, and useless,
because the plan was five stages away from needing components.

**Needed:** the scope of "each" — plan-wide, or the stage being gated.

**Resolved:** invented — raising is scoped to the gated stage plus the stage-agnostic
rules (assumptions, reference coverage). Warnings raised at their own stage persist in
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

## F11 — The vendored gap rules and gate criteria disagree about stage 1

**Rows:** `requirements:71`, `decisions:61`; assets `gap_rules.yaml` (M2) and
`gate_criteria.yaml` (M3).

**Insufficient:** not the frozen plan this time — the *vendored methodology*. v1 recorded
goals, non-goals and target stack as `decisions` rows distinguished by a text prefix
("Goal:", "Non-goal:", "Stack:"), a convention its gate SQL matched with `LIKE 'goal:%'`.
v2's generic PlanRow store makes separate tables the natural encoding, and M2's
`gap_rules.yaml` had already half-adopted it (`goal_without_success_criteria` reads a
`goals` table) while `stage1_not_started` still tested `decisions` for emptiness. The two
assets therefore disagreed about what stage 1 even fills.

**Consequence:** a complete, passing stage 1 was permanently accompanied by the warning
"Nothing recorded yet. Open the stage-1 interview."

**Resolved:** `stage1_not_started` now tests `goals`. Recorded here rather than silently
fixed because it is evidence about the *revision* path requirements:71 mandates: a
methodology revision that changes how content is encoded has to be applied to every
asset at once, and nothing checks that. M5 introduces rev 3 and will hit this again.

**Discovered by:** the end-to-end drive, third time. The unit tests could not catch it —
`tests/test_gaps.py` was written against `decisions` at M2 and so encoded the same
disagreement, and it passed.

**Class:** a cross-asset consistency hole. Worth a gate criterion in a future revision:
*every table named in one methodology asset is named in the others that cover the same
stage.*
