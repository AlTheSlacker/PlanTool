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

`attach_label`, `detach_label`, `labels`, and the `RowSelector.label` filter with its join. Registry
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
| 6 | 4B, `terms.py` reduces | |
| 7 | 4D.1–4D.3, the label service and the filter | |
| 8 | 4E, the methodology | after the registry rows its script names |
| 9 | 4F, the tests | last, because it asserts the rest landed |

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
| 2 | **`approved_at` leaves `TIMESTAMP_ROLES`**, because 4A.1 removes the only column in the schema that used it. |
| 3 | The set therefore holds **seven** members before and **seven** after — not eight. |
| 4 | `JUSTIFICATION_ROLES` is unchanged at **18**: nothing this change adds carries a reason. |
| 5 | Both counts are re-enumerated from source at build time, by the method in §14, and not carried from this document. |

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
| 2 | `idx_terms_live`, a partial unique index on `term WHERE superseded_at IS NULL`, becomes a plain `UNIQUE (term)`. |
| 3 | `label_attachments` is created, with its two indexes. |
| 4 | **No `term_comparisons`.** It goes with the near-match guard. |
| 5 | `LABELS_DDL` yields exactly **three** statements through `schema.statements`, verified through that function rather than counted by eye. |
| 6 | `label_attachments.word` carries no foreign key, and the DDL comment says why. |
| 7 | Any retained per-version DDL fixture lives **outside** `engine/schema.py`. |

**The DDL, carried from `04-labels.md` with `term_comparisons` removed:**

```sql
-- A label is a glossary term attached to rows; there is no label table (§3.3). This
-- table is the attachment and nothing else.
CREATE TABLE IF NOT EXISTS label_attachments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    word        TEXT    NOT NULL,  -- the term, as the word. No REFERENCES terms (term):
                                   -- keying on terms.id would cost the design, since a
                                   -- redefinition must not detach every target. The word
                                   -- is the identity that survives redefinition.
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
-- Probed at SQLite 3.49.1: it enforces nothing at all for the whole life of the table.
CREATE UNIQUE INDEX IF NOT EXISTS idx_label_attachments_live
    ON label_attachments (word, COALESCE(target_root, ''), COALESCE(task_id, 0))
    WHERE detached_at IS NULL;

-- Read when a row is rendered with the labels it carries. The live index above leads on
-- word and cannot answer that direction.
CREATE INDEX IF NOT EXISTS idx_label_attachments_target
    ON label_attachments (target_root, detached_at);
```

**Behaviour 2 is the half of this task that a reader will take for cosmetic.** `idx_terms_live` is
partial *because* definitions were superseded rather than edited; with `superseded_at` gone the
`WHERE` clause references a column that no longer exists, so the index does not survive the column
drop in any case. Replacing it with a total `UNIQUE (term)` is what makes `word` a candidate FK
parent in principle — and behaviour 6 still declines the FK, for the reason in the comment.

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
| 2 | Rebuilds `terms`: new table, copy `id`, `term`, `definition`, `created_at`, `updated_at`, drop the old, rename, then create `UNIQUE (term)`. |
| 3 | Only **live** term rows are copied — those with `superseded_at IS NULL`. |
| 4 | Seeds no word, and backfills no attachment. |
| 5 | Adds nothing to the snapshot table set. |
| 6 | Its docstring states what the migration **discards**. |

**Behaviour 2 is the real work in this packet.** Dropping six columns and swapping a partial unique
index for a total one is a table rebuild in SQLite, not a sequence of `ALTER`s.

**Behaviour 3 is the one place this migration could silently corrupt the table, and it is a
consequence of behaviour 2 rather than a choice.** Under the old schema a redefinition wrote a new
row and stamped the old one, so a word that has ever been redefined has **several** rows and only one
live. The new `UNIQUE (term)` is total. Copy everything and the rebuild fails on the first
redefined word — or, worse, if the copy is written to tolerate it, keeps an arbitrary one. The
lineage is what §4 deletes; the live row is what survives.

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
| 6 | `WORD` and `_word` survive. |

**Behaviour 2 deletes `ADDRESS` and that is a deliberate loss.** It stripped `requirements:61`-style
addresses before tokenising, so a citation of a retired word did not read as a use of it. It existed
for `violations()` and has no second caller — measured, not assumed. It goes with the scan.

**Behaviour 5 is not tidying.** The docstring currently argues at length for the banned list, for
`ban_scope` as a queryable denominator, and for proposal-and-approval — every one of which §1 and §4
delete. Left standing it is the most persuasive document in the repository arguing for machinery that
no longer exists, sitting in the file a reader opens first. It must instead carry §2.2: the failure
is a synonym sharing no letters, no scan sees it, and the glossary's job is to be **in front of the
writer at the moment of naming**. That argument is already in the file's own v2 docstring, one
paragraph down, and has been since before any of this was built.

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
| 1 | The submission scan at `rows.py:412` — `self.terms.violations(submission.content)` — is deleted with the warnings it raised. |
| 2 | The `terms` constructor parameter, its default `TermService` construction and the `self.terms` attribute are deleted. |
| 3 | **`terms` stays a reserved plan-row table name**, and its refusal still names `define_term`. |

**Behaviour 3 is the one thing in this module that does not change**, and it is called out because
the surrounding deletions make it look like an oversight. The reservation exists so that
`submit_rows(table='terms')` is refused with an explanation rather than writing plan rows into a
namespace the real table owns. That is as true after this change as before it.

### Task 4C.2 — `gates.py`

**Behaviours**

| | behaviour |
|---|---|
| 1 | `_retired_words()` is deleted whole, and the loop over it in `run_gate`. |
| 2 | The `terms` parameter, the `TermService` default and the `Usage` import go with it. |
| 3 | The gate's remaining warning kinds and their counting are untouched. |

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
| 3 | The violations rule at `gaps.py:331` is deleted, and its entry. |
| 4 | The `terms` parameter and the `TermService` default go. |
| 5 | `gap_rules.yaml` loses the rules' declarations, so the rule table and its declaration stay in step. |

**Behaviour 5 is the failure mode this engine has already had.** A rule table and its YAML
declaration are two lists that must agree; deleting one side leaves either a declared rule with no
implementation or an implementation nothing declares, and only one of those fails loudly.

### Task 4C.4 — `resume.py`

**Behaviours**

| | behaviour |
|---|---|
| 1 | The `glossary` `Fetch` field, its construction at `resume.py:420` and its two rendered lines go. |
| 2 | `terms_awaiting_approval`, its count at `resume.py:423` and the line naming `approve_term()` go. |
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
| 1 | The retired-word warning kind is deleted from the kind table. |
| 2 | Its key-construction comment and any suppression fixture naming it go with it. |

**Its only producer was `violations()`.** A warning kind with no producer cannot fire, and a kind
table listing one is a menu item that is never cooked — the register says a kind is declared where it
is raised.

## 11. Packet 4D — labels

Depends on 4A. 4D.0 lands with 4A; 4D.4 lands before 4C.

### Task 4D.0 — the models

**Signature.** Three frozen dataclasses in `models.py`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | `Attachment` — `id: int`, `word: str`, `target_root: RowRef \| None`, `task_id: int \| None`, `detached_at: str \| None`, `created_at: str`, with an `is_live` property. |
| 2 | `LabelUsage` — the word, its definition, and its live attachment count split into rows and tasks. |
| 3 | `LabelReport` — the usages, the two denominators, the count of live terms with no attachment, and, when one word was asked for, its targets. |
| 4 | `RowPage` gains `labels: dict[RowRef, tuple[str, ...]]`, defaulting to an empty dict. |
| 5 | There is no `Candidate`, no `TermComparison`, no `LabelResult` and no `Label`. |

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

**Signature.** Three private methods on `LabelService`: `_live_term(word) -> Term`,
`_target_key(target) -> tuple[str | None, int | None]`, `_attachments(word, live_only=True) -> tuple[Attachment, ...]`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | `_live_term` returns the live `terms` row, or refuses with `TermNotFound` naming `define_term`. |
| 2 | `_target_key` returns `(lineage root, None)` for a ref and `(None, task id)` for a task id, and refuses anything else. |
| 3 | The word is normalised — stripped and lowercased — and an empty one is refused. |
| 4 | `_attachments` returns live attachments unless asked for all. |

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
| 7 | Neither call takes an idempotency key; each derives one from the word and the sorted target keys. |
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
`label: str | None = None` and `RowService.read_rows` honours it.

**Behaviours**

| | behaviour |
|---|---|
| 1 | `labels()` returns every word with at least one live attachment, alphabetically, with its definition and its count split into rows and tasks. |
| 2 | The report carries **two** denominators — live plan rows, and live tasks — never their sum. |
| 3 | It carries the number of live terms with no live attachment as a count, not a list. |
| 4 | `labels(word)` returns that word, its counts, and every target carrying it; a plan row as its name and ref, a task as its id and title. |
| 5 | A word with no live attachment, named explicitly, reports a zero count — not missing. |
| 6 | No threshold, no warning, no gap. |
| 7 | `read_rows(label=w)` returns live plan rows whose **lineage root** carries a live attachment for `w`. |
| 8 | It composes with every other selector dimension by intersection, and returns a row once however many attachments it has. |
| 9 | `total` counts the filtered set; `limit` and `offset` apply after the filter. |
| 10 | An unknown word returns an empty page with `total = 0` rather than raising. |
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

**Behaviour 12 is where this goes wrong if it is written per row.** A page is up to a few hundred
rows, and a label lookup per row is a few hundred queries to render one page — the read that made the
index worth having becomes the reason the page is slow. The correct form is the same shape as
behaviour 7's filter, in reverse: collect the page's lineage roots, select every live attachment whose
`target_root` is in that set, and group in memory.

**Behaviour 13 matters because the alternative is silent.** A null would make every consumer test for
it before iterating, and the one that forgets fails on precisely the rows that carry no labels — which
is most of them early in a plan, and none of them in the fixture somebody writes to test labelling.

**Behaviour 2 is the half a builder drops**, because a count reads as complete on its own. It is not:
a label on all 687 rows and a label on one are both useless for filtering, and only the denominator
tells them apart.

**Behaviour 5 keeps a word findable.** Reporting it as missing would tell the planner the word is
free, which is the moment they define it again — and `define_term` would refuse it as a duplicate, so
the report would have walked them into a refusal.

**Behaviour 6 is the standing ruling restated where it would be broken.** A count of one and a count
of everything are both interesting, and any rule saying *which* is bad is a threshold — a judgment
written as arithmetic so review cannot see it.

**Behaviour 7 is a real join and it is the task the superseded draft never wrote** — it promised the
filter and specified only a dataclass field and a parser key. Attachments key on lineage roots while
`read_rows` is handed refs, so the join is `plan_rows` → `lineage_root(ref)` → `target_root`, and the
root is computed per candidate row rather than matched directly. **The cheap correct form is a
subquery over the attachments**: collect the attached roots for the word, then filter rows whose root
is in that set, because one word's target set is small and the row set is not.

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
| 4 | `read_rows` gains a `label` parameter, and the contract row and docstring enumeration are amended. |
| 4a | The rendered form of a page shows each row's labels, and `contracts:10` — the contract `RowPage` answers to — is amended to say the page carries them. |
| 5 | The registry rows land **before** any refusal whose text names the call. |
| 6 | Payload parsing for the label calls is registered once, under one name. |

**The arithmetic, measured from `engine/surface.py` on 2026-07-30 and stated as a method rather than
a number.** Today: **54** registrations via `_t(`, and **12** `ADDED` entries. Six glossary tools are
registered and all six are in `ADDED`, because the frozen plan never asked what the words mean, so
each carries `DEVIATION`. This change removes three and adds four, giving **55** and **13** — *against
today's code*. Changes 1, 2 and 3 all touch this file and none of them is built, so **re-run the
count at build time**; the number to trust is the one measured against what those changes actually
left. `EXCLUDED` and `DEFERRED` are both empty today and neither is touched.

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
| 1 | `engine/methodology/rev6/` is created from rev5, with a stage-6 labelling round. |
| 2 | The round says in as many words that **a label is a glossary term**, and that `define_term` is how you mint one. |
| 3 | `approve_term` is removed from `mandate.md` and `gap_rules.yaml`. |
| 4 | Residual packaging-round prose is deleted. |
| 5 | `get_stage_script(6)` renders without raising. |

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
| 5 | Both `COALESCE` sentinels are unreachable: `INSERT INTO tasks (id) VALUES (0)` and a `target_root` of `''` are both refused. |
| 6 | `label_attachments` is **not** in the snapshot table set, and **not** in the `junctions` exemption set. |

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
| 8 | `read_rows(label=w)` returns each row once, `total` matches the filtered set, and paging is correct across a boundary. |
| 9 | `read_rows(label=<unknown>)` returns an empty page rather than raising. |
| 10 | A row carrying three labels comes back from `read_rows` with all three, and a row carrying none appears in the mapping with an empty tuple. |
| 11 | Reading a page of N labelled rows issues a **fixed** number of queries, not one per row. |
| 12 | A label attached before a row was superseded is still reported against the live version. |

**Behaviour 3 is a one-line test for a defect that is invisible until a caller passes a flag.**

**Behaviour 8 needs more rows than one page** or it asserts nothing about the failure it exists for.

### Task 4F.3 — the deletions

**Behaviours**

| | behaviour |
|---|---|
| 1 | `tests/test_vocabulary.py` is already gone — change 1 deleted it (§4.1). Nothing here re-deletes it. |
| 2 | The `terms` tests are rewritten for the removed calls; every test of approval, bans, supersession and export goes. |
| 3 | `tests/test_schema_vocabulary.py` is untouched except for 4A.0's two edits to `TIMESTAMP_ROLES`. |
| 4 | No test asserts a warning kind, gap rule or status line that packet 4C deleted. |
| 5 | `get_stage_script(6)` renders without raising. |

## 14. What re-measuring disagreed with

**Four counts in §5 and `04-labels.md` did not survive re-derivation.** Each was correct when
written, against a design that has since changed. The method is stated so it can be re-run rather
than trusted.

| claim | measured 2026-07-30 | method |
|---|---|---|
| `TIMESTAMP_ROLES` becomes **8** | **7 → 7.** `detached_at` joins, `approved_at` leaves with the only column that used it | parse the dict in `test_schema_vocabulary.py`; grep `approved_at` across all 37 tables in `engine/schema.py` |
| `JUSTIFICATION_ROLES` is **18 today** | **it does not exist in the code.** It appears only in the specs for changes 2, 3 and 4, none of which is built | grep the repository |
| `LABELS_DDL` yields **four** statements | **three.** `term_comparisons` is deleted with the guard | count `CREATE` in the block; re-probe through `schema.statements`, because the split survives only on comments being stripped |
| the change *"removes three tools and adds three"* | **removes 3, adds 4.** `remove_term` is a new registration, not a rename of `retire_term`: different signature, different act | `_t(` and `Absence(` in `engine/surface.py` — 54 and 12 today |

**And one that held.** `SCHEMA_VERSION` is **7** in the code; changes 1–3 take it to 10, so this
change's 10 → 11 is right — but 10 is a number to verify at build time and not to assume, for the
same reason as every other number here.
