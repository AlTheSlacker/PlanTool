# Change 3 — the catalogue

**Specification, first draft. All five packets have been cold-read; the corrections are NOT yet
applied.** §11 holds what the four readers found and the worklist that follows from it. **Read §11
before §3–§8** — several numbers and at least four design decisions below are known wrong, and §11
says which. Third of the ten changes in `PLAN.md` §4. It
is early because two later changes depend on it: brief composition serves the catalogue entries
a task may call, and the cold read cannot tell "this decision is unanswered" from "this decision
is answered somewhere I cannot see" without being told what the task may call.

Depends on changes 1 and 2 — schema version 9 is its starting point, `tasks` is the build unit
and the name of what a builder is handed, `component` is a live word, and the justification
vocabulary check from 2E.1 is in force and will refuse two of this change's columns until they
are declared.

**This change closes three questions the original design left open and contradicts it in two
places, each with the measurement that forced it.** §2 lists what it inherits and what it does
not; §3 argues each departure.

---

## 1. What this change does

D10 in one sentence: **a catalogue of every object, method and function the plan intends to
exist**, each with one owner and a statement of the concept it owns, so that duplicated and
hard-to-maintain code is caught in the plan rather than in the tree.

The defect it answers is measured in this repo's own history: three naming collisions landed in
a single sitting, and a helper was duplicated verbatim under a slightly longer name. Neither was
carelessness. The code that would have prevented them was not visible at the moment of writing,
because the codebase had outgrown the window — and that condition gets worse, not better, as a
project grows.

**The design is not new and this document does not re-derive it.** `FUNCTION_CATALOGUE.md`
(2026-07-22) is the source and is complete; `CATALOGUE.md` records the name decision and settles
two of its three open questions. What is new here is the specification: the schema, the calls,
the refusals, and the five places where building it against the real code showed the design was
wrong or silent.

## 2. What is inherited, and what this change changes

**Inherited unchanged, and not re-argued:**

- Approval and registration are a single act, so there is no state in which a function has been
  agreed and is not in the table.
- The search reads in both directions — a close description under a different name is
  duplication; a close name with a different description is a naming collision.
- Overlap is recorded as a relationship, not a percentage, because overlap is asymmetric.
- The negatives are recorded too, or the next planner runs the same search and decides again.
- Dead entries stay, are never offered as candidates, and are still consulted for the name
  check, because the thing about to be written may have been removed on purpose.
- Trivial members — a function that only reads or writes a field, with no logic — stay out. The
  rule is about behaviour and never about name prefixes.
- The purpose line is a constrained shape: verb, object, qualifier. It carries the whole weight
  of the search, because inputs and outputs were rejected as a matching basis.
- The cross-container report ranks and never fires. A threshold is a judgment written as
  arithmetic so review cannot see it.

**Changed here, each argued in §3:**

| | what the design said | what this change says | §  |
|---|---|---|---|
| 1 | *(unstated)* | It is a real table, not a plan-row type | 3.1 |
| 2 | Two kinds of entry, public and private | Two axes: object or function, public or private | 3.2 |
| 3 | Identity is name and container | …and the obvious index for it does not work | 3.3 |
| 4 | The death commit is the only field deciding liveness | `retired_at` decides it; the commit is evidence | 3.4 |
| 5 | Near matches are **each** dismissed with a written reason | The highest-ranked one is; the rest are shown | 3.5 |
| 6 | Four relationships | Five — the asymmetry argument demands the fifth | 3.6 |
| 7 | 464 entries: 255 public, 209 private | **431**: 255 public, 176 private | 3.2 |

## 3. The design questions, answered

### 3.1 A real table, not a plan-row type

**A real table**, the same call the glossary made and for two of the same reasons, which are
quoted here rather than restated because the argument is already in the schema.

`engine/schema.py` on `terms`: *"D12 settled that an accounting denominator may never be
inferred from `content`, which is free-form JSON with no per-table schema."* The catalogue is an
accounting in three directions at once — the search's denominator, the cross-container report's
grouping, and (from change 5) the count of pseudocode calls with no entry. `container`,
`visibility` and `retired_at` all have to be columns something can query.

**And the identity does not fit.** `plan_rows` enforces one live row per `(table_name, name)`.
A catalogue identity is `(name, container)`: `_hydrate` is a legitimate method name on several
services, and under `plan_rows`' index the second one would be refused as a duplicate. The index
that makes naming a mechanism for plan rows is the wrong index for this table.

**Rejected: a qualified name** — `RowService._hydrate` as the plan row's `name` — which would
make `plan_rows`' existing index give exactly the right uniqueness. It fails on the report:
grouping by container means splitting a string, and a string that is parsed to find a relation is
a relation the schema does not have. §3.3's measurement is what settles it.

**What this costs, stated because it is the standing argument for the generic layer.** A
catalogue entry gets no provenance, no supersession lineage, no typed links and no `grounds`
from change 2. Three of the four are not wanted: §3.4 replaces supersession with retirement,
§3.6 gives the entry's argument its own table with a richer shape than free text, and an entry
links to exactly one owner, which is a column. The fourth — provenance — is a real loss, and it
is the smallest of the four: an entry is written by a planning session at stage 8, so
`DECIDED` would be its value every time.

### 3.2 What an entry is, and the number that was wrong

**D10 and `CATALOGUE.md` disagree, and D10 is right.** D10 catalogues "every object, method and
function"; `CATALOGUE.md` §3 settles granularity as "exactly two kinds of entry — public and
private" and objects fall out of the document without a word. They are two different
distinctions and the second one silently ate the first.

**There are two axes and this change keeps both.**

- **`kind`** — `object` or `function`. A method is a function with a container; that is what
  lets the procedural and object cases share one record shape.
- **`visibility`** — `public` or `private`. For a function this is `CATALOGUE.md`'s settlement
  exactly: public is a task's entry point, exactly one per task, and the only thing another
  task's pseudocode may call. For an object it is the same question one level up.

**Objects are the half that catches things, measured.** v2's engine holds **204 classes**, and
**six class names are defined in two modules each**: `RefNotFound`, `PlanUnreadable`,
`InvalidTransition`, `UnknownPackage`, `AlreadyResolved` and `Package`. Five of the six are
error types, which are the names contracts cite, and a reader who imports the wrong
`RefNotFound` writes an `except` clause that never fires. Catalogue objects and the sixth
registration of each is refused at the moment of typing. Leave them out and the container is
free text, which can be misspelt, and a misspelt container silently splits the search — the
disease this table exists to treat.

**An object's owner is a component, not a task, and D10 is wrong about this too.** D10 says
"each entry has one owning task". A service class carries the entry points of twenty tasks, so
no task owns it. Its owner is the **component**, which is the level directly above and the
reason D16's un-retirement of the word earns its keep. So: a function entry carries `task_id`, an
object entry carries `component_ref`, and exactly one of the two is set.

**Modules are not catalogued.** A module is a location, and `FUNCTION_CATALOGUE.md` §3 is
explicit that location is not identity: *"if a row is identified by location, reorganising files
reads as deletion plus addition and destroys the history the catalogue is accumulating."* So a
module-level function has no container. §3.3 is what makes that safe.

**The size check, recounted, because the figure in `CATALOGUE.md` is wrong.** It says 464
entries — 255 public, 209 private. Parsed from v2's engine: **464 is the total including 33
dunder methods**, which the trivial-member exclusion removes before anything is registered.
After the exclusion the catalogue is **431 function entries — 255 public, 176 private** — plus
204 objects. 255 public is right and is the same 255 that sizes the whole of v3's detailed
design, so the number everything else rests on survives; it was the private half that was
counted before the rule was applied. 431 and 176 are upper bounds: the exclusion is broader than
dunders and also removes accessors and one-line wrappers, which are not mechanically countable
from a parse.

### 3.3 Identity, and the index that silently does not work

Identity is `(name, container)`, at most one live entry per pair, exactly as
`FUNCTION_CATALOGUE.md` §8 specifies. **Measured against v2's engine: 431 entries, zero
collisions** — including the 56 module-level functions, which share the empty container and
still collide with nothing.

**The obvious index does not enforce it, and this is the single most likely build-time defect in
this change.** With `container_id` nullable for a module-level function, the natural

```sql
CREATE UNIQUE INDEX idx_catalogue_live_name ON catalogue (name, container_id)
    WHERE retired_at IS NULL;
```

accepts two live module-level entries with the same name, because SQL compares NULLs as
distinct. **Probed at SQLite 3.49.1 under Python 3.12.10: the second insert is accepted.** The
index would look correct, run green, and permit precisely the collision it was written to catch
— the failure this project has recorded twice already, where a check ran green while measuring
something narrower than its name.

**The fix, probed in the same run:** index the expression, not the column.

```sql
CREATE UNIQUE INDEX idx_catalogue_live_name
    ON catalogue (name, COALESCE(container_id, 0)) WHERE retired_at IS NULL;
```

The second insert is refused; the same name in two real containers is still accepted; the name
becomes free again once the first entry is retired. `PRAGMA index_list` reports the index
identically either way, so the parity check in 3E cannot tell the two apart — which is exactly
why 3E asserts the *behaviour* rather than the schema text.

### 3.4 Liveness: the death commit cannot decide it

`FUNCTION_CATALOGUE.md` §8 is unambiguous: *"The death commit is the only field that decides
liveness. A row with one is dead, a row without one is live. No separate status column alongside
it, because two fields that can disagree is where the tangle would come from."*

**That was true when the catalogue was a build-time record, and moving it to planning time (D10,
`CATALOGUE.md` §2) breaks it.** At planning time there are no commits. A helper designed at
stage 8 and designed away at stage 9 has no death commit and never will, so under the quoted
rule it stays live forever: it is offered as a search candidate for the rest of the plan, and its
name is locked against reuse by the index in §3.3. The design's own liveness rule makes a
planning-time catalogue unable to forget anything.

**Settled: liveness is `retired_at IS NULL`, and nothing else.** One field decides it, which is
the concern §8 actually had. `retired_at` is already a declared role in this schema —
*"withdrawn from live reads with a recorded reason"* — and the recorded reason is `retire_reason`,
the same pair `retire_row` and `retire_term` use. A planning-time withdrawal stamps it with a
reason and no commit. A build-time discovery stamps it with a reason **and** the commit at which
the absence was found, in one act.

**The owner's phrasing on that commit is preserved and worth preserving**: what the check knows
is where the absence was *discovered*, which may be well after the commit that removed it.
Recording what is actually known is honest.

**The commit fields are not in this change at all — see §3.9.**

### 3.5 How duplication is refused, and the rule that would not have been run

D10's mechanism is the written dismissal: *"Before a new entry is accepted, near matches already
catalogued are each dismissed with a written reason. A rule that merely says 'check for
duplicates' is an intention."* The mechanism is right. **Applied to every near match, its cost
is unaffordable, and this is measured rather than feared.**

Simulating registration of v2's 431 entries in order, each against the catalogue as it stood
before it, with a ranked search returning a page of five:

| | |
|---|---|
| mean candidates shown per registration | **3.3** |
| registrations shown nothing at all | 91 of 431 (21%) |
| registrations shown a full page | 235 of 431 (54%) |
| **written dismissals the plan would owe** | **1,415** |

**1,415 written sentences is not a rule anyone will run, and this project already knows what
happens to a rule like that.** `BUILD_SURFACE.md` §1 diagnoses v2's brief composition in exactly
these terms — *"every candidate row to be included or omitted with a written reason before a
unit can be handed over. It is a good rule with an unbudgeted cost, and it is why the execution
half was never exercised: the cheapest path was always to skip it."* Requiring a dismissal per
candidate rebuilds that rule one level down, in the change whose own design document diagnosed
it.

**Settled: the registration refuses until the highest-ranked candidate has been adjudicated. The
rest are shown and not required.** That is **~340 adjudications** across the whole plan — one
per registration where the search returns anything at all, which is 79% of them — against 1,415
for the strict form and none for the intention.

Three things make this the right cut rather than a compromise:

- **It is not a similarity threshold.** "The best candidate the ranking found" encodes no opinion
  about what similarity is worth acting on; it is the top of a list. The standing ruling against
  thresholds is untouched — no number decides whether something is a near match.
- **The friction sits where the risk is.** If the ranking is any good the duplicate is at the
  top; if it is not, no adjudication count fixes that.
- **The mandatory answer is the one that stops the registration** — see §3.6. A planner cannot
  tick the box, because the box has an answer in it that refuses the write.

**Rejected: a search receipt.** The registration would require a token from a prior
`search_catalogue` call, freezing the candidate set the way `brief_rows` freezes a brief's
closure. It makes "I did not look" impossible, and it adds a staleness question, a second call
and a table, to guard against a planner who could adjudicate the top match `unrelated` in the
same breath anyway. The tool running the search *inside* the registration gets the same
guarantee with no receipt to keep true.

**The mechanism is the refusal, not a discipline.** A registration arriving with no adjudication
is refused with the candidates in the refusal text, so the planner reads them and answers. There
is no path to an entry that did not pass a search, because the tool runs the search.

### 3.6 What a comparison records, and the verdict that refuses the write

A comparison is one judgment about one candidate: what the relationship is, and why.
`FUNCTION_CATALOGUE.md` §5 gives four relationships and the argument that overlap is asymmetric
— *"A small function may sit entirely inside a larger one, which is complete overlap of one and
slight overlap of the other."* **That argument demands a fifth**, because four values name only
one direction of containment, and the case they omit — the new function contains the existing one
— is a real and different instruction.

| relationship | what it means to do | may the entry be written? |
|---|---|---|
| `same` | merge: use what exists | **no** |
| `contains` | the existing entry contains the new one; use what exists | **no** |
| `contained_by` | the new one contains the existing; write it, and fold the old one in | yes |
| `partially_overlaps` | extract the shared middle as a third function | yes |
| `unrelated` | record the negative | yes |

**The two refusing verdicts are what make the adjudication load-bearing.** The cheap way past a
required field is to write whatever gets you through the door, and here the two answers a
planner would reach for if the match is real are exactly the two that stop the write. The
remaining dishonesty — answering `unrelated` about something that is not — is a lie in a record
the owner can read, which is the same standard `dismiss_gap` and the waiver log already set.

**A comparison is recorded whether or not an entry follows it**, and the refusing verdicts are
the ones that matter most. §6 of the design is the argument, and it applies with more force
here: *"if only merges are written down, the next planner runs the same search, sees the same
candidate, and decides again — possibly the other way."* The next planner about to write this
function should find that someone already reached it and was sent to the existing entry.

**So `same` and `contains` are an outcome, not an exception.** The call returns "no entry
written, use this one" and records the comparison. Raising instead would be wrong twice over: the
planner did exactly the right thing, and an exception path that also commits a write is a shape
nothing else in this engine has.

### 3.7 The search ranks and never fires

The search is `search_catalogue(query)`, returning live entries ranked by shared vocabulary in
the name and in the purpose line, both directions in one query, with no cut-off and no
notification. It is the same settlement `CATALOGUE.md` §5 reached for the cross-container report,
and for the same reason: the tool computes and shows, the planner decides.

**The ranking is lexical, and it has to be.** There is no model and there never will be
(`decisions:12`), and there are no embeddings, so retrieval is over words. **The glossary is
what makes it work and the dependency is load-bearing rather than incidental:** a keyword search
only finds what someone thought to describe in those words, so two functions doing the same job
in different vocabulary never match, and the glossary is what constrains the vocabulary the
purpose lines are written in. Without it the search is a lottery.

**Rejected: FTS5, and the reason is a measurement.** `engine/schema.py` ships a `source_fts`
virtual table and `references.py` writes to it. **Nothing reads it.** `ReferenceService.search`
claims *"retrieval is FTS5/BM25, with a substring fallback when FTS5 is absent"* and its
`_matches` helper is a plain lowercase substring scan; `source_fts` appears in exactly three
places in the engine — the DDL, one INSERT, and a comment. So there is no working FTS retrieval
here to borrow, only a docstring that says there is. Building one for the catalogue is a
different change with its own argument; borrowing the claim would be citing a row that says
something else.

**How stop words are handled is a task-local decision and this specification does not make it.**
What is not task-local, and is stated: the ranking function must be one function, called by both
the search and the registration, or the candidates a planner is shown and the candidate they are
required to adjudicate come from two rankings that will drift.

### 3.8 The cross-container report

`catalogue_clusters()` — live entries grouped by shared purpose vocabulary, ordered by how much
they share, with no cut-off and no notification. `CATALOGUE.md` §5 settled the shape and the
argument, and it stands as written.

**"Cluster" is reused deliberately and the test change 2 set is applied to it.** `GapCluster`
already means "a ranked grouping by affinity" in `gaps.py`, and this is the same concept applied
to a second object — which is one word for one role, not two roles for one word. If it were the
latter it would be the disease change 2 exists to treat.

**Nothing schedules a read of it in this change, and that is a hole this change deliberately
leaves open.** `CATALOGUE.md` §5 names the mechanism — a stage step that says read this report,
because a rule in a document is not a mechanism and a step in a script that the gate checks is.
The step belongs in the stage-8 script, and stage 8 does not exist until change 5. Putting it in
a stage-6 script now would tell a planner to read a report of an empty table. **Change 5 owes
this step**, and it is recorded in §9 so it is not lost.

### 3.9 What the build phase owes, and why none of it is here

Three things from the original design are **not in this change**: the `path` field, the landing
and death-discovery commits, and validation-at-point-of-use.

**They have no caller in v3, and the reason is D3.** The design has the catalogue validated
lazily, at the point of use: a search returns a candidate, and a single lookup confirms the named
function is really there. That requires someone searching the catalogue while a tree exists.
Under D3 the plan is finalized once, before any real building starts, so every search happens
before there is anything to validate against. `CATALOGUE.md` §2 says the safety property is
"dormant until the build phase"; it is stronger than dormant — **on the main path it never
activates at all.**

**Its real caller is the revision path.** A finalized plan reopens through a recorded revision,
and a revision made during or after the build is the one moment a planner searches the catalogue
with a tree in front of them. That is where validation, the commits, `path` and the churn
measurement belong, and it is a change of its own, after item 7.

**The cost is honest and is stated so it is not discovered later.** Churn — designed,
registered, and dead within a handful of commits — was the measurement that justified carrying
the two commit fields at all, and it is unavailable until that change lands. Shipping the columns
now with nothing writing them would be worse: this build has a recorded defect class of unread
fields, and `FUNCTION_CATALOGUE.md` §11 exists specifically because of it.

### 3.10 How this change lands

**One branch, one pull request, the packets as its commit order, the suite green at the end.**
Same shape as changes 1 and 2 and for the same reason: the packets cannot be made independently
green. 3B's registration calls the ranking function 3C specifies; 3D's registry rows name errors
3B raises; and 3E asserts that all of it landed.

**Unlike change 2, the packet letters *are* the landing order.** Nothing in this change emits
text naming a call — see §9 — so there is no `UnreachableCall` inversion to schedule around.

**This change touches no methodology asset and therefore mints no revision.** Nothing populates
the catalogue until stage 8 exists, so a script step added now would instruct a planner to fill a
table nothing else in the interview reaches. `PLAN.md` item 10 stays **revision 6**.

## 4. Packet 3A — the schema

Schema version 9 → 10. Nothing else in this change can start until this lands.

### Task 3A.1 — the DDL text

**Signature.** None — `schema.CATALOGUE_DDL` is module-level text appended to `DDL`, and
`SCHEMA_VERSION` becomes 10.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Two tables are declared: `catalogue` and `catalogue_comparisons`. |
| 2 | Held in one named block appended to `DDL`, so a fresh store and a migrated one are created from the same text. |
| 3 | Live-name uniqueness is enforced on `(name, COALESCE(container_id, 0))`. |
| 4 | At most one live public function entry per task, as a partial unique index. |
| 5 | Exactly one of `task_id` and `component_ref` is set, as a `CHECK`. |
| 6 | The version-9 DDL is retained as the fixture the parity check migrates from. |

**Behaviour 2 is the pattern `TERMS_DDL` established and its reason is quoted rather than
restated**: *"Two copies of a `CREATE TABLE` is a schema that drifts between the stores that
were migrated and the stores that were born — the same duplication this table exists to catch,
one layer down."* It reads oddly literally here, because this is the table that exists to catch
duplication.

**Behaviour 3 is §3.3, and the naive form is the trap.** The comment on the index says so, in the
schema, where the next person to edit it will read it.

**Behaviour 4 makes "exactly one public entry per task" a database invariant** rather than
something a service remembers to check — the same move `idx_obligation_live_owner` makes for
behaviour ownership, and the same reason. The "at least one" half is a gap and belongs to change
5, where tasks and pseudocode arrive together.

**Behaviour 5 is a `CHECK` and not a service guard**, because it is well-formedness and not
judgment: an entry with two owners or none is meaningless, in the same way a row with no
provenance is. `plan.guard` is the schema's precedent for a `CHECK` used this way.

**Behaviour 6 continues the pattern change 2 made a pattern.** The retained set grows by one text
per schema change; they are text, they diff, and they are never executed except by the parity
check.

**The DDL**

```sql
CREATE TABLE IF NOT EXISTS catalogue (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    container_id  INTEGER REFERENCES catalogue (id),  -- the object holding it; null at
                                                      -- module level. Not a path: location
                                                      -- is never identity.
    kind          TEXT    NOT NULL,      -- object | function
    visibility    TEXT    NOT NULL,      -- public | private
    purpose       TEXT    NOT NULL,      -- verb, object, qualifier; the whole of the search
    task_id       INTEGER REFERENCES tasks (id),      -- a function's owner
    component_ref TEXT,                                -- an object's owner
    retired_at    TEXT,                  -- null == live, and the only field that says so
    retire_reason TEXT,
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL,
    CHECK ((task_id IS NULL) != (component_ref IS NULL))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_catalogue_live_name
    ON catalogue (name, COALESCE(container_id, 0)) WHERE retired_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_catalogue_task_entry
    ON catalogue (task_id)
    WHERE kind = 'function' AND visibility = 'public' AND retired_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_catalogue_container
    ON catalogue (container_id, retired_at);

CREATE TABLE IF NOT EXISTS catalogue_comparisons (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    proposed     TEXT    NOT NULL,      -- the name that was being registered
    container_id INTEGER REFERENCES catalogue (id),
    matched_id   INTEGER NOT NULL REFERENCES catalogue (id),
    entry_id     INTEGER REFERENCES catalogue (id),  -- the entry written, if one was
    relationship TEXT    NOT NULL,
    reason       TEXT    NOT NULL,
    created_at   TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_comparisons_matched
    ON catalogue_comparisons (matched_id);
```

**`proposed` is a name and not a ref, and that is deliberate.** A comparison whose verdict is
`same` or `contains` produces no entry, so there is nothing to point at; the record has to carry
the name that was refused or it says nothing useful to the next planner. `entry_id` is null in
exactly those cases and is the field that distinguishes them.

**`catalogue_comparisons` has no `updated_at` and that is not an oversight.** It is an immutable
audit record, like `finding_reallocations` and `behaviour_amendments`; the vocabulary check's own
note says `updated_at` is *"absent on immutable tables by design"*.

**`catalogue` has one because an entry is mutable in two ways**: its purpose can be restated
(3B.4) and it can be retired.

### Task 3A.2 — `Storage._migration_steps`, the 9→10 branch

**Signature.** Unchanged. Gains one branch.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Creates both tables and all four indexes, from `schema.CATALOGUE_DDL` via `schema.statements`. |
| 2 | Backfills nothing. |
| 3 | Adds nothing to the snapshot table set. |

**Behaviour 1 reuses `statements()` rather than restating the SQL**, which is what the 3→4 step
did for `terms` and the 5→6 step for revisions. Restating it here would be the second copy
behaviour 2 of 3A.1 exists to prevent.

**Behaviour 2 invents nothing, and the test it passes is the one the glossary passed.** A plan
written before the catalogue existed has no catalogue, and empty is the truthful answer rather
than an invented one. There is no truth in the old store from which a set of function names could
be derived — and a catalogue derived from a tree is the design that was rejected in
`FUNCTION_CATALOGUE.md` §7 for dragging language-specific declaration-finding into the engine.

**Behaviour 3 reverses the instinct, and the reason is mechanical.** `snapshot_version` carries
nine tables and `tasks` is not among them: the whole execution layer sits outside snapshots. A
`catalogue` inside the snapshot set would be rewound while the `tasks` rows its `task_id`
references were not, leaving entries and tasks describing two different plans with no complaint
from anything. Both stay out, together.

**A consequence inherited, not created, and named so it is not read as new.** `recover('restart')`
clears eight tables and leaves `terms`, `findings` and the execution layer standing; the catalogue
joins that set. A restart therefore leaves a catalogue of a plan that no longer exists. That is
v2's behaviour for every table outside the eight, it is not this change's to fix, and fixing it
would be a change about recovery.

## 5. Packet 3B — the service

Depends on 3A. A new module, `engine/catalogue.py`, and `models.py`.

### Task 3B.1 — `catalogue_object`

**Signature.** `catalogue_object(self, name: str, purpose: str, visibility: str,
component_ref: RowRef | str, comparisons: tuple[Comparison, ...] = (),
idempotency_key: str = "") -> CatalogueResult`, on `CatalogueService`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Writes one `object` entry owned by the component, and returns it. |
| 2 | Refuses with `PurposeRequired` when `purpose` is blank. |
| 3 | Refuses with `RefNotFound` when `component_ref` is not a live `components` row, naming it. |
| 4 | Refuses with `NearMatchesUnadjudicated` when the search returns candidates and the highest-ranked one has no comparison, naming every candidate shown. |
| 5 | Refuses with `NameTaken` when a live entry already holds this name at module level, naming it. |
| 6 | Returns without writing an entry when a comparison on the highest-ranked candidate is `same` or `contains`, recording the comparison and naming the entry to use. |
| 7 | Every supplied comparison is written, whether or not an entry was. |
| 8 | Replaying the idempotency key returns the first result. |
| 9 | One transaction, one op batch. |

**Behaviour 3 checks the component is live and this is the one guard that is not obvious.** An
object owned by a superseded component is an entry whose owner has moved, and the entry is what
the cross-container report groups by. The check is `RefNotFound` and not a new error because the
codebase already has that name for exactly this.

**Behaviour 5 is the index in §3.3 reported as a refusal rather than as an `IntegrityError`.**
The service checks before writing so the message can name what already holds the name; the index
is what makes the check true rather than merely attempted. Both, deliberately — the same
arrangement `submit_rows` has with `idx_rows_live_name`.

**Behaviour 6 is §3.6, and the return type carries it.** `CatalogueResult` holds
`entry: CatalogueEntry | None`, `comparisons: tuple[Comparison, ...]`, and `use_instead:
CatalogueEntry | None`. A caller that reads `.entry` and finds `None` has been told the thing
already exists, with the entry in hand.

**Pseudocode**

```
if not purpose.strip():
    raise PurposeRequired naming the name
component = rows.get(component_ref)                   # RefNotFound naming the ref
if not component.is_live:
    raise RefNotFound naming the ref and its state
if a live entry holds (name, no container):
    raise NameTaken naming it
candidates = self._rank(name, "", purpose)            # 3C.1
if candidates and no comparison names candidates[0]:
    raise NearMatchesUnadjudicated naming every candidate shown
verdict = the comparison naming candidates[0], if any
ops = [insert each comparison]
if verdict is not in (SAME, CONTAINS):
    ops = [insert the entry] + [insert each comparison, entry_id borrowed from op 0]
write_atomic(ops, idempotency_key)
return CatalogueResult(entry, comparisons, use_instead=candidates[0] if refused else None)
```

`FromOp` is what lets the comparisons borrow the entry's assigned id inside one transaction; it
exists for exactly this and its docstring gives the reason — a parent and its children split
across two transactions leaves a parent with no children when a crash lands in between.

### Task 3B.2 — `catalogue_function`

**Signature.** `catalogue_function(self, name: str, purpose: str, visibility: str, task_id: int,
container: str | None = None, comparisons: tuple[Comparison, ...] = (),
idempotency_key: str = "") -> CatalogueResult`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Writes one `function` entry owned by the task, and returns it. |
| 2 | Everything 3B.1 refuses, refused the same way. |
| 3 | Refuses with `ContainerNotCatalogued` when `container` names no live object entry, naming it and saying to catalogue the object first. |
| 4 | Refuses with `TaskNotFound` when `task_id` is not a task, naming it. |
| 5 | Refuses with `EntryPointExists` when `visibility` is `public` and the task already has a live public entry, naming it. |
| 6 | A `container` of `None` is module level, and is not an error. |

**Behaviour 3 is what makes the container safe to be a foreign key.** The container is supplied
as a *name* because that is what a planner has in hand, and it is resolved to an id here; an
unresolvable one is refused rather than created, because creating it would be the tool deciding
that a new object exists.

**Behaviour 5 is the index of 3A.1 behaviour 4, reported as a refusal.** It is D6 stated as a
constraint: a task is one externally-callable function, so a second one means either the task is
two tasks or the name is wrong, and both are worth stopping for.

**A sequencing consequence that bites now and stops biting at change 5.** `task_id` references a
row in `tasks`, and in this change tasks are still derived at finalization from contract rows —
so until change 5 moves task creation to stage 8, function entries can only be catalogued for a
plan that has been finalized. That is awkward for the end-to-end drive of this change and it is
not a defect: the catalogue's real population happens at stage 8 and change 5 is what builds it.
Object entries have no such constraint, because a component is a plan row and exists from stage 6.

### Task 3B.3 — `retire_catalogue_entry`

**Signature.** `retire_catalogue_entry(self, name: str, container: str | None, reason: str,
idempotency_key: str) -> CatalogueEntry`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Stamps `retired_at` and `retire_reason`, and returns the entry. |
| 2 | Refuses with `RetireNeedsReason` when `reason` is blank. |
| 3 | Refuses with `EntryNotFound` when no live entry holds this name and container. |
| 4 | Refuses with `ContainerNotEmpty` when the entry is an object still holding live entries, naming them. |
| 5 | A retired entry is never returned as a search candidate and is still consulted for the name check. |
| 6 | Retirement is never undone; the name is free for a new entry, which is a new row. |

**Behaviour 2 reuses the error name change 2 gives `retire_row`**, because it is the same
refusal for the same reason and a second spelling of it is what this whole family of documents is
about.

**Behaviour 4 exists because the container is a foreign key.** Retiring an object whose methods
are still live leaves entries pointing at a dead container, and the report groups by it. Naming
the survivors is what makes the refusal actionable.

**Behaviour 5 is `FUNCTION_CATALOGUE.md` §8 unchanged**: a dead function cannot be reused and
offering it is a confidently wrong answer, but the thing about to be written may have been
removed on purpose, and the planner may be undoing somebody's decision without knowing it.

**Behaviour 6 is the reintroduction case, and the design's ruling stands.** A function written,
removed and written again is precisely the case that suggests something was wrong with the
original design, and nulling the retirement erases that history at the moment it becomes
interesting. The lineage is a query — every entry with this name and container, oldest first —
and no edge type is added, because the edge vocabulary is deliberately closed.

### Task 3B.4 — `restate_purpose`

**Signature.** `restate_purpose(self, name: str, container: str | None, purpose: str,
idempotency_key: str) -> CatalogueEntry`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Replaces `purpose` in place and stamps `updated_at`. |
| 2 | Refuses with `PurposeRequired` when blank, and `EntryNotFound` when there is no live entry. |
| 3 | Recorded comparisons are untouched. |

**In place, and this is a deliberate departure from every other justification-bearing field in
the store.** Change 2 made `grounds` write-once because an argument that can be rewritten is a
place to revise history quietly. A purpose line is not an argument; it is an index entry, and
nothing cites it. Forcing a retirement and a re-registration to fix a wrong verb would poison the
one measurement the commit fields were carried for — churn is designed-and-dead-quickly, and it
stops meaning anything if typos produce dead entries.

**Behaviour 3 is the honest cost.** A comparison recorded against the old wording is not
re-adjudicated, so a restatement can leave a `unrelated` verdict standing against an entry it no
longer describes. The alternative — invalidating comparisons on restatement — makes restating
expensive again and re-creates the problem this call solves. The comparison records what was
judged and when; the change feed records the restatement.

## 6. Packet 3C — the search and the report

Depends on 3B's module. Read-only.

### Task 3C.1 — the ranking

**Signature.** `_rank(self, name: str, container: str, purpose: str, limit: int = 5)
-> tuple[Candidate, ...]`, private to `CatalogueService`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Ranks live entries by shared words in the name and shared words in the purpose, both. |
| 2 | Name matches outrank purpose matches at equal counts. |
| 3 | An entry sharing nothing is not a candidate at any rank. |
| 4 | The entry being registered is never its own candidate. |
| 5 | Ties break on the older entry first, so the ranking is stable across calls. |
| 6 | Returns at most `limit`. |

**Behaviour 1 is the both-directions search stated as one function**, which is the design's own
point: one query answers two questions, so it costs nothing to look for both.

**Behaviour 2 encodes which defect is more expensive to miss.** A name collision is the one that
bit this build three times in a sitting; a description collision is the one the catalogue is
primarily aimed at. Ranking name matches first is a preference and is stated as one, so a later
change can argue with it.

**Behaviour 5 is not tidiness.** The registration refuses until the *highest-ranked* candidate is
adjudicated, so an unstable ranking makes the required answer change between the call that
showed the candidates and the call that answers them.

**This function is called by both `search_catalogue` and every registration**, per §3.7: two
rankings would drift, and the planner would be required to adjudicate a candidate they were never
shown.

**The limit is a page size and not a threshold.** It bounds what is displayed, not what counts as
similar; `references.search` already carries `limit: int = 10` for the same job. 5 is chosen
against the measurement in §3.5, where a page of five shows a mean of 3.3.

### Task 3C.2 — `search_catalogue`

**Signature.** `search_catalogue(self, query: str, limit: int = 5) -> tuple[Candidate, ...]`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Ranks live entries against a free-text query, using 3C.1. |
| 2 | Each candidate carries name, container name, purpose, kind, visibility and owner. |
| 3 | Returns an empty result for a query that matches nothing, and that is not an error. |

**Behaviour 2 carries the container's *name* and not its id**, because a caller reading a result
needs to be able to pass it back to `catalogue_function`, which takes a container name.

### Task 3C.3 — `catalogue_clusters`

**Signature.** `catalogue_clusters(self, limit: int = 20) -> tuple[Cluster, ...]`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Groups live entries whose purposes share vocabulary and whose containers differ. |
| 2 | Orders by how much they share; no cut-off, no notification, no gap. |
| 3 | Each cluster names the shared words and every entry in it, with its container. |
| 4 | Module-level entries participate, and share the empty container. |

**Behaviour 2 is `CATALOGUE.md` §5 and the argument is the owner's standing ruling.** A threshold
is a judgment written as arithmetic so that review cannot see it; "three or more containers share
a similar method" encodes an opinion about what similarity is worth acting on, as a number nobody
will ever revisit.

**Behaviour 4 is a decision and the alternative is worse.** Excluding module-level entries because
they have no container would hide the case where a module-level helper and a method do the same
job — which is one of the two shapes duplication actually takes here.

**The cost is honest and unchanged from the design**: nobody is standing there when a duplication
becomes true, so a ranked report only helps if someone reads it, and nothing in this change
schedules that read. §3.8 and §9 say who owes it.

## 7. Packet 3D — the surface and what a reader sees

Depends on 3B and 3C. `surface.py`, `render.py`.

### Task 3D.1 — the registry

**Behaviours**

| | behaviour |
|---|---|
| 1 | Six tools are added, all `DEVIATION`, each appearing in `ADDED` with its reason. |
| 2 | A `comparisons` payload parser accepts a list of `{matched, relationship, reason}`, rejecting an unknown relationship by name. |
| 3 | The registrations and the two mutating calls carry `writes=True`; the three reads do not. |
| 4 | No contract row is superseded. |

**The six tools.**

| tool | writes | why it exists |
|---|---|---|
| `catalogue_object` | yes | D10's objects; nothing else can record one |
| `catalogue_function` | yes | D10's functions and methods |
| `retire_catalogue_entry` | yes | a design that changes leaves entries behind, and an entry that cannot die locks its own name |
| `restate_purpose` | yes | the purpose carries the whole search; a wrong one is a search that fails |
| `search_catalogue` | no | the planner's half of the loop — the tool computes and shows |
| `catalogue_clusters` | no | the cross-container report |

**Behaviour 1's count is stated because a coverage test that asserts a number nobody wrote down
cements whichever number the builder guessed.** The planning surface goes from 54 tools to 60.

**Behaviour 4 is the correction to the instinct, and change 2's cold read is why it is stated.**
No contract row describes any of this — the frozen plan never anticipated a catalogue, so it
cannot have anticipated the calls — which is exactly what `DEVIATION` means and why each carries
a written reason in `ADDED`. No `Absence` entry is filed either: an absence records a call that
**exists** and is deliberately not exposed, and none of these was ever built before.

**No tool reads a comparison back, and that is a hole this change accepts with its eyes open.**
The comparisons are written and are readable only from the database. The next planner who would
benefit from them is the one the search shows the same candidate to — and giving them the prior
verdict is the whole of §3.6's argument. The reason it is not here is that the natural home is
the candidate itself: a search result should carry "the last time someone compared something to
this, they said X". **That is a change-5 item**, listed in §9, because the search result's shape
is what brief composition also consumes and specifying it twice is how two shapes drift.

### Task 3D.2 — rendering

**Behaviours**

| | behaviour |
|---|---|
| 1 | A rendered candidate shows its name, container and purpose, never a bare id. |
| 2 | A refusal listing candidates lists them the same way. |
| 3 | Refs inside a `purpose` or a comparison `reason` are rendered as `name (ref)`. |

**Behaviour 1 is the naming discipline applied to a table that has no refs.** A catalogue entry
is addressed by name and container, following `terms`, which is looked up *"by the word you were
about to type, never by an ordinal"*. So `door.scan` never sees a `catalogue:` address in outgoing
text, and `resolver_from` needs no third lookup — unlike `findings`, where the absence of one
made every `findings:3` in the owner's prose read as *no live row at this address* (F38).

**Behaviour 3 is the door's existing invariant and this change walks into it, exactly as change 2
did.** A comparison's `reason` is argumentative prose — *"different thing: this one is about the
contract, see components:6"* — and `door.scan` raises `BareAddress` on any `table:ordinal` in an
outgoing payload not accompanied by a name. Change 2 probed the pattern against realistic
justification prose and found one trap, a URL with a port; that probe stands and is not re-run.

**A comparison `reason` and a `purpose` are validated for unresolvable refs at the write**, for
the reason `record_grounds` behaviour 6 gives: combined with a field nothing can rewrite, an
unresolvable ref makes the row permanently unreadable through the surface. `purpose` is
restatable and so is repairable; a comparison `reason` is not, which makes the check matter more
here than there. **This is now the third task to reach the same answer**, and per the register's
own growth rule it is proposed as a convention entry — see §10.

## 8. Packet 3E — the enforcement

Depends on all of the above.

### Task 3E.1 — the justification vocabulary, extended

**Behaviours**

| | behaviour |
|---|---|
| 1 | `catalogue.retire_reason` and `catalogue_comparisons.reason` join `JUSTIFICATION_ROLES`. |
| 2 | The declared set becomes **eleven** members. |
| 3 | Both are role 1 — why an act was performed — and the declaration says which act. |

**This task exists because change 2 built a check that will refuse this change's schema.** 2E.1
behaviour 2: a column named `reason`, `grounds` or `alternatives`, or ending in `_reason`, must be
a declared member. `catalogue.retire_reason` and `catalogue_comparisons.reason` are both, so
without this task the suite fails on 3A.1 and the failure looks like a mistake rather than the
sequencing it is — the same shape as change 1's task 1A.0.

**Behaviour 3 applies change 2's own test rather than assuming the answer.** *A `reason` is
attached to an act and names a transition; `grounds` are attached to content and name no
transition.* `retire_reason` names retiring. `catalogue_comparisons.reason` names the comparison —
the act of judging one candidate against one proposal — which is why the column is `reason` and
not `grounds`, even though it reads like an argument. The comparison row **is** the act; it has no
content of its own to have grounds for.

**No new `_at` role and no new suffix.** `retired_at`, `created_at` and `updated_at` are all
declared. The commit fields that would have needed a `_commit` shape are not in this change (§3.9),
so `SHAPES` is untouched.

### Task 3E.2 — schema parity, and the index that must be shown to work

**Behaviours**

| | behaviour |
|---|---|
| 1 | A version-9 database migrated to 10 is structurally identical to a fresh 10 — raw `PRAGMA table_info`, `index_list` and `foreign_key_list` output, compared as-is. |
| 2 | Two live module-level entries with the same name are refused. |
| 3 | The same name in two different containers is accepted. |
| 4 | A retired name is available again, and the new entry is a new row. |
| 5 | A task cannot hold two live public function entries. |
| 6 | An entry with two owners, or none, is refused by the store itself. |

**Behaviour 2 is the whole reason this task is not just a parity check.** `PRAGMA index_list`
reports the naive index and the `COALESCE` index identically, so parity cannot tell them apart —
and the naive one accepts the duplicate. A test that asserts the schema text would pass on a
correct-looking index that does not work. The assertion has to be the behaviour, and it is the
one assertion in this change that would catch a builder writing the obvious thing.

**Behaviour 6 asserts the `CHECK` at the store**, not through the service, because a service guard
that happens to agree with a constraint proves nothing about the constraint.

### Task 3E.3 — the size and the shape

**Behaviours**

| | behaviour |
|---|---|
| 1 | The registry holds 60 tools, and every `DEVIATION` among the six appears in `ADDED`. |
| 2 | A registration with candidates and no comparison is refused, and the refusal names every candidate. |
| 3 | A `same` verdict writes the comparison, writes no entry, and returns the entry to use. |
| 4 | The ranking a registration adjudicates against is the ranking `search_catalogue` returns for the same input. |

**Behaviour 4 is the one a builder would skip**, because each half looks covered by a unit test of
its own. It is what makes §3.7's "one ranking function" a mechanism rather than a sentence: two
rankings would let a planner be shown one candidate and required to adjudicate another, and every
individual test would still pass.

## 9. What this change does not do

**It does not populate anything.** Nothing in the eight-stage interview reaches the catalogue, so
after this change the table is empty and stays empty until change 5 writes tasks, pseudocode and
entries at stage 8. This change builds the instrument; change 5 is what uses it.

**It does not add a gap rule.** The countable obligations — a task with no public entry, a
pseudocode call with no entry — all have denominators that do not exist yet. A rule counting
against an empty table would report a clean plan, which is F23's disease: a check that runs,
passes, and means nothing.

**It does not touch a stage script, a gate criterion or the mandate**, and so mints no methodology
revision. `PLAN.md` item 10 stays revision 6.

**It does not carry `path`, the landing commit, the death-discovery commit, validation at the
point of use, or churn** — §3.9, and they belong to a change after item 7 that gives the revision
path a catalogue to validate.

**It does not read a comparison back through the surface** — 3D.1, and the natural home is the
search result, whose shape change 5 settles.

**It does not schedule a read of the cross-container report.** §3.8; change 5's stage-8 script
owes that step, and without it the report is a query nobody runs.

**Three items change 5 inherits from this change, listed together so they are not rediscovered:**
the stage-8 script step that reads the report; the prior-verdict field on a search result; and the
"at least one public entry per task" gap.

## 10. A convention this change proposes

**Validate refs in stored prose at the write.** *A free-text field that will be rendered through
the door is checked at the write for `table:ordinal` tokens that do not resolve, and the write is
refused naming the token.* Change 2 reached this for `grounds` and `alternatives` (2B.2 behaviour
6) with a probe behind it; this change reaches it again for `purpose` and a comparison `reason`.
**That is the third task, which is the register's own bar** — an entry is proposed when the same
uncited decision appears in three tasks with the same answer — so it goes to `CONVENTIONS.md`
with change 2's probe as its evidence.

**Strip on store**, proposed by change 2 as its second occurrence, reaches its third here:
`name`, `purpose` and a comparison `reason` all need the same answer. It goes to `CONVENTIONS.md`
in this change.

## 11. The cold read, and the corrections it owes

**Four readers, one per packet group — 3A, 3B, 3C+3D, 3E. All four reported zero tool uses.** Each
was given its packet verbatim, the §3 sections it depends on verbatim, the adjacent packets
verbatim, the conventions register, and the source a builder would hold.

**The corrections below are NOT yet applied to §1–§10.** This section is the worklist. It is
written out in full because the readings cost about six minutes of wall clock and exist nowhere
else.

### 11.1 What was re-measured, and what the numbers actually are

Every count in §3 was taken from an AST parse of `engine/*.py` — 30 modules — treating a class as
an object entry, a method as a function entry with that class as its container, and a module-level
`def` as a function entry with no container. **The method was never stated, which is itself a
finding: a denominator produced by an unnamed method is not checkable.**

| | drafted | **measured** |
|---|---|---|
| catalogue entries | 464, then 431 | **635** — 204 objects + 431 functions |
| function entries | 255 public, 209 private | **255 public, 176 private**; 464 is the total *including* the 33 dunder methods the trivial-member rule excludes |
| identity collisions | "zero" | **6 names over 17 definitions — 11 registrations refused.** Zero among the 431 functions; all 11 are module-level objects |
| adjudications, every candidate | 1,415 | **2,475** |
| adjudications, top candidate only | ~340 | **561** (88% of registrations; 74 of 635 are shown nothing) |
| mean candidates shown, page of 5 | 3.3 | **3.90**; 441 of 635 (69%) see a full page |
| planning surface after this change | 60 | **57** — and `ADDED` becomes **16** |

**The collision count is the sharpest correction and it inverts a claim.** §3.3 measured identity
over the 431 functions and reported "zero collisions" for a table that also holds 204 objects.
`PlanUnreadable` is defined in four modules, `AlreadyResolved`, `InvalidTransition` and
`RefNotFound` in three each, `Package` and `UnknownPackage` in two. Eleven registrations are
refused — which is the mechanism working, and a far better argument for cataloguing objects than
the one §3.2 makes. §3.2's own "six class names defined in two modules each" is also wrong: six
names, seventeen definitions.

**The tool count was wrong at both ends and two readers caught it independently.** 54 today;
change 1 removes **four** tools, not three — `declare_package`, `assign_task`, `packaging` **and
`split_subtask`**, whose registry row and `split` payload parser go with it (change 1, task 1C.3);
change 2 adds `record_grounds`. 54 − 4 + 1 = 51, + 6 = **57**. `ADDED` is 12 today, loses three
(`split_subtask` is not in `ADDED` — it has a contract), gains `record_grounds` and the six:
**16**. §3D.1's own rationale is that an unstated count gets cemented at whatever the builder
guessed; it stated one and cemented the wrong number.

**Also miscounted:** "the three reads" in 3D.1 behaviour 3, where the table above it lists **two**;
"the 3→4 step and the 5→6 step" use `statements()`, where **three** of the four existing branches
do — 6→7 is the third, and 4→5 is the interesting mixed case that goes unmentioned.

### 11.2 What was probed

Run at SQLite 3.49.1 under Python 3.12.10, against the DDL as drafted:

- **The naive index is the trap and the `COALESCE` form fixes it** — confirmed, including that the
  same name in two real containers is still accepted and that a retired name is reusable.
- **`CHECK ((task_id IS NULL) != (component_ref IS NULL))` fires in both directions** — two owners
  refused, no owner refused, one owner accepted.
- **`idx_catalogue_task_entry` refuses a second live public entry for one task**, and admits a
  private entry for the same task and any number of object entries.
- **`schema.statements(CATALOGUE_DDL)` yields exactly six statements.** The 3E reader was right to
  ask: two comment lines in the DDL contain semicolons, and the split is safe only because
  comments are stripped first. Now measured rather than reasoned.
- **Parity holds**: `table_info`, `index_list` and `foreign_key_list` are identical for a fresh
  store and one built statement-by-statement.
- **The vocabulary parser sees all 20 new columns**, both tables, both `created_at`s; `_ref` is
  TEXT and all five `_id`s are INTEGER; the only `_at` names are declared roles; and the two
  justification columns are exactly `catalogue.retire_reason` and `catalogue_comparisons.reason`.
- **Foreign keys are enforced.** Three readers flagged that `PRAGMA foreign_keys = ON` sitting in
  `DDL` would bind only at `init_plan`. It is also issued in the connection factory
  (`engine/storage.py:132`), per connection, and a bad `task_id` is refused at runtime. The
  concern was right and the answer is good.
- **`_hydrate` is a method on five service classes**, so §3.1's argument that `plan_rows`' name
  index is the wrong index holds.

### 11.3 The design defects — corrections owed to §3–§8

**Landing order is inverted twice, exactly as it was in change 2.**
1. 3B's registration calls `_rank`, which packet 3C specifies. **`_rank` moves into 3B.**
2. 3B.2's `ContainerNotCatalogued` message tells the planner to catalogue the object first — text
   naming a call, which the door refuses with `UnreachableCall` until 3D.1 has registered it. So
   **3D.1 precedes 3B**, and §3.10's claim that "the packet letters are the landing order" and that
   "nothing in this change emits text naming a call" are both false.

**The suite is red between 3A and 3E.** 3E.1 says the justification check refuses 3A's two new
columns, and 3E lands last. **The `JUSTIFICATION_ROLES` entries become task 3A.0 and land first**,
which is exactly what change 1 did with task 1A.0 and for the same reason.

**`JUSTIFICATION_ROLES` keying was never stated and the count depends on it.** Under bare-column
keying — which is how `TIMESTAMP_ROLES` beside it is tested — `reason` and `retire_reason` are
already declared, change 3 adds nothing, and 3E.1's premise is false. The register must be keyed
**`table.column`**, because the role differs per table: `behaviour_amendments.reason` names
amending and `scope_attachments.reason` names attaching. Under that keying change 2's nine
enumerate exactly, and eleven is right. **Change 2's specification owes the same sentence.**

**Replay is specified wrongly and the default key is a hazard.** Every guard runs before
`write_atomic`, so a replayed registration that wrote an entry hits `NameTaken` first and behaviour
8 is unreachable. Worse, `idempotency_key: str = ""` means the first defaulted call's receipt
replays for **every** later defaulted call in that database. Fix: the key is required, as it
already is on 3B.3 and 3B.4; and behaviour 8 is restated in its two real cases — a replay of an
entry-writing call is refused with `NameTaken` naming the row the first call wrote, and a replay of
a `same`/`contains` call reaches `write_atomic` and returns the original receipt, which is the case
that matters.

**The CHECK is too loose and three value sets are unconstrained.** A `kind='function'` row may set
`component_ref` instead of `task_id`, pass the CHECK, and escape `idx_catalogue_task_entry`
entirely — the NULL trap §3.3 exists to close, reintroduced one index later. And `kind`,
`visibility` and `relationship` are enumerated in comments with no constraint, so `'Public'` slips
past the index predicate and a task quietly acquires two entry points, while a misspelt
relationship takes the permissive branch and writes the entry the planner meant not to write.
**All four get CHECKs**, and the argument is not "well-formedness" in general — `subtasks.state`
enumerates in a comment with no CHECK and is the schema's actual habit — but this: **a value that
appears in an index predicate must be constrained, because a typo there does not fail, it removes
the row from the invariant.** The `plan.guard` precedent §4 cites is a single-column constant test
and does not carry a cross-column exclusive-or; drop it.

**`_rank`'s signature cannot serve `search_catalogue`.** Three arguments against one free-text
query. The `container` parameter has no semantics and every call site passes `""` — **drop it**.
`search_catalogue(query)` calls `_rank(name=query, purpose=query)`, and the specification must say
so and say why it is right: an entry matching the query in both its name and its purpose is a
better match, and behaviour 2 is a property of the *entry* side, not the probe's.

**Behaviour 4 of 3C.1 is dead text** — at registration the entry does not exist yet, and
`search_catalogue` has no entry being registered. The only exclusion it could implement is name
equality, which would hide the exact name collision the search exists to find. **Delete it.**

**"Older first" must read `id`, not `created_at`** — the stability guarantee behaviour 5 makes, and
which 3B's refusal depends on, is false for two entries written in the same clock tick. `id` is the
only total order the schema guarantees.

**3C.3's behaviours cancel.** Grouping entries "whose containers differ" while module-level entries
"share the empty container" means two module-level functions can never cluster — excluding a large
share of real duplication. The report groups by shared purpose vocabulary and **reports** the
containers rather than filtering on them.

**The glossary dependency is asserted and wired nowhere.** §3.7 calls it load-bearing; nothing in
any packet reaches `TermService`, and convention 11 guarantees an unpassed collaborator fails
silently. The precedent to follow is `RowService._vocabulary_note`, which calls
`terms.violations()` and **warns without rejecting** at the moment of typing — *"naming happens at
the point of least attention, and the moment of typing is the only moment at which saying so
changes anything."* The catalogue is the second place that argument applies.

**Four models are consumed by three packets and defined by none** — `CatalogueEntry`, `Candidate`,
`Cluster` and `Comparison`. `Comparison`'s *input* shape is the load-bearing one: whether a
comparison names its candidate by id or by name decides the payload parser, the search result and
3B's matching test.

**3B has no read path at all**, yet needs lookups four times: the name check, the container
name→id resolution, the `(name, container)` finder for 3B.3 and 3B.4, and 3B.3's "still holding
live entries" query. And the returned entry has to be read back from somewhere.

**Smaller, all real:**
- The pseudocode never checks that `component_ref` names a `components` row — `RowService.get`
  takes any ref, so an object owned by a requirement is accepted.
- The behaviour table's refusal order is not the pseudocode's, and as pseudocoded
  `NearMatchesUnadjudicated` is unreachable for an exact name collision, because an exact match
  ranks first.
- `NameTaken` "at module level" is wrong for 3B.2, where the check is against the container.
- A blank comparison `reason` meets `NOT NULL` with no refusal in between — an `IntegrityError` on
  the change's central write path. It needs its own named refusal.
- "A retired entry is still consulted for the name check" has no implementation site anywhere. The
  result should carry the retired entry and its retire reason: the planner may be undoing
  somebody's decision without knowing it, which is the strongest argument in the section.
- `contained_by` and `partially_overlaps` describe actions nobody performs — say they are
  instructions to the planner, or give them a follow-through.
- Convention 1 forbids a status field in a success payload, and behaviour 6 is one. §3.6 argues the
  override; the register requires the override to be written in the task, not upstream.
- Stored prose is `door.Verbatim` — *served as written, annotated alongside* — which is the
  opposite of 3D.2 behaviour 3's inline rewrite. Verbatim is right; the behaviour is wrong.
- The write-time ref check has no named error, and the URL-with-port trap change 2 found is now
  promoted from "renders oddly" to "the write is refused"; the refusal must name the token.
- No tool's parameters are specified — and `Param.note` is, in `surface.py`'s own words, the whole
  of a tool's documented interface. Nor is it stated that all six are **planning**-surface tools,
  which convention 5 asks by name.
- `idx_comparisons_matched` has no reader in this change: **drop it** until the change that reads
  comparisons back. `idx_catalogue_container` does have one — `ContainerNotEmpty` and the container
  resolution — and should say so.
- 3E.2's behaviours 2 and 5 must be asserted **at the store**. Through the service, a second
  identical name is refused by `NearMatchesUnadjudicated` before the index is ever touched, so the
  test passes green on the naive index — the precise failure behaviour 2 exists to prevent.
- Parity should add `PRAGMA index_info` for the two new tables. As specified it is blind to which
  columns any index covers, which leaves `idx_catalogue_container` with no coverage at all.
- Nothing verifies 3A.2's "backfills nothing" or "adds nothing to the snapshot table set".
- Nothing asserts that `_columns()` still *finds* the two new tables. If the regex misses them the
  vocabulary checks pass while seeing nothing, and `test_the_check_can_actually_fail`'s `> 100`
  floor never moves.

### 11.4 The cross-change hole this found

**`_columns()` parses the whole of `engine/schema.py`.** Changes 1, 2 and 3 each retain the
previous version's DDL as the fixture their parity check migrates from, and no change says where
the retained text lives. If it lives in `schema.py`, every retained DDL becomes phantom schema for
three vocabulary tests — resurrecting the very table and column names change 1 renamed. Change 1's
task 1F.3 implicitly assumes otherwise, since it corrects an assertion from `subtasks` to `tasks`
that a retained v7 DDL would keep satisfying. **The retained DDL texts live outside
`engine/schema.py`, and changes 1 and 2 owe that sentence too.**

### 11.5 What the readers got wrong, and one bundle error of mine

Recorded because taking a cold read at face value is its own failure.

- One reader held that `errors.py` defines two classes named `RefNotFound` in one module. **That
  was my bundle, not the specification** — I wrote the note carelessly; the duplicates are in
  different modules. Third change running, a bundle defect produced a finding.
- One reader read `search_catalogue(query)` calling `_rank(query, "", query)` as double-counting
  that collapses the name-outranks-purpose rule. It does not: an entry only scores on words that
  appear in *its* name or *its* purpose, so matching both is a genuinely stronger match. The
  finding that the signature is unspecified stands; the consequence it drew does not.
- One reader called the parity check "close to unfailable" because both sides are built from the
  same text. That is right and it is the point — parity's job here is to catch a migration that
  omits the block, and the index behaviour is 3E.2's separate business.
- Convention 14 was cited against "reorganising" beside "finalized". Both are correct here:
  the first is a quotation, the second is this codebase's established spelling (`finalize_plan`).
