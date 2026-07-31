# Change 3 — the catalogue

**BUILT AND MERGED 2026-07-31. §12 is the build record** — schema 10, 647 tests, 57 tools —
and it is where the next change's cold read starts. Read §12.1 before §3.7, §9 or task 3B.1
behaviour 11: those three still carry the `engine/lexical.py` amendment that change 4 reversed,
and the build followed the reversal.

**Specification, complete. All five packets were cold-read and §11's corrections are applied
below. Amended twice on 2026-07-29 by change 4** — the ranking and the tokeniser are a shared
module, and stop words are settled here rather than left task-local; both are marked in place and
listed in §9, and neither changes a number this document measured. §11 stays as the record of what
the four readers found — the numbers they re-measured, the
probes that settled the technical claims, and the two findings they got wrong — because that is
evidence and it exists nowhere else. Third of the ten changes in `PLAN.md` §4. It
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
| 7 | 464 entries: 255 public, 209 private | **635**: 204 objects and 431 functions — 255 public, 176 private | 3.2 |

**Every count below was taken the same way, and the method is stated in full because a denominator
produced by an unnamed method is not checkable.** An AST parse of **every `.py` file under
`engine/`, recursively — 30 modules.** The recursion matters: `engine/*.py` matches 29 and misses
`engine/methodology/__init__.py`. A class is an object entry, a method is a function entry whose
container is that class, and a module-level `def` is a function entry with no container.

**Two exclusions, and both are needed to reproduce the numbers.** Dunder methods go, under the
trivial-member rule. **And a function defined inside another function does not count** — five of
them exist, they have no identity `(name, container)` can address, and no other task can call one.
Counting them gives 640 where this document says 635.

**That second exclusion was unstated in the first attempt at this paragraph and the counts could
not be reproduced from it** — 30 modules and 204 objects came out right, 255 public did not. It is
recorded because it is this change's own subject: the method *is* the denominator, and a method
that is 95% written produces a number that looks checkable and is not.

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
A catalogue identity is `(name, container)`: `_hydrate` is a legitimate method name on **five
service classes in this engine**, and under `plan_rows`' index the second one would be refused as
a duplicate. The index that makes naming a mechanism for plan rows is the wrong index for this
table.

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

**Objects are the half that catches things, and this is the measurement that carries the whole
section.** v2's engine holds **204 classes**, and **six names account for seventeen definitions**:
`PlanUnreadable` in four modules, `AlreadyResolved`, `InvalidTransition` and `RefNotFound` in three
each, `Package` and `UnknownPackage` in two. That is **eleven registrations the identity index
refuses** — seventeen definitions minus the six first ones — every one of them an object, and
**zero** among the 431 functions (§3.3). Five of the six are error types, which are the names
contracts cite, and a reader who imports the wrong `RefNotFound` writes an `except` clause that
never fires.

**So the catalogue's whole collision-catching yield is in the half `CATALOGUE.md` dropped.** Leave
objects out and eleven refusals become zero, and the container becomes free text, which can be
misspelt — and a misspelt container silently splits the search, which is the disease this table
exists to treat.

**An object's owner is a component, not a task, and D10 is wrong about this too.** D10 says
"each entry has one owning task". A service class carries the entry points of twenty tasks, so
no task owns it. Its owner is the **component**, which is the level directly above and the
reason D16's un-retirement of the word earns its keep. So: a function entry carries `task_id`, an
object entry carries `component_ref`, and exactly one of the two is set.

**Modules are not catalogued.** A module is a location, and `FUNCTION_CATALOGUE.md` §3 is
explicit that location is not identity: *"if a row is identified by location, reorganising files
reads as deletion plus addition and destroys the history the catalogue is accumulating."* So a
module-level function has no container. §3.3 is what makes that safe.

**The size check, recounted, because the figure in `CATALOGUE.md` is wrong twice.** It says 464
entries — 255 public, 209 private. Parsed from v2's engine: **464 is the total including 33
dunder methods**, which the trivial-member exclusion removes before anything is registered. After
the exclusion there are **431 function entries — 255 public, 176 private**. And it omits objects
entirely, so the catalogue is **635 entries: 204 objects plus 431 functions.**

255 public is right and is the same 255 that sizes the whole of v3's detailed design, so the
number everything else rests on survives; it was the private half that was counted before the rule
was applied, and the object half that was never counted at all. **635, 431 and 176 are upper
bounds**: the exclusion is broader than dunders and also removes accessors and one-line wrappers,
which are not mechanically countable from a parse.

### 3.3 Identity, and the index that silently does not work

Identity is `(name, container)`, at most one live entry per pair, exactly as
`FUNCTION_CATALOGUE.md` §8 specifies.

**Measured against v2's engine, over all 635 entries: the identity collides eleven times, and
every one of them is a module-level object.** The 431 functions collide with nothing — including
the 56 module-level ones, which share the empty container and still never meet. The eleven are
§3.2's six class names, and the fact that all of them sit at module level is what makes the next
paragraph the single most consequential line of DDL in this change: **every collision this
catalogue would catch in a codebase the size of v2's is a collision between two entries whose
`container_id` is NULL.**

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
something narrower than its name. **And per the measurement above, that is not a corner: it is
all eleven of them.** The naive index catches nothing this catalogue exists to catch.

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

Simulating registration of v2's 635 entries in order, each against the catalogue as it stood
before it, with a ranked search returning a page of five:

| | |
|---|---|
| mean candidates shown per registration | **3.90** |
| registrations shown nothing at all | 74 of 635 (12%) |
| registrations shown a full page | 441 of 635 (69%) |
| **written dismissals the plan would owe** | **2,475** |

**2,475 written sentences is not a rule anyone will run, and this project already knows what
happens to a rule like that.** `BUILD_SURFACE.md` §1 diagnoses v2's brief composition in exactly
these terms — *"every candidate row to be included or omitted with a written reason before a
unit can be handed over. It is a good rule with an unbudgeted cost, and it is why the execution
half was never exercised: the cheapest path was always to skip it."* Requiring a dismissal per
candidate rebuilds that rule one level down, in the change whose own design document diagnosed
it.

**Settled: the registration refuses until the highest-ranked candidate has been adjudicated. The
rest are shown and not required.** That is **561 adjudications** across the whole plan — one per
registration where the search returns anything at all, which is 88% of them — against 2,475 for
the strict form and none for the intention. It is a quarter of the cost and it is still the
largest single obligation this change creates, which is why §3.6's shape matters: 561 answers are
worth having only if answering carelessly is harder than answering honestly.

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

**The middle column is an instruction to the planner and nothing in the engine performs it.** That
is stated because it would otherwise read as a promise: `contained_by` does not fold the old entry
in, and `partially_overlaps` does not extract anything. Both write the entry and record the
judgment, and the follow-through is the planner's next call — a retirement, or two more
registrations. Automating either would be the tool deciding that a function it has never seen
should be restructured — the tool computes and shows, the planner decides, which is the same line
§3.7 and §3.8 draw for the search and the report. The record is what makes the follow-through
checkable later; it is not a work queue, and this change adds no gap that counts one.

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

**So the glossary is wired, not merely invoked — the draft asserted this dependency and connected
it to nothing.** `TermService` is a constructor collaborator of `CatalogueService`, and every
registration runs the purpose line past `terms.violations()` and **warns without rejecting**,
returned alongside the entry. That is `RowService._vocabulary_note` applied to its second site,
and its reason transfers whole: *"naming happens at the point of least attention, and the moment
of typing is the only moment at which saying so changes anything."* A purpose line written in
retired vocabulary is a search that will never match, and a warning three days later arrives after
the line has been indexed against everything.

**The collaborator is not optional and the specification says so out loud**, because convention 11
makes an unpassed collaborator fail *silently* — its guard skipped, its effects omitted, the call
proceeding. A catalogue whose glossary is absent is exactly the lottery the paragraph above
describes, and it would look identical to a working one.

**Rejected: FTS5, and the reason is a measurement.** `engine/schema.py` ships a `source_fts`
virtual table and `references.py` writes to it. **Nothing reads it.** `ReferenceService.search`
claims *"retrieval is FTS5/BM25, with a substring fallback when FTS5 is absent"* and its
`_matches` helper is a plain lowercase substring scan; `source_fts` appears in exactly three
places in the engine — the DDL, one INSERT, and a comment. So there is no working FTS retrieval
here to borrow, only a docstring that says there is. Building one for the catalogue is a
different change with its own argument; borrowing the claim would be citing a row that says
something else.

**The ranking must be one function, called by both the search and the registration**, or the
candidates a planner is shown and the candidate they are required to adjudicate come from two
rankings that will drift.

> **STALE — the amendment below was reversed on 2026-07-30 and the build followed the
> reversal. See §12.1.** There is no `engine/lexical.py`; `CatalogueService` keeps `_rank`
> private and owns the tokeniser, and it does **not** take `TermService`, so the glossary
> warning in 3B.2 behaviour 9 and 3B.5 behaviour 4 is not built. Change 4 deleted the
> glossary's own near-match guard, leaving one caller, and deletes `violations()` outright.

**Amended 2026-07-29 by change 4: it is one function for more callers than this change has, so it
is not private to this service.** The ranking and the tokeniser live in **`engine/lexical.py`**,
built here and called by `CatalogueService`, by change 4's labels and by change 4's `define_term`
guard — which is D12's own instruction, since the glossary's never-built near-duplicate refusal is
this same mechanism. `04-labels.md` §11.1 carries the argument, and it is the shape
`RowService.lineage_root` already settled in this engine: the second application is the reason a
primitive lives in one place rather than on either caller.

**The tokeniser is not written here either. `TermService._tokens` already exists** — lowercased,
plurals folded on a trailing `s`, addresses stripped, with its reason quoted: *"the crudest possible
rule … because anything cleverer starts guessing."* It moves to `engine/lexical.py` and
`TermService._tokens` becomes a one-line delegation naming the canonical one, following
`GapService.lineage_root`. **The draft of this change was about to write a second one**, in the
change whose own subject is duplication.

**And stop words are not a task-local decision, which is what the draft called them twice.**
Change 4 measured what that leaves: ranking fourteen proposals against a ten-word candidate set,
the word `the` accounts for **46% of every match**, and three of the fourteen top-ranked candidates
— the one the registration makes mandatory to adjudicate — rest entirely on words most candidates
share. **A shared word therefore contributes in inverse proportion to how many of the candidates
contain it**, computed from the candidate set rather than from a maintained list of English. This
is not a threshold: no cut-off decides whether a word counts, and the weight only orders a list
whose top is taken regardless. **It changes no number in this document** — eligibility is
untouched, so the 74 registrations shown nothing, the 561 adjudications and the mean of 3.90 all
stand. `04-labels.md` §3.4 and §11.2 are the measurement.

**The ranking lives in packet 3B and not with the search.** The draft put it in 3C and had 3B's
registrations call it, which is a packet naming a call a later packet builds — the landing-order
inversion that has now appeared in all three changes. §3.10 says what the order actually is.

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

**One branch, one pull request, the suite green at the end.** Same shape as changes 1 and 2 and
for the same reason: the packets cannot be made independently green.

**The packet letters are not the landing order, and the draft's claim that they were is the
correction the cold read is proudest of.** Three inversions, and the third change running in which
this has happened:

| # | lands | why it cannot land later |
|---|---|---|
| 1 | **3A.0** — the `JUSTIFICATION_ROLES` entries | 2E.1's check refuses `catalogue.retire_reason` and `catalogue_comparisons.reason` the moment 3A.1's DDL exists. Declared last, the suite is red from 3A to 3E and the failure reads as a mistake rather than the sequencing it is. Exactly change 1's task 1A.0. |
| 2 | **3D.1** — the registry rows | 3B.2's `ContainerNotCatalogued` message tells the planner to catalogue the object first. That is text naming a call, and `door.scan` raises `UnreachableCall` on a payload naming a call the registry cannot resolve. |
| 3 | **`engine/lexical.py`**, inside 3B | 3B's registrations call the ranking, so it cannot be specified by 3C and built after them. It is task 3B.1 here, not 3C.1 — and by change 4's amendment it is a shared module rather than a private method, because two later callers need the same one (§3.7). |

**So the order is 3A.0, 3A.1, 3A.2, 3D.1, 3B, 3C, 3D.2, 3E** — and the two rules behind it are
worth stating in general, because they have now caught something in every change: *a packet that
emits text naming a call lands after the registry row for that call*, and *a guard lands no later
than the schema it must permit.*

**This change touches no methodology asset and therefore mints no revision.** Nothing populates
the catalogue until stage 8 exists, so a script step added now would instruct a planner to fill a
table nothing else in the interview reaches. `PLAN.md` item 10 stays **revision 6**.

## 4. Packet 3A — the schema

Schema version 9 → 10. Nothing else in this change can start until this lands.

### Task 3A.0 — the justification vocabulary, extended

**This lands before the DDL it describes, and that is the whole point of it being 3A.0.**

**Behaviours**

| | behaviour |
|---|---|
| 1 | `catalogue.retire_reason` and `catalogue_comparisons.reason` join `JUSTIFICATION_ROLES`. |
| 2 | The declared set becomes **eighteen** members, re-enumerated from `engine/schema.py` rather than restated. |
| 3 | Both are role 1 — why an act was performed — and the declaration says which act. |
| 4 | `JUSTIFICATION_ROLES` is keyed `table.column`, and 2E.1's check looks up the qualified name. |

**This task exists because change 2 built a check that will refuse this change's schema.** 2E.1
behaviour 2: a column named `reason`, `grounds` or `alternatives`, or ending in `_reason`, must be
a declared member. `catalogue.retire_reason` and `catalogue_comparisons.reason` are both, so
declared anywhere later than here the suite fails on 3A.1 and the failure looks like a mistake
rather than the sequencing it is — the same shape as change 1's task 1A.0.

**Behaviour 4 is a hole the cold read found in change 2, not in this change, and the count above
depends on it.** `TIMESTAMP_ROLES` sitting beside it is keyed by bare column name, and change 2
never said which `JUSTIFICATION_ROLES` was. Under bare-column keying `reason` and `retire_reason`
are already declared, **this change adds nothing, behaviour 2 is false and behaviour 1 is a no-op**
— a task specified against a check that would never have fired. Keyed `table.column`, this change's
two additions are real.

**Behaviour 2's count is eighteen, not eleven, and this is change 4's correction applied here
(`builds/04-labels.md` §11.3).** Eleven was arithmetic on change 2's "nine", and nine was never
enumerated. **Re-measured from source on 2026-07-30**, with the method stated so it can be re-run:
parse `engine/schema.py` with `_columns()`'s own regex — every `CREATE TABLE IF NOT EXISTS name
(…\n);`, every line matching `^(\w+)\s+(INTEGER|TEXT|REAL|BLOB|NUMERIC)` with comments stripped —
and select the columns 2E.1 behaviour 2 requires to be declared. That returns **255 columns and
these eleven, today, before any v3 change adds anything**:

`plan_rows.retire_reason` · `plan_versions.reason` · `gap_overlay.reason` · `warnings.reason` ·
`spikes.block_reason` · `subtasks.block_reason` · `obligation_amendments.reason` ·
`brief_rows.reason` · `scope_attachments.reason` · `terms.ban_reason` ·
`finding_reallocations.reason`

Change 2 adds `plan_rows.grounds`, `.alternatives`, `.supersede_reason` and the
`findings.rationale` → `.reason` rename, plus `technical_claims.evidence` as the declared
**non**-justification — **sixteen after change 2**. This change's two make **eighteen**. Change 1
renames `subtasks.block_reason` to `tasks.block_reason` and changes no count.

**Change 2's "three `reason` columns" is the error that propagated**: it is a bare-column count
where there are **seven** bare `reason` columns, and it omits `terms.ban_reason` and both
`block_reason`s entirely. **Change 2's specification owes the same re-enumeration**, and
`builds/02-decision-context.md` carries it.

**And bare-column keying is wrong on its own terms, which is why this is a correction and not a
choice.** The role differs per table: `behaviour_amendments.reason` names amending,
`scope_attachments.reason` names attaching, and `catalogue_comparisons.reason` names judging one
candidate against one proposal. A register whose entry is the *role* cannot be keyed by a name
that carries three roles. **Change 2's specification owes this same sentence** — the register it
builds is under-specified there, not here.

**Behaviour 3 applies change 2's own test rather than assuming the answer.** *A `reason` is
attached to an act and names a transition; `grounds` are attached to content and name no
transition.* `retire_reason` names retiring. `catalogue_comparisons.reason` names the comparison —
the act of judging — which is why the column is `reason` and not `grounds`, even though it reads
like an argument. The comparison row **is** the act; it has no content of its own to have grounds
for.

**No new `_at` role and no new suffix.** `retired_at`, `created_at` and `updated_at` are all
declared. Probed against the DDL below: **the parser sees all 20 new columns across both tables,
the only `_at` names are declared roles, `component_ref` is TEXT and all five `_id` columns are
INTEGER, and the two justification columns are exactly `catalogue.retire_reason` and
`catalogue_comparisons.reason`** — no third one hiding. The commit fields that would have needed a
`_commit` shape are not in this change (§3.9), so `SHAPES` is untouched.

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
| 5 | Exactly one of `task_id` and `component_ref` is set, as a `CHECK` — and which one is set is fixed by `kind`. |
| 6 | `kind`, `visibility` and `relationship` are constrained to their value sets, as `CHECK`s. |
| 7 | The version-9 DDL is retained as the fixture the parity check migrates from, **outside `engine/schema.py`**. |

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

**Behaviours 5 and 6 are `CHECK`s, and the argument that got them there is not the one the draft
made.** The draft said "well-formedness, not judgment", cited `plan.guard`, and stopped. That
argument does not survive contact with the schema: **`subtasks.state` enumerates its values in a
comment with no `CHECK`, and that is this schema's actual habit** — so "an enumeration should be
constrained" is not a rule anyone here follows, and `plan.guard` is a single-column constant test
that carries no cross-column exclusive-or. The precedent is withdrawn.

**The real argument is narrower and it is decisive: a value that appears in an index predicate must
be constrained, because a typo there does not fail — it removes the row from the invariant.**
`idx_catalogue_task_entry` is predicated on `kind = 'function' AND visibility = 'public'`. Write
`'Public'` and the row is simply not in the index, the task quietly acquires a second entry point,
and D6 is broken with nothing red. Same for `kind`. This is `COALESCE` again one index later: an
index that looks correct, runs green, and does not cover the rows it was written for.

**Which is also why behaviour 5 constrains *which* owner, not just that there is one.** The
draft's `CHECK ((task_id IS NULL) != (component_ref IS NULL))` lets a `kind='function'` row carry
a `component_ref` instead of a `task_id`, pass the check, and escape `idx_catalogue_task_entry`
entirely — the same NULL escape, through the same door, a third time. `kind` decides the owner
column and the schema says so.

**`relationship` gets one for a different reason**: it is not in an index predicate, but it selects
between the branch that writes the entry and the branch that refuses it (§3.6). A misspelt
relationship takes the permissive branch and writes the entry the planner had just said not to
write — a value whose typo silently inverts the change's central refusal.

**Behaviour 4 makes "exactly one public entry per task" a database invariant** rather than
something a service remembers to check — the same move `idx_obligation_live_owner` makes for
behaviour ownership, and the same reason. The "at least one" half is a gap and belongs to change
5, where tasks and pseudocode arrive together. **Probed: the index refuses a second live public
function entry for one task, and admits a private entry for the same task and any number of object
entries.** The `CHECK`s were probed in both directions too — two owners refused, no owner refused,
one owner accepted.

**Behaviour 7 continues the pattern change 2 made a pattern, with one sentence change 2 owes as
much as this change does.** The retained set grows by one text per schema change; they are text,
they diff, and they are never executed except by the parity check. **They must live outside
`engine/schema.py`.** `_columns()` in `test_schema_vocabulary.py` reads that whole file and
regexes every `CREATE TABLE IF NOT EXISTS` out of it, so a retained v9 DDL sitting there is phantom
schema for all five vocabulary tests — declaring columns that no longer exist and, in change 1's
case, resurrecting the very names the change renamed. §11.4 has the full argument; it is a
cross-change hole and changes 1 and 2 owe the same sentence.

**The DDL**

```sql
CREATE TABLE IF NOT EXISTS catalogue (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    container_id  INTEGER REFERENCES catalogue (id),  -- the object holding it; null at
                                                      -- module level. Not a path: location
                                                      -- is never identity.
    kind          TEXT    NOT NULL,
    visibility    TEXT    NOT NULL,
    purpose       TEXT    NOT NULL,      -- verb, object, qualifier; the whole of the search
    task_id       INTEGER REFERENCES tasks (id),      -- a function's owner
    component_ref TEXT,                                -- an object's owner
    retired_at    TEXT,                  -- null == live, and the only field that says so
    retire_reason TEXT,
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL,
    CHECK (kind IN ('object', 'function')),
    CHECK (visibility IN ('public', 'private')),
    -- Both value sets are constrained because both appear in idx_catalogue_task_entry's
    -- predicate below, where a typo does not fail: it drops the row out of the invariant.
    CHECK ((task_id IS NULL) != (component_ref IS NULL)),
    CHECK (CASE kind WHEN 'function' THEN task_id IS NOT NULL
                     ELSE component_ref IS NOT NULL END)
    -- ...and a function owned by a component would pass the line above while escaping
    -- idx_catalogue_task_entry entirely. Same NULL escape, one index later.
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_catalogue_live_name
    ON catalogue (name, COALESCE(container_id, 0)) WHERE retired_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_catalogue_task_entry
    ON catalogue (task_id)
    WHERE kind = 'function' AND visibility = 'public' AND retired_at IS NULL;

-- Read by 3B.4's ContainerNotEmpty check and by every container name -> id resolution.
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
    created_at   TEXT    NOT NULL,
    CHECK (relationship IN ('same', 'contains', 'contained_by',
                            'partially_overlaps', 'unrelated'))
    -- Constrained because a misspelling takes the branch that writes the entry: the
    -- typo does not fail, it inverts the refusal (§3.6).
);
```

**Five statements — two tables and three indexes — and the count is measured rather than
reasoned.** `schema.statements` splits on semicolons, and **the split is safe only because
comments are stripped first**: comment lines in this block contain semicolons. The 3E reader was
right to ask. Probed on the drafted DDL, which then carried a sixth statement:
`schema.statements(CATALOGUE_DDL)` yields exactly the statements written and nothing fragmented.
3E.1 asserts the number so that a builder who drops one gets a failure rather than a smaller
schema.

**`idx_comparisons_matched` was in the draft and is dropped.** Nothing in this change reads a
comparison back — 3D.1 says so explicitly — so the index has no query to serve. It belongs to the
change that surfaces prior verdicts on a search result, which is the same change-5 item §9 lists.
Shipping it now would be an unread index beside the unread fields §3.9 refuses to ship.

**`proposed` is a name and not a ref, and that is deliberate.** A comparison whose verdict is
`same` or `contains` produces no entry, so there is nothing to point at; the record has to carry
the name that was refused or it says nothing useful to the next planner. `entry_id` is null in
exactly those cases and is the field that distinguishes them.

**`catalogue_comparisons` has no `updated_at` and that is not an oversight.** It is an immutable
audit record, like `finding_reallocations` and `behaviour_amendments`; the vocabulary check's own
note says `updated_at` is *"absent on immutable tables by design"*.

**`catalogue` has one because an entry is mutable in two ways**: its purpose can be restated
(3B.5) and it can be retired (3B.4).

### Task 3A.2 — `Storage._migration_steps`, the 9→10 branch

**Signature.** Unchanged. Gains one branch.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Creates both tables and all three indexes, from `schema.CATALOGUE_DDL` via `schema.statements`. |
| 2 | Backfills nothing. |
| 3 | Adds nothing to the snapshot table set. |

**Behaviour 1 reuses `statements()` rather than restating the SQL**, which is what **three of the
four existing migration branches** do — 3→4 for `terms`, 5→6 for revisions, 6→7. Restating it here
would be the second copy behaviour 2 of 3A.1 exists to prevent.

**4→5 is the fourth branch and it is the interesting one**, because it is the mixed case: it issues
`ALTER TABLE` statements of its own alongside the block it takes from `statements()`. The rule the
four of them share is not "always call `statements()`" but **a whole table is created from the one
text; a column added to an existing table is an `ALTER` the DDL also carries.** This change is
purely the first kind, which is why behaviour 1 is unqualified.

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

Depends on 3A and on 3D.1 (§3.10). A new module, `engine/catalogue.py`, and `models.py`.

**The service is constructed with `Storage` and `TermService`, and neither is optional.** The
first is convention 3; the second is §3.7, and it is written here rather than assumed because
convention 11 makes an unpassed collaborator skip its guard and proceed.

**Two tasks were added at the front of this packet and the rest renumbered**, because the draft
consumed five models nothing defined and needed four distinct lookups against no read path. Both
are the same defect: a task specified in terms of machinery that no task builds.

### Task 3B.0 — the models

**Signature.** Five frozen dataclasses in `models.py`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | `CatalogueEntry` — `id`, `name`, `container` (a name, or `None`), `kind`, `visibility`, `purpose`, `owner` (a `task_id` or a `component_ref`), `retired_at`, `retire_reason`. |
| 2 | `Candidate` — a `CatalogueEntry` plus the score's two components and the words that matched. |
| 3 | `Comparison` — `matched` (a name and container, not an id), `relationship`, `reason`. |
| 4 | `Cluster` — the shared words, and every member entry with its container. |
| 5 | `CatalogueResult` — `entry: CatalogueEntry \| None`, `comparisons`, `use_instead: CatalogueEntry \| None`, `vocabulary_note: str \| None`. |

**This task exists because of a recorded v2 defect, quoted in the conventions register's own §2:**
the plan named `WriteBatch`, `RowSelector`, `TraversalSpec` and `GraphScope` and defined none of
them, *"so two implementers would have built two incompatible interfaces."* The draft named four
and defined none. The register is explicit that a return type's fields are **not** a convention —
they differ per task — so they are a hole in every task that leaves them out, and they are closed
here.

**Behaviour 3 is the load-bearing one and it settles three other tasks at once.** Whether a
comparison names its candidate **by name and container or by id** decides 3D.1's payload parser,
the shape a search result must hand back, and how 3B matches a supplied comparison against
`candidates[0]`. **By name and container**, for the reason 3D.2 behaviour 1 gives: a catalogue
entry is addressed by the name you were about to type, never by an ordinal, and a planner
answering an adjudication has the name in front of them because the refusal just printed it.

**Behaviour 1 carries the container as a *name*, not an id**, for the same reason, and it is what
makes a `CatalogueEntry` passable straight back into `catalogue_function`.

**Behaviour 2 carries the words that matched** because the whole ranking is lexical and a planner
asked to adjudicate a candidate needs to see *why* it ranked — a candidate that matched on `get`
alone is dismissed at a glance, and one that matched on `resolve supersession chain` is not.

### Task 3B.1 — the read path and the ranking

> **STALE in one respect — see §12.1.** As built there is no `engine/lexical.py`:
> `engine/catalogue.py` itself exports `tokens(text)`, `rank(...)` and `tied_at_top(...)`,
> and `TermService._tokens` delegates to `tokens` while keeping its own scope/address half.
> `word()` stays in `terms.py` as `_word`. Behaviour 11 reads: *the tokeniser and the ranking
> are the catalogue's, and `TermService._tokens` becomes a delegation.* Everything else in
> this task — behaviours 1 to 10 and 12 — is built as written.

**Signature.** A new module `engine/lexical.py` exporting `tokens(text: str, scope: str) ->
set[str]`, `word(term: str) -> str`, `rank(name: str, text: str, candidates, limit: int = 5)` and
the error `NearMatchesUnadjudicated`; plus four private methods on `CatalogueService`: `_find(name: str,
container: str | None, include_retired: bool = False) -> CatalogueEntry | None`,
`_resolve_container(name: str) -> int | None`, `_live_within(container_id: int) ->
tuple[CatalogueEntry, ...]`, and `_rank(name: str, purpose: str, limit: int = 5) ->
tuple[Candidate, ...]`, which reads the live entries and hands them to `lexical.rank`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | `_find` returns the one live entry with this name and container, or `None`; `container` is a name and `None` means module level. |
| 2 | `_resolve_container` returns the id of the live object entry with this name, or `None` when there is none. |
| 3 | `_live_within` returns the live entries whose container is this id. |
| 4 | `_rank` ranks live entries by shared words in the name and shared words in the purpose, both. |
| 5 | Name matches outrank purpose matches at equal counts. |
| 6 | An entry sharing nothing is not a candidate at any rank. |
| 7 | Ties break on the lower `id` first, so the ranking is stable across calls. |
| 8 | Returns at most `limit`. |
| 9 | A retired entry is never a candidate; `_find(include_retired=True)` is how the name check sees one. |
| 10 | A shared word counts in inverse proportion to how many of the candidates contain it, so a word almost everything shares decides almost nothing. |
| 11 | `tokens`, `word` and `rank` are `engine/lexical.py`'s, not this service's; `TermService._tokens` and `TermService._word` become delegations. |
| 12 | `rank` marks every candidate tied at the top score, and the registration refuses until **each** of them is adjudicated — not just the first. |

**Behaviours 1 to 3 are the read path the draft never specified**, and they are not three
incidental helpers: the registrations need a lookup **four** times — the name check, the container
name-to-id resolution, the `(name, container)` finder that 3B.4 and 3B.5 both start from, and
3B.4's "is this object still holding live entries". Plus the entry that every one of these calls
returns has to be read back from somewhere. Left unspecified, five tasks each invent their own
query, which is this change's own subject matter happening inside this change.

**`_resolve_container` and `_live_within` are what `idx_catalogue_container` exists for**, which is
why that index survives §4's cull and `idx_comparisons_matched` does not.

**Behaviour 4 is the both-directions search stated as one function**, which is the design's own
point: one query answers two questions, so it costs nothing to look for both.

**Behaviour 5 encodes which defect is more expensive to miss.** A name collision is the one that
bit this build three times in a sitting; a description collision is the one the catalogue is
primarily aimed at. Ranking name matches first is a preference and is stated as one, so a later
change can argue with it.

**Behaviour 7 reads `id` and not `created_at`, and the draft's "older entry first" was not a
stability guarantee at all.** Two entries written in the same clock tick share a `created_at` —
`clock.now()` is microsecond precision but a batch write can land inside one — and their order is
then whatever SQLite returns. `id` is the only total order this schema guarantees. **The
registration refuses until the *highest-ranked* candidate is adjudicated**, so an unstable ranking
makes the required answer change between the call that showed the candidates and the call that
answers them: the planner adjudicates what they were shown and is refused for not adjudicating
something else. This is a one-word correction that decides whether the change's central refusal is
usable.

**Behaviour 9 is the implementation site the draft's "a retired entry is still consulted for the
name check" never had.** It was stated as a property in 3B.4 and nothing anywhere could perform
it.

**The draft's "the entry being registered is never its own candidate" is deleted.** At registration
the entry does not exist yet, so there is nothing to exclude; `search_catalogue` has no entry being
registered at all. The only exclusion it could have implemented is **name equality — which would
hide the exact name collision the search exists to find.** Dead text that would have been
implemented as the opposite of the requirement.

**The limit is a page size and not a threshold.** It bounds what is displayed, not what counts as
similar; `references.search` already carries `limit: int = 10` for the same job. 5 is chosen
against the measurement in §3.5, where a page of five shows a mean of 3.90.

**Behaviours 10, 11 and 12 are change 4's amendments and `builds/04-labels.md` §11 carries the
arguments.** Behaviour 10 is what the draft left as "task-local": measured over a real candidate
set, the commonest English word in it accounted for 46% of all matching and put noise at the top of
the list, which is where this change makes adjudication mandatory. Behaviour 11 is where the
functions live, and the reason is that **two** callers need them — this catalogue and change 4's
glossary guard — and neither owns them. `word()` joins `tokens()` there for the same reason it
applies to the tokeniser: the moment a second module normalises a word, one copy is the canonical
one and the other is a copy.

**Behaviour 12 is behaviour 7's other half, and it is a real hole rather than a refinement.**
Behaviour 7 makes the ranking *stable*, which is necessary — the argument above stands unchanged.
It does not make the top of the ranking *meaningful* when several candidates score identically:
the `id` tie-break then decides which candidate a planner is compelled to write a sentence about,
and the equally-ranked alternatives are never adjudicated at all. **Measured over change 4's
fourteen probes against ten candidates: the top score is a tie for 4 of 14 unweighted and 2 of 14
weighted, with a four-way tie in the worst case.** So behaviour 7 orders the display and behaviour
12 sets the obligation, and the two do different jobs.

**Behaviours 10 and 12 change no number in this document.** A shared word is still a shared word,
so eligibility — and with it the 74 registrations shown nothing, the 561 adjudications and the mean
of 3.90 — is untouched: a tie changes *which* comparisons a registration needs, not *whether* it
needs one. Only the order changes, and with it which candidates a planner must answer for.

### Task 3B.2 — `catalogue_object`

**Signature.** `catalogue_object(self, name: str, purpose: str, visibility: str,
component_ref: RowRef | str, idempotency_key: str,
comparisons: tuple[Comparison, ...] = ()) -> CatalogueResult`, on `CatalogueService`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Writes one `object` entry owned by the component, and returns it. |
| 2 | Refuses with `PurposeRequired` when `purpose` is blank, and `ReasonRequired` when any comparison's `reason` is blank. |
| 3 | Refuses with `RefNotFound` unless `component_ref` addresses a row that is **both** in `components` and live, naming it and what it actually is. |
| 4 | Refuses with `NameTaken` when a live entry already holds this name at module level, naming it. |
| 5 | Refuses with `NearMatchesUnadjudicated` when the search returns candidates and the highest-ranked one has no comparison, naming every candidate shown. |
| 6 | Refuses with `UnresolvableRef` when `purpose` or a comparison `reason` cites a `table:ordinal` that resolves to nothing, naming the token. |
| 7 | Returns without writing an entry when the comparison on the highest-ranked candidate is `same` or `contains`, recording the comparison and naming the entry to use. |
| 8 | Every supplied comparison is written, whether or not an entry was. |
| 9 | The purpose line is checked against the glossary, and retired vocabulary is returned as a warning without refusing. |
| 10 | One transaction, one op batch. |
| 11 | A replay that would have written an entry is refused with `NameTaken` naming the row the first call wrote; a replay of a `same`/`contains` call returns the original receipt. |

**The refusal order is the pseudocode's order and the two now agree.** In the draft they did not,
and the mismatch was not cosmetic: with the name check *after* the adjudication check, an exact
name collision would surface as `NearMatchesUnadjudicated` — because an exact match ranks first —
so the planner would be told to adjudicate a candidate when what they needed to be told is that the
name is taken. Cheap checks on the caller's own arguments run first; the lookups run next; the
search runs last because it is the expensive one.

**Behaviour 3 checks the component is live *and is a component*, and the draft checked neither
properly.** `RowService.get` takes any ref, so `catalogue_object(component_ref="requirements:4")`
was accepted and produced an object owned by a requirement. Both halves matter: an object owned by
a superseded component is an entry whose owner has moved, and the report groups by owner. The
error is `RefNotFound` and not a new name because the codebase already has that name for exactly
this.

**Behaviour 4 is the index in §3.3 reported as a refusal rather than as an `IntegrityError`.**
The service checks before writing so the message can name what already holds the name; the index
is what makes the check true rather than merely attempted. Both, deliberately — the same
arrangement `submit_rows` has with `idx_rows_live_name`. **And the message carries a retired
entry when it finds one**, with its retire reason: that is 3B.1 behaviour 9's reason for existing,
and the design's own argument — the planner may be undoing somebody's decision without knowing it.

**Behaviour 2's second half closes an `IntegrityError` on this change's central write path.** A
comparison `reason` is `NOT NULL`, and a blank one had no refusal in front of it, so the honest
answer "I have not written why" would have surfaced as a database error naming a column. It gets a
named refusal like every other required justification in this engine.

**Behaviour 6 is §10's proposed convention applied, and it needs its own error name.** The draft
specified the check and named no error for it, which is the shape convention 9 exists to prevent.
It matters more here than where change 2 met it: a comparison `reason` cannot be rewritten, so an
unresolvable ref in one makes the row permanently unreadable through the door. **And the trap
change 2's probe found is promoted by this behaviour** — a URL with a port reads as
`table:ordinal`, and where change 2 left it rendering oddly, here it *refuses the write*. So the
refusal names the token, and the planner can see it is their `localhost:8080` and not a citation.

**Behaviour 7 is §3.6, and it is a deliberate override of convention 1**, written here because the
register requires an override to be written in the task rather than upstream. Convention 1 says a
named error is raised and never reported as a status field in a success payload; `CatalogueResult`
with `entry=None` is exactly such a field. The override's reason is §3.6's: the planner did the
right thing, the call did what it exists to do, and a comparison **was** committed — an exception
path that also commits a write is a shape nothing else in this engine has. `use_instead` carries
the entry, so nothing has to be looked up to act on it.

**Behaviour 9 is §3.7's glossary dependency made real**, and it warns rather than refuses for
`_vocabulary_note`'s reason: a retired word inside a quotation of the owner is legitimate, and a
check that refused those would have the tool editing his words.

**Behaviour 11 replaces the draft's "replaying the idempotency key returns the first result",
which was unreachable.** Every guard above runs *before* `write_atomic`, so a replayed
entry-writing call never reaches the receipt — it hits `NameTaken` on the row the first call wrote.
That is the correct outcome and it is now stated as one. The case where replay does its job is
`same`/`contains`: no entry was written, no name is taken, the call reaches `write_atomic` and the
receipt suppresses a duplicate comparison row.

**And `idempotency_key` is required, not defaulted.** The draft gave it `= ""`, which means the
first defaulted call's receipt replays for **every** later defaulted call in that database — every
registration after the first silently returning the first one's result. It is required here as it
already is on 3B.4 and 3B.5, which is why the signature reorders the parameters.

**Pseudocode**

```
if not purpose.strip():
    raise PurposeRequired naming the name
for c in comparisons:
    if not c.reason.strip():
        raise ReasonRequired naming c.matched
refuse_unresolvable_refs(purpose, [c.reason for c in comparisons])   # UnresolvableRef
component = rows.get(component_ref)                   # RefNotFound naming the ref
if component.table != "components" or not component.is_live:
    raise RefNotFound naming the ref and what it actually is
existing = self._find(name, container=None, include_retired=True)   # 3B.1
if existing and existing.is_live:
    raise NameTaken naming it
candidates = self._rank(name=name, purpose=purpose)                 # 3B.1
if candidates and no comparison names candidates[0]:
    raise NearMatchesUnadjudicated naming every candidate shown
verdict = the comparison naming candidates[0], if any
note = self.terms.violations(purpose) or None
if verdict in (SAME, CONTAINS):
    ops = [insert each comparison, entry_id null]
    write_atomic(ops, idempotency_key)
    return CatalogueResult(None, comparisons, use_instead=candidates[0],
                           vocabulary_note=note)
ops = [insert the entry] + [insert each comparison, entry_id borrowed from op 0]
write_atomic(ops, idempotency_key)
return CatalogueResult(entry, comparisons, use_instead=None, vocabulary_note=note)
```

`FromOp` is what lets the comparisons borrow the entry's assigned id inside one transaction; it
exists for exactly this and its docstring gives the reason — a parent and its children split
across two transactions leaves a parent with no children when a crash lands in between.

### Task 3B.3 — `catalogue_function`

**Signature.** `catalogue_function(self, name: str, purpose: str, visibility: str, task_id: int,
idempotency_key: str, container: str | None = None,
comparisons: tuple[Comparison, ...] = ()) -> CatalogueResult`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Writes one `function` entry owned by the task, and returns it. |
| 2 | Everything 3B.2 refuses, refused the same way and in the same order. |
| 3 | Refuses with `ContainerNotCatalogued` when `container` names no live object entry, naming it and saying to catalogue the object first. |
| 4 | Refuses with `TaskNotFound` when `task_id` is not a task, naming it. |
| 5 | Refuses with `EntryPointExists` when `visibility` is `public` and the task already has a live public entry, naming it. |
| 6 | A `container` of `None` is module level, and is not an error. |
| 7 | `NameTaken` is checked against **this container**, not against module level. |

**Behaviour 7 is a one-word correction with a real consequence.** 3B.2's behaviour reads "a live
entry already holds this name at module level", which is right for an object and wrong here:
inherited verbatim, `catalogue_function("_hydrate", container="RowService")` would be refused
because a module-level `_hydrate` exists — the exact case §3.1 uses to argue the whole table's
identity. The check is `_find(name, container)`.

**Behaviour 3 is what makes the container safe to be a foreign key.** The container is supplied
as a *name* because that is what a planner has in hand, and `_resolve_container` turns it into an
id; an unresolvable one is refused rather than created, because creating it would be the tool
deciding that a new object exists.

**Behaviour 3's message is why this packet lands after 3D.1** (§3.10). "Catalogue the object
first" names a call, and `door.scan` raises `UnreachableCall` on outgoing text naming a call the
registry cannot resolve. Written before the registry row exists, the tool refuses its own refusal.

**Behaviour 5 is the index of 3A.1 behaviour 4, reported as a refusal.** It is D6 stated as a
constraint: a task is one externally-callable function, so a second one means either the task is
two tasks or the name is wrong, and both are worth stopping for.

**A sequencing consequence that bites now and stops biting at change 5.** `task_id` references a
row in `tasks`, and in this change tasks are still derived at finalization from contract rows —
so until change 5 moves task creation to stage 8, function entries can only be catalogued for a
plan that has been finalized. That is awkward for the end-to-end drive of this change and it is
not a defect: the catalogue's real population happens at stage 8 and change 5 is what builds it.
Object entries have no such constraint, because a component is a plan row and exists from stage 6.

### Task 3B.4 — `retire_catalogue_entry`

**Signature.** `retire_catalogue_entry(self, name: str, container: str | None, reason: str,
idempotency_key: str) -> CatalogueEntry`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Stamps `retired_at` and `retire_reason`, and returns the entry. |
| 2 | Refuses with `RetireNeedsReason` when `reason` is blank. |
| 3 | Refuses with `EntryNotFound` when no live entry holds this name and container. |
| 4 | Refuses with `ContainerNotEmpty` when the entry is an object still holding live entries, naming them. |
| 5 | A retired entry is never returned as a search candidate, and a later `NameTaken` or `EntryNotFound` naming this name carries it and its retire reason. |
| 6 | Retirement is never undone; the name is free for a new entry, which is a new row. |

**Behaviour 2 reuses the error name change 2 gives `retire_row`**, because it is the same
refusal for the same reason and a second spelling of it is what this whole family of documents is
about.

**Behaviour 4 exists because the container is a foreign key**, and `_live_within` is the query
that answers it. Retiring an object whose methods are still live leaves entries pointing at a dead
container, and the report groups by it. Naming the survivors is what makes the refusal actionable.

**Behaviour 5 is `FUNCTION_CATALOGUE.md` §8, and the draft stated it as a property with nowhere to
happen.** *"A retired entry is still consulted for the name check"* was true of nothing: no call
looked, and the search excluded retired entries by definition. It is a *delivery* obligation, so
it is written as one — the retired entry surfaces in the refusal text of the two calls that would
have found it. The reason is the strongest sentence in the design: a dead function cannot be
reused and offering it as a candidate is a confidently wrong answer, but **the thing about to be
written may have been removed on purpose, and the planner may be undoing somebody's decision
without knowing it.** Delivered nowhere, that argument protects nobody.

**Behaviour 6 is the reintroduction case, and the design's ruling stands.** A function written,
removed and written again is precisely the case that suggests something was wrong with the
original design, and nulling the retirement erases that history at the moment it becomes
interesting. The lineage is a query — every entry with this name and container, oldest first —
and no edge type is added, because the edge vocabulary is deliberately closed.

### Task 3B.5 — `restate_purpose`

**Signature.** `restate_purpose(self, name: str, container: str | None, purpose: str,
idempotency_key: str) -> CatalogueEntry`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Replaces `purpose` in place and stamps `updated_at`. |
| 2 | Refuses with `PurposeRequired` when blank, and `EntryNotFound` when there is no live entry. |
| 3 | Refuses with `UnresolvableRef` on the same terms as 3B.2 behaviour 6. |
| 4 | The new purpose is checked against the glossary and warns without refusing. |
| 5 | Recorded comparisons are untouched. |

**In place, and this is a deliberate departure from every other justification-bearing field in
the store.** Change 2 made `grounds` write-once because an argument that can be rewritten is a
place to revise history quietly. A purpose line is not an argument; it is an index entry, and
nothing cites it. Forcing a retirement and a re-registration to fix a wrong verb would poison the
one measurement the commit fields were carried for — churn is designed-and-dead-quickly, and it
stops meaning anything if typos produce dead entries.

**Behaviour 5 is the honest cost.** A comparison recorded against the old wording is not
re-adjudicated, so a restatement can leave an `unrelated` verdict standing against an entry it no
longer describes. The alternative — invalidating comparisons on restatement — makes restating
expensive again and re-creates the problem this call solves. The comparison records what was
judged and when; the change feed records the restatement.

## 6. Packet 3C — the search and the report

Depends on 3B's module. Read-only.

**The ranking is not here.** It was task 3C.1 in the draft and is now 3B.1, because 3B's
registrations call it — §3.10's third inversion.

### Task 3C.1 — `search_catalogue`

**Signature.** `search_catalogue(self, query: str, limit: int = 5) -> tuple[Candidate, ...]`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Ranks live entries against a free-text query by calling `_rank(name=query, purpose=query)`. |
| 2 | Each candidate carries name, container name, purpose, kind, visibility and owner. |
| 3 | Returns an empty result for a query that matches nothing, and that is not an error. |

**Behaviour 1 is stated as the exact call because the draft's `_rank` signature could not serve
it.** `_rank` took three arguments — name, container, purpose — against one free-text query, with
no rule for what the search should pass. The `container` parameter had no semantics and every call
site passed `""`, so it is dropped (3B.1), and the query goes into **both** remaining arguments.

**Passing the query twice is right, and it is worth saying why, because it reads like
double-counting that would collapse behaviour 5 of 3B.1.** It does not. An entry scores on words
appearing in **its own** name and **its own** purpose; the probe is only the source of the words.
So an entry that matches the query in its name *and* in its purpose is a genuinely stronger match
than one matching in either alone, and the name-outranks-purpose preference is a property of the
entry side, untouched. A cold reader drew the opposite conclusion from the same fact, which is why
the argument is written down rather than left to be re-derived.

**Behaviour 2 carries the container's *name* and not its id**, because a caller reading a result
needs to be able to pass it back to `catalogue_function`, which takes a container name.

### Task 3C.2 — `catalogue_clusters`

**Signature.** `catalogue_clusters(self, limit: int = 20) -> tuple[Cluster, ...]`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Groups live entries by shared purpose vocabulary. Containers are **reported**, never filtered on. |
| 2 | Orders by how much they share; no cut-off, no notification, no gap. |
| 3 | Each cluster names the shared words and every entry in it, with its container. |
| 4 | Module-level entries participate on the same terms as any other. |

**Behaviour 1 is a correction, and the two halves of the draft cancelled each other.** It said
group entries *"whose containers differ"* and, four lines later, that module-level entries *"share
the empty container"* — so no two module-level entries could ever cluster. Against §3.2's
measurement that is not a corner case: **56 module-level functions and every one of the 204
objects sit at module level**, and the report would have been blind to all of them. The container
filter goes; the report groups on the thing it is named for, shows the containers, and lets the
reader see that two entries share a container as easily as that they do not.

**Two entries in the same container that share vocabulary are also worth seeing**, which is the
positive case for the same change: `RowService.get_row` and `RowService.fetch_row` is duplication
of exactly the kind this table exists to catch, and the draft filtered it out by construction.
"Cross-container" names where the *design* expected to find things, not a predicate.

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

`surface.py`, `render.py`. **3D.1 lands before packet 3B and 3D.2 after packet 3C** — §3.10.

### Task 3D.1 — the registry

**Behaviours**

| | behaviour |
|---|---|
| 1 | Six tools are added to the **planning** surface, all `DEVIATION`, each appearing in `ADDED` with its reason. |
| 2 | A `comparisons` payload parser accepts a list of `{matched, container, relationship, reason}`, rejecting an unknown relationship by name. |
| 3 | The four writing tools carry `writes=True`; the two reads do not. |
| 4 | Every parameter of all six carries a `Param.note`. |
| 5 | No contract row is superseded, and no `Absence` entry is filed. |

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
cements whichever number the builder guessed — and the draft's number was wrong at both ends,
which two readers caught independently.** The arithmetic, from this change's own cited premises:

| | |
|---|---|
| v2's planning surface today | 54 |
| change 1 removes | **4** — `declare_package`, `assign_task`, `packaging` and **`split_subtask`** |
| change 2 adds | 1 — `record_grounds` |
| this change adds | 6 |
| **after this change** | **57** |

**`split_subtask` is the one that was missed**, and change 1 is explicit about it: task 1C.3
deletes the call, and convention 12 takes its registry row and its `split` payload parser with it.
Three removals was a count of the *renaming* work, and the fourth tool left the surface for a
different reason. `ADDED` moves the same way — 12 today, minus the three deviations that go
(`split_subtask` is not among them; it cites a contract), plus `record_grounds`, plus these six —
**16**.

The draft said 60, which is the number you get by adding six to 54 and forgetting both intervening
changes. **The paragraph arguing that an unstated count gets cemented at whatever the builder
guessed stated one and cemented the wrong one**, which is a sharper argument for the rule than the
paragraph made.

**Behaviour 3 also miscounted itself**: the table above lists **two** reads, not three, and four
writes. `search_catalogue` and `catalogue_clusters` are the reads.

**Behaviour 4 is not padding, and `surface.py` says why in its own words**: `Param.note` is *"the
whole of the tool's documented interface, so it says what the caller must decide — never what the
implementation does with it."* Three of these tools take a parameter whose whole difficulty is
knowing what to put in it — `visibility`, `container` and `comparisons` — and a caller who cannot
tell whether `container` wants a name or a ref will pass the wrong one and read
`ContainerNotCatalogued` as a bug in the tool.

**Behaviour 5 is the correction to the instinct, and change 2's cold read is why it is stated.**
No contract row describes any of this — the frozen plan never anticipated a catalogue, so it
cannot have anticipated the calls — which is exactly what `DEVIATION` means and why each carries
a written reason in `ADDED`. No `Absence` entry is filed either: an absence records a call that
**exists** and is deliberately not exposed, and none of these was ever built before.

**Behaviour 2 carries `container` because a comparison names its candidate by name and container**
(3B.0 behaviour 3). A bare name cannot identify a candidate in a table whose identity is a pair,
and the parser is where that would first go wrong.

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
| 3 | A `purpose` and a comparison `reason` are `door.Verbatim`: served as written, with every ref they cite resolved **alongside** them. |

**Behaviour 1 is the naming discipline applied to a table that has no refs.** A catalogue entry
is addressed by name and container, following `terms`, which is looked up *"by the word you were
about to type, never by an ordinal"*. So `door.scan` never sees a `catalogue:` address in outgoing
text, and `resolver_from` needs no third lookup — unlike `findings`, where the absence of one
made every `findings:3` in the owner's prose read as *no live row at this address* (F38).

**Behaviour 3 is a correction, and the draft had it exactly backwards.** It said refs inside those
fields *"are rendered as `name (ref)`"* — an inline rewrite of stored prose, which is the one thing
the door's design forbids. `Verbatim` is *"stored prose, served as written"*, and the door
**annotates alongside**: `render` appends the resolution of every address the prose cites and hands
the text back untouched. Its docstring says why the alternative broke the tool — annotation that
changes a value's shape turns an identifier a caller reads and passes back into an object.

**A `purpose` and a comparison `reason` are stored prose, so `Verbatim` is what they are**, and
this is a case where the type carries the rule so nothing rots: the value's own type exempts it
from the `BareAddress` invariant, rather than a list of exempt fields that has to be maintained.
A comparison's `reason` is argumentative prose — *"different thing: this one is about the contract,
see components:6"* — and that address is the planner's own writing, which the tool does not edit.

**The write-time check is the other half and it belongs to 3B, not here** (3B.2 behaviour 6), for
the reason `record_grounds` behaviour 6 gives: combined with a field nothing can rewrite, an
unresolvable ref makes the row permanently unreadable through the surface. `purpose` is restatable
and so is repairable; a comparison `reason` is not, which makes the check matter more here than
there. Change 2's probe against realistic justification prose found one trap, a URL with a port;
that probe stands and is not re-run, but **its consequence is worse here** — where change 2 left
such a token rendering oddly, this change refuses the write over it. That is why 3B.2 behaviour 6
names the token in the refusal.

**This is now the third task to reach the same answer**, and per the register's own growth rule it
is proposed as a convention entry — see §10.

## 8. Packet 3E — the enforcement

Depends on all of the above. **The justification-vocabulary task that was 3E.1 in the draft is now
task 3A.0 and lands first** — §3.10.

### Task 3E.1 — the store's own invariants, and the index that must be shown to work

**Behaviours**

| | behaviour |
|---|---|
| 1 | A version-9 database migrated to 10 is structurally identical to a fresh 10 — raw `PRAGMA table_info`, `index_list`, `index_info` and `foreign_key_list` output, compared as-is. |
| 2 | `schema.statements(CATALOGUE_DDL)` yields five statements. |
| 3 | Two live module-level entries with the same name are refused. |
| 4 | The same name in two different containers is accepted. |
| 5 | A retired name is available again, and the new entry is a new row. |
| 6 | A task cannot hold two live public function entries. |
| 7 | An entry with two owners, or none, is refused; so is a `function` owned by a component and an `object` owned by a task. |
| 8 | `kind`, `visibility` and `relationship` refuse a value outside their set. |
| 9 | The 9→10 migration writes no catalogue row, and `snapshot_version` still carries nine tables. |
| 10 | `_columns()` finds `catalogue` and `catalogue_comparisons`, and no table the retained v9 fixture declares. |

**Behaviours 3 to 8 are asserted at the store, with raw SQL, and this is the correction that
matters most in this packet.** Driven through the service instead, **behaviour 3 passes on the
naive index**: a second entry with an identical name ranks first in `_rank`, so
`NearMatchesUnadjudicated` refuses the call before the index is ever reached. The test would be
green, the refusal would be the wrong one, and the defect §3.3 exists to prevent would ship — a
check running green while measuring something narrower than its name, which is exactly the failure
this project has recorded twice. The same applies to behaviour 6: a service guard that happens to
agree with a constraint proves nothing about the constraint.

**Behaviour 3 is the whole reason this task is not just a parity check**, and the reason is not the
one first given here. **Corrected from `builds/04-labels.md` §11.3, probed 2026-07-29:** `PRAGMA
index_list` does report the naive index and the `COALESCE` index identically, but **`index_info`
distinguishes them** — an expression column reports `cid = -2` and a NULL name — so it is not true
that the pragmas cannot tell them apart. **Parity is blind for a better and more general reason:
both sides are built from the same DDL text**, so it catches a *missing* block and can never catch a
*wrong-but-consistent* index. A parity check written against a naive index would compare it happily
with itself. The assertion has to be the behaviour, and it is the one assertion in this change that
would catch a builder writing the obvious thing.

**Behaviour 1 adds `index_info`, which the draft omitted.** `index_list` names the indexes; only
`index_info` says which columns each covers. Without it the parity check is blind to
`idx_catalogue_container`'s columns entirely — an index could migrate as a name over the wrong
column and parity would report a match.

**Parity is close to unfailable here and that is the point, not a defect.** Both sides are built
from one text, which is the invariant 3A.1 behaviour 2 exists to hold; parity's job is to catch a
migration that omits the block, and every substantive question about the indexes is behaviours 3
to 8's business.

**Behaviour 9 exists because nothing verified 3A.2's two negative behaviours.** "Backfills
nothing" and "adds nothing to the snapshot table set" are both claims a builder could quietly
break — a helpful backfill, or a `catalogue` added to `snapshot_version` on instinct — and neither
would fail anything else. The snapshot half is the one with teeth: §4 argues that a catalogue
inside the snapshot set would be rewound while its `tasks` rows were not.

**Behaviour 10 is the guard on the guard.** `_columns()` parses `engine/schema.py` with a regex,
so if the new tables are declared in a shape it does not match, every vocabulary check passes while
seeing nothing of this change — and `test_the_check_can_actually_fail`'s `> 100` floor is far too
loose to notice. Its second half is §11.4: the retained v9 fixture must be invisible to the parser,
which is the assertion that proves it lives outside `schema.py`.

### Task 3E.2 — the size and the shape

**Behaviours**

| | behaviour |
|---|---|
| 1 | The planning registry holds **57** tools, `ADDED` holds **16**, and every `DEVIATION` among the six appears in `ADDED` with a reason. |
| 2 | A registration with candidates and no comparison is refused, and the refusal names every candidate. |
| 3 | A `same` verdict writes the comparison, writes no entry, and returns the entry to use. |
| 4 | The ranking a registration adjudicates against is the ranking `search_catalogue` returns for the same input. |
| 5 | A registration naming a container that is not a live object entry is refused, and the refusal passes `door.scan`. |
| 6 | An exact name collision is refused as `NameTaken`, not as `NearMatchesUnadjudicated`. |

**Behaviour 4 is the one a builder would skip**, because each half looks covered by a unit test of
its own. It is what makes §3.7's "one ranking function" a mechanism rather than a sentence: two
rankings would let a planner be shown one candidate and required to adjudicate another, and every
individual test would still pass.

**Behaviour 5 is the landing-order inversion made into an assertion.** `ContainerNotCatalogued`
names a call, so the refusal only survives the door if 3D.1's registry rows exist. Asserting that
the refusal *renders* — rather than that it is raised — is what catches the ordering being undone
later, and this project's standing evidence is that a missing route reports a refusal reading like
the caller's mistake (F39).

**Behaviour 6 asserts the refusal order**, which is a decision two tasks make jointly and neither
would fail alone: 3B.2's pseudocode order and 3B.3's container-scoped name check. Get it wrong and
the tool answers a name collision by asking the planner to adjudicate it.

## 9. What this change does not do

**It does not populate anything.** Nothing in the interview as it stands reaches the catalogue, so
after this change the table is empty and stays empty until change 5 writes tasks, pseudocode and
entries at stage 8. This change builds the instrument; change 5 is what uses it.

**Two different eights, said once so the rest of this document is unambiguous.** The interview
running today is v2's **eight stages**; every "stage 8" in this document means the eighth of
v3's **eleven** (`INTERVIEW.md` §2), which is detailed design and does not exist until change 5.

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

**It does not act on a `contained_by` or a `partially_overlaps` verdict** — §3.6. The judgment is
recorded and the follow-through is the planner's next call. No gap counts them, because the
denominator is a table nothing populates until change 5.

**Three items change 5 inherits from this change, listed together so they are not rediscovered:**
the stage-8 script step that reads the report; the prior-verdict field on a search result; and the
"at least one public entry per task" gap.

**Two sentences this change owes to earlier ones, because their specifications are wrong without
them and nothing else will notice:** change 2 must say that `JUSTIFICATION_ROLES` is keyed
`table.column` (3A.0), and changes 1 and 2 must say that their retained DDL fixtures live outside
`engine/schema.py` (3A.1 behaviour 7, §11.4).

**And two amendments this change received from change 4, applied above on 2026-07-29 rather than
left as a refactor**, because this change is merged and unbuilt: the ranking and the tokeniser are
`engine/lexical.py` and not private to `CatalogueService` (§3.7, task 3B.1 behaviour 11), and stop
words are answered by a rarity weight rather than left task-local (task 3B.1 behaviour 10). Neither
changes a number measured here. `04-labels.md` §11 is the argument and the measurement.

> **The first of those two was itself reversed on 2026-07-30, and the build followed the
> reversal — §12.1.** The rarity weight (behaviour 10) stands and is built. The shared module
> does not: there is no `engine/lexical.py`, `CatalogueService` keeps `_rank` private and owns
> the tokeniser, and it takes no `TermService`. With change 4's own near-match guard deleted
> there is one caller, and change 4 deletes `violations()` with its three enumerated call
> sites — a fourth added here would make that count wrong.

## 10. Two conventions this change proposes

**Validate refs in stored prose at the write.** *A free-text field that will be rendered through
the door is checked at the write for `table:ordinal` tokens that do not resolve, and the write is
refused naming the token, and the field is served `Verbatim` thereafter.* Change 2 reached this
for `grounds` and `alternatives` (2B.2 behaviour 6) with a probe behind it; this change reaches it
again for `purpose` and a comparison `reason`. **That is the third task, which is the register's
own bar** — an entry is proposed when the same uncited decision appears in three tasks with the
same answer — so it goes to `CONVENTIONS.md` with change 2's probe as its evidence.

**The `Verbatim` half is written into the entry deliberately**, because leaving it out is how this
change got it wrong: the draft specified the write-time check correctly and then had the renderer
rewrite the prose inline, which is the opposite of what the door does. The two halves are one
decision — *check it at the write, then never touch it again* — and an entry stating only the
first invites the second mistake.

**Strip on store**, proposed by change 2 as its second occurrence, reaches its third here:
`name`, `purpose` and a comparison `reason` all need the same answer. It goes to `CONVENTIONS.md`
in this change.

## 11. The cold read, and the corrections it owes

**Four readers, one per packet group — 3A, 3B, 3C+3D, 3E. All four reported zero tool uses.** Each
was given its packet verbatim, the §3 sections it depends on verbatim, the adjacent packets
verbatim, the conventions register, and the source a builder would hold.

**Everything below is applied to §1–§10, and this section stays as the record.** It is written out
in full because the readings cost about six minutes of wall clock and the evidence exists nowhere
else — the measurements, the probe results, and the two findings the readers got wrong.

**Task numbers below are the draft's.** Applying the corrections moved three tasks: the
justification vocabulary from 3E.1 to **3A.0**, the ranking from 3C.1 to **3B.1**, and the four
registrations down one to make room for **3B.0**, the models. Read a `3B.n` here as `3B.n+1` above.

### 11.1 What was re-measured, and what the numbers actually are

Every count in §3 was taken from an AST parse of the engine, treating a class as an object entry, a
method as a function entry with that class as its container, and a module-level `def` as a
function entry with no container. **The method was never stated, which is itself a finding: a
denominator produced by an unnamed method is not checkable.**

**And stating it took two attempts, which is worth recording.** The version written into §2 while
applying these corrections said `engine/*.py`, 30 modules, and named the two entry shapes — and
re-running it reproduced 30 modules and 204 objects but **260 public functions, not 255**. Two
things were missing: `engine/*.py` matches 29 modules, not 30 (`engine/methodology/__init__.py` is
the thirtieth), and **functions nested inside functions are excluded** — five of them, with no
identity `(name, container)` can address. With both, the parse returns 204 objects, 464 functions,
33 dunders, 255 public and 176 private exactly. §2 now carries the full method.

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

## 12. What the build found

**Built and merged 2026-07-31.** Schema 10, 647 tests green (561 before), 57 tools. One entry
per thing the specification did not say, said wrongly, or could not have known — this is where
the next change's cold read starts, and it is the section changes 1 and 2 made a habit.

### 12.1 The reversal the document still carried

**`engine/lexical.py` is not created, and §3.7, §9 and task 3B.1 behaviour 11 are stale.**
They were amended on 2026-07-29 to put the ranking and the tokeniser in a shared module for
three callers, then two. Change 4 then deleted the glossary's own near-match guard, leaving
**one** — this catalogue — and reversed the amendment in as many words:
*"change 3 keeps `CatalogueService._rank` private and takes the tokeniser with it"*
(`04-glossary-and-labels.md` §4). Extract on the second occurrence; there is no second
occurrence. Built that way: `engine/catalogue.py` owns `tokens()`, `WORD` and a module-level
`rank()`, and `TermService._tokens` is a delegation that change 4 deletes with `violations()`.
`WORD` left `terms.py` entirely, because `_word` is strip-and-lowercase and needs no regex.

**`CatalogueService` does not take `TermService`, and 3B.2 behaviour 9 / 3B.5 behaviour 4 —
the glossary warning — are not built.** Same reversal, and the decisive evidence is a count
rather than a preference: change 4 deletes `violations()` and **enumerates its call sites as
three** (the submission scan in `rows.py`, `_retired_words()` in `gates.py`, a gap rule in
`gaps.py`). Change 4's specification was written after this one and deliberately does not
include a fourth. Building the wiring here would make change 4's count wrong and would add a
caller to a scan Al ruled ineffective on 2026-07-30 — the ruling that deleted the guard. So
`CatalogueResult` has no `vocabulary_note`: it would be a field nothing writes, which is what
§3.9 refuses to ship.

### 12.2 The landing order, twice more

**3A.0 and 3A.1 cannot land as separate green commits, and the spec's §3.10 presents them as
if they could.** §3.10 is right that 3A.0 must come first — 2E.1's forward check refuses
`catalogue.retire_reason` the moment the DDL exists. But `test_the_declared_justification_set_
is_the_whole_of_it` also runs the **reverse** check, that every declared member is a column
that exists, so 3A.0 alone is red for naming columns nothing has created yet. The two block
each other and land in one commit. This is the mirror image of the failure §3.10 catches, in
the same test change 2 wrote.

**3D.1 cannot land before 3B either, for a reason the packet table missed.**
`test_every_tool_reaches_a_real_method` constructs a `Surface` and resolves `getattr(surface,
tool.service)` for every row, so the six registry rows are red until `CatalogueService` exists
*and* is wired on — which is 3D.2. The *substantive* rule §3.10 states is untouched (the
registry row must exist before anything emits `ContainerNotCatalogued`, and
`test_a_refusal_naming_a_call_survives_the_door` asserts it); it is only the claim that the
ordering is achievable as separate green landings that is false. The real dependency order is
**3A.0+3A.1 → 3A.2 → 3B.0 (models) → 3D.1 → 3B.1–3B.5 → 3C → 3D.2 → 3E**: the models move
ahead of 3D.1 because its payload parser returns `Comparison`.

### 12.3 Two names the specification chose that the codebase refused

**`UnresolvableRef` does not exist and was not created; the error is `UnresolvedReference`.**
Change 2 built that name for exactly this refusal, with this docstring. A second spelling of
it is the disease this whole family of documents is about, and the spec applies the same rule
twice elsewhere in its own text (3B.4 behaviour 2 reuses `RetireNeedsReason`; 3B.2 behaviour 3
reuses an existing name "because the codebase already has that name for exactly this").

**`RefNotFound` is `ComponentNotFound`, and this is the sharper one.** 3B.2 behaviour 3 says
to reuse `RefNotFound` "because the codebase already has that name for exactly this". It has
it **three times** — `conflicts.py:39`, `findings.py:71`, `validation.py:127` — and §3.2 of
this very document cites `RefNotFound` in three modules as one of the eleven collisions the
catalogue exists to refuse. Adding a fourth definition of that name, in the change that builds
the catalogue, would be the most quotable self-inflicted wound available; importing one of the
three arbitrarily couples this service to whichever was picked. And the name is not even
accurate: the refusal covers three conditions — no row at the address, a row in the wrong
table, a component that is not live — and only the first is "not found". Convention 9 asks the
error to name the specific thing at fault, and it does.

### 12.4 What driving it end to end caught, and the tests did not

**`retire_catalogue_entry` and `restate_purpose` were unreachable through the surface.** The
spec's signatures put `container: str | None` in the middle with no default, while the registry
rows mark it optional — so `dispatch` never bound it and Python raised `TypeError`, which the
surface reports as a bare `PlanToolError`. Every unit test passed, because a test calls the
method directly and supplies it. Fixed by moving `container` last with a default, matching
`catalogue_function`, which the spec already had right. **This is F46's shape again** — a
defect on the shipped surface that the engine's own tests cannot see — and it was found by
driving, not by reading.

**A new `Param.kind` needs a JSON-Schema entry in `engine/mcp.py`, and no rule says so.**
`SCHEMA_OF` is keyed by kind, and `input_schema` reads it with `[]`. Adding `comparisons` to
`DECODERS` without adding it there raises `KeyError` inside `tools/list` — which kills the
advertisement for the **whole registry**, not for the one tool that introduced the kind. The
repo's own `test_schema_and_decoders_cover_the_same_kinds` caught it. Convention 12 covers what
goes *with a deleted call*; there is no mirror entry for what a new parameter kind owes, and
this is the second half of the same rule. `test_the_whole_registry_still_advertises_over_mcp`
pins it.

### 12.5 The design consequences worth carrying to change 5

**Eligibility makes the article `a` a near match, and the rarity weight cannot help at small
n.** Behaviour 10 weights a shared word by how many *candidates* contain it — and the candidate
set is what already passed eligibility, so with one candidate the denominator is 1 and `a`
scores full. This is the specification working as written (§3.7: *"eligibility is untouched"*),
and §3.5's measurements assume it — 88% of registrations owing an adjudication is the same
fact. But the measurement that justified the design was taken at **n = 635**, and the table is
empty until change 5 fills it. Between now and then every registration will be refused over
articles. Recorded rather than fixed, because fixing it means a stop-word list, which is a
threshold wearing a wordlist.

**The retirement note is delivered on the *success*, not only on the two refusals 3B.4
behaviour 5 names.** The behaviour table names `NameTaken` and `EntryNotFound`; both are
implemented. But the case the design's strongest sentence was written for — *the thing about
to be written may have been removed on purpose, and the planner may be undoing somebody's
decision without knowing it* — is re-cataloguing a **freed** name, which is refused by nothing
and would therefore have said nothing at all. §11.3's own wording asked for "the result" to
carry it, and the applied behaviour narrowed that to two refusals. `CatalogueResult.note`
carries it, warning without refusing, for `_vocabulary_note`'s reason: re-introducing a retired
name is legitimate, and refusing it would have the tool overruling a decision whose grounds it
cannot see.

**A comparison naming an entry that is not live is refused (`EntryNotFound`), and no behaviour
said so.** `catalogue_comparisons.matched_id` is `NOT NULL REFERENCES catalogue (id)`, so the
alternative was an `IntegrityError` naming a column — the same hole 3B.2 behaviour 2 closes for
a blank `reason`, one column along. It is checked with the other lookups, before the search,
because it is a mistake in the caller's own argument and the ranking is the expensive step.

**`_find` orders by `id DESC`.** With reintroduction after retirement a name legitimately has
several rows, and `include_retired=True` must return the *newest* or the name check reports an
ancient retirement as though it were the current state. The spec says "the one live entry",
which is true only of the live lookup.

### 12.6 The counts, re-measured

| | specified | **built** |
|---|---|---|
| `JUSTIFICATION_ROLES` | 18 | **18** |
| statements in `CATALOGUE_DDL` | 5 | **5** |
| planning registry | 57 | **57** |
| `ADDED` | 16 | **16** |
| writes / reads among the six | 4 / 2 | **4 / 2** |
| suite | — | **647**, from 561 |

**Every number this document stated survived the build**, which is the first change of the
three where that is true — change 1 lost two counts and change 2 lost two more, both times a
denominator taken over the wrong population. The re-enumeration in §3D.1 and §11.1 is why.

**No contract row is superseded, and that was verified rather than assumed** (3D.1 behaviour
5). Of the six engine modules this change touches, only `storage.py` owns methods a contract
cites — `init_plan`, `recover`, `migrate` — and all three signatures and error lists are
unchanged; `_migration_steps` is private and merely gains a branch. `terms.py`'s six tools are
all deviations. So the `[[amend-the-frozen-plan]]` procedure does **not** run for change 3,
and the standing note that it would was an inherited claim, not a measurement.
