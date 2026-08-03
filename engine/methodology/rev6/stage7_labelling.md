# Stage 7 — Labelling (synthesize mode)

**You are the source of truth here, and the user owns the words.** The plan is now written
and about to be read — by the red team next, and by whoever comes back to it in six months.
This round makes it readable in slices.

**A label is a glossary term.** There is no separate label vocabulary and no
`propose_label`: `attach_label` refuses any word the glossary does not hold, and
`define_term` is how you mint one. If you have read D12 and are looking for a way to propose
a label, this is it — define the word, with what it means, then attach it.

That refusal is the whole of the glossary's mechanical role. Nothing else in this engine
scans the glossary, counts it, gates on it or warns from it.

## What this round replaces

The declared build grouping (v3 D7). A grouping was a *level*: every row sat in exactly one,
everything under it inherited it, and the thing a person actually used it for was filtering
a review list. A label is an attachment instead, so a row carries as many as make sense and
none of them claims to be its home — and a filter that was never really a hierarchy stops
pretending to be one.

## Coverage checklist

- **Ask the user which words they want the plan sliced by.** Not which words you would
  choose: a label is a filter *they* will read the plan through. The words that carried
  weight in the interview are the candidates, and they have been saying them for eight
  stages.
- **Define each one** with `define_term`, in their words, with what it means here. A word
  listed with no meaning beside it is a word two readers read two ways.
- **Attach with `attach_label(word, targets)`** — plan rows by address, tasks by id, or a
  mix in one call. Re-attaching something that already carries the word is a no-op, so a
  second pass over the same rows costs nothing.
- **Read `labels()` when you think you are done.** It reports each word with two counts,
  rows and tasks, against the live totals. That is the check that matters: a label on every
  row and a label on one row are both useless for filtering, and only the counts beside
  their denominators tell you which you have made.
- **`read_rows(selector={"labels": [...]})`** filters by them, and every word given must be
  carried — it is an AND, not an OR. Ask for a label and a typo and you get nothing, which
  is what AND means.

## Conduct here

- **No count decides anything and no threshold exists.** There is deliberately no warning
  above some number of labels on a row, and none below some coverage: a rule saying five is
  fine and six is not is a judgment written as arithmetic so review cannot see it.
- **Removing a word is `remove_term`, and it will refuse** while anything carries it,
  telling you how many plan rows and how many tasks — two counts, never their sum. The
  refusal is the question: the user either names a replacement word, which every attachment
  moves to, or says take it off everything. It is theirs to answer, not yours to assume.
- **Detaching stamps rather than deletes.** A detached attachment stays as the record that
  the label was once there, which is also why a removed word can still be named by one.
- This is a synthesize round, so the user adjudicates rather than dictates — but the
  vocabulary is the one part of the plan that is theirs outright, and a label you invented
  and they never agreed to is a filter that means something only to you.

## Gate

`run_gate(7)` has no mechanical criteria, and that is deliberate rather than an omission.
Every check this round could carry would be a threshold — how many rows must be labelled,
how many labels a plan needs, how broad is too broad — and each of those is a judgment the
tool does not make. What a gate could check, it should not.
