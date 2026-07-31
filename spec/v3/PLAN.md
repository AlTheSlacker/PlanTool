# The v3 plan

**Status: planning artefact, and the last of them.** What v3 does, what it stores, what it
exposes, and the order the work lands in. Read `DECISIONS.md` first; this assumes it.

**A note on its own vocabulary.** v3 retires "package", so v3's own build has no packages. The
order of work below is a list of **changes**, each landing as its own branch and pull request.
This is a bootstrap: v3 is being planned before v3 exists to plan it, so its own build plan is
written the old way — by hand, in documents. The owner settled the alternative in D17: **v2 is
not used to plan v3**, because it would put an unproven mechanism on the critical path of its own
replacement. The cost of that, named in D17 so it is not forgotten, is that v3's own plan has the
same shape as the failure D1 describes.

---

## 1. What v3 does

Unchanged from v2 in purpose: a tool that interviews the owner, analyses what it hears, and
applies software engineering method to produce a build plan whose units are small, self-contained
and fully specified.

What changes is that it now **actually produces the build plan**. v2 stopped at architecture and
the build plan was written by hand. v3 descends to tasks, behaviours and pseudocode, and serves
one task at a time to a builder that has nothing else.

## 2. What it stores

**Removed**

- `packages` — the level is gone (D7). With it: mandatory package membership, the finalization
  refusal for an unpackaged task, the packaging round, the package cut, and the package ordinal
  that shadowed it.
- `subtasks` — the level is gone (D5). The name `tasks` moves down to what a builder is handed.
- `split_subtask` and its machinery — nothing to split once tasks are function-sized.
- The planning-package ordinal on plan rows, replaced by a stage ordinal.

**Renamed**

- `obligations` → `behaviours` (D5). Same machinery, plainer word.
- The eight methodology assets → `stage1_context.md` … , and everything named `package` in the
  engine → `stage` where it means the interview, and nothing where it meant the build grouping.

**Added**

- `catalogue` — every object, method and function the plan intends to exist: name, container,
  purpose line, owning task, public or private, near-match dismissals, and the two git fields
  that stay empty until the build phase. Design in `CATALOGUE.md`.
- `labels` and their attachment to rows — governed by the glossary, proposed by the tool,
  settled by the owner (D12).
- **Pseudocode**, held against a task.
- **Scenarios** — tasks whose specification comes from a use case, step, extension or state-machine
  cell, frozen before implementation (D13).
- **Decision context** — a separate field carrying the reasoning and the rejected alternatives
  (D11).
- **Cold-read results**, stamped against the rows they read and marked stale when one is
  superseded (D14).

**Kept, untouched.** Everything the analysis marks as proven: atomic writes with real idempotency
keys; immutable rows with supersession and lineage-root identity; the typed link graph; derive
rather than store; the naming discipline that never hands back a bare address; the glossary as a
real owner-owned table; warn-don't-block; the three mechanical pre-build checks; findings,
conflicts, claims, spikes, gates, gaps, journal, the change feed and the revision service.

## 3. What it exposes

**Two surfaces. A session is either planning or building and sees only its own.**

The build surface is six calls and no row query — full specification in `BUILD_SURFACE.md`. Its
smallness is the design: the tool call is the context boundary, not a query interface.

The planning surface keeps most of v2's **fifty-four**, minus what dies with packages and
sub-tasks, plus what the catalogue, labels, pseudocode, scenarios and cold read require. (This line
said forty-eight until 2026-07-29. Counted from `engine/surface.py`: `REGISTRY` holds 54, `ADDED`
holds 12, and all 12 deviations appear in both. Changes 1 to 4 take it to **63** and `ADDED` to
**22** — the arithmetic is in `builds/03-catalogue.md` task 3D.1 and `builds/04-labels.md` task
4D.1.)

## 4. The order of work

Each item is a branch and a pull request. Ordering is by dependency, and the reason is given where
it is not obvious.

**Before any of it — one experiment. Done: `COLD_READ_CALIBRATION.md`, 2026-07-28.** The cold read
caught 11 of 12 sampled inventions, so stage 10 stands and the density argument holds. It also
changed two things carried below: the labelled test set is **37** pre-freeze specification holes
rather than 79, and stage 10's output is a triage surface rather than a gate. Item 8 inherits
both.

1. **Vocabulary and levels.** The rename and the removal, with the schema migration: drop
   packages, move `tasks` down, rename obligations to behaviours. Large and mechanical, and
   everything else sits on top of it.

   **Built 2026-07-31.** `SCHEMA_VERSION` is 8, the suite is 533 tests, and the surface is
   **50** tools: 54 less `declare_package`, `assign_task`, `packaging` and `split_subtask`.
   The enforcement-test rewrite this item used to carry is struck, not deferred — 1A.0
   deletes the existing check instead, on the owner's ruling that v3 code reads only the
   `terms` table. Two things the specification had not listed turned up in the build and are
   recorded in `builds/01-vocabulary-and-levels.md` §12.
2. **Decision context** (D11). Small, self-contained, and it improves the record of every change
   after it — so it goes early to earn its value across the rest of the work.
3. **The catalogue** (D10). A dependency of both brief derivation and the cold read, which is why
   it stops being the unscheduled topic it was in v2.
4. **The glossary and labels** (D12, D18). The glossary reduces to a five-column user-owned table,
   and labels are its one mechanical use: a label is a live glossary term, looked up when it is
   assigned. **Rewritten 2026-07-30** — this item used to read *"labels, including the starter list
   and the glossary refusal of a near-duplicate"*, and the refusal is gone with the rest of the
   scanning machinery. The work order is `builds/04-glossary-and-labels.md`; `builds/04-labels.md`
   is superseded and kept for its probes and its cold-read record. Net it **deletes more than it
   adds** — the banned list, the prose scans at submission and at the gate, two gap rules, the
   export, the brief's glossary section and a test file all go.
5. **Detailed design** — tasks, behaviours, pseudocode, and the rule that pseudocode may only call
   a catalogued entry. The stage script, the gap rules, the gate criteria. This is the density
   fix and it depends on the catalogue existing.
6. **Verification design** — scenarios, and the gap rules that count them against use cases, steps,
   extensions and state-machine cells. Ordered after detailed design in the *build* even though
   its stage runs before it in the *interview*, because scenarios need somewhere to attach.
7. **Brief derivation and the build surface.** The payoff: the derived bundle, the two-surface
   split, the returning-invention loop. Depends on 3, 5 and 6.
8. **The cold read** as a stage, with whatever the calibration taught.
9. **The derived end-to-end checkpoint** (D8), replacing the package gates removed in 1.
10. **Methodology revision 7** — all eleven stage scripts, the mandate, and a forward-only
    migration. Threads through most of the above; landed last so it is written once against what
    was actually built, rather than rewritten after every change.

    **Revision 4 moved into change 1**, and the reason is a mechanism rather than a preference.
    The stage-6 script tells the planner to call `declare_package()`, `assign_task()` and
    `packaging()`; every tool response passes through the door, which raises on a call name the
    registry cannot resolve. The moment change 1 removes those tools, serving that script raises
    and the interview stops at stage 6. So revision 4 is the existing eight stages with the
    vocabulary corrected and the dead calls removed — the smallest thing that keeps the tool
    working — and this item is the eleven-stage rewrite, which really is a function of what gets
    built and really does belong last.

    **The number climbs once per change that edits a script, and this line kept saying 5 while it
    did.** Change 2 minted revision 5 for the `record_grounds` asks, change 3 minted none, and
    change 4 mints revision 6 for the stage-6 labelling round that replaces the deleted packaging
    round. So this item is **revision 7**. The lesson is not about numbering: it is that nothing
    cold-reads this document, so it went stale for two changes with nobody looking — the same way
    D12 asserted a guard that had never existed.

**Drive the system end to end after every one of these.** That practice caught something every
time it was used in v2, and it is the reason several defects in this repo were found at all.

## 5. What would tell us this failed

Stated now, while it is cheap to be honest, and testable at the first real use:

- **Specification density does not move.** If a task's brief still averages a handful of bytes per
  line of code produced, the pseudocode is too shallow and stage 8 is theatre.
- **Builders still invent.** The returning-invention loop is the instrument. The baseline to beat
  is the **37** pre-freeze specification holes v2's build hit, not the 79 recorded items — the
  other 43 are build-time bugs, owner rulings and duplicates, and a brief cannot prevent those.
  Counting against 79 would flatter v3 for fixing things it never addressed.
- **Planning does not terminate.** Eleven stages and 255 tasks of detailed design is a large body
  of work, and if the interview cannot be driven to a freeze in a reasonable time then the trade
  in D9 was wrong, whatever its logic.
- **The cold read cannot tell a hole from a non-hole.** Calibration answers this before anything
  is built, which is why it comes first.

The fallback if any of these hold is a checkout of `v2-final`, which is why it is a tag.

## 6. What is still open, and who owns it

**Closed.** The cold-read calibration ran and is written up. Whether v2 plans v3 is settled: it
does not (D17).

Mine to design and bring back: how deep the pseudocode goes (`INTERVIEW.md` §8, where the
calibration killed the proposed test and left a candidate); whether eleven stages fold to fewer;
and how stage 10 promotes a real hole out of a list of sixty decisions, which the calibration
added.

**The starter label list is settled** — the ten in `VOCABULARY.md`, unchanged. Change 4 designed a
replacement and measured it away: 92% of a plan's rows have no path to a component, so a place-name
is not the redundant filter the replacement assumed (`builds/04-labels.md` §3.2).

**Settled by the owner, 2026-07-29:** tool-proposed labels under glossary rules **is** the right
level of control — the tool proposes, he adds and assigns freely and overturns anything. Specifying
it against the code then found the guard underneath it was imaginary; see D12 and change 4.

Still the owner's, at the build-phase discussion: whether `component` should be un-retired, which
is currently my call. Change 3 is evidence for keeping it — it gives the word a job nothing else
can do, as the owner of an object entry.

Item 7 carries a standing caution from D17: it rebuilds brief derivation on machinery that has
never been driven, so it should be driven end to end early rather than at the end.
