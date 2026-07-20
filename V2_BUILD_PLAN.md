# PlanTool v2 — Build Plan

Status: draft for review · 2026-07-20 · branch `v2-build-plan`

## 1. What v2 is

A self-contained Python system that:

- interviews the user and stores appropriately linked plan data
- permits edits and refinement through discussion between the user and the assistant
- supplies critical analysis, pushback and recommendations rather than transcribing
- validates claims against reality (spikes) and against the literature (scientific claims)
- documents the reference papers behind those claims, verifiably

v2 is a **rewrite and improvement of v1**, not a functionality extension of it. Where the
frozen plan specifies capability v1 lacked, that capability is in scope only if it improves
the plan-authoring loop. Capability that drives *execution of the plan* is explicitly out —
see §3.

v2 is built **from** the frozen plan at `spec/v2/plan.md`. That plan is read-only. It is the
specification, not a starting point for re-derivation.

## 2. Governing constraints

Carried from the frozen plan; these are settled and not to be relitigated.

| Constraint | Source |
|---|---|
| No direct LLM API integration or API-key management | `decisions:12`, `requirements:75` |
| Interoperates with any MCP-compliant LLM CLI engine | `requirements:75` |
| Cross-platform | `requirements:1` |
| One process, one SQLite plan file in the workspace | `decisions:50` |
| Tool records judgment; it never exercises judgment | `decisions:12` |

The last one is the design spine. `compose_brief` states it plainly: selections are made by
"the planning-session LLM ... never by the code engine or by the tool itself". Every feature
in v2 obeys it, including references (§5).

The no-LLM-API constraint has a consequence worth stating up front: **there is no embedding
model available to the tool**, so there is no vector search and no semantic retrieval. All
retrieval is lexical (SQLite FTS5) or structural (sections, links).

## 3. Scope

### In — 13 components

Foundation: `storage-engine`, `row-service`, `link-graph`
Planning: `guidance`, `gap-engine`, `gate-engine`, `warning-service`, `conflict-service`,
`validation-service`, `finding-service`
Surface: `session-service`, `mcp-surface`
Plus `revision-service` in reduced form (§4.1).

### Deferred to a later "execution module"

`task-graph` (`components:11`) and `brief-composer` (`components:12`), entire.

These are one module, not two. `compose_brief(subtask_id, selection)` has no input without a
graph producing sub-task ids, and `next_subtask` exists to feed it. The frozen plan groups
them as an execution layer; splitting them would produce a component that cannot be called.

This module is "how the plan drives development" and is to be designed in its own right —
see §7, M7.

### Out entirely for now

GUI, and plan-extraction/rendering beyond what v1 already does.

## 4. Deliberate deviations from the frozen plan

The plan is frozen and cannot be amended. Every departure below is logged in
`spec/v2/DEVIATIONS.md` with its reason, so the plan and the build never silently disagree.

### 4.1 revision-service, reduced

`open_revision` already refuses draft plans: *"draft plans are edited directly through the
interview; revisions exist for finalized plans."* The core loop — snapshot, version bump,
link-graph impact walkthrough, per-item owner adjudication, atomic apply or clean rollback —
is independently useful with no execution layer, and is **in scope**.

Deferred with the execution module (these are clauses inside `open_revision` and
`adjudicate_repercussion`, not separate contracts):

- freezing in-flight sub-tasks
- regenerating affected briefs
- flagging already-built work as needing rework at apply time

### 4.2 Pluggable surface

The frozen plan makes `mcp-surface` (`components:15`) the sole consumer of every service
contract. A GUI and the execution module are both future consumers of those same services.

v2 places a service layer beneath the surface and makes MCP the **first adapter** rather than
the assumed one. This is the cheapest structural change available now and an expensive one
later.

This is itself a methodology defect against the frozen plan: the architecture was frozen with
no extension seam and no story for a second consumer. Logged as such.

### 4.3 References as first-class rows

`record_claim_outcome(claim_id, outcome, evidence: str)` reduces the justification for a
scientific claim to a free string. Every other justification in the system is a linked row.
v2 makes sources and extracts real rows. Full design in §5.

## 5. Reference and citation design

### 5.1 Problem

Papers may arrive as PDF, text, or URL. They may be large. Three failure modes would each be
sufficient to derail a technical study:

1. **Fabrication** — a finding attributed to a paper that does not contain it
2. **Conflation** — a real finding attributed to the wrong paper
3. **Omission** — a critical detail elsewhere in the paper that was never extracted, later
   answered from model memory instead of from the source

A system cannot prevent the assistant from being wrong. It can ensure **a hallucination
cannot acquire a citation**, which is the property that matters.

### 5.2 Three tiers

| Tier | Contents | Travels into context? |
|---|---|---|
| Source row | title, authors, year, DOI/URL, local path, content hash | listing only |
| Extract row | verbatim quote + locator + optional paraphrase | **yes — this is the citation unit** |
| Full text | stored once under `refs/`, hashed | on demand only |

Plan rows link to **extracts, not to sources**. A closure walk therefore returns the one
paragraph that matters, not a 40-page document. Cost control falls out of the existing
link-graph rather than needing a bespoke mechanism.

**Invariant: papers are inert until cited.** Nothing about a source enters context unless a
plan row links to one of its extracts. Ingest costs one read, once.

### 5.3 The verification rule

> An extract cannot be written unless its verbatim quote is an exact substring of that
> source's stored text.

Normalized for whitespace and line-break hyphenation; otherwise byte-exact. Character offset
stored. Re-verified on read, so corruption or re-ingestion drift surfaces rather than rotting.

No LLM required — this is `str.find()`.

- Kills **fabrication**: invented text cannot pass a substring check.
- Kills **conflation**: the quote is checked against that specific `source_id`.
- Does not kill **misinterpretation** (real quote, wrong gloss). Mitigation: the quote is
  permanently adjacent to the paraphrase, so verification costs one sentence read rather than
  a re-read of the paper.

Corollary, and the answer to omission: **a plan row cannot cite a source without an extract,
and an extract cannot exist without a verifying quote.** Asserting what a paper says requires
searching the stored text and quoting it. Model recollection is structurally unable to enter
the plan; it can only prompt a lookup.

### 5.4 Retrieval — sections *and* keyword

**Sections** via heading detection at ingest. Structural, no judgment. Yields meaningful
locators and makes bounded reads possible.

**Keyword** via SQLite FTS5 over full text, scoped to one source or across all. Lexical
search underperforms semantic in general, but scientific terminology is precise and shared
between plan and paper, so BM25 does unusually well here — and the session can reformulate a
query that misses.

**Coverage meter** (the reason to have both): the tool records which sections have ever been
drawn from. A paper cited from Results and Methods but never from Limitations is a gap, and
Limitations is where study-killing caveats live. This routes to `gap-engine`, which already
exists to surface exactly this class of omission.

### 5.5 Workflow

The user supplies a feature name and a paper name. The session searches that source, reads
candidate spans, and files extracts with quotes. User input stays two strings; the reading is
the assistant's; the verification is the tool's. No manual snippet-to-detail assignment.

### 5.6 Decisions taken

- **Storage**: source files in `refs/`, gitignored. Hash, metadata and extracts in the DB.
  Papers are large and usually copyrighted. *Consequence*: on a machine without the files,
  quotes cannot be re-verified — extracts remain readable but the mechanical check degrades
  to trust.
- **Supersession**: sources supersede each other with bidirectional lineage, as decisions do.
  Retractions and revised editions must invalidate extracts loudly.
- **Link scope**: extracts may link anywhere in the plan. Restricting to claims/decisions
  would make "which papers underpin this plan" easier to answer but would push users into
  filing fake claims to attach evidence.
- **No tool-side fetching**: the session fetches; the tool stores the retrieved copy plus its
  hash. Citations then survive URL rot, which is the actual requirement.

### 5.7 Known limits

- **Selective quoting**: an accurate quote can still reverse meaning out of context. Storing
  a surrounding window and retaining the locator reduces this; it does not solve it.
- **PDF fidelity**: extraction mangles equations, ligatures, hyphenation and multi-column
  flow, so legitimate quotes may fail to verify. Raw extracted text is stored visibly so the
  user can see what the tool believes the paper says.
- **Ingestion pipeline is stubbed**: PDF parsing and URL fetching are deferred behind a
  manual path (point at a file or paste text). The *verification rule* is built now, because
  invariants are painful to add once violating rows exist.

## 6. Repository layout

```
PlanTool/
  archive/v1/        v1 engine, server, tests — preserved, runnable
  spec/v2/           frozen plan.md + plan.yaml + spikes/ + DEVIATIONS.md
  refs/              source files (gitignored)
  engine/            v2
  tests/             v2
```

`D:\PythonProjects\LLM_Manager_Plan\` is deleted **after** its plan exports, DB and spike
evidence are moved into `spec/v2/`. Its `.claude/`, `.mcp.json`, `CLAUDE.md`, `AGENTS.md` and
`__pycache__` are disposable.

## 7. Milestones

Each is a branch and a PR. Al merges; no self-merges.

| M | Content |
|---|---|
| 0 | Rescue spec to `spec/v2/`; archive v1; delete `LLM_Manager_Plan`; `DEVIATIONS.md`; v2 skeleton + test harness |
| 1 | Foundation: `storage-engine`, `row-service`, `link-graph`, **reference row types + verification rule** |
| 2 | Interview core: `guidance`, `gap-engine`, **section coverage meter** |
| 3 | Enforcement: `gate-engine`, `warning-service`, `conflict-service` |
| 4 | Reality-testing: `validation-service`, `finding-service` |
| 5 | Surface: `session-service`, `mcp-surface` on the pluggable seam (§4.2) |
| 6 | `revision-service`, reduced form (§4.1) |
| 7 | Dogfood: plan the execution module **using v2** |

Within each milestone, contracts are built in `contract_deps` order, one contract per unit of
work.

M2 carries the most product risk and should be expected to iterate. The frozen plan records
the user's own verbatim complaint about v1: *"I did not feel pushed that hard to add any [use
cases], how are you sure you have captured all of them? I think the discussion aspect needs to
be expanded from the prototype."* Interview quality is worth more than any component beneath
it.

M7 is the payoff. The execution-module design discussion becomes v2's first real plan, which
tests v2 the way the dogfood tested v1.

## 8. Success metric

**Execution sufficiency.** Every time the build hits missing or ambiguous information in the
frozen plan and must ask the user or invent something, that is a logged methodology defect.
Log it; do not paper over it. A low count validates the planning method. A high count is the
finding, and is equally valuable.

Defects are recorded in `spec/v2/DEFECTS.md` with the contract or row that was insufficient.

## 9. Open

- The execution module (`task-graph` + `brief-composer`) — design discussion pending, M7.
- GUI — not started, no design.
- Plan extraction/rendering — "how we extract the plan most effectively", not started.
