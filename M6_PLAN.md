# M6 — Surface: design and build plan

Written 2026-07-21, after M5b merged (PR #8) and the M6a infrastructure branch.
**Self-sufficient after a context clear**: read `GLOSSARY.md`, then `M5_PLAN.md` §0 (the
outstanding-problem table, which governs every gate), then this.

Status: **not started.** M6a (`engine/clock.py`, timestamp vocabulary) is a precursor branch
and is not M6 itself.

---

## 1. What M6 builds

`V2_BUILD_PLAN.md` §7 — **Surface**. Three things:

| Component | Contracts |
|---|---|
| `session-service` (`components:14`) | `contracts:48` journal_note, `contracts:49` set_next_action, `contracts:64` plan_status |
| `mcp-surface` (`components:15`) | `contracts:50` dispatch, `contracts:51` append_log |
| Methodology **rev 3**, second half | the vendored package scripts still name v1's tool surface |

`mcp-surface` is the **only externally visible component** and must be strictly
protocol-clean: no engine-specific calls or configuration (`decisions:4`,
`requirements:74`). It sits on the service-layer seam D2 introduced, so MCP is the first
adapter rather than the only possible one — the GUI in M8 is the second.

**Run the three pre-build checks before writing code** (`M5_PLAN.md` §0). `session-service`
brings no state machine, so checks 1 and 2 are light; check 3 is the live one, because
`plan_status`'s digest is an accounting of what a resuming session is owed.

---

## 2. The M6 gate — seven open items, all hard-locking

Per the outstanding-problem rule, **M6 cannot pass while any of these is open.** Full table
in `M5_PLAN.md` §0; this is the working detail.

### 2.1 v1 foreign-key sweep — **DONE 2026-07-21, DEFECTS.md F28**
Swept. v1 declared **eight** mandatory non-`plan_id` relations; two were already repaired
(F20, F24) and **six were still missing** — `uc_steps`→`use_cases`,
`uc_extensions`→`uc_steps`, `crud_grid`→`entities`, `state_machines`→`entities`,
`sm_cells`→`state_machines`, `dep_failure_modes`→`dependencies`. All six are now one
`belongs_to` edge, declared in `rev3/manifest.yaml`'s `containment:` block (methodology data,
never engine knowledge) and enforced at submission. `EDGE_TYPES` closes the edge vocabulary,
which was open and defaulted, so a misspelled edge type used to produce a durable invisible
relation. `spikes` row-level provenance is the one remaining loss, bound to the **M7 gate**.

*Original statement of the item:*
F20 (`contract_deps`) and F24 (`contracts.component_id`) are two instances of the same loss:
v1 typed tables had real foreign keys, the package-6 flattening into generic
`plan_rows`/`links` preserved the rows and dropped the relations. Two instances make it a
characteristic risk of that architectural move. **Sweep every remaining v1 FK against v2
rather than finding a third by accident.** v1 lives at `archive/v1/` — its schema is the
checklist. Both known instances were repaired as *typed links*, not typed tables.

### 2.2 Methodology rev 3, second half
Rev 3 carries v2's vocabulary but still names v1's tool surface (`submit_use_cases`, …).
The assets are `engine/methodology/rev3/package1_context.md` … `package8_freeze.md`.
`engine/methodology/rev2/` is frozen v1 provenance and **must never be edited**.
Never invent methodology (`findings:4`, `decisions:61`) — it is vendored, and a component
that starts *generating* guidance instead of serving it has re-opened `findings:4`.

Two additions belong in rev 3 and are new scope, both from this session:
- a **packaging step** at the architecture package: D13 makes package membership mandatory
  and `finalize_plan` refuses an unpackaged task, so the script must lead the owner to a cut.
  The tool enforces the invariant; the methodology leads; the owner decides.
- an **obligation-enumeration step** at the contracts package: D12 freezes a contract's
  obligation surface at finalization, and if the script never asks for it, every sub-task
  arrives unenumerated and unsplittable.

### 2.3 F17 — prose row citations dangle on supersession
A row's prose cites `contracts:52`; that row is superseded by `contracts:63`; the prose is
frozen and now points at a dead ref. Generalised from the F15 false alarm. Note the shape:
the *plan* is a live-rows export, so superseded originals vanish while the prose that cites
them does not.

### 2.4 §4 Q1 — mandate and package script: by value or by reference? — **DECIDED 2026-07-22**
**By reference.** `plan_status` names the two documents and the calls that fetch them
(`get_mandate`, `get_package_script`); it never carries their text. The owner's reasoning
settles it: the documents need to reach a session *once*, and the only party who knows
whether they have already arrived is the caller. A session mid-package that calls
`plan_status` again gets a small answer because it does not ask for what it already holds.

Note what was wrong with the framing that produced this question. All three options
considered — by value, by reference, by value on the first call only — assumed the *tool*
had to decide when the documents were needed, and the third was an attempt to make the tool
remember who had called it. That is session state, which this build deliberately abolished.
The caller already has the knowledge; nothing needs remembering. Recorded as **D17**.

*Original statement of the item:* `requirements:10` says return them on session open. They
are the biggest single chunk of the digest and are bounded by methodology size, not plan
size. By value makes the digest permanently fat; by reference contradicts `requirements:10`'s
plain reading; first-call-by-value makes `plan_status` stateful within a session.

### 2.5 §4 Q2 — does the digest name what to fetch? — **DECIDED 2026-07-22**
**Yes, on both halves, and they are separate obligations.** Every count in the digest names
the call that retrieves what it stands for — a bare number invites a session to reason about
it ("only 3 warnings, that's fine") instead of reading it. And the digest closes by stating
the single next action in a sentence, because a resuming session handed a tidy summary and no
instruction invents a plausible next step rather than asking for one.

Both halves guard one failure: a session reads the digest, feels informed, fetches nothing,
and proceeds on a summary. That is F14's shape — a check that ran, passed, and meant nothing.
This is also `requirements:58` doing real work rather than being decorative. Recorded as
**D17** with Q1, since they are one decision about what a digest is for.

### 2.6 D9 — the hard-lock as a product requirement — **DECIDED 2026-07-21 as D15**
Settled: a gate locks on every open item **allocated to it**; `resolve_by` is required at
creation and `NOT NULL`; the two exits are resolve, or re-allocate to a later gate with a
reason. Gaps are outside the scheme — they are closable by the agent now, so deferring one is
procrastination. No infinite-deferral brake is needed: you cannot defer to a gate that does
not exist, so the worst case is a pile-up at freeze, which correctly refuses to freeze.
**D16** follows from the same session: assumptions are attacked on arrival, not audited at
package 6. Both are unbuilt. The original statement of the item follows.


Decided 2026-07-20; built here, in gate-engine. **The load-bearing work is drawing the
severity line, and it must stay narrow.** v2's gates warn, they don't block
(`decisions:31`, D7); the only hard block today is `requirements:32`. D9 generalises that to
every gate. Advisory warnings (open gaps, coverage) **stay non-blocking** or D9 resurrects
the cry-wolf failure D7 fixed. The lock class binds outstanding *findings*; whether it also
binds conflicts and open assumptions is the M6 decision.

### 2.7 Glossary delivery to the writer — F27
See §3. This is the newest item and the one with a full design already agreed.

---

## 3. Project glossaries — design agreed 2026-07-21, not yet built

**The problem.** F27: `GLOSSARY.md` was declared binding and the next build package broke
it. The cause is not carelessness and is worth restating because the design follows from it:
**the read-only exception is also the primary input.** Retired words legitimately survive in
`spec/v2/plan.md`, which is exactly the file read immediately before writing each function.
Ranked by proximity to the moment of typing, the exception beats the rule. And naming happens
at the point of *least* attention — the thinking goes into the algorithm, the name is
incidental typing.

**The frozen plan has nothing on this.** Verified: zero occurrences of glossary,
terminology, vocabulary or "term" in `spec/v2/plan.md`, and none of its 16 row types is a
term type. So this is a deviation, **and arguably a defect in the planning method** — the
eight packages interview for use cases, entities, contracts, decisions and failure modes and
never ask *what do you call things, and what do those words mean?* Log it when built.

### 3.1 A real table, not a row type (owner's decision, and he was right)

I argued for a `terms` row type in `plan_rows` on the strength of free supersession, links
and provenance. The owner's counter — he keeps his databases tightly typed — was correct for
two reasons I had missed:

1. **A term needs two distinct relations that the generic layer collapses into one.**
   *Redefinition* (same word, sharpened meaning) and *replacement* (this word is out, use
   that different one) are both `superseded_by` in `plan_rows`. One mechanism serving two
   relations is the same disease as two names for one thing, inverted.
2. **My own D12 reasoning contradicts the row-type position.** An accounting denominator must
   never be inferred from `plan_rows.content`, because it is free-form JSON with no per-table
   schema — that is why `obligations` is a real table. The banned-word list *is* a
   denominator: the export needs `ban_scope` as a queryable column.

**This also means `GLOSSARY.md`'s two-layer rule is mis-stated** and should be corrected when
this lands. It says planning layer = generic, execution layer = typed — but `obligations` is
enumerated by the planning session and is typed. The real line is **content vs structure**:
rows that *make a claim* about the domain are generic and interchangeable; things that
*constrain or organise other rows* get real tables. That accommodates packages, tasks,
subtasks, obligations and terms, and stops the argument recurring.

### 3.2 The table

```sql
CREATE TABLE terms (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    term          TEXT    NOT NULL,
    definition    TEXT    NOT NULL,
    names_ref     TEXT,                            -- the entity/row this word names, if any
    ban_scope     TEXT,                            -- null = live; prose | identifier | both
    ban_reason    TEXT,
    replaced_by   INTEGER REFERENCES terms (id),   -- retired: use this word instead
    superseded_by INTEGER REFERENCES terms (id),   -- redefined: same word, newer definition
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL
);
CREATE UNIQUE INDEX idx_terms_live ON terms (term) WHERE superseded_by IS NULL;
```

`ban_scope` is the distinction our own glossary needed and would otherwise have hidden in
JSON: `component` is banned in new prose but pervasive as `components:N`; `part` was banned
as an identifier.

**The trap, and it must be written into the deviation.** A banned term **must stay in live
reads**. v2 retirement drops a row out of live reads (settled 2026-07-20 for spike-refuted
assumptions); apply that naively to terms and the banned list goes *empty*, so the check runs,
finds nothing to ban and reports success — F23's missing denominator, inside the mechanism
built to prevent F27. Here a retired word is `ban_scope IS NOT NULL`, not a row that
disappears. Say so explicitly.

Scope: **plan-level only**, deliberately. A word meaning two things in two packages is the
failure being prevented, so no package-level override.

### 3.3 Delivery — three points, in descending order of what they actually achieve

1. **Export a machine-readable manifest** the project's own CI consumes. The tool publishes
   the vocabulary; the project polices itself. This respects `decisions:12` completely (no
   judgment exercised), works in any language, and is the mechanism proven on ourselves —
   `tests/test_vocabulary.py` found 20 violations a human sweep had declared clean.
2. **The glossary in the brief as a first-class section, outside the 100% accounting.**
   This attacks F27's actual cause. Candidate rows are *context* and may be waived with a
   reason; a glossary is a *constraint on the output* and cannot be, or it isn't a constraint.
   `compose_brief` currently treats every candidate as omittable — that is wrong for a
   glossary, and the distinction (context vs constraint) is one the frozen plan never makes.
3. **Warn at submission, count at the gate.** Lexical scan of submitted row content;
   warn-don't-block, because a retired word inside a quotation is legitimate and blocking
   resurrects the cry-wolf failure.

### 3.4 What none of this catches, stated so it is not oversold
Inventing a *new* name for a concept that already exists, where the two names share no
lexical structure. No mechanism without judgment can catch that. The gap engine can report
**words appearing in N submitted rows with no term row** — pure counting, the same shape as
M2's section coverage meter, no meaning inferred — which forces the moment where the owner is
asked to define it, and at that moment the existing term is in front of them. That converts
"you must notice" into "the tool asks", which is the move the whole product makes.

---

## 4. The naming-collision countermeasures (this build's own)

Three collisions in one session: `part`/`component` (F27), eight spellings of `created_at`,
and `_age` duplicated verbatim as `_age_seconds`. Built so far:

- `tests/test_vocabulary.py` — retired words as identifiers; parses the ban list out of
  `GLOSSARY.md` rather than copying it.
- `tests/test_schema_vocabulary.py` — closed vocabularies for column roles (`*_at` enumerated
  with meanings; `_id` integer, `_key` opaque string, `_ref` `table:ordinal`), and a
  `created_at` on every table with independent existence.
- `tests/test_clock.py` — one owner for timestamp creation *and* interpretation.

**Nothing further is proposed here, by the owner's decision of 2026-07-22.** A duplicate-body
detector was sketched in this section, as part of a wider idea that good coding practice should
be enforced by standing mechanical checks. That whole approach is withdrawn: it is a large
implementation topic in its own right, and carrying half-designed checks alongside the build
work confuses both. The three checks above exist because each one holds a specific, stated
invariant; that is the bar for adding a fourth, and no fourth is currently wanted.

The general principle, which is also §3's, still stands for *invariants*: **a rule stated in a
document is not a mechanism.** When this build writes a rule for itself, ask of it what we ask
of the frozen plan — *what fires this, and what fails when it is broken?*

---

## 5. Pre-build audit — session-service, 2026-07-22

Run before a line of `engine/sessions.py` was written. Checks 1 and 2 pass; check 3 found two
problems, and a fourth thing turned up that is not a check result at all.

**Check 1 — every state-machine event has a contract that fires it.** Nothing to check.
`session-service` brings no state machine: a journal note and a next-action checkpoint are
records, not entities with a lifecycle.

**Check 2 — every outcome the signature offers is reachable.** Passes. `StorageUnavailable`
on both writes is the ordinary storage failure. `plan_status`'s `NoPlanFound` is reachable —
a workspace with no plan row is the state `Storage.init_plan` exists to leave. `PlanCorrupt`
is reachable through `Storage.integrity_check`.

**Check 3a — "accumulated learnings" has no denominator, and it contradicts a requirement.**
`requirements:58` says resume presents "accumulated learnings". Journal notes accumulate for
the life of the plan and nothing ever removes one, so "accumulated" taken literally means the
digest grows without bound — which `requirements:62` forbids in the same breath, demanding
resume cost scale with the current working set rather than total plan size. The two rows
disagree and neither names the set.

Resolution, which the build must state rather than assume: **the digest carries the journal
notes of the current package by value, and one count of everything older, naming the call
that fetches it.** The denominator is named (notes belonging to the current package), sourced
(the package `gaps.current_package()` reports), and — unlike F26's brief — legitimately fixed
at read time, because a status view is a live reading of where the plan *is*, not a frozen
accounting of what was owed at a past moment. That distinction is worth keeping: F26's rule
is that an *accounting* must not float, not that nothing may be computed fresh.

**Check 3b — drift flags have no baseline for the whole of planning, and silence would lie.**
`requirements:73`'s workspace fingerprint is captured at finalization and at each brief issue,
and that is already built (`engine/tasks.py`). `plan_status` is called throughout the planning
interview, long before either occasion, so for that entire phase there is no baseline to
compare against. Returning an empty drift list there is exactly F14's shape: a check that ran,
found nothing, and meant nothing — and the reader cannot tell "the workspace has not changed"
from "nothing ever recorded what it looked like". **The digest must answer "no baseline
captured yet" as a distinct state**, not as an absence of flags.

**And one thing no check would have caught: `requirements:70` is moot.** It requires
checkpoint-class writes rejected under writer-lock contention to park in a spill journal and
reconcile on the next lock acquisition. There is no writer lock (D5), so there is no
contention, no rejection, and nothing to park; `findings:12`'s collision between zero-loss
checkpointing and single-writer rejection dissolved with the lock that caused it. D5 currently
names `requirements:67`/`68` as moot and should name `requirements:70` and `findings:12` too —
the M6b deletion swept the mechanism and left this consequence unstated.

`requirements:69` also lands here: a planner opening a network-mounted workspace is warned
that machine-crash durability is untested there. Detection is **lexical only** — a UNC path or
a mapped drive letter, read from the path string. The tool never probes the network.

**And one the audit did find, which no existing check would have: `contracts:64` consumes a
thing no contract produces.** Three rows promise **gate history** to a resuming planner
(`uc_steps:5`, `requirements:10`, `contracts:64`) and `run_gate` computed its verdict,
returned it and forgot it — no table, no column. Logged as **F30** and fixed here. The three
checks all inspect a contract against itself; this gap is *between* two well-formed contracts
and it has a direction, which is the question worth adding to the audit habit: **which
contract writes this field, and does its signature admit that it did?** It is the mirror of
M5a's schema-only fix, where a write path had no reader.

### 5.1 What the driver caught that the tests could not

Four things, on the first run, in the module the tests had just passed:

1. **The methodology reported itself as `plantool-rev2-2026-07-15` while the engine was
   loading `rev3/`.** `rev3/manifest.yaml` had been created by copying rev 2's, stamp and all.
   **F31.** A test *did* guard the stamp — and asserted the copied literal, so it passed while
   agreeing with the copy. A test that asserts a copied literal cannot detect that the literal
   was copied; the replacement asserts that revision N's stamp contains `revN`. It was visible
   only because the digest prints the stamp and a person read the line.

   While fixing it: **rev 2 is not loadable by this loader at all** — it is frozen v1
   provenance and still says `stages:` where the loader wants `packages:`. So
   `requirements:71`'s promised migration path *from one revision to the next* currently has
   exactly one loadable revision. Bound to the M6 gate alongside rev 3's outstanding half.
2. **`journal_note` keyed its idempotency on the count of existing notes**, which makes every
   call a new operation and the key incapable of detecting a repeat. That is **F29 exactly**,
   written by me the same afternoon as F29's own defect entry, in a module whose docstring
   cites F29. Knowing the rule is not the mechanism; the driver was.
3. **Gate history grew without bound in the digest** — two runs of package 1 printed two
   identical lines. The same missing-denominator question the audit asked about the journal,
   which I answered for the journal and did not think to ask again about the neighbouring
   field. Now: newest verdict per package by value, the rest as a count naming `gate_runs()`.
4. **"1 active warnings", and "1 engineer's mandate — get_mandate() to read them".** Forcing
   a reference through a type built for counts produced nonsense at the one place the digest
   is actually read.

Item 2 is the one to remember. The rule was fully in mind, cited in the file, and broken
anyway, at the point of least attention — which is the same sentence F27 and F29 both end on.

---

## 6. How to run things

Tests: `.venv\Scripts\python.exe -m pytest -q` from repo root (288 passing at M6a; ~2 min,
so run it in the background).

Driver scripts: scratchpad `.py` files, run with
`$env:PYTHONIOENCODING='utf-8'; $env:PYTHONPATH='D:\PythonProjects\PlanTool'; & .venv\Scripts\python.exe <path>`.

**Drive the engine end-to-end after each build package and read the output.** Branch + PR;
the owner merges; no self-merges.
