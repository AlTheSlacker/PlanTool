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
