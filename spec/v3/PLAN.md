# The v3 plan

**Status: planning artefact, and the last of them.** What v3 does, what it stores, what it
exposes, and the order the work lands in. Read `DECISIONS.md` first; this assumes it.

**A note on its own vocabulary.** v3 retires "package", so v3's own build has no packages. The
order of work below is a list of **changes**, each landing as its own branch and pull request.
This is a bootstrap: v3 is being planned before v3 exists to plan it, so its own build plan is
necessarily written the old way. That is also the substance of the open question about whether v2
is used to plan v3, which is held for the build-phase discussion.

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

The planning surface keeps most of v2's forty-eight, minus what dies with packages and sub-tasks,
plus what the catalogue, labels, pseudocode, scenarios and cold read require.

## 4. The order of work

Each item is a branch and a pull request. Ordering is by dependency, and the reason is given where
it is not obvious.

**Before any of it — one experiment, needing the owner's approval (D4).**

**Calibrate the cold read.** The 79 recorded inventions are a labelled test set. Reconstruct the
specification that preceded a sample, run the cold read blind, count what it catches. This needs
no built machinery — a prompt and the existing record — and it should happen **during planning,
before the plan is frozen**, because a poor hit rate invalidates stage 10 and weakens the whole
density argument. It is the single cheapest thing that could change the design, and doing it after
building it is the wrong order.

1. **Vocabulary and levels.** The rename and the removal, with the schema migration: drop
   packages, move `tasks` down, rename obligations to behaviours, update the enforcement test's
   banned list. Large and mechanical, and everything else sits on top of it.
2. **Decision context** (D11). Small, self-contained, and it improves the record of every change
   after it — so it goes early to earn its value across the rest of the work.
3. **The catalogue** (D10). A dependency of both brief derivation and the cold read, which is why
   it stops being the unscheduled topic it was in v2.
4. **Labels** (D12), including the starter list and the glossary refusal of a near-duplicate.
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
10. **Methodology revision 4** — all eleven stage scripts, the mandate, and a forward-only
    migration from revision 3. Threads through most of the above; landed last so it is written
    once against what was actually built, rather than rewritten after every change.

**Drive the system end to end after every one of these.** That practice caught something every
time it was used in v2, and it is the reason several defects in this repo were found at all.

## 5. What would tell us this failed

Stated now, while it is cheap to be honest, and testable at the first real use:

- **Specification density does not move.** If a task's brief still averages a handful of bytes per
  line of code produced, the pseudocode is too shallow and stage 8 is theatre.
- **Builders still invent.** The returning-invention loop is the instrument: if inventions per
  task do not fall against v2's baseline of 79 across the build, the brief is not complete.
- **Planning does not terminate.** Eleven stages and 255 tasks of detailed design is a large body
  of work, and if the interview cannot be driven to a freeze in a reasonable time then the trade
  in D9 was wrong, whatever its logic.
- **The cold read cannot tell a hole from a non-hole.** Calibration answers this before anything
  is built, which is why it comes first.

The fallback if any of these hold is a checkout of `v2-final`, which is why it is a tag.

## 6. What is still open, and who owns it

Mine to design and bring back: how deep the pseudocode goes (`INTERVIEW.md` §8); the starter label
list; whether eleven stages fold to fewer.

The owner's, at the build-phase discussion: whether the cold-read calibration runs now as an
approved experiment; whether v2 is used to plan v3; whether tool-proposed labels under glossary
rules is the right level of control; and whether `component` should be un-retired, which is
currently my call.
