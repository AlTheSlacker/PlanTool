# Stage 8 — Freeze (verify mode)

Planning ends here, mechanically. No new content belongs in this stage — if the export or
the gate turns up a content problem, that is a stage-1..7 fix first.

## Procedure

1. `export_plan()` — writes `plan.md` (human-readable) and `plan.yaml` (the structured,
   round-trippable bundle) into the workspace. Skim `plan.md` **with the user**: this is
   the last cheap moment for a "that's not what I meant" catch. Anything caught is fixed
   in the DB (supersede/retire/submit) and re-exported — never by editing the files.
2. `run_gate(8)` — folds in gates 1–7, open conflicts, the `plan.md` render, and a
   lossless `plan.yaml` round-trip check. Work any holes with the user; each names its fix.
3. `freeze_plan()` — allowed only while gate 8 passes. Bumps the version, sets the plan
   read-only. **There is no unfreeze**; a new planning round is a new plan.
4. `export_plan()` again after the freeze so the files on disk carry the frozen version.

## Conduct here

- Do not freeze to be done. If the user hesitates over any part of the skim, that
  hesitation is an intent gap — resolve it first; the freeze can wait a day.
- The exports are derived views of the DB. Repeat that to the user if they ask to "just
  tweak the markdown".

## Exit condition (mechanical gate)

Gate 8 green and `freeze_plan()` recorded. The plan is now the contract implementation
sessions work from.
