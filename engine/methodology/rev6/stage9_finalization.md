# Stage 9 — Finalization (verify mode)

Planning ends here, mechanically. No new content belongs in this stage — if the render or
the gate turns up a content problem, that is a stage-1..8 fix first.

## Procedure

1. `render_plan()` — writes `plan.md` into the workspace: every live row, in the order the
   interview produced it. Read it **with the user**, end to end. This is the last cheap
   moment for a "that's not what I meant" catch; after finalization the same catch costs a
   revision. Anything caught is fixed in the rows (supersede/retire/submit) and rendered
   again — never by editing the file, whose next render discards the edit.
2. `run_gate(9)` — two criteria, and they are the whole gate: every earlier stage's gate
   is green, and no conflict is still open. Work any holes with the user; each names its
   fix. The render is not gated and cannot be: whether the plan says what the user meant is
   a judgment, and the gate only checks what a machine can check.
3. `finalize_plan()` — allowed only while gate 9 passes. It moves the plan out of draft and
   derives the task graph from the contracts. It also refuses a plan with a task in no
   stage, and names any contract whose behaviours were never enumerated; both are
   stage-6 work coming back, and both are fixed there rather than here.
4. `render_plan()` again, so the document on disk carries the finalized version rather than
   the draft the user skimmed.

## Conduct here

- Do not finalize to be done. If the user hesitates over any part of the skim, that
  hesitation is an intent gap — resolve it first; finalization can wait a day.
- The document is a derived view of the rows. Repeat that to the user if they ask to "just
  tweak the markdown".
- Finalization is not a wall. A finalized plan is reopened through a recorded revision, so
  the honest thing to tell a hesitating user is that this is the cheapest moment to change
  their mind, not the last one.
- The render marks any citation that no longer reaches a live row. Those are not cosmetic:
  a row whose prose points at nothing is a row whose reasoning has quietly lost its ground.

## Exit condition (mechanical gate)

Gate 8 green and `finalize_plan()` recorded. The plan is now the contract implementation
sessions work from.
