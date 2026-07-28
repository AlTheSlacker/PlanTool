# The interview — how the tool elicits a specification deep enough to build from

**Status: planning artefact.** This is where the density problem is won or lost, and nothing had
been written on it.

---

## 1. The gap, located exactly

v2's methodology runs eight stages:

| | Stage | Mode | What it writes |
|---|---|---|---|
| 1 | Context and goals | elicit | goals, non-goals, stack, actors |
| 2 | Use cases | elicit | use cases, steps, extensions |
| 3 | Requirements | elicit | requirements |
| 4 | Domain model | synthesize | entities, CRUD grid, state machines and their cells |
| 5 | External dependencies and failure modes | synthesize | dependencies, failure modes |
| 6 | Architecture | synthesize | components, contracts |
| 7 | Adversarial findings | verify | findings |
| 8 | Finalization | verify | — |

**The interview stops at architecture.** Stage 6 produces components and contracts; stage 7
attacks them; stage 8 freezes. No stage writes a task, a behaviour, a line of pseudocode, a
catalogue entry or a scenario. The build plan was never anyone's job, which is why the vacuum was
filled by four hand-written milestone documents.

This is worth stating precisely because it makes the fix a **targeted addition rather than a
redesign**. Stages 1 to 5 elicit the specification and are not the problem; the measured evidence
of the v2 build is that what was elicited was reasonable and what was *designed from it* stopped
one level too high. So they carry over close to unchanged, and the fix is what comes after.

## 2. The stage sequence

Eleven stages. New ones in bold.

| | Stage | Mode | What it writes |
|---|---|---|---|
| 1 | Context and goals | elicit | goals, non-goals, stack, actors |
| 2 | Use cases | elicit | use cases, steps, extensions |
| 3 | Requirements | elicit | requirements |
| 4 | Domain model | synthesize | entities, CRUD grid, state machines and cells |
| 5 | External dependencies and failure modes | synthesize | dependencies, failure modes, technical claims |
| 6 | Architecture | synthesize | components, contracts, labels |
| 7 | **Verification design** | synthesize | scenarios |
| 8 | **Detailed design** | synthesize | tasks, behaviours, pseudocode, catalogue entries |
| 9 | Adversarial findings | verify | findings |
| 10 | **Cold read** | verify | sufficiency results |
| 11 | Finalization | verify | — |

## 3. Why verification is designed *before* detailed design

This ordering looks wrong and is the most important decision in the sequence.

A scenario's *specification* — what it must prove — comes from the use case, not from the
implementation. Its wiring to tasks is derived afterwards, when tasks exist. So nothing forces
scenario design to come second, and two things argue strongly for it coming first:

- **It is the mechanism behind the freeze-before-implementation rule.** If one stage produced both
  the task design and the tests for it, a session could shape the tests around the design it had
  just invented — the same failure as a unit test written minutes after the unit, one level up. A
  stage boundary makes the independence structural rather than a matter of discipline.
- **The detailed design is then written knowing what it will be judged by**, which is exactly what
  a builder is told in its brief. The plan should not know less about its own acceptance than the
  builder does.

**Rejected: folding verification into detailed design** as one stage. It is fewer stages and
cheaper, and it destroys the independence that is the whole point.

The denominator is already in the plan by stage 7: 12 use cases, 40 steps, 50 extensions and 187
state-machine cells existed in v2 and nothing was ever written against them. A use case, step,
extension or illegal transition with no scenario is a gap, counted by the same machinery that
counts every other gap.

## 4. Stage 8 — detailed design, where density is actually produced

The stage that did not exist. For each component, it writes:

1. **Tasks** — one externally-callable function each, with its signature.
2. **Behaviours** for each task — the main effect, and each specific error with the exact
   condition that raises it. Enumerated and frozen here, before anything measures against them.
3. **Pseudocode** for each task.
4. **Catalogue entries** for every name the pseudocode uses, public or private, each dismissing
   its near matches with a written reason.

**Order matters inside the stage, and it is enforced rather than advised.** Behaviours before
pseudocode, because pseudocode written first quietly becomes the specification and the behaviour
list degrades into a summary of it. Pseudocode before catalogue entries, because the pseudocode is
what names them.

**The one hard rule: pseudocode may only call something already in the catalogue.** That single
constraint does most of the work. It forces every call to be a thing the plan has committed to,
it makes duplication visible at the moment of designing rather than the moment of coding, and it
is what makes a brief derivable instead of conversational.

**The honest cost.** For a system the size of v2's engine this is roughly 255 tasks, each with
behaviours and pseudocode. That is a large body of work and it is the single biggest thing the
owner is buying into. Three things make it the right trade rather than a doubling:

- It is **not additional** work. Behaviours, call graph and control flow all get decided anyway;
  today they are decided during coding, by whoever is standing there, unrecorded. This moves the
  same decisions to where they are reviewable and where a wrong one costs a line of pseudocode
  instead of a refactor.
- It is the **only** thing that raises 8 bytes of specification per line of code.
- It is verifiable, by the cold read, which the coding-time version of these decisions never was.

## 5. Stage 10 — the cold read, and why it is a stage rather than a check

A session holding **only** a task's specification, the catalogue entries it may call, and the
glossary — with no access to the conversation that produced it — lists every decision it would
have to make to implement the task, and cites against each the row that answers it. An uncited
decision is a hole.

It is a **stage** and not a gate criterion because it is a body of work with an output that gets
adjudicated: holes come back as findings against the specification, the specification is amended,
and stale results are re-read. Making it a check inside finalization would hide a substantial
activity inside a boolean.

**Calibrate it before it gates anything.** The 79 recorded inventions from the v2 build are a
labelled test set: reconstruct the specification that preceded a sample of them, run the cold read
blind, count what it catches. That produces a hit rate rather than an assurance, and if the hit
rate is poor we learn that while it is still cheap to change.

## 6. What makes an interview *deep*, mechanically

Depth cannot come from instructing the planner to be thorough. Five mechanisms carry it, four of
which already exist and need extending rather than inventing:

- **Gap rules** — per stage, computed live, naming what is missing. Extended to the new tables:
  a task with no behaviours, a behaviour with no verification, a task with no pseudocode, a
  pseudocode call with no catalogue entry, a use case with no scenario.
- **Divergence rounds** — already mandatory in elicit stages, where the tool must offer readings
  the owner has not proposed rather than transcribing what it is told.
- **The technical-claims rule (D4)** — no statement about anything we do not control survives
  without cited documentation, a probe that was run, or the owner's recorded acceptance of the
  risk. The tables exist in v2 and are unused; what is missing is the rule making it non-optional.
- **The glossary**, which stops a word drifting between stages, and which the catalogue's search
  depends on.
- **The cold read**, which is the only one of the five that measures sufficiency rather than
  presence.

The first four ask "is something there". Only the last asks "is it enough", which is why it
carries the weight and why calibrating it matters more than any other single number in this
design.

## 7. What changes in the existing stages

Small and worth listing so the fix stays targeted.

- **Stage 2** gains an explicit second consumer: use cases, steps and extensions are the
  denominator for scenarios at stage 7. Nothing about the elicitation changes; what changes is
  that they are now load-bearing rather than descriptive.
- **Stage 5** binds the technical-claims rule.
- **Stage 6** loses the packaging round and the mandatory package cut, which die with packages.
  It gains **labels** — the tool proposes from the starter list, the owner settles, and glossary
  rules refuse a near-duplicate.
- **Stage 6** keeps contracts, but they stop being the build unit and become what they always
  were: the architecture's statement of a component's obligations, which stage 8 turns into
  tasks.
- **Stage 9** now has more to attack: the pseudocode and the catalogue are the richest target the
  red team has ever had, and duplication and naming collisions are visible there for the first
  time.
- **Stage 11** gains the derived end-to-end checkpoint (D8) as something it validates is
  computable, rather than the package gates it replaces.

## 8. Open

- **How deep the pseudocode goes** before a task counts as specified. Too shallow and it decides
  nothing; too deep and it is code written twice. My instinct is that the test is behavioural
  rather than a length rule — the pseudocode is deep enough when the cold read finds no holes —
  which makes stage 10 the arbiter and avoids inventing a threshold. That needs the calibration
  to be run before it can be trusted.
- **Eleven stages may be too many.** Each has a distinct job and mode, and I have not found two
  that fold together without losing a mechanism, but the owner should see the count and say.
- **Whether the cold read runs per task or per component.** Per task is the honest unit and is
  what the design says; per component is cheaper and may be enough. This is measurable during
  calibration rather than arguable now.
