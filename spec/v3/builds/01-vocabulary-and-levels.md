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

### Task 1A.1 — `Storage._migration_steps`, the 7→8 branch

**Signature.** Unchanged: `_migration_steps(self, current: int, target: int) -> list[str]`.
Gains one branch.

**Behaviours**

| | behaviour |
|---|---|
| 1 | Renames `plan_rows.package` to `plan_rows.stage`, preserving every value. |
| 2 | Renames the index `idx_rows_package` to `idx_rows_stage`. |
| 3 | Drops `tasks.package_id` and its index, and drops the `packages` table. |
| 4 | Renames `obligations` → `behaviours`, `obligation_ownership` → `behaviour_ownership`, `obligation_amendments` → `behaviour_amendments`, and the index `idx_obligation_live_owner` with them. |
| 5 | Renames `subtasks` → `build_tasks` and `subtask_deps`/`subtask_verifications` to match, then drops the old `tasks` table and renames `build_tasks` to `tasks`. |
| 6 | **Refuses**, before any write, a plan holding more than one live declared package, naming them. |

**Behaviour 6 is the one that matters, and it is a decision, not a detail.** The existing
migration rule is explicit: a migrated value must be a truth the old store already implied, never
one invented to satisfy a constraint. Collapsing several declared packages into nothing invents
the claim that the owner's grouping meant nothing. So a plan with one live package migrates
silently — that grouping *is* the whole plan, which is a truth already implied — and a plan with
two or more is refused, with the owner told what he must retire first. Refusing is affordable
because exactly one such database exists.

**Pseudocode**

```
if current == 7 and target == 8:
    live = count of packages where superseded_at is null
    if live > 1:
        raise ValueError naming each live package        # caught by migrate(), snapshot restored
    emit  ALTER TABLE plan_rows RENAME COLUMN package TO stage
    emit  DROP INDEX idx_rows_package
    emit  CREATE INDEX idx_rows_stage ON plan_rows (stage)
    emit  the obligations -> behaviours renames (table, then each index)
    emit  the subtasks -> build_tasks renames (table, deps, verifications, index)
    emit  DROP TABLE tasks                                # the old middle level
    emit  ALTER TABLE build_tasks RENAME TO tasks         # the new bottom level takes the name
    emit  DROP TABLE packages
```

**Order is load-bearing and is not a style choice.** `packages` drops last because `tasks`
references it; the old `tasks` drops before `build_tasks` takes its name, or the rename collides.

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
text, or the two drift. Every rename above therefore edits `DDL` *and* emits a migration step,
and the equality of the two is what packet 1E's test asserts.

**The `task_id` column on the old `subtasks` becomes nothing.** It pointed at the dead middle
level. It was already nullable and already reported rather than guessed when absent, so removing
it loses no truth.

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

## 9. What a cold read must be given for each of these

Per `INTERVIEW.md` §8 and the calibration: the task's behaviours and pseudocode, the catalogue
entries it may call, the glossary, **and `CONVENTIONS.md`** — without the register the reader
returns 35 uncited decisions and buries the five that matter.

The holes already answered above, so a cold read should find them cited: what happens to a plan
with declared packages · which gates finalization requires with no package list · what becomes
of the middle scope level · whether the split's accounting survives · whether `redistribute_ops`
is renamed or deleted.

## 10. Not in this change

`labels` (change 4) take over the filtering job packages did. They are **not** built here, so
between this change and change 4 there is no way to filter a review list. That is accepted: the
alternative is holding the level alive across two changes, which means writing the migration
twice.
