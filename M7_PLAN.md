# M7 — the revision process (reduced)

This plans the next build package in advance, so it can be built in small, reviewable
chunks rather than discovered as I go. Written 2026-07-23.

## What this piece is, in plain terms

Once a plan is finalized, you are not allowed to edit it freely anymore — that is the whole
point of finalizing. Instead you open a **revision**: a controlled change process. The tool
takes an immutable snapshot of the plan as it stands, bumps the plan's version number, works
out everything the proposed change would ripple into, walks the owner through each ripple one
at a time so they can decide what to do about it, and then either commits the whole set of
changes at once or throws them all away and leaves the plan exactly as it was.

Nothing in the tool does this yet. The plan's lifecycle already knows the word `revising`
(it is in the state machine), but no code ever moves a plan into or out of that state. Only
`finalize` is wired up today. This package wires up the rest.

## What is deliberately left for the chunk after this one

The owner decided (2026-07-23) that two behaviours wait for the next package, because the part
of the tool they lean on only recently came into existence and they are heavy enough to be
their own work:

1. **Regenerating briefs.** When the plan changes, the instruction packets the tool hands to
   whoever builds each part ("briefs") are now out of date and should be rewritten to match.
2. **Flagging built work for rework.** Anything already built against the old plan should be
   flagged as possibly needing redoing.

One related behaviour does **not** wait, because a bug I have to fix here needs it anyway:
**freezing the right in-progress work.** See "Affected-only freeze" below.

## The two primitives this leans on already exist

I checked before planning. Both are built and tested:

- **Snapshotting** — `storage.snapshot_version(reason)` writes an immutable copy of the plan
  and returns its id (`contracts:7`).
- **Impact analysis** — `graph.impact(changed)` returns an `ImpactReport` enumerating every
  row transitively affected by a change, as a pure read that never mutates edges
  (`contracts:15`).

So `open_revision` composes existing parts; it does not invent snapshotting or graph-walking.

## The five contracts (frozen spec, `spec/v2/plan.md:859`)

| Contract | What it does |
|---|---|
| `open_revision` | Snapshot, bump version, run impact analysis, move the plan to `revising`, and create the Revision with its repercussion list frozen. |
| `next_repercussion` | Hand the owner the next ripple to decide on; resume losslessly if interrupted; return `WalkthroughComplete` at the end. |
| `adjudicate_repercussion` | Record the owner's accept/modify/defer decision. On **modify**, the owner's new wording is conflict-checked; if it comes back clean it is **applied to the live plan immediately** (the row is superseded); if it conflicts, it is shown and held until resolved. |
| `apply_revision` | Close a revision whose ripples have all been adjudicated and whose changes are already live; move the plan back to `finalized` with its new version. Refuse if any ripple is still undecided or any conflict is unresolved. |
| `abandon_revision` | Two-step. First call **previews** what will be reverted (the changes applied so far). The owner then either confirms — the plan is **rewound to the opening snapshot** — or steps back and keeps the revision. The analysis record survives either way. |

## Design decisions I have already resolved (so they are not discovered mid-build)

### Incremental application, conflict-checked; abandon rewinds (owner's decision, 2026-07-23)

The frozen contract text (`contracts:57`) chose *deferred* application — stage everything,
mutate nothing until apply — as the red team's fix for the fact that you cannot un-supersede a
row (`findings:5`). **The owner has since decided differently, and this build follows the
owner:** when the owner supplies new wording for a row, the tool runs it through the conflict
check, and the moment it comes back clean the row is **superseded on the live plan right then**.
A wording that conflicts is surfaced and held until the owner resolves it. This is logged as a
deviation (D25) because it contradicts the frozen contract's "deferred application" wording.

This is internally consistent with the write-once history rule because **abandon does not try
to un-supersede anything — it rewinds the whole plan to the immutable snapshot taken when the
revision opened.** That is viable precisely because the revision's analysis record is stored
**outside** the plan-row snapshot, so rewinding the plan never destroys the record of what was
tried. `findings:5`'s own text named "restore the pre-change snapshot" as the alternative to
deferred application; this build takes that alternative.

### Abandon is a confirmed, two-step action (owner's decision, 2026-07-23)

Because changes are live by the time an abandon is requested, abandon must not silently throw
work away. The first call **previews the rewind**: it reports exactly which applied changes
would be reverted. The owner then either confirms — and the plan is rewound to the opening
snapshot — or steps back, in which case nothing changes and the revision stays open for them to
keep working or to re-approve what is already live. Implemented with a `confirm` flag on
`abandon_revision` (the unconfirmed call is a pure read that mutates nothing); logged as
deviation D26 since the frozen signature has no such parameter.

### The Revision is born ready to walk, not "analyzing"

The state machine lists five states: `proposed → analyzing → walkthrough → applied | abandoned`.
But the analysis (`graph.impact`) is a synchronous read that finishes inside `open_revision`'s
own call — there is no asynchronous "analyzing" phase anyone can observe or interrupt. So
`open_revision` does the snapshot, bump and analysis in one act and the Revision it returns is
already in `walkthrough`. `proposed` and `analyzing` exist in the state machine but are passed
through inside that single call and never persisted. **This is logged as a deviation (D27).**

Why this matters beyond tidiness: it means `apply_revision` is always reached from
`walkthrough`, which the state machine says is mandatory before apply. If the Revision could
sit in a persisted `analyzing` state, `apply_revision` would need an error for "you haven't
walked the repercussions yet" that its frozen contract does not offer. Being born in
`walkthrough` closes that hole cleanly. Nothing is lost: opening a revision and immediately
abandoning it is still possible (abandon from `walkthrough`).

### The repercussion list is frozen at open time

`apply_revision` refuses if "every repercussion has not been adjudicated." The set it counts
against must be **fixed when the revision opens**, not recomputed at apply time against a plan
that may have moved. (This is the F26 lesson — an accounting whose denominator is re-derived at
read time is measured against a moving target.) So `open_revision` stores the enumerated
repercussion list, and everything downstream reads that stored list.

### Resurfacing accepted risks and suppressed warnings

The spec (`requirements:55`) says a revision that touches an accepted risk or a suppressed
warning must resurface it for re-adjudication. `active_warnings(context=revision)` already
returns suppressed warnings as reminders (built at M3). So `next_repercussion` folds any touched
accepted-risk finding and suppressed warning in the impact set into the walkthrough as items
the owner must look at again.

### Affected-only freeze — and the bug it fixes (F21)

There is a known open defect (F21): `next_subtask` has an `allow_draft` escape hatch that today
cannot serve anything, because sub-tasks only exist for a finalized plan and `allow_draft` only
makes sense once a plan has left `finalized`. The one situation where a plan has sub-tasks but
is not finalized is **exactly this one** — it is in `revising`. The owner's fix for a related
finding (`findings:6` / `decisions:62`) is an **affected-only freeze**: while a revision is
open, only the sub-tasks the revision actually touches are frozen; every unaffected sub-task
keeps flowing. So `next_subtask`, during `revising`, serves any sub-task **outside** the
revision's frozen impact set. This is the "freezing the right in-progress work" behaviour that
does not wait — computing the impact set is required by `open_revision` regardless, and F21 is
resolved by having `next_subtask` read it.

## Build chunks (small, in order)

1. **Storage + models.** The `revisions` table and a staged-decisions table; the models
   (`ChangeRequest`, `Revision`, `Repercussion`, `StagedChange`, `OwnerDecision`,
   `RevisionResult`, `RollbackReport`); the plan-state transition helper for
   `request_revision` / `apply_revision` / `abandon_revision`. Schema version bump with a real
   migration.
2. **`open_revision`** — snapshot, bump, impact, freeze the repercussion list, plan → `revising`,
   Revision born in `walkthrough`. Refusals: not-finalized, one-revision-at-a-time.
3. **`next_repercussion`** — checkpointed walkthrough, accepted-risk / suppressed-warning
   resurfacing, `WalkthroughComplete`.
4. **`adjudicate_repercussion`** — record accept/modify/defer. On modify, conflict-check the
   owner's new wording and, if clean, supersede the row live; if it conflicts, surface and hold.
5. **`apply_revision`** — close the revision once every repercussion is adjudicated and no
   conflict is unresolved (the row changes are already live); plan `revising → finalized`, new
   version live. Refuse on any undecided item or open conflict.
6. **`abandon_revision`** — first call previews what the rewind will revert; a confirmed call
   rewinds the plan to the opening snapshot; analysis preserved; refuse if already applied.
7. **F21** — `next_subtask` serves outside the frozen impact set during `revising`.
8. **Surface + drive.** Expose the five tools through `dispatch`; drive the whole loop
   end-to-end through the real surface and read the output.

Each chunk is a journal unit. Built in this order because each depends on the one before it.
Migration path stays forward-only from rev 3 (D24) — this package does not touch that.
