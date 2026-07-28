# The conventions register

**Status: planning artefact, and a real plan table in v3.** It is the answer to the noise the
cold-read calibration found, and it is the mechanism behind the pseudocode depth rule in
`INTERVIEW.md` §8.

---

## 1. Why it exists

The calibration ran ten task specifications through a blind cold read. Each produced a mean of 63
decisions, **35 of them uncited**. At v3's scale that is around nine thousand holes, which is not
a number anyone can act on.

Reading the ten lists side by side shows why, and it is not that the reader was being silly.
The same decisions came back task after task: how an error surfaces, whether the call logs
anything, where the database connection comes from, what happens under two concurrent callers,
what a timestamp's source and timezone are. Ten specifications asked those questions ten times
because **nothing in the plan had answered them once.**

That is a DRY failure in the specification itself — the identical question posed 255 times — and
the fix is the same as it is in code. Answer it once, in one place, and cite that place.

## 2. The test for entry, and the trap in it

A decision belongs in this register when it recurs across tasks **and every task gets the same
answer.** Both halves are load-bearing, and the second one is where this could quietly go wrong.

The most frequent decision across the ten readings was *what fields the return type has* — it
came up in nine of ten. It is **not** a convention. Every task returns something different, so
the answer differs every time, and a register entry saying "returns are dataclasses" would settle
nothing while appearing to. That decision is a hole in each task, and it is a recorded v2 defect:
the plan named `WriteBatch`, `RowSelector`, `TraversalSpec` and `GraphScope` and defined none of
them, so two implementers would have built two incompatible interfaces.

So: **recurrence alone does not admit an entry.** If the answer varies by task, it is a hole in
every task and belongs in the specification, not here. Getting this backwards would turn the
register into a machine for hiding exactly the defects the cold read exists to find.

## 3. The starter register

Drawn from the decisions that recurred across the ten calibrated readings with a single answer.
Each entry is a plan row with the usual provenance and decision context; several are recording
what v2 already does rather than deciding anything new.

| # | The recurring decision | Answer |
|---|---|---|
| 1 | How does a named error reach the caller? | Raised, as a typed exception per the contract's named errors. Never a status field in a success payload. |
| 2 | Does a call log or emit telemetry? | No. The plan database and the change feed are the record; there is no separate log. |
| 3 | Where does the database connection come from, and who commits? | Injected by the caller; the service never opens its own. One call is one transaction unless the contract says otherwise. |
| 4 | What happens under two concurrent callers? | Nothing special. One session plans; the writer lock was deliberately removed. Concurrency is not designed for and not defended against. |
| 5 | Is the function on a tool surface, and under what name? | Only if a contract row says so. A planning session and a building session see different surfaces and never both. |
| 6 | What is a timestamp's source, format and zone? | The injected clock, ISO-8601, UTC. Never `datetime.now()`, and never used for control flow. |
| 7 | How is a new row's identifier allocated? | Per-table ordinal, allocated at write inside the writing transaction; never reused, and gaps left by rejects are normal. |
| 8 | Is an entity's state stored or derived from its history? | Stored as a column, with the transition table as data rather than code. |
| 9 | What does an error message contain? | The specific field or ref at fault, and never a bare address — every address carries the name of what it addresses. |
| 10 | What does a call do with empty or absent input? | An empty collection is a valid no-op returning an empty result; absent required input is a validation rejection naming the field. |

## 4. How it grows, and the guard on it

**It grows from cold-read output, not from anticipation.** When the same uncited decision appears
in cold reads of three different tasks with the same answer, it is proposed as an entry. Nobody
sits down to imagine conventions in advance; that produces a document of plausible rules nobody
consults.

**The guard.** A convention is exactly as dangerous as it is useful: it settles a decision for
255 tasks at once, which means a wrong one is wrong 255 times, and it does so invisibly, because
a cited decision stops being reported. Two things hold against that:

- Each entry carries its decision context (D11) — the reasoning and what was rejected — like any
  other decision, so it can be argued with rather than merely obeyed.
- **A task may override an entry, in its own specification, with a written reason.** The
  override is what makes the register a default rather than a law, and the reason is what makes
  an override reviewable. A register with no overrides after 255 tasks is a register nobody
  tested.

**It is not a style guide.** Entries answer questions a cold read actually asked. Naming, layout
and formatting belong to tooling, not here.
