# Stage 6 — Architecture (synthesize mode)

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
- **The behaviours of each contract**, as a `behaviours` array on the contract row: one
  entry for the main effect of the signature, one for each named error. Each is a
  `statement` you could hand someone as "this is what you owe" — a behaviour is what
  evidence gets mapped to when the work is verified. **You enumerate it here or nobody
  does.** The set is frozen at finalization, deliberately before anyone is under pressure to
  make a particular verdict pass; a contract that arrives with no behaviours is reported as
  unenumerated, and its task can then not be verified at all.
- **Dependency edges:** who consumes each contract, recorded as a `depends_on` link from the
  consuming contract to the one it needs. A contract with no consumer and no `is_external`
  mark is invented scope — cut it.
- **Traceability** (`links`): every contract links to the requirement(s) it satisfies;
  every requirement is satisfied by ≥1 contract or explicitly deferred by a linked
  `deferrals` row saying why — that is the table the gate reads.
- **World-assumed contracts:** a contract whose shape depends on unverified external
  reality (`assumed`/`world`) gets a spike (`register_spike` linking it) or a
  user-accepted-risk decision — never silent hope.

## Divergence round — before presenting your cut
- Ask for the user's instinctive decomposition first ("if you had to split this into three
  boxes, what are they?") and any house constraints (deployment shape, team boundaries,
  build vs buy reflexes).
- Present your cut against theirs and name every divergence — each is a challenge to record
  on the adjudicating decision.

## Conduct here
- Every component and contract carries its own `grounds` and `alternatives`, and the gap
  engine counts the ones that do not. What a rule cannot check is whether the argument is
  any good: an alternative that was never a live option is a strawman, and "simpler" with
  nothing measured against it is a preference wearing an argument's clothes. Write the one
  a reader could use to overturn you.
- Present the cut as a whole (components, then contracts per component), your reasoning
  first; batch the user's adjudications.
- Gate holes about wrong rows are fixed with the named tools: `supersede_row` for corrected
  fields/links, `retire_row` for invented scope — never by duplicate submission.

## Self-review before gate
- Would two components change together for the same reason? Merge or re-cut.
- Do the error names in contracts match the failure handling recorded in stage 5?
- Can each requirement's acceptance test be exercised through the contracts alone?
- Is any `type_expr` a disguised "TBD"?
- Does every contract's behaviour list cover its errors as well as its main effect? An
  unlisted error is one nobody will ever be asked to show evidence for.

## Exit condition (mechanical gate)
Every deliverable component has a contract; every contract structurally complete; every
contract has ≥1 consumer or `external`; every world-assumed contract has a spike or
accepted-risk decision; requirements ↔ contracts trace both ways.
