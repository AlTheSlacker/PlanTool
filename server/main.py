"""plantool MCP server — stdio transport, official python SDK (FastMCP).

Everything the model needs (role, stage scripts, gap context) arrives as
tool results; MCP prompts/resources/elicitation are never load-bearing
(spec design principle 6). The workspace is the server's cwd (Claude Code
launches stdio servers in the project dir); PLANTOOL_WORKSPACE overrides
for tests.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import BaseModel, ConfigDict
from mcp.server.fastmcp import FastMCP

from engine import db, gaps, submits

PROMPTS_DIR = Path(__file__).parent / "prompts"
DB_FILENAME = "plan.db"

mcp = FastMCP("plantool")


def _workspace() -> Path:
    return Path(os.environ.get("PLANTOOL_WORKSPACE") or Path.cwd())


def _db_path() -> Path:
    return _workspace() / DB_FILENAME


def _mandate() -> str:
    return (PROMPTS_DIR / "mandate.md").read_text(encoding="utf-8")


def _stage_script(stage: int) -> str:
    matches = sorted(PROMPTS_DIR.glob(f"stage{stage}_*.md"))
    if matches:
        return matches[0].read_text(encoding="utf-8")
    return (
        f"(Stage {stage} script is not written yet — it arrives in a later build session. "
        "Apply the engineer's mandate: elicit stages 1-3 with the user as source of truth, "
        "synthesize stages 4-6 with you as designer and the user adjudicating, verify 7-8. "
        "Batch your submits; record provenance on every row.)"
    )


NO_PLAN = {
    "status": "no_plan",
    "instruction": (
        "No plan exists in this workspace yet. Ask the user what they want to plan, "
        "then call plan_start(name)."
    ),
}


class RequirementRow(BaseModel):
    """One EARS-typed requirement. Engine validates per-row; unknown fields are
    passed through so the engine can reject them pedagogically."""
    model_config = ConfigDict(extra="allow")
    ears_type: str | None = None       # ubiquitous | event | state | unwanted | optional
    trigger: str | None = None         # event/unwanted slot
    precondition: str | None = None    # state slot
    feature: str | None = None         # optional slot
    system_response: str | None = None # required for every type
    is_nfr: bool | None = None
    planguage_scale: str | None = None
    planguage_meter: str | None = None
    planguage_target: str | None = None
    provenance: str | None = None      # decided | derived | assumed
    assumption_kind: str | None = None # world | intent (assumed rows only)
    links: list[str] | None = None     # row refs like "use_cases:3"


class EntityRow(BaseModel):
    """One domain entity with a lifecycle judgment."""
    model_config = ConfigDict(extra="allow")
    name: str | None = None
    description: str | None = None
    has_lifecycle: bool | None = None
    lifecycle_reason: str | None = None  # required when has_lifecycle is false
    provenance: str | None = None
    assumption_kind: str | None = None
    links: list[str] | None = None


def plan_start_impl(name: str) -> dict:
    path = _db_path()
    if path.exists():
        conn = db.connect(path)
        try:
            plan = db.get_plan(conn)
        finally:
            conn.close()
        if plan is not None:
            return {
                "error": (
                    f"A plan already exists in this workspace: '{plan['name']}' "
                    f"(stage {plan['current_stage']}). Call plan_status() to resume it."
                )
            }
    conn = db.create_plan_db(path, name)
    try:
        plan = db.get_plan(conn)
        return {
            "status": "created",
            "plan_id": plan["id"],
            "name": plan["name"],
            "current_stage": 1,
            "mandate": _mandate(),
            "stage_script": _stage_script(1),
            "next": "Open the stage-1 interview with the user, then call next_gap() between batches.",
        }
    finally:
        conn.close()


def plan_status_impl() -> dict:
    path = _db_path()
    if not path.exists():
        return {**NO_PLAN, "mandate": _mandate()}
    conn = db.connect(path)
    try:
        plan = db.get_plan(conn)
        if plan is None:
            return {**NO_PLAN, "mandate": _mandate()}
        gates = [dict(r) for r in conn.execute(
            """SELECT stage, passed, holes, max(run_at) AS run_at
               FROM gate_results GROUP BY stage ORDER BY stage""")]
        return {
            "status": "ok",
            "plan": dict(plan),
            "counts": db.table_counts(conn),
            "gates": gates,
            "mandate": _mandate(),
            "stage_script": _stage_script(plan["current_stage"]),
            "next": "Call next_gap() for the next 3-5 related gaps to work with the user.",
        }
    finally:
        conn.close()


def next_gap_impl() -> dict:
    path = _db_path()
    if not path.exists():
        return NO_PLAN
    conn = db.connect(path)
    try:
        return gaps.next_gap(conn)
    finally:
        conn.close()


def _submit_impl(rows: list[dict], fn) -> dict:
    path = _db_path()
    if not path.exists():
        return NO_PLAN
    conn = db.connect(path)
    try:
        result = fn(conn, rows)
        if result["rejected"]:
            result["guidance"] = (
                "Fix and resubmit only the rejected rows; the accepted ones are recorded."
            )
        return result
    finally:
        conn.close()


def submit_requirements_impl(rows: list[dict]) -> dict:
    return _submit_impl(rows, submits.submit_requirements)


def submit_entities_impl(rows: list[dict]) -> dict:
    return _submit_impl(rows, submits.submit_entities)


@mcp.tool(description=(
    "Planning workspace status. Call this first in any session in this workspace, before "
    "responding to the user. Returns the plan summary, current stage, row counts, gate states, "
    "the engineer's mandate, and the current stage's interview script — everything needed to "
    "resume planning cold."
))
def plan_status() -> dict:
    return plan_status_impl()


@mcp.tool(description=(
    "Create a new plan in this workspace (one plan per workspace). Returns the engineer's "
    "mandate and the stage-1 interview script. Fails if a plan already exists — resume with "
    "plan_status() instead."
))
def plan_start(name: str) -> dict:
    return plan_start_impl(name)


@mcp.tool(description=(
    "The next 3-5 related gaps the planning interview should address, in priority order "
    "(open conflicts > current-stage holes > world-assumptions to spike > intent-assumptions "
    "to confirm with the user > open questions > stage advance), each with surrounding rows "
    "as context. Call after plan_status() and again between interview batches."
))
def next_gap() -> dict:
    return next_gap_impl()


@mcp.tool(description=(
    "Submit a batch of EARS-typed requirement rows. Each row is validated independently and "
    "gets its own accept/reject verdict — one bad row never bounces the batch. Slots by "
    "ears_type: ubiquitous(system_response), event(trigger+system_response), "
    "state(precondition+system_response), unwanted(trigger+system_response), "
    "optional(feature+system_response). NFRs (is_nfr=true) also need "
    "planguage_scale/meter/target. Every row carries provenance (decided|derived|assumed; "
    "assumed rows also carry assumption_kind world|intent) and optional links."
))
def submit_requirements(rows: list[RequirementRow]) -> dict:
    return submit_requirements_impl([r.model_dump() for r in rows])


@mcp.tool(description=(
    "Submit a batch of domain-entity rows (name, description, has_lifecycle judgment). "
    "has_lifecycle=false requires lifecycle_reason; true means a state machine is required "
    "later. Per-row verdicts — one bad row never bounces the batch. Every row carries "
    "provenance (+ assumption_kind when assumed) and optional links."
))
def submit_entities(rows: list[EntityRow]) -> dict:
    return submit_entities_impl([r.model_dump() for r in rows])


if __name__ == "__main__":
    mcp.run()
