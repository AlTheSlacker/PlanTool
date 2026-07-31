# What the tool serves a builder

**Status: planning artefact.** This is scope item 4 — "return to the fundamental concept of the
MCP, with much more design detail and software engineering, supported by better focus on the
data actually required for the task at hand." It is the largest and least specified of the four,
and it constrains the other three, which is why it is written first.

---

## 1. The diagnosis, counted

v2's surface exposes **54 tools. Six of them serve a builder**: fetch the next unit, compose a
brief, audit a brief, split an oversized unit, report status, verify completion. The other
forty-eight serve planning — filing rows, running gates, resolving gaps, glossary, findings,
conflicts, revisions.

**That is the count as v2 stood, and it is kept here because it is the diagnosis.** The number
has moved since and will keep moving: change 1 removed three tools — the split among them, so
the builder's six are five — and change 2 added `record_grounds`, leaving 51. Re-derive it from
`len(engine.surface.REGISTRY)` rather than quoting this line; the ratio is what this section is
about, and the ratio has not moved.

That ratio is the drift, and it is the whole of scope item 4. **v2 became a plan database with
CRUD tools hung off an MCP surface.** The execution half was an afterthought bolted to the side,
and it has never run.

Two consequences, both measured elsewhere and both explained by this:

- **The builder had no boundary.** The general row-query tool means a builder can read anything
  in the plan. Add the four milestone documents and the codebase, and there is no bound on
  context at all. The "flat context budget as the project grows" that the product exists to
  deliver was never actually enforced anywhere.
- **Serving one unit cost a conversation.** v2's brief composition requires every candidate row
  to be included or omitted **with a written reason** before a unit can be handed over. It is a
  good rule with an unbudgeted cost, and it is why the execution half was never exercised: the
  cheapest path was always to skip it.

## 2. The principle

**The tool call is the context boundary, not a query interface.**

A build session asks for its task and receives *exactly* the specification for that task and
nothing else. There is no browsing, no row query, no "let me check how the neighbouring module
did it". If something is needed to build the task and it is not in what was served, that is a
**hole in the plan**, and the correct response is to stop and file it — not to go and find out.

This is the inversion that makes the product's central claim true. More specification per unit
than could ever be held for the whole project, and a context budget that stays flat as the
project grows, are the same sentence: they are only both achievable if the served bundle is
complete *and* bounded. v2 delivered the bound and not the completeness, which is the worst of
the two, because a bounded incomplete brief forces invention while looking disciplined.

## 3. What a task hands over

The brief for one task, and the justification for each part being in it. Anything not on this
list is not served.

1. **Identity and signature.** The task's name, the externally-callable function it must
   produce, its exact parameters and types, and its return type. Not a description of the
   signature — the signature.
2. **Behaviours, enumerated.** Each one: the condition that triggers it, the effect it must
   have, and for an error, the exact condition and the exact error type raised. This is the
   list the builder is measured against and it is frozen before the builder sees it.
3. **The pseudocode** produced at detailed planning (D9). This is what raises specification
   density from 8 bytes per line to something that can actually be built from.
4. **The catalogue entries the task may call** — name, signature, owning task, and the concept
   each owns. This is what replaces reading the codebase, and it is the single most important
   item on the list after the pseudocode.
5. **The data structures it touches**, defined in full, not by reference.
6. **The glossary terms in force**, so the builder names things the way the plan does.
7. **The decisions that bear on it, with their context** (D11) — what was decided, what was
   rejected and why. Without the argument, a builder rediscovers a rejected alternative and
   quietly reintroduces it.
8. **Its verification:** the behaviour-level checks it must satisfy, and the scenarios that will
   exercise it (D13). A builder should know what it will be judged by.
9. **The boundary — what this task must *not* do.** Which neighbouring concerns belong to other
   tasks. This is the item most often absent in v2, and its absence is where scope crept.

## 4. Composition becomes derivable, and this is the important design move

v2 composed a brief by **conversation**: a candidate set assembled by graph closure, then each
row argued in or out with a written reason. Correct in spirit, unaffordable in practice.

Under D9 it stops being a conversation. **The pseudocode names exactly what the task calls**, and
every name it uses is a catalogue entry (D10) with an owning task. So the closure is *computable*:
the catalogue entries the pseudocode references, plus their signatures, plus the data structures
in the signature, plus the decisions and terms linked to the task. Nothing is argued in or out
because nothing is a candidate — the bundle is what the design already committed to.

That converts brief composition from a per-task conversation into a derivation, which is what
makes the execution half affordable enough to actually run. It also gives the cold read (D14) a
precise input: the reader gets the brief, and only the brief.

**The residual judgment is not eliminated, it moves earlier.** Deciding what a task may call is a
design act, and it now happens when the pseudocode is written, in the planning phase, where it is
reviewable and where it is cheap. That is the correct place for it.

## 5. What the tool can and cannot enforce, stated honestly

A build session is an agent with file access. **The tool cannot prevent it reading the
repository**, and any design that claims to is lying. Three mechanisms make the boundary real
without pretending otherwise:

- **Completeness by construction**, so there is no *need* to look elsewhere. This is the
  brief's contents above.
- **The cold read (D14)**, which proves sufficiency before a builder ever arrives — a session
  with only the brief lists every decision it would have to make and cites the row that answers
  each. An uncited decision is a hole, found at planning time.
- **The returning-invention loop.** Whatever gap survives both of the above, the builder hits
  it, and hitting it is an event that must go back into the plan as a finding against the task's
  specification. That is the only thing that makes the number 79 fall over time rather than
  being rediscovered every project.

The first two make the boundary unnecessary to police. The third makes a breach visible.

## 6. The shape of the surface that follows

Two surfaces, not one. A session is either planning or building, and sees only its own.

**The build surface is small** — that smallness is the design, not an economy:

| Call | Serves |
|---|---|
| next task | The next buildable task in dependency order, or a statement of why nothing is buildable |
| the brief | Everything in §3 for that task, derived per §4 |
| report progress | What was built, against the enumerated behaviours |
| verify completion | Every behaviour discharged, or a refusal naming which are not |
| file an invention | The builder had to decide something the plan did not — a finding against the specification, per §5 |
| file a finding | Something in the plan is wrong, filed against the rows it attacks |

**Notably absent: any row query.** v2's general row-read tool is what made the surface a query
interface, and it does not exist on the build side.

**The planning surface keeps most of v2's forty-eight**, minus what dies with packages and
sub-tasks, plus what the catalogue, labels, pseudocode and scenarios require. It is specified in
the plan document, not here.

## 7. What this commits us to, so it can be argued with

- Planning becomes substantially heavier: pseudocode, catalogue entries, behaviour enumeration
  and scenario specifications for every task, before any code exists.
- The plan becomes comparable in size to the code it produces. That is the trade being made
  deliberately, and it is affordable at build time only because a builder is served one task's
  worth of it.
- If the served brief is incomplete, the builder is now *blocked* where before it would have
  invented. That is the intended behaviour and it will feel like friction. Every block is a
  defect in the plan that the old design would have absorbed silently.

**Open, and marked as my reading rather than the owner's ruling:** the interpretation of "the
fundamental concept of the MCP" in §2. It is designed against here because everything else
depends on it. If it is wrong, this document is the thing to overturn, and §3's brief contents
are the part most worth keeping regardless.
