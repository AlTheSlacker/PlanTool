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
Session A of 5 (spec §9): schema v1, `plan_start` / `plan_status` / `next_gap` (naive) /
`submit_requirements` / `submit_entities`. Remaining submit surface, gates, spikes, export,
and the dogfood rewrite come in sessions B–E.
