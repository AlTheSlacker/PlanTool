# plantool — Stage 1 Build Specification

**Status:** approved for build · **rev 2** (2026-07-15, folds in review changes 1–20) · **Owner:** Al
**Scope of this document:** Stage 1 only — the interview engine, MCP server, and plan database. Stages 2 and 3 (described in §2) are future work but impose schema requirements marked **[S2]**/**[S3]** throughout. Build them into the schema now; build no features for them.

Rationale archive (optional background, not needed to build): `D:\PythonProjects\LLM_Manager\discussion\011–016_*.md`.

---

## 1. What this tool is

An LLM-led project-planning tool for software implementations. A user opens their CLI coding agent (any MCP-capable CLI; Claude Code first for testing) in a planning workspace and holds a conversation. The model interviews the user, records every planning fact as a **typed row in SQLite**, runs throwaway **spike experiments** to verify assumptions about the world, and cannot advance past **mechanical gates** enforced in code. The output is an ultra-detailed plan — down to interface contracts and signatures — stored in a database and exportable to readable documents and a structured bundle.

Core thesis: *the checklist enforcer that never gets bored.* Every planning technique used here is decades old and works when applied; it gets skipped because applying it exhaustively exhausts humans. The LLM does the tedium; the engine (plain code, no LLM) does the enforcement; the user makes only the decisions that are genuinely theirs.

Design principles (settled, do not relitigate):
1. **Plan hard.** Boundaries/contracts/data models are fully specified before code; component internals are decided at implementation time inside frozen contracts.
2. **Enforcement lives in code, not prompts.** A gate is a query plus a rule. Prompts guide; the engine refuses. Where a rule *cannot* be code-enforced, the spec says so openly (§5.1) rather than pretending.
3. **The DB is the source of truth; the model's context is a disposable conversational surface.** Any session, any vendor, can die at any moment and a new one resumes losslessly.
4. **Provenance on everything.** No silent invention by the model.
5. **Spikes verify the world.** Assumptions about external behaviour are resolved by experiment during planning, never left for implementation.
6. **Tool results are the only delivery surface.** Tools are the sole MCP capability every client must support. Everything the model needs — role, stage scripts, gap context — arrives as the return value of a tool call. MCP prompts, resources, and elicitation are never load-bearing.
7. **Agnostic twice over.** (a) LLM/CLI-agnostic: the user drives their CLI exactly as they always do; the tool bootstraps itself through tool descriptions and one template instruction file. (b) Language-agnostic: the planned project's stack is planning *data* (elicited in stage 1, recorded as decisions), never tool configuration. Nothing in the engine assumes the target is any particular language.

## 2. Product roadmap context (for orientation only)

- **Stage 1 (this build):** interview → plan DB, gates, spikes, export.
- **Stage 2 (future):** extraction — `get_task_pack()` serves small per-task context packs (1–2K tokens) to implementation sessions instead of large prompts; compiled artifacts (per-language stubs, spec.md). **[S2]** requires: every row addressable and scoped, dependency edges explicit, pack manifests recordable, `plan_version` on substantive rows, a staleness flag path, contracts stored as structure (not prose) so they slice cleanly into packs.
- **Stage 3 (future):** integration with a project-management layer (plan→deliver→measure→replan loop). **[S3]** requires: stable export bundle format; rework/deviation metrics derivable later — nothing extra in stage 1 beyond versioning.

## 3. Architecture

```
plantool/                        # its own repo (not inside LLM_Manager)
  engine/                        # plain Python, no LLM calls anywhere
    schema.sql
    db.py                        # thin sqlite3 wrapper; one DB file per plan; WAL + busy_timeout on open
    gaps.py                      # next_gap() priority walker
    gates.py                     # one function per gate
    render.py                    # export: plan.md, plan.yaml (round-trippable); reimport
  server/
    main.py                      # MCP server, official python `mcp` SDK (FastMCP), stdio transport
    prompts/                     # interview scripts — READ BY THE SERVER, returned inside tool
                                 # results (plan_start, plan_status, run_gate, get_stage_prompt).
                                 # NEVER registered as MCP prompts (those are user-invoked
                                 # slash commands in most clients; the model can't fetch them).
      stage1_context.md … stage8_freeze.md, spike_protocol.md, redteam.md
  workspace-template/            # copied per project being planned
    .mcp.json                    # stdio launch config for server/main.py
    AGENTS.md                    # ≤5 lines: "planning workspace; call plan_status() then
                                 # next_gap(); follow instructions returned by tools"
    CLAUDE.md                    # one line: pointer to AGENTS.md (Claude Code convention)
    spikes/                      # quarantine dir for spike code
  tests/                         # incl. gate unit tests against fixture DBs (§9)
```

- **stdio MCP**: the CLI spawns/kills the server per session automatically. No daemon.
- **One SQLite file per plan**, stored in the planning workspace so the plan travels with the project folder. Opened with `journal_mode=WAL` and a `busy_timeout` — two concurrent sessions on one workspace must degrade gracefully, not corrupt or hard-fail.
- **Bootstrap without user retraining:** the `plan_status` tool description itself says *"Planning workspace status. Call this first in any session in this workspace, before responding to the user."* Tool descriptions reach every MCP client automatically; the AGENTS.md/CLAUDE.md files are belt-and-braces for clients that read instruction files.
- Python 3.12+, stdlib `sqlite3` (no ORM), `mcp` SDK, `pyyaml` for export. Nothing else without cause. (The engine being Python is an implementation detail; it plans projects in any stack.)

## 4. Data model (schema v1)

All substantive tables carry: `id`, `plan_id`, `plan_version_added`, `provenance`, `created_at`. `provenance ∈ {decided, derived, assumed, verified}` — `decided` = user chose it; `derived` = follows from a recorded requirement/decision (store the link); `assumed` = model filled a gap, pending confirmation; `verified` = upgraded from `assumed` by a spike (`spike_id` required). **Every `assumed` row also carries `assumption_kind ∈ {world, intent}`**, set at submit time — `world` = a fact about external reality (resolvable by spike), `intent` = a fact about what the user wants (resolvable only by the user). Only the user upgrades intent-assumptions (→ `decided`); only a spike upgrades world-assumptions (→ `verified`). `next_gap()` routes on this field (§6).

Tables:

| table | purpose / key fields |
|---|---|
| `plans` | name, tier (hardcode `standard`), current_stage, version, state (open/frozen) |
| `use_cases` | title, actor, main scenario as ordered steps (child table `uc_steps`) |
| `uc_steps` | ordered step text; `no_extension_reason` (nullable) — the queryable home of "can't fail because…" for the stage-2 gate |
| `uc_extensions` | step_id, failure/variant description, in_scope bool, handling |
| `requirements` | ears_type ∈ {ubiquitous, event, state, unwanted, optional} **plus typed slots per type** — ubiquitous: `system_response`; event: `trigger` + `system_response`; state: `precondition` + `system_response`; unwanted: `trigger` (the unwanted condition) + `system_response`; optional: `feature` + `system_response`. The engine assembles the canonical EARS sentence from the slots — structure is validated, prose is never regex-parsed. NFRs additionally get planguage_scale, planguage_meter, planguage_target |
| `entities` | name, description, `has_lifecycle` bool + reason — state machine required iff true; a `false` needs a recorded justification (adjudicated like any synthesize-mode proposal) |
| `crud_grid` | entity_id × {C,R,U,D} → responsible actor/component or explicit `n/a` + reason; children-on-delete noted |
| `state_machines` / `sm_cells` | entity_id (lifecycle entities only), states, events; each state×event cell = transition or explicit `impossible` + reason |
| `components` | name, responsibility |
| `contracts` | component_id, name, kind (api/function/schema/file/event), **structured signature**: `params` (each: name, type_expr, required), `returns` type_expr, `errors` (each: name, semantics) or explicit `cannot_fail` + reason. Type expressions are free text *in the target stack's notation* — recorded, never compiled. Language-neutral by construction; makes [S2] packs sliceable and later per-language stub renderers a thin walk of structure. `stale` bool **[S2]** |
| `contract_deps` | consumer contract/component → provider contract (dependency edges) **[S2]** |
| `dependencies` | external dependency of the planned system: name, kind (service/library/api/filesystem/…), notes — the queryable object behind the stage-5 gate |
| `dep_failure_modes` | dep_id × mode ∈ {unavailable, slow, malformed, auth, partial} → handling + links; stage-5 gate = all five rows exist per dependency |
| `decisions` | text, rationale, provenance, links (JSON of related row refs); ADR-shaped: `alternatives` (JSON: each with one-line rejection reason), `challenge` (none \| raised{text, outcome: overridden\|revised}); `significant` bool — **set by heuristic, not by the model**: any decision whose links touch a component or contract is automatically significant (coarse but ungameable) |
| `open_questions` | text, state (open/resolved/deferred), owner, resolution |
| `conflicts` | description, refs (JSON row refs), source ∈ {engine, model}, state (open/resolved), resolution — engine files the mechanically detectable ones, the model files the semantic ones it notices; both drain through `next_gap()` priority 1 |
| `spikes` | question, hypothesis, method, budget, verdict ∈ {confirmed, refuted, inconclusive}, evidence_path, linked row refs |
| `findings` | source (redteam/premortem), text, disposition (fixed/accepted/spiked) + rationale |
| `gate_results` | stage, passed, holes (JSON), run_at |
| `pack_manifests` | **[S2]** — create the table, unused in stage 1 |

Schema churn is expected until the first real plan freezes; migrations are `DROP TABLE` until then. **The escape hatch is `plan.yaml`: export is round-trippable (export → recreate DB on new schema → reimport), which is the poor man's migration protecting the dogfood plan across churn.** Build no migration machinery beyond that.

## 5. MCP tool surface (v1, all typed)

**Every `submit_*` tool accepts a list of rows** and returns per-row accept/reject verdicts — one bad row never bounces the batch. (A 10-entity CRUD grid must not cost 40 round trips; batching is the tool shape, not just a prompt instruction.)

| tool | behaviour |
|---|---|
| `plan_start(name)` | create plan; returns the engineer's mandate (§7) + stage-1 script |
| `plan_status()` | plan summary, stage, counts, gate states, **plus the §7 mandate and current-stage instructions** — one call fully re-arms a cold session in any CLI. Tool description worded to trigger the first call (§3) |
| `next_gap()` | see §6 |
| `get_stage_prompt(stage)` | returns any stage script on demand (rehydration, red-team session setup) |
| `submit_use_cases / submit_requirements / submit_entities / submit_crud / submit_states / submit_contracts / submit_components / submit_dependencies / submit_dep_failure_modes (…)` | insert typed rows (batched); **validate at write time** and reject with pedagogic errors — e.g. `submit_requirements` rejects a row whose slots don't satisfy its ears_type and echoes that type's slot template with an example. Every submit takes `provenance` (+ `assumption_kind` when assumed) and optional `links` |
| `record_decision(text, provenance, rationale, links, alternatives, challenge)` | decisions & assumption confirmations; upgrading `assumed→decided` requires the user's answer quoted in rationale (prompt-enforced — see §5.1); decisions the *heuristic* marks significant are rejected with empty `alternatives` (code-enforced) |
| `file_question(text, owner)` / `resolve_question(id, resolution\|defer)` | create and close open questions |
| `file_conflict(description, refs)` | model files a semantic conflict it noticed; engine-detected conflicts are filed automatically at write time |
| `register_spike(question, hypothesis, method, budget)` | must be called **before** running spike code; returns spike id + quarantine path `spikes/NNN_slug/` |
| `record_spike_result(id, verdict, evidence_summary, evidence_path)` | `verified` upgrades linked rows only if method touched the real dependency — a mocked stand-in yields `inconclusive` at best (prompt + red-team enforced, §5.1) |
| `run_gate(stage)` | evaluate; return pass/fail with the **specific holes** (row-level); **on pass, the result carries the next stage's script** — stage transitions deliver their own instructions |
| `get_plan_pack(scope)` | render a scoped slice (stage, component, or full) as markdown — used for red-team session and cold-session deep rehydration |
| `file_finding(...)` / `disposition_finding(...)` | red-team/pre-mortem bookkeeping |
| `freeze_plan()` | allowed only when all gates pass; bumps version, sets state=frozen |
| `export_plan()` | write `plan.md` (human-readable) and `plan.yaml` (structured, round-trippable bundle — the **[S3]** seam and the schema-churn escape hatch); report result. No stub generation in stage 1 (see §10) |

Error style everywhere: refusals name the rule, show the offending input, and show what compliance looks like. Rejections are teaching moments for the model.

### 5.1 Enforcement ledger

Every rule in this spec is enforced by exactly one of these mechanisms — no rule pretends to be code-enforced when it isn't:

| rule | enforced by |
|---|---|
| Write-time validation (EARS slots, contract structure, provenance fields) | **code** |
| All stage gates; freeze precondition | **code** |
| Significance ⇒ alternatives required (heuristic: links touch component/contract) | **code** |
| Batch per-row verdicts; quarantine paths; version bumps | **code** |
| `assumed→decided` requires the user's actual answer (quote in rationale) | **prompt + red-team target** |
| Spike ran against the real dependency, not a mock | **prompt + red-team target** |
| Spike budget expiry ⇒ `inconclusive` | **prompt** |
| §7 conduct clauses (proposal-first, challenge duty, self-review) | **prompt; verified by dogfood transcript evidence (§9 session D)** |

The red-team prompt (stage 7) explicitly targets the prompt-enforced rows: empty-alternatives decisions, suspicious `assumed→decided` upgrades, and mock-shaped spike methods are standing red-team targets.

## 6. `next_gap()` — the design centre

Returns the work the interview should do next. Invest the most design care here; the dogfood session will judge the whole tool by whether this makes conversation flow.

- **Priority order:** (1) open rows in `conflicts` — engine-filed (mechanically detectable only; the initial list is exactly these three, add none until dogfood demands: duplicate state×event transitions, `n/a` CRUD cells contradicted by a use-case step, resolved questions whose resolution links to a since-changed row) and model-filed (semantic; via `file_conflict`) → (2) holes in current stage (empty CRUD cells, steps without extensions or `no_extension_reason`, undefined state cells, missing dep failure modes, contracts without consumers) → (3) `assumed` + `assumption_kind=world` → spike now → (4) `assumed` + `assumption_kind=intent` → ask user → (5) open questions → (6) advance to next stage (only if current gate passes).
- **Cluster output:** return 3–5 *related* gaps per call so the model asks the user a coherent batch, not one item (prevents ping-pong/form-filling feel). **Grouping key, in order: same entity → same table → same stage.** Session A's naive version and the dogfood rewrite share this contract.
- **Context-carrying:** each gap ships with its surrounding rows (the entity, contract structure, prior decision) so a cold session needs no other warm-up.
- **Hard requirement:** `plan_status()` + `next_gap()` must fully rehydrate a brand-new session mid-plan — plan state *and* operating protocol. This is a test, not an aspiration.
- **Prefer, don't handcuff:** submits for any stage are always accepted; `next_gap` prefers stage order but follows the conversation.

## 7. The engineer's mandate — conduct clauses carried by every stage prompt

The gates in §8 define the plan's **floor** — what stops an incomplete plan. This section defines the **ceiling** — the conduct that produces the most thorough and rigorous plan the model is capable of. **Delivery:** these clauses are returned verbatim by `plan_start()` and `plan_status()` and prefixed to every stage script — never dependent on the client or the user invoking anything. **Verification:** they are prompt-layer conduct (§5.1); the dogfood session's transcript evidence (§9, session D done-when) is what verifies them, not the engine. Run planning on the strongest model available — the engine makes the floor model-independent, but interview quality scales with the brain in the chair.

1. **Role.** The user is the product owner and domain expert. **The model is the lead software engineer and owns technical rigor.** It does not transcribe answers — it engineers them: restates fuzzy answers precisely before filing them, surfaces second-order consequences, applies the canon's judgment (coupling, cohesion, error semantics, idempotency, observability) as its own review lens, and treats "the user didn't mention it" as a gap to raise, never as permission to skip.
2. **Mode.** Stages differ in who is the source of truth (see mode column, §8). *Elicit* (1–3): the user is the source; the model probes, sharpens, formalises. *Synthesize* (4–6): **the model is the source** — the user cannot answer "what are the contracts?"; the model designs the domain model, state machines, components, and contracts, presents them with rationale, and the user adjudicates. *Verify* (7–8): adversarial and mechanical checking.
3. **Proposal-first questioning.** Wherever the model can form a defensible default, it presents a **proposal with rationale and asks for objection** — never an open question. ("I propose retry-twice-then-dead-letter because the consumer is idempotent (D-14) — objections?" not "what should happen on timeout?") Blank questions are reserved for genuine intent-unknowns. This is the primary countermeasure to interview stutter; batching is secondary.
4. **Challenge duty.** When a user decision conflicts with a stored requirement, contradicts an earlier decision, or is a recognised anti-pattern, the model must raise the conflict **before** filing the row. The challenge and its outcome (`overridden`/`revised`) are recorded on the decision. The user always wins; the override is simply visible. Agreeable form-filling is the tool's defining failure mode; this clause exists to prevent it.
5. **Self-review before gate.** Before calling `run_gate(n)`, the model runs the stage's judgment checklist from its prompt (e.g. stage 3: "can an acceptance test be written from this requirement alone?"; stage 6: "would two components change together for the same reason? — merge or re-cut") and fixes what it finds. Gates verify completeness; self-review is where quality lives.

## 8. Interview stages and gates

Stage scripts live in `server/prompts/`, delivered through tool results (§5); each carries the §7 clauses, what to elicit or synthesize, how to batch, provenance discipline, spike trigger, the self-review checklist, and exit condition. **Each script also carries its methodology's coverage checklist verbatim** — stage 2 lists the Cockburn fields to elicit per use case (primary actor, trigger, preconditions, minimal guarantee, main scenario, extensions per step); stage 3 lists the five EARS templates with one example each and the Planguage triad; stage 5 lists the five failure modes — so interview quality doesn't depend on the model's recall of the canon, and a weaker model degrades gracefully to working the printed list. The model converses naturally and submits in batches — scripts must say so explicitly.

| stage | mode | elicits / synthesizes | mechanical gate |
|---|---|---|---|
| 1 Context & goals | elicit | problem, users, constraints, **non-goals**, **target stack (language/platform/runtime — recorded as decisions, this is planning data)**, context-free questions | every goal has a success criterion; non-goals non-empty; target stack recorded |
| 2 Use cases | elicit | Cockburn: numbered main scenario + extensions per step | every step has ≥1 extension or a `no_extension_reason` |
| 3 Requirements | elicit | EARS-typed behaviour via typed slots; Planguage (scale/meter/target) for NFRs | zero free-prose requirements (all slot-structured); every NFR quantified; every use case traces to ≥1 requirement |
| 4 Domain | synthesize | entities (+ lifecycle judgment), CRUD grid, state machines, input domains — model proposes, user adjudicates | CRUD grid complete; every `has_lifecycle` entity has a complete machine (no undefined cells); every `has_lifecycle=false` has a reason |
| 5 Errors & deps | synthesize | external dependencies registered; per dependency: unavailable/slow/malformed/auth/partial; concurrency, idempotency, migration, observability as linked decisions | every dependency has all 5 failure-mode rows; ≥1 dependency or explicit "no external deps" decision |
| 6 Architecture | synthesize | components, contracts to structured-signature level, dependency edges — model designs, user adjudicates | every deliverable-component has a contract; **every contract structurally complete** (params typed or explicit `none`, return, ≥1 named error or `cannot_fail` + reason); every contract has ≥1 consumer or `external`; every world-`assumed` contract → spike or user-accepted risk; **traceability:** every requirement → ≥1 contract or explicitly deferred with rationale, every contract → ≥1 requirement (untraceable contracts are invented scope) |
| 7 Adversarial | verify | fresh-session red team via `get_plan_pack(full)` + `get_stage_prompt(redteam)`; pre-mortem; §5.1's prompt-enforced rules are standing targets | every finding dispositioned |
| 8 Freeze | verify | export, round-trip check | all gates green; plan.md + plan.yaml render; plan.yaml reimports losslessly; `freeze_plan()` |

**Spike protocol** (applies in any stage): world-assumption encountered → `register_spike` (question, hypothesis, timebox) → write throwaway code in the quarantine dir (any language — whatever probes the real dependency fastest) → run against the **real** dependency → `record_spike_result`. One spike = one question. Budget expiry ⇒ `inconclusive` ⇒ escalate to user as a risk decision. Spike code never migrates to any codebase; implementations rewrite from contracts. A refuted hypothesis is a success — update the linked rows.

## 9. Build order (each session has a definition of done)

- **Session A — skeleton that talks.** `schema.sql`, `db.py` (WAL, busy_timeout), FastMCP server with `plan_start`, `plan_status` (returning mandate + stage script), `next_gap` (naive version, correct grouping key), `submit_requirements`, `submit_entities` (batched); workspace-template with AGENTS.md/CLAUDE.md. **Done when:** a toy interview in Claude Code lands correct rows in the DB, a killed-and-restarted session re-arms itself from `plan_status()` + `next_gap()` alone, and a batch with one bad row is partially accepted with a per-row verdict.
- **Session B — the full submit surface.** All remaining submit/file tools with write-time validation: EARS slots, structured contracts, dependencies + failure modes, `file_question`, `file_conflict`, `record_decision` with the significance heuristic. **Done when:** invalid submits are rejected pedagogically (rule + offending input + compliant example) and the significance heuristic blocks an empty-alternatives decision linked to a contract.
- **Session C — enforcement.** Gates for stages 1–6 (pure SQL; CRUD completeness, contract structural completeness, dep failure modes, traceability first) **with unit tests against fixture DBs — including fixtures proving each gate can fail** (a gate that passes vacuously is worse than no gate); engine-side conflict detection filing into `conflicts`; spike tools + quarantine; **minimal plan.yaml export/reimport** (dumb table dump, no plan.md rendering — pulled forward from session E so the schema-churn escape hatch exists *before* dogfood, whose churn it protects); *thin* stage scripts (§7 clauses + coverage checklist + exit condition only — session D rewrites them from contact with reality). **Done when:** `run_gate` reports row-level holes, all gate tests pass both directions, and a populated DB survives export → drop → reimport.
- **Session D — dogfood.** Plan a real small project end-to-end (candidate: LLM Manager phase 1). Expect to rewrite `next_gap` priorities and the stage scripts — that is this session's purpose, not a failure. **Done when:** interview flows (proposal-first, batched, no ping-pong), a cold session resumes mid-plan losslessly, ≥1 spike has run honestly, and the transcript shows ≥1 recorded challenge and stages 4–6 running in synthesize mode (model designing, user adjudicating — not the model asking the user for contracts). The transcript is the verification artifact for the §7 conduct clauses.
- **Session E — the wrap.** `export_plan` (plan.md, plan.yaml + lossless reimport), red-team script + `get_plan_pack`, stages 7–8 gates, `freeze_plan`. **Done when:** the dogfood plan freezes with green gates, exports cleanly, and `plan.yaml` round-trips into a fresh DB losslessly.

## 10. Explicitly out of scope for this build

Tiering (hardcode `standard`), web UI, testing on second CLIs (the design is client-neutral but only Claude Code is exercised in stage 1), **stub generation and type-checking** (structured contracts make per-language stub renderers a thin later addition — [S2] territory; a mypy gate would have silently assumed Python targets), MCP elicitation (optional client capability — must never be load-bearing; at most a later progressive enhancement), NLP over requirement prose (structure via slots instead), migration tooling beyond the plan.yaml round-trip, task-pack extraction and manifests (schema only), LLM Manager integration.

## 11. Acceptance test for stage 1 as a whole

One real project planned start to freeze, across ≥3 sessions and ≥1 deliberate mid-stage session kill, with ≥3 spikes (≥1 refuted or inconclusive), architecturally significant decisions carrying alternatives-considered, and a red-team pass that found ≥1 real issue the author session missed (a red team that finds nothing means the red-team script is broken, not that the plan is perfect) — producing a frozen DB plus exports where `plan.yaml` round-trips losslessly, and the user prefers this over freeform planning for the next project. If that last clause fails, the interview feel is the bug; fix `next_gap` and the stage scripts before adding anything.
