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


class ExtensionRow(BaseModel):
    """One failure/variant of a use-case step."""
    model_config = ConfigDict(extra="allow")
    description: str | None = None
    in_scope: bool | None = None       # default true; false parks it out of scope
    handling: str | None = None        # required while in scope
    provenance: str | None = None      # omit to inherit the parent's
    assumption_kind: str | None = None
    links: list[str] | None = None


class UcStepRow(BaseModel):
    """One main-scenario step; array order in the use case is the step number."""
    model_config = ConfigDict(extra="allow")
    text: str | None = None
    no_extension_reason: str | None = None  # only when nothing can fail or vary here
    extensions: list[ExtensionRow] | None = None
    provenance: str | None = None
    assumption_kind: str | None = None
    links: list[str] | None = None


class UseCaseRow(BaseModel):
    """One Cockburn use case: title, primary actor, numbered main scenario."""
    model_config = ConfigDict(extra="allow")
    title: str | None = None
    actor: str | None = None
    steps: list[UcStepRow] | None = None
    provenance: str | None = None
    assumption_kind: str | None = None
    links: list[str] | None = None


class UcExtensionRow(ExtensionRow):
    """An extension added to an existing step (step_id from next_gap context)."""
    step_id: int | None = None


class CrudRow(BaseModel):
    """One entity x op cell: responsible actor/component, or explicit n/a + reason."""
    model_config = ConfigDict(extra="allow")
    entity_id: int | None = None
    op: str | None = None              # C | R | U | D
    actor: str | None = None
    na: bool | None = None
    na_reason: str | None = None
    children_on_delete: str | None = None  # D cells only
    provenance: str | None = None
    assumption_kind: str | None = None
    links: list[str] | None = None


class SmCell(BaseModel):
    """One state x event cell: a transition, or explicitly impossible + reason."""
    model_config = ConfigDict(extra="allow")
    state: str | None = None
    event: str | None = None
    transition_to: str | None = None
    impossible: bool | None = None
    impossible_reason: str | None = None
    provenance: str | None = None
    assumption_kind: str | None = None
    links: list[str] | None = None


class StateMachineRow(BaseModel):
    """One entity's state machine: states, events, and (optionally) initial cells."""
    model_config = ConfigDict(extra="allow")
    entity_id: int | None = None
    states: list[str] | None = None
    events: list[str] | None = None
    cells: list[SmCell] | None = None
    provenance: str | None = None
    assumption_kind: str | None = None
    links: list[str] | None = None


class StateCellRow(SmCell):
    """A cell added to an existing machine, addressed by its entity."""
    entity_id: int | None = None


class ComponentRow(BaseModel):
    """One component with its single responsibility."""
    model_config = ConfigDict(extra="allow")
    name: str | None = None
    responsibility: str | None = None
    provenance: str | None = None
    assumption_kind: str | None = None
    links: list[str] | None = None


class ContractParam(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str | None = None
    type_expr: str | None = None  # target stack's notation — recorded, never compiled
    required: bool | None = None  # default true


class ContractErrorSpec(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str | None = None
    semantics: str | None = None


class ContractRow(BaseModel):
    """One structured-signature contract on a component."""
    model_config = ConfigDict(extra="allow")
    component_id: int | None = None
    name: str | None = None
    kind: str | None = None            # api | function | schema | file | event
    params: list[ContractParam] | None = None  # [] = explicitly no params
    returns: str | None = None
    errors: list[ContractErrorSpec] | None = None
    cannot_fail: bool | None = None
    cannot_fail_reason: str | None = None
    is_external: bool | None = None    # consumed from outside the system
    provenance: str | None = None
    assumption_kind: str | None = None
    links: list[str] | None = None


class ContractDepRow(BaseModel):
    """One dependency edge: exactly one consumer (contract or component) -> provider contract."""
    model_config = ConfigDict(extra="allow")
    consumer_contract_id: int | None = None
    consumer_component_id: int | None = None
    provider_contract_id: int | None = None
    provenance: str | None = None
    assumption_kind: str | None = None
    links: list[str] | None = None


class DependencyRow(BaseModel):
    """One external dependency of the planned system."""
    model_config = ConfigDict(extra="allow")
    name: str | None = None
    kind: str | None = None            # service / library / api / filesystem / ...
    notes: str | None = None
    provenance: str | None = None
    assumption_kind: str | None = None
    links: list[str] | None = None


class DepFailureModeRow(BaseModel):
    """Handling for one dependency x failure mode."""
    model_config = ConfigDict(extra="allow")
    dep_id: int | None = None
    mode: str | None = None            # unavailable | slow | malformed | auth | partial
    handling: str | None = None
    provenance: str | None = None
    assumption_kind: str | None = None
    links: list[str] | None = None


class Alternative(BaseModel):
    model_config = ConfigDict(extra="allow")
    alternative: str | None = None
    rejected_because: str | None = None  # one line


class Challenge(BaseModel):
    model_config = ConfigDict(extra="allow")
    text: str | None = None
    outcome: str | None = None         # overridden | revised


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


def _record_impl(fn, *args, **kwargs):
    path = _db_path()
    if not path.exists():
        return NO_PLAN
    conn = db.connect(path)
    try:
        return fn(conn, *args, **kwargs)
    finally:
        conn.close()


def _submit_impl(rows: list[dict], fn) -> dict:
    result = _record_impl(fn, rows)
    if result.get("rejected"):
        result["guidance"] = (
            "Fix and resubmit only the rejected rows; the accepted ones are recorded."
        )
    return result


def submit_requirements_impl(rows: list[dict]) -> dict:
    return _submit_impl(rows, submits.submit_requirements)


def submit_entities_impl(rows: list[dict]) -> dict:
    return _submit_impl(rows, submits.submit_entities)


def submit_use_cases_impl(rows: list[dict]) -> dict:
    return _submit_impl(rows, submits.submit_use_cases)


def submit_uc_extensions_impl(rows: list[dict]) -> dict:
    return _submit_impl(rows, submits.submit_uc_extensions)


def submit_crud_impl(rows: list[dict]) -> dict:
    return _submit_impl(rows, submits.submit_crud)


def submit_states_impl(rows: list[dict]) -> dict:
    return _submit_impl(rows, submits.submit_states)


def submit_state_cells_impl(rows: list[dict]) -> dict:
    return _submit_impl(rows, submits.submit_state_cells)


def submit_components_impl(rows: list[dict]) -> dict:
    return _submit_impl(rows, submits.submit_components)


def submit_contracts_impl(rows: list[dict]) -> dict:
    return _submit_impl(rows, submits.submit_contracts)


def submit_contract_deps_impl(rows: list[dict]) -> dict:
    return _submit_impl(rows, submits.submit_contract_deps)


def submit_dependencies_impl(rows: list[dict]) -> dict:
    return _submit_impl(rows, submits.submit_dependencies)


def submit_dep_failure_modes_impl(rows: list[dict]) -> dict:
    return _submit_impl(rows, submits.submit_dep_failure_modes)


def file_question_impl(text: str, owner: str | None = None,
                       links: list[str] | None = None) -> dict:
    return _record_impl(submits.file_question, text, owner, links)


def resolve_question_impl(question_id: int, resolution: str | None = None,
                          defer: bool = False) -> dict:
    return _record_impl(submits.resolve_question, question_id, resolution, defer)


def file_conflict_impl(description: str, refs: list[str]) -> dict:
    return _record_impl(submits.file_conflict, description, refs)


def resolve_conflict_impl(conflict_id: int, resolution: str) -> dict:
    return _record_impl(submits.resolve_conflict, conflict_id, resolution)


def record_decision_impl(text: str, provenance: str, rationale: str | None = None,
                         links: list[str] | None = None,
                         alternatives: list[dict] | None = None,
                         challenge: dict | None = None,
                         assumption_kind: str | None = None) -> dict:
    return _record_impl(submits.record_decision, text, provenance, rationale=rationale,
                        links=links, alternatives=alternatives, challenge=challenge,
                        assumption_kind=assumption_kind)


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


@mcp.tool(description=(
    "Submit a batch of Cockburn use cases. Each row: title, primary actor, and steps — the "
    "numbered main scenario, array order = step number. Each step carries extensions "
    "(failure/variant + handling; in_scope=false parks one out of scope) or a "
    "no_extension_reason asserting nothing can fail there — never both. Add extensions to "
    "existing steps later with submit_uc_extensions. Per-row verdicts; a bad step or extension "
    "rejects only its own use case. Children inherit the row's provenance unless they carry "
    "their own."
))
def submit_use_cases(rows: list[UseCaseRow]) -> dict:
    return submit_use_cases_impl([r.model_dump() for r in rows])


@mcp.tool(description=(
    "Add extension rows (failure/variant + handling) to existing use-case steps by step_id — "
    "the gap-filling companion to submit_use_cases. Rejected if the step carries a "
    "no_extension_reason (file_conflict instead if that reason is now wrong). Per-row verdicts; "
    "every row carries provenance (+ assumption_kind when assumed)."
))
def submit_uc_extensions(rows: list[UcExtensionRow]) -> dict:
    return submit_uc_extensions_impl([r.model_dump() for r in rows])


@mcp.tool(description=(
    "Submit CRUD-grid cells: one row per entity_id x op (C|R|U|D), naming the responsible "
    "actor/component — or na=true + na_reason when the operation genuinely never happens. "
    "Note children_on_delete on D cells. The stage-4 gate needs all four ops per entity. "
    "Per-row verdicts; provenance on every row."
))
def submit_crud(rows: list[CrudRow]) -> dict:
    return submit_crud_impl([r.model_dump() for r in rows])


@mcp.tool(description=(
    "Submit state machines for lifecycle entities: entity_id, states, events, and optionally "
    "the first cells. Every state x event cell must eventually be a transition_to or an "
    "explicit impossible + reason (the stage-4 gate checks completeness); add remaining cells "
    "with submit_state_cells. One machine per entity. Per-row verdicts; provenance on every "
    "row, cells inherit it unless they carry their own."
))
def submit_states(rows: list[StateMachineRow]) -> dict:
    return submit_states_impl([r.model_dump() for r in rows])


@mcp.tool(description=(
    "Add cells to an entity's existing state machine (address by entity_id). Each cell is a "
    "transition_to one of the machine's states, or explicitly impossible + reason. Per-row "
    "verdicts; provenance on every row."
))
def submit_state_cells(rows: list[StateCellRow]) -> dict:
    return submit_state_cells_impl([r.model_dump() for r in rows])


@mcp.tool(description=(
    "Submit components — each with a name and its single responsibility (one sentence; if you "
    "cannot state it, re-cut the component). Synthesize mode: you design, the user adjudicates. "
    "Per-row verdicts; provenance on every row."
))
def submit_components(rows: list[ComponentRow]) -> dict:
    return submit_components_impl([r.model_dump() for r in rows])


@mcp.tool(description=(
    "Submit structured-signature contracts on components: name, kind "
    "(api|function|schema|file|event), params (array of {name, type_expr, required} — [] means "
    "explicitly none; type_exprs in the target stack's notation), returns, and >=1 named error "
    "with semantics or cannot_fail=true + reason. Mark is_external=true when consumed from "
    "outside the system. Record consumer edges with submit_contract_deps. Per-row verdicts; "
    "provenance on every row."
))
def submit_contracts(rows: list[ContractRow]) -> dict:
    return submit_contracts_impl([r.model_dump() for r in rows])


@mcp.tool(description=(
    "Record dependency edges between contracts: exactly one consumer (consumer_contract_id or "
    "consumer_component_id) -> provider_contract_id. The stage-6 gate requires every "
    "non-external contract to have a consumer. Per-row verdicts; provenance on every row."
))
def submit_contract_deps(rows: list[ContractDepRow]) -> dict:
    return submit_contract_deps_impl([r.model_dump() for r in rows])


@mcp.tool(description=(
    "Register external dependencies of the planned system: name, kind (service, library, api, "
    "filesystem, ...), notes. Each then needs all five failure-mode rows via "
    "submit_dep_failure_modes (stage-5 gate). Per-row verdicts; provenance on every row."
))
def submit_dependencies(rows: list[DependencyRow]) -> dict:
    return submit_dependencies_impl([r.model_dump() for r in rows])


@mcp.tool(description=(
    "Submit failure-mode handling per dependency: one row per dep_id x mode "
    "(unavailable|slow|malformed|auth|partial) with the handling. The stage-5 gate requires "
    "all five modes per dependency. Per-row verdicts; provenance on every row."
))
def submit_dep_failure_modes(rows: list[DepFailureModeRow]) -> dict:
    return submit_dep_failure_modes_impl([r.model_dump() for r in rows])


@mcp.tool(description=(
    "File an open question that cannot be answered right now (text, owner, optional links to "
    "related rows as \"table:id\"). Open questions surface through next_gap() until resolved "
    "with resolve_question."
))
def file_question(text: str, owner: str | None = None, links: list[str] | None = None) -> dict:
    return file_question_impl(text, owner, links)


@mcp.tool(description=(
    "Close an open question: record its resolution, or pass defer=true to park it deliberately "
    "(deferred questions can still be resolved later)."
))
def resolve_question(question_id: int, resolution: str | None = None,
                     defer: bool = False) -> dict:
    return resolve_question_impl(question_id, resolution, defer)


@mcp.tool(description=(
    "File a semantic conflict you noticed between recorded rows (description + refs "
    "\"table:id\" of the disagreeing rows). Engine-detected conflicts are filed automatically; "
    "this is for the ones only you can see. Conflicts sit at next_gap() priority 1 until "
    "resolved with the user via resolve_conflict."
))
def file_conflict(description: str, refs: list[str]) -> dict:
    return file_conflict_impl(description, refs)


@mcp.tool(description=(
    "Resolve an open conflict, recording the user's adjudication (or the correcting rows) as "
    "the resolution."
))
def resolve_conflict(conflict_id: int, resolution: str) -> dict:
    return resolve_conflict_impl(conflict_id, resolution)


@mcp.tool(description=(
    "Record a decision (ADR-shaped) or an assumption confirmation. Upgrading assumed->decided "
    "requires the user's actual answer quoted in rationale. links are row refs (\"table:id\") "
    "to what the decision touches. Significance is set by a code heuristic, never by you: "
    "links touching a component or contract make the decision significant, and significant "
    "decisions are rejected without alternatives (each with a one-line rejected_because). "
    "If you challenged the user's call, record it as challenge {text, outcome: "
    "overridden|revised}."
))
def record_decision(text: str, provenance: str, rationale: str | None = None,
                    links: list[str] | None = None,
                    alternatives: list[Alternative] | None = None,
                    challenge: Challenge | None = None,
                    assumption_kind: str | None = None) -> dict:
    return record_decision_impl(
        text, provenance, rationale=rationale, links=links,
        alternatives=[a.model_dump() for a in alternatives] if alternatives else None,
        challenge=challenge.model_dump() if challenge else None,
        assumption_kind=assumption_kind)


if __name__ == "__main__":
    mcp.run()
