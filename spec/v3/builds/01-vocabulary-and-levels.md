# Change 1 — vocabulary and levels

**Specification. No code until this is settled and cold-read.** First of the ten changes in
`PLAN.md` §4, and the one everything else sits on.

Written at the depth `INTERVIEW.md` §8 defines: tasks, their behaviours, and pseudocode, with
every decision either cited, covered by `CONVENTIONS.md`, or named here as a hole and answered.

---

## 1. What this change does

Three level changes and one rename, from D5, D7 and D16:

- **`package` is removed** as a build grouping — the table, the ids, the level, mandatory
  membership, the finalization refusal, and the two calls that declare and assign it.
- **`subtask` is removed** as a level. The name `tasks` moves *down* onto what a builder is
  handed.
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
| `findings.py` | 23 |
| everything else | 40 across 11 modules |

566 lines across 20 modules. That is why this is five packets and not one.

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

## 4. Packet 1A — schema and migration

Schema version 7 → 8. Nothing else in this change can start until this lands.

**This packet was cold-read before anything was built, and the first draft failed.** The reader
returned 74 decisions, 26 uncited, 16 of them cross-task, and found one outright bug: the draft
renamed `subtasks` to `tasks` and separately required the surviving table to carry no `task_id`
column — but a rename preserves every column, so `task_id` would have survived into the migrated
store and not into a fresh one, breaking the very invariant task 1A.2 exists to hold. It also
caught that the draft's behaviour list ordered drops the pseudocode never emitted. What follows
is the corrected specification; §4.4 records what was probed to close the rest.

### Task 1A.1 — `Storage._migration_steps`, the 7→8 branch

**Signature.** Unchanged: `_migration_steps(self, current: int, target: int) -> list[str]`.
Gains one branch.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Renames `plan_rows.package` to `stage`, preserving every value, and replaces `idx_rows_package` with `idx_rows_stage`. |
| 2 | Drops `subtasks.task_id` and `subtasks.superseded_by` before anything else references them. |
| 3 | Drops the old `tasks` table and then `packages`, in that order. Their indexes go with them. |
| 4 | Renames the three obligation tables, the two obligation-named columns, and all three obligation-named indexes. |
| 5 | Renames `subtask_deps`→`task_deps` and `subtask_verifications`→`task_verifications`, their `subtask_id` columns to `task_id`, and their indexes. |
| 6 | Renames `subtasks` to `tasks` and replaces `idx_subtasks_state` with `idx_tasks_state`. |
| 7 | Adds a unique index on `tasks.contract_ref`. |
| 8 | **Refuses**, before any write, a plan holding more than one live declared package, naming each. |
| 9 | **Refuses**, before any write, a plan in which two live sub-tasks share a contract, naming them. |

**Behaviour 8 is a decision, not a detail.** The standing migration rule is that a migrated value
must be a truth the old store already implied, never one invented to satisfy a constraint.
Collapsing several declared packages into nothing invents the claim that the owner's grouping
meant nothing. One live package migrates silently — that grouping *is* the whole plan, already
implied. Two or more is refused, and the owner retires what he does not want. Refusing costs
almost nothing because exactly one such database exists.

**Behaviour 9 is the same shape, and it is new.** A unique index on `contract_ref` is only
correct because splitting dies in packet 1C — the old column was deliberately *not* unique
precisely so a split's products could share a contract. A store that still holds a split would
have its second task silently rejected by the index, so the migration checks first and says so.

**Behaviour 2's placement is the bug the cold read found.** `subtasks.task_id` is a foreign key
to the old `tasks` table, so it must go before that table is dropped, and it must go explicitly —
the later rename carries every surviving column with it. `superseded_by` held split lineage and
dies with the split for the same reason `redistribute_ops` does.

**Pseudocode**

```
if (current, target) != (7, 8):
    fall through to the existing adjacent-pair table and its ValueError

if any live package beyond the first:
    raise ValueError naming each          # caught by migrate(); the snapshot is restored
if any contract_ref held by two live subtasks:
    raise ValueError naming each

emit  ALTER TABLE plan_rows RENAME COLUMN package TO stage
emit  DROP INDEX idx_rows_package
emit  CREATE INDEX idx_rows_stage ON plan_rows (stage)

emit  ALTER TABLE subtasks DROP COLUMN task_id          # the FK to the dying middle level
emit  ALTER TABLE subtasks DROP COLUMN superseded_by    # split lineage
emit  DROP TABLE tasks                                  # takes idx_tasks_package with it
emit  DROP TABLE packages                               # takes idx_packages_live with it

emit  ALTER TABLE obligations           RENAME TO behaviours
emit  ALTER TABLE obligation_ownership  RENAME TO behaviour_ownership
emit  ALTER TABLE obligation_amendments RENAME TO behaviour_amendments
emit  ALTER TABLE behaviour_ownership   RENAME COLUMN obligation_id TO behaviour_id
emit  ALTER TABLE behaviour_ownership   RENAME COLUMN subtask_id    TO task_id
emit  ALTER TABLE behaviour_amendments  RENAME COLUMN obligation_id TO behaviour_id
emit  the three index swaps: idx_obligations_contract -> idx_behaviours_contract,
      idx_obligation_live_owner -> idx_behaviour_live_owner (unique, partial),
      idx_obligation_owner_subtask -> idx_behaviour_owner_task

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
```

**Order is load-bearing, and three constraints fix it.** The two column drops precede
`DROP TABLE tasks`, or the foreign key is violated. `packages` drops after `tasks`, which
references it. `subtasks` is renamed to `tasks` only after the old table of that name is gone —
which is why the draft's `build_tasks` intermediate hop is unnecessary and has been removed.

**Every index is named explicitly, because renaming a table does not rename its indexes.**
Probed, not assumed — see §4.4. The draft said "each index" and listed one of the three on the
obligation tables, which is the same class of mistake as a check that saw four names where there
were twenty-two.

### 4.4 Technical claims, probed rather than asserted

The migration rests on four claims about SQLite, which we do not control. Under D4 each needs
cited documentation, a probe, or recorded acceptance of the risk. All four were probed on the
target environment, **SQLite 3.49.1 under Python 3.12.10**:

| claim | result |
|---|---|
| A foreign key in another table follows its parent through `RENAME TO` | **Confirmed.** The clause is rewritten to `REFERENCES "tasks" (id)` and still rejects an orphan insert. |
| `RENAME TO`, `RENAME COLUMN` and `DROP COLUMN` all run inside the runner's `BEGIN IMMEDIATE` | **Confirmed.** |
| `RENAME COLUMN` (needs ≥3.25) and `DROP COLUMN` (needs ≥3.35) are available | **Confirmed** at 3.49.1. |
| A table rename carries its indexes to the new table but **keeps their old names** | **Confirmed** — `idx_subtasks_state` survived pointing at `tasks`. This is why every index is renamed explicitly above. |

**The accepted risk.** These hold for the SQLite bundled with the Python in use. This is a
personal tool with one deployment, so the exposure is a future Python downgrade below 3.35's
SQLite, which would fail loudly on the first migration rather than corrupt anything.

### 4.5 The remaining cross-task answers

Closed from the existing code rather than by new decisions: `_migration_steps` handles **adjacent
pairs only** and raises `ValueError("no migration path from …")` for anything else, so 6→8 is not
supported and needs no composition rule; `migrate()` writes the `schema_version` bump itself, so
the branch must not; the migration emits nothing to the change feed, since the feed carries plan
edits and a schema change is not one.

### Task 1A.2 — the DDL text

**Signature.** None — `schema.DDL` is module-level text, and `SCHEMA_VERSION` becomes 8.

**Behaviours**

| | behaviour |
|---|---|
| 1 | A fresh database and a migrated one end structurally identical. |
| 2 | No `packages` table and no `package_id` column exist anywhere. |
| 3 | `tasks` is the build unit: `contract_ref`, `title`, `state`, `serve_epoch`, and no owning-group column. |

**Behaviour 1 already has a mechanism and this change must not break it.** The schema comment at
the terms table records the rule — a migration and a fresh init must create a table from one
text, or the two drift. Every rename in 1A.1 therefore edits `DDL` *and* emits a migration step,
and the equality of the two is what packet 1E's test asserts. **This is the invariant the cold
read caught the draft breaking**, and it is the reason behaviour 1 is stated before the others.

**The `task_id` column on the old `subtasks` becomes nothing.** It pointed at the dead middle
level. It was already nullable and already reported rather than guessed when absent, so removing
it loses no truth — but it has to be dropped explicitly in 1A.1, because a table rename preserves
every column it holds.

**`contract_ref` gains the uniqueness the old `source_ref` had.** The old `subtasks.contract_ref`
was deliberately not unique so a split's products could share one. With splitting removed in
packet 1C, one task *is* one contract, and the constraint states that rather than leaving it as
an invariant someone has to remember.

## 5. Packet 1B — `obligation` → `behaviour`

Depends on 1A. Deliberately second: it is the largest purely mechanical rename, it touches one
module plus its callers, and doing it before the level surgery keeps the two kinds of change from
being reviewed as one diff.

### Task 1B.1 — `BehaviourService` (was `ObligationService`)

**Signature.** Class and module rename: `engine/obligations.py` → `engine/behaviours.py`,
`ObligationService` → `BehaviourService`, `Obligation` → `Behaviour`, `ObligationSpec` →
`BehaviourSpec`. Its ten public methods keep their names except where the word appears:
`of_contract`, `for_subtask` → `for_task`, `require_enumerated`, `uncovered`, `foreign`,
`freeze_ops`, `redistribute_ops`, `amend`, `amendments`, `enumerate_from_row`.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Every public name carrying `obligation` or `subtask` is renamed; behaviour is otherwise unchanged. |
| 2 | The three errors rename with it: `NotEnumerated` keeps its name, `UnknownObligation` → `UnknownBehaviour`, `AmendmentNeedsReason` keeps its name. |
| 3 | `redistribute_ops` is **deleted**, not renamed. |

**Behaviour 3 is a removal, and it is the honest consequence of D7.** `redistribute_ops` exists
only to hand a split's products their share of the original's surface. Splitting dies with the
sub-task level — there is nothing to split once a task is one function — so the method has no
caller. Renaming it would carry a dead mechanism into v3 under a fresh name, which is how v2
accumulated `allow_draft`.

**Pseudocode** — none. This is a rename with one deletion; pseudocode would be the diff written
twice, which is the failure mode D9 warns about.

## 6. Packet 1C — the level surgery in `tasks.py` and `briefs.py`

Depends on 1A and 1B. The largest packet, and the only one with real design in it.

### Task 1C.1 — `TaskService.declare_package` and `assign_task` — deleted

**Behaviours**

| | behaviour |
|---|---|
| 1 | Both functions, their models `Package` and `Task`, and `unpackaged_tasks` are removed. |
| 2 | Their two surface tools are removed from the registry. |
| 3 | Their two `Absence` entries — the registry's record of *why* a call is not exposed — are removed with them. |

**Behaviour 3 is not tidying.** The registry carries a deliberate list of calls that exist but
are not on the surface, each with the reason. Leaving an absence entry for a function that no
longer exists is a citation to nothing, which is the defect where a mandate told every cold
planner to resume from a call that does not exist.

### Task 1C.2 — `TaskService.finalize_plan`

**Signature.** `finalize_plan(self) -> TaskGraph` — the `required_packages` parameter is
removed.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Derives one task per live contract row, as before. |
| 2 | Refuses with `GatesIncomplete` naming the stage, when a required stage gate has not passed. |
| 3 | Refuses with `UnresolvedFindings` when a finding is neither addressed nor accepted. |
| 4 | Refuses with `CycleDetected` naming the cycle. |
| 5 | **No longer refuses** a plan whose tasks have no group. That refusal dies with the level. |
| 6 | Freezes each task's behaviour surface at derivation, as `freeze_ops` does today. |

**Pseudocode**

```
guard_gates()                        # was _guard_gates(required_packages); the list is gone
guard_findings()
contracts = live rows where table == 'contracts'
for each contract:
    upsert task(contract_ref, title from the row's name)
    freeze its behaviours from the contract's content
derive deps from the typed depends_on links, consumer -> provider
order topologically; on failure raise CycleDetected naming the cycle
return TaskGraph(ordered tasks)
```

**The hole this task must answer, and it is cited, not invented.** `_guard_gates` currently
takes the caller's list of packages to require. With no packages, *which* gates must have passed?
The answer is already in the plan and needs no new decision: the interview's stages are the
standard set, so finalization requires every stage gate. That is what the old default did when
the caller passed nothing.

### Task 1C.3 — `BriefService.split_subtask` — deleted

**Behaviours**

| | behaviour |
|---|---|
| 1 | The function, its surface tool, its error `PartsDontCover`, and the `superseded_by` lineage column on the task row are removed. |
| 2 | `behaviours.uncovered` and `behaviours.foreign`, which existed only to serve the split's accounting, are removed. |

**Why the whole cluster goes rather than just the entry point.** The split existed because a v2
sub-task was one contract, which was not a servable size. A task is now one function, so there is
nothing to split. Its accounting denominator — the thing invented mid-build because the stated
check was vacuous — has no other reader. Keeping any of it would leave machinery whose reason for
existing has been removed, which is what D7 says about a level that owns nothing.

## 7. Packet 1D — the reporting layer

Depends on 1C. `gates.py`, `gaps.py`, `resume.py`, `guidance.py`, `findings.py`,
`attachments.py`.

### Task 1D.1 — stage-scoped reads

**Behaviours**

| | behaviour |
|---|---|
| 1 | Every parameter, column reference and message reading `package` in the *planning* sense reads `stage`. |
| 2 | `findings.resolve_by` continues to name the gate that locks until the finding is resolved; the value is a stage ordinal and the column is renamed to say so. |
| 3 | No behaviour changes. A gate that passed before passes now. |

**The one place this is not a rename.** `attachments.py` carries a scope level of
project / package / task. The middle level was the build grouping, and it is gone. Scope becomes
**project / task**, and any attachment sitting at the middle level migrates to project scope —
which is a widening, not a loss, and is the direction that cannot silently drop context.

That widening is a decision with a cost: D8 recorded that forcing subsystem-wide attachments to
plan scope is a silent "too high" failure. It is accepted here because the alternative is
inventing a grouping to hold them, and re-introducing packages under another name is exactly
what D7 rejected. **If the scope levels prove too coarse in use, that is evidence against D7 and
should be logged as a finding, not fixed by adding a level back quietly.**

## 8. Packet 1E — the banned-word enforcement

Depends on all of the above. Last, because it is the thing that proves the rest landed.

### Task 1E.1 — the vocabulary test

**Behaviours**

| | behaviour |
|---|---|
| 1 | Fails if `package`, `subtask`, `sub_task` or `obligation` appears in any identifier under `engine/`. |
| 2 | Fails if any of those words appears in a methodology asset or in text the tool emits. |
| 3 | Permits them in comments and documents that record *why* a word was retired. |
| 4 | Fails if the DDL and the migration produce structurally different databases. |

**Behaviour 3 is the hard one and it is where the check will go wrong.** The existing v2 test
of this shape reused a pattern tuned for a different job and could see four names where there
were twenty-two — it ran green while measuring something narrower than its name. So this test
takes the list of banned words from one place, scans identifiers rather than free text, and its
own fixture asserts the count it finds, so a pattern that silently narrows fails loudly.

**Behaviour 4 has no other home.** It is the mechanism behind 1A.2's first behaviour, and
without it the fresh-init and migrated schemas drift apart at exactly the moment nobody is
looking.

## 9. The cold read, and what it cost

Packet 1A was read blind, given only its own specification and the conventions register. The
result is the first evidence the depth rule works on real output rather than on the calibration's
reconstructions.

**What it returned:** 74 decisions, 26 uncited — 16 cross-task, 10 task-local. The conventions
register absorbed ten questions outright (error surfacing, logging, connection scope, timestamps,
identifiers, state storage, message content, surface exposure), which is the register earning its
place: without it those ten would have been holes.

**What it found that mattered:**

- **One outright bug** — `task_id` surviving into the migrated schema but not a fresh one. That
  is precisely the drift the schema's own comment warns about, and no test would have caught it
  until the two databases were compared.
- **Two contradictions inside the draft** — behaviours ordering drops the pseudocode never
  emitted.
- **Five real omissions** — the final names of the deps and verifications tables, the indexes
  beyond the one named, the obligation-named *columns*, which sub-task columns survive, and
  whether `contract_ref` becomes unique.
- **Four technical claims** about SQLite the draft had simply assumed. All four are now probed
  and recorded in §4.4, and one of them — that a table rename keeps its indexes' old names —
  would have left five wrongly-named indexes in the store.

**What it cost:** one blind reading, about three minutes, before a line of code existed. The
same defects found during the build would each have been a migration re-run against a snapshot.

**The residue, stated rather than hidden.** Ten task-local items are left uncited and stay that
way — whether the precheck is its own helper, whether drops carry `IF EXISTS`, how the count and
the names are queried. Under the depth rule those are the implementer's, and the specification is
finished when only they remain. Packets 1B to 1E have not yet been cold-read.

## 10. Not in this change

`labels` (change 4) take over the filtering job packages did. They are **not** built here, so
between this change and change 4 there is no way to filter a review list. That is accepted: the
alternative is holding the level alive across two changes, which means writing the migration
twice.
