# Calibrating the cold read against v2's recorded inventions

**Status: planning experiment, run 2026-07-28.** Approved by the owner under D4 (experiments
during planning). It builds nothing and releases nothing for building.

The cold read (D14) is the only one of the interview's five depth mechanisms that measures
*sufficiency* rather than *presence*, so it carries more weight than any other single thing in
the v3 design. This ran it against a labelled test set before it gates anything, because a poor
hit rate would invalidate a whole interview stage and much of the density argument — and we
would rather learn that now than after building it.

---

## 1. The test set is smaller than we have been saying

The set was taken to be "the 79 recorded inventions" — `spec/v2/DEFECTS.md` (52 headings) plus
`spec/v2/DEVIATIONS.md` (28 entries). Classifying all 80 shows they are not one kind of thing:

| | count |
|---|---|
| **Pre-freeze specification holes**, attributable to named plan rows | **37** |
| Build-time bugs and vendored-asset drift | 19 |
| Owner rulings, scope changes, net-new features | 13 |
| Deviations that only restate a defect they resolve | 11 |

Only the first row is a fair target for the cold read. The second row — a revision that stamped
itself with the wrong number, a check whose regex saw four names where there were twenty-two, a
crash on a ref-shaped token in owner prose — is caught by building and driving, not by planning
harder. The third row is the owner changing his mind, which is not a defect at all.

**This does not weaken D1.** 37 unspecified decisions across 68 contracts is still the density
finding. But it changes two things: the calibration denominator is **37**, and roughly a quarter
of what we have been calling planning failures were execution failures, whose remedy is the
returning-invention loop and the unscripted drive (D15), not a deeper specification.

## 2. Sample

Twelve items, stratified by *how* the specification failed. Strata and sample size were fixed
before drawing; the draw was seeded and is reproducible.

| how it failed | pool | drawn |
|---|---|---|
| an undefined term or unstated rule | 11 | nothing defines the current stage · a row's name · digest by value or by reference |
| named, but with no counterpart anywhere | 12 | two spike events nothing fires · the `withdrawn` outcome is unreachable · a backing link nothing writes |
| two rows contradict, or a rule is vacuous | 7 | the brief audit's denominator isn't frozen · findings are two stores under one name · a second finding is swallowed as a retry |
| structural omission | 7 | whose dependents get contested · component ownership was a dropped foreign key · supersession was two transactions |

An unstratified draw was taken first and discarded: it put half the sample in one class, which
random sampling is entitled to do and which would have told us much less.

## 3. Method

For each item, the specification that preceded the invention was **extracted, not paraphrased**,
from the frozen plan at `spec/v2/plan.md` — the contract with its errors and consumed-by line,
every row it links to, the owning component's responsibility, and any state machine it drives.
That is what a v2 builder actually held for that unit of work.

Each was given to a session with no access to this conversation, which was asked to list every
decision it would have to make to implement the function, including the obvious ones, and to cite
against each the row that settles it. Uncited means a hole. Twelve items needed ten specifications
— `file_finding` carries two of the sampled defects, and the spike specification carries two.

**Blindness controls, and their limit.** The specification was passed inline, all tool use was
forbidden, and every run reported **zero tool uses**, so none of them opened the defects file.
That is good evidence but not proof: the reader shares a filesystem with the answer key. A
stronger control would be a machine with no copy of the repository, and that is worth doing if
this number ever becomes load-bearing.

## 4. Result: 11 of 12 caught, 1 partial

| what v2 had to invent | caught? | what the cold read said |
|---|---|---|
| how the current stage is determined | **yes** | "How the 'current stage' is determined — UNCITED" |
| what names a row | **partial** | flagged the field set of a submission, and the validation rules, as uncited — the container of the hole, but never asked what a row is called |
| whether the digest carries the mandate or points at it | **yes** | "Whether the mandate and stage script are inlined in full or returned by reference/handle — UNCITED" |
| nothing fires a spike's `start` or `unblock` | **yes** | named both, then derived the consequence: a spike can never legally reach `executing`, and `executing` is the only state `conclude` is legal from |
| whose dependents a failed validation contests | **yes** | "How rows that depend on the assumption/claim are identified — UNCITED" |
| the brief audit's denominator is not frozen with the brief | **yes** | "Whether the closure is recomputed at audit time or read from a snapshot stored at composition — UNCITED" |
| supersession's two writes are not one transaction | **yes** | "Whether the create-plus-stamp pair is one all-or-nothing transaction spanning two rows — UNCITED" |
| the `withdrawn` outcome is unreachable | **yes** | "What state outcome 'withdrawn' produces, given no 'withdrawn' state exists in the machine" and "Who emits the dispute and uphold events, since no function in this surface does" |
| nothing writes the link that makes an assumption "backed" | **yes** | "Whether a merely registered spike makes its assumption count as 'backed' for the quality gate — UNCITED" |
| `findings` names two different stores | **yes** | refused the table as a citation and called it "a decoy": it describes the plan's own red-team records, not the storage the tool writes into |
| a second finding on the same rows is swallowed | **yes** | "Whether a replayed/retried identical call creates a second finding row or returns the existing one — UNCITED", noting the signature and the idempotency decision are in tension |
| which component owns a contract | **yes** | "How a contract's owning component is determined (trailer line vs the enclosing document heading) — UNCITED" |

Two results are worth more than their tick. The `findings` reader was handed a line that
*looked* like it answered where findings are stored, and declined to cite it — in v2 that
collision cost a red team filing every finding where the gate could not see it, and a gate
reporting "no adversarial findings recorded" however many were filed. The spike reader was not
told anything was wrong and reasoned unprompted to the same conclusion v2's pre-build audit
reached.

**Seven further recorded inventions were caught incidentally**, from specifications sampled for
something else: parameter types with no defined shape, contradiction never defined, no way to
link to a sibling in the same batch, "working set" and "accumulated learnings" undefined, prose
citations left dangling by supersession, `contract_deps` not existing, and the split having no
mechanism for superseding the original. Nineteen of the 37 holes were therefore touched by ten
readings.

### The second run, and what it says about the one miss

D14 accepts non-determinism and prescribes running more than once and taking the union. Two
specifications were re-read blind: the clean hit, and the partial.

The **hit reproduced** — the second reading of the gap engine again returned "how the 'current
stage' is determined — UNCITED", from a list that otherwise differed substantially (50 decisions
against 60). So the lists are unstable while the substantive holes in them are not, which is the
best case for the union rule: it costs a second run and buys coverage rather than confidence in
a number.

The **partial did not improve.** A second reading of row submission again flagged the submission's
field set, the validation rules and the storage schema as uncited, and again never asked what a
row is *called*. The union does not rescue it, so this is a structural limit rather than noise,
and it is worth naming precisely: **the cold read finds decisions the task's own implementation
forces, not decisions imposed by a consumer the specification never mentions.** Nothing in the
submission contract hints that a row is ever shown to a human, so nothing makes the name
question arise. Both runs did reproduce two bonus catches, contradiction detection and the
within-batch link, which are forced by the implementation.

The countermeasure already exists and is not the cold read: this is what the divergence rounds
and the "what will consume this, other than the thing you are building now?" question are for.

## 5. The real finding is the volume

The counts the hit rate does not show:

| | per specification |
|---|---|
| decisions listed | 46 to 80, mean **63** |
| of those, uncited | 20 to 47, mean **35** |
| uncited share | **55%** |

Re-reading the same specification produces a list of a different length with much the same holes
in it, so the volume is a property of the method, not of one run.

At v3's projected ~255 tasks that is on the order of **9,000 uncited decisions**. A hit rate
alone cannot tell insight from a shotgun, and this is close to a shotgun: alongside "how is the
current stage determined" sit "sync vs async", "logging and observability", and "how the function
obtains its database connection".

So the raw uncited count is not usable as a gate number, and the proposal in `INTERVIEW.md` §8 —
that a task is specified deeply enough when the cold read finds no holes — **cannot stand as
written.** It would never terminate.

What survives, and is worth more, is that the holes are **legible when read**. Every one of the
twelve was recognisable on sight in a list of sixty. The output is a triage surface, not a
verdict, and the stage has to be designed as one: the reader produces the list, and a pass over
it promotes the real holes to findings against the specification. That pass is judgment, which
this project normally refuses to put in the engine — but here it sits at planning time, in front
of the owner, which is exactly where the design already puts judgment.

## 6. What this settles, and what it does not

**Per task, not per component.** The open question in `INTERVIEW.md` §8 is answered by the
evidence rather than by argument. Four of the twelve holes are *cross-contract* — nothing fires
`start`, nothing emits `dispute`, nothing writes the backing link, nothing says which component
owns a contract — and every one was caught from a **single task's** specification, because the
reader was given the component's responsibility line and the state machine the task drives. The
unit is the task; what matters is that the packet includes the neighbours the task touches.

**Pseudocode depth stays open, and the answer is not a length rule.** The depth test cannot be
"no holes". A workable replacement, on this evidence: the pseudocode is deep enough when every
uncited decision left in the list is one whose answer could not change the shape of another
task. That is still a judgment, but it is the same judgment the triage pass is already making.

**Do not quote a hit rate as an assurance.** Twelve items, one reader, and the specifications
were reconstructed by someone who knew the answers — a real bias, mitigated by extracting rather
than writing the inputs, but not removed. The result is strong enough to keep the cold read as a
stage. It is not strong enough to claim a number.

**The cold read is still weaker than building.** It addresses 37 of the 80 recorded items and,
by construction, none of the 19 build-time bugs. The unscripted drive (D15) and the
returning-invention loop are not made redundant by a good hit rate here — this experiment
measures the half of the problem that planning can reach.
