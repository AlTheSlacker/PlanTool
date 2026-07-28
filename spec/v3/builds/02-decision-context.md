# Change 2 — decision context

**Specification. Packets 2A to 2C have been cold-read once and corrected; 2D and 2E have not.**
Second of the ten changes in `PLAN.md` §4, and deliberately early: it improves the record of every
change after it, so it earns its value across the rest of the work.

Depends on change 1 — schema version 8 is its starting point, `stage` is a legal identifier by
then, and the methodology is at revision 4.

**The first draft named the new field `reason`, which was wrong in a way worth keeping on the
record.** §2 settles that `reason` means *why an act was performed*, and then §3 gave the same
word to *why a row's content is what it is* — retiring one word for having two spellings and in
the same breath giving two concepts one spelling. §11 records the rest.

---

## 1. What this change does

D11 in one sentence: **a decision is stored with its context, in a separate field** — the
reasoning, what was rejected, and on what grounds — rather than as prose folded into the
description, because a convention is not checkable and cannot be required.

The defect it answers was logged from the GUI dogfood. A session resumed cold, read back a
decision about dragging references between panels, and **could recover the answer but not the
argument**. Nothing recorded why that shape was chosen, or that the alternative had been
considered and rejected. So the resuming session could neither defend the decision nor safely
reopen it — and reopening a settled question is the expensive failure, because it spends the
owner's attention on ground already covered.

## 2. Two roles, and the words for them

**This is the finding that shaped the change, and it was not visible from D11.** The codebase
already records justifications in nine places, under **three** different words:

| where | word | validated at the call? |
|---|---|---|
| `plan_rows.retire_reason`, written by `retire_row` | reason | **no** |
| `plan_rows.retire_reason`, written by `resolve_assumption` on reject | reason | **no** |
| `behaviour_amendments.reason`, written by `amend` | reason | yes, `.strip()` |
| `scope_attachments.reason`, written by `attach` and by promotion | reason | yes |
| `finding_reallocations.reason`, written by `reallocate_finding` | reason | yes |
| `findings.rationale`, written by `resolve_finding` | **rationale** | yes |
| `findings.rationale`, written by `uphold_finding` | **rationale** | yes |
| `technical_claims.evidence`, written by `fence_claim(rationale)` | **rationale** → **evidence** | yes |

Six of the eight check for blankness and two do not. Three words, one of which — `rationale` —
is a parameter name over a column called something else.

**But there are two genuinely different roles here, and conflating them would be the opposite
mistake:**

- **Why an *act* was performed.** It attaches to a transition, is written once at the moment of
  the act, and every one of the eight above is one of these.
- **Why a *row says what it says*** — the argument behind its content, and what was considered
  and rejected. It attaches to the row, not to a transition, and **nothing in the store records
  it.** That is D11, and it is genuinely new.

### The settlement

**Role 1 is `reason`, everywhere.** Where a table holds more than one, the column is prefixed by
the act: `retire_reason`, `supersede_reason`. `rationale` is retired as its second spelling, so
`findings.rationale` becomes `findings.reason` — one column written by two acts, which is
correct, because both are *closing* the finding and the column records how it was closed.

**`technical_claims.evidence` keeps its name, and the parameter is fixed instead.** The column
holds what was found when the claim was tested; that is evidence, not a justification, and it is
the *parameter* `fence_claim(rationale)` that is misnamed. It becomes `fence_claim(evidence)` —
not `reason`, because renaming it to `reason` would import role 1's word onto role-neutral data.
The first draft exempted this column on the grounds that "no data change is needed", which is the
consequence of a decision rather than an argument for one.

**Role 2 gets its own two words: `grounds` and `alternatives`.**

- `grounds` — why this row says what it says.
- `alternatives` — what else was considered, and why it lost.

**`grounds` rather than `reason` is the correction the cold read forced**, and the test that
keeps them apart is stated so it can be applied rather than remembered: **a `reason` is attached
to an act and names a transition; `grounds` are attached to content and name no transition.** A
row has grounds from the moment it exists; it acquires a `retire_reason` only if it is retired.

**`alternatives` rather than `rejected`**, which the first draft used. `submit_rows` already
*rejects* rows — `RowVerdict(index, False, problem=…)`, "a row failing validation is rejected
alone" — so a column called `rejected` on `plan_rows` reads as a verdict about the row's own fate.
That is two meanings for one word inside one table, which is the disease this section exists to
treat.

**A mechanism, because a rule in a document is not a mechanism.** `tests/test_schema_vocabulary.py`
already closes the vocabulary of the `_at`, `_id`, `_key`, `_ref` and `_by` suffixes. It gains a
declared set for justification columns — see 2E.1 — which has to match **bare** `reason`,
`grounds` and `alternatives` as well as the `_reason` suffix, because a suffix rule alone would
not see `findings.reason` at all.

## 3. The design questions, answered

### 3.1 One field or two?

**Two: `grounds` and `alternatives`.** D11 says "a separate field", singular, and that is the
answer this change rejects.

A single free-text field is checkable only for emptiness. A planner writes "chosen because it is
simpler", the check passes, and the half the dogfood defect was actually about — *"nothing
recorded that the alternative had been considered and rejected"* — is unrecorded and
unenforceable. The methodology already asks for that half in prose: `stage6_architecture.md`
line 60 says "**you rejected and why, one line each**". It has been asked for and never captured,
which is the profile of a rule with no mechanism.

**This argument is about *design* rows and it does not generalise**, which is why §3.3's starter
set contains no table carrying `grounds` alone. A table whose rows have no alternatives does not
get a weaker version of this rule; it stays out of the set.

**Rejected: a structured list of alternatives**, each with its own grounds. Better data, and a
schema for something nobody has yet written once. `alternatives` is free text like every other
justification in the store, and if the shape turns out to matter a later change can impose one on
a field that already has content in it.

**How a row with no alternative answers honestly.** It writes so, in the field: *"none — this
follows directly from use_cases:4."* There is no exemption flag, and the reason is not the one
the first draft gave. The draft said an exemption is invisible while a sentence is readable; the
cold read pointed out that the codebase already ships two exemption mechanisms — `unless_field`
on `untraced` rules, and `dismiss_gap`, which lets a planner dismiss any gap with a recorded
reason. **`dismiss_gap` is the exemption route**, it is keyed and recorded and the owner can read
the dismissals, and adding a second one specific to this rule would be a parallel mechanism for a
job the general one already does.

### 3.2 Required at write time, or prompted for?

**Neither: it is a gap.** Not refused at `submit_rows`, and not left to a prompt.

Refusing a row without grounds would make every synthesize stage a negotiation with the tool, and
it would produce padding — "because it seemed right" — which is *worse than absence*, because
absence is countable and padding is not. This project's standing position is warn-don't-block.

A prompt is the option D11 named and it is the weakest: a prompt is a convention with a user
interface, and D11's own argument for a separate field is that a convention "is not checkable and
cannot be required".

**The one place it *is* refused, and the reason it is the exception.** `supersede_row` gains a
required `reason`, refused when blank — because superseding is an *act*, and six of the eight
existing reason-bearing sites already refuse a blank. The two that do not are `retire_row` and
`resolve_assumption`, and both are fixed in 2B.3 rather than used as precedent.

### 3.3 Which row types must carry it?

**The gap rules are the list. There is no separate register.** `gap_rules.yaml` is already a
per-table declaration of what a table's rows owe, in versioned methodology data revisable without
a release, so a second list naming decision-bearing tables would be two sources of truth for one
thing.

**Rejected: deriving it from `provenance`, and now measured rather than asserted.** A row with
provenance `decided` is by definition one where someone chose — but `DECIDED` is the *default*
provenance, so the rule would select nearly every row. Counted against the frozen v2 plan, that
is **644 live rows**. The first draft guessed "three hundred", which understated it by half. Six
hundred gaps is the failure where a meter that cries wolf stops being read.

**The starter set. Every table is one the methodology assigns to a synthesize stage.**

| table | stage | live rows in the v2 plan |
|---|---|---|
| `entities` | 4 | 15 |
| `state_machines` | 4 | 10 |
| `dependencies` | 5 | 4 |
| `components` | 6 | 15 |
| `contracts` | 6 | 68 |
| | | **112 day-one gaps** |

**The stage allocation is cited, not chosen.** `manifest.yaml` assigns each table to exactly one
stage — `entities` and `state_machines` to stage 4, `dependencies` to stage 5, `components` and
`contracts` to stage 6. The first draft asserted these allocations and the cold read was right to
refuse them; the manifest is the source, and a gap allocated to a stage that does not own its
table fires at a gate where the planner cannot act on it.

**Every elicit-stage table stays out**, and that is now a rule rather than a list: stages 1, 2 and
3 record what the owner said, and what the owner said is not a decision the tool needs defended.
That drops `requirements`, which the first draft included. It is elicit, it is the largest table
in the plan at **80 rows** — 42% of the draft's day-one count — and its grounds would restate its
content. `goals`, `non_goals`, `actors`, `stack`, `use_cases`, `uc_steps` and `uc_extensions` are
out for the same reason.

**`crud_grid`, `sm_cells` and `dep_failure_modes` are out**, and it is worth saying why since
they belong to synthesize stages. Each is a *cell* of a grid whose grounds belong to the parent —
187 `sm_cells` rows do not each carry an argument; the state machine does. The containment map in
`manifest.yaml` already names each one's mandatory parent, and every parent is in the set.

**`findings` is out because its reason is role 1.** A finding's justification attaches to closing
it, is stored in the column 2B renames to `findings.reason`, and is already gate-checked. Giving
findings `grounds` as well would be a second field for the same obligation.

**There is no `decisions` table in v3's vocabulary**, though `spec/v2/plan.db` has 65 rows in one.
That table is a v1 artefact: `manifest.yaml`'s own comment records that stage 1's table list
"said [decisions, requirements, entities] until 2026-07-26", the v1 shape a defect migrated the
checks off. **One sentence in the stage-5 script still speaks that dialect** — "a decision whose
text contains 'no external dependencies' with the rationale" — and it is corrected in 2C.2 as part
of the same sweep, because it tells a planner to file where nothing reads.

### 3.4 How it interacts with supersession

Three answers, because it is three questions wearing one name.

**Does a replacement inherit its predecessor's grounds? No.** It writes its own. Content is never
edited and a replacement is a new row; inheriting the grounds would attach an argument for the old
content to new content, which is worse than an empty field because it reads as though somebody
checked.

**Is the old row's argument preserved? Yes, untouched.** Lineage is the audit trail. Reading back
`components:3 → components:9` and finding the argument for each is the whole point.

**Why the old row was abandoned is a third thing, and nothing records it today.** `retire_row`
takes a reason and stamps `retire_reason`. `supersede_row` takes none and stamps nothing, so the
two exits from "this row is no longer live" are treated differently and the asymmetry has no
recorded justification — an accident rather than a decision. **`supersede_reason` closes it**,
stamped on the *old* row, exactly as `retire_reason` is.

That matters more than it sounds: a replacement's own `grounds` say why the new content is right.
They do not say what was wrong with the old, and "we learned X at stage 7" is precisely the
argument a cold session needs in order not to re-propose the original.

### 3.5 How an existing row acquires grounds — the hole the cold read found

**The first draft had no answer and did not know it.** After 2A backfills nothing, all 112 rows in
the starter set are gaps. But `content is never edited`; `submit_rows` files new rows;
`supersede_row` replaces one; `retire_row` retires. **Nothing could write `grounds` onto a row
that already exists**, so the only route to closing the first reading was to supersede all 112
rows — each needing a full replacement submission and, after 3.4, a `supersede_reason` explaining
an abandonment that never happened. The draft called the mass gap "the instrument's first reading"
while providing no instrument that could be read down.

**`record_grounds(ref, grounds, alternatives, idempotency_key)` closes it, and it is write-once.**

Writing grounds for the first time is not an edit of the row's claim: the content is untouched,
and the grounds were never recorded. But if grounds can be rewritten they become a place to revise
history quietly, which is the one thing this store does not permit anywhere else. So: **a row
whose grounds are already recorded refuses**, and changing an argument requires superseding the
row — which is the existing mechanism for changing what a row says, with the existing audit trail.
That is the same shape as `AlreadySuperseded` ("lineage is write-once") and needs no new concept.

## 4. Packet 2A — the schema

Schema version 8 → 9. Nothing else in this change can start until this lands.

### Task 2A.1 — `Storage._migration_steps`, the 8→9 branch

**Signature.** Unchanged: `_migration_steps(self, current: int, target: int) -> list[str]`.
Gains one branch.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Adds `grounds`, `alternatives` and `supersede_reason` to `plan_rows`, all nullable text. |
| 2 | Renames `findings.rationale` to `findings.reason`. |
| 3 | Emits the three additions in the same order the DDL declares them. |
| 4 | Backfills nothing. |

**Behaviour 4 is the decision in this task.** Every existing row has no recorded argument and
there is no truth in the old store that says what it was. The standing migration rule is that a
migrated value must be a truth the old store already implied, never one invented to satisfy a
constraint — so the columns arrive NULL and the gap engine reports 112 live rows on the next run.
That is the instrument's first reading, not a defect, and §3.5 is what makes it possible to work
down.

**Behaviour 3 exists because of the single most likely build-time failure in this change.**
`ALTER TABLE … ADD COLUMN` appends to the end of the column list. If 2A.2's DDL puts `grounds`
next to `retire_reason`, where it reads naturally, a fresh database and a migrated one hold the
same columns in different positions — and `PRAGMA table_info` returns a different `cid` for each.
The three new columns therefore go **at the end of `plan_rows` in the DDL, in the ALTER order**,
and 2E.2 compares by column *name* rather than by `cid`. Both halves are needed: matching order
makes them agree, and comparing by name makes the check honest about what it is asserting.

**The columns are nullable and that is deliberate**, not an oversight to tighten later.
`NOT NULL DEFAULT ''` would make every row satisfy the column while satisfying nothing.

**Pseudocode**

```
if (current, target) != (8, 9):
    fall through to the existing adjacent-pair table and its ValueError

emit  ALTER TABLE plan_rows ADD COLUMN grounds          TEXT
emit  ALTER TABLE plan_rows ADD COLUMN alternatives     TEXT
emit  ALTER TABLE plan_rows ADD COLUMN supersede_reason TEXT
emit  ALTER TABLE findings  RENAME COLUMN rationale TO reason
```

No index is added. None of the three columns is ever a lookup key: the gap rules scan the live
rows of one table at a time, and that read is served by the existing indexes.

### Task 2A.2 — the DDL text

**Signature.** None — `schema.DDL` is module-level text, and `SCHEMA_VERSION` becomes 9.

**Behaviours**

| | behaviour |
|---|---|
| 1 | A fresh database and a migrated one end structurally identical, compared by column name. |
| 2 | The three new columns sit at the end of `plan_rows`, in 2A.1's order. |
| 3 | Each carries a comment naming its role, and `findings.reason`'s comment is rewritten. |
| 4 | The version-8 DDL is retained as the fixture the parity check migrates from. |

**Behaviour 3 is not decoration.** The whole risk this change carries is a future writer adding a
tenth justification column under a new name because they could not tell which role theirs was. The
comment that says *"`grounds` is why this row's content is what it is; the reason an act was
performed is prefixed by the act, as in `retire_reason`"* is what a person reads at the moment of
the mistake. `findings.reason`'s existing comment says "for accepted_risk: the owner's
acceptance", and a rename that leaves the comment behind is how a column ends up meaning two
things.

**Behaviour 4 inherits a pattern change 1 started and this is the change that makes it a
pattern.** Change 1 retained the v7 DDL so its parity check had something to migrate from; this
retains v8. The retained set grows by one text per schema change — the cost of having a parity
check at all, and small: they are text, they diff, and they are never executed except by that
check.

## 5. Packet 2B — the write path

Depends on 2A. `models.py`, `rows.py`, `findings.py`, `validation.py`, `gates.py`, `surface.py`.

### Task 2B.1 — `RowSubmission`, `PlanRow` and `submit_rows`

**Signature.** `RowSubmission` and `PlanRow` each gain `grounds: str | None = None` and
`alternatives: str | None = None`, **appended after every existing field**, and `PlanRow` also
gains `supersede_reason: str | None = None`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Both fields are stripped and written to their columns on every accepted submission. |
| 2 | A value that strips to empty is stored NULL, never `''`. |
| 3 | A submission with neither is accepted. Absence is a gap, not a rejection. |
| 4 | `PlanRow` carries all three back on every read. |
| 5 | The `rows` payload parser accepts both keys, optional, and rejects a non-string naming the field. |

**The fields are appended rather than inserted, and the first draft got this wrong twice.** It
said "after `package` and before `spike`" — naming a field change 1 renamed to `stage`, and
choosing a position that silently rebinds every positional construction of `RowSubmission` past
that point across ~537 tests. Appending costs nothing and breaks nothing.

**Behaviours 1 and 2 replace the draft's "written unmodified", which contradicted its own next
line.** The draft said unmodified *and* that whitespace-only becomes NULL, which leaves
`"  because X  "` unspecified. Strip on store, once, at the write — `supersede_row` already does
exactly this with `replacement.name.strip()`. This is a candidate register entry; see §10.

**Behaviour 5 is the omission that would have made the whole change inert.** The `rows` payload
type has a parser that validates each submitted row's structure; if it does not learn the two
keys, no client can ever supply them, every live row stays a gap forever, and 2C specifies an
unclosable gap.

**Pseudocode** — none. The fields join an existing insert that already carries eight columns from
the same submission.

### Task 2B.2 — `record_grounds`

**Signature.** `record_grounds(self, ref: RowRef | str, grounds: str, alternatives: str,
idempotency_key: str) -> PlanRow`, on `RowService`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Writes both columns on a live row that has neither. |
| 2 | Refuses with `RowNotFound` when the ref is unknown, naming it. |
| 3 | Refuses with `GroundsAlreadyRecorded` when either column is already set, naming the row and pointing at `supersede_row`. |
| 4 | Refuses with `GroundsNeedBoth` when either argument is blank, naming which. |
| 5 | Refuses on a superseded or retired row, naming its state. |
| 6 | One transaction, one op. |

**Behaviour 3 is what makes this safe**, and §3.5 gives the argument: writing an argument that was
never recorded is not editing the row's claim, but *re-writing* one is revising history, and
revising what a row says is what supersession is for. The error names the alternative rather than
just refusing, because an error that does not say what to do instead is how a planner ends up
inventing a workaround.

**Behaviour 5 exists because a superseded row is frozen history.** Recording grounds on it would
let a later session improve the argument for a decision that has already been replaced — the same
objection as behaviour 3, one step further from the reader.

**Behaviour 4 requires both because §3.1's "no exemption" only works if the honest answer is
written.** A row with no alternative writes "none — follows from use_cases:4"; permitting a blank
`alternatives` would restore the exemption flag §3.1 declined, spelled as an empty string.

**Pseudocode**

```
row = fetch(ref)                       # RowNotFound naming the ref
if row.state in (SUPERSEDED, RETIRED):
    raise GroundsAlreadyRecorded-family error naming the state
if row.grounds or row.alternatives:
    raise GroundsAlreadyRecorded naming the row, pointing at supersede_row
if not grounds.strip() or not alternatives.strip():
    raise GroundsNeedBoth naming which is blank
write_atomic([update plan_rows set grounds, alternatives where table_name, ordinal],
             idempotency_key)
return self.get(ref)
```

### Task 2B.3 — `supersede_row` gains a reason

**Signature.** `supersede_row(self, old, replacement, reason: str, idempotency_key: str)`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Refuses with `SupersedeNeedsReason` when `reason` is blank; nothing is written. |
| 2 | Stamps `supersede_reason` on the **old** row, on the first of the batch's existing ops. |
| 3 | The replacement's own `grounds` and `alternatives` are written from the submission, as 2B.1. |
| 4 | The blank check runs after `RowNotFound` and `AlreadySuperseded` and before the name check. |

**Behaviour 2's placement inside the existing batch is load-bearing.** Those writes are ordered so
the old row leaves the live-name index before the replacement enters it, and they were two
transactions until a crash between them left a row live and unstamped beside its own replacement.
The reason rides on the first op — the `update` setting the old row's state — because that op
already targets the old row. **The batch is three ops, or four when the replacement carries a
spike**; the first draft said "the existing three writes" without noticing the fourth.

**Behaviour 4 orders the guards so the message a caller sees is about the thing that is most
wrong.** A blank reason on a ref that does not exist should report the missing row.

**`reason` is a required positional parameter, not a keyword with a default.** A default of `""`
would make every existing caller compile and every existing caller wrong, silently. Every
in-process caller must be found and given one — and the cold read was right that the draft never
said who they are: `resolve_assumption` is the one to check first, since it can reject an
assumption and retire it.

### Task 2B.4 — the guards and the spelling that are missing

**Behaviours**

| | behaviour |
|---|---|
| 1 | `retire_row` refuses a blank reason with `RetireNeedsReason`. |
| 2 | `resolve_assumption` refuses a blank `retire_reason` when the resolution is `reject`. |
| 3 | `findings.rationale` becomes `findings.reason` in the column, the model, both writers and the reader in `gates.py`. |
| 4 | `validation.fence_claim`'s `rationale` parameter becomes `evidence`. |

**Behaviours 1 and 2 are bug fixes and they belong here.** Six of the eight justification sites
check for blankness and these two do not, so `retire_row(ref, "", key)` records a retirement with
no reason today. The draft claimed "every sibling act checks" and named only `retire_row`; the
cold read found the second. This change is the one that settles what a justification is, so the
odd ones out are fixed where the reader is already looking at the rule.

**Behaviour 3 reaches further than its module.** `gates.py` reads `finding.rationale` when it
checks that a resolved finding carries one; `uphold_finding` writes the same column; the registry
has a `Param("rationale", …)` with a note. All rename together, and per register 13 so do the
tests and the SQL comment.

**Behaviour 4 renames the parameter to match its column**, not to `reason` — see §2. `evidence` is
what that column holds and it is the right word; only the parameter was spelled wrongly.

## 6. Packet 2C — the gap rule

Depends on 2B. `gaps.py`, `engine/methodology/__init__.py`, and the methodology assets.

### Task 2C.1 — the `unreasoned` rule type

**Signature.** A new entry in the rule-type dispatch: `"unreasoned": self._rule_unreasoned`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Reports one gap per live row of `table` missing any of the named `fields`. |
| 2 | `fields` names row-level justification **columns**, not content keys. |
| 3 | The gap key is discriminated by which fields are missing. |
| 4 | The `ask` is formatted with the missing field names as well as the row's name. |
| 5 | A `fields` entry naming something `PlanRow` does not carry raises `PlanUnreadable` at load. |
| 6 | No `when_field`, and no `unless_field`. |

**Behaviour 2 is why this is a new rule type rather than a reuse of `missing_field`.**
`missing_field` reads `row.content.get(f)` — free-form JSON. The whole basis of the separate-field
design is that a convention inside content is not checkable, and D12 already settled that nothing
an accounting depends on may be inferred from `content`, because it has no per-table schema. A gap
rule *is* an accounting.

**Rejected: generalising `missing_field` with a `source: column` option.** Cheaper by one function
and it makes an existing rule type's behaviour depend on a flag most of its rules do not set —
which is how a rule that says four ends up measuring twenty-two.

**Behaviour 4 is a correction, and the draft's pseudocode could not have satisfied its own
behaviour table.** The draft required an `ask` "naming what is missing" and then called `_make`
with no formatting arguments, so an `ask` containing `{missing}` would have raised `KeyError` at
derive time. `_make` already accepts `**fmt` and passes it to `ask.format(...)`, so this needs no
change to the shared helper — only for the handler to pass `missing=`.

**Behaviour 5 is the cold read's catch on my own pseudocode.** `getattr(row, f, None)` turns a
misspelt column name into "missing on every live row" — a rule that silently measures something
other than its name, which is the exact failure this project has recorded before. Validating
`fields` against `PlanRow`'s field names at load, and raising the same `PlanUnreadable` that an
unknown rule type raises, makes the typo loud.

**Behaviour 6 drops two options the draft carried by habit.** `when_field` reads `content`, which
this rule type deliberately does not; none of the shipped rules would use it, so it would ship
untested. `unless_field` is the exemption §3.1 declined in favour of `dismiss_gap`.

**Pseudocode**

```
def _rule_unreasoned(rule):
    gaps = []
    for row in self._live(rule.spec["table"]):
        missing = [f for f in rule.spec["fields"] if not getattr(row, f)]
        if missing:
            gaps.append(self._make(rule, row,
                                   extra_key=",".join(sorted(missing)),
                                   missing=" and ".join(sorted(missing))))
    return gaps
```

`getattr(row, f)` without a default: the load-time validation in behaviour 5 is what makes the
two-argument form safe, and the two-argument form is what makes a validation failure impossible to
miss if it is ever skipped.

**Known and accepted: `Gap.context` will not show the missing fields.** `_make` hard-codes
`context={"row": row.content}`, and `grounds` and `alternatives` are columns, so the gap a planner
reads carries the row's content and not the fields it is complaining about. Changing `_make`
changes the payload of all eight rule types, and the `ask` already names the row and what is
missing. **Left alone deliberately**, and recorded here so that if the gap proves hard to act on,
the fix is known and its cost is known.

### Task 2C.2 — the rules, the scripts, and methodology revision 5

**Behaviours**

| | behaviour |
|---|---|
| 1 | Five `unreasoned` rules are added to `gap_rules.yaml`, one per table in §3.3. |
| 2 | Each is `priority: 2` and carries the stage `manifest.yaml` assigns its table. |
| 3 | The `Rule types:` block in the asset header gains a line for `unreasoned`. |
| 4 | The stage scripts stop asking for rationale in prose where a rule now asks for it as data. |
| 5 | The stage-5 script's `decisions`-table sentence is corrected. |
| 6 | `rev4` is copied to `rev5` and edited there; the revision stamp advances. |

**The rules, in full, because "seven rules are added" is not a specification.** Ids are permanent
once shipped — `Gap.key` is built from `rule.id`, and dismissals are recorded against that key —
so they are drafted here rather than left to the builder:

| id | stage | table | fields |
|---|---|---|---|
| `entity_without_grounds` | 4 | `entities` | `[grounds, alternatives]` |
| `state_machine_without_grounds` | 4 | `state_machines` | `[grounds, alternatives]` |
| `dependency_without_grounds` | 5 | `dependencies` | `[grounds, alternatives]` |
| `component_without_grounds` | 6 | `components` | `[grounds, alternatives]` |
| `contract_without_grounds` | 6 | `contracts` | `[grounds, alternatives]` |

Each `ask` follows the shape the file already uses — name the row, say what is missing, say what
to do:

> `{name}` records no {missing}. A design decision nobody can defend is one a later session will
> reopen. Write why this shape was chosen and what you considered instead — "none, it follows from
> X" is a complete answer when it is true.

**`priority: 2` is cited, not chosen.** The ladder at the head of `gap_rules.yaml` reads
"2 holes in the current stage", and an unmet row-level obligation inside the stage that owns the
table is exactly that.

**Behaviour 4 is the point of doing this at all.** `stage6_architecture.md` line 60 says "what you
rejected and why, one line each" — a sentence in a script, which is a rule with no mechanism, and
the evidence it does not work is that no row in the plan carries a rejected alternative. Leaving
the sentence *and* adding the rule gives the planner two sources for one obligation, which is the
duplication this product exists to catch. **The script keeps what a rule cannot express — what
makes a good argument — and hands the accounting to the rule.** The lines that go are the ones
stating the obligation; the lines that stay are `mandate.md`'s, which govern how the planner
converses rather than what a row owes, and stage 7's, which are about findings and out of scope.

**Behaviour 6's sequencing consequence.** Change 1 mints revision 4 because the door makes stale
asset text a runtime failure; this change edits assets again, so it mints revision 5, and
`PLAN.md` item 10's eleven-stage rewrite becomes revision 6. **The lesson is not about numbering:**
every change touching a stage script costs a revision, so the plan should expect the number to
climb once per such change rather than treating a bump as an event.

### Task 2C.3 — the loader

**Behaviours**

| | behaviour |
|---|---|
| 1 | `unreasoned`'s `table` and `fields` keys are folded into `rule.spec` as the other types' keys are. |
| 2 | A rule of this type with no `fields`, or with a `fields` entry `PlanRow` does not carry, raises `PlanUnreadable` naming the rule id. |

**This task exists because the draft's dependency line said "`gaps.py` and the methodology
assets", and the loader is neither.** Rules are written flat in YAML and reach the handler as
`rule.spec[...]`; something folds them. Behaviour 2 is where 2C.1 behaviour 5 is actually
implemented — at load, once, rather than per row per derive.

## 7. Packet 2D — the surface and what a reader sees

Depends on 2C. `surface.py`, `render.py`.

### Task 2D.1 — the registry

**Behaviours**

| | behaviour |
|---|---|
| 1 | The `rows` payload note and parser accept `grounds` and `alternatives`, both optional. |
| 2 | `supersede_row` gains a required `reason` parameter, before `idempotency_key`. |
| 3 | `record_grounds` is added as a `DEVIATION` tool with its reason. |
| 4 | `resolve_finding`'s and `uphold_finding`'s `rationale` parameters become `reason`. |
| 5 | The named errors of `contracts:12` and `contracts:13` gain the two new refusals. |

**Behaviour 3 is a new tool and §3.5 is why it has to be one.** Without it, the only way to give
an existing row its grounds is through the surface's supersede path, which demands a full
replacement submission and a `supersede_reason` for an abandonment that did not happen. It is a
`DEVIATION` because no contract row describes it — the plan never anticipated the field, so it
cannot have anticipated the call — and register 5 requires the written reason that goes with that.

**Behaviour 5 matters because register 1 ties a raised error to the contract's named-error list.**
`SupersedeNeedsReason` and `RetireNeedsReason` are new refusals on contracted calls, and a contract
whose error list omits an error the call raises is a contract that lies to its reader.

**No `why(ref)` tool is added.** It would be a pleasant thing to have and a second route to data
`read_rows` already returns. The build surface is six calls and its smallness is the design.

### Task 2D.2 — rendering

**Behaviours**

| | behaviour |
|---|---|
| 1 | A rendered row shows its grounds and alternatives when present, and says nothing when absent. |
| 2 | A superseded row shows why it was superseded, next to the ref that replaced it. |
| 3 | Refs inside the three new fields are rendered as `name (ref)`. |

**Behaviour 2 is the dogfood defect, closed, and it is worth checking against the original
complaint.** The session could recover the answer and not the argument. After this change, reading
back that row shows what it says, why it says it, what was rejected, and — if it has since been
replaced — why it was abandoned and by what.

**Behaviour 3 is not new work; it is the door's existing invariant, and this change walks into
it.** These fields' natural content is full of refs: "rejected the flat store — see
`entities:4`". `door.scan` raises `BareAddress` on any `table:ordinal` in an outgoing payload that
is not accompanied by a name, so a row rendered with an unresolved ref in its grounds **fails the
call**. The rendering path already resolves refs; these fields have to go through it.

## 8. Packet 2E — the enforcement

Depends on all of the above.

### Task 2E.1 — the justification-vocabulary check

**Behaviours**

| | behaviour |
|---|---|
| 1 | `test_schema_vocabulary.py` gains a declared set of justification columns, by exact name, each with its role. |
| 2 | It matches bare `reason`, `grounds` and `alternatives` as well as the `_reason` suffix. |
| 3 | Fails if any schema column is named `rationale`, `justification`, `explanation` or `why`. |
| 4 | Its own fixture asserts the count of justification columns it finds. |

**Behaviour 2 is a correction the cold read forced.** The draft added `_reason` to the existing
`SHAPES` map, which is a *suffix* check — and it would not have matched `findings.reason`,
`grounds` or `alternatives` at all. A mechanism that does not see the columns the change adds is
not a mechanism.

**Behaviour 3 is a deny-list and deny-lists are usually the wrong tool**, so the reason it is right
here is specific: the failure being prevented is a *second spelling of a role that already has a
word*, and the only way to catch that mechanically is to name the spellings. The general form — "a
new concept given a name that duplicates an existing one while sharing no lexical structure" — is
what this check's own docstring says nothing mechanical can catch.

**Behaviour 4 is the guard against the check going blind**, against the standing evidence of a
check that ran green while seeing four names where there were twenty-two.

### Task 2E.2 — schema parity and the new gap

**Behaviours**

| | behaviour |
|---|---|
| 1 | A version-8 database migrated to 9 is structurally identical to a fresh 9, compared **by column name** through `PRAGMA table_info` / `index_list` / `foreign_key_list`. |
| 2 | A live row of a rule-bearing table with no grounds produces exactly one gap, at the stage that owns its table. |
| 3 | A row whose `grounds` is whitespace produces the same gap as one whose grounds are absent. |
| 4 | `record_grounds` closes the gap; a second call on the same row refuses. |

**Behaviour 1 reuses the mechanism change 1 built and must not reimplement it**, and "by column
name" is the part that is easy to get wrong. Comparing the ordered `table_info` output would
compare `cid` too, and 2A.1's `ADD COLUMN` appends while a DDL edit could put the column anywhere.
2A.2 behaviour 2 makes them agree; this makes the check say what it means either way.

**Behaviour 4 is the test that §3.5 is real.** It is the end-to-end path — a gap exists, a call
closes it, the call is write-once — and it is the one a builder would skip, because each half looks
covered by a unit test of its own.

## 9. What this change does not do

**It does not make grounds mandatory.** A plan can be finalized with rows that have none, and the
gate reports them as holes. If that proves too weak the fix is a gate criterion, not a write-time
refusal, and it is a later change with its own evidence.

**It does not backfill**, and the 112 rows it lights up on the existing plan are the first honest
reading the instrument has taken.

**It does not give grounds to elicit-stage rows, to grid cells, or to findings**, each for the
reason in §3.3.

**It does not define what makes an argument good.** That stays in the stage scripts, where judgment
belongs, and out of the engine, which records judgment and never exercises it.

## 10. A convention this change proposes

**Strip on store.** *Is stored free text trimmed? Yes — a text value is stripped before it is
written, and a value that strips to empty is stored NULL, never `''`.* Both cold reads reached
this independently, `supersede_row` already does it with `replacement.name.strip()`, and this
change adds four more text fields that need the same answer. It goes to `CONVENTIONS.md` when a
third task needs it, per the register's own rule that entries grow from cold-read output rather
than from anticipation — this is the second.

## 11. The cold read

**Packets 2A, 2B and 2C were read blind**, two readers, given the specification, the conventions
register and the source a builder would hold. Both reported zero tool uses.

**What they found, in the order it mattered:**

- **The naming was self-contradictory.** §2 settled `reason` for "why an act was performed" and §3
  then used it for "why a row's content is what it is" — retiring `rationale` for being a second
  spelling while giving two concepts one spelling. `grounds` and `alternatives` are the fix, and
  `alternatives` also resolves a second collision: `submit_rows` already "rejects" rows, so a
  column named `rejected` reads as a verdict on the row's own fate.
- **There was no way to give an existing row its grounds.** Content is never edited, `submit_rows`
  files new rows, `supersede_row` replaces. The draft created 112 gaps and no instrument to close
  them. `record_grounds` (§3.5, 2B.2) is the answer, and write-once is what keeps it honest.
- **The `rows` payload parser was never mentioned**, which would have made every one of those gaps
  permanently unclosable from the surface.
- **`ADD COLUMN` appends and a DDL edit might not**, which would have failed the parity check on
  `cid` — the most likely build-time failure in the change.
- **The pseudocode could not satisfy its own behaviour table**: an `ask` "naming what is missing"
  with no formatting argument passed. And `getattr(row, f, None)` would turn a misspelt column into
  a gap on every row — a rule silently measuring something other than its name.
- **Six counting and quoting errors.** Four justification sites where there are eight; two words
  where there are three; "every sibling act checks" when `resolve_assumption` does not; nine
  submission columns where there are eight; "neither column" of three; "the existing three writes"
  when a spike makes four. And a methodology line misquoted inside quotation marks with no
  ellipsis, in a product built on verified quotes.
- **Four stage allocations asserted that `manifest.yaml` states outright**, and one — `dependencies`
  — justified by a script sentence that is actually about a `decisions` row, in a table v3 does not
  have.
- **"Three hundred gaps" was a guess.** Measured against the frozen plan, the rejected
  provenance-based rule would raise **644**; the starter set as drafted, **192**, of which 80 came
  from `requirements` alone. Dropping the elicit-stage table takes it to **112**.
- **The claim that there is no exemption flag was wrong**: `dismiss_gap` and `untraced`'s
  `unless_field` are both exemption mechanisms already shipped. `dismiss_gap` is now named as the
  route rather than denied.

**One reader was wrong about one thing**, recorded because taking a cold read entirely at face
value is its own failure: it held that making the `ask` name the missing fields would require
changing the shared `_make` helper. `_make` already accepts `**fmt` and forwards it to
`ask.format(...)`, so only the handler changes.

**Packets 2D and 2E have not been cold-read.** They were rewritten after these findings — the
naming changed under them, `record_grounds` is new, and the vocabulary check turned out not to
match the columns it was meant to govern — so what exists now has never been read blind. That is
the next job on this change, before any code.
