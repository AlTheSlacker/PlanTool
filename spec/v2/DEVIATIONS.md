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

## D7 — Gate warnings are scoped to the stage being gated

**Plan:** `requirements:21` — "WHEN a gate passes while open gaps or unresolved
assumptions exist, the system shall list each as an explicit warning."

**v2:** a gate *raises* warnings for open gaps in the stage being gated, plus the
stage-agnostic rules (open assumptions, reference coverage). Warnings already in the
ledger from earlier stages keep re-presenting until resolved or suppressed, so the
result of any gate still shows everything outstanding.

**Why:** the literal reading made the stage-1 gate report "No components yet" on a plan
five stages from needing components — ten noise warnings out of twelve. `gap_rules.yaml`
states the principle being violated: "a meter that cries wolf stops being read".
decisions:31's keep-pushing policy depends entirely on warnings being read.

See DEFECTS.md F10.
