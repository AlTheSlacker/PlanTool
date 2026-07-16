# plantool

LLM-led project-planning tool: an MCP server whose tools interview the user, record every
planning fact as a typed row in SQLite, and refuse to advance past mechanical gates.
Spec: `plantool_stage1_spec.md` (rev 2 — source of truth).

## Layout
- `engine/` — plain Python, no LLM calls: schema, DB wrapper, validation, `next_gap()` walker.
- `server/` — FastMCP stdio server + interview scripts (delivered inside tool results).
- `workspace-template/` — copy this directory to start planning a project.
- `tests/` — pytest suite (fixture DBs).

## Setup
```
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install mcp pyyaml pytest
```

## Use
Copy `workspace-template/` to a new folder, open your MCP-capable CLI (Claude Code first)
there, and talk. The `.mcp.json` launches the server over stdio; `plan_status()` bootstraps
the model.

## Tests
```
.venv\Scripts\python -m pytest
```

## Build status
Sessions A–D of 5 (spec §9) are in:
- **A** — schema v1, `plan_start` / `plan_status` / `next_gap`, first submit tools.
- **B** — the full submit surface (use cases, CRUD, state machines, components, contracts,
  dependencies, failure modes, decisions, questions, conflicts).
- **C** — enforcement: gates 1–6, spikes, engine conflict sweeps, plan.yaml export/reimport.
- **D** — the dogfood harvest: supersede/retire/confirm correction path with lineage
  (claim rows are never mutated or duplicated), dangling-ref checking on every batch
  submit, `plan_status` digest + `get_rows` targeted reads, `dismiss_gap`, and the
  interview-conduct rewrites (divergence rounds, recorded challenges, file-question-first).

Session E (red-team script, `get_plan_pack`, stages 7–8 gates, `export_plan`,
`freeze_plan`) closes stage 1.
