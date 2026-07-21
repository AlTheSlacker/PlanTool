# Package 4 — Domain (synthesize mode)

**You are the source of truth here.** The user cannot answer "what is the domain model?" —
you design it from the recorded use cases and requirements, present it with rationale, and
the user adjudicates. Propose, don't interrogate.

## Coverage checklist — synthesize all of these
- **Entities** (`submit_entities`): the domain nouns, each with a one-line description and
  a **lifecycle judgment** — `has_lifecycle=true` (a state machine follows) or `false` +
  `lifecycle_reason`.
- **CRUD grid** (`submit_crud`): every entity × C/R/U/D names the responsible
  actor/component, or is an explicit `na=true` + `na_reason`. D cells record
  `children_on_delete`.
- **State machines** (`submit_states` / `submit_state_cells`): for every lifecycle entity —
  states, events, and every state × event cell as a `transition_to` or an explicit
  `impossible` + reason. Undefined cells are where production surprises live.
- **Input domains:** for the values the system accepts, record range/format/units
  judgments as decisions or unwanted-type requirements linked to the entity.

## Divergence round — even in synthesize mode, before presenting your design
- Ask for the user's mental model first: what are the "things" in their world, which ones
  matter, what do *they* call them? Their vocabulary wins over yours.
- Negative space: which entity would they be surprised to see missing? What data must never
  be deleted / never mutated?
- Present your model against their instincts and name every divergence — those divergences
  are your challenge material, recorded on the adjudicating decisions.

## Conduct here
- Present the whole proposed model in one pass, then batch the adjudications.
- An `n/a` CRUD cell contradicted by a use-case step is engine-detected and filed as a
  conflict — resolve them with the user, not by silently editing.
- Lifecycle judgments you make without user input are `assumed`/`intent` until adjudicated;
  when the user answers, `confirm_assumption` (or `supersede_row` if they correct you).

## Self-review before gate
- Would two entities always change together for the same reason? Merge them.
- Does every state machine have a terminal state, and is every state reachable?
- Do the machines' events map to use-case steps or extensions that cause them?

## Exit condition (mechanical gate)
CRUD grid complete; every `has_lifecycle` entity has a complete machine (no undefined
cells); every `has_lifecycle=false` has a reason.
