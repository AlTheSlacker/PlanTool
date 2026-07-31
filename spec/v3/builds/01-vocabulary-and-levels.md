# Change 1 — vocabulary and levels

**Specification. No code until this is settled and cold-read.** First of the ten changes in
`PLAN.md` §4, and the one everything else sits on.

Written at the depth `INTERVIEW.md` §8 defines: tasks, their behaviours, and pseudocode, with
every decision either cited, covered by `CONVENTIONS.md`, or named here as a hole and answered.

**All six packets have now been cold-read.** §10 records what that cost and what it found; the
specification below is the corrected one. The first draft of packets 1B to 1F contained six
factual errors about the code they change, four of them miscounts, and left eleven cross-task
holes. None of it had been built.

---

## 1. What this change does

Three level changes and one rename, from D5, D7 and D16:

- **`package` is removed** as a build grouping — the table, the ids, the level, mandatory
  membership, the finalization refusal, and the three calls that declare, assign and show it.
- **`subtask` is removed** as a level. The name `tasks` moves *down* onto what a builder is
  handed, and the model, the errors and the graph move with it.
- **`obligation` becomes `behaviour`** — same machinery, plainer word.
- **`stage` is un-retired** for the interview's ordered steps, taking over the other meaning of
  "package".

## 2. The measurement that sizes it

| module | lines mentioning the dying words |
|---|---|
| `tasks.py` | 186 |
| `briefs.py` | 86 |
| `obligations.py` | 79 |
| `schema.py` | 71 |
| `gates.py` | 61 |
| `surface.py` | 49 |
| `resume.py` | 43 |
| `gaps.py` | 28 |
| `methodology/__init__.py` | 24 |
| `findings.py` | 23 |
| `guidance.py` | 19 |
| `attachments.py` | 10 |
| everything else | 31 across 9 modules |

710 lines across 21 modules, plus the methodology assets and the test suite. That is why this is
six packets and not one.

**The methodology module was missing from this table until the cold read.** It holds
`class Package`, `Methodology.packages`, `criteria_for`, `package()` and `package_range`, and
`gates.py`, `findings.py`, `gaps.py` and `guidance.py` all read them. A module nothing claimed,
which four claimed modules cannot compile without.

## 3. The hole this change turns on, found before any code

**`package` names two different things in v2, and only one of them dies.**

`plan_rows.package` is the *planning* package — the ordinal 1..8 of the interview step that
produced the row. `packages` is the *build* grouping declared by the owner under D13. The schema
says so itself, in a comment above the index: "*`package` here is the planning package that
produced the row, not a row in the `packages` table.*"

D7 removes the second. The first becomes `stage`. A migration that treats them as one word
destroys either the interview's own record or the owner's declared groupings.

This is the class of decision `INTERVIEW.md` §8 calls a hole rather than a convention: answered
differently, it changes the specification of every task below.

**And `stage` is not a free word today.** `GLOSSARY.md` bans it as an identifier, enforced by a
test that parses the ban line out of that file. So does `project`. Clearing that check is
therefore the *first* task of this change, not a consequence of it — see 1A.0, where it is done by
deleting the check rather than by editing the document.

## 3.5 How this change lands, and why it is one pull request

**One branch, one pull request, six packets as its commit order. The suite is required green at
the end and nowhere in the middle.**

This is a decision, and the alternative is the one this project normally takes — a packet per
pull request, each green. The cold reads killed it by finding three places where a packet cannot
be green on its own, and the three are not accidents of ordering:

- 1B deletes `redistribute_ops`; its only caller, `split_subtask`, lives until 1C.
- 1D writes `stage` into six modules; the ban on that identifier lifts in 1A.0, but 1D's own
  callers in the methodology module do not exist until 1E.
- 1F is a test asserting that everything above landed. It cannot pass before it does.

**1F lost its first task on 2026-07-30 and now holds only schema parity** — see 1F.1's replacement
note. That does not change this argument: 1F.2 is still a test of what the packets above it did.

**Rejected: reordering so each packet is green.** It is achievable and it costs more than it
saves — the level surgery would have to precede the rename that makes the level's machinery
dead, so the migration gets written twice and several identifiers get renamed twice, once to an
interim name and once to the real one. Interim names are how a codebase acquires words nobody
chose.

**What is given up, stated rather than discovered later:** a large diff reviewed in one sitting.
The mitigation is that the packets are the commits, each with its own message, so the diff can
be read a packet at a time even though it lands together.

## 4. Packet 1A — the vocabulary rule, schema and migration

Schema version 7 → 8. Nothing else in this change can start until this lands.

### Task 1A.0 — delete `tests/test_vocabulary.py`

**Rewritten 2026-07-30. This task previously edited `GLOSSARY.md`'s ban line so the live check
would permit `stage`.** The owner then ruled that `GLOSSARY.md` is **a transitional document used
to help write v3**, and that **v3 code reads only the `terms` table** — twice in one conversation,
and again when a later session put the question back to him. A test that parses a markdown file to
police identifiers is exactly the thing he struck. The full argument and its consequences are in
`04-glossary-and-labels.md` §4.1; change 4's own deletion list no longer carries this file, because
by then it is gone.

**Signature.** None — a file is deleted.

**Behaviours**

| | behaviour |
|---|---|
| 1 | `tests/test_vocabulary.py` is deleted whole: all three tests, and the two helpers that parse `GLOSSARY.md`. |
| 2 | Nothing replaces it. No v3 module and no v3 test opens `GLOSSARY.md`. |
| 3 | `tests/test_schema_vocabulary.py` is untouched — it reads `engine/schema.py`, not a document, and changes 2 and 4 both depend on it. |
| 4 | `GLOSSARY.md` itself is left on disk, unedited, as the transitional reading aid it now is. |

**This still lands first, and for the same reason the old 1A.0 did.** Every packet after it writes
an identifier the current check forbids. Deleting the check first means the first commit of 1A does
not fail the suite on `stage`, and the failure that would have looked like a mistake never happens.

**What is given up, stated plainly: nothing mechanical then enforces v3's own identifier naming,
and that is the decision rather than an oversight.** The argument is `04-glossary-and-labels.md`
§2.2 — the failure this discipline exists to prevent is a synonym that shares no letters with the
word it duplicates, and no scan of any kind sees it. What replaces the check is the glossary being
read into context at the moment of naming.

**Two things the old task did that now simply do not happen.** The vocabulary-exceptions fence is
not emptied, it is abandoned with the file; one of its two entries had been protecting
`engine/briefs.py:PartsDontCover`, an identifier that does not exist in `briefs.py` and survives
only inside a docstring. And `project` is not re-banned. It is a tempting name for the surviving
top attachment scope, it stays out of use, and **the level stays `plan` (see 1D) with nothing but
this sentence and `VOCABULARY.md` holding the line.**

### Task 1A.1 — `Storage._migration_steps`, the 7→8 branch

**Signature.** Unchanged: `_migration_steps(self, current: int, target: int) -> list[str]`.
Gains one branch.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Renames `plan_rows.package` to `stage`, preserving every value, and replaces `idx_rows_package` with `idx_rows_stage`. |
| 2 | Drops `subtasks.task_id` and `subtasks.superseded_by` before anything else references them. |
| 3 | Drops the old `tasks` table and then `packages`, in that order. Their indexes go with them. |
| 4 | Renames the three obligation tables, the two obligation-named columns, the ownership table's `subtask_id`, and all three obligation-named indexes. |
| 5 | Renames `subtask_deps`→`task_deps` and `subtask_verifications`→`task_verifications`, their `subtask_id` columns to `task_id`, and their indexes. |
| 6 | Renames `subtasks` to `tasks` and replaces `idx_subtasks_state` with `idx_tasks_state`. |
| 7 | Adds a unique index on `tasks.contract_ref`. |
| 8 | Renames the four remaining planning-sense `package` columns and their two indexes: `gate_runs.package`, `journal_notes.package`, and `finding_reallocations.from_package` / `to_package`. |
| 9 | Rewrites the `behaviours.kind` and `behaviours.key` vocabulary, and the `obligations` key inside contract rows' JSON content. |
| 10 | Collapses the four attachment scope levels to two — task 1A.3. |
| 11 | **Refuses**, before any write, a plan holding more than one live declared package, naming each. |
| 12 | **Refuses**, before any write, a plan in which two live sub-tasks share a contract, naming them. |

**Behaviour 11 is a decision, not a detail.** The standing migration rule is that a migrated
value must be a truth the old store already implied, never one invented to satisfy a constraint.
Collapsing several declared packages into nothing invents the claim that the owner's grouping
meant nothing. One live package migrates silently — that grouping *is* the whole plan, already
implied. Two or more is refused, and the owner retires what he does not want. Refusing costs
almost nothing because exactly one such database exists.

**Behaviour 12 is the same shape.** A unique index on `contract_ref` is only correct because
splitting dies in packet 1C — the old column was deliberately *not* unique precisely so a
split's products could share a contract. A store that still holds a split would have its second
task silently rejected by the index, so the migration checks first and says so.

**Behaviour 8 is the cold read's largest catch, and the draft's claim to completeness is what
made it dangerous.** The draft renamed `plan_rows.package` and declared the schema list closed.
Four more columns and two more indexes carry the planning-sense word: `gate_runs.package` (read
and written by `_record_run` and its idempotency key), `journal_notes.package` (what bounds the
resume digest), and the reallocation log's `from_package`/`to_package`. Packet 1D renames the
parameters that address them. A parameter renamed against a column that was not is a join that
matches nothing, which is the F20/F24 failure this schema already carries scars from.

**`findings.resolve_by` is deliberately left alone**, reversing the draft. It carries no dying
word; only its *meaning* is a stage ordinal, and its comment now says so. Renaming a column that
does not hold the retired word is churn with a migration attached, and the standing rule is that
this change stays targeted.

**Behaviour 9 has two halves and both are data, not structure.** `PRIMARY = "behaviour"` is a
stored `key`, and `BEHAVIOUR = "behaviour"` is a stored `kind` — so after the rename a
`Behaviour` row would have `kind == "behaviour"`, and its `ref` would read
`contracts:40#behaviour`. One word for two things is the same disease as two words for one, and
this project has a schema that already caught the second. The kinds become **`effect`** and
`error`, and `PRIMARY` becomes `effect` — which is also exactly the pair `INTERVIEW.md` §4 uses
to describe what a behaviour list contains ("the main effect, and each specific error"). Two
`UPDATE` statements migrate the stored values.

The second half is the `obligations` array inside contract rows' free-form JSON `content`. It
becomes `behaviours`, because `enumerate_from_row` reads it by that key, the stage-6 methodology
asset instructs the planner to write it by that key, and 1F fails on the word appearing in
either. The migration rewrites the key in place for every contract row that has one; the value
is untouched.

**Order is load-bearing, and three constraints fix it.** The two column drops precede
`DROP TABLE tasks`, or the foreign key is violated. `packages` drops after `tasks`, which
references it. `subtasks` is renamed to `tasks` only after the old table of that name is gone.

**Every index is named explicitly, because renaming a table does not rename its indexes.**
Probed, not assumed — see §4.5. The draft said "each index" and listed one of the three on the
obligation tables, which is the same class of mistake as a check that saw four names where there
were twenty-two.

**Pseudocode**

```
if (current, target) != (7, 8):
    fall through to the existing adjacent-pair table and its ValueError

if any live package beyond the first:
    raise ValueError naming each          # caught by migrate(); the snapshot is restored
if any contract_ref held by two live subtasks:
    raise ValueError naming each

# --- the planning-sense word ---
emit  ALTER TABLE plan_rows RENAME COLUMN package TO stage
emit  DROP INDEX idx_rows_package
emit  CREATE INDEX idx_rows_stage ON plan_rows (stage)
emit  ALTER TABLE gate_runs RENAME COLUMN package TO stage
emit  DROP INDEX idx_gate_runs_package
emit  CREATE INDEX idx_gate_runs_stage ON gate_runs (stage, id)
emit  ALTER TABLE journal_notes RENAME COLUMN package TO stage
emit  DROP INDEX idx_journal_package
emit  CREATE INDEX idx_journal_stage ON journal_notes (stage, id)
emit  ALTER TABLE finding_reallocations RENAME COLUMN from_package TO from_stage
emit  ALTER TABLE finding_reallocations RENAME COLUMN to_package   TO to_stage

# --- the dying levels ---
emit  ALTER TABLE subtasks DROP COLUMN task_id          # the FK to the dying middle level
emit  ALTER TABLE subtasks DROP COLUMN superseded_by    # split lineage
emit  DROP TABLE tasks                                  # takes idx_tasks_package with it
emit  DROP TABLE packages                               # takes idx_packages_live with it

# --- obligation -> behaviour ---
emit  ALTER TABLE obligations           RENAME TO behaviours
emit  ALTER TABLE obligation_ownership  RENAME TO behaviour_ownership
emit  ALTER TABLE obligation_amendments RENAME TO behaviour_amendments
emit  ALTER TABLE behaviour_ownership   RENAME COLUMN obligation_id TO behaviour_id
emit  ALTER TABLE behaviour_ownership   RENAME COLUMN subtask_id    TO task_id
emit  ALTER TABLE behaviour_amendments  RENAME COLUMN obligation_id TO behaviour_id
emit  the three index swaps: idx_obligations_contract -> idx_behaviours_contract,
      idx_obligation_live_owner -> idx_behaviour_live_owner (unique, partial),
      idx_obligation_owner_subtask -> idx_behaviour_owner_task
emit  UPDATE behaviours SET kind = 'effect' WHERE kind = 'behaviour'
emit  UPDATE behaviours SET key  = 'effect' WHERE key  = 'behaviour'
emit  UPDATE plan_rows SET content = json_remove(
          json_set(content, '$.behaviours', json_extract(content, '$.obligations')),
          '$.obligations')
      WHERE table_name = 'contracts' AND json_extract(content, '$.obligations') IS NOT NULL

# --- the sub-task level moves down ---
emit  ALTER TABLE subtask_deps          RENAME TO task_deps
emit  ALTER TABLE task_deps             RENAME COLUMN subtask_id TO task_id
emit  ALTER TABLE subtask_verifications RENAME TO task_verifications
emit  ALTER TABLE task_verifications    RENAME COLUMN subtask_id TO task_id
emit  the two index swaps: idx_subtask_deps_on -> idx_task_deps_on,
      idx_verifications_subtask -> idx_verifications_task
emit  ALTER TABLE subtasks RENAME TO tasks        # the name is free now
emit  DROP INDEX idx_subtasks_state
emit  CREATE INDEX idx_tasks_state ON tasks (state)
emit  CREATE UNIQUE INDEX idx_tasks_contract ON tasks (contract_ref)

emit  the attachment scope collapse            # task 1A.3
```

### Task 1A.2 — the DDL text

**Signature.** None — `schema.DDL` is module-level text, and `SCHEMA_VERSION` becomes 8.

**Behaviours**

| | behaviour |
|---|---|
| 1 | A fresh database and a migrated one end structurally identical. |
| 2 | No `packages` table and no `package_id` column exist anywhere. |
| 3 | `tasks` is the build unit: `contract_ref`, `title`, `state`, `serve_epoch`, and no owning-group column. |
| 4 | The version-7 DDL is retained, as the fixture 1F's parity check migrates *from*. |

**Behaviour 1 already has a mechanism and this change must not break it.** The schema comment at
the terms table records the rule — a migration and a fresh init must create a table from one
text, or the two drift. Every rename in 1A.1 therefore edits `DDL` *and* emits a migration step,
and the equality of the two is what packet 1F's test asserts. **This is the invariant the cold
read caught the draft breaking**, and it is the reason behaviour 1 is stated before the others.

**Behaviour 4 exists because editing the DDL in place destroys the thing the check needs.** 1F
compares a freshly-initialised version-8 database against one migrated from version 7. After
1A.2 there is no version-7 text left in the repository to build the second from. So the v7 DDL
is retained — as text, next to the migration, not as a checked-in binary database, because a
`.db` file is opaque to review and a text fixture diffs.

**And it is retained outside `engine/schema.py`. This sentence was missing and it is load-bearing**
— found by change 3's cold read, which meets the same question a third time (`03-catalogue.md`
§11.4). `_columns()` in `test_schema_vocabulary.py` reads the whole of `schema.py` and regexes
every `CREATE TABLE IF NOT EXISTS` out of it. A retained v7 DDL living there is **phantom schema**
for all five vocabulary tests: it declares `subtasks` and `package_id`, so this change's renames
would be undone as far as those checks can see, and the suite would certify the presence of the
words 1A.1 exists to remove. **1F.3 already assumes this** — it corrects an assertion from
`subtasks` to `tasks`, which a retained v7 DDL in `schema.py` would keep satisfying either way, so
the assumption is currently unstated and unenforced. 3E.1 behaviour 10 is where it finally gets a
test.

**The `task_id` column on the old `subtasks` becomes nothing.** It pointed at the dead middle
level. It was already nullable and already reported rather than guessed when absent, so removing
it loses no truth — but it has to be dropped explicitly in 1A.1, because a table rename preserves
every column it holds.

**A trap the rename creates, named so the reader is not caught by it.** The *old*
`subtasks.task_id` (an owner FK) disappears, while `subtask_deps.subtask_id` *becomes* `task_id`.
After this change, a column called `task_id` means something it never meant before. Every
surviving read of that name is audited in 1C and 1D rather than assumed to still be right.

**`contract_ref` gains the uniqueness the old `source_ref` had.** The old `subtasks.contract_ref`
was deliberately not unique so a split's products could share one. With splitting removed in
packet 1C, one task *is* one contract, and the constraint states that rather than leaving it as
an invariant someone has to remember. Note it constrains non-null values only — SQLite treats
NULLs as distinct in a unique index (probed, §4.5) — so it says "no two tasks share a contract",
not "every task has one".

### Task 1A.3 — the attachment scope collapse

**Signature.** None — migration steps, specified separately because the mapping is the design.

`scope_attachments.scope_level` holds **four** values today: `plan`, `package`, `task`,
`subtask`. Two of the four lose their anchor in this change, not one: `packages` is dropped, and
so is the old `tasks` table that `task` scope keyed. `subtask` becomes the new task level.

**Behaviours**

| | behaviour |
|---|---|
| 1 | `plan` is unchanged. `package` and the old `task` become `plan`. `subtask` becomes `task`. |
| 2 | Each widened row is superseded and replaced, never updated in place. |
| 3 | Each replacement carries `promoted_from` set to its old level and a reason in the migration's own voice. |
| 4 | Where several widened rows land on the same target, one live placement survives and the rest are superseded. |

**Behaviour 2 is not a preference.** The schema states the invariant above the table: "*a target
has exactly one live placement*", and `idx_attachments_live` is **not** a unique index — it is a
lookup index, so nothing stops a second live row. A bulk `UPDATE ... SET scope_level = 'plan'`
would leave a target that had a package-scope and a task-scope attachment holding two live
placements at plan scope, and the invariant would be false with no error anywhere. Supersede-then-
insert is how every other placement change in this table is already written.

**Behaviour 3 answers a refusal the migration would otherwise walk straight through.**
`PromotionNeedsReason` exists because broadening a scope is the free direction and the one that
silently bloats context. A migration that promotes in bulk without a reason is the exact act that
guard was written to make visible. The reason is the migration's, and it says so: *"the build
grouping was removed in schema 8; this attachment was at that level and has been widened rather
than dropped."* One sentence, identical on every row, and honest about being automatic.

**The cost this incurs, recorded because it is real and it is unpopular.** D8 recorded that
forcing subsystem-wide attachments to plan scope is a silent "too high" failure. This does it
deliberately, to every attachment at two of the four levels. See 1D for what that does to the
resume bound, which is the part the draft missed entirely.

### 4.5 Technical claims, probed rather than asserted

The migration and 1F's parity check rest on claims about SQLite, which we do not control. Under
D4 each needs cited documentation, a probe, or recorded acceptance of the risk. All were probed
on the target environment, **SQLite 3.49.1 under Python 3.12.10**:

| claim | result |
|---|---|
| A foreign key in another table follows its parent through `RENAME TO` | **Confirmed.** The clause is rewritten to `REFERENCES "tasks" (id)` and still rejects an orphan insert. |
| `RENAME TO`, `RENAME COLUMN` and `DROP COLUMN` all run inside the runner's `BEGIN IMMEDIATE` | **Confirmed.** |
| `RENAME COLUMN` (needs ≥3.25) and `DROP COLUMN` (needs ≥3.35) are available | **Confirmed** at 3.49.1. |
| A table rename carries its indexes to the new table but **keeps their old names** | **Confirmed** — `idx_subtasks_state` survived pointing at `tasks`. This is why every index is renamed explicitly above. |
| A migrated database and a fresh one have **identical stored DDL text** | **Refuted.** `RENAME COLUMN` substitutes the name into the stored `CREATE TABLE` text in place and keeps the original column padding. Re-aligning the column in `DDL` — which any editor does — leaves `'stage             INTEGER'` fresh against `'stage           INTEGER'` migrated, with identical structure. **This is why 1F compares through `PRAGMA table_info` / `index_list` / `foreign_key_list` and never through `sqlite_master.sql`.** |
| A unique index treats two NULLs as distinct | **Confirmed.** Two NULL `contract_ref` rows both insert under `idx_tasks_contract`. |
| An `id` allocated by the schema is never reused | **Confirmed by construction, not by SQLite.** 29 of the 30 primary keys in the schema declare `AUTOINCREMENT`, which suppresses rowid reuse; the thirtieth is the singleton `plan` table's `guard`, which allocates nothing. A plain `INTEGER PRIMARY KEY` *does* reuse a deleted maximum rowid — probed — which is what `AUTOINCREMENT` is there to prevent. |

**The accepted risk.** These hold for the SQLite bundled with the Python in use. This is a
personal tool with one deployment, so the exposure is a future Python downgrade below 3.35's
SQLite, which would fail loudly on the first migration rather than corrupt anything.

### 4.6 The remaining cross-task answers

Closed from the existing code rather than by new decisions: `_migration_steps` handles **adjacent
pairs only** and raises `ValueError("no migration path from …")` for anything else, so 6→8 is not
supported and needs no composition rule; `migrate()` writes the `schema_version` bump itself, so
the branch must not; the migration emits nothing to the change feed, since the feed carries plan
edits and a schema change is not one.

## 5. Packet 1B — `obligation` → `behaviour`

Depends on 1A. Deliberately second: it is the largest purely mechanical rename, it touches one
module plus its callers, and doing it before the level surgery keeps the two kinds of change from
being reviewed as one diff.

### Task 1B.1 — `BehaviourService` (was `ObligationService`)

**Signature.** Module rename `engine/obligations.py` → `engine/behaviours.py`, and with it
`ObligationService` → `BehaviourService`, `Obligation` → `Behaviour`, `ObligationSpec` →
`BehaviourSpec`.

**Seven of the ten public methods survive**, keeping their names except where the word appears:
`enumerate_from_row`, `freeze_ops`, `for_subtask` → `for_task`, `of_contract`,
`require_enumerated`, `amend`, `amendments`. **Three go**: `uncovered`, `foreign` and
`redistribute_ops`. The draft said "its ten public methods keep their names" and then deleted one
of them in the next table.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Every name carrying `obligation` or `subtask` is renamed — parameters, private helpers and the test module included, per register 13. |
| 2 | `NotEnumerated` and `AmendmentNeedsReason` keep their names. `UnknownObligation` is **deleted**. |
| 3 | `redistribute_ops`, `uncovered` and `foreign` are **deleted**, not renamed. |
| 4 | The kind vocabulary becomes `effect` and `error`, and `PRIMARY` becomes `effect`. |
| 5 | `enumerate_from_row` reads `content["behaviours"]`. |
| 6 | `superseded_at` and the live-ownership unique index stay. |

**Behaviour 3 grew by two methods, and the two came from packet 1C's list.** `uncovered` and
`foreign` were specified as 1C's, on the same argument that deletes `redistribute_ops` here: all
three exist only to account for a split, and splitting dies with the sub-task level. Three
methods with one justification, split across two packets, is a reviewer being asked to check the
same reasoning twice and a maintainer being invited to save one of them. They go together, in the
module that owns them. `require_enumerated`, called on the line above them in `split_subtask`,
does **not** go: it also guards `verify_completion`, which survives.

**Behaviour 2 is a deletion the draft got wrong, and the draft's own argument is what convicts
it.** `UnknownObligation` is defined and raised nowhere — not in this module, not anywhere in the
repository. Renaming it to `UnknownBehaviour` carries a dead symbol into v3 under a fresh name,
which is precisely the reason given three lines earlier for deleting `redistribute_ops`. A
specification that applies its own principle to one dead symbol and not the other is one nobody
read back.

**Behaviour 4 avoids one word meaning two things.** `PRIMARY = "behaviour"` is a stored `key` and
`BEHAVIOUR = "behaviour"` is a stored `kind`, so a `Behaviour` would have `kind == "behaviour"`
and a `ref` of `contracts:40#behaviour`. `effect` and `error` are the pair `INTERVIEW.md` §4
already uses. The stored values migrate in 1A.1 behaviour 9.

**Behaviour 6 is a decision to leave something alone, and it needs its reason recorded because
the opposite is arguable.** Once splitting is gone, nothing supersedes an ownership row, so
`superseded_at` is always NULL and `idx_behaviour_live_owner`'s partial predicate is always true.
That is an argument for dropping both. They stay: the column is what makes the *amendment* path —
retiring a behaviour and vesting a replacement — expressible without a second mechanism, and the
unique index is what states "nothing is owed twice" as a constraint rather than a convention.
A degenerate predicate costs nothing; re-deriving the constraint later costs a migration.

**Pseudocode** — none. This is a rename with four deletions, and every deletion's consequence is
in the behaviour table above. Pseudocode would be the diff written twice, which is the failure
mode D9 warns about.

### Task 1B.2 — the callers

**Signature.** None — this is the other half of 1B.1, specified separately because the draft
called 1B "one module plus its callers" and named none of them.

**Behaviours**

| | behaviour |
|---|---|
| 1 | The three importers rename: `tasks.py`, `surface.py`, `briefs.py` — the `obligations=` constructor keyword, the `self.obligations` attribute, and `_scope_obligations`. |
| 2 | The two docstring references in `errors.py` and `resume.py` are rewritten. |
| 3 | `tasks.py`'s emitted message about a superseded sub-task's obligations is rewritten. |
| 4 | The six test files are updated and `tests/test_obligations.py` becomes `tests/test_behaviours.py`. |

**Behaviour 1's keyword is the one that bites.** `surface.py` passes `obligations=self.obligations`
into another service's constructor; `tasks.py` and `briefs.py` receive it. Caller and callee have
to rename in the same commit or the constructor raises, and a keyword argument is not something
the export surface shows you.

## 6. Packet 1C — the level surgery in `tasks.py` and `briefs.py`

Depends on 1A and 1B. The largest packet, and the only one with real design in it.

**The class is `TaskGraphService`.** The draft wrote `TaskService` three times. It keeps its name:
it derives and serves the graph, and that is still what it does.

### Task 1C.1 — the build grouping is deleted

**Behaviours**

| | behaviour |
|---|---|
| 1 | Three functions go: `declare_package`, `assign_task`, `packaging`. |
| 2 | Four models go: `Package`, `Task`, `PackageCut`, `Packaging`. |
| 3 | Two errors go: `PackageNotFound`, `UnpackagedTask`. |
| 4 | Two helpers go: `unpackaged_tasks`, `_guard_packaging`. And `_owning_task_id`, which resolved the dropped FK. |
| 5 | **Three** registry rows are removed, and `finalize_plan`'s `required_packages` parameter is removed from a fourth. |
| 6 | **Three** `Absence` entries are removed — the registry's record of *why* a call is not exposed. |
| 7 | No text the tool emits names any of them. |

**The counts are the correction, and the miscount is the finding.** The draft said "both
functions", "their models `Package` and `Task`", "their two surface tools" and "their two
`Absence` entries". Every one of those numbers was low: `packaging()` is a third registered tool
with a third absence entry, and it is the sole caller of `unpackaged_tasks` and the only
constructor of `PackageCut` and `Packaging`. A specification that says "two" where the registry
says three is the same defect as a check that saw four names where there were twenty-two — it
reads as complete and is not, and nothing downstream can tell.

**Behaviour 6 is not tidying.** The registry carries a deliberate list of calls that exist but
are not on the surface, each with the reason. Leaving an absence entry for a function that no
longer exists is a citation to nothing, which is the defect where a mandate told every cold
planner to resume from a call that does not exist.

**Behaviour 7 is enforced by a mechanism, not by care, and that is why it is stated as its own
behaviour.** `door.scan` runs over every tool response and raises `UnreachableCall` for any
`name()` in the payload that the registry cannot resolve. `_guard_packaging`'s message says
"declare_package() then assign_task() for each" — deleting the calls while that string survives
turns a message into a crash. The same mechanism is what makes packet 1E mandatory rather than
cosmetic.

### Task 1C.2 — `TaskGraphService.finalize_plan`

**Signature.** `finalize_plan(self) -> TaskGraph` — the `required_packages` parameter is removed.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Derives one task per live contract row, inserting as it does today. |
| 2 | Refuses with `GatesIncomplete` naming the stage, when the terminal stage gate has not passed. |
| 3 | Refuses with `UnresolvedFindings` when a finding is neither addressed nor accepted. |
| 4 | Refuses with `CycleDetected` naming the cycle, before anything is written. |
| 5 | **No longer refuses** a plan whose tasks have no group. That refusal dies with the level. |
| 6 | Freezes each task's behaviour surface at derivation, in the same transaction as the insert. |
| 7 | Moves the plan from `draft` to `finalized`, and captures the drift fingerprint. |
| 8 | Returns a `TaskGraph` of `order`, `tasks`, `edge_count`, `resurfaced_warnings` and `unenumerated`. |

**The hole this task must answer, and the draft's answer was false.** `_guard_gates` currently
takes the caller's list of packages to require. With no packages, *which* gates must have passed?
The draft said "the interview's stages are the standard set, so finalization requires every stage
gate — that is what the old default did when the caller passed nothing." **It is not.** The code
reads `if self.gates is None or required_packages is None: return`. Passing nothing checked
**zero** gates. So requiring every gate is a new decision that would refuse plans which finalize
today, and it was presented as a citation.

**The answer, derived rather than invented: finalization requires the terminal stage gate, and
nothing else.** The terminal gate already folds in every earlier one — `gate_criteria.yaml`
gives stage 8 a `prior_gates_green` criterion, and `_c_prior_gates_green` re-runs every earlier
gate's *criteria* rather than calling `run_gate`, deliberately. Requiring the terminal gate
therefore requires all of them, through the mechanism that already exists, with one gate number
in the error instead of eight. Requiring the whole list separately would re-implement
`prior_gates_green` in `tasks.py` and give two answers to "did the plan pass its gates".

**Behaviour 4's placement is the second correction.** The draft's pseudocode upserted every task
and froze its behaviours, *then* derived dependencies, *then* raised `CycleDetected` — so a
cyclic plan would leave task rows behind and a refusal would be a partial write. It also said
"upsert" while behaviour 1 said "as before", and before is an insert. Guards, derivation and the
topological sort all complete before the first `write_atomic`, as they do today.

**Two transactions, and the seam is deliberate.** Register 3's default is one, and this call
overrides it with a reason: the nodes must exist before the edges can reference them by id, and
the plan-state flip rides with the edges so that a plan is never `finalized` with no graph. The
override is recorded here rather than left as something the reader discovers in the code.

**Pseudocode**

```
guard_gates()                        # the terminal stage gate only; see above
guard_findings()

specs  = live rows where table == 'contracts'
edges  = typed depends_on links between them, consumer -> provider
order  = toposort(specs, edges)      # raises CycleDetected naming the cycle

ops = []
unenumerated = []
for ref, title, content in specs:
    node = len(ops)
    ops += insert task(contract_ref=ref, title=title, state=PENDING, serve_epoch=0)
    specs_for_row = behaviours.enumerate_from_row(content)
    if specs_for_row:
        ops += behaviours.freeze_ops(ref, specs_for_row,
                                     FromOp(node, "id"), base_index=len(ops))
    else:
        unenumerated += ref
write_atomic(ops, key("finalize", "nodes"))

dep_ops = [insert task_deps(task_id, depends_on) for each edge, resolved by contract_ref]
dep_ops += update plan set state = 'finalized'
write_atomic(dep_ops, key("finalize", "edges"))

capture_fingerprint("finalization")
return TaskGraph(order, tasks, edge_count, resurfaced_warnings, unenumerated)
```

**Behaviours 7 and 8 are in the pseudocode because they were missing from the draft entirely.**
The plan-state transition is the sole firing of the `finalize` event — until it existed nothing
wrote `finalized`, which left the revision loop unreachable. The fingerprint is the drift
baseline. And `TaskGraph`'s five fields are named here because the register's own worked example
is that return-type fields are a hole in every task: four types named and none defined is v2's
recorded defect, and a specification that says "returns a `TaskGraph`" repeats it.

### Task 1C.3 — `BriefService.split_subtask` — deleted

**Behaviours**

| | behaviour |
|---|---|
| 1 | The function goes, with its registry row and the `split` payload parser that exists only for its parameter. |
| 2 | Three errors go: `ObligationsNotCovered`, `ObligationsNotOwned`, `NothingToSplit`. |
| 3 | The supersession machinery goes: the `superseded_by` field, `is_live`, `guard_live`, `SubTaskSuperseded`, and `_dependants`. |

**Behaviour 2 corrects a name that does not exist.** The draft removed "its error
`PartsDontCover`". There is no such class. `PartsDontCover` is what the *frozen plan* calls the
error; `briefs.py` says so in a docstring and names the class `ObligationsNotCovered`, with a
mirror `ObligationsNotOwned` and a third, `NothingToSplit`, that the draft never mentioned. One
error named that is not there, three real ones unnamed — and the same phantom is the subject of a
`GLOSSARY.md` vocabulary exception — which now simply stops mattering, since 1A.0 deletes the check
that reads those exceptions and leaves the document unedited. The three are **deleted, never renamed**,
so 1B's rename does not touch them.

**Behaviour 3 is the part that reaches outside this packet.** `guard_live` exists so a superseded
node cannot be served, reported on or verified — three call sites in the serve and report paths.
With nothing able to supersede a task, the guard is dead and the paths that call it lose a
branch. That is why it is named here rather than left to whoever notices.

**Why the whole cluster goes rather than just the entry point.** The split existed because a v2
sub-task was one contract, which was not a servable size. A task is now one function, so there is
nothing to split. Keeping any of it would leave machinery whose reason for existing has been
removed, which is what D7 says about a level that owns nothing.

### Task 1C.4 — the name moves down

**Behaviours**

| | behaviour |
|---|---|
| 1 | `SubTask` becomes `Task`, in the slot the deleted grouping model vacated. |
| 2 | `SubTaskNotFound` becomes `TaskNotFound`. |
| 3 | `TaskGraph.subtasks` becomes `TaskGraph.tasks`; every `subtask_id` parameter becomes `task_id`. |
| 4 | `TaskGraphService` keeps its name. |

**This task exists because no packet claimed the change's stated purpose.** "The name `tasks`
moves *down* onto what a builder is handed" is the second bullet of §1, 1A moves the *table*, and
nothing anywhere moved the model, the error or the graph field. Four packets specified in detail
and the headline rename was in none of them.

**Behaviour 1's ordering is not free.** `Task` is a live model until 1C.1 deletes it, so the
rename lands after that deletion, in the same packet, and never in a commit where both exist.

## 7. Packet 1D — the reporting layer

Depends on 1C. `gates.py`, `gaps.py`, `resume.py`, `guidance.py`, `findings.py`,
`attachments.py`, `methodology/__init__.py`, and the registry rows that name them.

### Task 1D.1 — the methodology module

**Signature.** `Methodology.packages` → `stages`, `Package` → `Stage`, `criteria_for(package)`
→ `criteria_for(stage)`, `package(number)` → `stage(number)`, `package_range` → `stage_range`,
`Criterion.package` → `Criterion.stage`, **`Rule.package` → `Rule.stage`**.

**`Rule.package` was missing from this list until the cold read of change 2 tripped over it.**
`gaps.py` reads `rule.package` when it builds a gap, so a `Rule` renamed without its reader is an
`AttributeError` on every gap the engine derives — and `Gap.package` (1D.2 behaviour 2) is the
other half of the same pair. Two dataclass fields, one read apart, in two modules this packet
already claims.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Every accessor renames; the numbering and the file order are untouched. |
| 2 | The manifest's `packages:` key and the criteria file's `package:` key become `stages:` and `stage:`. |
| 3 | No gate outcome changes. |

**This task is first in its packet because four other modules cannot compile without it.**
`gates.py`, `findings.py`, `gaps.py` and `guidance.py` all read `methodology.package_range`; the
draft listed none of them as depending on a module it never mentioned.

**Behaviour 2 has a precedent in the repository, which is worth knowing before writing it.**
`engine/methodology/rev2/gate_criteria.yaml` is keyed by `stage:` and says "every earlier stage
gate passes". `stage` was the original word; v2 renamed it to `package` and rev3 carries the
result. This is a revert, and rev2 is a working example of the target shape.

### Task 1D.2 — stage-scoped reads

**Behaviours**

| | behaviour |
|---|---|
| 1 | Every parameter, column reference and message reading `package` in the *planning* sense reads `stage`. |
| 2 | `UnknownPackage` becomes `UnknownStage`; `GateResult.package` and `next_package` become `stage` and `next_stage`; `Gap.package` becomes `Gap.stage`. |
| 3 | `gaps.current_package()` becomes `current_stage()`; `guidance.get_package_script()` becomes `get_stage_script()`. |
| 4 | `findings.resolve_by` keeps its name; only its comment changes. |
| 5 | No behaviour changes. A gate that passed before passes now. |

**Behaviour 2 crosses a module boundary and the draft's module list did not.** `UnknownStage` and
`GateResult`'s fields are what a caller sees, so the registry row and any client change with
them.

**Behaviour 3 is a tool rename, which makes it emitted text as well as an identifier.**
`get_package_script` is a registered tool with a `Param("package")`, and `resume.py` writes
`f"get_package_script({package})"` into the digest a resuming planner reads. `door.scan` resolves
that name against the registry, so the tool row, the parameter and the digest string rename in
one commit or the digest raises `UnreachableCall`.

**Behaviour 4 reverses the draft**, which renamed the column "to say so". See 1A.1: it holds no
dying word, and a migration to improve a comment is not a trade this change should make.

### Task 1D.3 — attachment scope, and what it costs resume

**Behaviours**

| | behaviour |
|---|---|
| 1 | The constants become `PLAN` and `TASK`. `PACKAGE` and the old `TASK` go. |
| 2 | `UnknownScopeLevel`'s message names the two surviving levels. |
| 3 | `context_for(task_key="")` replaces the three-keyword signature. |
| 4 | A caller passing the removed levels is refused by name, not silently widened. |

**The draft was wrong about this module in three ways and they compound.** It said the levels
were "project / package / task": the top level is **`plan`**, not `project` — and `project` is a
retired word that stays retired, now by this sentence rather than by a check (1A.0) — there are
**four** levels and not three, and
**two** of them lose their anchor rather than one, because the old `task` level keyed the `tasks`
table that 1A drops. Three of the four levels change meaning or die, and the draft named one.

**What this does to the resume bound, which the draft did not record.** `attachments.py` states
its own purpose: resume cost that scales with session history is worse than the plan-size scaling
`requirements:62` exists to kill, every candidate bound is arbitrary invention, and the fix is
that "resume serves plan ∪ current-package ∪ current-task ∪ current-subtask, and **the bound is
structural**". With two levels the union is plan ∪ current-task, and everything formerly at
package or old-task scope now sits at plan scope — where it is served to **every** task. The
structural bound survives in form and is materially weaker in fact.

**That is the price of D7 and it is paid here.** The alternative is inventing a grouping to hold
those attachments, and re-introducing packages under another name is exactly what D7 rejected.
D8 already recorded that forcing subsystem-wide attachments to plan scope is a silent "too high"
failure; this makes it loud by writing it down in advance. **If briefs start arriving bloated,
that is evidence against D7 and it should be logged as a finding, not fixed by adding a level
back quietly.** The instrument already exists: `compose_brief` makes the composer omit an
allocated row *with a reason*, in a log the owner reads. A rising count of omission reasons on
plan-scope rows is what this failure looks like, and it is countable.

### Task 1D.4 — `resume.py` and `guidance.py`

**Behaviours**

| | behaviour |
|---|---|
| 1 | The digest's stage line, journal scoping and gate history read `stage`. |
| 2 | `_package_of` is deleted, and the brief composer's context call passes one key. |
| 3 | `guidance.py`'s script accessor and its module docstring rename. |

**Behaviour 2 is a deletion the draft could not have seen from its module list.** `_package_of`
walks a sub-task to its task to its package — through `subtasks.task_id` and `tasks.package_id`,
both of which 1A drops. It lives in `briefs.py`, not in this packet's modules, and it is the
caller that makes 1D.3's signature change land.

## 8. Packet 1E — the methodology assets

Depends on 1C and 1D. **This packet was not in the draft at all, and without it the tool breaks
at runtime rather than merely reading oddly.**

### Task 1E.1 — methodology revision 4

**Behaviours**

| | behaviour |
|---|---|
| 1 | `rev3` is copied to `rev4` and edited there; `rev3` is left untouched. |
| 2 | The eight assets are renamed `stage1_context.md` … `stage8_finalization.md`. |
| 3 | Every `package` in asset prose and in the manifest becomes `stage`; every `obligation` becomes `behaviour`; the contract row's array is `behaviours`. |
| 4 | The stage-6 script stops naming `declare_package()`, `assign_task()` and `packaging()`. |
| 5 | **The stage-6 packaging round is deleted, not just its call names**, and the stage is left with no mandatory grouping. |
| 6 | The revision stamp is 4, and `plan_status` reports it. |

**Behaviour 5 is change 4's correction applied here (`builds/04-labels.md` §11.3), and without it
behaviour 4 leaves the round standing.** `rev3/package6_architecture.md`'s round is more than the
three calls behaviour 4 strips: its prose says *"Every component is a task, and every task belongs
to exactly one package… this is the one grouping a human chooses rather than derives"*, and **that
sentence names no call**, so removing call names leaves it untouched. A planner would read a stage
instructing them to cut packages, with no tool that cuts one. **The whole round goes**, and stage 6
keeps its architecture work and loses its grouping round — which is what `INTERVIEW.md` §7 already
says: *"Stage 6 loses the packaging round and the mandatory package cut… It gains labels."*

**What fills the hole is change 4's**, and it is named here so the two changes do not each assume
the other did it: revision 6 adds a labelling round in the same place, and this change leaves the
place empty rather than half-filled. A residual packaging round surviving into rev6 would sit
beside the round that replaced it.

**Behaviour 4 is why this packet exists, and it is a correctness break, not untidiness.**
`rev3/package6_architecture.md` tells the planner: "`declare_package()` each one the user agrees
to, then `assign_task()` every component into it. `packaging()` shows the cut so far". That text
is served through `get_stage_script`, and every tool response goes through `door.scan`, which
raises `UnreachableCall` for a call name the registry cannot resolve. After 1C removes those
three tools, **serving stage 6's script raises**. The interview stops at stage 6.

**Behaviour 1 answers the question the cold read raised as a hole: edit in place, or mint a new
revision?** Editing `rev3` in place retroactively changes what already-run sessions were scripted
with, and the revision stamp exists precisely so that a plan can say which methodology produced
it. Minting rev4 costs one directory copy. That is not a close call, and the only reason it
looked like one is that `PLAN.md` item 10 had reserved the number.

**What this does to `PLAN.md` item 10, stated plainly because it is a change to the plan.** Item
10 deferred "methodology revision 4 — all eleven stage scripts, the mandate, and a forward-only
migration" to last, so it would be "written once against what was actually built, rather than
rewritten after every change". That reasoning stands for the **eleven-stage rewrite**, which is
genuinely a function of what gets built. It does not stand for the vocabulary, because the door
turns stale asset text into a failed call the moment 1C lands. So revision 4 is this: the same
eight stages, correctly worded, with the dead calls removed. Item 10 becomes **revision 5**, the
eleven-stage rewrite, and it keeps its position and its reasoning.

**Behaviour 2 renames the files, and rev2 shows the shape.** `engine/methodology/rev2/` is
already keyed by `stage`, from before v2 retired the word. This is a revert to a spelling the
repository has used before, not an invention.

## 9. Packet 1F — schema parity

Depends on all of the above. Last, because it is the thing that proves the rest landed.

### Task 1F.1 — struck 2026-07-30

**This was the banned-word enforcement test, rewritten to scan `engine/` and `tests/` for
`package`, `subtask` and `obligation`, taking its word list from `GLOSSARY.md`. It is not built.**

The owner ruled that `GLOSSARY.md` is a transitional document used to help write v3 and that **v3
code reads only the `terms` table**; a test parsing that file for a ban list is the mechanism he
struck, not an exception to it. `04-glossary-and-labels.md` §4.1 carries the decision and its
reasoning. 1A.0 now deletes the existing version of this test rather than rewriting it, and **no
replacement is specified** — see 1A.0 for what is given up and why that is the decision.

**Three findings from this task's cold read are recorded here rather than lost, because each is a
live trap the next mechanical check in this project will walk into:**

- **`sub_task` cannot be banned as a word.** The check tokenises, `sub_task` splits to
  `{sub, task}`, and `task` must stay legal because it is the surviving level. A rule that cannot
  fire is the disease this whole change is about, and the draft shipped one inside the behaviour
  table of the test meant to catch it.
- **Read-only quotations are excluded by path, never by content.** `spec/v2/` and
  `engine/methodology/rev2/` are quotations; deciding by content whether a document "records why a
  word was retired" is a judgment, and this project does not put judgment in a check.
- **A list going missing and a scanner going blind are two guards, not one.** The second is the
  failure to beat: a check that ran green while seeing four names where there were twenty-two.
  Any future scanner needs a floor on what it found, asserted by its own fixture.

### Task 1F.2 — schema parity

**Behaviours**

| | behaviour |
|---|---|
| 1 | Builds a version-7 database from the retained v7 DDL, migrates it to 8, and initialises a fresh 8. |
| 2 | Compares the two through `PRAGMA table_info`, `index_list` and `foreign_key_list` — never through `sqlite_master.sql`. |
| 3 | Fails naming the table and column that differ. |

**Behaviour 2 is probed, and the obvious implementation is the wrong one.** Comparing stored DDL
text fails on a structurally identical pair: `RENAME COLUMN` substitutes the new name into the
stored `CREATE TABLE` text and keeps the original column padding, so a re-aligned `DDL` gives
`'stage             INTEGER'` fresh against `'stage           INTEGER'` migrated. Probed at
SQLite 3.49.1 — §4.5. A parity check that fails on whitespace gets disabled within a week, which
is how a check becomes theatre.

**This is its own task, not a behaviour of 1F.1, because it is not about vocabulary.** The draft
had it as behaviour 4 of the vocabulary test on the grounds that it "has no other home". A
schema-parity check inside a file named for vocabulary is the two-things-under-one-name defect
this change is spending 710 lines to remove.

### Task 1F.3 — the two checks the change breaks

**Behaviours**

| | behaviour |
|---|---|
| 1 | `test_schema_vocabulary.py`'s existence assertion names `tasks`, not `subtasks`. |
| 2 | Its junction-table exemption list names `task_deps`, not `subtask_deps`. |

**Behaviour 2 is the dangerous one and it fails silently.** The exemption list is a set of table
names; after the rename `subtask_deps` matches nothing, so `task_deps` is no longer exempt and
the "every table records when its rows were created" check starts failing — or, if the assertion
were the other way round, would start passing vacuously. A set membership test against a renamed
string is exactly the borrowed-check failure this repository has recorded before: the check keeps
running and quietly measures something else.

## 10. The cold read, and what it cost

Packet 1A was read blind before anything was built. Packets 1B to 1F were read blind afterwards,
one reader each, given the packet's specification, the conventions register, and the source a
builder would actually hold. All five readings reported **zero tool uses**, so none of them
opened this file or the decisions record.

**What it returned across the five packets:** four independent readings, each listing 27 to 44
decisions, and between them 11 factual errors about the existing code, 5 internal contradictions
and 11 cross-task holes. The conventions register absorbed the recurring noise as designed —
error surfacing, logging, connection scope, timestamps, identifiers, empty input — which is what
kept the lists at forty rather than the calibration's sixty.

**The errors it found in the specification, all of them checkable and all of them checked:**

- `PartsDontCover` does not exist. Three real errors were unnamed and a phantom was scheduled for
  deletion — and a `GLOSSARY.md` vocabulary exception has been protecting the phantom.
- `TaskService` does not exist; the class is `TaskGraphService`.
- **Four miscounts in one packet.** Two functions where there are three, two models where there
  are four, two registry rows where there are three plus a parameter, two absence entries where
  there are three.
- "Requiring every stage gate is what the old default did." The old default checked **zero**.
- `attachments.py` has four scope levels, not three; the top one is `plan`, not `project`; two
  of them die, not one.
- "`redistribute_ops` has no caller." It has one until the next packet.
- "Ten public methods keep their names", in a packet that deletes one of the ten.
- `UnknownObligation` is raised nowhere, and was scheduled for a rename rather than deletion, in
  the same table as a deletion justified by that exact argument.

**The holes it found that no packet owned:** the `SubTask` → `Task` rename, which is the change's
stated purpose; `GLOSSARY.md`, whose ban on `stage` fails the suite on the first commit; the
methodology module, which four claimed modules cannot compile without; seven more schema objects
carrying the planning-sense word; the `obligations` key inside contract-row JSON; the methodology
assets, whose stale text turns into a raised `UnreachableCall`; and the resume bound, which this
change materially weakens without recording it.

**Four claims about SQLite were probed rather than argued.** One was **refuted**: a migrated
database and a fresh one do *not* have identical stored DDL text, which would have made 1F.2 fail
on whitespace and be disabled. Two others confirmed the unique index's NULL semantics and that
`AUTOINCREMENT` — on 29 of the schema's 30 primary keys — is what makes "ids are never reused"
true, since a plain `INTEGER PRIMARY KEY` reuses a deleted maximum rowid.

**And it found four defects in the conventions register itself**, which matter more than any one
packet: entries 3, 5, 6 and 7 described a plausible design rather than the code — an injected
clock, a surface that only cites contracts, one transaction per call, one id mechanism. They were
drafted from the calibration's reconstructions instead of from the source. A wrong entry is wrong
across every task that cites it and is invisible, because a cited decision stops being reported.
`CONVENTIONS.md` §3 now carries the correction and the rule that follows from it: **an entry must
quote the code or the schema it records.** The same reading also showed the register is
service-shaped and settles nothing for a task whose deliverable is a test.

**What it cost:** five blind readings, about four minutes of wall clock, before a line of code
existed. Every one of the eleven factual errors would otherwise have been found by a failing
migration, a failing import, or — in the case of the methodology assets — by an interview that
stopped at stage 6 with an error message about a call that does not exist.

**The residue, stated rather than hidden.** Around forty task-local items stay uncited and stay
that way: whether the precheck is its own helper, whether drops carry `IF EXISTS`, the wording
inside the naming discipline, which file a helper lives in, the exact text of a rejection message.
Under the depth rule those are the implementer's, and the specification is finished when only
they and the register's entries remain. That is now true of all six packets.

## 11. Not in this change

`labels` (change 4) take over the filtering job packages did. They are **not** built here, so
between this change and change 4 there is no way to filter a review list. That is accepted: the
alternative is holding the level alive across two changes, which means writing the migration
twice.

The **eleven-stage interview** is not built here either. Revision 4 is the existing eight stages
with the vocabulary corrected and the dead calls removed; the eleven-stage rewrite is the last
item of `PLAN.md` §4, which is **revision 7** by the time changes 2 and 4 have each minted one.

## 12. What the build found, 2026-07-31

Built as specified, in the landing order §3.5 gives, six commits and one pull request. **533
tests green at the end and green nowhere in the middle**, which is what §3.5 said to expect.
Nine things the specification did not say, each recorded with what it cost.

**Two schema objects the behaviour tables missed, found by enumerating rather than reading.**
`briefs.subtask_id` (with `idx_briefs_subtask`) and `workspace_fingerprints.subtask_id` carry
the dying word and appear in none of 1A.1's twelve behaviours. Both are renamed, because 1C
and 1D rename the parameters that address them and a parameter renamed against a column that
was not is the F20/F24 join that matches nothing. **The method that found them is worth
keeping: parse every `CREATE TABLE`/`CREATE INDEX` out of `schema.py` and grep the *names*,
rather than reading the list and believing it.** §4.5's index rule was written from exactly
that lesson and the column list was not.

**A third, one level down: the generated behaviour key.** `enumerate_from_row` keyed the
second and later entries of a bare string list `o1`, `o2` — an `o` for the retired word. It
now generates `b1`, `b2`, and the migration moves the stored ones with `key GLOB 'o[0-9]*'`.
Leaving them would have had the store and the code disagreeing about the key of the same
behaviour, which is what `UNIQUE (contract_ref, key)` exists to make impossible.

**`contracts:40` needed an `EXCLUDED` entry and no packet said so.** 1C.3 deletes
`split_subtask`; the surface's coverage test subtracts `EXCLUDED` from the 39 contracts the
frozen plan sends to the surface, so deleting the tool without the entry reports a shortfall
with no explanation. Added with its reason, and `test_thirty_six_are_required` becomes
thirty-five.

**rev3 had to become unloadable, which 1E did not say.** 1D.1 makes the loader read `stages:`,
so rev3's `packages:` manifest raises a bare `KeyError` — the exact shape F43 ruled on for
rev2. `EARLIEST_LOADABLE_REVISION` is 4 and the refusal is typed, so "retained as frozen
provenance and deliberately not loaded" is what a caller is told.

**A check pinned to a directory name, found the same way F37 was.**
`test_surface.py::calls_named_in_rev3` scanned `engine/methodology/rev3` by name. After 1E it
would have gone on passing green against a frozen archive while the *served* scripts named
calls the registry cannot resolve — a check measuring something narrower than its name, which
is the failure this repository has recorded three times. It now scans `load().root`.

**F39's regression test tested a mechanism this change deletes.** It drove
`declare_package` → `assign_task` → `packaging`. The instance is gone and the class is not, so
it is replaced by the question F39 actually asks: can a plan authored through this surface be
finalized through it? The answer was "no" for a month and nothing noticed.

**`SHAPES`'s comment cited two columns that no longer exist** (`package_id`, `subtask_id`) as
its examples of legitimately per-table `_id` stems. Corrected to `brief_id`/`task_id`. A
convention illustrated by examples that have been deleted is one nobody can check.

**The parity fixture needs a guard of its own, and 1F.2 did not specify one.** A retained v7
DDL quietly edited to the current shape makes the parity check pass by comparing schema 8
against schema 8 — a check that cannot fail. `test_the_retained_ddl_is_the_version_it_claims`
asserts the fixture still holds `subtasks`, `packages` and `obligations`.

**Found by driving, pre-existing, and not fixed here because it is not this change's:
`serve_brief` is not on the surface.** The registry exposes `finalize_plan`, `graph_status`,
`next_task`, `verify_completion` and `report_status`. `verify_completion` requires
`in_progress`; the only call that reaches `in_progress` is `serve_brief`, which no tool
exposes. So through the shipped surface a task can be derived and offered and can never be
verified or completed — F39's shape exactly, in the execution half, and it was true before
this change. It belongs to change 7's build surface. **Raised rather than silently repaired.**
