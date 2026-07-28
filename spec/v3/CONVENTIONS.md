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

**Entries 3, 5, 6 and 7 were wrong when first written, and the way they were wrong is the
lesson.** They were drafted from the calibration's *reconstructions* rather than from the
codebase, so each described a plausible design instead of the one that exists: an injected
clock (`engine/clock.py` exposes a module-level `now()`), a surface that only ever cites a
contract (the registry has a whole deviation category), one transaction per call
(`finalize_plan` makes two), and one id mechanism where there are two. Corrected 2026-07-28
against the source, after the cold reads of packets 1B to 1E caught three of the four.

This is the guard in §4 failing in its first week, and it failed in the worst direction — a
cited decision stops being reported, so each wrong entry would have silently settled the same
question wrongly across every task that cited it. **An entry must quote the code or the schema
it records.** A convention drawn from anywhere else is a proposal, not a record.

| # | The recurring decision | Answer |
|---|---|---|
| 1 | How does a named error reach the caller? | Raised, as a typed exception per the contract's named errors. Never a status field in a success payload. |
| 2 | Does a call log or emit telemetry? | No. The plan database and the change feed are the record; there is no separate log. |
| 3 | Where does the database connection come from, and who commits? | The `Storage` handle is passed to the service's constructor; the service never opens its own. **A call is one transaction per `write_atomic`, and a call may make more than one** — `finalize_plan` writes nodes, then edges and the plan-state flip. A call needing two must say in its own specification where the seam is and what is true between them. |
| 4 | What happens under two concurrent callers? | Nothing special. One session plans; the writer lock was deliberately removed. Concurrency is not designed for and not defended against. |
| 5 | Is the function on a tool surface, and under what name? | Only if a registry row says so. Most cite a contract; a **deviation** tool cites none and carries a written reason instead. A call that is deliberately *not* exposed carries an absence entry with its reason. A planning session and a building session see different surfaces and never both. |
| 6 | What is a timestamp's source, format and zone? | `engine/clock.py` — `now()` for writing, `parse()` for reading, and nothing outside that module constructs or interprets a stamp. ISO-8601, timezone-aware UTC, microsecond precision. Never `datetime.now()`, and never used for control flow. |
| 7 | How is a new row's identifier allocated? | Two mechanisms, and which one applies is fixed by the table, not by the task. A **plan row** gets a per-table ordinal, `MAX(ordinal) + 1` inside the writing transaction. **Every other table** gets its `id` from `INTEGER PRIMARY KEY AUTOINCREMENT`. Neither is ever reused, and gaps left by rejects are normal. |
| 8 | Is an entity's state stored or derived from its history? | Stored as a column, with the transition table as data rather than code. |
| 9 | What does an error message contain? | The specific field or ref at fault, and never a bare address — every address carries the name of what it addresses. |
| 10 | What does a call do with empty or absent input? | An empty collection is a valid no-op returning an empty result; absent required input is a validation rejection naming the field. |
| 11 | A collaborator was not passed to the constructor. Now what? | Its guard is skipped and its effects are omitted; the call proceeds. A collaborator is optional only where the specification says so, and a task that must not proceed without one says that instead. |
| 12 | A call is being **deleted**. What goes with it? | Its named errors; its registry row, and any payload parser existing only for its parameters; its absence entry if it has one; every model and helper left with no reader; every mention of its name in text the tool emits, because the door refuses a payload naming a call the registry cannot resolve; and its tests. |
| 13 | A word is being **renamed**. How far does the rename reach? | Every identifier derived from it — parameters, private helpers, dataclass fields, dict keys, constants, idempotency-key literals, module and test-module filenames — plus prose in docstrings and emitted text. A rename that stops at the export surface is not finished. |
| 14 | Which spelling, and what about plurals? | British. `behaviour`, not `behavior`. A banned word is banned in its plural and possessive forms too. The Python-packaging sense of `package` is exempt by path, recorded once. |

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

## 5. What it does not cover, found by using it

**The register is service-shaped.** Every entry answers a question about a call: how it errors,
what it writes, where its connection comes from. The cold read of the enforcement packet — a
task whose deliverable is a *test* — found that only three of the ten entries touched it at all,
and none of them settled a decision that mattered. A test's questions are different ones: what
it scans, what counts as a violation, where its list of rules comes from, what its own fixture
asserts so that a silently-narrowing pattern fails loudly.

That is a gap and not a defect in the entries: a convention earns its place by recurring, and
there had been one test-shaped task. It is recorded here so the second and third are noticed,
because the standing evidence is that a check can run green while measuring something narrower
than its name, and that failure has no register entry to prevent it.
