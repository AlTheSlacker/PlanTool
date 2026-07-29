# Change 4 — labels

## STOP — §1–§13 are superseded by the owner's decision of 2026-07-29. Rewrite the change against §0.

**§1–§11 are the draft specification, §12 is the cold read's record of it, and §13 the conventions it
proposed.** They are kept because the measurements, the probes and the readers' findings are
evidence that exists nowhere else, and roughly half of it survives the rewrite. **But the central
structural decision in §3.1 is wrong and the owner overturned it.** Do not build from §1–§11, and do
not re-derive §0.

---

## 0. The design, as the owner settled it

**A label is a glossary term that has been attached to rows. There is no separate label
vocabulary.**

**§3.1 got this backwards and the error is worth naming, because it is the disease this change
exists to treat.** The draft gave labels their own table, reasoning that `idx_terms_live` allows one
live row per word, so a word that was both a defined term and a label — `engine`, `surface`,
`execution`, all three likely in this project's own plan — would have one refuse the other. **That
refusal is the point, not the obstacle.** Two rows spelled `engine`, each with its own separately
maintained description, free to drift apart, is two words for one job written into the schema by the
change whose whole purpose is to prevent it.

### What this deletes

- **The `labels` table.** A label is a `terms` row.
- **`propose_label`, `approve_label`, `retire_label`.** They are `define_term`, `approve_term` and
  `redefine_term`, which exist, work, and are already on the surface.
- **The `kind` column on the comparisons table**, and with it the question of whether a term's
  near-match judgment is the same shape as a label's. There is only one kind.
- **Label supersession, the in-place definition rewrite, and the orphaned-attachment problem it
  created** (draft §3.7). Terms already supersede on redefinition, and attachments key on the word.
- **The `Label`, `LabelUsage` and `LabelResult` models**, and every finding in §12.3 about them.

### What remains, and what is new

**Three new tools, not six:** `attach_label`, `detach_label`, and `labels` — the usage report and
the filter. **`define_term` gains the near-match refusal**, which is what D12 claimed already existed
and never did. That is now the whole of the guard, for one vocabulary rather than two.

**Attachments key on the word, not on a row id**, and the glossary's own code is the argument,
quotable: *"a retirement outlives the entry it points at — the replacement will itself be redefined
one day — and the word is the identity that survives that."* This also disposes of the draft's
worst structural problem: redefining a description no longer detaches anything, because nothing
pointed at the row.

**The target keying is unchanged from the draft and its measurements stand**: a plan row is keyed on
its lineage root, a task on its id, exactly one of the two per row — and the uniqueness index must be
over the `COALESCE` expressions, because the natural form enforces nothing whatsoever for every row
in the table (§3.6, probed, and the two sentinel guards in §12.2).

### The one thing that genuinely breaks, and its fix

**Retirement means two different things.** Retiring a *term* sets `ban_scope`, and the glossary then
warns whenever the word appears in row content. Retiring a *label* should mean only "stop filtering
by this" — and if it set a ban, every row that merely mentions `gui` would start nagging. That is
the cry-wolf failure `terms.violations` was written to avoid.

**The glossary's own shape already resolves it.** A word is banned only if it carries a `ban_scope`,
and taking a filter out of use sets none. So **there is no label retirement to build**: finishing
with a label is detaching it from everything, which `detach_label` already does. A word that is
banned from prose and a word that is no longer a useful filter are two states of one row, and the
column that distinguishes them exists.

### Open for the owner, and not to be decided without him

**`export_glossary()` writes a manifest the codebase's own CI consumes.** Under this design, filter
words appear in it. That is probably right — they are words the plan uses, with meanings — but it is
his file and his check. **Ask before the rewrite lands.**

### Two naming calls to make in the rewrite, not before

The attachments table (`label_attachments` reads correctly — it attaches a term *used as* a label —
against `term_attachments`, which names the row rather than the act), and whether the comparisons
table keeps the name `word_comparisons` now that there is one word vocabulary rather than two.

### Which cold-read findings survive the rewrite

**Survive, and must still be applied:** the justification-column count of twenty and its enumeration
(§12.1, and §12.4's corrections to changes 2 and 3); the `index_info` correction; the two sentinel
guards; the rarity weight and the honest statement of what it does and does not buy (§12.3's last
correction); the starter list as a code constant that the ranking includes as candidates, so day one
is not an empty corpus; the label filter having no task that implements it; `contracts:10` needing
supersession; change 1's undeleted packaging round; and every missing assertion in 4F, including the
one that matters most — that `get_stage_script(6)` renders without raising.

**Die with the `labels` table:** everything in §12.3 under the models, the pseudocode's unbound
`label`, the retired-label warning with no delivery route, the `TermService`-collaborator
contradiction, `approve_label`'s defaulted key, `retire_label`'s return type, the two-parser name
collision, and `LabelExists` having nowhere to point.

**Still true and still owed to change 3:** the ranking, the tokeniser **and `word()`** move to a
shared `engine/lexical.py`. That amendment gets simpler, not harder — there are now two callers, the
catalogue and the glossary, rather than three.

---

## 1. What this change does *(superseded — see §0)*

Depends on changes 1, 2 and 3 — schema version 10 is its starting point, `tasks` is the build unit,
the justification-vocabulary check from 2E.1 is in force and will refuse two of this change's
columns until they are declared, and **change 3's shared ranking is the mechanism this change
reuses rather than rebuilds.**

**This change builds a guard D12 said needed no new mechanism.** D12 asserted that a
near-duplicate label is *"refused exactly as a near-duplicate term is"* — and nothing in the
glossary has ever detected a near-duplicate. `TermService.define_term` calls `find(word)`, a direct
lookup on an exact match. So the sentence described a mechanism by pointing at another one that was
equally imaginary, which is this project's oldest recorded failure made twice in one sentence.
Corrected in D12 on 2026-07-29; **building it is this change's job, for labels and for the glossary
both.**

**Specifying it against the real code contradicted the design in three places and confirmed it in
one, each with a measurement.** §2 lists them; §3 argues each.

---

## 1. What this change does

D12 in one sentence: **a label is a word attached to any row for filtering and review, governed by
the glossary's rules and affecting nothing in the build.** The owner adds, assigns and overturns
freely; the tool proposes; a near-duplicate is refused.

The defect it answers is the owner's own stated risk, and it is a shape this repository has
recorded before: *too many specific labels, and near-duplicate names.* Two words for one job, at
the level of the tag rather than the entity. `GLOSSARY.md` exists because that failure cost this
build three naming collisions in a single sitting; labels are a place where it could happen a
hundred times, cheaply, unnoticed, because **nothing about a label is load-bearing enough for
anyone to notice it going wrong.**

**The safety argument and the danger argument are the same argument, and that is why the guard has
to be mechanical.** D12 gives the tool proposal rights *because* a bad label costs only a slightly
worse filter. Precisely because it costs so little, no one will ever be stopped by a bad one — so
if the tool does not refuse a near-duplicate at the moment of typing, nothing ever will.

## 2. What is inherited, and what this change changes

**Inherited unchanged, and not re-argued:**

- Labels sit **outside the breakdown entirely**. They never affect build order, completion,
  ownership or what a builder is served. This is what makes tool proposal safe.
- A row may carry none or several, and they **overlap freely**. Overlap is the design, not a
  defect — which is the one place labels part company with the catalogue (§3.5).
- Labels are governed by the glossary's *rules*: a definition is required, the tool proposes and
  the owner settles, retirement is recorded with a reason.
- The starter list names **a place in the system**, never a kind of work: "refactor", "bugfix" and
  "cleanup" describe an activity that is over once it is done, and a label has to stay true for the
  life of the row.
- No threshold decides what a bad label is. The report counts and shows.

**Changed here, each argued in §3:**

| | what the design said | what this change says | § |
|---|---|---|---|
| 1 | *(unstated)* | Labels are a real table, and their attachments a second | 3.1 |
| 2 | The starter list is settled and generic | **Confirmed by measurement**, and the argument that would have replaced it is refuted | 3.2 |
| 3 | Near-duplication is refused as the catalogue refuses it | …with two relationships, not five — labels are *allowed* to overlap | 3.5 |
| 4 | *(unstated)* | Stop words are **not** a task-local decision, and change 3 says they are | 3.4 |
| 5 | Attachments key on the lineage root, like scope attachments | …and the natural uniqueness index for two nullable targets enforces **nothing at all** | 3.6 |

**Every measurement below was taken the same way, and the method is stated in full because a
denominator produced by an unnamed method is not checkable.** Two sets of numbers appear:

- **The near-match measurements** rank fourteen proposals against the ten starter labels.
  Candidates are the ten from `VOCABULARY.md`, each carrying the one-sentence definition a
  proposal would write for it. The probes are fourteen words of the kind the owner named as his
  risk — an acronym, a synonym, a plural, a longer spelling. The tokeniser is `TermService._tokens`
  **unchanged** (lowercased, plurals folded on a trailing `s`, addresses stripped, `_` and case
  boundaries splitting identifiers). A candidate scores on words shared with the probe, name words
  counting double, and a candidate sharing nothing is not a candidate at any rank. The page is
  five. **Both lists are written out in full in §3.3, definitions included, because the definitions
  are what the ranking actually matches on — a method that omits them looks checkable and is not.**
- **The component-reachability measurement** counts live rows in `spec/v2/plan.db` — the frozen v2
  plan, 687 live rows across seventeen row tables — and asks how many have any path to a component,
  by column or by link.

## 3. The design questions, answered

### 3.1 A real table, and a second one for the attachments

**A real table, not `terms` rows, and the argument is one line of the existing schema.**
`idx_terms_live` is `UNIQUE (term) WHERE superseded_at IS NULL` — one live row per word — and **a
word can legitimately be both a defined term and a label.** "engine" is a term this plan defines
*and* a place a row can be filed under; so is "database", so is "storage". One table refuses one of
them, and which one it refuses depends on which was typed first.

That is the same shape as change 3's `_hydrate` argument one table over: an index that makes naming
a mechanism for one thing is the wrong index for another thing that happens to be spelled the same.

**Labels reuse the glossary's rules, not its table**, and the second half of that sentence is load
bearing: `export_glossary()` writes a manifest the codebase's own CI consumes, and the moment
filter tags start appearing in it, a check that polices vocabulary begins policing tags. The
manifest's consumer has no way to tell them apart.

**A second table for the attachments, because an attachment is not a property of the label.** One
label reaches many targets and one target carries many labels; there is no column for that.

**What this costs, stated because it is the standing argument for the generic layer.** A label gets
no provenance, no supersession lineage, no typed links and no `grounds`. Three of the four are not
wanted — §3.7 replaces supersession with in-place restatement and retirement, an attachment is not
an argument, and a label links to nothing. The fourth, provenance, is the same small loss change 3
recorded: a label is written by a planning session, so `DECIDED` would be its value every time.

### 3.2 The starter list stands, and the argument that would have replaced it is refuted

`VOCABULARY.md` settles the starter list at **ten**, each naming a place in the system:

> `engine` · `surface` · `storage` · `schema` · `methodology` · `interview` · `execution` ·
> `tests` · `docs` · `gui`

**A replacement was designed and is rejected, and the reasoning is recorded because it is the
useful part.** The proposal was to drop place-names in favour of *cross-cutting concerns* —
`performance`, `security`, `error-handling`, `migration`, `testing`, `documentation`,
`accessibility` — under a rule that reads well: **a label earns its place when the filter it gives
you is not already available from the plan's structure.** Place-names looked like exactly what a
component already gives you, so the label would re-implement a filter the plan can already answer.

**Measured against the frozen v2 plan, that is true of 8% of it.**

| | |
|---|---|
| live rows across seventeen row tables | **687** |
| rows carrying a component, as a column | **53** (contracts, and only contracts) |
| rows linking to a component | **4** |
| **rows with no path to a component at all** | **630 of 687 — 92%** |

Requirements, decisions, entities, use cases, steps, extensions, state-machine cells, the CRUD
grid, dependencies, findings and spikes are 92% of a plan and **none of them belongs to a
component.** "Show me everything about the storage engine" is not a query the plan's structure can
answer for any of them. The rule survives; the conclusion drawn from it was drawn from the one
table that happened to be the exception.

**The rule does bite in one place, and it is named rather than hidden.** A *task* reaches a
component through its contract, so a place-label on a task is partly redundant with a query the
graph can already answer. That is one of the two things the owner asked to filter, and it is worth
knowing that half of his stated need has a structural answer as well as a label answer. It is not
an argument for withholding the label: the structural query requires knowing the contract and the
component, and the label answers it in one word at the moment of review.

**Nothing is added to the ten, and the reason is the failure mode.** `VOCABULARY.md`'s argument —
*ten because the failure mode is too many, not too few* — is the whole design, and adding seven
cross-cutting concerns on top would be a 70% increase in the starting set with no measurement
behind it. The tool adds one when nothing fits, which is a proposal the guard can refuse, which is
the mechanism this change exists to build.

### 3.3 What the guard actually catches, measured

The lexical ranking is the guard, and this is what it does against the ten starter labels.

**The candidates, in full, because the definition is what the ranking matches on.** These are the
one-sentence definitions a proposal would carry, and every number in this section is a function of
them:

| label | definition |
|---|---|
| `engine` | the plan store and the services over it |
| `surface` | the tool surface a client calls |
| `storage` | the database handle, transactions and migrations |
| `schema` | the table declarations and their constraints |
| `methodology` | the stage scripts, gap rules and gate criteria |
| `interview` | the eleven stages and how the planner drives them |
| `execution` | serving a task to a builder and verifying what comes back |
| `tests` | the suite and what it asserts |
| `docs` | written documents for a person to read |
| `gui` | the graphical user interface |

**The fourteen probes, their definitions, and the top-ranked candidate each was shown:**

| proposal (and its definition) | top candidate | matched on |
|---|---|---|
| `ui` — the user interface | `gui` | interface, the, user |
| `database` — the database and its tables | `engine` | and, it, the |
| `db` — where rows are stored | **— nothing —** | |
| `testing` — checking that the code does what it says | `tests` | it, the, what |
| `test` — a check over one behaviour | `tests` | test |
| `documentation` — written documents for a person to read | `docs` | document, documents, for, person, read, to, written, a |
| `front-end` — the part the user sees | `gui` | the, user |
| `api` — the calls a client makes | `surface` | call, calls, client, a, the |
| `migrations` — moving a store from one schema version to the next | `storage` | migration, migrations, the |
| `stages` — the interview's ordered rounds | `interview` | stage, stages, the |
| `performance` — how fast it runs and how much it costs | `engine` | and, it |
| `security` — keeping the store and its secrets safe | `engine` | and, it, store, the |
| `error-handling` — what happens when a call fails | `surface` | call, a |
| `errors` — the named failures a call can raise | `surface` | call, a, the |

**13 of 14 proposals are shown a candidate to adjudicate, at a mean of 4.43 candidates on a page of
five.** The guard fires, and the headline number flatters it.

**The word `the` accounts for 46% of every match.** Across the 140 probe-by-candidate pairs there
are 155 matched-word occurrences, and `the` is 72 of them, `and` 21, `a` 18. Three of the fourteen
top-ranked candidates rest **entirely** on words that several labels share: `database` is ranked
against `engine` on *and, it, the*, and `performance` against `engine` on *and, it*.

**This is the owner's own standing ruling arriving from the other side.** He killed a word-frequency
rule with *"are we going to make a glossary entry for 'the'?"*. Here `the` does not create a
threshold — it creates a **false top-ranked candidate**, which is worse, because the top of the
ranked list is the one thing the mechanism makes mandatory to adjudicate. The planner is required
to write a sentence about why `performance` is not `engine`.

**One case is caught by nothing: `db`.** No shared word with any label, so no candidate at any
rank. `terms.py`'s own docstring already admits this and the admission transfers verbatim: *"it
matches words, so a new name invented for an existing concept, sharing no letters with it, goes
unseen. Nothing without judgment can catch that."* An acronym is that case. It is stated here so
the guard is not oversold: it catches the near-duplicate that shares vocabulary, which is most of
them, and it will never catch `db`.

**And the definition is what does the work, not the word.** On the bare word with no definition,
only 4 of 14 proposals are shown anything; against starter labels that have no definitions, only 1
of 14. That is change 3's *"the purpose line carries the whole weight of the search"* holding at a
second site, and it is why `definition` is required on a label exactly as it is on a term.

### 3.4 Stop words are not a task-local decision, and the fix is a weight rather than a list

**Change 3 says twice — §3.7 and task 3B.1 — that "how stop words are handled is task-local and
this specification does not make it."** §3.3's measurement is what that decision looks like when
it is made by nobody: `the` deciding 46% of the matching, and three of fourteen mandatory
adjudications being noise.

Three answers were measured against the same set.

| | proposals shown a candidate | mean shown | top candidate resting only on common words |
|---|---|---|---|
| **A** count shared words, all equal *(change 3 as written)* | 13/14 | 4.43 | **3** |
| **B** drop words appearing in more than one candidate | 12/14 | 1.07 | 1 |
| **C** weight each shared word by how rare it is | 13/14 | 4.43 | **1** |

**Settled: C. A shared word contributes in inverse proportion to how many live candidates contain
it.** A word in eight of ten labels contributes an eighth of what a word in one contributes. `the`
stops deciding anything without anybody writing `the` down anywhere.

Three things make this the right answer rather than a compromise:

- **It is not a threshold, and B is.** B has a number in it that decides whether a word counts,
  which is a judgment written as arithmetic so review cannot see it — the standing ruling. C has no
  cut-off: every shared word still counts, and the weight orders the list. The mechanism already
  takes *the top of the list* without asking whether it is similar enough, so ordering is the only
  thing the weight can affect.
- **It is not a maintained list.** A stop list is a document of English that somebody has to keep
  true, in an engine whose entire subject is that a rule in a document is not a mechanism. C is
  computed from the candidate table itself and is right by construction as the table changes.
- **It changes no candidate's eligibility, so every number change 3 measured stands.** A shared
  word is still a shared word: the set of candidates is identical under A and C for every probe
  (verified with the page limit removed). Change 3's *74 of 635 registrations shown nothing*, its
  *561 adjudications* and its *mean 3.90 on a page of five* are all properties of eligibility and
  page size, and none of them moves. **B does not have this property** — it silently drops
  candidates, taking one probe from "shown something" to "shown nothing", and would invalidate
  change 3's denominators without anyone noticing.

**What it buys, precisely: 2 of the 14 top-ranked candidates change, and both changes are
corrections.** `database` moves from `engine` (*and, it, the*) to `storage` (*database*), and
`performance` moves from `engine` (*and, it*) to `interview`. The first is the guard working. The
second is junk replaced by different junk — and that is the honest reading: **weighting fixes the
matches that had a real word available and does not manufacture one where none exists.**

**This is a correction owed to change 3, and §11 is where it is written.**

### 3.5 Two relationships, not five, because labels are allowed to overlap

Change 3 records a comparison with five relationships — `same`, `contains`, `contained_by`,
`partially_overlaps`, `unrelated` — and the argument for the fifth is that overlap is asymmetric
and each direction is a different instruction to the planner.

**None of that transfers, and the reason is in D12's first paragraph.** A row *"may carry none or
several, they overlap freely"*. In the catalogue an overlap is a defect with a prescribed repair —
extract the shared middle, fold the smaller in. For a label, overlap is the specification. A row
labelled `engine` and `storage` is not a duplication to be resolved; it is two true filters.

**So there is exactly one judgment a planner can make about a near match: is this the same label?**

| relationship | what it means to do | may the label be written? |
|---|---|---|
| `same` | use the label that exists | **no** |
| `distinct` | a different filter; write it, and the reason says how they differ | yes |

**`distinct` and not `unrelated`, and the difference is not cosmetic.** `unrelated` is change 3's
word for "these are not the same thing, record the negative", and it is honest there because
containment has its own values. Here it would be a lie in the common case: `error-handling` and
`errors` are plainly *related* and plainly not the same label, and a planner forced to file that as
`unrelated` is being made to write something untrue in a record the owner reads. One word per job.

**`same` refuses the write, which is what makes the adjudication load-bearing**, exactly as in
change 3: the cheap way past a required field is to write whatever gets you through the door, and
the answer a planner reaches for when the match is real is the one that stops the write. The
remaining dishonesty — answering `distinct` about something that is not — is a lie in a record the
owner can read, which is the standard `dismiss_gap` and the waiver log already set.

**A comparison is recorded whether or not a label follows it**, and change 3's argument applies
unchanged: *"if only merges are written down, the next planner runs the same search, sees the same
candidate, and decides again — possibly the other way."*

**One comparisons table serves both labels and terms, and does not serve the catalogue.** A label
and a term are the same shape — a word with a definition — and the judgment recorded about each is
the same act, so `word_comparisons` carries a `kind` and both callers write to it. The catalogue
keeps its own, because a catalogue entry is identified by *(name, container)* and
`catalogue_comparisons.matched_id` is a real foreign key into a real table; collapsing the two
would trade that key for a string. **And the argument that keeps `terms` and `labels` apart does not
reach the comparisons**: it is entirely about the live-word uniqueness index, and a comparison
record has no uniqueness index at all.

**`matched` is stored as the word, not as an id**, following `terms.use_instead`, whose reason is
quotable and transfers whole: *"a retirement outlives the entry it points at — the replacement will
itself be redefined one day — and the word is the identity that survives that."*

### 3.6 Attachments key on the lineage root, and the obvious index enforces nothing

**Keyed on the lineage root**, following `scope_attachments` and `gap_overlay`, whose comment is
the argument: keyed that way so a record *"neither re-surfaces nor silently detaches"* across
supersession. A label that detached on supersession would mean every revision silently drops the
owner's filters, one row at a time, with nothing to see. `RowService.lineage_root` is the canonical
implementation and this is its third application.

**Two id spaces, and the shape is change 3's.** A plan row is addressed by ref; a task is an
integer id in a table of its own. So `target_root TEXT` and `task_id INTEGER`, with a `CHECK` that
exactly one is set — the arrangement `catalogue` already uses for `task_id` / `component_ref`, and
a real foreign key on each half, which a single polymorphic `target_key` string could not have.

**No `target_kind` column.** Change 3 needed `kind` because object-or-function is an independent
fact that also appears in an index predicate. Here nothing is independent: which column is set
*is* the kind, and storing it as well would be a second source of truth for a fact the row already
carries. That is convention 8 — derived reports are computed at read and stored nowhere.

**The natural uniqueness index enforces nothing whatsoever, and this is the single most likely
build-time defect in this change.** One live attachment per (label, target) is what makes the usage
count in §3.8 mean anything — attach twice and the count silently inflates. The obvious index is

```sql
CREATE UNIQUE INDEX idx_label_attachments_live
    ON label_attachments (label_id, target_root, task_id) WHERE detached_at IS NULL;
```

**Probed at SQLite 3.49.1 under Python 3.12.10: every duplicate is accepted.** Not some — every
one. SQL compares NULLs as distinct, and by the `CHECK` above *every row in this table has exactly
one NULL among the two target columns*, so no two rows ever compare equal and the index is inert
for its entire lifetime.

**Change 3 met this trap and it was worse there than it looked; here it is worse again.** In the
catalogue only module-level entries escaped — which was all eleven of the collisions the table
existed to catch. Here **100%** of rows escape. The index would look correct, run green, and
enforce nothing at all.

**The fix, probed in the same run:** index the expressions.

```sql
CREATE UNIQUE INDEX idx_label_attachments_live
    ON label_attachments (label_id, COALESCE(target_root, ''), COALESCE(task_id, 0))
    WHERE detached_at IS NULL;
```

Probed: the duplicate row attachment is refused, the duplicate task attachment is refused, two
different rows are accepted, two different tasks are accepted, and re-attaching after a detach is
accepted. `PRAGMA index_list` reports the two forms identically, so the parity check in 4F cannot
tell them apart — which is why 4F asserts the *behaviour*.

### 3.7 A label does not supersede, and its definition is replaced in place

`approve_term` supersedes: when the owner rewrites a proposed definition, the proposal is kept and
a new row written, because *"the difference between the two is the most interesting line in a
glossary's history — it is exactly where the tool's reading of the plan and the owner's diverged."*

**That argument does not transfer, and following it would break the attachments.** A term's
definition is *what the plan means by a word*, and rows are written against it; a label's
definition exists to make the ranking work and to tell the owner what the tag is for, and **nothing
is ever written against it.** Meanwhile every attachment keys on `label_id`, so superseding a label
on every wording change would either orphan its attachments or require a cascade — machinery to
maintain a history nobody reads.

**Settled: `approve_label` stamps `approved_at`, and when the owner supplies his own wording it
replaces the definition in place.** This is change 3's `restate_purpose` decision, and its reason
transfers exactly: *"A purpose line is not an argument; it is an index entry, and nothing cites
it."*

**It inherits `restate_purpose`'s honest cost too.** A comparison recorded against the old wording
is not re-adjudicated, so a restatement can leave a `distinct` verdict standing against a label it
no longer describes. The comparison records what was judged and when; the change feed records the
restatement.

**It also removes a tool.** With no supersession there is no `redefine_label` to mirror
`redefine_term`, which is what keeps this change at six tools rather than seven.

### 3.8 The usage report, and the denominator without which it says nothing

`labels()` returns every live label with its definition, whether it is proposed or approved, and
**how many live attachments it has.** No threshold decides what a bad count is.

**The count alone is not enough, and this project has a defect class for that.** A label on one row
and a label on all of them are both useless for filtering, and the second is invisible without
knowing how many things there are to label. F23 is the standing evidence — a check that runs,
passes and means nothing because its denominator was never defined. So the report carries the
denominator: **the number of live plan rows and live tasks**, beside the counts.

**No gap counts a label, and nothing warns.** Both would be judgments: a gap for an unlabelled row
makes labels mandatory, which D12 forbids in its first sentence, and a warning for an over-used
label is a threshold in disguise. The tool computes and shows; the owner decides. §9 says so again
where it will be looked for.

**A proposed label may be attached, and this is deliberate.** Blocking would make the tool unable
to do the one job it was given proposal rights for, and a label affects nothing in the build —
which is D12's whole safety argument. The usage count on an unapproved label is precisely the
number that tells the owner whether to settle it or kill it, and it cannot exist if attachment
waits for approval.

### 3.9 The filter, and the two routes it takes

**A label set with no filter is a write-only feature**, which is the unread-field defect class
change 3 refused to ship. So this change delivers the read.

- **`RowSelector` gains `label`**, so `read_rows` filters plan rows by label alongside everything
  else it already does — table, provenance, liveness, paging. A reviewer wants the rows, with their
  content, a page at a time, and `read_rows` is the call that does that.
- **`labels(label)` returns what carries that label** — plan rows as `name (ref)` and tasks by id
  and title.

**Two routes, deliberately, and the overlap is stated rather than discovered.** Change 2 refused a
`why(ref)` tool as a second route to data `read_rows` already returns, and the same objection has to
be answered here. It does not hold, for one mechanical reason: **a task is not a plan row.**
`read_rows` cannot return one, and there is no other listing call for tasks on the surface —
`graph_status` is a whole-graph report and `next_subtask` is the build-side serve. So a label filter
that lived only in `RowSelector` would leave the owner unable to filter tasks, which is one of the
two things he asked for by name. The two calls answer different questions: *what is this label on,
across both* and *give me those rows to read.*

**`RowSelector.label` is a new dimension and not an inherited one.** The selector's existing
`package` field is the *interview stage* ordinal, which change 1 renames to `stage`; it is not the
build grouping and labels do not take its place.

### 3.10 How this change lands

**One branch, one pull request, the suite green at the end.** Same shape as changes 1 to 3 and for
the same reason: the packets cannot be made independently green.

**The packet letters are not the landing order, and this is the fourth change running in which that
has been true.** The three rules that produced the order have now caught something in every change:

| # | lands | why it cannot land later |
|---|---|---|
| 1 | **4A.0** — the declared vocabulary | 2E.1's check refuses `labels.retire_reason` and `word_comparisons.reason` the moment 4A.1's DDL exists, and `detached_at` is an undeclared `*_at` role that fails `test_every_timestamp_column_is_a_declared_role`. Declared last, the suite is red from 4A to 4F. Change 1's 1A.0 and change 3's 3A.0, a fourth time. |
| 2 | **4D.1** — the registry rows | 4B.2's refusal says to use the existing label, and 4B.5's says to propose the label first. Both are text naming a call, and `door.scan` raises `UnreachableCall` on a payload naming a call the registry cannot resolve. |
| 3 | **4E.1** — the stage-6 script | Same reason one step further out: the labelling round names `propose_label()` and `attach_label()`, and the script is served through `get_stage_script`, so it raises until the registry rows exist. |

**So the order is 4A.0, 4A.1, 4A.2, 4D.1, 4B, 4C, 4D.2, 4E, 4F.**

**The shared ranking is not in this order, and that is the point of §11.** It lands in change 3,
because change 3 is merged and unbuilt and amending its specification is cheaper and more honest
than specifying a refactor of code nobody has written.

**This change mints methodology revision 6, and `PLAN.md` item 10 becomes revision 7.** Change 2
already stated the general form: *every change touching a stage script costs a revision, so the plan
should expect the number to climb once per such change rather than treating a bump as an event.*

## 4. Packet 4A — the schema

Schema version 10 → 11. Nothing else in this change can start until this lands.

### Task 4A.0 — the declared vocabulary, extended

**This lands before the DDL it describes, and that is the whole point of it being 4A.0.**

**Behaviours**

| | behaviour |
|---|---|
| 1 | `labels.retire_reason` and `word_comparisons.reason` join `JUSTIFICATION_ROLES`, which becomes **twenty** members. |
| 2 | `detached_at` joins `TIMESTAMP_ROLES`, which becomes **eight**. |
| 3 | Both justification columns are role 1 — why an act was performed — and each declaration says which act. |
| 4 | `approved_at`'s existing role string is widened, because this change gives it a second site. |
| 5 | No new suffix and no new `SHAPES` member. |

**Behaviour 1 is 2E.1's check applied to this change's schema — and the count is twenty rather than
the thirteen this task first claimed, because changes 2, 3 and 4 all stated it without ever
enumerating it.** Change 2 said nine, change 3 said eleven, and this task said thirteen; all three
are arithmetic on a base nobody counted. The cold read challenged it and the measurement settles it.

**The method, in full, because a denominator produced by an unnamed method is not checkable.** Parse
`engine/schema.py` with `_columns()`'s own regex — every `CREATE TABLE IF NOT EXISTS name (…\n);`,
every line matching `^(\w+)\s+(INTEGER|TEXT|REAL|BLOB|NUMERIC)` with comments stripped — and select
the columns 2E.1 behaviour 2 requires to be declared: named `reason`, `grounds` or `alternatives`,
or ending in `_reason`. **Re-run and it returns 255 columns and these eleven, today, before any of
the three changes adds anything:**

`plan_rows.retire_reason` · `plan_versions.reason` · `gap_overlay.reason` · `warnings.reason` ·
`spikes.block_reason` · `subtasks.block_reason` · `obligation_amendments.reason` ·
`brief_rows.reason` · `scope_attachments.reason` · `terms.ban_reason` ·
`finding_reallocations.reason`

| | |
|---|---|
| matching columns today | **11** |
| change 2 adds `plan_rows.grounds`, `.alternatives`, `.supersede_reason`, and renames `findings.rationale` → `findings.reason` | +4 → 15 |
| plus `technical_claims.evidence`, the declared **non**-justification | **16 entries after change 2** |
| change 3 adds `catalogue.retire_reason`, `catalogue_comparisons.reason` | **18 after change 3** |
| this change adds `labels.retire_reason`, `word_comparisons.reason` | **20** |

**Change 1 renames one key and changes no count**: `subtasks.block_reason` becomes
`tasks.block_reason` when the table moves down.

**Change 2's enumeration is where it went wrong, and the way it went wrong is the register's own
recorded lesson.** Its "three `reason` columns" is a bare-column count — there are **seven** bare
`reason` columns in the schema today — and `terms.ban_reason` and both `block_reason`s are missing
altogether. It was drafted under bare-column keying, change 3 re-keyed it to `table.column` and
restated the total without re-enumerating the members, and this change added two to a base that was
never right. **A count drafted from a reconstruction rather than from the source**, which is exactly
why `CONVENTIONS.md` requires an entry to quote the code it records. **Changes 2 and 3 owe this
correction and §11.3 carries it.**

**Behaviour 4 is small and it is the same disease one size down.** `approved_at`'s declared role
reads *"terms: the owner settled a definition the planner proposed"* — a role string that names one
site, written when there was one. `labels.approved_at` means precisely that for a label, and every
neighbouring role carries its site (`spikes:`, `state_machines`, `requirements:61`). Left alone, the
count still comes to eight and nothing goes red: a declaration silently narrowed by the next change,
found only because somebody read it.

**Behaviour 2 is a genuinely new transition and it is declared as one.** `TIMESTAMP_ROLES`'
comment draws the line: `created_at` and `updated_at` are the general pair, and *"the rest name a
specific transition in a lifecycle — they are not creation wearing a costume."* Detaching a label
is a transition in an attachment's lifecycle, and no declared role fits it:

- `retired_at` is *"withdrawn from live reads with a recorded reason"*, and detaching a label
  records no reason. Requiring one would put friction on the one act D12 says the owner does
  freely.
- `superseded_at` is *"stamped once when a replacement is written"*, and a detachment writes no
  replacement.

So `detached_at` is declared with its own meaning: **the attachment was taken off its target; the
row stays as the record that it was once there.**

**Behaviour 4 is checked rather than assumed.** `label_id`, `matched_id` and `task_id` are all
INTEGER, `target_root` is TEXT and carries no closed suffix, and `SHAPES` is untouched.

### Task 4A.1 — the DDL text

**Signature.** None — `schema.LABELS_DDL` is module-level text appended to `DDL`, and
`SCHEMA_VERSION` becomes 11.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Three tables are declared: `labels`, `label_attachments` and `word_comparisons`. |
| 2 | Held in one named block appended to `DDL`, so a fresh store and a migrated one are created from the same text. |
| 3 | Live-label uniqueness is `UNIQUE (label) WHERE retired_at IS NULL`. |
| 4 | One live attachment per (label, target), enforced on `(label_id, COALESCE(target_root, ''), COALESCE(task_id, 0))`. |
| 5 | Exactly one of `target_root` and `task_id` is set, as a `CHECK`. |
| 6 | `word_comparisons.kind` and `.relationship` are constrained to their value sets, as `CHECK`s. |
| 7 | The version-10 DDL is retained as the fixture the parity check migrates from, **outside `engine/schema.py`**. |

**Behaviour 2 is the pattern `TERMS_DDL` established**, quoted rather than restated: *"Two copies of
a `CREATE TABLE` is a schema that drifts between the stores that were migrated and the stores that
were born."*

**Behaviour 4 is §3.6, and the naive form is the trap.** The comment sits on the index, in the
schema, where the next person to edit it will read it — and it says that the naive form accepts
**every** duplicate rather than an unlucky few.

**Behaviour 6 constrains `relationship` for change 3's reason, restated because it is the same
mechanism**: the value selects between the branch that writes the label and the branch that refuses
it, so a misspelling does not fail — it takes the permissive branch and writes the label the
planner had just said not to write. `kind` is constrained because a misspelt kind silently files a
label's comparison where no reader of label comparisons will ever look.

**`labels` has no `superseded_at` and that is §3.7**, not an omission. There is no supersession
lineage here; a definition is replaced in place and a retirement is stamped.

**Behaviour 7 continues the pattern changes 1, 2 and 3 all owe a sentence to.** `_columns()` in
`test_schema_vocabulary.py` reads the whole of `engine/schema.py` and regexes every
`CREATE TABLE IF NOT EXISTS` out of it, so a retained v10 DDL sitting there is phantom schema for
every vocabulary test — including 4A.0's own new count.

**The DDL**

```sql
CREATE TABLE IF NOT EXISTS labels (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    label         TEXT    NOT NULL,
    definition    TEXT    NOT NULL,   -- required, and it carries the whole of the
                                      -- near-match search; a bare word matches almost
                                      -- nothing (measured: 4 of 14 against 13 of 14)
    approved_at   TEXT,               -- null == the planner proposed it and the owner
                                      -- has not answered
    retired_at    TEXT,               -- null == live, and the only field that says so
    retire_reason TEXT,
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL    -- the definition is replaced in place at approval
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_labels_live
    ON labels (label) WHERE retired_at IS NULL;

CREATE TABLE IF NOT EXISTS label_attachments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    label_id    INTEGER NOT NULL REFERENCES labels (id),
    target_root TEXT,                 -- the lineage root of a plan row, so the label
                                      -- neither re-surfaces nor silently detaches when
                                      -- the row is superseded
    task_id     INTEGER REFERENCES tasks (id),
    detached_at TEXT,                 -- null == the label is on this target now
    created_at  TEXT    NOT NULL,
    CHECK ((target_root IS NULL) != (task_id IS NULL))
);

-- Indexed on the expressions, not the columns. Every row here has exactly one NULL among
-- the two target columns, and SQL compares NULLs as distinct — so the natural form,
-- (label_id, target_root, task_id), accepts *every* duplicate rather than an unlucky
-- few. Probed: it enforces nothing at all for the whole life of the table, and the usage
-- count in `labels()` silently inflates on a double attach.
CREATE UNIQUE INDEX IF NOT EXISTS idx_label_attachments_live
    ON label_attachments (label_id, COALESCE(target_root, ''), COALESCE(task_id, 0))
    WHERE detached_at IS NULL;

-- Read when a row is rendered with the labels it carries (4D.2). The live index above
-- leads on label_id and cannot answer that direction.
CREATE INDEX IF NOT EXISTS idx_label_attachments_target
    ON label_attachments (target_root, detached_at);

-- One judgment about one near match, for a word that has a definition: a label or a
-- term. The catalogue keeps its own table, because its identity is (name, container) and
-- its matched_id is a real foreign key.
CREATE TABLE IF NOT EXISTS word_comparisons (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    kind         TEXT    NOT NULL,    -- label | term
    proposed     TEXT    NOT NULL,    -- the word that was being written
    matched      TEXT    NOT NULL,    -- the candidate, as the word: a retirement
                                      -- outlives the entry it points at
    relationship TEXT    NOT NULL,
    reason       TEXT    NOT NULL,
    created_at   TEXT    NOT NULL,
    CHECK (kind IN ('label', 'term')),
    CHECK (relationship IN ('same', 'distinct'))
    -- Constrained because a misspelling takes the branch that writes the word: the typo
    -- does not fail, it inverts the refusal (§3.5).
);
```

**Six statements — three tables and three indexes.** `schema.statements` splits on semicolons and
the split is safe only because comments are stripped first; the comment lines in this block contain
no semicolons, but the rule is the same one change 3 probed and 4F.1 asserts the number so that a
builder who drops one gets a failure rather than a smaller schema.

**`word_comparisons` has no `updated_at` and that is not an oversight.** It is an immutable audit
record like `catalogue_comparisons`, `finding_reallocations` and `behaviour_amendments`; the
vocabulary check's own note says `updated_at` is *"absent on immutable tables by design"*.

**`label_attachments` has none either**, following `scope_attachments`, which carries `created_at`
and a lifecycle stamp and nothing else. An attachment is not edited; it is made and taken off.

### Task 4A.2 — `Storage._migration_steps`, the 10→11 branch

**Signature.** Unchanged. Gains one branch.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Creates all three tables and all three indexes, from `schema.LABELS_DDL` via `schema.statements`. |
| 2 | Backfills nothing, and seeds no starter label. |
| 3 | Adds nothing to the snapshot table set. |

**Behaviour 1 reuses `statements()` rather than restating the SQL.** By the time this change lands
there are seven migration branches, and the split between them is clean: **all four that create
whole new tables** — 3→4 for the glossary, 5→6 for the revision tables, 6→7 for the change feed and
9→10 for the catalogue — take their SQL from `statements()`, and the three that alter existing
tables issue `ALTER`s of their own (4→5 does both). The rule is *a whole table is created from the
one text; a column added to an existing table is an `ALTER` the DDL also carries*, and this change
is purely the first kind, which is why behaviour 1 is unqualified.

**Behaviour 2's second half is the decision in this task, and it is the starter list's mechanism
question answered.** The ten could have been inserted here as proposed rows. They are not, for two
reasons: a migration is the schema changing, not the tool proposing, and seeding would put ten
proposals into every existing plan including ones that are finished. **The ten live in the stage-6
script (4E.1), which is where the tool reads them and proposes from them** — and they live in
exactly one place, rather than as a constant in code that only a script's prose consumes.

**Nothing else depends on the list, which is what makes a script the right home for it.** There is
no gap rule counting labels and no gate criterion requiring one, so the list is not a denominator
and does not need to be queryable. Where a list *is* a denominator — the banned words — the schema
comment on `terms` is explicit that it must be a column, and that argument is deliberately not
being borrowed here.

**Behaviour 3 follows change 3's reasoning exactly.** `snapshot_version` carries nine tables and
`tasks` is not among them: the whole execution layer sits outside snapshots. A `label_attachments`
inside the snapshot set would be rewound while the `tasks` rows and `plan_rows` it points at were
not. All three stay out, together.

**A consequence inherited, not created.** `recover('restart')` clears eight tables and leaves
`terms`, `findings` and the execution layer standing; labels join that set, so a restart leaves
labels attached to a plan that no longer exists. That is v2's behaviour for every table outside the
eight, and fixing it would be a change about recovery.

## 5. Packet 4B — the service

Depends on 4A and on 4D.1 (§3.10). A new module, `engine/labels.py`, and `models.py`.

**The service is constructed with `Storage`, `RowService` and `lexical.rank`'s module, and none is
optional.** `RowService` resolves a target's lineage root and confirms it is live. The reason this
is written out rather than assumed is convention 11: an unpassed collaborator has its guard skipped
and its effects omitted, and the call proceeds — so a label service missing its row service would
attach labels to refs it never checked, and look identical to a working one.

**`TermService` is *not* a collaborator here**, and that is a deliberate difference from
`CatalogueService`. The catalogue takes one so it can run purpose lines past `terms.violations()`.
A label *is* a word in its own right, not prose written in the plan's vocabulary; warning that a
label uses a retired word would be the glossary policing the tag namespace, which §3.1 is the
argument against.

### Task 4B.0 — the models

**Signature.** Four frozen dataclasses in `models.py`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | `Label` — `id`, `label`, `definition`, `approved_at`, `retired_at`, `retire_reason`, with `is_approved` and `is_live` properties. |
| 2 | `LabelUsage` — a `Label`, its live attachment count, and the denominator that count is against. |
| 3 | `WordComparison` — `matched` (the word), `relationship`, `reason`. |
| 4 | `LabelResult` — `label: Label \| None`, `comparisons`, `use_instead: Label \| None`. |

**This task exists for the reason change 3's 3B.0 exists**, and the conventions register states it
as a rule: a return type's fields are **not** a convention, because they differ per task, so they
are a hole in every task that leaves them out. The recorded v2 defect is `WriteBatch`,
`RowSelector`, `TraversalSpec` and `GraphScope` — four types named by the plan and defined nowhere,
*"so two implementers would have built two incompatible interfaces."*

**Behaviour 3 names its candidate by the word and nothing else**, which settles 4D.1's payload
parser and 4C.1's shape at the same time. A label has no container, so the pair that identifies a
catalogue entry collapses to one field here — and the planner answering an adjudication has the
word in front of them, because the refusal just printed it.

**Behaviour 2 carries the denominator inside the result rather than beside it** (§3.8), so a caller
cannot render the count without it. A count whose denominator is one call away is a count that gets
rendered alone.

**`LabelResult` mirrors `CatalogueResult` deliberately**: same three-branch shape, same
`use_instead` field carrying the thing to use so that nothing has to be looked up to act on it.

### Task 4B.1 — the read path and the near-match search

**Signature.** Four private methods on `LabelService`: `_find(label: str, include_retired: bool =
False) -> Label | None`, `_require(label: str) -> Label`, `_candidates(word: str, definition: str,
limit: int = 5) -> tuple[Candidate, ...]`, and `_attachments(label_id: int) -> tuple[Attachment,
...]`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | `_find` returns the one live label for this word, or `None`. |
| 2 | `_require` is `_find` with the refusal, naming the word and saying `propose_label` records one for the first time. |
| 3 | `_candidates` ranks live labels against a proposed word and definition by calling the shared ranking. |
| 4 | A retired label is never a candidate; `_find(include_retired=True)` is how the name check sees one. |
| 5 | The word is normalised exactly as `TermService._word` normalises a term — stripped and lowercased — and an empty one is refused. |

**Behaviour 3 calls the shared ranking and does not implement one**, which is the whole of §11 and
the reason this change exists in the order it does. `_candidates` supplies the label word as the
name and the definition as the text, and the ranking does the rest.

**Behaviour 4 is the design's own strongest sentence, applied one table over.** A retired label
cannot be reused and offering it as a candidate is a confidently wrong answer — but **the label
about to be proposed may have been retired on purpose, and the planner may be undoing somebody's
decision without knowing it.** So it surfaces in the refusal text of the calls that would have found
it, with its retire reason, exactly as change 3 delivers it for entries.

**Behaviour 5 reuses the glossary's normalisation rather than writing a second one**, and the case
that makes this matter is real: `GUI` and `gui` proposed a week apart are the same label, and a
guard that catches near-duplicates while admitting exact ones differing by case would be absurd.
`_word` is a static method on `TermService` today; §11 does not move it, because unlike the
tokeniser it has one behaviour and no second policy waiting to appear — but `LabelService` calls
`TermService._word` rather than copying its two lines, and the delegation names the canonical one in
its docstring, following `GapService.lineage_root`.

### Task 4B.2 — `propose_label`

**Signature.** `propose_label(self, label: str, definition: str, idempotency_key: str,
comparisons: tuple[WordComparison, ...] = ()) -> LabelResult`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Writes one unapproved label and returns it. |
| 2 | Refuses with `DefinitionRequired` when `definition` is blank, and `ReasonRequired` when any comparison's `reason` is blank. |
| 3 | Refuses with `LabelExists` when a live label already holds this word, naming it and its definition. |
| 4 | Refuses with `NearMatchesUnadjudicated` when the search returns candidates and the highest-ranked one has no comparison, naming every candidate shown with its definition. |
| 5 | Refuses with `UnresolvableRef` when the definition or a comparison reason cites a `table:ordinal` that resolves to nothing, naming the token. |
| 6 | Returns without writing when the comparison on the highest-ranked candidate is `same`, recording the comparison and naming the label to use. |
| 7 | Every supplied comparison is written, whether or not a label was, with `kind='label'`. |
| 8 | One transaction, one op batch. |
| 9 | A replay that would have written a label is refused with `LabelExists`; a replay of a `same` call returns the original receipt. |

**The refusal order is the pseudocode's order and they agree**, which is change 3's correction
inherited rather than rediscovered: with the name check *after* the adjudication check, an exact
duplicate would surface as `NearMatchesUnadjudicated` — because an exact match ranks first — and the
planner would be told to adjudicate a candidate when what they need to be told is that the label
already exists. Cheap checks on the caller's own arguments run first, the lookup next, the search
last because it is the expensive one.

**Behaviour 3's message carries the existing label's definition, and that is the point of it.** The
whole failure being prevented is two labels meaning the same thing; a refusal that says only "taken"
tells the planner to invent a variant, which is the disease. **And it carries a retired label when
it finds one**, with its retire reason (4B.1 behaviour 4).

**Behaviour 4's message carries each candidate's definition for the same reason**, and §3.3 is the
measurement that makes it necessary: the top-ranked candidate is sometimes noise, and a planner
shown `performance` against `engine` with no definitions cannot see that in one glance.

**Behaviour 5 is the convention change 3 proposed and `CONVENTIONS.md` now carries** — a free-text
field rendered through the door is checked at the write for `table:ordinal` tokens that do not
resolve, and served `Verbatim` thereafter. A comparison `reason` cannot be rewritten, so an
unresolvable ref in one makes the row permanently unreadable through the surface. The refusal names
the token, because change 2's probe found that a URL with a port reads as `table:ordinal` and the
planner needs to see it is their `localhost:8080`.

**Behaviour 6 is a deliberate override of convention 1**, written here because the register requires
an override to be written in the task rather than upstream. Convention 1 says a named error is
raised and never reported as a status field in a success payload; `LabelResult` with `label=None` is
exactly such a field. The reason is §3.5's: the planner did the right thing, the call did what it
exists to do, and a comparison **was** committed — an exception path that also commits a write is a
shape nothing else in this engine has.

**`idempotency_key` is required, not defaulted**, and the reason is change 3's measured one: a
default means the first defaulted call's receipt replays for every later defaulted call in that
database.

**Pseudocode**

```
word = terms._word(label)                       # TermNotFound on empty
if not definition.strip():
    raise DefinitionRequired naming word
for c in comparisons:
    if not c.reason.strip():
        raise ReasonRequired naming c.matched
refuse_unresolvable_refs(definition, [c.reason for c in comparisons])   # UnresolvableRef
existing = self._find(word, include_retired=True)
if existing and existing.is_live:
    raise LabelExists naming it and its definition
candidates = self._candidates(word, definition)
if candidates and no comparison names candidates[0]:
    raise NearMatchesUnadjudicated naming every candidate with its definition
verdict = the comparison naming candidates[0], if any
if verdict is SAME:
    ops = [insert each comparison, kind='label']
    write_atomic(ops, idempotency_key)
    return LabelResult(None, comparisons, use_instead=candidates[0])
ops = [insert the label] + [insert each comparison, kind='label']
write_atomic(ops, idempotency_key)
return LabelResult(label, comparisons, use_instead=None)
```

**The comparisons do not borrow the label's id and so need no `FromOp`**, unlike change 3's: a
`word_comparison` names its candidate by word, not by id (§3.5), so there is no forward reference
inside the transaction. The comparisons still go in the same batch, because a comparison written
without the label it justified is a record of a decision that did not happen.

### Task 4B.3 — `approve_label`

**Signature.** `approve_label(self, label: str, definition: str | None = None,
idempotency_key: str = ...) -> Label`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Stamps `approved_at` and returns the label. |
| 2 | With a `definition`, replaces it in place and stamps `updated_at` as well. |
| 3 | Refuses with `AlreadyApproved` when it is already settled and no new definition is supplied. |
| 4 | Refuses with `DefinitionRequired` when `definition` is supplied and blank. |
| 5 | Refuses with `LabelNotFound` when there is no live label for the word. |
| 6 | Recorded comparisons are untouched. |
| 7 | A rewritten definition is **not** re-run past the near-match search. |

**Behaviours 1 to 4 are `approve_term`'s shape**, and the two-acts-in-one-call reason transfers
verbatim: *"they are one decision with two outcomes, and the friction has to be small: a glossary is
a handful of words, and a review step that costs a paragraph per word does not get done."*

**Behaviour 2 is where this parts company with `approve_term`, and §3.7 is the argument.** No
supersession, no proposal kept as history.

**Behaviour 7 is a decision, not an omission, and the alternative is worse.** Re-running the search
would mean the owner's own wording could be refused as a near-duplicate of a label the tool
proposed — the tool adjudicating the owner. The guard exists to stop the *tool* multiplying labels;
the owner is the one who overturns, and D12 settles that level.

**Behaviour 6 inherits `restate_purpose`'s honest cost** (§3.7): a comparison judged against the old
wording stands against the new one.

### Task 4B.4 — `retire_label`

**Signature.** `retire_label(self, label: str, reason: str, idempotency_key: str) -> Label`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Stamps `retired_at` and `retire_reason`, and returns the label. |
| 2 | Refuses with `RetireNeedsReason` when `reason` is blank. |
| 3 | Refuses with `LabelNotFound` when no live label holds this word. |
| 4 | Live attachments are **left standing** and stop appearing in every live read. |
| 5 | The returned label reports how many attachments went dark. |
| 6 | Retirement is never undone; the word is free for a new label, which is a new row with a new id. |

**Behaviour 2 reuses the error name change 2 gives `retire_row` and change 3 reuses for
`retire_catalogue_entry`.** This is its third occurrence, which is the register's own bar, and §10
proposes what to do about where it lives.

**Behaviour 4 is the decision in this task, and it is the opposite of change 3's
`ContainerNotEmpty`.** Retiring a catalogue object with live methods is refused, because the entries
would point at a dead container and the report groups by it. Retiring a label with live attachments
is *the ordinary case*: the owner has decided the filter was wrong, and refusing until he detaches
forty rows one at a time is friction on exactly the act D12 says he performs freely. The
attachments stay because they are the record that the label was once there; every live read joins
on `retired_at IS NULL` and stops seeing them.

**Behaviour 5 exists because behaviour 4 is silent otherwise.** Retiring a label with sixty
attachments and one with none look identical from the outside, and the first is a large change to
what every filter returns.

**Behaviour 6 is `terms`' ruling and it stands.** A label retired and proposed again is a new row:
its old attachments stay with the old dead label, which is honest — the owner retired it, and
resurrecting sixty attachments he had taken down would be the tool deciding what he meant.

### Task 4B.5 — `attach_label` and `detach_label`

**Signature.** `attach_label(self, label: str, targets: tuple[RowRef | str | int, ...],
idempotency_key: str) -> tuple[Attachment, ...]` and `detach_label(self, label: str,
targets: tuple[RowRef | str | int, ...], idempotency_key: str) -> tuple[Attachment, ...]`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | One label, many targets, in one transaction. |
| 2 | A plan-row target is keyed on its **lineage root**; a task target on its id. |
| 3 | Refuses with `LabelNotFound` when the label is not live, saying to propose it first. |
| 4 | Refuses with `RowNotFound` naming the ref, or `TaskNotFound` naming the id, when a target does not exist. |
| 5 | Attaching a label already on a target is a **no-op**, not an error; detaching one that is not attached is likewise. |
| 6 | A proposed label may be attached. |
| 7 | An empty `targets` is a valid no-op returning an empty result. |
| 8 | Attaching requires no reason, and neither does detaching. |

**Behaviour 1's shape — one label, many targets — is the direction the work actually goes.** A
planner labelling at stage 6 has just decided what `engine` means and is placing it across a
handful of rows; the opposite shape would make that call once per row.

**Behaviour 2 is §3.6.** The lineage root is resolved through `RowService.lineage_root`, which is
the canonical implementation and is not reimplemented here.

**Behaviour 3's message names a call**, which is what puts 4D.1 before this packet (§3.10).

**Behaviour 5 is convention 10 applied and it is a decision worth stating.** An empty collection is
a valid no-op returning an empty result — and here the same reasoning extends to a duplicate:
attaching a label that is already there is the caller asking for a state that already holds, and
refusing it would make a batch of ten targets fail because one was already labelled. The uniqueness
index in §3.6 is what makes the no-op safe rather than a silent second row.

**Behaviour 8 is D12's control level in the schema.** Attaching is the act the owner performs
freely; every other write in this change records a reason, and this one deliberately does not.

**Behaviour 6 is §3.8.** Blocking would make the tool unable to do the job it was given proposal
rights for.

**A sequencing consequence that bites now and stops biting at change 5.** `task_id` references a row
in `tasks`, and until change 5 moves task creation to stage 8, tasks are still derived at
finalization — so a task can only be labelled on a plan that has been finalized. That is awkward for
this change's end-to-end drive and it is not a defect; it is the same constraint change 3 recorded
for function entries, and change 5 is what removes it. Plan-row targets have no such constraint.

### Task 4B.6 — `labels`

**Signature.** `labels(self, label: str | None = None) -> LabelReport`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | With no argument: every live label, alphabetically, with its definition, whether it is approved, and its live attachment count. |
| 2 | The report carries the denominator — live plan rows plus live tasks — beside the counts. |
| 3 | With a label: that label, its count, and every target carrying it. |
| 4 | A plan-row target is returned as its name and ref; a task as its id and title. |
| 5 | Retired labels are excluded; a retired label named explicitly is reported as retired with its reason, not as missing. |
| 6 | No threshold, no warning, no gap. |

**Behaviour 2 is §3.8 and it is the half a builder would drop**, because a count reads as complete
on its own. It is not: a label on all 687 rows and a label on one are both useless for filtering and
only the denominator distinguishes the first from a healthy one.

**Behaviour 3 is the second of the two read routes, and §3.9 is why there are two.** It exists
because a task is not a plan row and `read_rows` cannot return one.

**Behaviour 5 keeps a retired label findable by name.** Reporting it as missing would tell the
planner the word is free, which is the moment they propose it again.

**Behaviour 6 is the standing ruling, restated where it would be broken.** A count of one and a
count of everything are both interesting, and any rule that says *which* is bad is a threshold —
a judgment written as arithmetic so review cannot see it.

## 6. Packet 4C — the glossary's own guard

Depends on 4B. `terms.py`.

**This packet is what makes D12's correction true rather than half-true.** D12 said a near-duplicate
label is refused *as a near-duplicate term is*; the term half has never existed. Change 4 was always
going to build the mechanism, and pointing `define_term` at the same one costs a single task — which
is D12's own argument for doing it here: *"building a second near-match mechanism instead would be
the duplication the catalogue exists to catch, in the change that inherits the catalogue."*

### Task 4C.1 — `define_term` gains the near-match refusal

**Signature.** `define_term(self, term: str, definition: str, names_ref: RowRef | str | None = None,
comparisons: tuple[WordComparison, ...] = ()) -> Term`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | The search runs over live terms, ranked by the shared ranking on the word and its definition. |
| 2 | Refuses with `NearMatchesUnadjudicated` when candidates are returned and the highest-ranked has no comparison, naming every candidate with its definition. |
| 3 | A `same` verdict returns without writing, naming the term to use, and records the comparison. |
| 4 | Every supplied comparison is written with `kind='term'`. |
| 5 | `TermExists` still precedes the search, and its message is unchanged. |
| 6 | `redefine_term` and `approve_term` are untouched. |

**Behaviour 6 is the boundary and it needs its argument, because the instinct is to guard every
write.** `redefine_term` sharpens what an *existing* word means — the word is already in the
glossary, so there is no new near-duplicate to create. `approve_term` is the owner settling a
definition, and running his wording past a guard would be the tool adjudicating him, which is 4B.3
behaviour 7's reasoning at the term level. **The guard belongs at the one call that mints a new
word, and that is `define_term`.**

**Behaviour 3 is a departure from `define_term`'s current contract shape and it is deliberate.**
Today the call either writes a term or raises. Returning "no term written, use this one" is the
same convention-1 override 4B.2 behaviour 6 records, for the same reason, and it is registered here
so that both overrides are visible rather than one inheriting the other silently.

**Nothing supersedes a contract row.** `define_term` is a `DEVIATION` tool — the frozen plan never
asks what the words mean, which is DEFECTS.md F40 and the reason the glossary exists at all — so
there is no contract to amend, and no `Absence` entry changes.

**What this costs the interview, stated because it is a real change to a call planners already
make.** Every first definition of a word now runs a search and may be refused. Against v2's own
glossary that is a handful of calls; against a plan with two hundred terms it is two hundred
searches and up to two hundred adjudications. That is the same trade change 3 measured and accepted
at 561, and it is smaller here by an order of magnitude — but it is the reason the weighting in
§3.4 matters, because a mandatory adjudication against a candidate matched on `the` is friction
that buys nothing.

## 7. Packet 4D — the surface and what a reader sees

`surface.py`, `models.py`, `render.py`. **4D.1 lands before packet 4B and 4D.2 after it** — §3.10.

### Task 4D.1 — the registry

**Behaviours**

| | behaviour |
|---|---|
| 1 | Six tools are added to the **planning** surface, all `DEVIATION`, each appearing in `ADDED` with its reason. |
| 2 | A `comparisons` payload parser accepts a list of `{matched, relationship, reason}`, rejecting an unknown relationship by name. |
| 3 | `define_term`'s registry row gains the same `comparisons` parameter, optional. |
| 4 | `RowSelector` and the `selector` parser gain `label`. |
| 5 | The four writing tools carry `writes=True`; the two reads do not. |
| 6 | Every parameter of all six carries a `Param.note`. |
| 7 | No contract row is superseded, and no `Absence` entry is filed for any of the six. |

**The six tools.**

| tool | writes | why it exists |
|---|---|---|
| `propose_label` | yes | D12's proposal right; nothing else can mint a label |
| `approve_label` | yes | the owner settling it, as proposed or in his own words |
| `retire_label` | yes | the owner overturning one, on the record |
| `attach_label` | yes | one label across many targets — the act the filter is made of |
| `detach_label` | yes | taking it off; without this the owner can only ever add |
| `labels` | no | the set, the usage counts and their denominator — and what one label is on |

**Behaviour 1's count is stated because a coverage test that asserts a number nobody wrote down
cements whichever number the builder guessed — and change 3's draft got exactly that wrong.** The
arithmetic, from this change's own cited premises:

| | |
|---|---|
| v2's planning surface today | 54 |
| change 1 removes | 4 — `declare_package`, `assign_task`, `packaging`, `split_subtask` |
| change 2 adds | 1 — `record_grounds` |
| change 3 adds | 6 |
| this change adds | **6** |
| **after this change** | **63** |

`ADDED` moves the same way: 12 today, minus the three deviations change 1 removes, plus
`record_grounds`, plus change 3's six, plus these six — **22**. Both were re-derived here rather
than carried from a note, and the 54 and 12 were re-counted from `engine/surface.py`.

**Behaviour 3 is the change that is easy to miss**, because `define_term` is not a new tool and the
packet is named for new ones. Without it 4C.1's parameter has no route through the door and the
guard can be satisfied by nobody.

**Behaviour 4 is §3.9's first route.** The parser's accepted-key set is explicit — it raises on an
unknown field by name — so a new selector dimension that is not added there is refused at the
surface while working perfectly in-process, which is the shape F39 records.

**Behaviour 6 is not padding, and `surface.py` says why in its own words**: `Param.note` is *"the
whole of the tool's documented interface, so it says what the caller must decide — never what the
implementation does with it."* Two of these tools take a parameter whose whole difficulty is
knowing what to put in it — `comparisons`, and `targets`, which accepts a ref or a task id — and a
caller who cannot tell which will pass the wrong one and read the refusal as a bug in the tool.

**Behaviour 7 is the correction to the instinct.** No contract row describes any of this — the
frozen plan never anticipated labels, so it cannot have anticipated the calls — which is what
`DEVIATION` means. No `Absence` entry either: an absence records a call that **exists** and is
deliberately not exposed, and none of these was ever built.

### Task 4D.2 — rendering

**Behaviours**

| | behaviour |
|---|---|
| 1 | A rendered row shows the labels it carries, and says nothing when it carries none. |
| 2 | A rendered label shows its word and its definition, and says whether it is approved. |
| 3 | A refusal listing candidates lists each with its definition. |
| 4 | A label `definition` and a comparison `reason` are `door.Verbatim`: served as written, with every ref they cite resolved **alongside** them. |
| 5 | A label is addressed by its word, never by an id. |

**Behaviour 1 is what makes the whole change visible.** A label attached and never shown is the
unread-field defect class; `idx_label_attachments_target` exists for exactly this read, which is why
it survives the same cull that keeps this change's index list to three.

**Behaviour 4 is the convention change 3 proposed and `CONVENTIONS.md` now carries**, and the trap
is worth restating because change 3's draft got it backwards: `Verbatim` is *"stored prose, served
as written"*, and the door **annotates alongside** rather than rewriting inline. Annotation that
changes a value's shape turns an identifier a caller reads and passes back into an object, which
broke the tool once already.

**Behaviour 5 follows `terms`**, which is looked up *"by the word you were about to type, never by
an ordinal"* — so `door.scan` never sees a `labels:` address in outgoing text and `resolver_from`
needs no new lookup.

## 8. Packet 4E — the methodology

Depends on 4D.1. `engine/methodology/rev6/`.

### Task 4E.1 — methodology revision 6, and the labelling round

**Behaviours**

| | behaviour |
|---|---|
| 1 | `rev5` is copied to `rev6` and edited there; `rev5` is left untouched. |
| 2 | `stage6_architecture.md` gains a **labelling round**, in the place the packaging round vacated. |
| 3 | The round lists the ten starter labels, and says the tool proposes only when none of them fits. |
| 4 | It names `propose_label()` and `attach_label()`, and says the owner settles with `approve_label()`. |
| 5 | The revision stamp is 6, and `plan_status` reports it. |
| 6 | No gate criterion and no gap rule is added. |

**Behaviour 1 is change 1's ruling and it is not re-argued**: editing a revision in place
retroactively changes what already-run sessions were scripted with, and the stamp exists precisely
so a plan can say which methodology produced it.

**Behaviour 2 is why this packet is not optional, and the evidence is in the file.**
`rev3/package6_architecture.md` carries a packaging round — *"Every component is a task, and every
task belongs to exactly one package… this is the one grouping a human chooses rather than
derives"* — which change 1's revision 4 deletes, because the tools it names no longer exist. That
leaves stage 6 with a hole where the plan's only human-chosen grouping used to be, and
`INTERVIEW.md` §7 already says what fills it: *"Stage 6 loses the packaging round and the mandatory
package cut… It gains labels."* This is that sentence built.

**Behaviour 3 is the starter list's only home** (4A.2 behaviour 2). Ten words and one rule — *a
label names a place in the system, never a kind of work* — written where the planner reads them at
the moment they are needed.

**Behaviour 6 is the difference between this round and the one it replaces, and it is the whole of
D12.** The packaging round was mandatory and `finalize_plan` refused a plan with an unpackaged
task. Labelling is not: no criterion requires a label, no gap counts an unlabelled row, and a plan
with no labels at all finalizes exactly as it does today. **The script's language has to carry that
difference**, because a script written in the packaging round's imperative voice would create an
obligation the engine does not enforce — which is a rule in a document, and the failure this whole
family of documents is about.

## 9. Packet 4F — the enforcement

Depends on all of the above.

### Task 4F.1 — the store's own invariants

**Behaviours**

| | behaviour |
|---|---|
| 1 | A version-10 database migrated to 11 is structurally identical to a fresh 11 — raw `PRAGMA table_info`, `index_list`, `index_info` and `foreign_key_list` output, compared as-is. |
| 2 | `schema.statements(LABELS_DDL)` yields six statements. |
| 3 | **The same label attached twice to the same plan row is refused, at the store, with raw SQL.** |
| 4 | The same label attached twice to the same task is refused. |
| 5 | The same label on two different rows, and on two different tasks, is accepted. |
| 6 | Re-attaching after a detach is accepted. |
| 7 | An attachment with two targets, or none, is refused. |
| 8 | Two live labels with the same word are refused; a retired word is available again. |
| 9 | `kind` and `relationship` refuse a value outside their set. |
| 10 | The 10→11 migration writes no label row, and `snapshot_version` still carries nine tables. |
| 11 | `_columns()` finds all three new tables, and no table the retained v10 fixture declares. |

**Behaviours 3 to 7 are asserted at the store, with raw SQL, and this is the correction that matters
most in this packet.** Driven through the service instead, **behaviour 3 passes on the naive
index**: `attach_label` treats an existing attachment as a no-op (4B.5 behaviour 5), so the service
never issues the second insert and the index is never reached. The test would be green, the index
would enforce nothing, and the first caller to write an attachment any other way — a migration, a
later change, a repair script — would double every affected usage count with nothing red. This is
change 3's lesson arriving one change later at a table where the escape is total rather than
partial.

**Behaviour 1 includes `index_info` because `index_list` names indexes without saying which columns
they cover** — and these two indexes are the whole of §3.6.

**Behaviour 10 exists because nothing else verifies 4A.2's two negative behaviours.** "Seeds no
starter label" and "adds nothing to the snapshot table set" are both claims a builder could quietly
break — a helpful seed of the ten, or `label_attachments` added to `snapshot_version` on instinct —
and neither would fail anything else.

**Behaviour 11 is the guard on the guard**, and it is 4A.1 behaviour 7 given a test: the retained
v10 fixture must be invisible to `_columns()`, which is the assertion that proves it lives outside
`schema.py`.

### Task 4F.2 — the size and the shape

**Behaviours**

| | behaviour |
|---|---|
| 1 | The planning registry holds **63** tools, `ADDED` holds **22**, and every `DEVIATION` among the six appears in `ADDED` with a reason. |
| 2 | A proposal with candidates and no comparison is refused, and the refusal names every candidate **with its definition**. |
| 3 | A `same` verdict writes the comparison, writes no label, and returns the label to use. |
| 4 | The ranking a proposal adjudicates against is the ranking the same input produces for `define_term`. |
| 5 | A proposal naming a label that is not live is refused, and the refusal passes `door.scan`. |
| 6 | An exact duplicate is refused as `LabelExists`, not as `NearMatchesUnadjudicated`. |
| 7 | A word may be a live term and a live label at the same time, and neither refuses the other. |
| 8 | Retiring a label with live attachments succeeds, and the attachments vanish from every live read. |
| 9 | `read_rows` with a label selector returns the rows carrying it, and follows a row through supersession. |

**Behaviour 4 is the one a builder would skip**, because each half looks covered by a unit test of
its own. It is what makes the shared ranking a mechanism rather than a sentence: two rankings would
let a planner be shown one candidate and required to adjudicate another, and every individual test
would still pass. It is change 3's 3E.2 behaviour 4 asserted across two *modules* rather than two
calls, which is the stronger version of the same check.

**Behaviour 7 is §3.1 asserted rather than assumed**, and it is the single test that would catch
somebody deciding during the build that labels belong in `terms` after all.

**Behaviour 9's second half is §3.6 end to end**, and it is the assertion that would catch a label
keyed on the row ref instead of the lineage root: attach, supersede the row, read again. Keyed
wrongly, the label silently disappears and every individual unit test still passes.

**Behaviour 5 is the landing-order inversion made into an assertion**, following change 3: asserting
that the refusal *renders* rather than that it is raised is what catches the ordering being undone
later, against the standing evidence that a missing route reports a refusal reading like the
caller's mistake (F39).

## 10. What this change does not do

**It does not make a label mandatory anywhere.** No gap counts an unlabelled row, no gate criterion
requires one, and `finalize_plan` is untouched. That is D12's first sentence, and it is what makes
tool proposal safe.

**It does not judge a label set.** The report counts and shows a denominator; nothing warns, and no
threshold decides what a bad count is.

**It does not label a catalogue entry.** Entries are addressed by name and container, have their own
report, and nobody has asked to filter them. Adding a third target space would mean a third column
and a third arm on the `CHECK`, for a filter with no stated reader.

**It does not seed the starter list into the database** — §4A.2. The ten live in the stage-6 script.

**It does not give a label to a term, a finding or a warning.** The targets are plan rows and tasks,
which is what D12 says — *"attached to any row"* — plus the one thing the owner named that is not a
row.

**It does not re-run the near-match search on approval or redefinition** — 4B.3 behaviour 7 and
4C.1 behaviour 6. The guard is on the call that mints a new word.

**It does not fold `label_comparisons` into `catalogue_comparisons`** — §3.5. The catalogue's
matched entry is a foreign key; a word is not.

**It does not build the shared ranking.** That lands in change 3, by amendment — §11.

**One item change 5 inherits from this change**, listed so it is not rediscovered: **task labelling
is only reachable on a finalized plan until stage 8 creates tasks** (4B.5). Change 5 is what removes
that, and it removes the identical constraint change 3 recorded for function entries at the same
time.

## 11. What this change owes change 3

**Two amendments to `builds/03-catalogue.md`, both applied there rather than specified here as a
refactor.** Change 3 is merged and **unbuilt**, so the cheapest and most honest correction is to the
specification. Specifying a refactor of code nobody has written would be inventing work.

### 11.1 The ranking and the tokeniser move to a shared module

**`engine/lexical.py`, holding two functions and one error**, built in change 3 and called by change
3, change 4's labels, and change 4's glossary guard.

| | |
|---|---|
| `tokens(text, scope)` | `TermService._tokens`, moved unchanged. `TermService._tokens` becomes a one-line delegation whose docstring names the canonical one. |
| `rank(name, text, candidates, limit=5)` | change 3's `CatalogueService._rank`, taking its candidates as `(key, name, text)` rather than reading the catalogue table itself. |
| `NearMatchesUnadjudicated` | the refusal, raised by three callers and therefore owned by none of them. |

**The argument is already in this codebase and is quoted rather than re-derived.**
`RowService.lineage_root` says why the supersession-stable identity primitive lives there rather
than on either caller — *"scope attachments take the same keying, which makes this the second
application and the reason it lives here rather than on either caller"* — and `GapService`'s
delegation is one line naming it. **Verified 2026-07-29: it is delegation, not duplication.** This
is the same shape with three callers instead of two.

**And `fingerprint.py` is the precedent for it being a module rather than a method**, in its own
words: capture and comparison *"are one piece of knowledge — what counts as the workspace — and
splitting them puts the two halves in different files with nothing holding them to the same field
list."* The tokeniser and the ranking are one piece of knowledge — what counts as a shared word —
and the failure mode is identical: change the tokeniser in one place and the other ranking
silently starts matching differently.

**Change 3 was already about to write a second tokeniser.** It says stop words are "task-local",
which is a second tokenisation policy with a different answer, in the change whose own subject is
duplication.

**The name, and the two that were rejected.** `lexical` is the codebase's own word for this layer —
`terms.py` heads the scan *"the lexical scan"*, `references.py` says *"Lexical retrieval"*, and
change 3 §3.7 says *"the ranking is lexical, and it has to be."* `words.py` was rejected as one
letter of daylight from `terms.py`, which defines a term as *a word the plan has agreed the meaning
of* — two modules named for near-synonyms is the collision this catalogue exists to catch.
`similarity.py` was rejected because the module deliberately computes no similarity verdict: it
ranks, and the standing ruling is that a threshold is a judgment written as arithmetic.

**What change 3's document has to say, precisely:** task 3B.1's `_rank` becomes a call to
`lexical.rank`; §3.7's *"the ranking function must be one function, called by both the search and
the registration"* extends to *and by every later caller, which is why it is not private to this
service*; and 3E.2 behaviour 4 keeps its assertion unchanged, because it tests the property rather
than the location.

### 11.2 Stop words are not task-local, and the answer is a weight

§3.4 is the measurement and the settlement. Change 3 says twice that stop-word handling is
task-local; §3.3 shows what that leaves — `the` deciding 46% of all matching and three of fourteen
mandatory adjudications resting on nothing else.

**`lexical.rank` weights each shared word by how rare it is across the candidates it was given**,
and change 3's §3.7 and 3B.1 drop the "task-local" sentence in favour of naming the weight.

**This changes no number in change 3**, and that is what makes it an amendment rather than a
redesign: eligibility is untouched — a shared word is still a shared word — so *74 of 635 shown
nothing*, *561 adjudications* and *mean 3.90 on a page of five* all stand. Verified against the
same fourteen probes with the page limit removed: the candidate set is identical under both
rankings for every probe.

## 12. The cold read, and the corrections it owes

**Four readers, one per packet group — 4A, 4B, 4C+4D, 4E+4F. All four reported zero tool uses.**
Each was given its packet verbatim, the §3 sections it depends on, the adjacent packets, the
conventions register and the source a builder would hold. **The specification below §12 is the
draft they read; §12.3's corrections are NOT yet applied except where marked APPLIED.** Nothing is
built until they are.

**This was the most productive of the four cold reads so far, and the reason is worth naming: it
was the first one run against a change that reuses another change's mechanism.** Most of what it
found lives in the seam — a model consumed and never defined, a parser registered twice under one
name, a sentence about `writes=True` carried across from a change where it was true.

### 12.1 What was re-measured, and what the numbers actually are

| | drafted | **measured** |
|---|---|---|
| `JUSTIFICATION_ROLES` after this change | 13 | **20** — and 9 (change 2) and 11 (change 3) are both wrong; the base was never enumerated |
| justification columns in the schema **today** | *(never counted)* | **11**, over 255 columns |
| migration branches when this change lands | 7 | **8**; and **five** create whole new tables, not four — 4→5 creates `finding_reallocations` |
| mean candidates shown per proposal | 4.43 | **4.43 over all fourteen probes, 4.77 over the thirteen that were shown anything** — 4.43 × 14 = 62 exactly, so the drafted figure silently includes the probe that was shown nothing |
| writing tools among the six | 4 writes, 2 reads | **5 writes, 1 read** |
| `define_term`'s adjudication cost against change 3's 561 | "an order of magnitude" smaller | **2.8×** smaller at the paragraph's own figure of 200 |
| statements in `LABELS_DDL` | 6 | **6** ✓ (probed) |
| `TIMESTAMP_ROLES` after this change | 8 | **8** ✓ |

**The justification count is the finding of this cold read, and its cause is the register's own
recorded lesson.** Change 2 enumerated "three `reason` columns" where the schema has seven bare
`reason` columns, and missed `terms.ban_reason` and both `block_reason`s entirely; change 3 re-keyed
the register to `table.column` and restated the total without re-enumerating; this change added two
to a base that was never right. Three changes each did arithmetic on a number none of them counted.
**Changes 2 and 3 owe this correction** — §12.4.

### 12.2 What was probed

| claim | result |
|---|---|
| The naive unique index over two nullable target columns accepts every duplicate | **Confirmed**, SQLite 3.49.1 / Python 3.12.10. Six cases: both duplicates accepted, and the `CHECK` guarantees every row has exactly one NULL, so no two rows ever compare equal. |
| The `COALESCE` form refuses both duplicates, admits two different rows and two different tasks, and permits re-attachment after a detach | **Confirmed**, same run. |
| `schema.statements(LABELS_DDL)` yields six statements | **Confirmed** — and the block *does* contain a semicolon inside a comment, in `definition`'s. The split survives only because comments are stripped first, which makes the point sharper than the draft's false claim that there were none. |
| A migrated v10→11 store and a fresh v11 are identical across `table_info`, `index_list`, `index_info` and `foreign_key_list` | **Confirmed**, byte-identical. |
| *"`PRAGMA index_list` reports the two index forms identically, so the parity check cannot tell them apart"* | **Half refuted.** `index_list` is identical, but **`index_info` distinguishes them**: an expression column reports `cid = -2` and a NULL name. So parity *can* see the difference — and is blind anyway, for a better reason: both sides are built from the same `LABELS_DDL`, so parity catches a *missing* block and can never catch a *wrong-but-consistent* index. **Change 3 makes the same imprecise claim and owes the same correction.** |
| `COALESCE(task_id, 0)`'s sentinel is unreachable | **Refuted.** `INSERT INTO tasks (id) VALUES (0)` is accepted despite `AUTOINCREMENT`, and a row with `target_root = ''` collides with a row with `task_id = 0` — two different targets sharing one index key. Probed: `CHECK (target_root IS NULL OR target_root <> '')` and `CHECK (task_id IS NULL OR task_id > 0)` make both sentinels unreachable, and real rows and tasks still insert. |

### 12.3 The design defects — corrections owed to §1–§11

**Applied while the readers ran:** the `JUSTIFICATION_ROLES` count and its method (4A.0, APPLIED);
`approved_at`'s role string widened (4A.0, APPLIED); `matched_id` corrected to `matched TEXT` in
4A.0 behaviour 4 (APPLIED); the migration-branch count (4A.2, APPLIED); the ten candidate
definitions written into §3.3 so the measurement can be re-run (APPLIED).

**Outstanding, grouped by what they break.**

**Models the specification consumes and never defines** — the defect 4B.0 exists to prevent,
committed inside 4B.0. Seven types are used; four are defined. `Candidate`, `LabelReport` and the
attachment model are missing, `_attachments` is declared with no behaviour and no caller, and
`Label` omits `created_at` and `updated_at` although both are `NOT NULL`. `LabelUsage` has no
reader.

**The pseudocode does not run.** `label` is returned unbound — the receipt line
(`self._get(receipt["results"][0]["id"])`) is missing, and `attachments.py`'s own comment says why
it must come from the receipt rather than the op. `use_instead=candidates[0]` assigns a `Candidate`
to a field typed `Label`. `refuse_unresolvable_refs` is called and defined nowhere.

**The refusal order contradicts its own table.** `UnresolvableRef` is behaviour 5 and runs third,
ahead of two checks listed before it — and the prose calling the ref check a "cheap check on the
caller's own arguments" is wrong: it resolves addresses against the database, so it *is* a lookup.

**The retired-label warning cannot be delivered.** 4B.1 behaviour 4 calls it "the design's own
strongest sentence" and routes it through `LabelExists` — which fires only when the word is
**live**. Proposing a previously-retired word is a success, so there is no refusal to carry it, and
`LabelResult` has no note field where `CatalogueResult` has `vocabulary_note`.

**`TermService` is and is not a collaborator.** The prose says it is not; the pseudocode's first
line calls `terms._word(label)`. The fix is not to inject it: `_word` belongs beside `tokens` in
`engine/lexical.py`, by the same argument that put the tokeniser there — **which is a third
amendment to change 3.**

**A guard that is never reached.** Every one of the four writing calls refuses a replay *before*
`write_atomic`: `LabelExists`, `AlreadyApproved`, `LabelNotFound` (because `_require` is live-only),
and the attach no-op. So the idempotency key the specification argues hard for is never consulted
twice on any path, and a caller who lost the first response gets an error rather than the original
result. Change 3 met this and stated it per call; this change must too.

**A unique index does not produce a no-op — it raises and aborts the batch.** 4B.5 behaviour 5's
duplicate-attach no-op has to be a service-side check; the index is the backstop, not the mechanism.
And duplicate targets *within one call* will raise, taking the other nine with them.

**Liveness of an attach target is incoherent as written.** The constructor prose says `RowService`
"resolves a target's lineage root and confirms it is live" — but wherever a supersession chain
exists the root is *by definition* superseded. The check is on the supplied ref; the key is the root.

**Two contradictions inherited from change 3's wording, and both are change 3's to fix too.**
`writes=True` on "the four writing tools" is five here. And 4D.1 behaviour 1 requires all six to
appear in `ADDED` while behaviour 7 says "no `Absence` entry is filed" — `ADDED` *is* a
`tuple[Absence, ...]`, and its twelve current entries are all registered deviation tools, so the
class docstring ("a contract no tool exposes") describes none of its uses. The sentence reasons from
the docstring rather than the data.

**Nothing implements the label filter.** §3.9 promises `read_rows` filtering by label and 4F.2
behaviour 9 tests it, but 4D.1 only adds a dataclass field and a parser key. No task writes the
join — and the join is not trivial: attachments key on lineage roots while `read_rows` is handed
refs, and DISTINCT, `total` and paging are all unspecified. It needs its own task in 4B.

**`targets` has no payload parser**, and no `Param.kind` exists for a heterogeneous list of refs
or task ids — the exact F39 shape 4D.1 behaviour 4 cites. `isinstance(x, int)` also accepts
`True`, since `bool` subclasses `int`.

**Two `comparisons` parsers under one name.** Change 3 registers `{matched, container,
relationship, reason}` over five relationships; this change registers `{matched, relationship,
reason}` over two. One shadows the other, or the catalogue's comparisons start being validated
against `same | distinct`.

**`LabelExists` has nowhere to send the caller.** `TermExists` points at `redefine_term`; there is
no `redefine_label`. The answer is that `approve_label(label, definition=…)` **is** the amend path,
and the message must say so.

**`contracts:10` is a contract this change changes.** `read_rows`' selector gains a dimension and
`RowSelector`'s docstring enumerates them. Change 2's precedent superseded five contract rows for
exactly this; 4D.1 behaviour 7 scopes itself to "the six" and never answers it.

**The starter list has two homes and no mechanism holding them equal** — `VOCABULARY.md` and the
stage-6 script — which is the duplication this product exists to catch, in the packet that quotes
the doctrine. **And the reader found the deeper problem: with nothing seeded and the ranking over
live labels only, on day one the corpus is empty and the guard shows nothing at all.** Both are
fixed the same way: `STARTER_LABELS` is a constant in `engine/labels.py`, the ranking includes the
unadopted starters as candidates, `VOCABULARY.md` quotes the constant, and 4F asserts the quote is
true. That reverses 4A.2's "the list is not a denominator" — it is one.

**Change 1 does not delete the packaging round.** 1E.1 behaviour 4 removes three *call names*; the
round's prose names no call and survives. So "in the place the packaging round vacated" has no
anchor, and rev6 would ship a residual packaging round beside the labelling round. Change 1 is
under-specified and change 4 must delete the prose.

**4F asserts nothing about 4E, and misses the highest-value test in the change**:
`get_stage_script(6)` renders without raising. Change 1 shipped exactly that break; this change
recreates the conditions and adds no guard. Also unasserted: `plan_status` reports 6, `rev5` is
untouched, no gap rule or gate criterion was added, the whole of §3.8 (`labels()`' counts and
denominator, and the dark-attachment count), `approve_label` in its entirety, and that the
`junctions` exemption set was not quietly widened to include `label_attachments`.

**4F.2 behaviour 5 names the wrong call.** "A proposal naming a label that is not live is refused"
— proposing a word no label holds is the success path. The refusal that names a call is
`attach_label`'s, which is the whole of §3.10's landing-order argument.

**Smaller, all real:** `approve_label`'s `idempotency_key: str = ...` contradicts 4B.2's own
argument for requiring it; `retire_label` returns `Label`, which cannot carry behaviour 5's count;
the denominator is described as two numbers in §3.8 and one sum in 4B.6; a target is `name (ref)` in
§3.9 and two fields in 4B.6; `labels(label)` takes no `limit`/`offset` against `requirements:62`;
4D.2 behaviour 2 drops the retire reason 4B.6 behaviour 5 requires; a rendered *task* showing its
labels is nowhere specified; term definitions rendered in 4C.1's refusal are not `Verbatim` and
legacy ones were never ref-validated, so a refusal can raise `BareAddress`; `word_comparisons` has
no index and no reader, which is right and needs saying with change 3's argument; `4B.0` settles
4D.1's parser while landing after it, so the models must land with 4A; and `(measured: 4 of 14…)`
is an uncheckable number written into permanent schema prose.

**One correction to the rarity weight itself, and it matters because the draft overclaims.** The
weight **reorders**; it does not exclude. An entry sharing only `the` still has a non-zero share,
is still a candidate, and can still be `candidates[0]` — as this change's own measurement shows,
where `performance` merely moves from one noise match to another. So §3.4's heading is wrong: stop
words are not "answered". What the weight buys is precisely and only this — *when a real shared word
exists, it wins*; when none exists, the planner still adjudicates noise. §3.3's figures are the
**unweighted** ranking's and must be labelled as such.

**Two errors of naming this change inherits and should name rather than fix:** the glossary retires
a word with `BanNeedsReason`, not `RetireNeedsReason`, so the engine already carries two names for
that act and `retire_label` makes a third site; and `RefNotFound` is defined in **three** modules
(`conflicts.py`, `findings.py`, `validation.py`) while `RowService.get` raises `RowNotFound` — which
is change 3's pseudocode citing a name its own source does not use, and one of the eleven collisions
the catalogue exists to catch, live in the engine today.

### 12.4 The cross-change corrections this found

**Change 2** — `JUSTIFICATION_ROLES` is **16 entries** after change 2, not nine, and its enumeration
must be re-derived from the schema rather than restated.

**Change 3** — five things: the count is **18** after change 3, not eleven; `engine/lexical.py` also
owns `word()`, not just `tokens()` and `rank()`; the `index_list`/`index_info` claim is imprecise and
parity's real blindness is that both sides come from one text; "the four writing tools carry
`writes=True`" is a sentence its successor copied wrongly and which should say *the writers*; and
3E.1 behaviour 10's *"no table the retained v9 fixture declares"* is **unsatisfiable** — the fixture
declares `plan_rows`, which `schema.py` also declares. What it means is *no table is declared
twice*, and 4F.1 behaviour 11 inherited the same flaw.

**Change 1** — the stage-6 packaging round's prose is not removed by 1E.1 behaviour 4, and something
must remove it.

### 12.5 What the readers got wrong, and the bundle errors of mine that caused it

**Two false findings, both mine.** A reader reported that `kind = 'term'` has no producer in this
change — 4C.1 behaviour 4 is its producer, and I did not put packet 4C in that reader's bundle.
Another reported that the register has no three-occurrence bar and that `GapService.lineage_root`'s
delegation does not exist; the register's §4 states the bar and the delegation is in `gaps.py`
lines 122–133, and I had abridged the register and passed only `rows.py`. **That is the third and
fourth time a bundle of mine has produced a false finding**, and both are the same error the
procedure already names: summarise or abridge, and the reader correctly reports a hole in what you
gave it.

**One reader was right about something I had counted and wrong about what it implied.** It read
`labels.label` as having no unique constraint; the constraint is in 4A.1 behaviour 3 and the DDL,
which that reader had. The underlying point survives and is a real hole: the index has no
`COLLATE NOCASE`, so `Engine` and `engine` are two live labels unless the service normalises — and
the service does, through `_word`, which is exactly the arrangement `terms` already has.

## 13. Two conventions this change proposes

**A shared error type lives with the mechanism that raises it, not with its first caller.**
`RetireNeedsReason` reaches its third caller here — `retire_row`, `retire_catalogue_entry`,
`retire_label` — and `DefinitionRequired` its second, and `NearMatchesUnadjudicated` is born with
three. `errors.py`'s existing rule is *contract-named errors live here*, which answers a different
question and leaves this one open; the register's bar is three tasks with the same answer, and this
is the third. **The entry: an error raised by more than one module lives in `errors.py` or in the
module of the mechanism that defines the refusal — never imported from whichever service happened to
need it first.** The evidence is this repository's own measurement: six class names over seventeen
definitions in v2's engine, five of them error types, and *"a reader who imports the wrong
`RefNotFound` writes an `except` clause that never fires."*

**A uniqueness index over a nullable column is indexed on the expression, not the column.**
`COALESCE(col, sentinel)`. Change 3 met it once and measured that the naive form missed **all
eleven** collisions the catalogue existed to catch; this change meets it again with two nullable
columns and measures that the naive form enforces **nothing at all**. Twice in two changes, both
times with the index looking correct and running green, is the register's own bar reached in the
sharpest possible way. **The entry carries its test as well as its rule**: the assertion must be the
behaviour at the store, because `PRAGMA index_list` reports the two forms identically and a service
guard that agrees with the constraint proves nothing about the constraint.
