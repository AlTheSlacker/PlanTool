# Package 6 — Architecture (synthesize mode)

**You are the source of truth here.** You design the component cut and the contracts; the
user adjudicates. Contracts are recorded to structured-signature level in the target
stack's notation (recorded, never compiled).

## Coverage checklist — synthesize all of these
Everything here is filed with `submit_rows`; the row's `table` says what it is.
- **`components`**: each with a single responsibility you can state in one sentence — if you
  can't, re-cut it.
- **`contracts`**, each belonging to its component: every deliverable component gets ≥1.
  Structurally complete means: `params` typed (or explicitly `[]`), a `returns` type, and ≥1
  named error with semantics or `cannot_fail=true` + reason. "What does the caller see when
  it fails?" is part of the signature, not an implementation detail.
- **The obligations of each contract**, as an `obligations` array on the contract row: one
  entry for the primary behaviour of the signature, one for each named error. Each is a
  `statement` you could hand someone as "this is what you owe" — an obligation is what
  evidence gets mapped to when the work is verified, and what a split hands out when a
  sub-task turns out too big. **You enumerate it here or nobody does.** The set is frozen at
  finalization, deliberately before anyone is under pressure to make a particular split
  pass; a contract that arrives with no obligations is reported as unenumerated, and its
  sub-task can then be neither split nor verified.
- **Dependency edges:** who consumes each contract, recorded as a `depends_on` link from the
  consuming contract to the one it needs. A contract with no consumer and no `is_external`
  mark is invented scope — cut it.
- **Traceability** (`links`): every contract links to the requirement(s) it satisfies;
  every requirement is satisfied by ≥1 contract or explicitly deferred by a linked
  decision with rationale.
- **World-assumed contracts:** a contract whose shape depends on unverified external
  reality (`assumed`/`world`) gets a spike (`register_spike` linking it) or a
  user-accepted-risk decision — never silent hope.

## Divergence round — before presenting your cut
- Ask for the user's instinctive decomposition first ("if you had to split this into three
  boxes, what are they?") and any house constraints (deployment shape, team boundaries,
  build vs buy reflexes).
- Present your cut against theirs and name every divergence — each is a challenge to record
  on the adjudicating decision.

## Packaging round — after the cut is adjudicated
Every component is a task, and **every task belongs to exactly one package**: the build
package it will be worked in. This is the one grouping a human chooses rather than derives,
so it is the one you have to lead the user to — the tool will not invent it, and there is no
catch-all bucket, because a grouping nobody chose is a grouping nobody reviews.

- Propose a cut, with your reasoning: what would be built together, what a single person
  could hold in their head at once, what has to ship before anything else can. Name the
  alternatives you rejected — this is a design decision like any other here.
- `declare_package()` each one the user agrees to, then `assign_task()` every component into
  it. `packaging()` shows the cut so far and what is still outside it; a package is
  referenced by its id and never by its name, so read the ids back rather than retyping.
- A one-package plan is a fine answer — declared, not defaulted. A plan that wants packages
  inside packages is a plan asking to be split; say so rather than nesting.
- Nothing is finalized until every task is placed, so a component left out here surfaces as a
  refusal at the end of package 8 rather than as anything you can ignore.

## Conduct here
- Design decisions here are significant by the code heuristic: a `decisions` row linked to
  a component/contract is rejected without `alternatives`. That is the point — name what
  you rejected and why, one line each. **Link the decision to the components/contracts it
  touches, or the heuristic cannot see it.**
- Present the cut as a whole (components, then contracts per component), rationale first;
  batch the user's adjudications.
- Gate holes about wrong rows are fixed with the named tools: `supersede_row` for corrected
  fields/links, `retire_row` for invented scope — never by duplicate submission.

## Self-review before gate
- Would two components change together for the same reason? Merge or re-cut.
- Do the error names in contracts match the failure handling recorded in package 5?
- Can each requirement's acceptance test be exercised through the contracts alone?
- Is any `type_expr` a disguised "TBD"?
- Does every contract's obligation list cover its errors as well as its behaviour? An
  unlisted error is one nobody will ever be asked to show evidence for.
- Does `packaging()` show an empty unplaced list?

## Exit condition (mechanical gate)
Every deliverable component has a contract; every contract structurally complete; every
contract has ≥1 consumer or `external`; every world-assumed contract has a spike or
accepted-risk decision; requirements ↔ contracts trace both ways.
