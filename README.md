# plantool

An LLM-led planning tool. It interviews you about a project, records every planning fact as a
typed row in SQLite with its provenance, and refuses to advance past mechanical gates. It is
reached over MCP, so the model on the other end can be any model.

**The design spine, which explains most of the decisions in here: the tool records judgment,
it never exercises it.** It has no LLM inside it and no API key. Selections are made by the
planning session; the tool does the accounting, and the accounting is what a session's memory
cannot be trusted with. Retrieval is lexical or structural for the same reason — no embedding
model, so no semantic search.

## What is here

This is **v2**, a rewrite of v1's plan-authoring loop. It was planned using v1, and that plan
is frozen at `spec/v2/plan.md` — read-only, and the specification this code is built from.

- `engine/` — the whole engine, plain Python. Storage, rows and links, the interview
  (guidance, gaps), enforcement (gates, warnings, conflicts), validation and findings, tasks
  and briefs, resume, and the surface.
- `spec/v2/` — the frozen plan, plus two ledgers kept as the build runs: `DEFECTS.md` (the
  plan was insufficient and something had to be invented) and `DEVIATIONS.md` (built
  deliberately differently, with the reasoning).
- `archive/v1/` — v1, preserved and still runnable.
- `tests/` — pytest.
- `GLOSSARY.md` — the structural vocabulary, and it is binding. `tests/test_vocabulary.py`
  parses the retired-word list out of it and fails the suite on a violating identifier.

## Running the tool

```
.venv\Scripts\python -m engine.mcp <workspace>
```

stdio JSON-RPC. Point an MCP-capable client at it, in a directory you want a plan to live in.
The tool never creates the workspace and never writes outside it. Start with `plan_status` —
in a fresh workspace it tells you to call `init_plan`, and in one that has a plan it tells a
planner with no memory where the work got to and what to do next.

## Tests

```
.venv\Scripts\python -m pytest -q
```

## Build status

Build packages M0–M6 are in: foundation, the interview core, enforcement, validation and
findings, tasks and briefs, timestamps, session resume, row naming, and the MCP surface.

**M6 is not closed.** Its open items are listed in `M6_PLAN.md` §2 — the largest is that the
vendored methodology's last package still names tools that do not exist. **M7** is
revision-service; **M8** dogfoods the whole thing by planning the GUI with it.

The execution module — deriving a task graph and composing briefs from it — is deliberately
deferred and wants a design discussion before any of it is built.
