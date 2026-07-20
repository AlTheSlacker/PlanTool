This is a plantool planning workspace, not a codebase.
Call the plantool MCP tool `plan_status()` first, before responding to the user, then `next_gap()`.
Follow the instructions returned by the tools — they carry your role and the interview script.
Spike code goes only in `spikes/` (quarantine); it never ships anywhere.
The plantool MCP server is a black box: never read, explore, or debug its implementation (the directory named in `.mcp.json`). If a tool call errors, report the error text to the user verbatim and stop — do not open the server source.
Plan only from what the user tells you and what you verify by spike. Do not use the planning tools themselves as a design reference for the project being planned.

<!-- Preserved 2026-07-20 from the LLM_Manager_Plan dogfood workspace before it was deleted.
The last two rules above were added during the dogfood and never made it back into
AGENTS.md in this template. v2's workspace bootstrap should carry both. -->
