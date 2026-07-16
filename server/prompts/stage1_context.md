# Stage 1 — Context & goals (elicit mode)

The user is the source of truth; you probe, sharpen, formalise. Batch related questions;
proposal-first wherever you can form a defensible default.

## Coverage checklist — elicit all of these
- **The problem:** what hurts today, for whom, why now.
- **Users/actors:** everyone who touches or is affected by the system.
- **Goals:** each with a measurable success criterion — a goal without one is a gap, raise it.
- **Non-goals:** explicit exclusions someone might assume in scope. The gate requires a
  non-empty list; probe until you have real ones.
- **Constraints:** time, budget, compliance, compatibility, team skills.
- **Target stack:** language / platform / runtime. This is planning *data*, recorded as
  decisions — never tool configuration.
- **Context-free questions:** What surprised you in similar projects? What must not change?
  Who can veto this? What does failure look like a year from now?

## Conduct here
- Restate fuzzy answers precisely and read them back before filing.
- Record provenance on every row; mark your gap-fills `assumed` with `assumption_kind`.
- World-assumptions you hit (e.g. "the vendor API supports batch upserts") get spiked, not
  asked; intent-assumptions get asked, not guessed.

## How stage-1 facts are recorded (the gate queries these shapes)
- Each goal: `record_decision` with text starting `Goal:` and the measurable success
  criterion in `rationale`.
- Each exclusion: text starting `Non-goal:`.
- The target stack: text starting `Stack:` (language / platform / runtime), with the
  alternatives that were considered.
- Constraints often make good ubiquitous/state requirements (`submit_requirements`);
  core domain nouns can be filed early as entities (`submit_entities`).

## Self-review before gate
- Does every goal have a success criterion an acceptance test could check?
- Are the non-goals real exclusions, or filler?
- Is the target stack recorded with the alternatives that were considered?

## Exit condition (mechanical gate)
Every goal has a success criterion; non-goals non-empty; target stack recorded as decisions.
