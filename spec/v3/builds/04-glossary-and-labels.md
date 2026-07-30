# Change 4 — the glossary and labels

**Work order, written 2026-07-30 from the owner's decisions of that date.** This is not yet a
packet-level specification: §1–§4 are settled design and are **not to be re-derived or re-opened**,
§5 is the work order, §6 the questions still open. The next session writes the specification from
this, cold-reads it, then builds.

**It supersedes `04-labels.md`**, which specified labels against a glossary that no longer exists.
§5.8 lists what survives from that file — the attachment table, its probes, and the cold-read record
— so none of it is re-derived.

---

## 1. The decision, in the owner's words

Quoted rather than paraphrased, because a cold session inherits the conclusion and cannot defend it
otherwise:

> Glossary table exists, but the user defines the contents with prompting from you or asking to add
> to it, labels must exist in the glossary. You only use the glossary for a mechanical look up
> (assigning labels). At the start of each session you load the glossary as a memory (I know, this
> is not robust), this might help you use the right words, it might not. If the user want to update
> the glossary for your memory then they need to restart the session.

And, ruling out the machinery that was proposed around it:

> retire term is dead, banned is dead, use_instead is pointless you will no longer be checking
> against the glossary or banned for that purpose.

> at the start of the project when the glossary is empty the user probably won't know or they can
> as to add to the glossary. Forget you prompting the user, it's another friction point.

> plan_status reporting of glossary is pointless, the user can look at it in the gui later.

> Kill the test_vocabulary.py - you clear do not have a strategy to use it at an appropriate time,
> so it is not robust.

> If the user tries to delete a glossary item that is a label then prompt for a replacement label,
> do not arbitrarily remove the label from all the references.

> The brief idea is dumb, you don't build it until the plan is finished, but you need the glossary
> context during the plan.

> no to the stage script glossary, and make sure you DO NOT save the glossary as a memory at the end
> of a session (that needs a robust mechanism or you will just accummulate mixed up glossarys in
> memory).

**One distinction inside those quotes that a reader will otherwise flatten.** "Forget you prompting
the user" kills the *mechanical* prompt — no gap rule, no warning, no status nag. It does not
forbid suggesting a word in conversation; that is the "prompting from you" of the first quote. The
line is between a mechanism that interrupts him and a sentence in a reply.

---

## 2. Why, including the argument that failed

**Do not re-run any of this. It was measured on 2026-07-30 and the scripts are reproducible from
the methods stated.**

### 2.1 The failure this exists to prevent

The owner's own statement of it, and it is the acceptance test for any mechanism proposed here:

> you calling something a "part" one day and a "component" the next, or me using the word "part"
> and you assuming I mean something else without checking with me for a description and re-starting
> the mixture of part and components again.

Two directions. **A:** the tool invents a second word for a thing that has one. **B:** the owner
uses a word the tool does not hold, and the tool assumes instead of asking.

### 2.2 No scan catches it, and this is the finding everything else follows from

`part` and `component` share no letters. Every mechanism proposed before this decision — the banned
list, an allowlist over structural slots, near-match ranking — is **lexical**, and none of them can
see a synonym that shares no vocabulary. `terms.py` has admitted this in its own docstring since v2:

> it matches words, so a *new* name invented for an existing concept, sharing no letters with it,
> goes unseen. Nothing without judgment can catch that.

**So the glossary's job is not to be scanned. It is to be in front of the writer at the moment of
naming.** That is what the session load is for, and it is why the owner accepted a mechanism he
himself called not robust: the alternative is not a better mechanism, it is a mechanism that cannot
work.

### 2.3 The allowlist was measured and it fails

The proposal was: a row write is refused when the row's name contains a word not in the glossary.
Measured against the frozen v2 plan (`spec/v2/plan.db`), walking named rows in id order and counting
those introducing a word not seen before:

| | |
|---|---|
| named rows | 115 |
| distinct words used in row names | 136 |
| …used exactly once | **82** |
| …used three or more times | 29 |
| **rows that would refuse** | **78 of 115 — 68%** |
| among the first 100 rows | 74 |
| among the last 100 rows | **64 — it does not decay** |

Names are meant to be distinctive, so most of them carry a word nothing else uses. `acquire writer
lock` brings three new words and none is vocabulary. A refusal firing on two thirds of writes
forever is a worse cry-wolf than the banned list it was meant to replace.

### 2.4 "The" versus "package" is a category, not a threshold

The owner's word-frequency ruling — *"are we going to make a glossary entry for 'the'?"* — was
reused in this conversation to argue that checking word usage against the glossary is unbounded.
**That was a false equivalence and he rejected it.** Measured over the same plan:

| | distinct words |
|---|---|
| appearing in **structural slots** (table names, column names) | 238 |
| appearing in the plan's **prose** | 2,455 |

`the` is the commonest prose word and appears in **zero** structural slots. `package` appears in
them, beside `plan`, `subtask`, `contract`, `obligation`, `spike`, `finding`, `provenance`.

But 238 is still the wrong set — it sweeps in `id`, `at`, `created`, `by`, which are plumbing. The
words that name *kinds* of thing in the v2 plan are its **22 row types** plus levels and link types.
That is the order of magnitude the owner predicted unprompted: *"I'm expecting a typical project
glossary to have <100 words."*

### 2.5 Why the banned list had to go

A banned list is a **denylist somebody hand-types**, in an engine whose subject is that a rule in a
document is not a mechanism. The owner: *"I hate banned, it adds nothing except supporting hand
crafted bad words, but that does not automate well."* Nothing replaces it, because §2.2 says nothing
can.

### 2.6 What replaced `use_instead`, and it is a better shape

The column stored a replacement word forever, for a scan that no longer exists. Under §3.4 the
replacement is a **parameter of the delete** — supplied at the one moment it is needed and consumed
immediately. Same information, no stored mirror to go stale.

---

## 3. What the glossary becomes

### 3.1 The table

```
terms (id, term, definition, created_at, updated_at)
UNIQUE (term)
```

Five columns, down from eleven. `definition` is the description-and-context field: what the word
means here, in a sentence, in the owner's terms.

### 3.2 The tools

| tool | what it does |
|---|---|
| `define_term(term, definition)` | add a word with its description |
| `redefine_term(term, definition)` | change the description, **in place** |
| `remove_term(term, replacement=None)` | take a word out — §3.4 |
| `glossary()` | the whole table, alphabetically |

There is no approval step. The owner defines the contents; whatever is written was authorised by him
at the moment it was written, so there is no queue of unsettled proposals and nothing to settle.

### 3.3 The one mechanical use

**A label must be a live glossary term.** `attach_label(word, targets)` looks the word up and
refuses if no live term holds it, naming `define_term`. That lookup is the whole of the glossary's
mechanical role. Nothing else scans it, counts it, gates on it or warns from it.

### 3.4 Removing a word that is in use as a label

`remove_term("part")` while anything carries `part` as a label **refuses**, naming how many plan
rows and how many tasks are affected. It never strips the label silently.

The resolution is a replacement word, which must itself be a live glossary term: every live
attachment moves from `part` to `component`, then the `terms` row is deleted — one transaction.

**Two mechanical details to specify rather than discover.** A target already carrying `component`
must not raise on the move; the attachment collapses to one, which is the dedupe `attach_label`
already performs. And the move is over live attachments only — a detached one stays detached and
stays pointing at the dead word, because it is the record that the label was once there.

### 3.5 The session load, and the rule attached to it

At session start the glossary is **read** into context. It is never **written** out. The owner
accepted the read as deliberately non-robust — *"this might help you use the right words, it might
not"* — and updating it mid-session means restarting the session.

**Persisting it is forbidden.** *"that needs a robust mechanism or you will just accummulate mixed
up glossarys in memory."* N stale copies with nothing keeping them true, consulted in preference to
the live table, is the exact defect the glossary exists to prevent, committed by the thing meant to
prevent it. Recorded as a standing rule in the assistant's own memory, not only here.

**Rejected, and not to be re-proposed:** carrying the glossary in the stage-script payload (offered
as a fix to the restart limitation; the owner said no), and carrying it in the brief (§4).

---

## 4. What is deleted, and the evidence for each

| deleted | evidence |
|---|---|
| `violations()` and its three call sites — the submission scan in `rows.py`, `_retired_words()` in `gates.py`, a gap rule in `gaps.py` | §2.2, §2.5 — the scan cannot catch the failure it exists for |
| `banned()`, `ban_scope`, `ban_reason` | owner, §1 |
| `use_instead` (the column) | owner, §1; returns as a parameter, §2.6 |
| `retire_term` | owner, §1; replaced by `remove_term`, §3.4 |
| the retired-word warning kind in `warnings.py` | its only producer was `violations()` |
| `export_glossary`, `GlossaryExport`, `EXPORT_FILENAME` | **no consumer exists.** Searched 2026-07-30: `glossary.json` is named in `terms.py` (which writes it) and in two test files asserting it was written. No `.github`, no workflow, no script reads it |
| `names_ref` | **no consumer once the export goes.** `terms.py`'s own comment: *"Only to resolve `names_ref` to the name of the row it names, in the export"* |
| `approve_term`, `approved_at`, `is_approved`, `awaiting_approval()` | §3.2 — and their only two readers were the gap rule and `plan_status`, both deleted below |
| `superseded_at` on `terms`, and the definition lineage | nothing cites a definition. Change 3 settled the identical case for purpose lines: *"a purpose line is not an argument; it is an index entry, and nothing cites it"* |
| both glossary gap rules — `_rule_no_glossary`, and the awaiting-approval gap | owner, §1 — *"another friction point"* |
| `plan_status`'s glossary count and its "N definitions waiting on approve_term" line | owner, §1 |
| the brief's live glossary section (`briefs.py`) | owner, §1 — the brief is served after finalisation; the naming drift happens while rows are being written, so it arrives after the damage |
| `tests/test_vocabulary.py`, entire | owner, §1 — and it is **change 1** that deletes it, not this change; see §4.1. **Safe: it is a different file from `test_schema_vocabulary.py`**, which holds the column-role checks change 2 and this change both depend on |
| `TermService._tokens` | its only caller was `violations()` |
| change 4's near-match guard — the whole of `04-labels.md` packet 4C, `term_comparisons`, the ranking, the ties | §3.3 — one mechanical use, and it is not this. A guard refusing the owner's own word is the tool adjudicating him |

### 4.1 `GLOSSARY.md` is transitional, and change 1 loses two tasks because of it

**The owner ruled on this twice on 2026-07-30 and a later session logged it as open anyway. It is
not open.** *"Why are you writing `GLOSSARY.md` if you are not using it? The glossary should be a
table in the database"*, and *"if the data is in a table in the database, why are you writing an md
file?"* Restated when the question was put again: the file is **a transitional tool used to help
write v3**, and **v3 code reads only the `terms` table**.

So no v3 module and **no v3 test** reads that file. Two tasks in `01-vocabulary-and-levels.md` are
built on it and both are struck:

- **Task 1A.0** rewrote the file's ban line so the live check would permit `stage`. Gone.
- **Packet 1F, task 1F.1**, the banned-word enforcement test, whose behaviour 4 is *"takes its word
  list from `GLOSSARY.md`"*. Gone with the packet's other member re-homed, since 1F.2 is schema
  parity and unaffected.

**In their place, change 1's first task deletes `tests/test_vocabulary.py`.** It must be first for
the same reason 1A.0 was: change 1 renames the words that check bans, so every packet after it goes
red otherwise. Change 1 lands before change 4, which is why the deletion belongs there and not here.

**What is left enforcing v3's own identifier naming: nothing mechanical, deliberately.** §2.2 is the
argument — the failure is a synonym sharing no letters, and no scan sees it. `test_schema_vocabulary.py`
survives untouched; it checks column-name *roles* in `engine/schema.py` and never opens a markdown
file. The starter labels are not seeded into `terms` either: the owner defines the contents, and ten
words written by the tool at plan creation is the tool defining them.

**And one reversal of an amendment made earlier the same day.** `engine/lexical.py` was to hold a
shared tokeniser and ranking because three callers needed them, then two. With this change's guard
gone there is **one** — change 3's catalogue, which ranks function and object names and has nothing
to do with the glossary. Extract on the second occurrence; there is no second occurrence. **Change
3 keeps `CatalogueService._rank` private and takes the tokeniser with it**, and `CatalogueService`
stops taking `TermService` as a collaborator, since running purpose lines past `violations()` was
its only job there.

---

## 5. The work order

### 5.1 Amend the decisions first

**D12** currently reads that labels are *"governed by the glossary machinery"* and asserts a
near-duplicate refusal. Amend to §3.3: a label is a live glossary term, and the lookup is the
governance.

**Add D18 — the glossary is a user-owned table with one mechanical use.** §1–§4 of this document are
its content: the decision, the two directions of the failure, the measurement that killed the
allowlist, why no scan can work, and the rejected alternatives. A decision without its rejected
alternatives cannot be safely reopened.

**Amend `01-vocabulary-and-levels.md` too** — §4.1: task 1A.0 and task 1F.1 are struck, and change
1's first task becomes the deletion of `tests/test_vocabulary.py`. **Done 2026-07-30**, along with
`VOCABULARY.md`'s status header.

**`VOCABULARY.md`'s `Label` entry still describes the overturned design** and must be rewritten to
§3.3: it says labels are proposed by the tool and settled by the owner, that a near-duplicate is
refused, and that labels get their own table rather than glossary rows. All four are now false. Its
argument for a separate table — that a word can be both a term and a label, as `engine` is here —
dissolves, because under this design a label **is** a term. The ten starter labels stay in that
document as a suggestion to a reader; **they are not seeded into `terms`**, since the owner defines
its contents.

**PLAN.md item 4** reads *"Labels (D12), including the starter list and the glossary refusal of a
near-duplicate."* Rewrite: *the glossary reduces to a user-owned table, and labels are its one
mechanical use.* Items 5–10 are unaffected and are **not renumbered** — this change absorbs the
reduction rather than displacing anything, and it is smaller than the change it replaces despite
doing more, because the deletions outweigh what labels add.

### 5.2 Packet A — the schema

Version 10 → 11.

- The declared-vocabulary task lands **first**, as in changes 1, 2 and 3: `detached_at` joins
  `TIMESTAMP_ROLES` (**7 today**, measured 2026-07-30, and **staying 7** — `approved_at` leaves with
  the only column that used it; see §8 task 4A.0 and §14, which correct the "becoming 8" written
  here). **No column joins
  `JUSTIFICATION_ROLES`** — `term_comparisons` is gone and `label_attachments` records no reason —
  so the count after this change is **18**, unchanged from change 3. Re-enumerate from source at
  spec time; do not carry the number.
- `terms` loses six columns: `approved_at`, `names_ref`, `ban_scope`, `ban_reason`, `use_instead`,
  `superseded_at`. `idx_terms_live` becomes a plain `UNIQUE (term)`.
- **The migration is the real work in this packet.** Dropping six columns and swapping a partial
  unique index for a total one is a table rebuild, not a sequence of `ALTER`s, and it is the first
  migration in this engine that **loses data** — the ban metadata on existing plans. The words and
  their definitions survive; state the loss in the migration's docstring, because every existing
  migration says in its own words that it invents nothing, and this one must say what it discards.
- `label_attachments` is created. **Its design is settled and carried from `04-labels.md`** — see
  §5.8.

### 5.3 Packet B — `terms.py` reduces

Delete: `violations`, `banned`, `Usage`, `export_glossary`, `GlossaryExport`, `retire_term`,
`approve_term`, `awaiting_approval`, `is_approved`, `is_banned`, `bans`, `_tokens`, `_entry`,
`_name_of`.

Keep and simplify: `define_term` (no `names_ref`, no approval), `redefine_term` (in place, no
supersession), `glossary`, `find`, `_word`.

Add: `remove_term` — §3.4.

### 5.4 Packet C — the call sites lose their hooks

`rows.py` (the submission scan and the `TermService` construction behind it), `gates.py`
(`_retired_words` and its warning keys), `gaps.py` (two gap rules and the violations rule),
`resume.py` (the `glossary` Fetch, the awaiting-approval count and its line), `briefs.py` (the
glossary section, its field and the compose call), `warnings.py` (the retired-word kind).

**`terms` stays a reserved plan-row table name** (`rows.py`) — that is unaffected and its refusal
message still names `define_term`.

### 5.5 Packet D — labels

`attach_label`, `detach_label`, `labels`, and the `RowSelector.labels` filter with its join. Registry
rows, payload parsers, rendering. **All of this is already specified** in `04-labels.md` packets 4B,
4D and 4F — see §5.8 for what transfers and what changes.

The surface arithmetic **changes and must be re-derived, not carried**: this change *removes* three
tools (`retire_term`, `approve_term`, `export_glossary`) and adds **four** (`remove_term`,
`attach_label`, `detach_label`, `labels`) — see §14 for why "adding three" written here was wrong.
The measured inputs, re-counted from `engine/surface.py` on 2026-07-30, are **54** registrations and
**12** `ADDED` entries today.

### 5.6 Packet E — the methodology

Revision 6. The stage-6 labelling round; the residual packaging-round prose deleted (change 1's
1E.1 behaviour 5 deletes it at source — this catches anything reaching rev6 by copy); and
`approve_term` removed from `mandate.md` and `gap_rules.yaml`, which instruct the planner to use a
call that will no longer exist.

The round must say in as many words that **a label is a glossary term** and that `define_term` is
how you mint one — a planner who has read D12 will otherwise look for a `propose_label` that does
not exist.

### 5.7 Packet F — the tests

Rewrite the `terms` tests for the removed calls (`tests/test_vocabulary.py` is already gone —
change 1 deletes it, §4.1). Assert the new
shape: the migration drops the columns and keeps the words; `remove_term` refuses while attachments
exist and names the count; the replacement move collapses a duplicate rather than raising;
`get_stage_script(6)` renders without raising; the attachment index refuses a duplicate **at the
store, in raw SQL** (§5.8).

### 5.8 What transfers from `04-labels.md`, so none of it is re-derived

**Carried whole, all probed or measured:**

- The `label_attachments` design: keyed on the **word** (not a term id — a term id detaches every
  target on redefinition) and on the target's **lineage root** via `RowService.lineage_root`;
  `target_root TEXT` / `task_id INTEGER` with a `CHECK` that exactly one is set.
- **The uniqueness index must be over the `COALESCE` expressions.** Re-probed 2026-07-30 at SQLite
  3.49.1 against this exact shape: the natural form `(word, target_root, task_id)` accepts **every**
  duplicate, because every row has exactly one NULL among the target columns and SQL compares NULLs
  as distinct. It is inert for the life of the table.
- **Both `COALESCE` sentinels are reachable and need `CHECK`s.** `INSERT INTO tasks (id) VALUES (0)`
  is accepted despite `AUTOINCREMENT`, and collides with a row whose `target_root` is `''`.
- The index behaviour must be asserted **at the store with raw SQL**, never through the service: the
  service treats a duplicate attach as a no-op, so a service-driven test passes on the broken index.
- `attach_label` collapses duplicate targets **within one call** before the write — a unique index
  raises and aborts the batch rather than producing a no-op.
- `isinstance(x, int)` must not be the ref-or-task-id test: `bool` subclasses `int`, so `True` reads
  as task 1.
- Attachments and `terms` stay **out** of the snapshot table set, with the execution layer.
- The `read_rows` label filter is a real task with a real join, not a dataclass field: attachments
  key on lineage roots while `read_rows` is handed refs, and `total`, paging and DISTINCT all need
  specifying.
- The measurements in §2 of this document, and the counts of 54 / 12 / 7 / 11 / 255 in §5.

**Kept as a record, not as a specification:** `04-labels.md` §12, the cold read of the first draft.
Four readers, and its findings are why several items above are stated at all. Read it as evidence.

**Dead with the design:** everything in `04-labels.md` about `propose_label`, `approve_label`,
`retire_label`, the `labels` table, `term_comparisons`, `LabelResult`, the ranking, the ties, the
starter-list-as-candidates argument, and §11's shared-module amendment.

### 5.9 Order

Vocabulary declaration → schema and migration → models → registry rows → the service → the call-site
deletions → rendering → methodology → tests. The three rules that set it are unchanged from changes
1–3: a declaration lands before the DDL it describes, a registry row lands before any refusal whose
text names that call, and a stage script lands after the registry rows it names.

**One new sequencing hazard, specific to this change.** The deletions in packet C and the deletions
in packet B are mutually dependent — `rows.py` constructs a `TermService` for a scan that packet B
removes. Land the call-site removals **before** the service reduction, or the suite is red in the
middle with failures that read as mistakes.

---

## 6. Settled 2026-07-30 — nothing here is open

**Both remaining questions were answered. Recorded with his words so neither is re-opened.**

> yes to take it off everything, keep the two tools: there should be a tool to create terms and a
> tool to edit (redefine) them.

1. **"Take it off everything" is an allowed answer** to the `remove_term` prompt. Deletion is not
   blocked until nothing carries the word — the owner may detach the label from every target and
   delete the term in one act. It stays a choice he makes at the moment of removal; nothing about it
   is automatic, and the refusal that names the affected counts (§3.4) still comes first.
2. **`define_term` and `redefine_term` stay as two tools**, on the stated ground that creating a
   term and editing one are different acts. `define_term`'s refusal on an existing word is therefore
   kept, not inherited.

### The questions as they were put, for the record

**Two questions listed here on 2026-07-30 were never open — he had ruled twice.** `GLOSSARY.md` and
`spec/v3/VOCABULARY.md` are **transitional documents used to write v3**, read by people and sessions,
never by code. See §4.1, which also carries the two change-1 tasks that struck. Do not restore either
question and do not propose a mechanism over either file.

1. **Is "take it off everything" an allowed answer to the `remove_term` prompt**, or is deletion
   simply blocked until nothing carries the word? The assumption written into §3.4 is that it is
   allowed, because otherwise a filter you have decided is wrong must be detached by hand from forty
   rows first. Either way the owner chooses; it is never automatic. **Stated to him and not
   contradicted, which is not the same as confirmed.**
2. **`define_term` and `redefine_term` as two tools or one upsert.** Two keeps a refusal that catches
   "I thought this word was new"; one is less to know. Currently two, by inheritance rather than by
   decision.

---

# The specification

**Written 2026-07-30 from §1–§6, which are settled and are the input to everything below.** Every
count here was enumerated from source on that date and the method is stated beside it, because a
count nobody enumerated is the defect this build keeps rediscovering. §14 lists the four places
where re-measuring disagreed with what §5 or `04-labels.md` had written down.

## 7. How this change lands

**One branch, one pull request, six packets as its commit order.** The suite is required green at
the end and nowhere in the middle, as in change 1 and for the same reason: the deletions cross
module boundaries and no cut of them leaves every packet independently green.

### 7.1 The landing order is not the packet order

The letters are the commit order; this is the order the work has to happen in. Three standing rules
set most of it — a declaration lands before the DDL it describes, a registry row lands before any
refusal naming that call, and a stage script lands after the registry rows it names.

| | what lands | why here |
|---|---|---|
| 1 | 4A.0, the declared vocabulary | `detached_at` is an undeclared `*_at` role the moment 4A.1's DDL exists, and the suite goes red from 4A to 4F otherwise. Fourth change running. |
| 2 | 4A.1 DDL, 4A.2 migration | everything reads the tables |
| 3 | 4D.0, the models | the parser and the selector field both consume these types |
| 4 | 4D.4, the registry rows | `remove_term`'s refusal names `attach_label`; `attach_label`'s names `define_term` |
| 5 | **4C, the call-site removals** | **before 4B — see §7.2** |
| 6 | **4D.1–4D.3, the label service and the filter** | **before 4B — `remove_term` counts, moves and detaches attachments, which is all label-service work (4B.3 behaviour 12). The draft had these the other way round.** |
| 7 | 4B, `terms.py` reduces | |
| 8 | 4E, the methodology | after the registry rows its script names |
| 9 | 4F, the tests | last, because it asserts the rest landed |

**Row 6 was inverted in the draft and the cold read caught it.** That makes **four landing-order
inversions in four changes**, and change 3 had three at once. The shape is always the same: a task's
text names work that a later task provides. It is now worth treating as a standing pre-write check
rather than something the readers find.

### 7.2 The one sequencing hazard specific to this change

**The packet B and packet C deletions are mutually dependent.** `rows.py` constructs a `TermService`
and calls `violations()` at submission; `gates.py`, `gaps.py`, `resume.py` and `briefs.py` each hold
one too. Reduce the service first and every one of those five modules raises `AttributeError` on a
call that no longer exists, with the suite red in the middle showing failures that read as mistakes
rather than as sequencing.

**So the call sites lose their hooks first, and the service loses its methods second.** Measured
2026-07-30, the live call sites are `rows.py:412`, `gates.py:398`, `gaps.py:331` (`violations`),
`gaps.py:284` and `gaps.py:302` (`glossary`, `awaiting_approval`), `resume.py:421` and
`resume.py:423`, and `briefs.py:538`.

## 8. Packet 4A — the schema

Version 10 → 11. `SCHEMA_VERSION` is **7 in the code today**; changes 1, 2 and 3 take it to 8, 9 and
10, and none of them is built yet, so 10 is the number this change must find rather than assume.

### Task 4A.0 — the declared vocabulary

**Signature.** None — `TIMESTAMP_ROLES` in `tests/test_schema_vocabulary.py`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | `detached_at` joins `TIMESTAMP_ROLES`, meaning *the attachment was taken off its target; the row stays as the record that it was once there.* |
| 2 | **`approved_at` leaves `TIMESTAMP_ROLES` — but in 4A.1's commit, not this one**, because it must leave at the same moment its column does. |
| 3 | The set therefore holds **seven** members before and **seven** after — not eight. |
| 3a | A new test asserts the **reverse** direction: every declared role has at least one column in `engine/schema.py`. |
| 3b | `SHAPES` gains **`_root`** — *"the lineage root of a target row, as a `table:ordinal` ref"* — and the check requires it to be `TEXT`. |
| 4 | `JUSTIFICATION_ROLES` is unchanged at **18**: nothing this change adds carries a reason. |
| 5 | Both counts are re-enumerated from source at build time, by the method in §14, and not carried from this document. |

**Behaviour 2 splits across two commits, and the cold read is why.** The draft removed `approved_at`
here, in the task that lands *first* — while `terms.approved_at` still exists in `engine/schema.py`
until 4A.1 lands second. That fails `test_every_timestamp_column_is_a_declared_role` between the two
commits, which is the exact red window the "declaration lands before the DDL" rule exists to prevent,
running in the opposite direction. **The rule only covers additions; a removal wants the reverse
order.** So: `detached_at` is added here, `approved_at` is removed in 4A.1's commit alongside the
column. Fourth change running that this ordering rule has needed stating, and the first time it has
been stated in both directions.

**Behaviour 3a is the mechanism this whole finding shows is missing.** `test_every_timestamp_column_is_a_declared_role`
iterates columns and looks each up in the register; nothing iterates the register and looks for
columns. A role left behind after its column dies is therefore invisible **forever**, which is how
`approved_at` would have survived. The check is a few lines against the same `_columns()` helper,
generalises to every future change, and is the reverse of a check this repository has now been bitten
by twice — `GLOSSARY.md`'s exception protecting `PartsDontCover`, an identifier that does not exist,
was the same defect in the other register.

**Behaviour 3b is this task noticing its own subject, and it is the reason the task exists at all.**
The schema already holds two names for one concept: `gap_overlay.root_ref` and
`scope_attachments.target_root` are both *the lineage root of the row this record is keyed to*, spelt
two ways. `SHAPES` polices `_id`, `_key`, `_ref` and `_by`, and has no entry for `_root`, so
`target_root` has never been checked by anything. **`label_attachments.target_root` is the third
occurrence**, added by this change — so this is the moment the declared-vocabulary task either does
its job or becomes the thing it exists to prevent. Declaring `_root` does not rename either existing
column; it makes the next one a deliberate act. Renaming `root_ref` is a separate change's work and
is noted here rather than smuggled in.

**Behaviour 2 is a finding, not bookkeeping, and it is invisible to the mechanism that would
otherwise catch it.** `test_every_timestamp_column_is_a_declared_role` flags a column with no
declared role; it has nothing to say about a **declared role with no column**. Measured 2026-07-30
across all 37 tables: `approved_at` appears exactly once in `engine/schema.py`, on `terms`, and its
declared meaning is *"terms: the owner settled a definition the planner proposed"* — a table, an act
and an owner-facing state that all cease to exist here. Left in place it is a citation to nothing,
which is precisely the defect change 1 found in `GLOSSARY.md`'s exception for `PartsDontCover`, in a
register whose whole purpose is that names are declared deliberately.

**Behaviour 3 is where `04-labels.md` and §5.2 of this document are both wrong**, and the reason is
worth stating because it is the same trap twice. Both say the set becomes **eight**. Under the
superseded design that was right — approval survived, so `detached_at` was a net addition. Under §3.2
approval is deleted, so the arithmetic is 7 − 1 + 1. **A finding survives a design change only if you
re-derive it**, and this is the third time that has bitten this change.

**Behaviour 4's 18 is inherited from change 3 and must still be re-run.** `JUSTIFICATION_ROLES` does
not exist in the code today — measured 2026-07-30, it appears only in the specifications for changes
2, 3 and 4 — so there is nothing to count until change 2 lands. What this change contributes is
**zero**: `term_comparisons` is deleted with the near-match guard, and `label_attachments` records no
reason, because attaching is the act §1 makes free.

### Task 4A.1 — the DDL

**Signature.** `engine/schema.py`: `TERMS_DDL` is rewritten; a new `LABELS_DDL` is added.

**Behaviours**

| | behaviour |
|---|---|
| 1 | `terms` loses six columns: `approved_at`, `names_ref`, `ban_scope`, `ban_reason`, `use_instead`, `superseded_at`. |
| 2 | `idx_terms_live`, a partial unique index on `term WHERE superseded_at IS NULL`, is replaced by a **`CREATE UNIQUE INDEX` on `term`** — an index, not a table constraint, so that 4A.2 can create it after the drops. |
| 3 | `label_attachments` is created, with **three** indexes — the live uniqueness index, one leading on `target_root`, and one leading on `task_id`. |
| 4 | **No `term_comparisons`.** It goes with the near-match guard. |
| 5 | `LABELS_DDL` yields exactly **four** statements through `schema.statements` — one table, three indexes — verified through that function rather than counted by eye. |
| 6 | `label_attachments.word` carries no foreign key, and the DDL comment says why — **the reason rewritten, see below**. |
| 7 | Any retained per-version DDL fixture lives **outside** `engine/schema.py`. |
| 8 | **`DDL += LABELS_DDL`.** Without this line no freshly created plan has the table. |
| 9 | **`SCHEMA_VERSION` becomes 11**, and the running comment block above it gains this change's reasoning, as all four previous bumps did. |
| 10 | **The 3→4 migration branch stops sharing `TERMS_DDL`** and takes a frozen copy of the eleven-column text, held outside `engine/schema.py` per behaviour 7. |
| 11 | `approved_at` leaves `TIMESTAMP_ROLES` in this commit (4A.0 behaviour 2). |
| 12 | The 33-line comment block above `TERMS_DDL` is rewritten, and `CHANGE_LOG_DDL`'s comment loses its `ban_scope` sentence. |

**Behaviours 8, 9 and 10 are cold-read findings and each one alone stops the change working.**

*Behaviour 8.* `engine/schema.py` assembles its full DDL by explicit append — `DDL += TERMS_DDL`,
`DDL += REALLOCATIONS_DDL`, `DDL += REVISIONS_DDL`, `DDL += CHANGE_LOG_DDL`, four times — and
`init_plan` runs `executescript(schema.DDL)`. The draft said the table "is created" and never said to
append it. Every new plan would come up without it and fail on first use, while migrated stores had
it; and §8 says no migrated store exists.

*Behaviour 9.* Nothing in the draft set `SCHEMA_VERSION = 11`. `init_plan` stamps whatever that
constant says, so a v11 store would call itself v10, and `migrate(schema.SCHEMA_VERSION)` would never
select the new branch.

*Behaviour 10 is the nastiest, because it fails late and in the data-losing step.* `storage.py`
contains `if (current, target) == (3, 4): return schema.statements(schema.TERMS_DDL)`, and
`schema.py` says why in its own words — *"Held apart from DDL above so that `migrate`'s 3 -> 4 step
and a fresh `init_plan` create it from the same text."* Rewriting `TERMS_DDL` therefore rewrites
**history**: a store climbing from 3 would be handed the new five-column table, then reach 10→11 and
be asked for `superseded_at`, a column it never had. A migration is a point-in-time step and must
name a point-in-time text — which is exactly what behaviour 7 already says, applied one branch
earlier than the draft applied it.

**The DDL, carried from `04-labels.md` with `term_comparisons` removed:**

```sql
-- A label is a glossary term attached to rows; there is no label table (§3.3). This
-- table is the attachment and nothing else.
CREATE TABLE IF NOT EXISTS label_attachments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    word        TEXT    NOT NULL,  -- the term, as the word, and deliberately NOT
                                   -- REFERENCES terms (term): a detached attachment must
                                   -- go on naming a word the owner has since removed,
                                   -- because it is the record that the label was once
                                   -- there. An FK would delete or forbid that record.
    target_root TEXT,              -- the lineage root of a plan row, so the label neither
                                   -- re-surfaces nor silently detaches when the row is
                                   -- superseded (rows.py, lineage_root)
    task_id     INTEGER REFERENCES tasks (id),
    detached_at TEXT,              -- null == the label is on this target now
    created_at  TEXT    NOT NULL,
    CHECK ((target_root IS NULL) != (task_id IS NULL)),
    -- Both COALESCE sentinels below are reachable without these. Probed 2026-07-30:
    -- a task row with id 0 inserts despite AUTOINCREMENT once its NOT NULL columns are
    -- supplied, and an attachment on it then collides with one whose target_root is ''
    -- — two different targets sharing the index key (word, '', 0).
    CHECK (target_root IS NULL OR target_root <> ''),
    CHECK (task_id IS NULL OR task_id > 0)
);

-- Indexed on the expressions, not the columns. Every row here has exactly one NULL among
-- the two target columns, and SQL compares NULLs as distinct — so the natural form,
-- (word, target_root, task_id), accepts *every* duplicate rather than an unlucky few.
-- Probed at SQLite 3.49.1: it enforces nothing at all for the whole life of the table.
CREATE UNIQUE INDEX IF NOT EXISTS idx_label_attachments_live
    ON label_attachments (word, COALESCE(target_root, ''), COALESCE(task_id, 0))
    WHERE detached_at IS NULL;

-- Read when a row is rendered with the labels it carries. The live index above leads on
-- word and cannot answer that direction.
CREATE INDEX IF NOT EXISTS idx_label_attachments_target
    ON label_attachments (target_root, detached_at);

-- The same read for the other target kind. Half the rows here have a null target_root,
-- so the index above cannot serve them: remove_term's refusal has to count the tasks
-- carrying a word, and labels(word) has to list them, and both would be a table scan.
CREATE INDEX IF NOT EXISTS idx_label_attachments_task
    ON label_attachments (task_id, detached_at);
```

**Behaviour 2 is the half of this task that a reader will take for cosmetic, and the cold read found
the spec saying two different things about it.** `idx_terms_live` is partial *because* definitions
were superseded rather than edited; with `superseded_at` gone the `WHERE` clause names a column that
no longer exists, and SQLite refuses the column drop while it stands (probed — 4A.2 behaviour 4).

**It is an index, not a table-level `UNIQUE (term)` constraint**, and the draft wrote it both ways —
§3.1 and this behaviour as a constraint, 4A.2 as something "created" after a rename. A table
constraint cannot be added after the fact, so the constraint reading would have made 4A.2's step list
impossible; the index reading is what makes the in-place `ALTER` route work at all. §3.1's shorthand
stands as a description of the shape, not as DDL.

**And behaviour 6 still declines the foreign key, but the comment's reason was wrong and is
rewritten.** The draft's comment announced that it was rejecting `REFERENCES terms (term)` and then
argued against keying on `terms.id` — a non sequitur — on the ground that a redefinition would detach
every target. Under §3.2 a redefinition is an in-place `UPDATE` and detaches nothing, so that
argument is dead. The real reason is §3.4: a detached attachment must go on naming a word the owner
has since removed, because it is the record that the label was once there, and a foreign key would
either forbid the removal or delete the record. That is what the comment now says. **This is the
defect 4A.0 behaviour 2 exists to catch — a citation to nothing — committed inside the same task.**

**Behaviour 5 is a real dependency and not arithmetic.** `schema.statements` splits on semicolons and
the block above **contains semicolons inside comments**, so the count holds only because comments are
stripped first. Probed against the superseded four-statement block; re-probe the three-statement one
rather than assuming the property carried.

**Behaviour 7 is the debt change 3 repaid to changes 1 and 2, restated because it recurs here.**
`_columns()` in `test_schema_vocabulary.py` regexes every `CREATE TABLE IF NOT EXISTS` out of the
whole of `engine/schema.py`, so a retained v10 DDL sitting in that file is phantom live schema — for
4A.0's own new count, among others.

### Task 4A.2 — `Storage._migration_steps`, the 10→11 branch

**Signature.** Unchanged: `_migration_steps(self, current: int, target: int) -> list[str]`. Gains one
branch.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Creates `label_attachments` and both indexes from `schema.LABELS_DDL` via `schema.statements`. |
| 2 | Reduces `terms` **in place, with `ALTER TABLE … DROP COLUMN`** — no table rebuild, no second copy of the DDL. |
| 3 | Only **live** term rows survive: the superseded ones are deleted, and that `DELETE` runs **first**. |
| 4 | The steps are, in this exact order: delete superseded rows → `DROP INDEX idx_terms_live` → six `DROP COLUMN`s → `CREATE UNIQUE INDEX` on `term`. |
| 5 | Seeds no word, and backfills no attachment. |
| 6 | Adds `label_attachments` **to** the snapshot table set. |
| 7 | Its docstring states what the migration **discards**, and its opening line stops saying "Two paths exist" when it will then document eight. |
| 8 | `migrate` **chains**: a store at any version below the target steps through every intermediate branch in one call, rather than raising "no migration path". |

**Behaviour 8 closes a hole that is not this change's fault and becomes unavoidable at this change.**
`_migration_steps` matches adjacent pairs only — `(3,4)`, `(4,5)`, `(5,6)`, `(6,7)` — and ends by
raising when no pair matches. `SCHEMA_VERSION` is 7 in the code and exactly one database exists, at
7. Changes 1, 2 and 3 each add one branch and this change adds the fourth, so reaching 11 means four
separate `migrate` calls in the right order, and a single `migrate(11)` — the obvious thing to do —
raises. Nobody would discover that until the one real database was in front of them. Chaining is a
loop over the intermediate versions; each step keeps its own snapshot and its own failure, so nothing
about the existing safety changes.

**Behaviour 2 reverses the draft, and it was settled by probe rather than by argument.** The draft
asserted that dropping six columns and swapping a partial unique index for a total one "is a table
rebuild in SQLite, not a sequence of `ALTER`s" — offered with no probe, and the cold read challenged
it. `ALTER TABLE … DROP COLUMN` has existed since SQLite 3.35 and this engine runs 3.49.1. Probed on
2026-07-30 against a v10 `terms` holding a redefined word and a banned word:

| | result |
|---|---|
| the six drops plus the index swap, inside `BEGIN IMMEDIATE`, `PRAGMA foreign_keys = ON` | **works**; final columns are exactly `id, term, definition, created_at, updated_at` |
| live rows | kept, with their original `created_at` and `updated_at` |
| `sqlite_sequence` | **preserved** — high-water mark 3 before, next id allocated 4 after, so register entry 7's "ids are never reused" survives |
| the new `UNIQUE (term)` | enforcing — a duplicate is refused |
| forcing a failure on the last step, then `ROLLBACK` | table restored to all **11** columns and all 3 rows; DDL is transactional here |

This deletes a hole the draft carried without noticing: a rebuild would have needed a second
`CREATE TABLE terms` written inside `storage.py`, and `schema.py` forbids exactly that in its own
words — *"Two copies of a `CREATE TABLE` is a schema that drifts between the stores that were
migrated and the stores that were born."* There is now no second copy.

**Behaviour 4's order is not stylistic; two of its three dependencies were probed and both bite.**
Dropping `superseded_at` while `idx_terms_live` still exists fails with *"error in index
idx_terms_live after drop column: no such column: superseded_at"* — SQLite validates surviving
indexes against the reduced table. And the `DELETE` must precede the drop, because after it
`superseded_at` is not there to filter on. Written in any other order the migration fails, and it
fails inside the step that is discarding data.

**Behaviour 3 is the one place this migration could silently corrupt the table.** Under the old
schema a redefinition wrote a new row and stamped the old one, so a word that has ever been redefined
has **several** rows and one live. The new `UNIQUE (term)` is total, so keeping them all makes the
index creation fail — and a copy written to tolerate that would keep an arbitrary definition. The
lineage is what §4 deletes; the live row is what survives.

**Behaviour 6 reverses the draft too, and the draft stated the decision with no argument at all.**
`snapshot_version` covers nine tables, and `storage.py` says what earns a place: *"overlays and
ledgers that are not derivable from the rows. A snapshot that dropped these would silently unblock
gates on restore … and re-surface dismissals the owner had already answered."* `label_attachments` is
precisely that — an overlay keyed on lineage roots, the same primitive as `gap_overlay`, holding
judgments that cannot be recomputed from the rows. Left out: `restore_snapshot` on an abandoned
revision rewinds `plan_rows` and strands attachments on roots that no longer exist; `recover("restart")`
deletes every plan row and orphans all of them, and neither column carries a foreign key to catch it;
and `remove_term`'s refusal would then report affected rows that do not exist. **`terms` itself stays
out**, because it is not derived from the plan and is not rewound by a revision — but the attachment
of a word to a row is a judgment about the plan, and it belongs with the plan's other overlays.

**Behaviour 6 is a first for this engine and it is why the task is specified rather than assumed.**
Every existing migration says in its own words that it invents nothing. This one **loses data**: the
ban metadata on existing plans, and every superseded definition. The words and their live meanings
survive. A migration that discards must say so where the next reader looks, which is its docstring,
because the alternative is a silent loss discovered by its absence.

**One thing this migration does not do, stated because it is the tempting fix.** It does not refuse
when ban metadata exists. Change 1's 1A.1 refuses a plan holding more than one live declared package,
on the ground that collapsing them invents a claim about the owner's grouping. This is not that
shape: nothing is being invented, a record is being dropped on the owner's explicit instruction, and
exactly one database exists.

## 9. Packet 4B — `terms.py` reduces

Depends on 4C having landed first (§7.2).

### Task 4B.1 — the deletions

**Signature.** Removal only.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Deleted from `terms.py`: `violations`, `banned`, `bans`, `is_banned`, `is_approved`, `approve_term`, `awaiting_approval`, `retire_term`, `export_glossary`, `_tokens`, `_entry`, `_name_of`. |
| 2 | Deleted types and constants: `Usage`, `GlossaryExport`, `EXPORT_FILENAME`, `BAN_SCOPES`, `PROSE`, `IDENTIFIER`, `BOTH`, `ADDRESS`. |
| 3 | Deleted errors: `AlreadyApproved`, `BanNeedsReason`. |
| 4 | `Term` loses `approved_at`, `names_ref`, `ban_scope`, `ban_reason`, `use_instead`, `superseded_at`. |
| 5 | The module docstring is rewritten to §2.2 and §3.3. |
| 6 | `_word` survives. **`WORD` does not** — see below. |
| 7 | **Also deleted, each with no reader left:** `_segments` (only caller `violations`), `_succeed` (only callers `redefine_term`, now an `UPDATE`, and `approve_term`), `Term.is_live` (reads the deleted `superseded_at`), `history()` (a lineage that no longer exists), and the `rows` constructor parameter with `self.rows` (only reader `_name_of`). |
| 8 | `find()` and `glossary()` lose their `superseded_at IS NULL` predicates; `_hydrate` stops reading the six dropped columns. |
| 9 | The now-unused imports go: `json` and `Path` (only `export_glossary`), `RowRef` (only `names_ref`). |
| 10 | Stale prose on **surviving** members is rewritten, not just the module docstring: `find`'s "banned or not", `glossary`'s "Banned words are included", `redefine_term`'s "the old wording stays as history", `TermExists`'s promise of history. |

**Behaviours 7 to 10 are cold-read findings, and every one of them meets the test §4 already applies
elsewhere.** §4 justifies deleting `_tokens`, `ADDRESS` and `names_ref` on "no second caller" — and
then the draft's list stopped, leaving five members whose only callers it was deleting in the same
task. `history()` is the sharpest: over a table with no lineage it can only ever return the one live
row, so it survives as a call whose answer is `find()`.

**Behaviour 6 reverses the draft on `WORD`, because the draft's own reason contradicted itself.** It
kept the regex "because change 3 needs a tokeniser", citing §4's ruling — which says
`CatalogueService` keeps `_rank` private **and takes the tokeniser with it**. Both cannot be true. If
change 3 takes it, `WORD` has no reader here once `_tokens` and `violations` go, because `_word` is
strip-and-lowercase and needs no regex; if change 3 imports `terms.WORD` instead, that is the second
caller whose absence §4 used to justify deleting `engine/lexical.py`. The tokeniser goes to change 3,
and `WORD` goes with it.

**Behaviour 2 deletes `ADDRESS` and that is a deliberate loss.** It stripped `requirements:61`-style
addresses before tokenising, so a citation of a retired word did not read as a use of it. It existed
for `violations()` and has no second caller — measured, not assumed. It goes with the scan.

**Behaviour 5 is not tidying.** The docstring currently argues at length for the banned list, for
`ban_scope` as a queryable denominator, and for proposal-and-approval — every one of which §1 and §4
delete. Left standing it is the most persuasive document in the repository arguing for machinery that
no longer exists, sitting in the file a reader opens first. It must instead carry §2.2: the failure
is a synonym sharing no letters, no scan sees it, and the glossary's job is to be **in front of the
writer at the moment of naming**.

**And the sentence that argument comes from is not where this document twice said it was.** §2.2 and
the draft of this behaviour both claim it sits in `terms.py`'s *module* docstring, "one paragraph
down". It does not. Measured 2026-07-30: the module docstring runs to line 50 and covers F27, the
real-table argument, propose-and-approve, the retired-word trap and plan-level scope. The sentence —
*"it matches words, so a new name invented for an existing concept, sharing no letters with it, goes
unseen. Nothing without judgment can catch that"* — is at **line 482, inside the docstring of
`violations()`**, the method behaviour 1 deletes. So a builder doing the deletions before the rewrite
destroys the text this behaviour tells them to promote. **Copy it out before deleting**, and correct
§2.2, which rests the whole design on a claim about where it lives.

**Behaviour 6 keeps `WORD` because change 3 needs a tokeniser and `lexical.py` is reversed.** §4's
last paragraph is the ruling: one caller, so no shared module, and `CatalogueService` keeps `_rank`
private and takes the tokeniser with it. `_word` — strip and lowercase, refusing empty — stays here
because the glossary is where a word is normalised.

### Task 4B.2 — `define_term` and `redefine_term` simplify

**Signature.** `define_term(self, term: str, definition: str) -> Term` and
`redefine_term(self, term: str, definition: str) -> Term`. Both lose `names_ref`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | `define_term` writes one row and returns it. No approval state, no `names_ref`. |
| 2 | `define_term` still refuses an existing word with `TermExists`, naming `redefine_term`. |
| 3 | `redefine_term` updates `definition` **in place** and stamps `updated_at`. |
| 4 | `redefine_term` refuses an unknown word with `TermNotFound`, naming `define_term`. |
| 5 | Both still refuse an empty definition with `DefinitionRequired`. |
| 6 | Neither writes a comparison, ranks anything, or consults another term. |

**Behaviours 1 and 2 are the owner's ruling of 2026-07-30**, in his words: *"keep the two tools:
there should be a tool to create terms and a tool to edit (redefine) them."* So `define_term`'s
refusal is kept **by decision** and no longer by inheritance — which matters, because the argument
for merging them into an upsert is otherwise good and would be made again.

**Behaviour 3 is the change that removes a whole lifecycle.** Redefinition was a supersession: stamp
the old row, write a new one, one transaction, ordered so the partial live index never saw two live
rows for one word. All of that existed to keep a definition's history, and §4 deletes the history on
change 3's settled ground — nothing cites a definition, so there is no argument depending on the
wording it had last week. In place is now literally an `UPDATE`, and the ordering hazard disappears
with the partial index.

**Behaviour 5 keeps `DefinitionRequired` on both, and it is the last mechanical opinion the glossary
holds.** A word listed with no meaning beside it is a word two readers read two ways, which is the
failure in §2.1 direction B arriving through the glossary itself.

**Behaviour 6 is where the near-match guard is refused a second time.** Under §3.3 the one mechanical
use is the lookup at `attach_label`. A ranking inside `define_term` would be the tool adjudicating
the owner's own word at the moment he defines it.

### Task 4B.3 — `remove_term`

**Signature.** `remove_term(self, term: str, replacement: str | None = None, detach_all: bool = False) -> None`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | With no live attachment: deletes the `terms` row. |
| 2 | With live attachments and no instruction: **refuses**, naming how many plan rows and how many tasks carry the word — two counts, never their sum. |
| 3 | With `replacement`: every live attachment moves from the word to the replacement, then the row is deleted. One transaction. |
| 4 | The replacement must itself be a live term, refused with `TermNotFound` naming `define_term` if not. |
| 5 | A target already carrying the replacement does **not** raise: the attachment collapses to one. |
| 6 | The move covers **live attachments only**; a detached one stays detached and keeps pointing at the dead word. |
| 7 | With `detach_all=True`: every live attachment is detached, then the row is deleted. One transaction. |
| 8 | `replacement` and `detach_all` together are refused — they are two answers to one question. |
| 9 | Removing an unknown word refuses with `TermNotFound`. |
| 10 | **`Storage`'s op vocabulary gains a `delete` kind**, without which none of the above can be written. |
| 11 | Two new errors: `TermInUse` (behaviour 2) and `AmbiguousRemoval` (behaviour 8). |
| 12 | The attachment work is done through `LabelService`, which therefore lands **before** this task. |
| 13 | A `replacement` equal to the word being removed is refused; a `replacement` supplied when nothing is attached is still validated as a live term, then ignored. |

**Behaviour 10 is the cold read's hardest finding in this packet: as drafted, `remove_term` was
unbuildable.** `Storage.write_atomic` accepts `kind: Literal["insert", "update", "insert_row"]` and
nothing else — there is no delete, and `briefs.py` states the reason in the source: *"storage's op
vocabulary is insert/update by design (no delete: plan history is append-only)."* Every one of
behaviours 1, 3 and 7 ends by deleting the `terms` row.

**The rule that forbids a delete does not reach this table, and that is the owner's own decision.**
Append-only is a property of **plan history** — `plan_rows` and the ledgers keyed to it, where a
superseded row is the record of what the plan used to say. `terms` was deliberately made a real table
rather than a plan-row type, and §1 makes its contents the owner's to edit: *"the user defines the
contents."* A glossary you may add to and rewrite but never remove from is not a table the owner
owns. So the vocabulary gains `delete`, and the guard is that it is **the narrowest possible
addition** — one op kind, and this specification names `terms` as its only permitted target, so a
later change deleting from `plan_rows` has to argue for it in its own words rather than inherit
permission from here.

**Behaviour 11 exists because the draft named two refusals and no error classes**, while 4B.1 deletes
two and adds none. The register requires a typed exception per named error, and there were none to be
per.

**Behaviour 12 reverses the landing order and §7.1 is corrected to match.** The draft put this packet
at step 6 and the label service at step 7, while requiring this task to count live attachments, move
them, dedupe the collapse and detach them — all of it label-service work. The alternative the draft
implied is that `remove_term` reaches into `label_attachments` directly, which duplicates the dedupe
and the root resolution, in the same change that deleted `engine/lexical.py` on the ground that there
was no second occurrence. **This would have been the second occurrence.**

**Behaviour 2 is the owner's instruction and the shape of it matters.** *"If the user tries to delete
a glossary item that is a label then prompt for a replacement label, do not arbitrarily remove the
label from all the references."* The refusal **is** the prompt — this engine has no other way to ask
a question — so it must carry what the owner needs in order to answer: not that the word is in use,
but how widely, split by population. The two-denominator rule from `04-labels.md` §3.8 applies here
for the same reason it applies to `labels()`: a word on three rows and a word on four hundred are
different decisions, and a summed count hides which one this is.

**Behaviour 7 is his ruling of 2026-07-30**, in his words: *"yes to take it off everything."* It is
opt-in and explicit; nothing about it is a default. The alternative — deletion blocked until the
owner detaches by hand — was rejected because a filter he has decided is wrong would have to be
peeled off forty rows before he is allowed to say so.

**Behaviour 5 is the mechanical detail that would otherwise be discovered by a raise in production.**
Moving `part` to `component` on a target that already carries `component` is two live attachments for
one pair, which the unique index refuses, aborting the whole transaction — so a single already-tagged
row would make the entire replacement fail. The collapse is the same dedupe `attach_label` performs
in behaviour 7 of 4D.2, and it belongs on the write path in both places rather than being left to the
index.

**Behaviour 6 is the record surviving the word.** A detached attachment is the evidence that the
label was once there; rewriting it to the replacement would falsify that record, and deleting it
would destroy it.

**Behaviour 8 exists because the two parameters read as compatible and are not.** Supplying both is
the caller not having decided, and this engine refuses rather than picking.

**Why this is one call with a parameter rather than three calls.** The three outcomes share the whole
of their work — normalise, look up, count, transact, delete — and differ only in what happens to the
attachments. Three tools would be three copies of the refusal and three registry rows for one act.
`use_instead` was a stored column for exactly this information and §2.6 is the argument for it being
a parameter instead: supplied at the one moment it is needed and consumed immediately.

## 10. Packet 4C — the call sites lose their hooks

**This lands before packet 4B (§7.2).** Six modules, each losing a hook into machinery that is about
to stop existing. Line numbers are as measured 2026-07-30 and are a finding aid, not an address.

### Task 4C.1 — `rows.py`

**Behaviours**

| | behaviour |
|---|---|
| 1 | The submission scan at `rows.py:412` is deleted, **and with it `_vocabulary_note` whole (`rows.py:399`) and its call site at `rows.py:218`.** |
| 2 | The `terms` constructor parameter, its default `TermService` construction and the `self.terms` attribute are deleted. |
| 3 | **`terms` stays a reserved plan-row table name** — but its refusal text is rewritten, because the argument in it dies here. |
| 4 | `RowVerdict.note` is left with no producer in `rows.py`; the field stays, and this task says so rather than leaving it to be discovered. |

**Behaviour 1 is corrected from the draft, which said the scan is "deleted with the warnings it
raised."** It raises no warnings. It produces a **verdict note** —
`verdicts.append(RowVerdict(index, True, note=self._vocabulary_note(submission)))` — so what the
deletion actually orphans is the `_vocabulary_note` method, its call site, and the argument. The
draft named none of the three.

**Behaviour 3's reservation survives; its stated reason does not.** The refusal text argues that the
glossary is a real table *"because a word being redefined and a word being replaced are two different
relations that supersession collapses into one."* After this change redefinition is an `UPDATE`,
replacement is a parameter of the delete, and supersession is gone — so the sentence explains the
table by machinery the same change deletes. The reservation is still right for the plain reason: a
real table owns that name, so plan rows must not be written into it.

**Behaviour 3 is the one thing in this module that does not change**, and it is called out because
the surrounding deletions make it look like an oversight. The reservation exists so that
`submit_rows(table='terms')` is refused with an explanation rather than writing plan rows into a
namespace the real table owns. That is as true after this change as before it.

### Task 4C.2 — `gates.py`

**Behaviours**

| | behaviour |
|---|---|
| 1 | `_retired_words()` is deleted whole, and the loop over it — which is in **`_raise_warnings` (`gates.py:340`)**, not in `run_gate`. |
| 2 | The `terms` parameter, the `TermService` default, the `Usage` import **and the `RETIRED_TERM` import (`gates.py:49`)** go with it. |
| 3 | The gate's remaining warning kinds and their counting are untouched. |

**Behaviour 2's `RETIRED_TERM` import is the one that would have broken the entire suite, not just
the glossary tests.** 4C.6 deletes that constant from `warnings.py`; `gates.py` imports it by name at
module level, so the import fails and every test importing `gates` fails with it. The draft's
behaviour 2 listed only the `Usage` import.

**This is the gate that "counts what submission only mentioned in passing", and losing it is the
deliberate half of §2.5.** The gate counted a denominator that came from the banned list; with no
banned list there is no denominator, and a coverage check with an empty denominator reports success —
F23's shape, which is worse than not running.

### Task 4C.3 — `gaps.py`

**Behaviours**

| | behaviour |
|---|---|
| 1 | `_rule_no_glossary` is deleted, and its `"no_glossary"` entry in the rule table. |
| 2 | The awaiting-approval rule is deleted, and its entry. |
| 3 | **`gaps.py:331` is not a rule and there is no third entry to delete.** It is the `violations()` loop inside `live_warning_keys()`, and *that loop* is what goes. |
| 4 | The `terms` parameter and the `TermService` default go. |
| 5 | `gap_rules.yaml` loses the two rules' declarations **in every loadable revision — rev3, rev4, rev5 and rev6 — not only the newest.** |

**Behaviour 3 is a factual correction and it matters because the draft's version fires the exact
hazard §7.2 sequences the whole change around.** The rule table holds seven handlers —
`empty_table`, `missing_field`, `untraced`, `open_assumption`, `uncited_section`, `no_glossary`,
`unsettled_term` — and no violations rule; §4's evidence table repeats the same error. A builder
following the draft deletes nothing at line 331, then behaviour 4 removes `self.terms`, and
`live_warning_keys()` — called from both `GateEngine._clear_settled_warnings` and
`WarningService._reconcile` — raises on a collaborator that is gone, and then on `violations` once 4B
lands. The count of three call sites was right; the identification of the third was wrong.

**`live_warning_keys` is the F50 reconciliation method**, and losing its retired-word branch is
correct: it reconciles live warnings against what still holds, and a warning kind with no producer
has nothing to reconcile.

**Behaviour 5 is widened, and the draft's version left the harm it describes in place.** `rev3` is
`EARLIEST_LOADABLE_REVISION`, so it stays loadable forever, and its `gap_rules.yaml` declares both
rules — with `unsettled_term`'s text ending *"record the answer with `approve_term`"*. Strip only the
newest revision and `load(3)` still yields two rules whose types `gaps.py` no longer implements, and
still tells a planner to call a tool the registry cannot resolve. That is 4E's own stated harm,
surviving in three of the four loadable revisions.

### Task 4C.4 — `resume.py`

**Behaviours**

| | behaviour |
|---|---|
| 1 | The `glossary` `Fetch` field, its construction at `resume.py:420` and its **one** rendered line — `lines.append(self.glossary.present())` at `resume.py:262` — go. |
| 2 | `terms_awaiting_approval`, its count at `resume.py:423` and the sub-line naming `approve_term()` (`resume.py:263–272`) go. |
| 3 | The "No agreed terms yet — `define_term()`…" line goes with them. |
| 4 | The `terms` parameter and the `TermService` default go. |

**Behaviour 3 is the one a builder will want to keep and must not.** It reads as helpful onboarding
rather than as a nag. It is the mechanical prompt in §1 — *"Forget you prompting the user, it's
another friction point"* — and it fires on exactly the plans where the owner has not yet decided he
wants a glossary. §1's distinction is the line: this is a mechanism that interrupts him, not a
sentence in a reply.

### Task 4C.5 — `briefs.py`

**Behaviours**

| | behaviour |
|---|---|
| 1 | The `glossary` field on the brief, its population at `briefs.py:538` and its rendered section go. |
| 2 | The `terms` parameter and the `TermService` default go. |

**The owner's reasoning, because it is better than the one the code carries:** *"The brief idea is
dumb, you don't build it until the plan is finished, but you need the glossary context during the
plan."* The brief is served after finalisation; naming drift happens while rows are being written.
The glossary arrives after the damage. The module's own comment had already reached half of this —
*"serving last week's glossary would enforce a rule the plan has since retired"* — and drew the wrong
conclusion from it.

### Task 4C.6 — `warnings.py`

**Behaviours**

| | behaviour |
|---|---|
| 1 | The `RETIRED_TERM` constant is deleted from `warnings.py`, **and removed from `SETTLEABLE_KINDS`**. |
| 2 | Its rationale comment in `warnings.py` goes; the key-construction literals it describes live in `gates.py` and `gaps.py` and go with 4C.2 and 4C.3. |
| 3 | **Any `retired_term` rows already in a live `warnings` table are settled by the migration**, not left active. |

**Its only producer was `violations()`.** A warning kind with no producer cannot fire, and a kind
table listing one is a menu item that is never cooked.

**Behaviour 3 is a hole the draft left open and it fails in the direction that annoys the owner.**
Once `RETIRED_TERM` leaves `SETTLEABLE_KINDS`, neither `_reconcile` nor `_clear_settled_warnings`
will ever touch an existing `retired_term` row again — so it stays `active` forever, with nothing
able to produce it and nothing able to settle it. A permanent nag, in the digest §1 exists to
de-noise, about a rule that no longer exists.

**And behaviour 2 corrects the draft, which put the key-construction comment in the wrong file.**
`warnings.py` holds the kind's rationale; the `f"term:{root}:{usage.term}"` literals are in `gates.py`
and `gaps.py`.

## 11. Packet 4D — labels

Depends on 4A. 4D.0 lands with 4A; 4D.4 lands before 4C.

### Task 4D.0 — the models

**Signature.** Three frozen dataclasses in `models.py`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | `Attachment` — `id: int`, `word: str`, `target_root: RowRef \| None`, `task_id: int \| None`, `detached_at: str \| None`, `created_at: str`, with an `is_live` property. |
| 2 | `LabelUsage` — `word: str`, `definition: str`, `row_count: int`, `task_count: int`. |
| 3 | `LabelTarget` — `kind: str` (`"row"` or `"task"`), `ref: RowRef \| None`, `task_id: int \| None`, `name: str`. |
| 4 | `LabelReport` — `usages: tuple[LabelUsage, ...]`, `live_rows: int`, `live_tasks: int`, `unattached_terms: int`, `targets: tuple[LabelTarget, ...]`. |
| 5 | `RowPage` gains `labels: dict[RowRef, tuple[str, ...]] = field(default_factory=dict)`. |
| 6 | `RowSelector` gains `labels: tuple[str, ...] = ()` — **here, not in 4D.3**, because the payload parser lands before the filter. |
| 7 | There is no `Candidate`, no `TermComparison`, no `LabelResult` and no `Label`. |

**Behaviours 2 to 4 spell out every field because the draft did not, and that is the defect this task
was written to prevent.** Its own justification names the v2 case — `WriteBatch`, `RowSelector`,
`TraversalSpec` and `GraphScope`, four types the plan named and nobody defined, *"so two implementers
would have built two incompatible interfaces"* — and then gave `LabelUsage` and `LabelReport` as
prose. Two builders would have produced `LabelUsage(word, definition, rows, tasks)` and
`LabelUsage(term, definition, row_count, task_count)`. Worse, 4D.3 requires the report to carry
"a plan row as its name and ref, a task as its id and title" — a fourth type with no name at all,
which is now `LabelTarget`.

**Behaviour 5's `default_factory` is not a detail.** `RowPage` is `@dataclass(frozen=True,
slots=True)`, and a bare `= {}` is a `ValueError` at class-definition time. Note also that `frozen`
synthesises `__hash__`, so a page carrying a dict can no longer be hashed — harmless today, since
nothing puts a page in a set, and recorded so it is not discovered by a `TypeError`.

**Behaviour 6 moves the selector field into this task, correcting §7.1.** The landing order justified
putting the models early because "the parser and the selector field both consume these types", then
defined the field three steps later than the parser that fills it.

**Every field is listed because a return type's fields are not a convention.** They differ per task,
so a type named and not defined is a hole in every task that consumes it — the recorded v2 defect is
`WriteBatch`, `RowSelector`, `TraversalSpec` and `GraphScope`, four types the plan named and nobody
defined, *"so two implementers would have built two incompatible interfaces."*

**Behaviour 1's `target_root` is a `RowRef`, not a string**, because every other model here that
holds a row address holds a `RowRef`. The column is TEXT; the model coerces.

**Behaviour 2 drops `is_approved` and `is_banned`** from the shape `04-labels.md` specified. Neither
state exists.

**Behaviour 3 carries the denominators inside the report rather than beside it**, so a caller cannot
render a count without one. A count whose denominator is one call away is a count that gets rendered
alone.

### Task 4D.1 — the read path

**Signature.** A new module `engine/labels.py` holding `LabelService`, with
`__init__(self, storage: Storage, rows: RowService, terms: TermService)` — **all three required, none
optional** — and three private methods: `_live_term(word) -> Term`,
`_target_key(target) -> tuple[str | None, int | None]`, `_attachments(word, live_only=True) -> tuple[Attachment, ...]`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | `_live_term` returns the live `terms` row, or refuses with `TermNotFound` naming `define_term`. |
| 2 | `_target_key` returns `(str(lineage root), None)` for a ref and `(None, task id)` for a task id, and refuses anything else with `InvalidTarget`. |
| 3 | A ref is checked for **existence** via `RowService.get` before its root is taken; an unknown one raises `RowNotFound`. A task id is checked against `tasks`. |
| 4 | The word is normalised — stripped and lowercased — and an empty one is refused. |
| 5 | `_attachments` returns live attachments unless asked for all. |

**The constructor is specified, and its collaborators are required rather than optional, because the
register's default would have made this fail silently.** Nothing in the draft said which module
`LabelService` lives in, what it takes, or who builds it. Register entry 11 says a collaborator not
passed has "its guard skipped and its effects omitted" — so `LabelService(storage)` would have
constructed cleanly and quietly stopped resolving lineage roots, which is the one thing the whole
keying design exists to do. This task overrides entry 11, with that as the written reason.

**Behaviour 3 is a cold-read finding and the draft's delegation could not deliver it.** The draft said
`_target_key` "refuses an unknown one" and named `RowService.lineage_root` as the mechanism.
`lineage_root` does not refuse anything — its body is `if not found or not found[0]["supersedes"]:
return current`, so a row that does not exist and a row with no parent take the same branch and both
return the input ref. `attach_label("engine", ("nosuch:99",))` would have succeeded, writing an
attachment to a target that has never existed and that nothing would ever clean up, since `word` and
`target_root` both carry no foreign key. Existence has to be checked explicitly.

**Behaviour 1 is the whole of the glossary's mechanical role** (§3.3). There is no ban branch and no
`TermBanned`; the superseded design had both.

**Behaviour 2 is where the two id spaces are told apart, and `isinstance(x, int)` is not how.** `bool`
subclasses `int`, so `isinstance(True, int)` is `True` and `attach_label(word, (True,))` reads as
task 1. The test is `type(x) is int`, or an explicit `bool` rejection first.

**The lineage root is why this is a method and not an inline expression.** Attachments key on the
root so a label neither re-surfaces nor silently detaches when a row is superseded; that resolution
belongs in one place, and it delegates to `RowService.lineage_root`.

### Task 4D.2 — `attach_label` and `detach_label`

**Signature.** `attach_label(self, word: str, targets: Sequence[RowRef | str | int]) -> tuple[Attachment, ...]`
and `detach_label` with the same shape.

**Behaviours**

| | behaviour |
|---|---|
| 1 | `attach_label` refuses unless a live term holds the word, naming `define_term`. |
| 2 | Each target resolves to a lineage root or a task id, refusing an unknown one. |
| 3 | Re-attaching an already-attached target is a **no-op**, not an error. |
| 4 | Detaching an unattached target is a no-op. |
| 5 | Duplicate targets **within one call** are collapsed before the write. |
| 6 | Detaching stamps `detached_at`; it never deletes the row. |
| 7 | Neither call takes an idempotency key; each derives one from **the call's own name**, the word, and the sorted target keys. |
| 8 | No reason is recorded on either act. |
| 9 | Both return the word's live attachments after the call, not the delta. |

**Behaviours 3 and 5 are service-side guards, and the index is the backstop rather than the
mechanism.** A unique index does not produce a no-op — it raises and aborts the batch. So a repeat
attach must be filtered before the write, and duplicate targets inside one call must be collapsed
first or they reach the index as two inserts in one batch and take the other nine rows with them.

**Behaviour 7 is a decision this design earns rather than inherits.** `write_atomic` requires a key,
and the honest reason not to take one from the caller is that both calls are **idempotent by
construction**: behaviour 3 makes a repeat a no-op returning the same answer, so there is no replay
to protect against. The superseded draft argued for caller-supplied keys on four writing calls and
the cold read found that not one of them could ever consult it, because every path refused or no-oped
before `write_atomic`. Here the guard is not unreachable — it is unnecessary.

**The call's name is in the key because without it the two calls collide, and the cold read caught
it.** The draft derived the key from "the word and the sorted target keys" — which are *identical*
for `attach_label("part", refs)` and `detach_label("part", refs)`. `Storage.replay(key)` returns the
original receipt and skips execution, so a detach following an attach on the same targets would have
been swallowed as a replay of the attach and written nothing, silently. `terms.py` already carries
the fix as a pattern — `key("retire_term", word, current.id)`, `key("approve_term", word, ...)` — the
act is always part of the key. **This is the one finding in the packet that produces wrong data
rather than a loud failure.**

**A second replay hazard follows from it and is why the key must also carry the resolved live set.**
Attach → detach → re-attach on the same targets re-derives the first attach's key. Include the
current live-attachment keys in the derivation, so the third call is a different act from the first.

**Behaviour 8 is the control level, in the schema.** Attaching is the act §1 leaves free; a required
reason on it would be friction on the one thing the design says is frictionless.

**Behaviour 9 returns state rather than delta** because a no-op has no delta, and a caller handed an
empty tuple could not tell "already attached" from "nothing happened".

**A sequencing consequence that bites now and stops at change 5.** `task_id` references `tasks`, and
until change 5 moves task creation to stage 8, tasks are derived at finalization — so a task can only
be labelled on a finalized plan. That is awkward for this change's end-to-end drive and it is not a
defect; it is the constraint change 3 recorded for function entries. Plan-row targets are unaffected.

### Task 4D.3 — `labels` and the `read_rows` filter

**Signature.** `labels(self, word: str | None = None) -> LabelReport`; `RowSelector` gains
`labels: tuple[str, ...] = ()` and `RowService.read_rows` honours it.

**Behaviours**

| | behaviour |
|---|---|
| 1 | `labels()` returns every word with at least one live attachment, alphabetically, with its definition and its count split into rows and tasks. |
| 2 | The report carries **two** denominators — never their sum — and each counts the same population its numerator does: **live lineages** (rows with no successor) and live tasks. |
| 3 | It carries the number of live terms with no live attachment as a count, not a list. |
| 4 | `labels(word)` returns that word, its counts, and every target carrying it; a plan row as its name and ref, a task as its id and title. |
| 5 | A word with no live attachment, named explicitly, reports a zero count — not missing. |
| 6 | No threshold, no warning, no gap. |
| 7 | `read_rows` with one or more labels returns live plan rows whose **lineage root** carries a live attachment for **every** word given — AND, never OR. |
| 8 | It composes with every other selector dimension by intersection, and returns a row once however many attachments it has. |
| 9 | `total` counts the filtered set; `limit` and `offset` apply after the filter. |
| 10 | An empty `labels` is not a filter: the page is unfiltered, not empty. |
| 10a | A word nothing carries makes the whole result empty, however many of the others match. |
| 10b | Duplicate words in the request are collapsed before the query, and each is normalised — stripped and lowercased. |
| 10c | A bare `str` passed as `labels` is **refused**, naming the tuple form. |
| 11 | **`RowPage` gains `labels: dict[RowRef, tuple[str, ...]]`**, keyed by the ref of each row in the page, holding that row's live labels alphabetically — populated whether or not a label filter was used. |
| 12 | The labels for a whole page are fetched in **one** query keyed on the page's lineage roots, never one query per row. |
| 13 | A row with no labels appears in the mapping with an empty tuple, rather than being absent from it. |

**Behaviour 11 answers the question the owner asked on 2026-07-30 — can a reference carry more than
one label — and it is the read this change had specified an index for and no caller.** A reference
carries as many labels as are attached to it: the live index is unique on *(word, target)*, so a
second word on the same target is a different key and is permitted, and only the same word twice on
one target is refused. There is no cap, and there is deliberately no warning above some number,
because a rule saying five is fine and six is not is a threshold (behaviour 6).

**The defect this behaviour repairs, stated plainly because it is this project's own recurring
shape.** 4A.1 creates `idx_label_attachments_target` and its DDL comment says it exists *"when a row
is rendered with the labels it carries"* — and no task performed that read. `labels(word)` runs
word → targets. Nothing ran target → words. So a row could carry six labels and the only way to
discover them was to call `labels()` once per word in the glossary, while the index built for exactly
that read sat with no consumer. An index with no reader and a read with no index are the same defect
seen from two sides, and this change had one of each.

**Behaviour 11 puts the labels on the page and not on `PlanRow`, and that is a modelling decision
rather than a convenience.** A `labels` field on `PlanRow` is the obvious shape and it is wrong twice.

*It misstates what a label is attached to.* A `PlanRow` is **one version** of a row; a label is
attached to the row's **lineage root**, so every version shares one set. A field on the version says
labels are a property of that version, which is the thing `target_root` was chosen to avoid — the
whole reason attachments key on the root is so a label neither re-surfaces nor silently detaches when
a row is superseded.

*And it would make an empty tuple mean two different things.* `PlanRow` is hydrated on many paths;
only this one would populate the field. A row fetched anywhere else would carry `()` and be
indistinguishable from a row that genuinely has no labels — a value that is only true where something
refreshed it, which is the defect F50 already cost this build once, when `plan_status` nagged about a
term that had just been settled. On the page, the mapping's presence *is* the statement that
somebody looked.

**Behaviour 13 closes the same hole from the other side.** If unlabelled rows were simply absent from
the mapping, a caller could not tell "this row has no labels" from "this page did not fetch them",
and would write `labels.get(ref, ())` — restoring the ambiguity the mapping exists to remove.

**Behaviour 12 promised what its only primitive forbade, and it is fixed the same way.** A label
lookup per row is a few hundred queries to render one page — but "the page's lineage roots" cannot be
had without one `lineage_root` walk per row *before* the single query runs, so the draft's own
mechanism defeated its own promise. The fix is the mirror of behaviour 7's: one recursive CTE walking
`supersedes` **backward** from the page's refs, joined to the attachments in the same statement.
Probed at SQLite 3.49.1, on a page mixing a thrice-superseded row with two never-superseded ones:

```sql
WITH RECURSIVE walk(ref, cur) AS (
    SELECT value, value FROM json_each(?)          -- the page's refs
    UNION ALL
    SELECT w.ref, p.supersedes
      FROM walk w
      JOIN plan_rows p ON p.table_name || ':' || p.ordinal = w.cur
     WHERE p.supersedes IS NOT NULL
)
SELECT w.ref, la.word FROM walk w
  JOIN plan_rows p ON p.table_name || ':' || p.ordinal = w.cur
  JOIN label_attachments la ON la.target_root = w.cur AND la.detached_at IS NULL
 WHERE p.supersedes IS NULL
 ORDER BY w.ref, la.word
```

It returned each row's labels correctly, including for the superseded lineage whose attachment sits
on a root three versions back. `ORDER BY … la.word` is where behaviour 11's alphabetical ordering
actually comes from, rather than being left to the grouping.

**Behaviour 13 matters because the alternative is silent.** A null would make every consumer test for
it before iterating, and the one that forgets fails on precisely the rows that carry no labels — which
is most of them early in a plan, and none of them in the fixture somebody writes to test labelling.

**Behaviour 2 is the half a builder drops**, because a count reads as complete on its own. It is not:
a label on all 687 rows and a label on one are both useless for filtering, and only the denominator
tells them apart.

**And the cold read found the two halves counting different populations, which would have made the
ratio quietly wrong.** The numerator counts live *attachments*, which key on lineage roots; the draft's
denominator was "live plan rows". Those two sets coincide only for lineages that have never been
superseded — so on a plan with any revision history the fraction compares labelled roots against live
rows and drifts. Both sides now count live lineages: one row per lineage, the one with no successor.
That is also the population a person means by "how much of the plan carries this label".

**Behaviour 5 keeps a word findable.** Reporting it as missing would tell the planner the word is
free, which is the moment they define it again — and `define_term` would refuse it as a duplicate, so
the report would have walked them into a refusal.

**Behaviour 6 is the standing ruling restated where it would be broken.** A count of one and a count
of everything are both interesting, and any rule saying *which* is bad is a threshold — a judgment
written as arithmetic so review cannot see it.

**Behaviour 7's join had no mechanism, and this is the deepest thing the cold read found.** The draft
said "collect the qualifying roots, then filter rows whose root is in that set" — but there is no way
to express *a row's root* in the single `WHERE` clause `read_rows` builds. The only root primitive in
the engine is `RowService.lineage_root`, a **Python loop issuing one query per supersession hop**. So
a builder had three options and the draft chose none: a recursive CTE, which the draft never
mentions; matching roots against refs directly, which is correct only for rows that have never been
superseded and silently drops exactly the lineages root-keying exists to preserve; or resolving in
Python, which breaks behaviour 9, since `total` and paging both ride in SQL.

**The fix walks the chain the other way, and it was probed.** Rather than resolving every candidate
row *back* to its root, resolve the small attached set *forward* to its live heads — the CTE above.
Probed at SQLite 3.49.1 on 2026-07-30 against a lineage superseded twice, labelled at its root:

| request | live rows returned |
|---|---|
| `('engine',)` where `requirements:1` (root, now `requirements:9`) and `requirements:2` carry it | `requirements:2`, `requirements:9` |
| `('engine', 'schema')` where only the first lineage carries both | `requirements:9` |

So a label attached before three supersessions still finds the live row, the AND still holds, and the
result is a plain set of refs that composes with every other selector dimension and leaves `total`,
`limit` and `offset` in SQL where behaviour 9 needs them.

**One placeholder style, not two.** The draft's SQL mixed `?` and `:n` in one statement. Probed: it
runs today with a `DeprecationWarning` and becomes a `ProgrammingError` in Python 3.14 — and every
`Storage.query` call in the engine passes a tuple. The count binds as a trailing `?`.

**The AND is the owner's decision of 2026-07-30, taken against my recommendation, and it is stated
here so nobody re-argues it.** I proposed one label only, on the ground that a second with an AND is
the start of a filter language. He asked for it *"for completeness"*. The form is one query, and the
`HAVING` is the whole of it:

```sql
WITH RECURSIVE attached(root) AS (
    SELECT target_root FROM label_attachments
     WHERE word IN (?, ?, …) AND detached_at IS NULL AND target_root IS NOT NULL
     GROUP BY target_root
    HAVING COUNT(DISTINCT word) = ?
),
chain(root, ref) AS (
    SELECT root, root FROM attached
    UNION ALL
    SELECT c.root, p.superseded_by
      FROM chain c
      JOIN plan_rows p ON p.table_name || ':' || p.ordinal = c.ref
     WHERE p.superseded_by IS NOT NULL
)
SELECT DISTINCT ref FROM chain
 WHERE ref IN (SELECT table_name || ':' || ordinal FROM plan_rows WHERE superseded_by IS NULL)
```

**`COUNT(DISTINCT word)` and not `COUNT(*)`, and this was probed rather than reasoned.** The live
unique index is supposed to guarantee one live attachment per word per target, which would make the
two forms equivalent — but this change already measured that the *natural* spelling of that index
enforces nothing whatsoever, because every row has exactly one NULL among the target columns and SQL
compares NULLs as distinct. So the duplicate the two forms disagree about is reachable in exactly the
case the index was got wrong.

Probed at SQLite 3.49.1 on 2026-07-30, against a fixture holding a row with `engine` only, a row with
`schema` only, a row with both, and a row with all three:

| query for `('engine', 'schema')` | returns |
|---|---|
| `COUNT(DISTINCT word)` | the both-row and the all-three row — **correct** |
| `COUNT(*)`, after one duplicate `engine` row is inserted on the engine-only row | the engine-only row as well — **a row that carries neither `schema` nor two labels** |

`DISTINCT` makes the filter correct independently of the constraint, which is what a query should be
when the constraint protecting it has already been observed to fail. The same run confirmed that
detaching one of two labels drops the row from the result, and that a typo'd word returns nothing.

**Behaviour 10b is not tidying either.** `labels=("engine", "engine")` sets `:n` to two while the
`HAVING` can only ever reach one, so the query returns nothing at all — a filter that silently
matches zero rows because the caller repeated a word. Deduplicating after normalising also means
`("Engine", "engine")` collapses rather than guaranteeing an empty page.

**Behaviour 10c is the same class of trap as `isinstance(True, int)` in 4D.1**, and it is worse
because it fails quietly. A bare `str` **is** a sequence of `str`, so `labels="engine"` iterates to
`'e', 'n', 'g', 'i', 'n', 'e'` — **four** distinct single characters after dedupe, measured rather
than counted by eye, none of which is a term, so the page comes back empty and correct-looking. The
selector refuses a bare `str` outright.
The payload parser is the one place allowed to be generous: a JSON `"labels": "engine"` is coerced to
a one-element tuple there, so the friendliness lives at the edge and the model stays strict.

**Behaviour 10a is a consequence worth stating because it will look like a bug.** Asking for `engine`
and `schemer` when the second is a typo returns nothing, not the `engine` rows. That is what AND
means, and it is why 10c and 10b matter: two of the three ways to get an empty page from this filter
are input mistakes, and only the third is a real answer.

**Behaviours 8 and 9 are stated because they are where this kind of filter fails silently.** A join
against a one-to-many table duplicates rows; `total` computed before the filter reports a page count
for a different query; `limit` applied before the filter returns short pages that look like the end
of the results.

### Task 4D.4 — the surface

**Signature.** `engine/surface.py`, plus payload parsing and rendering.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Removed: `approve_term`, `retire_term`, `export_glossary` — from the registry **and** from `ADDED`. |
| 2 | Added: `remove_term`, `attach_label`, `detach_label`, `labels` — to the registry **and** to `ADDED`, each with the reason it exists. |
| 3 | `define_term` and `redefine_term` keep their registry rows; `define_term` loses its `names_ref` parameter. |
| 4 | **`labels` is a field of the `selector` payload, not a top-level `read_rows` parameter**, and `as_selector`'s whitelist gains `"labels"` and constructs it. |
| 4a | The rendered form of a page shows each row's labels, and `contracts:10` — the contract `RowPage` answers to — is amended to say the page carries them. |
| 4b | The labels mapping is rendered with a **name beside every address**, never as a dict keyed on a bare `table:ordinal`. |
| 4c | `redefine_term` **also** loses its `names_ref` parameter. |
| 4d | The surviving glossary tools' summaries are rewritten: `define_term`'s "the owner settles it", `redefine_term`'s "keeping the old wording as history. Also how a retired word comes back", `glossary`'s "retired ones included", and `define_term`'s `ADDED` reason. |
| 4e | `Surface.__init__` constructs `LabelService` and the registry rows name the attribute it is bound to. |
| 4f | A payload decoder for a **mixed** sequence of refs and task ids is registered, since `DECODERS` today has `refs` and `ints` and nothing that accepts both. |
| 4g | The `Surface` attribute holding `LabelService` is **`label_service`**, not `labels`. |
| 4h | `read_rows` refuses a `limit` above a stated ceiling, because both new queries bind one parameter per element. |

**Behaviour 4g avoids a collision this change was walking into.** Four things would otherwise be
called `labels`: the tool, the `RowSelector` field, the `RowPage` field, and the service method — plus
the `Surface` attribute the registry's `service` column resolves to, which would be a fifth. The three
data fields are fine, because each is qualified by what holds it. The service attribute is the one
that would sit beside the tool name in dispatch, and `surface.py` already records the precedent
against exactly that: *"`renderer`, not `render`: the door's `render` is a module-level function used
a few lines below in `dispatch`, and two things called the same word in one class is exactly the
collision this build keeps writing down."*

**Behaviour 4h is a small ceiling on an unbounded thing.** `read_rows` validates only that `limit` is
positive. Both recursive CTEs bind one parameter per page ref or per requested word, so a caller
asking for fifty thousand rows builds a fifty-thousand-parameter statement. SQLite's default limit is
well above a sensible page and well below that, so the failure would be a driver error rather than a
refusal naming the field.

**Behaviour 4 is a correction, and as drafted the filter could not have run.** The `read_rows`
registry row takes exactly one parameter, `selector`, and dispatch calls
`getattr(service, method)(**args)` against `read_rows(self, selector: RowSelector)`. A top-level
`labels` parameter produces `read_rows(selector=…, labels=[…])` → `TypeError`, caught by the blanket
handler and reported as a `"partial"` failure — the tool blaming the caller for the spec's mistake.
And `as_selector` whitelists its keys explicitly, refusing anything else with *"a selector; it has no
field 'labels'"*, so both halves must change together.

**Behaviour 4c is the same omission one row over.** The draft said `define_term` loses `names_ref`
and said nothing about `redefine_term`, whose registry row carries one too. Left as drafted, `_bind`
decodes it and passes it to a method that no longer accepts it.

**Behaviour 4e is a hole that would have made all four new tools fail.** Dispatch resolves a tool by
`getattr(getattr(self, tool.service), tool.method)`. No task in the draft constructed `LabelService`,
named its attribute, or said which module it lives in.

**And the arithmetic paragraph below carried a wrong count, which is worth recording rather than
quietly fixing.** It said `EXCLUDED` and `DEFERRED` are both empty. `DEFERRED` is; **`EXCLUDED` holds
three** — `renew_lease`, `release_writer_lock`, `acquire_writer_lock`, the writer-lock tools, and
`surface.py`'s own docstring says so in prose. The script I measured with matched `Absence(`
followed by a bare identifier, and those three begin with a quoted contract address, so they counted
as zero. **A method that is 95% written produces a number that looks checkable and is not** — the
same lesson §14 was written to enforce, failing inside the change that wrote it.
| 5 | The registry rows land **before** any refusal whose text names the call. |
| 6 | Payload parsing for the label calls is registered once, under one name. |

**The arithmetic, measured from `engine/surface.py` on 2026-07-30 and stated as a method rather than
a number.** Today: **54** registrations via `_t(`, and **12** `ADDED` entries. Six glossary tools are
registered and all six are in `ADDED`, because the frozen plan never asked what the words mean, so
each carries `DEVIATION`. This change removes three and adds four, giving **55** and **13** — *against
today's code*. Changes 1, 2 and 3 all touch this file and none of them is built, so **re-run the
count at build time**; the number to trust is the one measured against what those changes actually
left. `DEFERRED` is empty; **`EXCLUDED` holds three** (the writer-lock tools). Neither is touched.

**Behaviour 1 must remove the `ADDED` entries too, or the suite fails.** A test asserts that every
tool carrying `DEVIATION` appears in `ADDED`; the register is the reverse direction, so a stale
`ADDED` entry for a tool that no longer exists is the mirror defect and is caught by the same test's
partner. This is the same class as 4A.0 behaviour 2: a declaration outliving the thing declared.

**Behaviour 6 is the collision the cold read found across changes 3 and 4** — two payload parsers
registered under one name. Change 3 registers a parser; this change must not register a second under
the same key.

## 12. Packet 4E — the methodology

Revision 6. Lands after the registry rows its script names.

### Task 4E.1 — the labelling round

**Behaviours**

| | behaviour |
|---|---|
| 1 | `engine/methodology/rev6/` is created from rev5, with a labelling round added as a **new stage**, not bolted onto an existing one. |
| 1a | **`manifest.yaml`'s `revision:` becomes 6 and `revision_stamp` is changed.** |
| 1b | The new stage declares all five fields `Package` requires — `number`, `name`, `mode`, `script`, `tables` — and the stage list and `package_range` grow to match. |
| 1c | `gate_criteria.yaml` gains entries for the new stage, or records that it deliberately has none. |
| 1d | `DEFAULT_REVISION` in `engine/methodology/__init__.py` becomes 6. |
| 2 | The round says in as many words that **a label is a glossary term**, and that `define_term` is how you mint one. |
| 3 | `approve_term` is removed from `mandate.md` and `gap_rules.yaml`. |
| 4 | Residual packaging-round prose is deleted. |
| 5 | The stage script renders without raising, **under whatever name change 1 leaves that call** — see below. |
| 6 | A plan sitting on rev5 is either owed a rev5→rev6 migration or explicitly is not, with the reason recorded. |

**Behaviour 1a is the failure this project has already had, and the draft was walking straight back
into it.** `load()` reads `revision` and `revision_stamp` out of `manifest.yaml`, and rev6 is a
**copy** of rev5. The manifest's own comment is the record: *"It identified itself as rev 2 until
2026-07-22 — revision and stamp both copied along with the content they exist to distinguish, so
every caller asking which methodology was in force got the wrong answer (F31). Change the stamp
whenever the content changes."* The draft cited the sibling of that failure — rev2's `stage` keying
surviving two revisions — as its reason for behaviour 4, and then repeated the original.

**Behaviour 1d is the difference between an asset and a used asset.** `DEFAULT_REVISION` and
`EARLIEST_LOADABLE_REVISION` are both 3 today and no packet touched them; rev6 would have been a
directory nothing loads.

**Behaviour 1's "new stage" resolves a collision the draft did not see.** It called this "a stage-6
labelling round" — and in the manifest, number 6 is **Architecture**. Either the labelling round is a
new stage with its own number and the list grows, or it is bolted onto architecture, which is a
different thing. Nothing in the draft chose, and none of the five fields a stage needs was given.

**Behaviour 5 is stated conditionally on purpose.** The draft named `get_stage_script(6)`; the call
in the code today is `get_package_script`, and the loader exposes `package(number)`. The rename to
`stage` belongs to change 1, which is not built. Naming the post-change-1 call here and being wrong
is how a stage script comes to name a call the door cannot resolve — a failure this loop has already
caught twice.

**Behaviour 2 is not decoration.** A planner who has read D12 will look for a `propose_label`, find
nothing, and either invent a call or skip the round. The script is the only place that gap gets
closed.

**Behaviour 3 is the same failure as 4C.3 behaviour 5, one layer up.** `mandate.md` and
`gap_rules.yaml` instruct the planner to use a call that will no longer exist; an instruction to make
a call that raises `UnknownTool` is worse than no instruction, because it costs a round trip and
reads as the planner's mistake.

**Behaviour 4 is a catch, not the fix.** Change 1's 1E.1 behaviour 5 deletes the packaging round at
source. This catches anything that reached rev6 by copy — which is how rev2's `stage` keying survived
two revisions.

## 13. Packet 4F — the tests

Last. Asserts what the packets above did.

### Task 4F.1 — the schema and migration tests

**Behaviours**

| | behaviour |
|---|---|
| 1 | The 10→11 migration drops the six columns and keeps every live word and definition. |
| 2 | A plan holding a redefined word — several rows, one live — migrates to exactly one row. |
| 3 | Migration parity: a migrated v11 and a fresh v11 are byte-identical across all four pragmas. |
| 4 | The duplicate-attachment refusal is asserted **at the store, in raw SQL**. |
| 5 | Both `COALESCE` sentinels are unreachable **at `label_attachments`**: an attachment with `task_id = 0`, and one with `target_root = ''`, are each refused by their `CHECK`. |
| 6 | `label_attachments` **is** in the snapshot table set, and a restore round-trip preserves attachments. |
| 7 | The `ALTER` route's order dependencies fail loudly if reversed: dropping `superseded_at` before `idx_terms_live`, and filtering live rows after the drop. |
| 8 | `sqlite_sequence` survives the migration — a term inserted afterwards gets an id above the pre-migration maximum. |
| 9 | A migration failure rolls back to the full eleven-column table with every row intact. |
| 10 | **`COUNT(*)` is caught here, not in 4F.2**: a duplicate live attachment inserted in raw SQL makes the AND filter return a row carrying only one of two requested labels, unless the query uses `COUNT(DISTINCT word)`. |

**Behaviour 5 is corrected, and the draft's version asserted something this change does not do.** It
said `INSERT INTO tasks (id) VALUES (0)` is "refused" — but nothing here touches the `tasks` table,
and the DDL comment says the opposite, that such a row *is* accepted. Written literally the test
fails, and the tempting repair is to add a constraint to `tasks`, which is out of scope and would be
a schema change nobody specified. What this change constrains is `label_attachments`, and that is
what the test asserts.

**Behaviour 10 moved down from 4F.2, because there it could not fail.** The claim was that a fixture
of three rows — one `engine`, one `schema`, one both — fails if the query is written as `COUNT(*)`.
It does not: the two spellings diverge only when a *duplicate live attachment* exists, and
`attach_label` treats a duplicate as a no-op, so no service-driven fixture can create one. Against
that fixture both spellings return the same rows. The test catches OR and nothing else. To catch
`COUNT(*)` the duplicate must be inserted in raw SQL — which makes it a store-level test, alongside
behaviour 4, for exactly the reason behaviour 4 already gives.

**Behaviour 6 follows 4A.2's reversal** — the table is in the snapshot set now — and the round trip is
what proves it, since the list itself is a tuple in `storage.py` that no test reads.

**Behaviour 3's parity check is inert for `label_attachments` and load-bearing only for `terms`.**
Both the fresh path and the migration build the attachment table from `schema.LABELS_DDL`, so
comparing them proves that one constant executed twice gives the same answer. A defect shared by both
paths — a missing `CHECK`, a wrong index — is invisible to it. `terms` is where parity earns its
keep, because there the migration reaches the shape by a different route than a fresh install does.

**Behaviour 4 is the one that cannot be written through the service and is the reason this task
exists.** `attach_label` treats a duplicate as a no-op, so a service-driven test passes against a
completely inert index — and the natural index form *is* completely inert, probed at SQLite 3.49.1:
every row has exactly one NULL among the target columns and SQL compares NULLs as distinct. A test
that drives the service proves nothing about the constraint.

**Behaviour 2 is the migration's sharpest edge** (4A.2 behaviour 3) and it needs a fixture that has
actually been redefined, not a fresh one.

**Behaviour 6's second half is a specific predicted mistake.** A new table with no `updated_at` looks
like a junction, and `label_attachments` is not one — it has independent existence and its own
lifecycle stamp.

### Task 4F.2 — the service tests

**Behaviours**

| | behaviour |
|---|---|
| 1 | `attach_label` refuses a word no live term holds, and the message names `define_term`. |
| 2 | A repeat attach is a no-op returning the same attachments; duplicate targets in one call collapse. |
| 3 | `attach_label(word, (True,))` does **not** attach to task 1. |
| 4 | `remove_term` refuses while attachments exist, and the message carries both counts. |
| 5 | The replacement move collapses a duplicate rather than raising, and leaves detached rows pointing at the dead word. |
| 6 | `detach_all=True` removes the word and leaves every attachment detached. |
| 7 | `replacement` and `detach_all` together are refused. |
| 8 | `read_rows` on one label returns each row once, `total` matches the filtered set, and paging is correct across a boundary. |
| 9 | An unknown word returns an empty page rather than raising. |
| 9a | **The AND is exclusive.** A fixture with a row carrying `engine` alone, one carrying `schema` alone, and one carrying both returns **only the third** for `("engine", "schema")` — the test that fails if the query is ever written as OR or as `COUNT(*)`. |
| 9b | Asking for a real label and a typo returns nothing, not the real label's rows. |
| 9c | `labels=("engine", "engine")` returns the same rows as `("engine",)`, not an empty page. |
| 9d | `labels="engine"` is refused, and the message names the tuple form. |
| 10 | A row carrying three labels comes back from `read_rows` with all three, alphabetically, and a row carrying none appears in the mapping with an empty tuple. |
| 11 | Reading a page of N labelled rows issues **one** label query, asserted by counting statements, not a number obtained by running the code once. |
| 12 | A label attached before a row was superseded is still reported against the live version, and `read_rows(labels=…)` still finds that row. |
| 13 | `labels=()` is **not** a filter: the page comes back unfiltered rather than empty. |
| 14 | `("Engine", "engine")` collapses to one word; `attach_label(" Engine ")` matches the term `engine`. |
| 15 | A row carrying a **superset** of the requested labels is returned. |
| 16 | `read_rows(labels=…)` composes with `table=` and with paging, and a row with two matching attachments is returned once. |
| 17 | `labels()` — alphabetical order from an out-of-order fixture; both denominators present and **different from each other**; the unattached-term count; a named word with no attachment reporting zero rather than missing. |
| 18 | `detach_label` — an unattached target is a no-op; detaching stamps rather than deletes; attach → detach → re-attach leaves the label attached. |
| 19 | `define_term`/`redefine_term` — a redefine leaves **one** row with the same `id` and `created_at` and a changed `updated_at`. |
| 20 | Every count and emptiness assertion in this task carries a **positive control** — a fixture the assertion demonstrably fails against. |

**Behaviour 11 is restated because "a fixed number" and "one" are different claims**, and the draft's
test asserted the weaker one against the specification's stronger one. A two-query implementation
satisfies "fixed" while violating 4D.3 behaviour 12. And a count captured by running the code once is
a change-detector, not a check.

**Behaviour 17 exists because the draft tested `labels()` not at all.** A whole new tool with a new
report type had no test — including the two denominators, which the specification itself calls "the
half a builder drops", and the zero-rather-than-missing rule, which exists to stop a planner being
walked into a `define_term` refusal.

**Behaviour 20 is the register gap made concrete.** This repository's own idiom is
`test_the_check_can_actually_fail`, and the standing evidence is a check that ran green while seeing
four names where there were twenty-two. The draft's filter tests asserted emptiness three times —
unknown word, typo, and the implied negatives — all of which a filter returning nothing for every
input satisfies. Three of the draft's assertions could not fail: the both-labels fixture had no
duplicate to catch `COUNT(*)`, the "returned once" case filtered on a single label so no row could
duplicate, and the two-count refusal had no fixture where the two counts differed, so a summed count
would have passed the rule that exists to forbid summing.

**Behaviour 3 is a one-line test for a defect that is invisible until a caller passes a flag.**

**Behaviour 8 needs more rows than one page** or it asserts nothing about the failure it exists for.

### Task 4F.3 — the deletions

**Behaviours**

| | behaviour |
|---|---|
| 1 | `tests/test_vocabulary.py` is already gone — change 1 deleted it (§4.1). Nothing here re-deletes it. |
| 2 | `tests/test_terms.py` holds **41** tests today. Six survive; the rest are deleted or rewritten, and this task enumerates them rather than naming categories. |
| 3 | `tests/test_schema_vocabulary.py` gains 4A.0's two `TIMESTAMP_ROLES` edits **and** behaviour 3a's reverse check; the `junctions` set is hoisted to module scope so it can be asserted against. |
| 4 | `tests/conftest.py` loses every `terms=` fixture argument for the five services that drop the parameter. |
| 5 | The stage script for the new round renders without raising. |
| 6 | The second file asserting `glossary.json` was written is **`tests/test_surface.py`** — two tests, one dispatching `export_glossary` and asserting the filename appears in the summary and the file exists on disk, the other reading it back. Both go. |
| 7 | Two tests that survive the change but can no longer fail are deleted: `test_a_clean_row_carries_no_note` and `test_the_question_stops_once_any_word_is_defined`. |
| 8 | Packet 4C's deletions are asserted positively, not by the absence of tests. |

**Behaviour 2 replaces four categories that reached 16 of 41 tests.** The draft said "approval, bans,
supersession and export", and behaviour 4 added warning kinds, gap rules and status lines — together
about 22. That leaves roughly **13 tests neither behaviour names**: the lexical-scan tests, the
submission-note tests, the two brief-glossary tests, `test_a_term_records_what_a_word_means` (which
asserts `is_banned`) and `test_redefining_carries_the_named_row_forward` (which asserts `names_ref`).
Most fail loudly, because the module's import line names `BOTH`, `IDENTIFIER`, `PROSE`,
`AlreadyApproved` and `BanNeedsReason` — that import is the real mechanism protecting this change and
the draft never acknowledged it.

**Behaviour 7 is the sharp one, because those two do not fail loudly.** `test_a_clean_row_carries_no_note`
asserts a verdict note is `None` — and after 4C.1 nothing can produce that note, so the setup
satisfies the assertion. `test_the_question_stops_once_any_word_is_defined` filters open gaps for
`no_glossary` and asserts the result is empty — and after 4C.3 that comprehension is empty forever.
Both call only surviving methods, so both stay green while meaning nothing. **This change would have
left two checks in the suite that run, pass, and measure nothing** — the defect the whole project is
organised against, created by the packet that deletes their subject.

**Behaviour 8 is the biggest single gap the read found.** The draft's entire coverage of packet 4C
was one line saying *no test asserts* the deleted things — a statement about the repository, not code
that executes. Nineteen behaviours across six modules, including the one the specification itself
flags as "the one a builder will want to keep and must not", had nothing that would fail if a builder
simply kept them.

## 14. What re-measuring disagreed with

**Four counts in §5 and `04-labels.md` did not survive re-derivation.** Each was correct when
written, against a design that has since changed. The method is stated so it can be re-run rather
than trusted.

| claim | measured 2026-07-30 | method |
|---|---|---|
| `TIMESTAMP_ROLES` becomes **8** | **7 → 7.** `detached_at` joins, `approved_at` leaves with the only column that used it | parse the dict in `test_schema_vocabulary.py`; grep `approved_at` across all 37 tables in `engine/schema.py` |
| `JUSTIFICATION_ROLES` is **18 today** | **it does not exist in the code.** It appears only in the specs for changes 2, 3 and 4, none of which is built | grep the repository |
| `LABELS_DDL` yields **four** statements | **three**, then **four again** — and the round trip is the point. `term_comparisons` went with the guard, taking it to three; the cold read then found the task-side read had no index, and adding it brings it back to four. Same number, different four | count `CREATE` in the block; re-probe through `schema.statements`, because the split survives only on comments being stripped |
| the change *"removes three tools and adds three"* | **removes 3, adds 4.** `remove_term` is a new registration, not a rename of `retire_term`: different signature, different act | `_t(` and `Absence(` in `engine/surface.py` — 54 and 12 today |

**A fifth, found by the cold read rather than by me:** the arithmetic paragraph in §11 said
`EXCLUDED` and `DEFERRED` are both empty. `DEFERRED` is; **`EXCLUDED` holds three**. My script
matched `Absence(` followed by a bare identifier and those three entries begin with a quoted contract
address, so it reported zero and I published it. The lesson §14 exists to enforce — write the method,
then re-run it and confirm it returns the number in the document — failed on its own page, because I
never checked the method against a number I could see by eye.

**And one that held.** `SCHEMA_VERSION` is **7** in the code; changes 1–3 take it to 10, so this
change's 10 → 11 is right — but 10 is a number to verify at build time and not to assume, for the
same reason as every other number here.

---

## 15. The cold read — what it found, and what was done

**Run 2026-07-30 against §7–§14 as first written.** Four readers, one per packet group — 4A, 4B+4C,
4D, 4E+4F — each given a bundle and told to open nothing else. **All four reported exactly one file
opened.** Every finding below was checked against the source before it was acted on; the ones marked
*probed* were settled by experiment rather than argument. §7–§14 above are the corrected text. This
section is the record of what they were before, and is evidence, not specification.

### 15.1 A change of method, and why

Previous reads pasted the whole bundle inline and forbade every tool, because the reader shares a
filesystem with the build documents. That control held for three changes and **produced four bad
bundles in four changes**, every one of them from abridging something to make it fit — the last run
alone returned two false findings, one because the conventions register was trimmed and one because a
packet the reader depended on was left out.

So the bundles were staged as four files, each carrying every relevant source file **whole**:
`terms.py`, `rows.py`, `gates.py`, `gaps.py`, `resume.py`, `briefs.py`, `warnings.py`, `models.py`,
`surface.py`, `schema.py`, `storage.py`, the tests, the methodology assets and the full register. The
largest was 4,279 lines. Each reader opened exactly one path and reported it.

**The blindness that matters is sharper this way, not weaker.** What a reader must not see is the
build document, where the conclusions already are — a reader that wandered into §14 would have handed
back the four counts I had already caught, as fresh findings. What it *should* see is ground truth.
The staged directory held the specification and the source and nothing else. **This is the method to
use from now on**, and the tell that it worked is that no reader reported a finding that turned out
to be an artefact of a missing file — the first run of four with none.

### 15.2 Four defects that each stopped the change dead

None of these is a matter of degree; each one alone means the change does not work.

- **Nothing appended the new table to the schema.** `schema.py` builds its DDL by explicit
  `DDL += …`, four times over. The draft said the table "is created". Every new plan would have come
  up without it.
- **Nothing bumped `SCHEMA_VERSION`.** A v11 store would call itself v10 and never select the
  migration branch.
- **Rewriting `TERMS_DDL` rewrote history.** The 3→4 migration branch reuses that same constant, on
  purpose and with a comment saying so. Any store climbing from 3 would have been handed the new
  five-column table and then asked for `superseded_at` in the 10→11 step — failing inside the one
  migration that destroys data.
- **`remove_term` deleted a row through a store with no delete.** `Storage`'s op vocabulary is
  `insert`, `update`, `insert_row`. Resolved by 4B.3 behaviour 10, narrowly.

### 15.3 The deepest one: a join with no mechanism

`read_rows(labels=…)` has to match live rows against attachments keyed on lineage roots, and the
draft said "collect the qualifying roots, then filter rows whose root is in that set" — which cannot
be written in the single `WHERE` clause `read_rows` builds. The only root primitive in the engine is
a Python loop doing one query per supersession hop. Every route a builder could have taken was wrong:
matching roots to refs directly drops exactly the superseded lineages root-keying exists to preserve;
resolving in Python breaks `total` and paging. The same wall stood behind the promise of one label
query per page, which needs the page's roots *before* the query runs.

Fixed with two recursive CTEs, both probed: forward along `superseded_by` from the attached roots to
their live heads for the filter, backward along `supersedes` from a page of refs for the read.

### 15.4 Probes that refuted what was written down

| claim | outcome |
|---|---|
| dropping six columns "is a table rebuild in SQLite, not a sequence of `ALTER`s" | **refuted.** `ALTER TABLE … DROP COLUMN` works at 3.49.1, inside `BEGIN IMMEDIATE`, with `sqlite_sequence` preserved and rollback clean. The rebuild — and the second copy of `CREATE TABLE terms` it would have forced into `storage.py`, against `schema.py`'s explicit prohibition — is gone |
| `INSERT INTO tasks (id) VALUES (0)` "is accepted despite AUTOINCREMENT" | **refuted as written** — `tasks` has four `NOT NULL` columns and the statement fails on the first. Re-probed properly: with them supplied, **task id 0 is reachable**, so the `CHECK` still earns its place. Inherited from the superseded document and never re-run |
| the AND filter's SQL | **would not have run** — it mixed `?` and `:n` placeholders in one statement. Deprecated today, a hard error in Python 3.14 |
| the both-labels fixture "fails if the query is written as `COUNT(*)`" | **refuted.** The two spellings diverge only when a duplicate live attachment exists, and `attach_label` no-ops duplicates, so no service-driven fixture can make one. Moved to a raw-SQL test |
| the order of the migration's steps | **confirmed as load-bearing.** Dropping `superseded_at` before its index fails; filtering live rows after the drop fails. Both would have failed inside the data-losing step |

### 15.5 The shapes that recurred, again

- **A landing-order inversion.** `remove_term` needed the label service and landed before it. **Four
  changes, four inversions** — change 3 had three at once. This is now a pre-write check.
- **A citation to nothing.** `approved_at` would have stayed in the timestamp register after its only
  column died, and the register's check is blind in that direction — it validates columns against
  roles, never roles against columns. The reverse check is now specified. The `word` foreign-key
  comment was the same defect inside the same task, arguing from a redefinition behaviour this change
  deletes.
- **A count nobody enumerated.** Five this time, one of them mine after §14 was written to prevent it.
- **A check that cannot fail.** Two live ones would have been left in the suite by the packet that
  deletes their subject, both passing because their setup satisfies them.
- **A denominator that is not a denominator.** The label counts count attachments on lineage roots
  against a denominator of live rows — two populations that coincide only for lineages never
  superseded.

### 15.6 What the readers found that nothing else would have

The test packet was the worst result of the four: roughly **sixty of ninety-nine behaviours** across
the change had no test that would fail if a builder skipped them. `labels()` had none at all;
`detach_label` had none; the tool surface was never exercised; and packet 4C's entire coverage was one
sentence asserting that no test exists — a claim about the repository rather than code that runs.
That is not a thing a specification's author can see, because the author knows what the code is
supposed to do and reads the intent rather than the assertion.
