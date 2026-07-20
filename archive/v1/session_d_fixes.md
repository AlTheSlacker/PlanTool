# Session D harvest — prototype 1 fix plan

> **Status (2026-07-16): W1–W8 executed and committed.** Confirmed with Al:
> supersede-with-lineage over in-place amend (W1); reject forward refs (W2).
> One factual correction: **F6 is wrong** — `gate_results.holes` has existed since
> Session C and the dogfood DB's stage-6 failure holes ARE persisted (verified
> read-only against `LLM_Manager_Plan/plan.db`); W4 became a regression test instead
> of a schema change. Everything else landed as written: `supersede_row` /
> `retire_row` / `confirm_assumption` with bidirectional lineage and active-row
> semantics throughout (gates, sweeps, next_gap, duplicate checks, partial unique
> indexes), dangling/inactive-ref rejection on every batch surface incl. nested
> children, `plan_status` digest + `get_rows`, `dismiss_gap`, mandate + stage-script
> conduct rewrites, db-wrapper seam. 156 tests green. Next: Session E.

*2026-07-16. Source: dogfood run planning "LLM Manager — planning tool for LLM CLI code engines"
(workspace `D:\PythonProjects\LLM_Manager_Plan`, plan.db parked at stage 7, 1 plan / 57 decisions /
66 requirements / 51 contracts; gates 1–6 passed, one honest stage-6 fail). Findings come from the
plan's own "observed prototype friction" decisions (d28, d36, d49, d57) plus DB forensics done in
the PlanTool session. This file is the work order for the next build session(s); Session E
(red-team script, get_plan_pack, stages 7–8 gates, export_plan, freeze_plan) follows it.*

## Findings (evidence first)

- **F1 — No amend/supersede path.** (d28, d57) An `assumed` decision cannot be upgraded to
  `decided` in place — three `record_decision` retries left duplicates (decisions 25–27) while
  `next_gap` kept re-surfacing the original. The stage-6 gate said "link it or cut it" when no tool
  can do either. This was the known B/C judgment call ("wrong rows need conflict adjudication");
  dogfood proved it wrong.
- **F2 — Cold resume is lossless but expensive.** (d49) `plan_status` serves counts, not content,
  and there is no targeted row-read API; a post-/clear resume cost 4k+ tokens including a full DB
  dump to a text file.
- **F3 — The interview under-challenges and under-records.** (d36 + column forensics) 0/57
  decisions carry a `challenge`; 0 are marked `significant` (16 do carry alternatives);
  `file_question` was never called once (0 rows ever); the agent authored all use cases and the
  owner "did not feel pushed". The mechanisms exist; nothing in the stage scripts makes the
  interviewer use them.
- **F4 — `next_gap` nags answered items.** (d28a) With no upgrade path, an already-answered
  `assumed` decision kept re-surfacing, forcing the duplicate rows of F1.
- **F5 — Batch submits skip dangling-ref checking.** Contracts 3/4/8/51 (created 14:59:43–45)
  reference requirements 63–66 (created 15:02:41). `_dangling_refs_error` is wired into the
  single-row tools only (`engine/submits.py:1194,1249,1297`); `_submit_batch` envelope validation
  format-checks links but never resolves them. This accidental forward-ref hole was the only
  reason the stage-6 gate failure was fixable — so it must be closed **together with** F1, not
  before it.
- **F6 — `gate_results` stores pass/fail only.** The stage-6 failure's row-level holes lived only
  in the conversation; the table has no details column, so the audit trail loses the reasons.
- **F7 — DB access audit ("move to the db wrapper" — Al).** Only `engine/db.py:28` calls
  `sqlite3.connect`, but `conflicts/gaps/gates/render/spikes/submits` all `import sqlite3`
  directly (Row/exception types, possibly ad-hoc pragmas). Consolidate every DB touchpoint behind
  `engine/db.py` so WAL/busy_timeout/foreign-keys behavior is uniform; keep it a thin seam — the
  dogfood plan's backend-neutral storage interface (its d48) is the eventual shape, do not build
  that abstraction now.

## Work items (in order)

- **W1 — Supersede/amend path** *(schema-touching; do first — everything else leans on it)*.
  Adopt the dogfood plan's own answer (its d42): supersede-with-lineage, not in-place mutation.
  `supersede_row(table, id, replacement_fields, reason)` creates the successor row carrying a
  `supersedes` pointer; original gains `superseded_by` (bidirectional, machine-checkable). Plus
  the one cheap special case: provenance upgrade (`assumed` → `decided`/`verified` with evidence)
  as an explicit tool or supersede shorthand, since it was the actual blocker.
  Gates, conflict sweeps, `next_gap`, and export must treat superseded rows as inactive;
  plan.yaml round-trip must carry lineage losslessly. Rewrite gate fix-instruction texts so every
  remedy they name is a tool that exists.
  *Open design point for Al: confirm supersede-with-lineage over in-place amend (recommended:
  supersede — it matches immutability + provenance philosophy and the dogfood plan chose it).*
- **W2 — Close the dangling-ref hole** *(immediately after W1)*. Run `_dangling_refs_error` on
  every links field in `_submit_batch`. Decide forward-ref policy explicitly: reject (recommended,
  now that W1 provides the sanctioned remedy) and say so in the pedagogic error text.
- **W3 — `plan_status` digest + targeted reads.** Digest: stage, last gate result per stage
  (incl. holes once W4 lands), row counts, open conflicts/questions, and a working set (active
  gaps + most recent rows). New `get_rows(table, ids | simple filter)` selector tool for
  everything else. Acceptance: a cold resume rebuilds context in well under ~1k tokens with no
  full-DB dump.
- **W4 — `gate_results.details`.** Persist the row-level holes JSON with each run.
- **W5 — Stage-script rewrites (the conduct fixes).** Mandatory divergence rounds *before* the
  agent shows drafts (context-free questions, negative-space probes, owner-generated candidates —
  d36's own countermeasure list); explicit instructions to record challenges in the `challenge`
  field, set `significant` where the heuristic warrants, and `file_question` BEFORE asking the
  user anything (so a kill can never lose an open question); name the W1 tools as the remedy for
  wrong rows.
- **W6 — `next_gap` respects resolution.** Stop re-surfacing rows that were superseded or
  provenance-upgraded; consider a lightweight gap dismiss/acknowledge (the dogfood plan's
  gap-engine has dismiss/re-arm — steal the shape, defer anything heavier).
- **W7 — DB wrapper audit (F7).** Mechanical pass: all connections/pragmas/Row factories via
  `engine/db.py`; no behavior change intended.
- **W8 — Tests.** Every new gate/validation behavior proven in both directions (fail AND pass);
  supersession survives export → drop → reimport; a fixture reproducing the F5 timeline (dangling
  batch refs) now rejected with the pedagogic error.

## Then Session E (unchanged scope)

Red-team script + `get_plan_pack`, stages 7–8 gates, `export_plan` (plan.md + plan.yaml),
`freeze_plan`. After it ships: reopen the LLM_Manager_Plan workspace, run the red team, execute
the SMB spike for real (registered as spike 1, verdict null), freeze. §11 acceptance needs ≥3
spikes (≥1 refuted/inconclusive) before freeze.

## Strategy context (settled with Al, 2026-07-16)

Prototype 2 is not a fork: the dogfood plan's brief-composer/task-graph IS roadmap stage 2. Order:
this fix list → Session E → red-team + freeze the dogfood plan → build "prototype 2" by executing
the frozen plan from its own briefs (which is simultaneously the stage-2 dogfood). The dogfood DB
is a load-bearing artifact — do not touch the workspace until Session E ships.
