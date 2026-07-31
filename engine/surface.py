"""mcp-surface (`components:15`) — the only externally visible part of the tool.

Contracts: `contracts:50` dispatch, `contracts:51` append_log.

An engine-agnostic MCP stdio toolset wrapping every service contract, with per-call
validation, pedagogical errors, and an append-only observability log. Strictly
protocol-clean: no engine-specific calls and no engine-specific configuration
(`decisions:4`, `requirements:74`), so any model on the other end sees the same tools.

**Why a registry and not a pile of functions.** The component's stated responsibility —
wrapping *every* service contract — is an accounting claim, and an accounting claim needs a
denominator that is defined somewhere other than the thing being measured. The frozen plan
declares its own: 39 contracts carry `consumed by: components:15`. `tests/test_surface.py`
parses them out of `spec/v2/plan.md` and compares against `REGISTRY`, so "we wrapped
everything" is a test rather than a sentence in a docstring. A hand-kept list inside this
module would report success the first time somebody added a contract and forgot.

Four of those 39 are `EXCLUDED` here, each carrying its reason, rather than quietly absent:
a permanent false shortfall is a gap everyone learns to ignore, and a real omission
eventually hides inside it. Three are the writer lock, deleted with the mechanism it
guarded (D5); the fourth is the split, deleted with the level it divided (v3 change 1). The
five revision-service contracts were `DEFERRED` until M7 and are now built and exposed, so
`DEFERRED` is empty. `EXCLUDED` is what the coverage test subtracts, so nothing is
unaccounted for and nothing is silently missing.

**Six tools are here that the frozen plan does not send here** — the mandate, the stage
script, the active warnings, the journal, the gate history and `compose_brief` (DEVIATIONS
D18). They are exposed because `plan_status` tells a resuming planner to call them. The
alternative was to reword the digest so it only names what happens to be exposed, which
would let the specification's internal bookkeeping decide what a planner is allowed to
know. The door (`engine/door.py`) now makes the two lists agree mechanically: any call
named in outgoing text must resolve here, or the call fails.

The same shape recurred once at the build-grouping level and cost more: three tools of ours
went unexposed while finalization refused a plan whose tasks were in no group, so an
invariant that was enforceable and not satisfiable stopped every plan authored through this
surface (DEFECTS.md F39). That level is gone (v3 change 1) and those three tools with it,
but the question it leaves is permanent, and it is worth asking of every guard: **which
exposed call satisfies this invariant?** Every tool with no contract behind it appears in
`ADDED` with the reason it exists.

The glossary is the third such group (D23) and the plan has nothing to say about it at all —
it never asks what the words mean (DEFECTS.md F40). `plan_status` names `glossary()` even
when the plan has no terms yet, because a line that appears only once there are terms can
never be the line that produces the first one.

**`NotWriter` is moot, not implemented.** `contracts:50` declares it for "a write tool
invoked without holding the writer lease"; there is no lease, the lock having been removed
entirely (D5). An outcome whose precondition cannot arise is not an error to raise — it is a
line to strike, and striking it is recorded rather than assumed.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from engine.attachments import AttachmentService
from engine.briefs import BriefComposer, BriefSelection
from engine.clock import now
from engine.conflicts import ConflictService
from engine.door import (
    Resolution,
    collect,
    display,
    render,
    resolver_from,
    scan,
    successor_lookup,
)
from engine.errors import PlanToolError
from engine.findings import FindingService
from engine.gaps import GapEngine
from engine.gates import GateEngine
from engine.graph import LinkGraph
from engine.guidance import Guidance
from engine.models import (
    ChangeRequest,
    Disposition,
    LinkSpec,
    OwnerDecision,
    Provenance,
    RowRef,
    RowSelector,
    RowSubmission,
)
from engine.behaviours import BehaviourService
from engine.render import PlanRender
from engine.resume import ResumeService
from engine.revision import RevisionService
from engine.rows import RowService
from engine.storage import Storage
from engine.tasks import TaskGraphService
from engine.terms import TermService
from engine.validation import SpikeSpec, ValidationService
from engine.warnings import WarningService

LOG_FILENAME = "toolcalls.log"

#: The door's display form as an *input*: `name (table:ordinal)`. It reads the address out
#: of what this surface printed, so what goes out can come back. Anchored at the end,
#: because the name in front of it is prose and may hold brackets of its own.
DISPLAYED = re.compile(r"\(([a-z][a-z0-9_]*:[1-9][0-9]*)\)\s*$")

#: `dep_failure_modes:11`-`15` — the failure-mode vocabulary `contracts:51` labels each
#: logged event with. `ok` is not one of them: a successful call is not a failure mode, and
#: giving success a slot in the same field is how a count of failures quietly becomes a
#: count of calls.
FAILURE_MODES = ("unavailable", "slow", "malformed", "auth", "partial")


class UnknownTool(PlanToolError):
    """contracts:50 — names the unknown tool and lists the valid ones."""


class MalformedCall(PlanToolError):
    """contracts:50 — pedagogical rejection naming the specific problem; nothing is filed
    (`dep_failure_modes:13`, `requirements:14`)."""


class LogWriteError(PlanToolError):
    """contracts:51 — the log is unwritable. Fails fast and surfaces: operations are never
    silently unlogged (`decisions:46`)."""


# --- argument decoding -------------------------------------------------------------
#
# JSON gives us strings, numbers, lists and dicts. The service contracts want RowRefs,
# RowSubmissions, selectors and specs. Each decoder below turns one into the other and
# raises MalformedCall naming the field — `requirements:14`'s pedagogical rejection is the
# whole point of having a validation layer here rather than letting a TypeError out.


def _fail(field_name: str, want: str, got: Any) -> MalformedCall:
    return MalformedCall(
        f"{field_name} must be {want}", field=field_name, got=repr(got)[:120]
    )


def as_str(field_name: str, value: Any) -> str:
    if not isinstance(value, str):
        raise _fail(field_name, "a string", value)
    return value


def as_int(field_name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _fail(field_name, "a whole number", value)
    return value


def as_bool(field_name: str, value: Any) -> bool:
    if not isinstance(value, bool):
        raise _fail(field_name, "true or false", value)
    return value


def as_ref(field_name: str, value: Any) -> RowRef:
    """An address, in either form the caller could have got it in.

    `requirements:61` is the storage form. `the plan is living (requirements:61)` is the
    **display** form, and it is the only form this surface ever prints: D19 forbids an
    address from travelling without the name of what it addresses. So a caller who reads a
    ref out of one payload and passes it to the next tool is handing back exactly what we
    printed — and refusing it is the round-trip the door broke once already, when
    annotation changed a gap key's shape. Whatever the tool emits, the tool accepts.
    """
    if isinstance(value, str):
        match = DISPLAYED.search(value)
        try:
            return RowRef.parse(match.group(1) if match else value)
        except ValueError as exc:
            raise _fail(field_name, str(exc), value) from exc
    raise _fail(field_name, "an address like 'requirements:61'", value)


def as_refs(field_name: str, value: Any) -> list[RowRef]:
    if not isinstance(value, list):
        raise _fail(field_name, "a list of addresses", value)
    return [as_ref(f"{field_name}[{i}]", v) for i, v in enumerate(value)]


def as_ints(field_name: str, value: Any) -> list[int]:
    if not isinstance(value, list):
        raise _fail(field_name, "a list of whole numbers", value)
    return [as_int(f"{field_name}[{i}]", v) for i, v in enumerate(value)]


def as_dict(field_name: str, value: Any) -> dict:
    if not isinstance(value, dict):
        raise _fail(field_name, "an object", value)
    return value


def as_text_map(field_name: str, value: Any) -> dict[str, str]:
    got = as_dict(field_name, value)
    return {
        as_str(f"{field_name} key", k): as_str(f"{field_name}[{k}]", v)
        for k, v in got.items()
    }


def as_submission(field_name: str, value: Any) -> RowSubmission:
    """One row offered for filing.

    `name` has no default anywhere in the engine and gets none here (M6_PLAN.md §6): a
    surface that invented a name would put the guess back exactly where the design took it
    out.
    """
    got = as_dict(field_name, value)
    unknown = set(got) - {
        "table", "content", "name", "provenance", "assumption_kind", "links", "stage",
        "spike", "grounds", "alternatives",
    }
    if unknown:
        raise _fail(field_name, f"a row; it has no field {sorted(unknown)[0]!r}", value)
    for required in ("table", "content", "name"):
        if required not in got:
            raise _fail(field_name, f"a row with a {required}", value)
    provenance = got.get("provenance", "decided")
    try:
        prov = Provenance(as_str(f"{field_name}.provenance", provenance))
    except ValueError as exc:
        raise _fail(
            f"{field_name}.provenance",
            "one of " + ", ".join(p.value for p in Provenance),
            provenance,
        ) from exc
    return RowSubmission(
        table=as_str(f"{field_name}.table", got["table"]),
        content=as_dict(f"{field_name}.content", got["content"]),
        name=as_str(f"{field_name}.name", got["name"]),
        provenance=prov,
        assumption_kind=got.get("assumption_kind"),
        links=[
            _as_link(f"{field_name}.links[{i}]", link)
            for i, link in enumerate(got.get("links") or [])
        ],
        stage=got.get("stage"),
        # D16 — a world-assumption is filed with the spike that will attack it; row-service
        # requires it there and refuses it anywhere else, so the decoder just carries it.
        spike=(
            as_spike_spec(f"{field_name}.spike", got["spike"])
            if got.get("spike") is not None
            else None
        ),
        # v3 D11, and this parser is the whole of the client-facing route to them: a row
        # filed through the surface without these keys can never carry its argument, and
        # every live row stays a gap forever. One decoder serves both `rows` (submit_rows)
        # and `row` (a supersede replacement), so the two cannot diverge.
        grounds=(
            as_str(f"{field_name}.grounds", got["grounds"])
            if got.get("grounds") is not None
            else None
        ),
        alternatives=(
            as_str(f"{field_name}.alternatives", got["alternatives"])
            if got.get("alternatives") is not None
            else None
        ),
    )


def _as_link(field_name: str, value: Any) -> LinkSpec:
    got = as_dict(field_name, value)
    target = got.get("target")
    if isinstance(target, int) and not isinstance(target, bool):
        resolved: RowRef | int = target
    else:
        resolved = as_ref(f"{field_name}.target", target)
    return LinkSpec(target=resolved, edge_type=got.get("edge_type", "links"))


def as_submissions(field_name: str, value: Any) -> list[RowSubmission]:
    if not isinstance(value, list):
        raise _fail(field_name, "a list of rows", value)
    return [as_submission(f"{field_name}[{i}]", v) for i, v in enumerate(value)]


def as_selector(field_name: str, value: Any) -> RowSelector:
    got = as_dict(field_name, value)
    unknown = set(got) - {
        "ids", "table", "stage", "provenance", "live_only", "neighbourhood_of",
        "limit", "offset",
    }
    if unknown:
        raise _fail(
            field_name, f"a selector; it has no field {sorted(unknown)[0]!r}", value
        )
    provenance = got.get("provenance")
    return RowSelector(
        ids=as_refs(f"{field_name}.ids", got["ids"]) if got.get("ids") else None,
        table=got.get("table"),
        stage=got.get("stage"),
        provenance=Provenance(provenance) if provenance else None,
        live_only=bool(got.get("live_only", False)),
        neighbourhood_of=(
            as_ref(f"{field_name}.neighbourhood_of", got["neighbourhood_of"])
            if got.get("neighbourhood_of")
            else None
        ),
        limit=got.get("limit", 100),
        offset=got.get("offset", 0),
    )


def as_spike_spec(field_name: str, value: Any) -> SpikeSpec:
    got = as_dict(field_name, value)
    for required in ("question", "hypothesis", "method", "budget"):
        if not got.get(required):
            raise _fail(field_name, f"a spike with a {required}", value)
    return SpikeSpec(
        question=as_str(f"{field_name}.question", got["question"]),
        hypothesis=as_str(f"{field_name}.hypothesis", got["hypothesis"]),
        method=as_str(f"{field_name}.method", got["method"]),
        budget=as_str(f"{field_name}.budget", got["budget"]),
    )


def as_selection(field_name: str, value: Any) -> BriefSelection:
    got = as_dict(field_name, value)
    included = got.get("included") or []
    if not isinstance(included, list):
        raise _fail(f"{field_name}.included", "a list of addresses", included)
    return BriefSelection(
        included=tuple(as_str(f"{field_name}.included[{i}]", v) for i, v in enumerate(included)),
        omitted=as_text_map(f"{field_name}.omitted", got.get("omitted") or {}),
    )


def as_change_request(field_name: str, value: Any) -> ChangeRequest:
    got = as_dict(field_name, value)
    unknown = set(got) - {"targets", "intent"}
    if unknown:
        raise _fail(
            field_name, f"a change request; it has no field {sorted(unknown)[0]!r}", value
        )
    for required in ("targets", "intent"):
        if not got.get(required):
            raise _fail(field_name, f"a change request with {required}", value)
    return ChangeRequest(
        targets=tuple(as_refs(f"{field_name}.targets", got["targets"])),
        intent=as_str(f"{field_name}.intent", got["intent"]),
    )


def as_owner_decision(field_name: str, value: Any) -> OwnerDecision:
    got = as_dict(field_name, value)
    unknown = set(got) - {"disposition", "words", "replacement"}
    if unknown:
        raise _fail(
            field_name, f"a decision; it has no field {sorted(unknown)[0]!r}", value
        )
    for required in ("disposition", "words"):
        if not got.get(required):
            raise _fail(field_name, f"a decision with {required}", value)
    try:
        disposition = Disposition(as_str(f"{field_name}.disposition", got["disposition"]))
    except ValueError as exc:
        raise _fail(
            f"{field_name}.disposition",
            "one of " + ", ".join(d.value for d in Disposition),
            got["disposition"],
        ) from exc
    replacement = (
        as_submission(f"{field_name}.replacement", got["replacement"])
        if got.get("replacement") is not None
        else None
    )
    return OwnerDecision(
        disposition=disposition,
        words=as_str(f"{field_name}.words", got["words"]),
        replacement=replacement,
    )


# `as_split` stood here, decoding the parts a split divided into. It existed for one
# parameter of one call, and both are gone with the level (v3 change 1).


DECODERS: dict[str, Callable[[str, Any], Any]] = {
    "str": as_str,
    "int": as_int,
    "bool": as_bool,
    "ref": as_ref,
    "refs": as_refs,
    "ints": as_ints,
    "rows": as_submissions,
    "row": as_submission,
    "selector": as_selector,
    "spike": as_spike_spec,
    "selection": as_selection,
    "evidence": as_text_map,
    "change_request": as_change_request,
    "owner_decision": as_owner_decision,
}


# --- the registry ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Param:
    name: str
    kind: str
    required: bool = True
    #: What this argument is for, in the reader's words. It is the whole of the tool's
    #: documented interface, so it says what the caller must decide — never what the
    #: implementation does with it.
    note: str = ""


@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    service: str
    method: str
    contract: str
    summary: str
    params: tuple[Param, ...] = ()
    #: A tool that changes the plan. Recorded because the log is more useful when a reader
    #: can find every write without knowing the tool set by heart — not because anything
    #: gates on it. `contracts:50`'s write/read split existed to enforce the writer lease,
    #: and the lease is gone.
    writes: bool = False


def _t(name, service, method, contract, summary, *params, writes=False) -> Tool:
    return Tool(name, service, method, contract, summary, tuple(params), writes)


#: The contract address of a tool the frozen plan never declared. It is a word rather than
#: an address on purpose: a plausible-looking `contracts:N` here would be a citation to a
#: row that says something else, which is the one failure this whole build is about. Every
#: tool carrying it must appear in `ADDED` below, and a test enforces that.
DEVIATION = "deviation"


#: The tools, grouped by the task that owns them. Order is the frozen plan's own order, so
#: a reader comparing the two reads them the same way round.
REGISTRY: dict[str, Tool] = {
    t.name: t
    for t in (
        # --- storage-engine (components:1) ---
        _t("init_plan", "storage", "init_plan", "contracts:1",
           "Start a plan in this workspace.",
           Param("name", "str", note="what the plan is called"),
           Param("tier", "str", note="the plan tier; 'standard' is the only value today"),
           writes=True),
        _t("recover", "storage", "recover", "contracts:6",
           "Restore, salvage or restart after an integrity failure; never a silent repair.",
           Param("strategy", "str", note="restore, salvage or restart"),
           writes=True),
        _t("migrate", "storage", "migrate", "contracts:8",
           "Move the store to a schema version, snapshotting first and stating what changed.",
           Param("target_schema_version", "int", note="the schema version to reach"),
           writes=True),
        # --- row-service (components:2) ---
        _t("submit_rows", "rows", "submit_rows", "contracts:9",
           "File a batch of rows; each is accepted or rejected on its own, and the batch is "
           "atomic.",
           Param("batch", "rows", note="the rows to file, each with a name of its own; a "
                                       "world-assumption also carries the spike that will "
                                       "attack it (question, hypothesis, method, budget)"),
           Param("idempotency_key", "str", note="replaying this key returns the first receipt"),
           writes=True),
        _t("read_rows", "rows", "read_rows", "contracts:10",
           "Read the rows a selector picks out, a page at a time.",
           Param("selector", "selector", note="which rows: by address, table, stage, "
                                              "provenance, liveness or neighbourhood")),
        _t("resolve_assumption", "rows", "resolve_assumption", "contracts:11",
           "Upgrade an open assumption in place, quoting the owner's answer.",
           Param("ref", "ref", note="the assumption to settle"),
           Param("quote", "str", note="the owner's answer, in his words"),
           Param("resolution", "str", note="confirm, revise or reject"),
           Param("idempotency_key", "str", note="replaying this key changes nothing twice"),
           Param("retire_reason", "str", required=False,
                 note="why, when the resolution is reject"),
           Param("name", "str", required=False,
                 note="a new name, when the answer changed what the row says"),
           writes=True),
        _t("supersede_row", "rows", "supersede_row", "contracts:12",
           "Replace a row with a new one, keeping the old as frozen history.",
           Param("old", "ref", note="the row being replaced"),
           Param("replacement", "row", note="the row that replaces it; if it is a "
                                            "world-assumption it carries its spike, as at "
                                            "submission"),
           Param("reason", "str", note="why the old row was abandoned — what was learned "
                                       "that makes it wrong, which is not what the "
                                       "replacement's grounds say"),
           Param("idempotency_key", "str", note="replaying this key returns the first result"),
           writes=True),
        _t("retire_row", "rows", "retire_row", "contracts:13",
           "Retire a row that no longer applies, with the reason on the record.",
           Param("ref", "ref", note="the row to retire"),
           Param("reason", "str", note="why it no longer applies"),
           Param("idempotency_key", "str", note="replaying this key retires it once"),
           writes=True),
        _t("record_grounds", "rows", "record_grounds", DEVIATION,
           "Give a row the reasoning behind it: why it says what it says, and what was "
           "considered instead. Write-once per field.",
           Param("ref", "ref", note="the live row the argument belongs to"),
           Param("grounds", "str", note="why this row's content is what it is"),
           Param("alternatives", "str", note="what else was considered and why it lost; "
                                             "\"none, it follows from X\" is a complete "
                                             "answer when it is true"),
           Param("idempotency_key", "str", note="replaying this key returns the first result"),
           writes=True),
        # --- gap-engine (components:5) ---
        _t("next_gaps", "gaps", "next_gaps", "contracts:19",
           "The next cluster of gaps to work, newest deficiency first.",
           Param("limit", "int", required=False, note="how many to return"),
           Param("stage", "int", required=False,
                 note="restrict to one stage; omit for the current one")),
        _t("dismiss_gap", "gaps", "dismiss_gap", "contracts:66",
           "Set a gap aside with a recorded reason; it stops re-surfacing.",
           Param("gap_key", "str", note="the gap being dismissed"),
           Param("reason", "str", note="why it does not need answering"),
           writes=True),
        _t("reopen_gap", "gaps", "reopen_gap", "contracts:67",
           "Bring a dismissed gap back.",
           Param("gap_key", "str", note="the gap being reopened"),
           Param("reason", "str", note="what changed"),
           writes=True),
        # --- gate-engine (components:6) ---
        _t("run_gate", "gates", "run_gate", "contracts:22",
           "Run a stage's mechanical gate and record the verdict with its holes.",
           Param("stage", "int", note="which stage to gate"),
           writes=True),
        # --- warning-service (components:7) ---
        _t("suppress_warning", "warns", "suppress_warning", "contracts:24",
           "Silence a warning with a recorded reason; it still returns at critical points.",
           Param("warning_id", "int", note="the warning to silence"),
           Param("reason", "str", note="why it does not apply here"),
           writes=True),
        _t("active_warnings", "warns", "active_warnings", "contracts:23",
           "The warnings still standing; at a critical point the suppressed ones come too.",
           Param("context", "str", required=False,
                 note="a critical point, if this is one")),
        # --- conflict-service (components:8) ---
        _t("raise_conflict", "conflicts", "raise_conflict", "contracts:26",
           "Put two incompatible rows to the owner, with the engineering recommendation.",
           Param("refs", "refs", note="the rows that disagree"),
           Param("description", "str", note="what the disagreement is"),
           Param("recommendation", "str", note="what you would do, and why"),
           writes=True),
        _t("resolve_conflict", "conflicts", "resolve_conflict", "contracts:27",
           "Record the owner's adjudication permanently, override and all.",
           Param("conflict_id", "int", note="the conflict being settled"),
           Param("outcome", "str", note="which way it went"),
           Param("adjudication", "str", note="the owner's reasoning, in his words"),
           writes=True),
        # --- validation-service (components:9) ---
        _t("register_spike", "validation", "register_spike", "contracts:29",
           "Register a bounded experiment against a world-assumption.",
           Param("assumption", "ref", note="the assumption the spike will settle"),
           Param("spec", "spike", note="question, hypothesis, method and budget"),
           writes=True),
        _t("record_spike_result", "validation", "record_spike_result", "contracts:30",
           "Record what a spike found and settle the assumption accordingly.",
           Param("spike_id", "int", note="the spike that ran"),
           Param("outcome", "str", note="confirmed, refuted, inconclusive or blocked"),
           Param("evidence", "str", note="what was observed"),
           writes=True),
        _t("file_claim", "validation", "file_claim", "contracts:31",
           "File a load-bearing technical claim so it is validated rather than assumed.",
           Param("text", "str", note="the claim, stated so it can be wrong"),
           Param("kind", "str", note="what kind of claim it is, which routes its validation"),
           Param("refs", "refs", note="the rows resting on it"),
           Param("red_flag", "bool", required=False,
                 note="true if dependent planning must wait for it"),
           writes=True),
        _t("record_claim_outcome", "validation", "record_claim_outcome", "contracts:32",
           "Record a claim's validation outcome; a failure raises conflicts on its dependents.",
           Param("claim_id", "int", note="the claim validated"),
           Param("outcome", "str", note="how it came out"),
           Param("evidence", "str", note="what was found"),
           writes=True),
        # --- finding-service (components:10) ---
        _t("file_finding", "findings", "file_finding", "contracts:33",
           "File a finding against the specific rows it attacks.",
           Param("refs", "refs", note="the rows under attack"),
           Param("description", "str", note="the attack, stated so it can be adjudicated"),
           Param("severity", "str", note="how badly it matters"),
           Param("name", "str", note="what the finding says, in a few words"),
           Param("resolve_by", "int",
                 note="the stage gate this must be resolved by — its deadline, made a gate"),
           writes=True),
        _t("resolve_finding", "findings", "resolve_finding", "contracts:34",
           "Take a finding to a terminal outcome; an accepted risk stays visible at handoff.",
           Param("finding_id", "int", note="the finding being closed"),
           Param("outcome", "str", note="how it was closed"),
           Param("reason", "str", note="the reasoning, which an accepted risk needs most"),
           writes=True),
        _t("reallocate_finding", "findings", "reallocate_finding", DEVIATION,
           "Defer an open finding to a later gate, on the record. The one alternative to "
           "resolving it at its own gate.",
           Param("finding_id", "int", note="the open finding being deferred"),
           Param("resolve_by", "int", note="the later stage gate it now answers to"),
           Param("reason", "str", note="why it belongs there instead — the owner reads this"),
           writes=True),
        # --- task-graph (components:11) ---
        _t("finalize_plan", "tasks", "finalize_plan", "contracts:35",
           "Freeze the plan and derive the task graph from it.",
           writes=True),
        _t("graph_status", "tasks", "graph_status", "contracts:38",
           "Where the build has got to across the whole graph."),
        _t("next_task", "tasks", "next_task", "contracts:55",
           "The next ready task and its candidate rows — the selection is yours to make.",
           Param("allow_draft", "bool", required=False,
                 note="true to work from a plan that is not finalized"),
           Param("consent", "str", required=False,
                 note="the owner's recorded agreement to work from a draft")),
        _t("verify_completion", "tasks", "verify_completion", "contracts:62",
           "Check delivered evidence against every behaviour the task owes.",
           Param("task_id", "int", note="the task being verified"),
           Param("evidence", "evidence", note="what was delivered, per behaviour"),
           writes=True),
        _t("report_status", "tasks", "report_status", "contracts:60",
           "The engine's report of what it observed; 'done' still needs a passing verification.",
           Param("task_id", "int", note="the task reported on"),
           Param("status", "str", note="what happened"),
           Param("detail", "str", required=False, note="notes, which are not evidence"),
           writes=True),
        # --- brief-composer (components:12) ---
        _t("compose_brief", "briefs", "compose_brief", "contracts:68",
           "Record your selection as an immutable brief; every candidate must be accounted for.",
           Param("task_id", "int", note="the task the brief is for"),
           Param("selection", "selection",
                 note="the rows you include, and a reason for each you leave out"),
           writes=True),
        _t("audit_brief", "briefs", "audit_brief", "contracts:41",
           "Meter a brief against the closure frozen with it.",
           Param("brief_id", "int", note="the brief to audit")),
        # --- session-service (components:14) ---
        _t("journal_note", "resume", "journal_note", "contracts:48",
           "Leave an informal learning that is not a plan row.",
           Param("note", "str", note="what was learned"),
           Param("task", "ref", required=False, note="the row it came up against"),
           writes=True),
        _t("set_next_action", "resume", "set_next_action", "contracts:49",
           "Leave the next intended action, which is where the next planner resumes.",
           Param("intent", "str", note="what to do next"),
           writes=True),
        _t("plan_status", "resume", "plan_status", "contracts:64",
           "Where the work got to — the one call a cold planner makes first."),
        _t("journal", "resume", "journal", "contracts:48",
           "The journal notes, in full.",
           Param("stage", "int", required=False, note="restrict to one stage")),
        _t("gate_runs", "resume", "gate_runs", "contracts:22",
           "Every gate verdict recorded, newest first."),
        # --- guidance (components:4) ---
        _t("get_mandate", "guidance", "get_mandate", "contracts:17",
           "The engineer's mandate the methodology serves."),
        _t("get_stage_script", "guidance", "get_stage_script", "contracts:65",
           "The script for one planning stage.",
           Param("stage", "int", note="which stage's script")),
        _t("get_auxiliary", "guidance", "get_auxiliary", DEVIATION,
           "A script that belongs to no single stage — the red team's, for one.",
           Param("name", "str", note="which auxiliary script")),
        # --- the glossary (components:2, by deviation) ---
        _t("define_term", "terms", "define_term", DEVIATION,
           "Propose what a word means in this plan; the owner settles it. Draft the "
           "definition yourself — you have just read the rows it appears in.",
           Param("term", "str", note="the word itself"),
           Param("definition", "str",
                 note="what you believe it means here, in a sentence, for the owner to "
                      "accept or rewrite"),
           Param("names_ref", "ref", required=False,
                 note="the row this word names, if it names one"),
           writes=True),
        _t("approve_term", "terms", "approve_term", DEVIATION,
           "Record the owner settling a definition — as proposed, or in his own words.",
           Param("term", "str", note="the word being settled"),
           Param("definition", "str", required=False,
                 note="the owner's own wording, when he rewrote it; omit to accept the "
                      "proposal as it stands"),
           writes=True),
        _t("redefine_term", "terms", "redefine_term", DEVIATION,
           "Sharpen what a word means, keeping the old wording as history. Also how a "
           "retired word comes back.",
           Param("term", "str", note="the word being redefined"),
           Param("definition", "str", note="what it means now"),
           Param("names_ref", "ref", required=False,
                 note="the row it names, if that changed too"),
           writes=True),
        _t("retire_term", "terms", "retire_term", DEVIATION,
           "Take a word out of use, saying where it may no longer appear and what to say "
           "instead.",
           Param("term", "str", note="the word being retired"),
           Param("ban_scope", "str",
                 note="where it is out: prose, identifier, or both"),
           Param("ban_reason", "str", note="why, so the next writer can agree with it"),
           Param("use_instead", "str", required=False,
                 note="the word to say instead; it must be defined already"),
           writes=True),
        _t("glossary", "terms", "glossary", DEVIATION,
           "Every word this plan has agreed the meaning of, retired ones included."),
        _t("export_glossary", "terms", "export_glossary", DEVIATION,
           "Publish the vocabulary as a manifest in the workspace for your own checks to "
           "read.",
           writes=False),
        # --- the render (components:15, by deviation) ---
        _t("render_plan", "renderer", "render_plan", DEVIATION,
           "Write the plan to a document in the workspace for the owner to read; the "
           "rows stay the only source of truth.",
           writes=False),
        # --- revision-service (components:13) ---
        _t("open_revision", "revision", "open_revision", "contracts:42",
           "Open a revision of a finalized plan: it snapshots the plan, bumps the version, "
           "and enumerates every row the change touches.",
           Param("change", "change_request",
                 note="the rows you want to change, and why, in your words"),
           writes=True),
        _t("next_repercussion", "revision", "next_repercussion", "contracts:43",
           "The next ripple to decide on, or notice that the walkthrough is complete.",
           Param("revision_id", "int", note="the open revision")),
        _t("adjudicate_repercussion", "revision", "adjudicate_repercussion", "contracts:57",
           "Decide the ripple the walkthrough is presenting: accept it, reword the row, or "
           "defer. A reword applies to the live plan the moment it is conflict-free.",
           Param("revision_id", "int", note="the open revision"),
           Param("item_id", "int", note="the repercussion the walkthrough is presenting now"),
           Param("decision", "owner_decision",
                 note="accept, modify (carrying the replacement row), or defer — in your "
                      "words"),
           writes=True),
        _t("apply_revision", "revision", "apply_revision", "contracts:45",
           "Close a fully-adjudicated revision; the plan's new version goes live.",
           Param("revision_id", "int", note="the revision to close"),
           writes=True),
        _t("abandon_revision", "revision", "abandon_revision", "contracts:46",
           "Preview or perform a rewind of the plan to how it stood when the revision "
           "opened. Without confirmation it only shows what would be undone.",
           Param("revision_id", "int", note="the revision to abandon"),
           Param("confirm", "bool", required=False,
                 note="true to actually rewind; omit to preview what a rewind reverts"),
           writes=True),
    )
}


@dataclass(frozen=True, slots=True)
class Absence:
    """A contract the frozen plan sends to the surface that no tool exposes, and why.

    An absence carries its reason so the coverage test can subtract it. That is the whole
    mechanism: a shortfall with no entry here fails the suite, and an entry here is a
    visible act with a sentence attached to it.
    """

    contract: str
    call: str
    reason: str


#: Contracts the plan sends here that this tool does not implement, each with the decision
#: that struck it. Three are the writer lock, removed entirely (D5) on the grounds that the
#: owner plans in one session and the lock guarded a situation that cannot arise. The fourth
#: is the split, removed with the sub-task level (v3 D5/D7): a task is one function, so
#: there is nothing to divide, and the call is named here under the frozen plan's own
#: spelling so a reader grepping it lands on the reason.
EXCLUDED: tuple[Absence, ...] = (
    Absence("contracts:53", "renew_lease",
            "the writer lock was removed; there is no lease to renew"),
    Absence("contracts:54", "release_writer_lock",
            "the writer lock was removed; there is nothing held to release"),
    Absence("contracts:63", "acquire_writer_lock",
            "the writer lock was removed; there is nothing to acquire"),
    Absence("contracts:40", "split_subtask",
            "the level it divided is gone (v3 change 1): a task is one externally-callable "
            "function, so an over-large brief is answered by the plan naming smaller "
            "contracts, not by the graph dividing a node after the fact"),
)

#: Not built yet, each bound to the build stage that owes it — the outstanding-problem
#: rule: an unresolved item is fixed now or bound to a named gate, never floating.
DEFERRED: tuple[Absence, ...] = (
)

#: The other direction from `DEFERRED`: tools that exist with no contract behind them. The
#: coverage test only reads plan → surface, so without this list a tool could be added with
#: no contract, no reason and nobody noticing — the mirror of the shortfall that list
#: catches. Each entry names the deviation that decided it.
ADDED: tuple[Absence, ...] = (
    Absence(DEVIATION, "render_plan",
            "the plan scoped plan rendering out, and the last planning stage ends by "
            "skimming a rendered plan with the owner (D21)"),
    Absence(DEVIATION, "get_auxiliary",
            "the red-team script is a content asset requirements:71 ships and no contract "
            "served it, so the red team could not fetch its own brief (D21)"),
    Absence(DEVIATION, "define_term",
            "the eight planning stages never ask what the words mean, so a plan could "
            "not say — and a vocabulary nothing records is the one F27 broke (D23)"),
    Absence(DEVIATION, "approve_term",
            "a definition the tool took from a planning session and filed as settled is "
            "the tool deciding what the owner's words mean; he accepts it or writes his "
            "own (D23)"),
    Absence(DEVIATION, "redefine_term",
            "a meaning sharpens, and the old wording has to stay readable or the change "
            "reads as a contradiction later (D23)"),
    Absence(DEVIATION, "retire_term",
            "retiring a word is the act the whole mechanism exists to make visible, and "
            "the banned list is what every check downstream counts against (D23)"),
    Absence(DEVIATION, "glossary",
            "a writer needs the words before typing, and a resuming planner has no other "
            "way back to them (D23)"),
    Absence(DEVIATION, "export_glossary",
            "the delivery point that achieves the most: the tool publishes the vocabulary "
            "and the codebase's own checks enforce it, with no judgment exercised (D23)"),
    Absence(DEVIATION, "reallocate_finding",
            "D15 gives a finding two exits, resolve or defer-to-a-later-gate; without a tool "
            "for the second, the gate lock could only ever be satisfied by resolving, and a "
            "finding that genuinely belongs later would have no honest move (D15, F39)"),
    Absence(DEVIATION, "record_grounds",
            "the plan never anticipated the decision-context fields, so it cannot have "
            "anticipated the call; without one, the only way to give an existing row its "
            "grounds is a full replacement submission and a supersede reason for an "
            "abandonment that never happened (v3 D11)"),
)

#: What a contract's frozen text no longer says about the call that implements it.
#:
#: Five contracts changed shape in v3 change 2 — a new required parameter, a new refusal, a
#: renamed one. `spec/v2/plan.md` is the frozen specification and has not been edited since
#: it was frozen; every divergence from it since has been recorded at the code instead
#: (`EXCLUDED`, `ADDED`, the frozen spellings in `errors.py`). This is the same mechanism
#: for the same reason: a contract whose signature or error list is stale lies to its
#: reader, and the cheapest honest answer is to say so where the reader is.
#:
#: **The build specification asked for these five rows to be *superseded* in the frozen
#: plan instead** (`spec/v3/builds/02-decision-context.md` §7, task 2D.1 behaviour 5). That
#: is a bigger act than it reads: superseding mints new ordinals, so every one of the ~50
#: citations of these five addresses across the engine, the tests and the v3 documents would
#: point at frozen history, `plan.md` would have to be re-rendered, and the coverage test's
#: denominator moves. It is the owner's call to make and this list is the work order for it.
AMENDED: tuple[Absence, ...] = (
    Absence("contracts:9", "submit_rows",
            "a submitted row may now carry `grounds` and `alternatives`, both optional; the "
            "frozen payload shape predates them"),
    Absence("contracts:11", "resolve_assumption",
            "raises RetireNeedsReason: a rejection retires the row, and a blank reason "
            "supplied for it is refused rather than replaced by the owner-rejected default"),
    Absence("contracts:12", "supersede_row",
            "the signature gains a required `reason` — why the old row was abandoned — and "
            "it raises SupersedeNeedsReason when that is blank"),
    Absence("contracts:13", "retire_row",
            "raises RetireNeedsReason; the frozen contract takes a reason and never said a "
            "blank one was refused, and until schema 9 it was not"),
    Absence("contracts:34", "resolve_finding",
            "the `rationale` parameter is now `reason`, with the column it writes; the word "
            "was retired as a second spelling of one this store already had"),
)

#: `contracts:50`'s `NotWriter`, struck rather than implemented. Recorded here because an
#: outcome that is simply absent looks the same as one that was forgotten.
MOOT_OUTCOMES = {
    "NotWriter": "there is no writer lease to be without; the lock was removed (D5)",
}


# --- the log -----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LogEvent:
    """contracts:51 — one tool call or failure, as the observability log records it."""

    tool: str
    started_at: str
    finished_at: str
    outcome: str
    summary: str
    failure_mode: str | None = None

    def as_line(self) -> str:
        return json.dumps(
            {
                "tool": self.tool,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "outcome": self.outcome,
                "summary": self.summary,
                "failure_mode": self.failure_mode,
            },
            separators=(",", ":"),
        )


class ObservabilityLog:
    """The append-only record of what was called (`decisions:46`, `requirements:66`).

    One JSON object per line, appended and never rewritten. A failure to write raises:
    `contracts:51` says operations are never silently unlogged, and a log that drops lines
    when the disk is full is worse than no log, because it is trusted.
    """

    def __init__(self, workspace: Path | str):
        self.path = Path(workspace) / LOG_FILENAME

    def append_log(self, event: LogEvent) -> None:
        if event.failure_mode is not None and event.failure_mode not in FAILURE_MODES:
            raise LogWriteError(
                "unknown failure mode", mode=event.failure_mode,
                expected=", ".join(FAILURE_MODES),
            )
        try:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(event.as_line() + "\n")
        except OSError as exc:
            raise LogWriteError(
                "the observability log cannot be written",
                path=str(self.path), cause=str(exc),
            ) from exc

    def read(self) -> list[dict]:
        """Every event, for tests and for anyone auditing a run. Not a tool: the log is
        about the tool, and a tool that serves its own log invites a planner to reason
        about its own history instead of the plan's."""
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]


# --- dispatch ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ToolCall:
    """contracts:50 — an MCP tool name and its JSON arguments."""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolResult:
    """contracts:50 — engine-agnostic MCP content.

    `ok` and a payload, or `ok=False` and an error naming the problem. There is no third
    shape: a caller that has to guess which fields are populated is a caller that will
    guess wrong on the failure path, which is the path that matters.

    **The failure path takes the door's gentler half, and that is deliberate.** An engine
    error names the row it refused — `RowNotFound(ref='requirements:61')` — so almost every
    refusal carries an address. Rejecting the message for it would replace a pedagogical
    error (`requirements:14`) with a complaint about the pedagogical error, which serves
    nobody. So a refusal is annotated rather than rewritten or rejected: the message stands
    exactly as the engine wrote it, with each address resolved beside it. The strict half of
    the door still applies to text the surface itself composes, where a bare address is our
    failure and not the engine's report of the caller's.
    """

    ok: bool
    tool: str
    payload: Any = None
    error: str | None = None
    problem: str | None = None
    #: Every address this result mentions, resolved to the row it addresses. One block
    #: beside the payload rather than a note at each occurrence, so that no value's shape
    #: changes on its way out — a gap key stays a gap key, and the caller can hand it
    #: straight back.
    cites: tuple[Resolution, ...] = ()

    def as_content(self) -> dict[str, Any]:
        body: dict[str, Any] = {"ok": self.ok, "tool": self.tool}
        if self.ok:
            body["result"] = self.payload
        else:
            body["error"] = self.error
            body["problem"] = self.problem
        if self.cites:
            body["cites"] = list(self.cites)
        return body


class Surface:
    """The toolset. One instance per workspace, holding the services it wraps.

    It owns nothing of its own: every tool is a service contract with validation in front
    of it and the door behind it. That is what keeps this an adapter — the MCP toolset is
    the first one, and a second (the GUI) plugs into the same seam without moving anything.
    """

    def __init__(self, storage: Storage, *, guidance: Guidance | None = None):
        self.storage = storage
        self.terms = TermService(storage)
        # The glossary is built before the row service, which consults it at submission:
        # the moment of typing is the only moment at which saying "that word is retired"
        # changes what gets written (D23).
        self.rows = RowService(storage, terms=self.terms)
        self.terms.rows = self.rows
        self.graph = LinkGraph(storage)
        self.conflicts = ConflictService(storage, self.rows)
        self.warns = WarningService(storage)
        self.gaps = GapEngine(storage, self.rows)
        # The warning ledger mirrors conditions the gap-engine computes (open gaps, open
        # assumptions, retired-word uses). Late-bound here — the gap-engine is built after
        # the warning service — so `active_warnings` reconciles those against live state and
        # never reports one a mutation has already cleared (DEFECTS.md F50). Same late-bind
        # shape as `terms.rows = rows` above.
        self.warns.live_warning_keys = self.gaps.live_warning_keys
        # Findings are built before the gate that reads them: the stage-7 criteria go
        # through the finding service now, not through plan_rows (D22).
        self.findings = FindingService(storage, self.rows)
        self.gates = GateEngine(
            storage, self.rows, self.conflicts, self.warns, gaps=self.gaps,
            findings=self.findings, terms=self.terms,
        )
        self.validation = ValidationService(
            storage, self.rows, self.graph, self.conflicts
        )
        self.attachments = AttachmentService(storage, self.rows)
        self.behaviours = BehaviourService(storage)
        self.tasks = TaskGraphService(
            storage, self.rows, graph=self.graph, findings=self.findings
        )
        self.briefs = BriefComposer(
            storage, self.tasks, graph=self.graph, attachments=self.attachments,
            behaviours=self.behaviours, terms=self.terms,
        )
        self.revision = RevisionService(
            storage, self.graph, self.rows, self.findings, self.warns, self.conflicts
        )
        self.guidance = guidance or Guidance()
        # `renderer`, not `render`: the door's `render` is a module-level function used a
        # few lines below in `dispatch`, and two things called the same word in one class
        # is exactly the collision this build keeps writing down.
        self.renderer = PlanRender(storage, self.rows, self.findings)
        self.resume = ResumeService(
            storage, gaps=self.gaps, warnings=self.warns, guidance=self.guidance,
            terms=self.terms,
        )
        self.log = ObservabilityLog(storage.workspace)
        self._resolve = resolver_from(self.rows, self.findings)
        # Follows a dead citation to its live successor (F17, owner's ruling): a brief is
        # read by a code engine that cannot go and look, so a superseded address that names
        # its successor is the difference between a lead and a dead end.
        self._follow = successor_lookup(self.rows, self.findings)

    # --- contracts:50 ---

    @property
    def tool_names(self) -> set[str]:
        return set(REGISTRY)

    def describe(self) -> list[dict[str, Any]]:
        """The tool list an MCP client asks for on connect."""
        return [
            {
                "name": tool.name,
                "description": tool.summary,
                "arguments": [
                    {
                        "name": p.name,
                        "type": p.kind,
                        "required": p.required,
                        "description": p.note,
                    }
                    for p in tool.params
                ],
            }
            for tool in REGISTRY.values()
        ]

    def dispatch(self, call: ToolCall) -> ToolResult:
        """Route one call, log it either way, and let nothing past the door.

        The order matters and is the reason this is one function: validate before touching
        a service so a malformed call files nothing (`requirements:14`), and scan after
        rendering so a payload that cannot be read fails as a call rather than arriving as
        confusion.
        """
        started = now()
        tool = REGISTRY.get(call.name)
        if tool is None:
            return self._refuse(call.name, started, self._no_such_tool(call.name),
                                "malformed")
        try:
            args = self._bind(tool, call.arguments)
        except MalformedCall as exc:
            return self._refuse(tool.name, started, exc, "malformed")

        try:
            value = getattr(getattr(self, tool.service), tool.method)(**args)
        except PlanToolError as exc:
            return self._refuse(tool.name, started, exc, self._mode_of(exc))
        except Exception as exc:  # noqa: BLE001 — an unexpected failure is still a result
            return self._refuse(
                tool.name, started,
                PlanToolError(f"{type(exc).__name__}: {exc}"), "partial",
            )

        cites: list[Resolution] = []
        detail: Any = render(value, self._resolve, cites, self._follow)

        # The presented digest is the one string on this path the surface assembles rather
        # than reads, so it is the one the strict half of the door applies to — hand-assembled
        # presentation text is exactly where both invariants were broken before they were
        # checks. But a digest is not uniformly the tool's own words: it quotes stored prose
        # (a warning, a journal note, a recorded next action) whose addresses are the owner's
        # input, not the tool's failure. A digest that can carry that mix exposes
        # `present_lines`, returning provenance-typed parts — plain lines held strictly,
        # `Verbatim` lines exempt. We scan the parts (granular) but serve the joined string,
        # so the payload contract is unchanged and owner prose no longer crashes the call
        # (DEFECTS.md F49). A composed-only digest keeps the plain `present` path and its
        # strict scan.
        present_segments = getattr(value, "present_lines", None)
        if callable(present_segments):
            segments = present_segments(lambda ref: display(ref, self._resolve))
            payload: Any = {"summary": "\n".join(segments), "detail": detail}
            to_scan: Any = {"summary": segments, "detail": detail}
        else:
            digest = getattr(value, "present", None)
            payload = {"summary": digest(), "detail": detail} if callable(digest) else detail
            to_scan = payload
        try:
            scan(to_scan, self.tool_names)
        except PlanToolError as exc:
            return self._refuse(tool.name, started, exc, "malformed")

        self.log.append_log(
            LogEvent(
                tool=tool.name, started_at=started, finished_at=now(),
                outcome="ok", summary=_summarise(value),
            )
        )
        return ToolResult(
            ok=True, tool=tool.name, payload=payload, cites=tuple(cites)
        )

    # --- validation ---

    @staticmethod
    def _no_such_tool(name: str) -> UnknownTool:
        """`contracts:50` — name the unknown tool and list the valid ones.

        With one thing added that the driver made obvious: a call we deliberately did not
        build is answered with the reason we did not, not with the same shrug a typo gets.
        `EXCLUDED` and `DEFERRED` already carry those reasons for the coverage test, and a
        planner reading "no tool called 'acquire_writer_lock'" alongside the whole tool
        list has been told nothing — it looks like an omission, and the
        reasons were written down precisely so it would not.
        """
        for absence in EXCLUDED:
            if absence.call == name:
                return UnknownTool(
                    f"{name} is not exposed, on purpose: {absence.reason}"
                )
        for absence in DEFERRED:
            if absence.call == name:
                return UnknownTool(f"{name} is not built yet: {absence.reason}")
        return UnknownTool(
            f"no tool called {name!r}", valid=", ".join(sorted(REGISTRY))
        )

    def _bind(self, tool: Tool, arguments: Any) -> dict[str, Any]:
        """Turn JSON arguments into the service call's arguments, or refuse and say why."""
        if not isinstance(arguments, dict):
            raise MalformedCall(
                f"{tool.name} takes named arguments", got=repr(arguments)[:120]
            )
        expected = {p.name for p in tool.params}
        unknown = sorted(set(arguments) - expected)
        if unknown:
            raise MalformedCall(
                f"{tool.name} has no argument {unknown[0]!r}",
                expected=", ".join(sorted(expected)) or "none",
            )
        bound: dict[str, Any] = {}
        for param in tool.params:
            if param.name not in arguments:
                if param.required:
                    raise MalformedCall(
                        f"{tool.name} needs {param.name}: {param.note}",
                        missing=param.name,
                    )
                continue
            bound[param.name] = DECODERS[param.kind](param.name, arguments[param.name])
        return bound

    # --- failure ---

    @staticmethod
    def _mode_of(exc: PlanToolError) -> str:
        """Label a failure with the vocabulary `contracts:51` logs in.

        Everything the engine refuses on purpose is `malformed` — the call asked for
        something the plan's rules do not allow — except a store that cannot be reached,
        which is `unavailable`. Guessing more finely than the evidence supports would put
        invented labels into the one record that is supposed to be evidence.
        """
        return "unavailable" if type(exc).__name__ == "StorageUnavailable" else "malformed"

    def _refuse(
        self, tool_name: str, started: str, exc: PlanToolError, mode: str
    ) -> ToolResult:
        cites: list[Resolution] = []
        problem = str(collect(str(exc), self._resolve, cites, self._follow))
        self.log.append_log(
            LogEvent(
                tool=tool_name, started_at=started, finished_at=now(),
                # `summary` carries the exception's own name, which is what distinguishes
                # a caller's malformed call from the door refusing our own output. The
                # five failure modes are the vocabulary `contracts:51` names and none of
                # them is "the tool wrote something unreadable"; inventing a sixth would
                # put a label into the record that no row defines.
                outcome="refused", summary=type(exc).__name__, failure_mode=mode,
            )
        )
        return ToolResult(
            ok=False, tool=tool_name, error=type(exc).__name__, problem=problem,
            cites=tuple(cites),
        )


def _summarise(value: Any) -> str:
    """One line for the log. Never the payload: the log records that a call happened and
    how it went, and a log that carries plan content is a second copy of the plan that
    nothing keeps in step."""
    if value is None:
        return "no content"
    if isinstance(value, (list, tuple)):
        return f"{len(value)} item(s)"
    return type(value).__name__
