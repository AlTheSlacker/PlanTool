# Stage 1 — Context & goals (elicit mode)

The user is the source of truth; you probe, sharpen, formalise. Batch related questions;
proposal-first wherever you can form a defensible default.

## Divergence round — before any proposal of yours
- Ask the user to brain-dump the project in their own words first; file the fragments, don't
  reshape them yet.
- Context-free questions (below) come before your framing does.
- Negative space: what must this system **never** do? Whose problem is explicitly not being
  solved? What would make the project pointless even if delivered?

## Coverage checklist — elicit all of these
- **The problem:** what hurts today, for whom, why now.
- **Users/actors:** everyone who touches or is affected by the system.
- **Goals:** each with a measurable success criterion — a goal without one is a gap, raise it.
- **Non-goals:** explicit exclusions someone might assume in scope. The gate requires a
  non-empty list; probe until you have real ones.
- **Constraints:** time, budget, compliance, compatibility, team skills.
- **Target stack:** language / platform / runtime. This is planning *data*, recorded as
  `stack` rows — never tool configuration.
- **Context-free questions:** What surprised you in similar projects? What must not change?
  Who can veto this? What does failure look like a year from now?

## Conduct here
- Restate fuzzy answers precisely and read them back before filing.
- Record provenance on every row; mark your gap-fills `assumed` with `assumption_kind`.
- World-assumptions you hit (e.g. "the vendor API supports batch upserts") get spiked, not
  asked; intent-assumptions get asked, not guessed.

## How stage-1 facts are recorded (the gate queries these shapes)

Everything is filed with `submit_rows`; the row's `table` says what it is. Each fact gets its
own typed table, and the gate queries those tables by name — a fact filed anywhere else is a
fact the gate cannot see.
- Each goal: a `goals` row, its `name` the goal, with the measurable success criterion in
  `success_criteria` — a scale and a target an acceptance test could check.
- Each exclusion: a `non_goals` row, its `name` the thing this system explicitly will not do.
  At least one real exclusion is required; the gate rejects an empty list.
- Each actor: an `actors` row, its `name` the actor. Every actor needs a scenario eventually
  (the stage-2 cross-check enforces it), so record only those who touch or are affected by
  the system.
- The target stack: a `stack` row per element — language, platform, runtime — carrying the
  alternatives that were considered. This is planning *data* about what is being built, never
  tool configuration.
- Constraints often make good ubiquitous/state `requirements` rows; core domain nouns can be
  filed early into `entities`. File them now; they are gated in stages 3 and 4.

## Self-review before gate
- Does every goal have a success criterion an acceptance test could check?
- Are the non-goals real exclusions, or filler?
- Is the target stack recorded with the alternatives that were considered?

## Exit condition (mechanical gate)
Every goal has a success criterion; non-goals non-empty; target stack recorded as `stack`
rows; every recorded actor is on a path to a use case.
