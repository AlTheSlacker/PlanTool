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
  `TIMESTAMP_ROLES` (**7 today**, measured 2026-07-30, becoming 8). **No column joins
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

The surface arithmetic **changes and must be re-derived, not carried**: this change now *removes*
three tools (`retire_term`, `approve_term`, `export_glossary`) as well as adding three. The measured
inputs, re-counted from `engine/surface.py` on 2026-07-30, are **54** registrations and **12**
`ADDED` entries today.

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

## 6. Still open

**The owner has not ruled on these. Do not invent an answer and proceed silently.**

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
