# Change 4 — labels

## SUPERSEDED 2026-07-30 by `04-glossary-and-labels.md`. Do not build from this file.

**The owner reduced the glossary itself later the same day**, after this file was rewritten. There
is no near-duplicate guard, no `term_comparisons`, no ranking, no banned words and no
`approve_term`; the glossary is a five-column table whose only mechanical use is looking a word up
when a label is assigned. **`04-glossary-and-labels.md` is the work order**, and its §5.8 lists
exactly what transfers from here — the attachment table, its two index probes, the sentinel checks
and the measurements — so nothing below needs re-deriving.

**Keep reading below only for those carried items and for §12**, the cold read of the first draft.
Everything else here describes a design that was overtaken twice.

---

## Status — §1–§11 were rewritten against §0 on 2026-07-30, then superseded the same day.

**§0 is the owner's settled design of 2026-07-29 and the rewrite builds from it.** §1–§11 are the
specification; **they replaced a draft the owner overturned, and every number in them was re-measured
from source on 2026-07-30 rather than carried across.** §12 is the cold read of the *superseded*
draft — kept because its measurements, probes and findings are evidence that exists nowhere else, and
because §11.3 is still working off what it found. **Read §12 as a record, never as a description of
what is above it**; where the rewrite departs from a §12 finding it says so and gives the reason
(§3.2, §3.3, §4A.0, §11.3). §13 is the conventions the change proposes, unchanged.

**Nothing is built until this has been cold-read**, and the read has two things to check that no
previous one had: a specification rewritten against a design decision rather than drafted fresh, and
three measurements where the re-run disagreed with the draft.

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

## 1. What this change does

**A label is a glossary term that has been attached to rows.** §0 is the owner's settled design and
this section builds from it rather than re-arguing it.

D12 in one sentence: *a label is a word attached to any row for filtering and review, governed by
the glossary's rules and affecting nothing in the build.* The owner adds, assigns and overturns
freely; the tool proposes; a near-duplicate is refused. **Under §0 "governed by the glossary's
rules" stops being a resemblance and becomes an identity** — there is one vocabulary, and a label
is a use of it.

Depends on changes 1, 2 and 3 — schema version 10 is its starting point, `tasks` is the build unit,
the justification-vocabulary check from 2E.1 is in force and will refuse this change's one new
justification column until it is declared, and **change 3's shared ranking is the mechanism this
change reuses rather than rebuilds.**

**This change builds a guard D12 said needed no new mechanism.** D12 asserted that a near-duplicate
label is *"refused exactly as a near-duplicate term is"* — and nothing in the glossary has ever
detected a near-duplicate. `TermService.define_term` calls `find(word)`, a direct lookup on an exact
match (`terms.py:243`). So the sentence described a mechanism by pointing at another one that was
equally imaginary, which is this project's oldest recorded failure made twice in one sentence.
Corrected in D12 on 2026-07-29; **building it is this change's job, and under §0 there is one place
to build it.**

The defect it answers is the owner's own stated risk, and it is a shape this repository has recorded
before: *too many specific labels, and near-duplicate names.* Two words for one job, at the level of
the tag rather than the entity. `GLOSSARY.md` exists because that failure cost this build three
naming collisions in a single sitting.

**The safety argument and the danger argument are the same argument, and that is why the guard has
to be mechanical.** D12 gives the tool proposal rights *because* a bad label costs only a slightly
worse filter. Precisely because it costs so little, no one will ever be stopped by a bad one — so if
the tool does not refuse a near-duplicate at the moment of typing, nothing ever will.

**What is left to build, once §0 has deleted what it deletes:** an attachment table, three tools,
one refusal on `define_term`, one selector dimension, one methodology round, and the tests. §3 is
the argument for each and every number in it was re-measured on 2026-07-30 rather than carried from
the superseded draft — including three the draft got wrong (§3.3, §3.4, and the count in 4A.0).

---

## 2. What is inherited, what §0 settled, and what is measured here

**Inherited unchanged, and not re-argued:**

- Labels sit **outside the breakdown entirely**. They never affect build order, completion,
  ownership or what a builder is served. This is what makes tool proposal safe.
- A row may carry none or several, and they **overlap freely**. Overlap is the design, not a defect
  — which is the one place labels part company with the catalogue (§3.5).
- Labels are governed by the glossary's rules: a definition is required, the tool proposes and the
  owner settles, a retirement is recorded with a reason.
- The starter list names **a place in the system**, never a kind of work: "refactor", "bugfix" and
  "cleanup" describe an activity that is over once it is done, and a label has to stay true for the
  life of the row.
- No threshold decides what a bad label is. The report counts and shows.

**Settled by the owner on 2026-07-29 and stated in §0, not re-opened here:** a label is a `terms`
row; there is no `labels` table, no `propose_label` / `approve_label` / `retire_label`, no label
supersession and no label retirement.

**Decided in this rewrite, each argued in §3:**

| | what it is | § |
|---|---|---|
| 1 | Attachments key on the **word** and on the target's **lineage root**, and the natural uniqueness index over two nullable target columns enforces **nothing at all** — re-probed against this shape | 3.6 |
| 2 | The starter list stands at ten, as a **code constant with one home**, and is **not** injected into the ranking as a phantom candidate | 3.2 |
| 3 | The refusal must name **every candidate tied at the top score**, because "the highest-ranked one" is not a well-defined single candidate — newly measured, 4 of 14 probes tie | 3.3 |
| 4 | Stop words are **not** a task-local decision; the answer is a rarity weight, and what it buys is smaller than the draft claimed and includes something the draft never noticed | 3.4 |
| 5 | Near-match judgments take **two relationships, not five**, because labels are allowed to overlap | 3.5 |
| 6 | Attaching a **banned** word is refused, which is the one place this parts company with the glossary's warn-never-block rule, and it is argued rather than assumed | 3.6 |
| 7 | `attach_label` and `detach_label` are **idempotent by construction**, so neither carries a replay problem the draft had to argue around | 4B.2 |

**Two naming calls §0 left to the rewrite, both settled here.**

**`label_attachments`**, not `term_attachments`. The row records an *act* — this term is being used
as a filter on this target — and `term_attachments` names the row rather than the act, which would
read as "attachments belonging to a term". `scope_attachments` is the precedent for both the name
shape and the keying.

**`term_comparisons`**, not `word_comparisons`. The draft's name existed to serve two vocabularies
under a `kind` column; with one vocabulary the column is gone and so is the reason for the name.
`term_comparisons` sits beside `catalogue_comparisons` under one rule — a comparisons table is named
for the table whose entries it judges — and `catalogue_comparisons` is the existing half of that
pair.

**Every measurement below was taken on 2026-07-30 and the method is stated in full, because a
denominator produced by an unnamed method is not checkable.** The scripts are reproducible from the
method statements alone; each measurement says what it ran against.

---

## 3. The design questions, answered

### 3.1 One vocabulary, and what that deletes

**A label is a `terms` row that has been attached to something.** The argument is §0's and it is
quoted rather than restated, because it is the disease this change exists to treat:

> Two rows spelled `engine`, each with its own separately maintained description, free to drift
> apart, is two words for one job written into the schema by the change whose whole purpose is to
> prevent it.

The superseded draft reasoned the other way from the same line of schema. `idx_terms_live` is
`UNIQUE (term) WHERE superseded_at IS NULL` (`schema.py:716`) — one live row per word — so a word
that is both a defined term and a label would have one refuse the other. **That refusal is the
point, not the obstacle.**

**What follows mechanically, and each of these is a thing this change does not have to build:**

| the draft had | §0 leaves |
|---|---|
| a `labels` table | a `terms` row |
| `propose_label` | `define_term` |
| `approve_label` | `approve_term` |
| `retire_label` | nothing — see §3.7 |
| a `redefine_label` it had to argue away (draft §3.7) | `redefine_term`, which exists and supersedes |
| `Label`, `LabelUsage`, `LabelResult` | one usage model and one report model (4B.0) |
| a `kind` column on the comparisons table | one kind |
| label supersession orphaning attachments | nothing — attachments key on the word |

**The orphaning problem disappears rather than being solved, and that is the strongest evidence for
§0.** The draft's §3.7 refused supersession for labels *because* every attachment keyed on
`label_id`, so a wording change would either orphan attachments or need a cascade. Key on the word
and the whole problem is not there: `redefine_term` supersedes freely, the word is unchanged, and
every attachment still points at it. The glossary's own code is the argument, quotable from
`DEVIATIONS.md`:

> a retirement outlives the entry it points at — the replacement will itself be redefined one day —
> and the word is the identity that survives that.

**What this costs, stated because the draft's version of this paragraph is now wrong.** The draft
said a label gets no provenance, no supersession lineage, no typed links and no `grounds`. Under §0
a label gets everything a term gets, because it *is* one: supersession on redefinition, a
`names_ref`, an approval stamp, a ban with a reason and a replacement word. The only thing an
attachment itself carries is its target and its lifecycle, and that is right — an attachment is not
an argument.

**One consequence is open for the owner and is the only thing in this document waiting on him**
(§0). `export_glossary()` writes `glossary.json` into the plan workspace, and under one vocabulary a
word used as a filter appears in it. **Spiked 2026-07-30, so the question is what he wants rather
than what breaks:**

- `export_glossary` exports `self.glossary()` — every live term — as `terms[]` (`term`,
  `definition`, `approved`, optionally `names`) plus a `banned[]` list built from `ban_scope`
  (`terms.py:544-584`). **The `banned[]` half is untouched**: attaching a word sets no `ban_scope`,
  so the enforcement half of the manifest does not move. Only the `terms[]` inventory grows.
- **Nothing in this repository consumes the manifest today.** There is no `.github`, no workflow and
  no script reading `glossary.json`; the only vocabulary check that runs here is
  `tests/test_vocabulary.py`, which parses the banned bullet out of `GLOSSARY.md`. The consumer the
  delivery point was written for is external and prospective.
- So the decision is a design one, not a repair: **should an entry say that a word is in use as a
  filter** — an attachment count, or a flag — so a consumer can tell a vocabulary word from a filter
  word? **Under §0 the honest answer is probably no**, because a label is not a different kind of
  thing; the attachment count is a fact *about* a term, and `_entry`'s own comment already draws
  that line for `approved`: a consumer deciding what to enforce is exercising judgment, *"and that
  judgment is not the tool's to make on its behalf — but it cannot make it without being told."*
  That sentence argues for including the count and letting the consumer ignore it.

**No task in this change touches `export_glossary`.** If the owner wants the count, it is one field
in `_entry` and one assertion in 4F; if he does not, the change is already correct as written.

### 3.2 The starter list stands at ten, with one home, and is not a phantom candidate

`VOCABULARY.md` settles the starter list at **ten**, each naming a place in the system:

> `engine` · `surface` · `storage` · `schema` · `methodology` · `interview` · `execution` ·
> `tests` · `docs` · `gui`

**A replacement was designed and is rejected, and the reasoning is recorded because it is the useful
part.** The proposal was to drop place-names in favour of cross-cutting concerns — `performance`,
`security`, `error-handling`, `migration`, `testing`, `documentation`, `accessibility` — under a
rule that reads well: **a label earns its place when the filter it gives you is not already
available from the plan's structure.** Place-names looked like exactly what a component already
gives you.

**Measured against the frozen v2 plan, that is true of 8% of it.** Method: count live rows across
the seventeen row tables in `spec/v2/plan.db` and ask how many have any path to a component, by
column or by link.

| | |
|---|---|
| live rows across seventeen row tables | **687** |
| rows carrying a component, as a column | **53** (contracts, and only contracts) |
| rows linking to a component | **4** |
| **rows with no path to a component at all** | **630 of 687 — 92%** |

Requirements, decisions, entities, use cases, steps, extensions, state-machine cells, the CRUD grid,
dependencies, findings and spikes are 92% of a plan and **none of them belongs to a component.**
"Show me everything about the storage engine" is not a query the plan's structure can answer for any
of them. The rule survives; the conclusion drawn from it was drawn from the one table that happened
to be the exception.

**The rule does bite in one place, and it is named rather than hidden.** A *task* reaches a
component through its contract, so a place-label on a task is partly redundant with a query the
graph can already answer. That is one of the two things the owner asked to filter. It is not an
argument for withholding the label: the structural query requires knowing the contract and the
component, and the label answers it in one word at the moment of review.

**Nothing is added to the ten.** `VOCABULARY.md`'s argument — *ten because the failure mode is too
many, not too few* — is the whole design, and adding seven cross-cutting concerns would be a 70%
increase in the starting set with no measurement behind it.

**The list has one home and it is a code constant.** `STARTER_LABELS` in `engine/labels.py`;
`VOCABULARY.md` quotes it, the stage-6 script quotes it, and 4F asserts the quotes are true. The
draft put it in the stage-6 script alone and called it "not a denominator"; the cold read found the
duplication that argument hid — the same ten words were also written out in `VOCABULARY.md`, with
nothing holding the two equal. **That is the duplication this product exists to catch, in the packet
that quotes the doctrine**, and a constant with two asserted quotations is the mechanism that makes
the rule true rather than stated.

**And the starters are deliberately *not* injected into the ranking as candidates, which reverses
the cold read's fix.** The reader's argument was that with nothing seeded and a corpus of live
labels only, day one shows the planner nothing. That argument was correct for a separate label
vocabulary that nothing ever seeded. **Under one vocabulary it does not hold**, for two reasons, and
the second is measured:

- The corpus is the glossary, which fills from stage 1. By the stage-6 labelling round a plan has
  terms in it, and the first `define_term` call on an empty glossary cannot be a near-duplicate of
  anything — an empty corpus at that moment is the correct answer, not a hole.
- **An undefined word cannot rank.** A candidate with no definition is a bare word, and §3.3's
  measurement below is that against candidates carrying no definitions only **3 of 14** proposals
  are shown anything at all, against **13 of 14** when the definitions are there. Injecting ten
  definitionless starters would add candidates that almost never surface, and when one did surface
  it would offer the planner a word nobody has defined — a confidently wrong answer of exactly the
  kind 4B.1 refuses to give for retired entries.

### 3.3 What the guard actually catches, re-measured — and the tie nobody had noticed

**Method, in full.** Fourteen proposals are ranked against ten candidates. The tokeniser is
`TermService._tokens` unchanged: `WORD` and `ADDRESS` from `terms.py:82-86`, lowercased, plurals
folded on a trailing `s`, addresses stripped from prose, `_` and case boundaries splitting
identifiers. A candidate's token set is its word plus its definition; a proposal's is the same. A
candidate scores on words shared with the proposal, **a word in the candidate's own name counting
double**, and a candidate sharing nothing is not a candidate at any rank. The page is five. Both
lists are written out in full below, definitions included, because **the definitions are what the
ranking matches on** — a method that omits them looks checkable and is not.

**The candidate corpus is the ten starter words with the one-sentence definitions a proposal would
write for them.** It is a stand-in for a real glossary and it is the right shape for one: under §0 a
candidate is a term, and a term is a word with a one-sentence definition. `spec/v2/plan.db` has no
`terms` table to measure against instead — the frozen v2 plan predates the glossary, which is D1.

| candidate | definition |
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

**The fourteen proposals and the top-ranked candidate each was shown, unweighted** — this is the
ranking exactly as change 3 specifies it today, and every figure in this table is labelled
*unweighted* because §3.4 changes it:

| proposal (and its definition) | top candidate | matched on |
|---|---|---|
| `ui` — the user interface | `gui` | interface, the, user |
| `database` — the database and its tables | **4-way tie** | engine / schema / storage / tests |
| `db` — where rows are stored | **— nothing —** | |
| `testing` — checking that the code does what it says | `tests` | it, the, what |
| `test` — a check over one behaviour | `tests` | test |
| `documentation` — written documents for a person to read | `docs` | a, document, documents, for, person, read, to, written |
| `front-end` — the part the user sees | `gui` | the, user |
| `api` — the calls a client makes | `surface` | a, call, calls, client, the |
| `migrations` — moving a store from one schema version to the next | `schema` | schema, the |
| `stages` — the interview's ordered rounds | `interview` | interview, stage, stages, the |
| `performance` — how fast it runs and how much it costs | **3-way tie** | engine / interview / tests |
| `security` — keeping the store and its secrets safe | `engine` | and, it, store, the |
| `error-handling` — what happens when a call fails | **2-way tie** | execution / surface |
| `errors` — the named failures a call can raise | `surface` | a, call, the |

**13 of 14 proposals are shown a candidate to adjudicate, at a mean of 4.43 candidates over all
fourteen and 4.77 over the thirteen that were shown anything.** The two figures are given because
4.43 × 14 = 62 exactly, so a single mean silently includes the probe that was shown nothing — which
is what the draft did.

**The word `the` accounts for 46% of every match.** Across the 140 proposal-by-candidate pairs there
are 155 matched-word occurrences; `the` is 72 of them, `and` 21, `a` 18. `the` appears in **8 of the
10** candidate definitions and `and` in 7.

**Four of the fourteen top-ranked candidates rest entirely on words several candidates share** —
`database`, `testing`, `performance` and `error-handling`. The draft said three; the fourth is
`testing → tests` on *it, the, what*, which reaches the right answer by pure noise and is worth
naming as such: the guard being accidentally right is not the guard working.

**This is the owner's own standing ruling arriving from the other side.** He killed a word-frequency
rule with *"are we going to make a glossary entry for 'the'?"*. Here `the` does not create a
threshold — it creates a **false top-ranked candidate**, which is worse, because the top of the
ranked list is the one thing the mechanism makes mandatory to adjudicate.

**The finding the draft's own table concealed: the top of the ranking is frequently a tie.**

| | unweighted | rarity-weighted (§3.4) |
|---|---|---|
| proposals whose top-ranked candidate is a **tie** | **4 of 14** | **2 of 14** |
| the worst case | `database`: `engine`, `schema`, `storage` and `tests` all score 3.0 | `database`: `schema` and `storage` both score 1.2679 |

**The draft reported one arbitrary member of each tie as "the top candidate", and that is why its
table is not reproducible from its own stated method** — it has `database → engine` where `engine`
is one of four at the same score, and `error-handling → surface` where `surface` and `execution` are
level. Re-running a stated method before trusting it is the standing lesson from the last cold read,
and this is the second measurement in this change to fail it.

**It is a design hole, not just a reporting one — and change 3 has half the answer already, which
is worth being precise about rather than claiming it has none.** Change 3's task 3B.1 behaviour 7
breaks ties on the lower `id`, and its argument is right and is not reopened here: without a total
order the required answer changes between the call that showed the candidates and the call that
answers them, so *"the planner adjudicates what they were shown and is refused for not adjudicating
something else."*

**Stability is necessary and it is not sufficient.** A deterministic tie-break makes "the
highest-ranked candidate" well-defined; it does not make it *meaningful*. When four candidates score
identically, the `id` tie-break decides which one the planner is compelled to write a sentence
about — insertion order standing in for relevance — and the three equally-ranked alternatives are
never adjudicated at all. The planner answers for `engine` because it was defined first, and
`storage` goes by unexamined.

**Settled: the refusal names every candidate tied at the top score and requires a comparison for
each of them.** The tie-break then orders the display; this sets the obligation, and the two do
different jobs. Requiring all of them is not a threshold — it is what "highest-ranked" means when
more than one candidate is highest. **And it is a third thing the rarity weight buys**: it halves
the ties, so the common cost is one adjudication and the worst case falls from four to two.

**Change 3 has the identical hole and does not know it**, because its own measurement counted
adjudications per registration rather than per candidate. §11.2 carries the amendment, and it moves
none of change 3's numbers: a tie changes which comparisons a registration needs, not whether it
needs one.

**One case is caught by nothing: `db`.** No shared word with any candidate, so no candidate at any
rank. `terms.py`'s own docstring already admits this and the admission transfers verbatim: *"it
matches words, so a new name invented for an existing concept, sharing no letters with it, goes
unseen. Nothing without judgment can catch that."* An acronym is that case. Stated here so the guard
is not oversold: it catches the near-duplicate that shares vocabulary, which is most of them, and it
will never catch `db`.

**And the definition is what does the work, not the word.** Three variants, same method:

| | proposals shown anything |
|---|---|
| both sides carry definitions | **13 of 14** |
| the **proposal** carries no definition | **4 of 14** |
| the **candidates** carry no definitions | **3 of 14** |
| neither side carries one | **1 of 14** |

That is change 3's *"the purpose line carries the whole weight of the search"* holding at a second
site, it is why `definition` is already required on a term, and it is §3.2's argument against
injecting definitionless starters. **The draft reported the third row as 1 of 14; 1 of 14 is the
fourth row.**

### 3.4 Stop words are not a task-local decision, and the fix is a weight rather than a list

**Change 3 says twice — §3.7 and task 3B.1 — that "how stop words are handled is task-local and this
specification does not make it."** §3.3 is what that decision looks like when it is made by nobody:
`the` deciding 46% of the matching, four of fourteen mandatory adjudications resting on noise, and
four of fourteen top positions undefined.

Three answers, measured against the same set:

| | proposals shown a candidate | mean shown (all / shown) | top resting only on common words | top is a tie |
|---|---|---|---|---|
| **A** count shared words, all equal *(change 3 as written)* | 13/14 | 4.43 / 4.77 | **4** | **4** |
| **B** drop words appearing in more than one candidate | 12/14 | 1.07 / 1.25 | 1 | — |
| **C** weight each shared word by how rare it is | 13/14 | 4.43 / 4.77 | **1** | **2** |

**Settled: C. A shared word contributes in inverse proportion to how many candidates contain it.** A
word in eight of ten candidates contributes an eighth of what a word in one contributes. `the` stops
deciding anything without anybody writing `the` down anywhere.

Three things make this the right answer rather than a compromise:

- **It is not a threshold, and B is.** B has a number in it that decides whether a word counts,
  which is a judgment written as arithmetic so review cannot see it — the standing ruling. C has no
  cut-off: every shared word still counts, and the weight orders the list. The mechanism already
  takes *the top of the list* without asking whether it is similar enough, so ordering is the only
  thing the weight can affect.
- **It is not a maintained list.** A stop list is a document of English that somebody has to keep
  true, in an engine whose entire subject is that a rule in a document is not a mechanism. C is
  computed from the candidate set itself and is right by construction as that set changes.
- **It changes no candidate's eligibility, so every number change 3 measured stands.** A shared word
  is still a shared word: verified with the page limit removed, the candidate set is identical under
  A and C for every one of the fourteen proposals. Change 3's *74 of 635 registrations shown
  nothing*, its *561 adjudications* and its *mean 3.90 on a page of five* are all properties of
  eligibility and page size, and none of them moves. **B does not have this property** — it silently
  drops candidates, taking one proposal from "shown something" to "shown nothing", and would
  invalidate change 3's denominators without anyone noticing.

**What it buys, precisely, and the draft overclaimed it.** The weight **reorders; it does not
exclude.** A candidate sharing only `the` still has a non-zero score, is still a candidate, and can
still be the one at the top. So this section is not headed "stop words are answered" — they are not
answered, and a planner will still sometimes adjudicate noise. What the weight buys is exactly
three things:

1. **When a real shared word exists, it wins.** Four noise-topped proposals become one.
2. **Ties at the top halve**, from four to two, which is the new finding in §3.3 and the one that
   matters most, because a tie makes the mandatory adjudication undefined.
3. **Nothing else.** `performance` moves from `engine` (*and, it*) to `interview` (*and, how*) —
   junk replaced by different junk. That is the honest reading: **weighting fixes the matches that
   had a real word available, and does not manufacture one where none exists.**

**The draft's headline example is also wrong and the correction is instructive.** It claimed
`database` moves from `engine` to `storage` on the word *database*. Re-measured, weighting leaves
`database` tied between `storage` (on *and, database, the*) and `schema` (on *and, table, the*) at
1.2679 apiece — the rare word `database` in `storage`'s definition and the rare word `table` in
`schema`'s are worth the same. Both are defensible answers and the planner should see both, which is
§3.3's settlement doing its job on the very example the draft used to advertise the weight.

**This is a correction owed to change 3, and §11 is where it is written.**

### 3.5 Two relationships, not five, because labels are allowed to overlap

Change 3 records a comparison with five relationships — `same`, `contains`, `contained_by`,
`partially_overlaps`, `unrelated` — and the argument for the fifth is that overlap is asymmetric and
each direction is a different instruction to the planner.

**None of that transfers, and the reason is in D12's first paragraph.** A row *"may carry none or
several, they overlap freely"*. In the catalogue an overlap is a defect with a prescribed repair —
extract the shared middle, fold the smaller in. For a label, overlap is the specification. A row
labelled `engine` and `storage` is not a duplication to be resolved; it is two true filters.

**The same holds one level up, for terms, and that is what makes one table right for both.** Two
glossary terms are allowed to be related without either containing the other; `define_term`'s
question has never been "how do these two overlap", it is "have you just defined this twice".

**So there is exactly one judgment to record about a near match: is this the same word?**

| relationship | what it means to do | may the word be written? |
|---|---|---|
| `same` | use the term that exists | **no** |
| `distinct` | a different meaning; write it, and the reason says how they differ | yes |

**`distinct` and not `unrelated`, and the difference is not cosmetic.** `unrelated` is change 3's
word for "these are not the same thing, record the negative", and it is honest there because
containment has its own values. Here it would be a lie in the common case: `error-handling` and
`errors` are plainly *related* and plainly not the same word, and a planner forced to file that as
`unrelated` is being made to write something untrue in a record the owner reads. One word per job.

**`same` refuses the write, which is what makes the adjudication load-bearing**, exactly as in change
3: the cheap way past a required field is to write whatever gets you through the door, and the answer
a planner reaches for when the match is real is the one that stops the write. The remaining
dishonesty — answering `distinct` about something that is not — is a lie in a record the owner can
read, which is the standard `dismiss_gap` and the waiver log already set.

**A comparison is recorded whether or not a term follows it**, and change 3's argument applies
unchanged: *"if only merges are written down, the next planner runs the same search, sees the same
candidate, and decides again — possibly the other way."*

**`term_comparisons` does not serve the catalogue**, and the boundary is the same one change 3 drew:
a catalogue entry is identified by *(name, container)* and `catalogue_comparisons.matched_id` is a
real foreign key into a real table; collapsing the two would trade that key for a string.

**`matched` is stored as the word, not as an id**, following `terms.use_instead`, whose reason is
quotable and transfers whole: *"a retirement outlives the entry it points at — the replacement will
itself be redefined one day — and the word is the identity that survives that."* This is the same
sentence that keys the attachments in §3.6, applied to a second column, and it is the sentence §0
turns on.

### 3.6 Attachments key on the word and on the lineage root, and the obvious index enforces nothing

**Keyed on the word**, for §0's reason, which is `terms.use_instead`'s reason. A `label_id` would be
a pointer into a table whose rows supersede on every redefinition, so redefining a description would
detach every row that carried it. Keyed on the word, `redefine_term` is invisible to the
attachments, which is the correct behaviour and requires no code to achieve.

**No foreign key on the word, and it is a real cost stated rather than hidden.** `idx_terms_live` is
a *partial* unique index, and SQLite requires a non-partial UNIQUE or PRIMARY KEY as an FK's parent,
so `REFERENCES terms (term)` cannot be declared. The service enforces it (4B.2 behaviour 3) and 4F
asserts the service enforces it, which is weaker than the database refusing it. The alternative —
keying on `label_id` to get a real FK — buys the constraint by reintroducing the detach-on-redefine
bug §0 exists to remove, and that trade is not close.

**Keyed on the target's lineage root**, following `scope_attachments` and `gap_overlay`, whose
comment is the argument: keyed that way so a record *"neither re-surfaces nor silently detaches"*
across supersession. A label that detached on supersession would mean every revision silently drops
the owner's filters, one row at a time, with nothing to see. `RowService.lineage_root`
(`rows.py:585`) is the canonical implementation and this is its third application — its own
docstring already says why it lives there rather than on a caller.

**Two id spaces, and the shape is change 3's.** A plan row is addressed by ref; a task is an integer
id in a table of its own. So `target_root TEXT` and `task_id INTEGER`, with a `CHECK` that exactly
one is set — the arrangement `catalogue` already uses for `task_id` / `component_ref`, and a real
foreign key on the task half, which a single polymorphic `target_key` string could not have.

**No `target_kind` column.** Change 3 needed `kind` because object-or-function is an independent fact
that also appears in an index predicate. Here nothing is independent: which column is set *is* the
kind, and storing it as well would be a second source of truth for a fact the row already carries.
That is convention 8 — derived reports are computed at read and stored nowhere.

**The natural uniqueness index enforces nothing whatsoever, and this is the single most likely
build-time defect in this change.** One live attachment per (word, target) is what makes the usage
count in §3.8 mean anything — attach twice and the count silently inflates. The obvious index is

```sql
CREATE UNIQUE INDEX idx_label_attachments_live
    ON label_attachments (word, target_root, task_id) WHERE detached_at IS NULL;
```

**Re-probed at SQLite 3.49.1 under Python 3.12.10 against this shape — the key column is now `word
TEXT` rather than the draft's `label_id INTEGER`, so the probe was re-run rather than inherited.
Every duplicate is accepted.** Not some — every one. SQL compares NULLs as distinct, and by the
`CHECK` above *every row in this table has exactly one NULL among the two target columns*, so no two
rows ever compare equal and the index is inert for its entire lifetime.

**Change 3 met this trap and it was worse there than it looked; here it is worse again.** In the
catalogue only module-level entries escaped — which was all eleven of the collisions the table
existed to catch. Here **100%** of rows escape. The index would look correct, run green, and enforce
nothing at all.

**The fix, probed in the same run:** index the expressions, and close both sentinels.

```sql
CREATE UNIQUE INDEX idx_label_attachments_live
    ON label_attachments (word, COALESCE(target_root, ''), COALESCE(task_id, 0))
    WHERE detached_at IS NULL;
```

Probed on the rewritten shape: the duplicate row attachment is refused, the duplicate task attachment
is refused, two different rows are accepted, two different tasks are accepted, and re-attaching after
a detach is accepted.

**Both sentinels are reachable and both are closed by a `CHECK`.** `COALESCE(task_id, 0)`'s sentinel
is not hypothetical: `INSERT INTO tasks (id) VALUES (0)` is accepted despite `AUTOINCREMENT`, and a
row with `target_root = ''` collides with a row with `task_id = 0` — two different targets sharing
one index key. `CHECK (target_root IS NULL OR target_root <> '')` and
`CHECK (task_id IS NULL OR task_id > 0)` make both unreachable; probed, and real rows and tasks still
insert.

**Case is normalised at the source and needs no `COLLATE NOCASE`.** The word written into an
attachment comes from `lexical.word()`, which lowercases and strips, so `GUI` and `gui` are one word
before the index ever sees them — the arrangement `terms` already has. 4F asserts it at the service,
because that is where it is true.

**Attaching a banned word is refused, and this is the one place labelling parts company with the
glossary's warn-never-block rule.** `TermService.violations` warns rather than blocks, and its reason
is quotable: *"a retired word inside a quotation is legitimate — the owner's own words are quoted
verbatim all over a plan — and blocking on one would resurrect the cry-wolf failure D7 fixed."*
**That reason does not reach an attachment.** An attachment is not quoted prose; it is a new
structured act, performed now, by a tool that has just been told the word is retired — and
`use_instead` names exactly what to file the row under instead. There is no legitimate case for
filing a row under a word the plan has agreed to stop using, so there is no cry-wolf to resurrect,
and a warning nobody must act on would leave the filter quietly wrong.

### 3.7 There is no label retirement to build

**Retirement means two different things and §0 resolves it.** Retiring a *term* sets `ban_scope`, and
the glossary then warns whenever the word appears in row content. Retiring a *label* should mean only
"stop filtering by this" — and if it set a ban, every row that merely mentions `gui` would start
nagging. That is the cry-wolf failure `terms.violations` was written to avoid.

**The glossary's own shape already resolves it.** A word is banned only if it carries a `ban_scope`,
and taking a filter out of use sets none. **So there is no label retirement to build:** finishing
with a label is detaching it from everything, which `detach_label` already does. A word that is
banned from prose and a word that is no longer a useful filter are two states of one row, and the
column that distinguishes them exists.

**And the two acts compose correctly rather than colliding.** `retire_term` bans the word for prose;
the attachments carrying it stay, because they are the record that rows were once filed under it, and
`labels()` reports the word as banned with its reason (4B.3 behaviour 5). Attaching it again is
refused (§3.6). Nothing had to be invented for any of that.

**One tool disappears against the draft and it is the second one this design deletes for free.** The
draft argued at length for `retire_label` and for `retire_label` returning a count of attachments
gone dark; neither exists now, and the count is not lost — `labels()` reports it, which is where a
reader would look for it.

### 3.8 The usage report, and the denominator without which it says nothing

`labels()` returns every word that has live attachments, with its definition, whether it is approved,
whether it is banned, and **how many live attachments it has.** No threshold decides what a bad count
is.

**The count alone is not enough, and this project has a defect class for that.** A label on one row
and a label on all of them are both useless for filtering, and the second is invisible without
knowing how many things there are to label. F23 is the standing evidence — a check that runs, passes
and means nothing because its denominator was never defined. So the report carries the denominator:
**the number of live plan rows and the number of live tasks**, as two numbers beside the counts.

**Two numbers and not their sum**, because the targets are two populations and a label on every task
and no row is a different fact from a label on 12% of everything. The draft described it as two
numbers in one place and one sum in another; this settles it.

**The report is over words that are attached, not over the glossary.** A glossary of two hundred
terms of which six are used as filters should not produce a usage report with 194 zero rows —
that is the report drowning its own signal. **`labels()` lists every word with at least one live
attachment**, plus, separately, a count of words that have none, so the absence is visible without
being enumerated.

**No gap counts a label, and nothing warns.** Both would be judgments: a gap for an unlabelled row
makes labels mandatory, which D12 forbids in its first sentence, and a warning for an over-used label
is a threshold in disguise. The tool computes and shows; the owner decides. §10 says so again where
it will be looked for.

**A proposed (unapproved) term may be attached, and this is deliberate.** Blocking would make the
tool unable to do the one job it was given proposal rights for, and a label affects nothing in the
build — which is D12's whole safety argument. The usage count on an unapproved word is precisely the
number that tells the owner whether to settle it or kill it, and it cannot exist if attachment waits
for approval.

### 3.9 The filter, and the two routes it takes

**A label set with no filter is a write-only feature**, which is the unread-field defect class change
3 refused to ship. So this change delivers the read, and — correcting the draft, where the cold read
found that nothing implemented it — **it is a task, 4B.4, not a dataclass field.**

- **`RowSelector` gains `label`**, so `read_rows` filters plan rows by label alongside everything
  else it already does — table, provenance, liveness, paging.
- **`labels(word)` returns what carries that word** — plan rows as name and ref, tasks by id and
  title.

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

**`contracts:10` is a contract this change changes**, and the draft never answered it. `read_rows` is
`contracts:10`, its docstring enumerates the selector's dimensions — *"by ids | table | package |
provenance | liveness | link-neighborhood"* (`models.py:257`) — and this change adds one. Change 2's
precedent superseded five contract rows for exactly this. **4D.1 supersedes `contracts:10` with the
dimension added**, and that is the one contract row this change touches.

### 3.10 How this change lands

**One branch, one pull request, the suite green at the end.** Same shape as changes 1 to 3 and for
the same reason: the packets cannot be made independently green.

**The packet letters are not the landing order, and this is the fourth change running in which that
has been true.** Three rules produce the order, and each has now caught something in every change:

| # | lands | why it cannot land later |
|---|---|---|
| 1 | **4A.0** — the declared vocabulary | 2E.1's check refuses `term_comparisons.reason` the moment 4A.1's DDL exists, and `detached_at` is an undeclared `*_at` role that fails `test_every_timestamp_column_is_a_declared_role`. Declared last, the suite is red from 4A to 4F. Change 1's 1A.0 and change 3's 3A.0, a fourth time. |
| 2 | **4B.0** — the models | 4D.1's `comparisons` parser parses into `TermComparison`, and 4B.4's selector field is typed. Models specified after the packet that consumes them is the cold read's own finding against the draft; they land with 4A. |
| 3 | **4D.1** — the registry rows | 4B.2's refusal says to define the term first, and 4C.1's says to use the existing one. Both are text naming a call, and `door.scan` raises `UnreachableCall` on a payload naming a call the registry cannot resolve. |
| 4 | **4E.1** — the stage-6 script | Same reason one step further out: the labelling round names `define_term()` and `attach_label()`, and the script is served through `get_stage_script`, so it raises until the registry rows exist. |

**So the order is 4A.0, 4A.1, 4A.2, 4B.0, 4D.1, 4B.1, 4B.2, 4B.3, 4B.4, 4C.1, 4D.2, 4E.1, 4F.**

**A guard landing after the schema it must permit is the third recurring shape, and it does not
occur here** — checked rather than assumed. 4A.0 is the only guard this change lands, it is
permissive (it declares vocabulary rather than restricting it), and it lands first.

**The shared ranking is not in this order, and that is the point of §11.** It lands in change 3,
because change 3 is merged and unbuilt, and amending its specification is cheaper and more honest
than specifying a refactor of code nobody has written.

**This change mints methodology revision 6, and `PLAN.md` item 10 becomes revision 7.** Change 2
already stated the general form: *every change touching a stage script costs a revision, so the plan
should expect the number to climb once per such change rather than treating a bump as an event.*

---

## 4. Packet 4A — the schema

Schema version 10 → 11. Nothing else in this change can start until this lands.

### Task 4A.0 — the declared vocabulary, extended

**This lands before the DDL it describes, and that is the whole point of it being 4A.0.**

**Behaviours**

| | behaviour |
|---|---|
| 1 | `term_comparisons.reason` joins `JUSTIFICATION_ROLES`, which becomes **nineteen** members. |
| 2 | `detached_at` joins `TIMESTAMP_ROLES`, which becomes **eight**. |
| 3 | The justification declaration is role 1 — why an act was performed — and names the act: *a near match was judged the same word, or a different one.* |
| 4 | No new suffix and no new `SHAPES` member. |

**Behaviour 1 is 2E.1's check applied to this change's schema, and the count is nineteen — not the
twenty §0 carried forward.** §0 listed "the justification-column count of twenty" among the findings
that survive the rewrite, and the *enumeration and the method* do survive; the total does not.
Twenty was 18 after change 3 plus this change's two, `labels.retire_reason` and
`word_comparisons.reason`. **§0 deletes the `labels` table, so `labels.retire_reason` does not
exist**, and one column is added rather than two. **Re-enumerated from source on 2026-07-30 rather
than adjusted by arithmetic**, because adjusting a count by arithmetic is exactly what produced the
wrong one three changes running.

**The method, in full, because a denominator produced by an unnamed method is not checkable.** Parse
`engine/schema.py` with `_columns()`'s own regex — every `CREATE TABLE IF NOT EXISTS name (…\n);`,
every line matching `^(\w+)\s+(INTEGER|TEXT|REAL|BLOB|NUMERIC)` with comments stripped — and select
the columns 2E.1 behaviour 2 requires to be declared: named `reason`, `grounds` or `alternatives`, or
ending in `_reason`. **Re-run 2026-07-30: 255 columns, and these eleven, before any of the four
changes adds anything:**

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
| this change adds `term_comparisons.reason` | **19** |

**Change 1 renames one key and changes no count**: `subtasks.block_reason` becomes
`tasks.block_reason` when the table moves down.

**Change 2's enumeration is where it went wrong, and the way it went wrong is the register's own
recorded lesson.** Its "three `reason` columns" is a bare-column count — there are **seven** bare
`reason` columns in the schema today, re-counted in the same run — and `terms.ban_reason` and both
`block_reason`s are missing altogether. It was drafted under bare-column keying, change 3 re-keyed it
to `table.column` and restated the total without re-enumerating the members, and the draft of this
change added two to a base that was never right. **A count drafted from a reconstruction rather than
from the source**, which is exactly why `CONVENTIONS.md` requires an entry to quote the code it
records. **Changes 2 and 3 owe this correction and §11.3 carries it.**

**Behaviour 2 is a genuinely new transition and it is declared as one.** `TIMESTAMP_ROLES` holds
**seven** today, re-counted in the same run: `created_at`, `updated_at`, `superseded_at`,
`retired_at`, `resolved_at`, `concluded_at`, `approved_at`. Its comment draws the line: `created_at`
and `updated_at` are the general pair, and *"the rest name a specific transition in a lifecycle —
they are not creation wearing a costume."* Detaching a label is a transition in an attachment's
lifecycle, and no declared role fits it:

- `retired_at` is *"withdrawn from live reads with a recorded reason"*, and detaching records no
  reason. Requiring one would put friction on the one act D12 says the owner does freely.
- `superseded_at` is *"stamped once when a replacement is written"*, and a detachment writes no
  replacement.

So `detached_at` is declared with its own meaning: **the attachment was taken off its target; the row
stays as the record that it was once there.**

**`approved_at` needs no widening, and that is a task the draft had and this one does not.** The
draft added `labels.approved_at`, which would have given a role string naming one site a second one.
There is no second site: approval happens on the `terms` row, where the role already is.

**Behaviour 4 is checked rather than assumed.** `task_id` is INTEGER, `word`, `target_root`,
`proposed`, `matched` and `relationship` are TEXT and none carries a closed suffix, and `SHAPES` —
`_id`, `_key`, `_ref`, `_by`, re-counted at four — is untouched. `task_id` matches `_id` and is an
integer id, which is what that shape declares.

### Task 4A.1 — the DDL text

**Signature.** None — `schema.LABELS_DDL` is module-level text appended to `DDL`, and
`SCHEMA_VERSION` becomes 11.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Two tables are declared: `label_attachments` and `term_comparisons`. |
| 2 | Held in one named block appended to `DDL`, so a fresh store and a migrated one are created from the same text. |
| 3 | One live attachment per (word, target), enforced on `(word, COALESCE(target_root, ''), COALESCE(task_id, 0))`. |
| 4 | Exactly one of `target_root` and `task_id` is set, as a `CHECK`; and neither sentinel value is reachable, as two more. |
| 5 | `term_comparisons.relationship` is constrained to `same | distinct`, as a `CHECK`. |
| 6 | `label_attachments.word` carries **no** foreign key, and the DDL comment says why. |
| 7 | The version-10 DDL is retained as the fixture the parity check migrates from, **outside `engine/schema.py`**. |

**Behaviour 2 is the pattern `TERMS_DDL` established**, quoted rather than restated: *"Two copies of
a `CREATE TABLE` is a schema that drifts between the stores that were migrated and the stores that
were born."*

**Behaviour 3 is §3.6, and the naive form is the trap.** The comment sits on the index, in the
schema, where the next person to edit it will read it — and it says that the naive form accepts
**every** duplicate rather than an unlucky few.

**Behaviour 5 constrains `relationship` for change 3's reason, restated because it is the same
mechanism**: the value selects between the branch that writes the term and the branch that refuses
it, so a misspelling does not fail — it takes the permissive branch and writes the term the planner
had just said not to write.

**Behaviour 6 is the cost §3.6 states, written where a builder will meet it.** A builder reading
`word TEXT NOT NULL` beside `task_id INTEGER REFERENCES tasks (id)` will assume the missing
`REFERENCES terms (term)` is an oversight and add it, and SQLite will reject it at create time with a
message about the parent key — which reads as a mistake rather than the constraint it is.

**Behaviour 7 continues the pattern changes 1, 2 and 3 all owe a sentence to.** `_columns()` in
`test_schema_vocabulary.py` reads the whole of `engine/schema.py` and regexes every `CREATE TABLE IF
NOT EXISTS` out of it, so a retained v10 DDL sitting there is phantom schema for every vocabulary
test — including 4A.0's own new count.

**The DDL**

```sql
-- A label is a glossary term that has been attached to rows; there is no label table
-- (spec/v3/builds/04-labels.md §0). This table is the attachment and nothing else.
CREATE TABLE IF NOT EXISTS label_attachments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    word        TEXT    NOT NULL,  -- the term, as the word. No REFERENCES terms (term):
                                   -- idx_terms_live is a *partial* unique index and SQLite
                                   -- will not take one as an FK parent. Keying on terms.id
                                   -- would buy the FK and cost the design — every
                                   -- redefine_term supersedes the row, silently detaching
                                   -- every target. The word is the identity that survives
                                   -- redefinition (DEVIATIONS.md, terms.use_instead).
    target_root TEXT,              -- the lineage root of a plan row, so the label neither
                                   -- re-surfaces nor silently detaches when the row is
                                   -- superseded (rows.py, lineage_root)
    task_id     INTEGER REFERENCES tasks (id),
    detached_at TEXT,              -- null == the label is on this target now
    created_at  TEXT    NOT NULL,
    CHECK ((target_root IS NULL) != (task_id IS NULL)),
    -- Both COALESCE sentinels below are reachable without these. Probed: INSERT INTO tasks
    -- (id) VALUES (0) is accepted despite AUTOINCREMENT, and a row with target_root = ''
    -- then collides with it — two different targets sharing one index key.
    CHECK (target_root IS NULL OR target_root <> ''),
    CHECK (task_id IS NULL OR task_id > 0)
);

-- Indexed on the expressions, not the columns. Every row here has exactly one NULL among
-- the two target columns, and SQL compares NULLs as distinct — so the natural form,
-- (word, target_root, task_id), accepts *every* duplicate rather than an unlucky few.
-- Probed at SQLite 3.49.1: it enforces nothing at all for the whole life of the table, and
-- the usage count in labels() silently inflates on a double attach.
CREATE UNIQUE INDEX IF NOT EXISTS idx_label_attachments_live
    ON label_attachments (word, COALESCE(target_root, ''), COALESCE(task_id, 0))
    WHERE detached_at IS NULL;

-- Read when a row is rendered with the labels it carries (4D.2). The live index above
-- leads on word and cannot answer that direction.
CREATE INDEX IF NOT EXISTS idx_label_attachments_target
    ON label_attachments (target_root, detached_at);

-- One judgment about one near match between two words. The catalogue keeps its own table,
-- because its identity is (name, container) and its matched_id is a real foreign key.
CREATE TABLE IF NOT EXISTS term_comparisons (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    proposed     TEXT    NOT NULL,  -- the word that was being defined
    matched      TEXT    NOT NULL,  -- the candidate, as the word: a retirement outlives
                                    -- the entry it points at
    relationship TEXT    NOT NULL,
    reason       TEXT    NOT NULL,
    created_at   TEXT    NOT NULL,
    CHECK (relationship IN ('same', 'distinct'))
    -- Constrained because a misspelling takes the branch that writes the word: the typo
    -- does not fail, it inverts the refusal (§3.5).
);
```

**Four statements — two tables and two indexes — and this was probed through `schema.statements`
itself** rather than counted by eye: the block above yields exactly four. The split is on semicolons
and survives **only because comments are stripped first**, which is a real dependency and not the
non-issue the draft called it: the block contains semicolons inside comments.

**`term_comparisons` has no `updated_at` and that is not an oversight.** It is an immutable audit
record like `catalogue_comparisons`, `finding_reallocations` and `behaviour_amendments`; the
vocabulary check's own note says `updated_at` is *"absent on immutable tables by design"*.

**`label_attachments` has none either**, following `scope_attachments`, which carries `created_at`
and a lifecycle stamp and nothing else. An attachment is not edited; it is made and taken off.

**There is no `kind` column on `term_comparisons`**, which the draft had, and its absence is the
whole of §0 in one column: there is one vocabulary, so there is one kind.

### Task 4A.2 — `Storage._migration_steps`, the 10→11 branch

**Signature.** Unchanged. Gains one branch.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Creates both tables and both indexes, from `schema.LABELS_DDL` via `schema.statements`. |
| 2 | Backfills nothing, and seeds no starter word. |
| 3 | Adds nothing to the snapshot table set. |

**Behaviour 1 reuses `statements()` rather than restating the SQL, and the split between the branches
is clean.** Re-counted from `engine/storage.py` on 2026-07-30: **four branches exist today** — 3→4
(the glossary), 4→5 (`findings.resolve_by` plus `finding_reallocations`), 5→6 (the revision tables)
and 6→7 (the change feed). Changes 1, 2, 3 and 4 add one each, so **this change lands the eighth.**
Every branch that creates a whole new table takes its SQL from `statements()`; the ones that add a
column to an existing table issue `ALTER`s of their own, and 4→5 does both. **This change is purely
the first kind**, which is why behaviour 1 is unqualified.

**Behaviour 2's second half is the starter list's mechanism question answered.** The ten could have
been inserted here as proposed terms. They are not, for two reasons: a migration is the schema
changing, not the tool proposing, and seeding would put ten proposals into every existing plan
including ones that are finished. **The ten live in `STARTER_LABELS` in `engine/labels.py`** (§3.2),
quoted by `VOCABULARY.md` and by the stage-6 script, with 4F asserting both quotations.

**This reverses the draft's "the list is not a denominator", and the reversal is the cold read's.**
The draft put the list in the stage-6 script alone and argued that nothing depends on it. Two
documents already wrote the same ten words out, with nothing holding them equal — which is the
duplication this product exists to catch. A constant with asserted quotations is the mechanism; the
draft had a rule in a document.

**Behaviour 3 follows change 3's reasoning exactly.** `snapshot_version` carries nine tables and
`tasks` is not among them: the whole execution layer sits outside snapshots. A `label_attachments`
inside the snapshot set would be rewound while the `tasks` rows and `plan_rows` it points at were
not. Both new tables stay out, together.

**A consequence inherited, not created.** `recover('restart')` clears eight tables and leaves
`terms`, `findings` and the execution layer standing; the attachments join that set, so a restart
leaves labels attached to a plan that no longer exists. That is v2's behaviour for every table
outside the eight, and fixing it would be a change about recovery.

---

## 5. Packet 4B — the attachment service

Depends on 4A and, from 4B.1 onward, on 4D.1 (§3.10). A new module, `engine/labels.py`, and
`models.py`.

**`LabelService` is constructed with `Storage`, `RowService` and `TermService`, and none is
optional.** `RowService` resolves a target's lineage root and confirms the supplied ref exists;
`TermService` answers whether a live term holds the word and whether it is banned. The reason this is
written out rather than assumed is convention 11: an unpassed collaborator has its guard skipped and
its effects omitted, and the call proceeds — so a label service missing its row service would attach
labels to refs it never checked, and look identical to a working one.

**`TermService` *is* a collaborator here, which reverses the draft.** The draft argued it was not,
on the grounds that a label is a word in its own right rather than prose written in the plan's
vocabulary — and then its own pseudocode called `terms._word()` on the first line, which the cold
read caught. Under §0 the question does not arise: a label *is* a term, so the service that owns
terms is the service that answers whether one exists.

**`LabelService` does no ranking.** The near-match search lives in `TermService` (4C.1), because
under §0 the thing being guarded is the glossary. This is the largest single simplification §0 buys
and it is worth stating plainly: **there is one near-match mechanism, in one module, with one
caller.**

### Task 4B.0 — the models

**Signature.** Five frozen dataclasses in `models.py`. **This task lands with 4A** (§3.10), because
4D.1's parser and 4B.4's selector field both consume these types.

**Behaviours**

| | behaviour |
|---|---|
| 1 | `TermComparison` — `matched: str`, `relationship: str`, `reason: str`. |
| 2 | `Candidate` — `word: str`, `definition: str`, `matched_on: tuple[str, ...]`, `score: float`, `tied_at_top: bool`. |
| 3 | `Attachment` — `id: int`, `word: str`, `target_root: RowRef \| None`, `task_id: int \| None`, `detached_at: str \| None`, `created_at: str`, with an `is_live` property. |
| 4 | `LabelUsage` — the word, its definition, `is_approved`, `is_banned`, and its live attachment count split into rows and tasks. |
| 5 | `LabelReport` — the usages, the two denominators, the count of live terms with no attachment, and, when one word was asked for, its targets. |

**This task exists for the reason change 3's 3B.0 exists**, and the conventions register states it as
a rule: a return type's fields are **not** a convention, because they differ per task, so they are a
hole in every task that leaves them out. The recorded v2 defect is `WriteBatch`, `RowSelector`,
`TraversalSpec` and `GraphScope` — four types named by the plan and defined nowhere, *"so two
implementers would have built two incompatible interfaces."* **The draft committed that defect inside
the task written to prevent it** — it used seven types and defined four — which is why every type
this change names is in the table above and every field is listed.

**Behaviour 2's `tied_at_top` is §3.3's finding made into a field.** The refusal must require a
comparison for every candidate tied at the top score, so *which candidates those are* is part of the
search's answer and not something a caller recomputes from `score` floats. Recomputing it would put a
float equality test in the refusal path, in two places, with nothing holding them equal.

**Behaviour 3's `target_root` is a `RowRef`, not a string**, because every other model in this engine
that holds a row address holds a `RowRef`, and the door resolves them. The column is TEXT; the model
coerces.

**Behaviour 4 carries the counts split by population rather than summed** (§3.8), and behaviour 5
carries the denominators inside the report rather than beside it, so a caller cannot render a count
without one. A count whose denominator is one call away is a count that gets rendered alone.

**There is no `LabelResult` and no `Label`.** `define_term` returns a `Term`, which exists;
`attach_label` returns `Attachment`s. The draft's three-branch `LabelResult` was the shape a
`propose_label` needed, and there is no `propose_label`.

### Task 4B.1 — the read path

**Signature.** Three private methods on `LabelService`: `_live_term(word: str) -> Term`,
`_target_key(target: RowRef | str | int) -> tuple[str | None, int | None]`, and
`_attachments(word: str) -> tuple[Attachment, ...]`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | `_live_term` returns the live `terms` row for a word, or refuses with `TermNotFound` naming `define_term`. |
| 2 | `_live_term` refuses with `TermBanned` when the word carries a `ban_scope`, naming the ban reason and `use_instead`. |
| 3 | `_target_key` returns `(lineage root, None)` for a ref and `(None, task id)` for a task id, and refuses anything else. |
| 4 | The word is normalised through `lexical.word()` — stripped and lowercased — and an empty one is refused. |
| 5 | `_attachments` returns live attachments only, unless asked for all. |

**Behaviour 2 is §3.6's departure from warn-never-block**, and the refusal carries `use_instead`
because that is the whole of the remedy: the planner is one word away from the right call.

**Behaviour 3 is where the two id spaces are told apart, and `isinstance(x, int)` is not how.**
`bool` subclasses `int` in Python, so `isinstance(True, int)` is `True` and `attach_label(word,
(True,))` would be read as task 1. The test is `type(x) is int`, or an explicit `bool` rejection
first. This is small and it is exactly the class of thing that is invisible until a caller passes a
flag by mistake.

**Behaviour 4 reuses the glossary's normalisation rather than writing a second one**, and the case
that makes it matter is real: `GUI` and `gui` attached a week apart are the same label, and an index
that treated them as two would inflate every count. `_word` moves to `engine/lexical.py` as
`word()` in change 3 (§11.1), so both services call one function rather than one importing the
other's private static method — which is what the draft specified and the cold read flagged.

### Task 4B.2 — `attach_label` and `detach_label`

**Signature.** `attach_label(self, word: str, targets: tuple[RowRef | str | int, ...]) ->
tuple[Attachment, ...]` and `detach_label(self, word: str, targets: tuple[RowRef | str | int, ...])
-> tuple[Attachment, ...]`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | One word, many targets, in one transaction. |
| 2 | A plan-row target is keyed on its **lineage root**; a task target on its id. |
| 3 | Refuses with `TermNotFound` when no live term holds the word, saying to define it first. |
| 4 | Refuses with `TermBanned` when the word is retired, naming the reason and `use_instead`. |
| 5 | Refuses with `RowNotFound` naming the ref, or `TaskNotFound` naming the id, when a target does not exist. |
| 6 | Attaching a word already on a target is a **no-op**; detaching one that is not attached is likewise. |
| 7 | Duplicate targets **within one call** are collapsed before the write, not left to the index. |
| 8 | An empty `targets` is a valid no-op returning an empty result. |
| 9 | An unapproved term may be attached. |
| 10 | Neither call takes a reason. |
| 11 | Both return the live attachments for the word after the call. |

**Behaviour 1's shape — one word, many targets — is the direction the work actually goes.** A planner
labelling at stage 6 has just decided what `engine` means and is placing it across a handful of rows;
the opposite shape would make that call once per row.

**Behaviour 2 is §3.6.** The lineage root is resolved through `RowService.lineage_root`, which is the
canonical implementation and is not reimplemented here.

**Behaviour 3's message names a call**, which is what puts 4D.1 before this packet (§3.10).

**Behaviours 6 and 7 are one decision and the draft got half of it.** An empty collection is a valid
no-op returning an empty result (convention 10), and the same reasoning extends to a duplicate:
asking for a state that already holds is not an error, and refusing would make a batch of ten targets
fail because one was already labelled. **But a unique index does not produce a no-op — it raises and
aborts the batch**, so the no-op has to be a service-side check and the index is the backstop, not
the mechanism. The cold read found this against the draft, and it found the sharper half too:
**duplicate targets inside a single call** would reach the index as two inserts in one batch and take
the other nine rows with them. Behaviour 7 collapses them first.

**Behaviours 3 to 5 make the guards service-side, and 4F asserts the index behaviour separately for
exactly that reason** — driven through the service, the duplicate never reaches the index, so a test
that drives the service proves nothing about the constraint (4F.1).

**Neither call takes an idempotency key, and this is a decision the new design earns.** `write_atomic`
requires one, so each passes a key derived from the call's own arguments — the word and the sorted
target keys — rather than taking one from the caller. The reason is that **both calls are idempotent
by construction**: behaviour 6 makes a repeat a no-op that returns the same answer, so there is no
replay to protect against. The draft argued hard for a caller-supplied key on four writing calls and
the cold read found that **not one of them could ever consult it**, because every path refuses or
no-ops before `write_atomic`. Here the guard is not unreachable — it is unnecessary, which is a
different and better answer.

**Behaviour 10 is D12's control level in the schema.** Attaching is the act the owner performs
freely, and a required reason on it would be friction on the one thing the design says is free.

**Behaviour 9 is §3.8.** Blocking would make the tool unable to do the job it was given proposal
rights for.

**Behaviour 11 returns the state rather than the delta**, because a no-op has no delta and a caller
that got an empty tuple could not tell "already attached" from "nothing happened".

**Pseudocode**

```
w = lexical.word(word)                      # TermNotFound on empty
term = self._live_term(w)                   # TermNotFound / TermBanned
keys = []
for t in targets:
    keys.append(self._target_key(t))        # RowNotFound / TaskNotFound / TypeError
keys = dedupe(keys)                         # behaviour 7, before the index sees them
live = {key of a for a in self._attachments(w)}
ops = [insert (w, root, task_id) for key in keys if key not in live]     # attach
#     [update detached_at for key in keys if key in live]                # detach
if ops:
    self.storage.write_atomic(ops, self._key(w, keys))
return self._attachments(w)
```

**A sequencing consequence that bites now and stops biting at change 5.** `task_id` references a row
in `tasks`, and until change 5 moves task creation to stage 8, tasks are still derived at
finalization — so a task can only be labelled on a plan that has been finalized. That is awkward for
this change's end-to-end drive and it is not a defect; it is the same constraint change 3 recorded
for function entries, and change 5 is what removes it. Plan-row targets have no such constraint.

### Task 4B.3 — `labels`

**Signature.** `labels(self, word: str | None = None) -> LabelReport`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | With no argument: every word carrying at least one live attachment, alphabetically, with its definition, whether it is approved, whether it is banned, and its live attachment count split into rows and tasks. |
| 2 | The report carries **two** denominators — live plan rows, and live tasks — never their sum. |
| 3 | It also carries the number of live terms with no live attachment, as a count and not a list. |
| 4 | With a word: that word, its counts, and every target carrying it. |
| 5 | A banned word with live attachments is reported, marked banned, with its ban reason. |
| 6 | A plan-row target is returned as its name and its ref; a task as its id and its title. |
| 7 | A word with no live attachment, named explicitly, is reported with a zero count — not as missing. |
| 8 | No threshold, no warning, no gap. |

**Behaviour 2 is §3.8 and it is the half a builder would drop**, because a count reads as complete on
its own. It is not: a label on all 687 rows and a label on one are both useless for filtering, and
only the denominator distinguishes the first from a healthy one.

**Behaviour 3 is the report refusing to drown itself** (§3.8). A glossary of two hundred terms of
which six are filters must not render 194 zero rows; one number says the same thing and stays
readable.

**Behaviour 4 is the second of the two read routes, and §3.9 is why there are two.** It exists
because a task is not a plan row and `read_rows` cannot return one.

**Behaviour 7 keeps a word findable.** Reporting it as missing would tell the planner the word is
free, which is the moment they define it again — and under §0 they cannot, because `define_term`
would refuse it as an exact duplicate, so the report would have sent them into a refusal.

**Behaviour 8 is the standing ruling, restated where it would be broken.** A count of one and a count
of everything are both interesting, and any rule that says *which* is bad is a threshold — a judgment
written as arithmetic so review cannot see it.

### Task 4B.4 — the label filter on `read_rows`

**Signature.** `RowSelector` gains `label: str | None = None`; `RowService.read_rows` honours it.
**This task exists because the cold read found that nothing in the draft implemented the filter** —
§3.9 promised it and 4F tested it, but the only work specified was a dataclass field and a parser
key.

**Behaviours**

| | behaviour |
|---|---|
| 1 | `read_rows` with `label=w` returns the live plan rows whose **lineage root** carries a live attachment for `w`. |
| 2 | It composes with every other selector dimension — table, ids, provenance, liveness, neighbourhood — by intersection. |
| 3 | A row is returned once however many attachments it has. |
| 4 | `total` counts the filtered set, not the unfiltered one, so paging is correct. |
| 5 | `limit` and `offset` apply after the filter. |
| 6 | An unknown word is not an error: it returns an empty page with `total = 0`. |
| 7 | The word is normalised through `lexical.word()` before the join. |

**Behaviour 1 is the join the draft never wrote, and it is not trivial.** `label_attachments` keys on
lineage roots; `read_rows` is handed and returns row refs. So the join is
`plan_rows` → `lineage_root(ref)` → `label_attachments.target_root`, and the root must be computed
per candidate row rather than matched directly. **The cheap correct form is a subquery over the
attachments** — collect the attached roots for the word, then filter rows whose root is in that set —
because the attached set is small (one word's targets) and the row set is not.

**Behaviours 3 to 5 are stated because they are where this kind of filter goes wrong.** A join
against a one-to-many table duplicates rows; `total` computed before the filter reports a page count
for a different query; and `limit` applied before the filter returns short pages that look like the
end of the results. Each is silent.

**Behaviour 6 follows the selector's existing manner.** `RowSelector(table='nosuchtable')` returns an
empty page rather than raising, and a label the owner has retired and detached everywhere is exactly
the query that should come back empty rather than angry.

**`contracts:10` is superseded here in spirit and in 4D.1 in fact** (§3.9). This task changes what
`read_rows` does; 4D.1 is where the contract row and the docstring enumeration are amended.

---

## 6. Packet 4C — the glossary's guard

Depends on 4A, 4B.0 and 4D.1. `terms.py`, and `engine/lexical.py` from change 3.

**This packet is the whole of the guard, and under §0 that sentence is literal.** D12 said a
near-duplicate label is refused *as a near-duplicate term is*; the term half has never existed. With
one vocabulary there is one call that mints a new word, and this is it.

### Task 4C.1 — `define_term` gains the near-match refusal

**Signature.** `define_term(self, term: str, definition: str, names_ref: RowRef | str | None = None,
comparisons: tuple[TermComparison, ...] = ()) -> Term`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | A private `_candidates(word, definition, limit=5)` ranks live terms by calling `lexical.rank`, and returns `Candidate`s with `tied_at_top` set. |
| 2 | Refuses with `NearMatchesUnadjudicated` when candidates are returned and **any candidate tied at the top score** has no comparison, naming every candidate shown, each with its definition. |
| 3 | Refuses with `ReasonRequired` when any supplied comparison's `reason` is blank, naming the candidate. |
| 4 | Refuses with `UnresolvableRef` when the definition or a comparison reason cites a `table:ordinal` that resolves to nothing, naming the token. |
| 5 | A `same` verdict on any top-tied candidate returns the existing term without writing, and records the comparisons. |
| 6 | Every supplied comparison is written, whether or not a term was, in the same batch. |
| 7 | `DefinitionRequired` and `TermExists` still precede the search, in that order, and their messages are unchanged. |
| 8 | A banned word is never a candidate; it surfaces instead in `TermExists`' message when the proposed word *is* that word. |
| 9 | `redefine_term` and `approve_term` are untouched. |

**The refusal order is the pseudocode's order and they agree**, which is change 3's correction
inherited rather than rediscovered: with the name check *after* the adjudication check, an exact
duplicate would surface as `NearMatchesUnadjudicated` — because an exact match ranks first — and the
planner would be told to adjudicate a candidate when what they need to be told is that the word
already exists.

**And the draft's own order was wrong in a way worth recording, because it reasoned from a false
description.** It called the unresolvable-ref check "a cheap check on the caller's own arguments" and
ran it third, ahead of two checks it had listed as earlier. It is not cheap: it resolves addresses
against the database, so it *is* a lookup. The order below is by cost, and the ref check sits with
the lookups.

**Behaviour 2 is §3.3's settlement and it is the sentence a builder is most likely to soften.** Not
"the highest-ranked candidate" — **every candidate tied at the top score**. Measured, that is one
candidate for eleven of fourteen proposals and two for the other two (weighted); unweighted it would
be four in the worst case, which is the third argument for the weight.

**Behaviour 2's message carries each candidate's definition**, and §3.3 is the measurement that makes
it necessary: the top-ranked candidate is sometimes noise, and a planner shown `performance` against
`interview` with no definitions cannot see that in one glance.

**Behaviour 4 is the convention change 3 proposed and `CONVENTIONS.md` now carries** — a free-text
field rendered through the door is checked at the write for `table:ordinal` tokens that do not
resolve, and served `Verbatim` thereafter. A comparison `reason` cannot be rewritten, so an
unresolvable ref in one makes the row permanently unreadable through the surface. The refusal names
the token, because change 2's probe found that a URL with a port reads as `table:ordinal` and the
planner needs to see it is their `localhost:8080`.

**Behaviour 5 is a deliberate override of convention 1**, written here because the register requires
an override to be written in the task rather than upstream. Convention 1 says a named error is raised
and never reported as a status field in a success payload; returning the *existing* term from a call
that wrote no new one is that shape. The reason is §3.5's: the planner did the right thing, the call
did what it exists to do, and a comparison **was** committed — an exception path that also commits a
write is a shape nothing else in this engine has. **It is the only such override in this change**;
the draft had two, and one of them belonged to a tool that no longer exists.

**Behaviour 8 needs its argument, because "surface the retired one" is the draft's own strongest
sentence and it changes shape here.** For labels the draft offered a retired label in the refusal so
a planner would not silently undo somebody's decision. Under §0 a banned word is still a live `terms`
row — `find()` returns it, banned or not — so `TermExists` already fires on it and already carries
the entry. What the message must add is the ban: its reason and its `use_instead`. Offering a banned
word as a *near-match candidate* would be different and is refused, because it would invite the
planner to write a definition for a word the plan has agreed to stop using.

**Behaviour 9 is the boundary and it needs its argument, because the instinct is to guard every
write.** `redefine_term` sharpens what an *existing* word means — the word is already in the
glossary, so there is no new near-duplicate to create. `approve_term` is the owner settling a
definition, and running his wording past a guard would be the tool adjudicating him. **The guard
belongs at the one call that mints a new word.**

**Pseudocode**

```
word = self._word(term)                          # TermNotFound on empty
if not definition.strip():
    raise DefinitionRequired naming word
for c in comparisons:
    if not c.reason.strip():
        raise ReasonRequired naming c.matched
existing = self.find(word)
if existing is not None:
    raise TermExists naming it, its definition, and — if banned — its reason and use_instead
self._refuse_unresolvable_refs(definition, [c.reason for c in comparisons])
candidates = self._candidates(word, definition)
top = [c for c in candidates if c.tied_at_top]
if top and any(c.word not in {x.matched for x in comparisons} for c in top):
    raise NearMatchesUnadjudicated naming every candidate with its definition
if any(x.relationship == SAME for x in comparisons if x.matched in {c.word for c in top}):
    ops = [insert each comparison]
    self.storage.write_atomic(ops, key)
    return self.find(the matched word)
ops = [insert the term] + [insert each comparison]
receipt = self.storage.write_atomic(ops, key)
return self._get(receipt["results"][0]["id"])
```

**The term is read back from the receipt, not from the op**, and `attachments.py`'s own comment says
why: the id belongs to the write, and reconstructing the row from the arguments returns a value the
database never confirmed. The draft returned an unbound variable here, which the cold read caught.

**`_refuse_unresolvable_refs` is a method on `TermService`, defined in this task**, not a free
function the draft called and never defined. It takes the strings, scans each with `door.ADDRESS`,
resolves each token, and raises naming the first that fails.

**The comparisons need no `FromOp`**, unlike change 3's: a `term_comparison` names its candidate by
word, not by id (§3.5), so there is no forward reference inside the transaction. They go in the same
batch, because a comparison written without the term it justified is a record of a decision that did
not happen.

**Nothing supersedes a contract row here.** `define_term` is a `DEVIATION` tool — the frozen plan
never asks what the words mean, which is DEFECTS.md F40 and the reason the glossary exists at all —
so there is no contract to amend and no `Absence` entry changes. **`contracts:10` is superseded by
4D.1, for `read_rows`, which is a different call.**

**What this costs the interview, stated because it is a real change to a call planners already
make.** Every first definition of a word now runs a search and may be refused. Against v2's own
glossary that is a handful of calls; against a plan with two hundred terms it is two hundred searches
and up to two hundred adjudications. That is the same trade change 3 measured and accepted at 561 —
**2.8× smaller at that figure, not the order of magnitude the draft claimed** — and it is the reason
the weighting in §3.4 matters, because a mandatory adjudication against a candidate matched on `the`
is friction that buys nothing.

---

## 7. Packet 4D — the surface and what a reader sees

`surface.py`, `models.py`, `render.py`. **4D.1 lands before 4B.1 and 4D.2 after 4C.1** — §3.10.

### Task 4D.1 — the registry

**Behaviours**

| | behaviour |
|---|---|
| 1 | Three tools are added to the **planning** surface, all `DEVIATION`, each appearing in `ADDED` with its reason. |
| 2 | A `comparisons` payload parser accepts a list of `{matched, relationship, reason}`, rejecting an unknown relationship by name. |
| 3 | `define_term`'s registry row gains the same `comparisons` parameter, optional. |
| 4 | A `targets` payload parser accepts a heterogeneous list of refs and task ids, rejecting `bool` explicitly. |
| 5 | `RowSelector` and the `selector` parser gain `label`. |
| 6 | `attach_label` and `detach_label` carry `writes=True`; `labels` does not. |
| 7 | Every parameter of all three carries a `Param.note`. |
| 8 | `contracts:10` is superseded, with `RowSelector`'s docstring enumeration extended. |
| 9 | No `Absence` entry is filed for any of the three, and none is removed. |

**The three tools.**

| tool | writes | why it exists |
|---|---|---|
| `attach_label` | yes | one word across many targets — the act the filter is made of |
| `detach_label` | yes | taking it off; without this the owner can only ever add |
| `labels` | no | the words in use, their counts and denominators — and what one word is on |

**Three, not six, and the three that are gone are `define_term`, `approve_term` and `redefine_term`
under other names** (§0). This is the change's smallest surface and its strongest argument.

**Behaviour 1's count is stated because a coverage test that asserts a number nobody wrote down
cements whichever number the builder guessed — and change 3's draft got exactly that wrong.** The
arithmetic, from premises **re-counted from `engine/surface.py` on 2026-07-30** rather than carried:

| | |
|---|---|
| v2's planning surface today (`_t(` registrations) | **54** |
| change 1 removes | 4 — `declare_package`, `assign_task`, `packaging`, `split_subtask` |
| change 2 adds | 1 — `record_grounds` |
| change 3 adds | 6 |
| this change adds | **3** |
| **after this change** | **60** |

`ADDED` moves the same way: **12 today**, minus the three deviations change 1 removes, plus
`record_grounds`, plus change 3's six, plus these three — **19**.

**Behaviour 2's parser is registered once, and the name collision the cold read found is gone with
the `kind` column.** The draft registered `{matched, container, relationship, reason}` over five
relationships for the catalogue and `{matched, relationship, reason}` over two for labels, under one
name, so one shadowed the other. **They are still two different shapes and they still need two
names**: change 3's is the catalogue's, keyed `catalogue_comparisons`; this one is
`term_comparisons`. Registering both under `comparisons` is the defect; each parser is named for the
table it writes.

**Behaviour 3 is the change that is easy to miss**, because `define_term` is not a new tool and the
packet is named for new ones. Without it 4C.1's parameter has no route through the door and the guard
can be satisfied by nobody.

**Behaviour 4 is the F39 shape named in the draft and left unbuilt.** No existing `Param.kind` covers
a heterogeneous list of refs and integers, so one is added — and `isinstance(x, int)` is not the
test, because `bool` subclasses `int` and `True` would parse as task 1 (4B.1 behaviour 3). The parser
rejects `bool` by type before anything else.

**Behaviour 5 is §3.9's first route.** The parser's accepted-key set is explicit — it raises on an
unknown field by name — so a new selector dimension that is not added there is refused at the surface
while working perfectly in-process, which is the shape F39 records.

**Behaviour 7 is not padding, and `surface.py` says why in its own words**: `Param.note` is *"the
whole of the tool's documented interface, so it says what the caller must decide — never what the
implementation does with it."* Two of these parameters have their whole difficulty in knowing what to
put in them — `comparisons`, and `targets`, which accepts a ref or a task id — and a caller who
cannot tell will pass the wrong one and read the refusal as a bug in the tool.

**Behaviour 8 is the correction to the draft, which scoped itself to "the six" and never asked.**
`read_rows` is `contracts:10` and its docstring enumerates the selector's dimensions verbatim; adding
one and leaving the contract unamended is a contract that describes a call that no longer exists.
Change 2's precedent superseded five contract rows for exactly this.

**Behaviour 9 is the correction to the *other* instinct, and it needs the data rather than the
docstring.** `Absence` is documented as *"a contract no tool exposes"*, which reads as though a
registered tool should not appear in `ADDED` — but `ADDED` is itself a `tuple[Absence, ...]` and all
twelve of its current entries are registered deviation tools. The docstring describes none of its
uses. **What `ADDED` records is a tool with no contract behind it**, which is what all three of these
are, so all three appear — and behaviour 1 and behaviour 9 do not contradict each other, which in the
draft they did.

### Task 4D.2 — rendering

**Behaviours**

| | behaviour |
|---|---|
| 1 | A rendered plan row shows the labels it carries, and says nothing when it carries none. |
| 2 | A rendered **task** shows the labels it carries, on the same rule. |
| 3 | A refusal listing candidates lists each with its definition, and marks which are tied at the top. |
| 4 | A term `definition` and a comparison `reason` are `door.Verbatim`: served as written, with every ref they cite resolved **alongside** them. |
| 5 | A label is addressed by its word, never by an id. |

**Behaviour 1 is what makes the whole change visible.** A label attached and never shown is the
unread-field defect class; `idx_label_attachments_target` exists for exactly this read, which is why
it survives the cull that keeps this change to two indexes.

**Behaviour 2 was nowhere in the draft** — it rendered labels on rows and forgot tasks, which are
half the target space and the half the owner named first.

**Behaviour 3's second half is §3.3.** A planner shown five candidates must be able to see which ones
they are obliged to answer for; without the marking, a refusal that lists five and requires two reads
as a refusal that requires five.

**Behaviour 4 is the convention change 3 proposed and `CONVENTIONS.md` now carries**, and the trap is
worth restating because change 3's draft got it backwards: `Verbatim` is *"stored prose, served as
written"*, and the door **annotates alongside** rather than rewriting inline. Annotation that changes
a value's shape turns an identifier a caller reads and passes back into an object, which broke the
tool once already.

**Legacy definitions are the hazard behaviour 4 has to survive**, and the cold read found it: term
definitions written before this change were never ref-validated, so a refusal that renders one can
raise `BareAddress` on an address that does not resolve. **Rendering a candidate's definition
tolerates an unresolvable ref and renders it as written**; the validation in 4C.1 behaviour 4 applies
to writes, and a refusal is a read.

**Behaviour 5 follows `terms`**, which is looked up *"by the word you were about to type, never by an
ordinal"* — so `door.scan` never sees a `labels:` address in outgoing text and `resolver_from` needs
no new lookup.

---

## 8. Packet 4E — the methodology

Depends on 4D.1. `engine/methodology/rev6/`.

### Task 4E.1 — methodology revision 6, and the labelling round

**Behaviours**

| | behaviour |
|---|---|
| 1 | `rev5` is copied to `rev6` and edited there; `rev5` is left untouched. |
| 2 | `stage6_architecture.md` gains a **labelling round**, and the residual packaging-round prose is **deleted** in the same edit. |
| 3 | The round quotes `STARTER_LABELS`, and says the tool proposes a new word only when none of them fits. |
| 4 | It names `define_term()` and `attach_label()`, and says the owner settles with `approve_term()`. |
| 5 | It says in as many words that a label is a glossary term, and that there is no separate label vocabulary. |
| 6 | The revision stamp is 6, and `plan_status` reports it. |
| 7 | No gate criterion and no gap rule is added. |

**Behaviour 1 is change 1's ruling and it is not re-argued**: editing a revision in place
retroactively changes what already-run sessions were scripted with, and the stamp exists precisely so
a plan can say which methodology produced it.

**Behaviour 2's second half is a belt-and-braces check, and the reason it is not simply change 1's
job is worth stating.** `rev3/package6_architecture.md` carries a packaging round — *"Every
component is a task, and every task belongs to exactly one package… this is the one grouping a human
chooses rather than derives"*. Change 1's 1E.1 behaviour 4 removes three *call names* from that
script, and **the round's prose names no call, so it survived the removal**; the draft's "in the
place the packaging round vacated" had no anchor, and rev6 would have shipped a residual packaging
round beside the labelling round that replaced it.

**Change 1 now deletes the round — 1E.1 behaviour 5, added by this change's §11.3 — and this task
still checks.** Two changes, two revisions, and one of them copies the other's files: rev6 is copied
from rev5, which is copied from rev4. If change 1's deletion is incomplete or is undone, the residue
arrives here by copy, and 4F.2 behaviour 6 is the assertion that catches it. **The rule is deleted
once and asserted where it would reappear**, which is not duplication — it is the difference between
a rule and a mechanism.

**Behaviour 3 is the starter list quoted from one home** (§3.2, 4A.2 behaviour 2). Ten words and one
rule — *a label names a place in the system, never a kind of work* — written where the planner reads
them at the moment they are needed, and asserted equal to the constant by 4F.

**Behaviour 5 is the round's most important sentence and it is the one a writer would leave out**,
because it states an absence. A planner who has read D12 will look for `propose_label`; the script
has to say the word is a glossary term and `define_term` is how you mint one, or the round reads as
describing tools that do not exist.

**Behaviour 7 is the difference between this round and the one it replaces, and it is the whole of
D12.** The packaging round was mandatory and `finalize_plan` refused a plan with an unpackaged task.
Labelling is not: no criterion requires a label, no gap counts an unlabelled row, and a plan with no
labels at all finalizes exactly as it does today. **The script's language has to carry that
difference**, because a script written in the packaging round's imperative voice would create an
obligation the engine does not enforce — which is a rule in a document, and the failure this whole
family of documents is about.

---

## 9. Packet 4F — the enforcement

Depends on all of the above.

### Task 4F.1 — the store's own invariants

**Behaviours**

| | behaviour |
|---|---|
| 1 | A version-10 database migrated to 11 is structurally identical to a fresh 11 — raw `PRAGMA table_info`, `index_list`, `index_info` and `foreign_key_list` output, compared as-is. |
| 2 | `schema.statements(LABELS_DDL)` yields **four** statements. |
| 3 | **The same word attached twice to the same plan row is refused, at the store, with raw SQL.** |
| 4 | The same word attached twice to the same task is refused. |
| 5 | The same word on two different rows, and on two different tasks, is accepted. |
| 6 | Re-attaching after a detach is accepted. |
| 7 | An attachment with two targets, or none, is refused. |
| 8 | `target_root = ''` is refused, and `task_id = 0` is refused — the two sentinels. |
| 9 | `relationship` refuses a value outside `same | distinct`. |
| 10 | The 10→11 migration writes no attachment and no term, and `snapshot_version` still carries nine tables. |
| 11 | `_columns()` finds both new tables, and **no table is declared twice** across `schema.py` and the retained v10 fixture. |

**Behaviours 3 to 8 are asserted at the store, with raw SQL, and this is the correction that matters
most in this packet.** Driven through the service instead, **behaviour 3 passes on the naive index**:
`attach_label` treats an existing attachment as a no-op (4B.2 behaviour 6), so the service never
issues the second insert and the index is never reached. The test would be green, the index would
enforce nothing, and the first caller to write an attachment any other way — a migration, a later
change, a repair script — would double every affected usage count with nothing red.

**Behaviour 1 includes `index_info` because `index_list` names indexes without saying which columns
they cover.** And a precision the draft got wrong and change 3 gets wrong too: **`index_info` *does*
distinguish an expression index** — an expression column reports `cid = -2` and a NULL name — so it
is not true that the pragmas cannot tell the two index forms apart. **Parity is blind for a better
reason**: both sides are built from the same `LABELS_DDL`, so it catches a *missing* block and can
never catch a *wrong-but-consistent* index. That is why behaviours 3 to 8 exist as behaviour
assertions and not as pragma comparisons.

**Behaviour 10 exists because nothing else verifies 4A.2's two negative behaviours.** "Seeds no
starter word" and "adds nothing to the snapshot table set" are both claims a builder could quietly
break — a helpful seed of the ten, or `label_attachments` added to `snapshot_version` on instinct —
and neither would fail anything else.

**Behaviour 11 is the guard on the guard, and it is stated as *no table is declared twice*.** The
draft wrote it as *"no table the retained v10 fixture declares"*, which is **unsatisfiable**: the
fixture declares `plan_rows`, and so does `schema.py`. What it means is that `_columns()`, reading
`schema.py`, finds each table exactly once — which is the assertion that proves the fixture lives
outside it. **3E.1 behaviour 10 has the identical flaw and §11.3 carries the correction.**

### Task 4F.2 — the size and the shape

**Behaviours**

| | behaviour |
|---|---|
| 1 | The planning registry holds **60** tools, `ADDED` holds **19**, and each of the three appears in `ADDED` with a reason. |
| 2 | `get_stage_script(6)` renders without raising, through the door. |
| 3 | `plan_status` reports methodology revision 6, and `rev5`'s files are byte-identical to before. |
| 4 | No gap rule and no gate criterion was added, asserted as a count against rev5. |
| 5 | The stage-6 script's ten words are exactly `STARTER_LABELS`, and so are `VOCABULARY.md`'s. |
| 6 | The script contains no packaging round: none of `package`, `declare_package` or `assign_task` appears. |
| 7 | A definition with candidates and no comparison is refused, and the refusal names every candidate **with its definition**. |
| 8 | When candidates tie at the top, a comparison on **one** of them is still refused, and the refusal names both. |
| 9 | A `same` verdict writes the comparison, writes no term, and returns the existing term. |
| 10 | An exact duplicate is refused as `TermExists`, not as `NearMatchesUnadjudicated`. |
| 11 | Attaching a word with no live term is refused, and the refusal passes `door.scan`. |
| 12 | Attaching a banned word is refused, naming its `use_instead`. |
| 13 | `Engine` and `engine` attach as one word, and the count is one. |
| 14 | Attaching the same word to the same row twice, through the service, is a no-op and the count stays 1. |
| 15 | Ten targets of which one is already attached: all ten end attached, and the call does not raise. |
| 16 | The same target listed twice **in one call** attaches once and does not raise. |
| 17 | `attach_label(w, (True,))` is refused, not read as task 1. |
| 18 | `labels()` reports both denominators, the zero-attachment count, and a banned word with its reason. |
| 19 | `read_rows` with a label selector returns the rows carrying it, follows a row through supersession, returns each row once, and reports a `total` matching the filtered set. |
| 20 | A rendered row and a rendered task each show their labels. |
| 21 | `label_attachments` was not added to the `junctions` exemption set. |

**Behaviour 2 is the highest-value test in the change and the draft had nothing like it.** Change 1
shipped exactly this break — a stage script naming a call the registry could not resolve, raising at
`get_stage_script` — and this change recreates the conditions precisely: 4E.1 names three calls, one
of which (`define_term`) already exists and two of which 4D.1 must have registered first.

**Behaviours 3 to 6 assert 4E, which the draft's 4F did not touch at all.** Behaviour 6 is the
packaging-round deletion made checkable; without it, the residual prose survives silently, which is
how it survived change 1.

**Behaviour 8 is §3.3's settlement asserted.** It is the one a builder will implement as "the
highest-ranked candidate" and pass every other test.

**Behaviours 14 to 17 are 4B.2's no-op, batch and type rules**, each of which the cold read found
either missing or wrong in the draft. Behaviour 15 in particular is the batch-abort case: it passes
trivially on a service that checks, and raises on one that leaves it to the index.

**Behaviour 13 is the case normalisation asserted at the service**, which is where it is true — the
index has no `COLLATE NOCASE` and does not need one (§3.6).

**Behaviour 19's second clause is §3.6 end to end**, and it is the assertion that would catch a label
keyed on the row ref instead of the lineage root: attach, supersede the row, read again. Keyed
wrongly, the label silently disappears and every individual unit test still passes.

**Behaviour 11 is the landing-order inversion made into an assertion**, following change 3: asserting
that the refusal *renders* rather than that it is raised is what catches the ordering being undone
later, against the standing evidence that a missing route reports a refusal reading like the caller's
mistake (F39).

**Behaviour 21 is the exemption set checked rather than assumed.** A builder meeting a two-column
table with no `updated_at` will reach for the `junctions` exemption; `label_attachments` is not a
junction — it has a lifecycle stamp — and widening the set would exempt it from checks it should
face.

**One test this change does *not* need, and the reason is §0.** The draft's strongest single
assertion was *"a word may be a live term and a live label at the same time, and neither refuses the
other"* — the test that would catch somebody deciding during the build that labels belong in `terms`
after all. Under §0 that is no longer a property to protect; **it is the design, and its inverse is
the test**: behaviour 10 asserts that defining a word twice is refused, which is the same mechanism
read the right way round.

---

## 10. What this change does not do

**It does not make a label mandatory anywhere.** No gap counts an unlabelled row, no gate criterion
requires one, and `finalize_plan` is untouched. That is D12's first sentence, and it is what makes
tool proposal safe.

**It does not judge a label set.** The report counts and shows two denominators; nothing warns, and
no threshold decides what a bad count is.

**It does not create a label vocabulary.** There is one vocabulary and it is the glossary — §0.

**It does not build a label retirement.** Finishing with a filter is detaching it; banning a word is
`retire_term`, which exists — §3.7.

**It does not label a catalogue entry.** Entries are addressed by name and container, have their own
report, and nobody has asked to filter them. Adding a third target space would mean a third column
and a third arm on the `CHECK`, for a filter with no stated reader.

**It does not seed the starter list into the database** — 4A.2. The ten live in `STARTER_LABELS`.

**It does not give a label to a term, a finding or a warning.** The targets are plan rows and tasks,
which is what D12 says — *"attached to any row"* — plus the one thing the owner named that is not a
row.

**It does not re-run the near-match search on redefinition or approval** — 4C.1 behaviour 9. The
guard is on the call that mints a new word.

**It does not fold `term_comparisons` into `catalogue_comparisons`** — §3.5. The catalogue's matched
entry is a foreign key; a word is not.

**It does not build the shared ranking.** That lands in change 3, by amendment — §11.

**One item change 5 inherits**, listed so it is not rediscovered: **task labelling is only reachable
on a finalized plan until stage 8 creates tasks** (4B.2). Change 5 removes it, and removes the
identical constraint change 3 recorded for function entries at the same time.

---

## 11. What this change owes changes 1, 2 and 3

**All of these are amendments to the other changes' specifications, applied there rather than
specified here as refactors.** Changes 1, 2 and 3 are merged and **unbuilt**, so the cheapest and
most honest correction is to the specification. Specifying a refactor of code nobody has written
would be inventing work.

### 11.1 The ranking, the tokeniser and `word()` move to a shared module

**`engine/lexical.py`, holding three functions and one error**, built in change 3 and called by
change 3's catalogue and change 4's glossary guard.

| | |
|---|---|
| `tokens(text, scope)` | `TermService._tokens`, moved unchanged. `TermService._tokens` becomes a one-line delegation whose docstring names the canonical one. |
| `rank(name, text, candidates, limit=5)` | change 3's `CatalogueService._rank`, taking its candidates as `(key, name, text)` rather than reading the catalogue table itself, **weighting each shared word by its rarity across the candidates given** (§3.4), and **marking every candidate tied at the top score** (§3.3). |
| `word(term)` | `TermService._word`, moved. The draft left it behind, arguing it had "one behaviour and no second policy waiting to appear"; it has two callers in two modules the moment this change lands, which is the same test the tokeniser passed. |
| `NearMatchesUnadjudicated` | the refusal, raised by two callers and therefore owned by neither. |

**This is simpler than the draft's version, not harder**: there are **two** callers — the catalogue
and the glossary — where the draft had three, because `propose_label` is gone.

**The argument is already in this codebase and is quoted rather than re-derived.**
`RowService.lineage_root` says why the supersession-stable identity primitive lives there rather than
on either caller — *"scope attachments take the same keying, which makes this the second application
and the reason it lives here rather than on either caller"* (`rows.py:591`) — and `GapService`'s
delegation is one line naming it (`gaps.py:122-133`). **Verified 2026-07-30: it is delegation, not
duplication.**

**And `fingerprint.py` is the precedent for it being a module rather than a method**, in its own
words: capture and comparison *"are one piece of knowledge — what counts as the workspace — and
splitting them puts the two halves in different files with nothing holding them to the same field
list."* The tokeniser and the ranking are one piece of knowledge — what counts as a shared word — and
the failure mode is identical: change the tokeniser in one place and the other ranking silently
starts matching differently.

**The name, and the two that were rejected.** `lexical` is the codebase's own word for this layer —
`terms.py` heads the scan *"the lexical scan"*, `references.py` says *"Lexical retrieval"*, and
change 3 §3.7 says *"the ranking is lexical, and it has to be."* `words.py` was rejected as one
letter of daylight from `terms.py`, which defines a term as *a word the plan has agreed the meaning
of*. `similarity.py` was rejected because the module deliberately computes no similarity verdict: it
ranks, and the standing ruling is that a threshold is a judgment written as arithmetic.

**What change 3's document has to say, precisely:** task 3B.1's `_rank` becomes a call to
`lexical.rank`; §3.7's *"the ranking function must be one function, called by both the search and the
registration"* extends to *and by every later caller, which is why it is not private to this
service*; and 3E.2 behaviour 4 keeps its assertion unchanged, because it tests the property rather
than the location.

### 11.2 Stop words are not task-local, and the answer is a weight — and the top of the ranking can tie

§3.4 is the measurement and the settlement. Change 3 says twice that stop-word handling is
task-local; §3.3 shows what that leaves — `the` deciding 46% of all matching, four of fourteen
mandatory adjudications resting on nothing else, and four of fourteen top positions undefined.

**Two amendments to change 3, not one:**

- **`lexical.rank` weights each shared word by how rare it is across the candidates it was given**,
  and change 3's §3.7 and 3B.1 drop the "task-local" sentence in favour of naming the weight.
- **`lexical.rank` marks every candidate tied at the top score, and change 3's refusal requires a
  comparison for each of them** rather than for "the highest-ranked". This is **3B.1 behaviour 12**,
  added beside behaviour 7 rather than replacing it: behaviour 7's `id` tie-break is right and its
  argument stands — an unstable ranking changes the required answer between calls — but it only
  orders the display. When candidates score identically it picks by insertion order which one the
  planner must answer for, and leaves the rest unexamined. **The count does not move** — a tie
  changes which comparisons a registration needs, not whether it needs one — but the refusal's
  wording does.

**Neither changes a number change 3 measured**, and that is what makes them amendments rather than a
redesign: eligibility is untouched — a shared word is still a shared word — so *74 of 635 shown
nothing*, *561 adjudications* and *mean 3.90 on a page of five* all stand. Verified against the same
fourteen probes with the page limit removed: the candidate set is identical under both rankings for
every probe.

### 11.3 The remaining corrections, by change

**Change 3 — six, all now applied in `builds/03-catalogue.md`.**

| | correction | where |
|---|---|---|
| 1 | `JUSTIFICATION_ROLES` is **18 entries** after change 3, not eleven, and the enumeration is re-derived from the schema with its method stated rather than restated. The base is the eleven in 4A.0, re-measured 2026-07-30. | 3A.0 behaviour 2 |
| 2 | `engine/lexical.py` also owns `word()`, not just `tokens()` and `rank()` — §11.1. | 3B.1 signature and behaviour 11 |
| 3 | `rank` marks the candidates tied at the top and the refusal requires a comparison for each — §11.2. | 3B.1 behaviour 12, **new** |
| 4 | The `index_list` / `index_info` claim is imprecise: `index_info` *does* distinguish an expression index (`cid = -2`, NULL name). Parity's real blindness is that both sides come from one DDL text, so it catches a missing block and never a wrong-but-consistent index — 4F.1. | 3E.1 behaviour 3 |
| 5 | *"the four writing tools carry `writes=True`"* should say *the writers*: change 3 has five writes and one read among its six, and this change has two and one. A copied sentence with a number in it is the recurring shape. | applied earlier |
| 6 | 3E.1 behaviour 10's *"no table the retained v9 fixture declares"* is **unsatisfiable** — the fixture declares `plan_rows` and so does `schema.py`. It means *no table is declared twice* — 4F.1 behaviour 11. | applied earlier |

**Change 2 — one, applied.** `JUSTIFICATION_ROLES` is **16 entries** after change 2, not nine, and
its enumeration is re-derived from the schema with the method stated rather than restated. Its
"three `reason` columns" is a bare-column count where there are seven, and it omits
`terms.ban_reason` and both `block_reason`s entirely — 2E.1 behaviour 4, and 4A.0 here.

**Change 1 — one, applied.** 1E.1 behaviour 4 removes three call names from the stage-6 script;
**the packaging round's prose names no call and survives.** `builds/01-vocabulary-and-levels.md`
gains **1E.1 behaviour 5**, which deletes the round itself and leaves stage 6 with no mandatory
grouping; 4E.1 behaviour 2 deletes any residue that reaches rev6 by copy, and 4F.2 behaviour 6
asserts it. Left as it was, revision 4 would ship a packaging round for tools that no longer exist,
and revision 6 would ship it beside the labelling round that replaced it.

**A note on §0's surviving-findings list, because one item in it moved.** §0 records "the
justification-column count of twenty" as surviving the rewrite. **The enumeration and the method
survive; the total does not** — twenty counted `labels.retire_reason`, and §0 deletes the table that
column was on. Re-enumerated, it is **nineteen** (4A.0). This is the same lesson one turn later:
a count carried across a design change is a count nobody re-derived.

---

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
