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
