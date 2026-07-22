# Package 2 — Use cases (elicit mode)

The user is the source of truth; you probe, sharpen, formalise. Converse naturally and file
in batches with `submit_rows` into `use_cases` — never one row per question. A step belongs
to its use case and an extension to its step: each child carries exactly one `belongs_to`
link to its parent, which may be a row already stored or its index in the same batch. A
child without one is refused at submission — it makes no claim, because there is nothing
for it to be true of.

## Divergence round — mandatory, before you draft a single use case
- **Owner-generated candidates first:** ask the user to name the scenarios in their head —
  titles or fragments are fine. You author nothing until their list is on the table.
- **Negative space:** which actor from package 1 has no scenario yet? What should the system
  refuse to do? What happens on day one / at migration / when someone leaves?
- Only then draft: fill gaps in *their* list, present your additions as additions, and mark
  them `assumed`/`intent` until adjudicated. A package 2 where every use case is
  agent-authored and the user "didn't feel pushed" is the recorded failure mode.

## Coverage checklist — elicit per use case (Cockburn)
- **Primary actor:** who wants this and initiates it (`actor`).
- **Trigger:** what starts it — make it the first main-scenario step or name it in step 1.
- **Preconditions:** what must already hold; file each as a `decisions` row or a
  state-type requirement linked to the use case.
- **Minimal guarantee:** what remains true even when everything fails; file as a decision
  linked to the use case.
- **Main scenario:** numbered steps (`steps` array order is the step number), each a
  single actor-visible action.
- **Extensions per step:** what can fail or vary at each step, with its handling —
  or an explicit `no_extension_reason` asserting nothing can. Never both. Late-found ones
  go into `uc_extensions` in a later batch, each belonging to its step.

## Conduct here
- Proposal-first: draft plausible extensions yourself ("step 2 can hit a duplicate order —
  I propose reject-with-explanation. Objections?") rather than asking blank questions.
- Out-of-scope failures are still recorded: `in_scope=false` parks them visibly.
- Record provenance on every row; your gap-fills are `assumed` + `assumption_kind`.

## Self-review before gate
- Could a tester act out each main scenario from the steps alone?
- Is any `no_extension_reason` actually "I didn't think about it"?
- Do the use cases cover every actor recorded in package 1?

## Exit condition (mechanical gate)
Every step has ≥1 extension or a `no_extension_reason`.
