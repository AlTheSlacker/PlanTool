# Deviations from the frozen plan

The plan at `plan.md` is FROZEN (version 2, 2026-07-17) and cannot be amended. Every
place where the v2 build departs from it is recorded here, so plan and build never
silently disagree.

Format: what the plan says · what v2 does · why.

---

## D1 — Execution layer deferred

**Plan:** `decisions:50` specifies fifteen components in four layers, the execution
layer being `task-graph` (`components:11`), `brief-composer` (`components:12`) and
`revision-service` (`components:13`).

**v2:** `task-graph` and `brief-composer` are not built. `revision-service` is built in
reduced form — the change-order loop (snapshot, version bump, impact walkthrough,
per-item adjudication, atomic apply or clean rollback) is in scope; its execution-coupled
clauses are not:

- freezing in-flight sub-tasks (`open_revision`)
- regenerating affected briefs (`adjudicate_repercussion`)
- flagging already-built work as needing rework at apply time (`adjudicate_repercussion`)

**Why:** owner decision, 2026-07-20. v2 is an improvement of v1's plan-authoring loop,
not an extension into driving execution. The execution module is to be designed in its
own right, and `task-graph` in particular needs a design discussion that has not happened.

`task-graph` and `brief-composer` defer together because they cannot be separated:
`compose_brief(subtask_id, selection)` has no input without a graph producing sub-task
ids, and `next_subtask` exists to feed it.

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
