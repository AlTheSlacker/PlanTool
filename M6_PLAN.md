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

## 2. The M6 gate — nine open items, all hard-locking

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
See §3.

### 2.8 Every row has a name — added 2026-07-22
See §6. The item that changes the most: it puts a required field on `submit_rows`, a migration
on every existing row, and a question in the interview scripts.

### 2.9 The digest names calls the surface cannot reach — added 2026-07-22
See §7.4. Found by the surface's pre-build audit; three decisions are needed before the surface
can be built at all (§7.5).

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

**A prose check was proposed and refused, 2026-07-22 — second instance of the same ruling.**
`component` is retired *in prose* and nothing checks prose: the existing check bans retired
words as **identifiers**, so the one retirement whose scope is prose-only is the one with no
mechanism. It shows: `GLOSSARY.md` uses `component` twice in live prose two lines below the row
retiring it, and I used it again in conversation the next day. A markdown scanner was proposed
and declined — prose bans wait for `ban_scope` (§3.2) with the rest of F27, rather than adding a
fourth standing check whose exclusion rule (retirement table, quoted frozen plan) would have
been designed while writing it. **When `ban_scope` lands, its first run is over our own five
writable documents** — roughly 26 uses of `component`, only 7 of them `components:N` refs. Do
not sweep by hand first; a hand sweep is what §3 says cannot be trusted — the rule that is not a mechanism.

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

## 6. Every row has a name — design agreed 2026-07-22, not yet built

**The owner's requirement, in his words: nothing this tool says to a reader should make them
look something up.** Raised after a session in which almost every sentence I wrote to him was
made of bare addresses — `contracts:50`, `F30`, `D17`, `M6b` — and he could not read any of
them without going and fetching something. This is not a style complaint about me. **Every
plan built with this tool inherits it**, because the tool's own output is made of the same
material, and it is served to whatever engine is on the other end as well as to a person.

### 6.1 The rule

1. **Every addressable thing carries a meaningful name, supplied at creation.** Plan rows,
   packages, tasks, sub-tasks, obligations, terms — and our own defect and deviation entries.
2. **A name is unique among live rows in its table.** A duplicate is refused.
3. **A name does not survive a change of meaning.** When a write changes a row's content, the
   name must be supplied again — re-affirmed deliberately, or replaced.
4. **The tool never emits an address without the name of what it addresses.** The address
   becomes optional detail; the name carries the sentence.

### 6.2 Why it is a product requirement and not a preference

A reference is an address, not a name, and an address alone forces a lookup. Both kinds of
reader fail on it, differently and badly. A person does not do the lookup — they nod along and
act on a sentence they did not understand. A model does something worse: handed an address with
no name, it will produce a confident, plausible account of what lives there without ever
fetching it, because a plausible continuation is always available.

**The owner already made this ruling once, narrowly, and it wants to be general.** D17 settled
that every count in the status digest must name the call that fetches what it counts, on the
grounds that a bare number invites a reader to reason about the number instead of reading the
thing. A bare address is that same failure with the same cause. This section is that decision
applied to the whole surface rather than to one digest.

### 6.3 What blocks it today, and the honest cost

**`plan_rows` has no name.** The column list is `table_name`, `ordinal`, `content` (free-form
JSON), provenance, state, lineage and timestamps — and `submit_rows` (`contracts:9`) validates
content only as "a non-empty object". So the tool cannot render a name for any row, because no
row has one.

**Deriving one from `content` is refused**, and by an argument this build has already accepted:
D12 established that an accounting denominator must never be inferred from `plan_rows.content`
because it is free-form JSON with no per-table schema — which is why `obligations` is a real
table. A display name is the same case. A truncated first sentence is not a name, and inference
here is the same disease in a new place.

So: **`plan_rows.name TEXT NOT NULL`**, and the same on the typed tables. The costs, stated
plainly because they are real:

- `submit_rows` gains a required field, and rejects a submission without one, pedagogically.
- Every existing row needs a name — a migration, and for the dogfood plan a real content job.
- The interview scripts must ask for the name **as a question**, not collect it as a field.
- Our own defect and deviation registers need naming: a few dozen entries, bounded.

Two things it pays for beyond this rule. The glossary work (§3) needs exactly this material —
its "words appearing in N rows with no term row" meter has nothing to count without names. And
F17, where frozen prose cites a row that later gets superseded, is softened: a citation that
carries the name still communicates after the address dies, instead of dangling silently.

### 6.4 Presence is mechanical; meaning is not

A `NOT NULL` column guarantees a name exists. It does not guarantee the name means anything,
and what it will produce by default is `logging requirement` and `handle the error case`.
**Naming happens at the point of least attention** — the thinking goes into the content and the
name is incidental typing, which is the sentence F27, F29 and F31 all end on. So the column is
necessary and not sufficient, and the interview carries the other half: it asks for the name as
its own question, at the moment the author still knows what the thing is.

### 6.5 Uniqueness is the part that makes it a mechanism

A unique index on live rows turns a convention into something that fires. **Two rows arriving
with the same name is a signal every time** — either the same thing has been filed twice, or
there are two things and nobody has distinguished them. That is the naming collision this
build has hit three times (`part`/`component`, eight spellings of `created_at`, `_age`
duplicated as `_age_seconds`), caught at the moment of typing instead of a week later. No
judgment is exercised, so `decisions:12` is respected.

Block within a table; warn across tables, where the same word legitimately names a requirement
and the entity it constrains. Superseded rows are not live, so a replacement may reuse its
original's name — which is the *redefinition* case, and correctly distinguished from
*replacement* by whether the name changed. That is the same two-relations distinction the
`terms` design (§3.1) was built around, arriving again in the general layer.

### 6.6 Staleness — a name is only valid against the content it was given for

The owner's point, and it would have eaten this design a month after it landed: **a name that
was accurate when written quietly stops being true when the content moves.**

The mechanism is already in the codebase to borrow — `engine/references.py` hashes content for
the verified-quote design. A row stores its name **and the fingerprint of the content it was
named for**. When a write changes the content, the fingerprint no longer matches and the name
is not carried forward silently: it must be supplied again. **Passing the same name a second
time is a deliberate act; silence is not.**

It bites at the two writes where meaning can actually change:

- `resolve_assumption` (`contracts:11`) upgrades a row **in place**, and a `revise` changes
  what the row says while leaving it live under its existing name. That is the one case that
  demands a name. **Narrowed during the build, 2026-07-22:** this section first said `revise`
  *or* `reject`, and `reject` was wrong — it retires the row, which takes it out of live reads
  altogether, so naming what a departing row now says buys nothing. A `confirm` records that
  the owner agreed and changes no meaning. Demanding a re-name in either case would be
  friction that teaches callers to click through, which is how a check stops being read.
  **The resolution is already a parameter of the call, so nothing is inferred.**
- `supersede_row` (`contracts:12`) creates a replacement, which is a new row and must be named
  like any other.

**The honest limit:** a fingerprint proves the content changed, not that the change made the
name wrong. What it buys is the *moment of attention* — the tool asks at the instant the author
has both the old name and the new content in front of them. That is the move the whole product
makes: "you must notice" becomes "the tool asks".

### 6.7 The output rule, and where it is enforced

**The surface is the single door.** `mcp-surface` (`components:15`) is the only externally
visible task, so every byte reaching any planner passes one choke point. That is why this rule
belongs in this build package and not later.

Two layers, and the second is the one that holds:

1. **Storage form and display form become different types.** `RowRef` is the storage form —
   `str(ref)` produces `table:ordinal` and that is correct for the `links`, `supersedes` and
   `superseded_by` columns, which must not change. But a `RowRef` may never appear in a
   returned payload. Anything outbound carries a display value that **cannot be constructed
   without a name**. The code path that emits a bare address stops existing.
2. **A scan at the door.** Every string in an outgoing payload is checked for address syntax; a
   bare one fails the call, loudly. This is the backstop for hand-assembled message strings,
   which the type system cannot see — and hand-assembled strings are exactly where the digest's
   "1 engineer's mandate — get_mandate() to read them" nonsense came from.

Applying check 3 to this design itself: **the set** is every address-shaped token in an
outgoing payload; **its source** is the payload being returned; **it is fixed** per call, at
the moment of dispatch. Nothing is re-derived later against a moved target.

### 6.8 The one exemption: verbatim frozen content

A brief serves stored row prose **verbatim**, and that prose may cite addresses. The tool must
not rewrite it — frozen content that gets edited in flight is a far worse defect than a
lookup. So quoted content is exempt from rewriting, and the tool **annotates alongside**: when
it serves prose containing addresses, it appends the resolution of each one, naming the row.
Verbatim service is preserved and the lookup is still removed.

This is also where F17 becomes visible rather than silent: an address in frozen prose with no
live row resolves to "no live row at this address", instead of dangling unnoticed.

### 6.9 Compactness — the one real tension, and why it resolves

`requirements:62` requires resume cost to scale with the working set, and names cost bytes.
It resolves if we stay strict about what is rendered: **a name is short — a word or a short
phrase — and it is the row's *content* that is long.** Render the name, never the content. The
digest keeps both promises at once.

### 6.9a Found by driving it: errors were citing our own build documents

The first end-to-end run printed, to a planner using the tool, *"…the address rides alongside
it (M6_PLAN.md §6)"*. A planner has no copy of `M6_PLAN.md`. That is this section's own
failure — pointing the reader at something they cannot reach — committed inside the fix for
it, and it was visible only because a person read the driver output rather than a test.

Stripped from the three new messages. **Two pre-existing instances remain** and belong with
clause 4's work, since the outgoing scan needs a policy on them anyway: `rows.py`'s containment
rejection cites `DEFECTS.md F28`, and `tasks.py`'s draft-brief refusal cites `DEFECTS.md F21`.
The rule to settle there: internal build documents may be cited in code comments and
docstrings, which we read, and never in a message the tool hands out.

### 6.10 What this does not catch, stated so it is not oversold

- **A name that is present, unique, fresh and useless.** `misc`, `thing`, `the main one`. No
  mechanism without judgment catches a bad name; §6.4's interview question is the mitigation.
- **Addresses the owner writes into content he submits.** That is input, and input is the
  owner's words. Warn at submission and count at the gate — the same policy as §3.3 — never
  block, because a retired address inside a quotation is legitimate.
- **Prose that is hard to read for reasons other than addresses.**

### 6.11 Binding

The frozen plan says nothing about names, so this is a **deviation and a new requirement**, to
be logged when built. Bound to the **M6 gate** under the outstanding-problem rule — not
floating, because the surface that enforces it is being built now.

---

## 7. Pre-build audit — mcp-surface, 2026-07-22

Run before a line of the surface was written. Check 1 is empty, check 2 found one dead outcome
and three dead tools, check 3 produced a denominator worth building a test around — and then a
fourth thing turned up that none of the three checks was looking for.

### 7.1 Check 1 — every state-machine event has a contract that fires it

Nothing to check. The surface brings no state machine: `dispatch` (`contracts:50`) is a router
and `append_log` (`contracts:51`) is append-only. Neither is an entity with a lifecycle.

### 7.2 Check 2 — every outcome the signature offers is reachable

`UnknownTool` and `MalformedCall` on dispatch, and `LogWriteError` on the log, are all
reachable. One is not:

**`NotWriter` cannot occur.** Dispatch declares it as "a write tool was invoked without holding
the writer lease". There is no writer lease — the lock was removed entirely (D5, superseded
2026-07-22, on the grounds that the owner plans in one session and the lock guarded a situation
that cannot arise). The outcome must be **declared moot, not implemented**. This is the same
class as `requirements:70` and `findings:12`, which the session-service audit found moot the
same day for the same reason: the M6b deletion swept the mechanism and kept leaving consequences
unstated in its neighbours. **D5 should name `contracts:50`'s `NotWriter` alongside them.**

**And the surface's own tool list carries three dead entries.** `renew_lease`
(`contracts:53`), `release_writer_lock` (`contracts:54`) and `acquire_writer_lock`
(`contracts:63`) each declare `consumed by: components:15` and are deliberately not
implemented. They must be **declared exclusions with reasons**, not quietly absent — otherwise
§7.3's denominator reports a permanent false shortfall, and a real omission hides inside a gap
everyone has learned to ignore.

### 7.3 Check 3 — what does "wrapping every service contract" count?

The surface's stated responsibility is "an engine-agnostic MCP stdio toolset wrapping **every**
service contract". That is an accounting claim, so it gets the three questions:

- **The set:** every contract declaring `consumed by: components:15` in the frozen plan —
  **39** of them, spanning eleven owning tasks.
- **Its source:** the frozen plan, extracted mechanically. **Not** a hand-kept list inside the
  surface module, which rots the first time someone adds a contract and forgets, and reports
  success while doing it.
- **When it is fixed:** permanently. The plan is frozen, so unlike F26's brief there is no
  moving target.
- **Less a declared exclusion list, each entry carrying its reason** — today the three
  writer-lock calls above, leaving **36 tools required**.

So the registry check is a test that parses the frozen plan and compares. That test is the
mechanism; "we wrapped everything" in a docstring is not.

### 7.4 The finding no check was looking for: the digest names calls the surface cannot reach

`plan_status` tells a resuming planner what to fetch — D17's ruling, and a good one. Of the six
calls it names, **one is reachable through the surface.**

| The digest says to call | In the frozen plan | Exposed? |
|---|---|---|
| `next_gaps()` | `contracts:19` | **yes** |
| `get_mandate()` | `contracts:17` | no — consumed by `components:14` only |
| `get_package_script(N)` | `contracts:65` (`get_stage_script`, renamed for the `stage`→`package` retirement) | no — consumed by `components:14` only |
| `active_warnings()` | `contracts:23` | no — consumed by `components:14`, `11`, `13` |
| `journal()` | **not a contract** | our own addition, M6 session-service |
| `gate_runs()` | **not a contract** | our own addition, the gate-history fix (F30) |

So a cold planner is handed a digest that closes by instructing it to make calls it has no way
to make, and two of those calls exist nowhere in the specification at all.

**Why nothing caught it.** This is **F30's exact shape one level up**: every contract is
well-formed in isolation, and the gap runs *between* two of them with a direction. F30 added
the question *which contract writes this field, and does its signature admit that it did?* This
finding names its mirror: **which contract can the reader actually call, and does the thing
telling them to call it know?**

**And D17 created it, yesterday.** Ruling that the digest names calls instead of carrying text
was right, and it moved the entire burden onto a surface that did not exist yet — after which
nobody re-checked that surface's denominator against the new obligation. Worth stating
generally, because it will happen again: **a decision that is correct in itself can still put a
defect into a neighbour, and the neighbour is where to look the moment a decision changes who
does the work.**

**A seventh instance, independent of the digest.** `compose_brief` (`contracts:68`) is declared
consumed by `contracts:55` alone, yet the plan's own text says composing a brief is "a separate
second call" made by the planning session — which reaches the tool only through the surface.
Either the consumed-by declaration is wrong or the prose is. Owner's call.

### 7.5 What must be decided before the surface is built

1. **Are the mandate, the package script and the active warnings exposed as tools?** My
   recommendation is yes. The alternative — rewriting the digest so it only names what happens
   to be exposed — lets the specification's consumed-by declarations decide what a planner is
   allowed to know, which is backwards. Exposing them widens the surface beyond the frozen
   plan's declarations and is therefore a deviation, logged as one.
2. **`journal()` and `gate_runs()` need contract status.** They are ours, they are named in
   output, and they are specified nowhere. Deviation entries with contracts of their own.
3. **`compose_brief`** — resolve the contradiction in §7.4.

### 7.6 The mechanism that stops it recurring

The denominator in §7.3 should have a second half: **every call named in any tool output must
be exposed by the surface.** Output is scanned for call names, each is resolved against the
registry, and an unresolvable one fails. That is cheap, exercises no judgment, and it is the
same door-scan §6.7 already installs for addresses — one pass, two invariants, because they are
the same invariant: **the tool never points a reader at something the reader cannot get to.**

---

## 8. How to run things

Tests: `.venv\Scripts\python.exe -m pytest -q` from repo root (288 passing at M6a; ~2 min,
so run it in the background).

Driver scripts: scratchpad `.py` files, run with
`$env:PYTHONIOENCODING='utf-8'; $env:PYTHONPATH='D:\PythonProjects\PlanTool'; & .venv\Scripts\python.exe <path>`.

**Drive the engine end-to-end after each build package and read the output.** Branch + PR;
the owner merges; no self-merges.
