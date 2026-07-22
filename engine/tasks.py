"""task-graph (components:11).

Derives the dependency-ordered implementation task graph at finalization and maintains
build-state truth: readiness, engine status reports, staleness flags, and draft-serving
policy.

Contracts: contracts:35 finalize_plan, contracts:38 graph_status, contracts:55
next_subtask, contracts:60 report_status, contracts:62 verify_completion.

Plus two contracts the frozen plan does not have. `state_machines:9` names six events and
the plan names a firing contract for only four of them: nothing fires `deps_satisfied` or
`serve_brief` (DEFECTS.md F18). They are supplied here as `readiness_of`/`refresh_readiness`
and `serve_brief`, on task-graph, because both are the *system's* judgment —
`crud_grid:35` splits system-owned readiness from engine-owned status reports, and routing
them through `report_status` would let the code engine assert its own readiness, voiding
`sm_cells:131` ("unbuildable work is never served"). A gate the graded party can open is
not a gate.

Two design decisions the plan does not make, both logged:

- **D10** — readiness is a level-triggered *predicate*, not a stored edge event. `ready` is
  therefore never written to `subtasks.state`; it is computed from dependency state every
  time it is asked for. This is what makes `rework_flagged` recoverable: under an
  edge-triggered reading its `deps_satisfied` edge has already fired for the last time and
  the state is a trap (DEFECTS.md F19a).
- **D11** — the provider/consumer dependency edge is a typed link (`edge_type='depends_on'`,
  consumer -> provider). `decisions:63` derives edges from `contract_deps`, which does not
  exist in v2 (DEFECTS.md F20).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from engine.errors import PlanToolError
from engine.models import RowRef
from engine.obligations import ObligationService
from engine.clock import age_seconds, now
from engine.idempotency import key
from engine.storage import FromOp, Op, Storage

# --- state_machines:9, the SubTask lifecycle ---

PENDING = "pending"
READY = "ready"
IN_PROGRESS = "in_progress"
BLOCKED = "blocked"
DONE = "done"
REWORK_FLAGGED = "rework_flagged"

#: The states actually written to `subtasks.state`. `ready` is absent by design (D10):
#: it is derived from dependency state, never stored.
STORED_STATES = (PENDING, IN_PROGRESS, BLOCKED, DONE, REWORK_FLAGGED)

#: (presented state, event) -> next *stored* state, from sm_cells:130-165. Absent pairs
#: are the "impossible" cells. Keyed on the presented state because `ready` is what the
#: state machine transitions from even though it is never stored.
_TRANSITIONS = {
    (PENDING, "block"): BLOCKED,
    (READY, "serve_brief"): IN_PROGRESS,
    (READY, "block"): BLOCKED,
    (IN_PROGRESS, "serve_brief"): IN_PROGRESS,     # sm_cells:143, re-serving is legal
    (IN_PROGRESS, "complete"): DONE,
    (IN_PROGRESS, "block"): BLOCKED,
    (BLOCKED, "unblock"): PENDING,                 # presented as ready when deps allow
    (DONE, "flag_rework"): REWORK_FLAGGED,
    (REWORK_FLAGGED, "block"): BLOCKED,
}

#: Why each forbidden pair is forbidden, quoted from the sm_cells rationale so the error
#: message carries the plan's own reasoning rather than a paraphrase.
_IMPOSSIBLE = {
    (PENDING, "serve_brief"): "dependencies unfinished — unbuildable work is never served",
    (PENDING, "complete"): "no work served",
    (PENDING, "unblock"): "not blocked",
    (PENDING, "flag_rework"): "nothing built",
    (READY, "complete"): "no work in progress",
    (READY, "unblock"): "not blocked",
    (READY, "flag_rework"): "nothing built",
    (IN_PROGRESS, "unblock"): "not blocked",
    (IN_PROGRESS, "flag_rework"):
        "nothing delivered yet — mid-work defects go through block",
    (BLOCKED, "serve_brief"): "unblock first",
    (BLOCKED, "complete"): "blocked work cannot complete",
    (BLOCKED, "block"): "already blocked",
    (BLOCKED, "flag_rework"): "nothing delivered",
    (DONE, "serve_brief"): "already done",
    (DONE, "complete"): "already done",
    (DONE, "block"): "done work is flagged for rework, not blocked",
    (DONE, "unblock"): "not blocked",
    (REWORK_FLAGGED, "serve_brief"): "must re-enter readiness first",
    (REWORK_FLAGGED, "complete"): "no work served",
    (REWORK_FLAGGED, "unblock"): "not blocked",
    (REWORK_FLAGGED, "flag_rework"): "already flagged",
}

#: The events a code engine may report (crud_grid:35 — its half of the update
#: responsibility). `deps_satisfied` and `serve_brief` are the system's and are excluded:
#: readiness the engine can assert is not readiness. See DEFECTS.md F18.
ENGINE_EVENTS = ("complete", "block", "unblock", "flag_rework")

#: dep_failure_modes:6 — a sub-task untouched this long is stale.
STALENESS_SECONDS = 24 * 3600

#: D11 — the typed edge task-graph derivation reads. Untyped links are traceability.
DEPENDS_ON = "depends_on"


class GatesIncomplete(PlanToolError):
    """contracts:35 — a required package gate has not passed; names it."""


class CycleDetected(PlanToolError):
    """contracts:35 — the derived graph contains a dependency cycle, surfaced as a design
    conflict before implementation starts (requirements:35)."""


class UnresolvedFindings(PlanToolError):
    """contracts:35 — findings neither addressed nor explicitly accepted block
    finalization (requirements:32)."""


class PlanNotFinalized(PlanToolError):
    """contracts:55 — refused unless allow_draft with recorded owner consent."""


class SubTaskNotFound(PlanToolError):
    """contracts:60/62 — names the missing id."""


class InvalidTransition(PlanToolError):
    """contracts:60 — not a legal transition in state_machines:9; state unchanged."""


class VerificationMissing(PlanToolError):
    """contracts:60 — status 'done' reported without a passing verify_completion verdict
    for the sub-task; transition refused, state unchanged."""


class MalformedReport(PlanToolError):
    """contracts:60 — report fails validation; rejected naming the specific problem;
    sub-task state unchanged, engine resubmits (dep_failure_modes:8)."""


class EvidenceIncomplete(PlanToolError):
    """contracts:62 — a contract in the sub-task's scope has no mapped evidence item;
    verification refused naming the unaccounted contracts, state unchanged."""


class UnpackagedTask(PlanToolError):
    """Not in the frozen plan. GLOSSARY.md / DEVIATIONS.md D13: every task belongs to
    exactly one package and finalization refuses a plan with an unpackaged task. There is
    deliberately no catch-all: a default bucket satisfies the invariant while quietly
    restoring the three-level model, and a grouping nobody chose is a grouping nobody
    reviews."""


class PackageNotFound(PlanToolError):
    """A package is a row with an id, never a free-text label. A name-keyed grouping
    yields an empty context set on a typo, which is the mistake `milestone` made."""


class SubTaskSuperseded(PlanToolError):
    """Not in the frozen plan. DEFECTS.md F25: `contracts:40` says a split's products
    supersede the original "in the graph" without saying what that means, so nothing stopped
    a split original from being served, reported on or verified. It is out of the graph: its
    work is owned by the sub-tasks that replaced it."""


class NotInProgress(PlanToolError):
    """Not in the frozen plan. contracts:62 declares no state precondition, so a passing
    verdict could be banked against a `pending` sub-task and later satisfy contracts:60's
    guard — verification of work that was never served. DEFECTS.md F19(b)."""


@dataclass(frozen=True, slots=True)
class SubTask:
    id: int
    contract_ref: RowRef
    title: str
    #: The owning task's id, resolved at finalization from the contract's `belongs_to`
    #: link. None when the contract declares no owner — see DEFECTS.md F24.
    task_id: int | None
    state: str
    serve_epoch: int
    deps: tuple[int, ...] = ()
    detail: str | None = None
    block_reason: str | None = None
    #: The sub-task that replaced this one in a split (`contracts:40`). A superseded node
    #: leaves the graph entirely — see `is_live` and DEFECTS.md F25.
    superseded_by: int | None = None
    created_at: str = ""
    updated_at: str = ""

    @property
    def is_live(self) -> bool:
        return self.superseded_by is None


@dataclass(frozen=True, slots=True)
class Package:
    """The one level a human declares (D13). A row with an id — never a name."""

    id: int
    name: str
    intent: str = ""
    created_at: str = ""


@dataclass(frozen=True, slots=True)
class Task:
    """The work of realising one unit of the architecture. Derived one per `components:N`
    row — the frozen plan's read-only spelling of this same entity — so a task cannot be
    misfiled; its *package* is the judgment, and that is what gets recorded."""

    id: int
    source_ref: str
    name: str
    package_id: int


@dataclass(frozen=True, slots=True)
class GraphStatus:
    """contracts:38 — built, in-flight, blocked and stale sub-tasks, so any fresh session
    resumes the build exactly."""

    built: tuple[int, ...]
    in_flight: tuple[int, ...]
    blocked: tuple[int, ...]
    ready: tuple[int, ...]
    pending: tuple[int, ...]
    rework: tuple[int, ...]
    stale: tuple[int, ...]

    @property
    def complete(self) -> bool:
        return not (self.in_flight or self.blocked or self.ready
                    or self.pending or self.rework)


@dataclass(frozen=True, slots=True)
class TaskGraph:
    """contracts:35 — ordered so no sub-task precedes its dependencies
    (requirements:34)."""

    order: tuple[int, ...]
    subtasks: tuple[SubTask, ...]
    edge_count: int
    #: requirements:23 — finalization is a critical point, so suppressed warnings
    #: resurface here rather than staying quiet.
    resurfaced_warnings: tuple[str, ...] = ()
    #: Contracts whose obligation surface the planning session never declared (D12).
    #: Reported rather than invented: the tool will not guess a denominator. These
    #: sub-tasks cannot be split or verified until the enumeration exists, and saying so
    #: at finalization is the loud failure F23's silent one has to become.
    unenumerated: tuple[str, ...] = ()

    @property
    def all_roots(self) -> bool:
        """No dependency edges at all. Legitimate on a plan that declares none, but
        worth surfacing rather than assuming — see DEVIATIONS.md D11's accepted cost."""
        return self.edge_count == 0 and len(self.subtasks) > 1


@dataclass(frozen=True, slots=True)
class VerificationVerdict:
    """contracts:62 — recorded durably with the evidence."""

    subtask_id: int
    serve_epoch: int
    verdict: str
    evidence: dict[str, str]
    unaccounted: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return self.verdict == "pass"


@dataclass(frozen=True, slots=True)
class SubTaskCandidates:
    """contracts:55 — the ready sub-task plus its full candidate closure, for the
    planning session's LLM to make the BriefSelection from. Composing the brief is a
    separate second call (findings:3)."""

    subtask: SubTask
    closure: tuple[RowRef, ...]
    is_draft: bool = False


@dataclass(frozen=True, slots=True)
class AllBlockedReport:
    """contracts:55 / uc_extensions:34 — naming the blocking dependencies instead of
    serving unbuildable work."""

    blocking: dict[int, tuple[int, ...]] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return False


class TaskGraphService:
    def __init__(
        self, storage: Storage, rows, graph=None, gates=None, findings=None,
        obligations=None,
    ):
        self.storage = storage
        self.rows = rows
        self.graph = graph
        self.gates = gates
        self.findings = findings
        self.obligations = obligations or ObligationService(storage)

    # --- the package/task levels (DEVIATIONS.md D13, GLOSSARY.md) ---

    def declare_package(self, name: str, intent: str = "") -> Package:
        """Declare a build package — "the GUI", "the controller", "the persistence layer".

        The **only** level a human chooses rather than derives, which is why it is the only
        one that needs entity discipline: an id, an owner, supersession. Nothing here
        proposes a cut. Which package a task belongs to is a judgment, and the tool records
        judgment but never exercises it (`decisions:12`); the methodology's architecture
        script is what leads the planner to a cut, and the owner decides. A packaging
        heuristic in the engine would be the tool holding opinions about architecture.
        """
        stamp = now()
        op = Op("insert", "packages", {
            "name": name, "intent": intent, "created_at": stamp, "updated_at": stamp,
        })
        self.storage.write_atomic([op], key("package", name))
        return Package(id=op.result["id"], name=name, intent=intent, created_at=stamp)

    def assign_task(self, source_ref: RowRef | str, package_id: int) -> Task:
        """Place the task described by `source_ref` into a package — the recorded
        judgment. `source_ref` is a `components:N` row: that is the frozen plan's
        read-only spelling of **task**, one entity with one id space (`GLOSSARY.md`)."""
        ref = str(source_ref)
        if not self.storage.query("SELECT id FROM packages WHERE id = ?", (package_id,)):
            raise PackageNotFound(
                f"no package {package_id}; declare it first — a package is a row with an "
                "id, never a free-text label",
                package_id=package_id,
            )
        found = self.storage.query(
            "SELECT content FROM plan_rows WHERE table_name || ':' || ordinal = ?", (ref,)
        )
        if not found:
            raise SubTaskNotFound("no such task source row", ref=ref)
        content = json.loads(found[0]["content"])
        name = content.get("title") or content.get("name") or ref

        stamp = now()
        existing = self.storage.query("SELECT id FROM tasks WHERE source_ref = ?", (ref,))
        if existing:
            op = Op("update", "tasks",
                    {"package_id": package_id, "updated_at": stamp},
                    where={"id": existing[0]["id"]})
            self.storage.write_atomic([op], key("task", ref, package_id))
            return Task(existing[0]["id"], ref, name, package_id)
        op = Op("insert", "tasks", {
            "source_ref": ref, "name": name, "package_id": package_id,
            "created_at": stamp, "updated_at": stamp,
        })
        self.storage.write_atomic([op], key("task", ref, package_id))
        return Task(op.result["id"], ref, name, package_id)

    def _guard_packaging(self) -> None:
        """D13 — finalization refuses a plan with an unpackaged task.

        The invariant the *database* enforces is `tasks.package_id NOT NULL`; what it cannot
        enforce is that a task row exists at all. That gap is this check. It is deliberately
        loud: an unpackaged task is one whose sub-tasks would silently miss their mid-level
        context, and a sub-task quietly missing context is exactly what `decisions:14`
        measures.
        """
        unplaced = [
            f"{r['table_name']}:{r['ordinal']}"
            for r in self.storage.query(
                "SELECT table_name, ordinal FROM plan_rows WHERE table_name = 'components' "
                "AND superseded_by IS NULL AND retired_at IS NULL "
                "AND table_name || ':' || ordinal NOT IN (SELECT source_ref FROM tasks) "
                "ORDER BY ordinal"
            )
        ]
        if unplaced:
            raise UnpackagedTask(
                "every task belongs to exactly one package; these tasks have none: "
                + ", ".join(unplaced)
                + ". Declare a package and assign them — there is no catch-all, because a "
                  "bucket nobody chose is a grouping nobody reviews.",
                tasks=unplaced,
            )

    # --- contracts:35 ---

    def finalize_plan(self, required_packages: list[int] | None = None) -> TaskGraph:
        """Derive the task graph and move the plan out of `draft`.

        This is the sole contract firing `state_machines:1`'s `finalize` event
        (`sm_cells:1`). Until it existed nothing wrote `finalized`, which left the
        revision loop unreachable and the drift baseline never captured
        (M5_PLAN.md 1.2).
        """
        self._guard_gates(required_packages)
        self._guard_findings()
        self._guard_packaging()

        specs = self._derive_nodes()
        edges = self._derive_edges(specs)
        order = self._toposort(specs, edges)

        ops: list[Op] = []
        unenumerated: list[str] = []
        stamp = now()
        for ref, title, content in specs:
            node = len(ops)
            ops.append(Op("insert", "subtasks", {
                "contract_ref": str(ref),
                "title": title,
                "task_id": self._owning_task_id(ref),
                "state": PENDING,
                "serve_epoch": 0,
                "created_at": stamp,
                "updated_at": stamp,
            }))
            # D12 — the obligation surface is frozen here, in the same transaction that
            # creates the sub-task, and before any split that will be measured against it.
            # Freezing later would let the party being audited pick its own denominator
            # (DEFECTS.md F23); freezing in a second batch would leave a window in which a
            # sub-task exists with no accounting at all.
            obligation_specs = (
                self.obligations.enumerate_from_row(content)
                if self.obligations is not None else []
            )
            if obligation_specs:
                ops.extend(self.obligations.freeze_ops(
                    str(ref), obligation_specs, FromOp(node, "id"), base_index=len(ops)
                ))
            else:
                unenumerated.append(str(ref))
        self.storage.write_atomic(ops, key("finalize", "nodes"))

        by_ref = {str(s.contract_ref): s.id for s in self._all()}
        dep_ops = [
            Op("insert", "subtask_deps", {
                "subtask_id": by_ref[consumer],
                "depends_on": by_ref[provider],
            })
            for consumer, provider in edges
        ]
        dep_ops.append(Op("update", "plan", {"state": "finalized"}, where={"guard": 1}))
        self.storage.write_atomic(dep_ops, key("finalize", "edges"))

        self._capture_fingerprint("finalization")

        subtasks = self._all()
        ordered = [by_ref[str(ref)] for ref in order]
        return TaskGraph(
            order=tuple(ordered),
            subtasks=tuple(subtasks),
            edge_count=len(edges),
            resurfaced_warnings=tuple(self._resurfaced_warnings()),
            unenumerated=tuple(unenumerated),
        )

    def _guard_gates(self, required_packages: list[int] | None) -> None:
        if self.gates is None or required_packages is None:
            return
        for package in required_packages:
            result = self.gates.run_gate(package)
            if not result.clean:
                raise GatesIncomplete(
                    f"package {package} gate has not passed; "
                    f"{len(result.holes)} outstanding",
                    package=package,
                )

    def _guard_findings(self) -> None:
        """requirements:32 — `findings.open_findings()` already implements exactly this
        rule. Wired, not reinvented."""
        if self.findings is None:
            return
        unresolved = self.findings.open_findings()
        if unresolved:
            raise UnresolvedFindings(
                "findings neither addressed nor explicitly accepted block finalization: "
                + ", ".join(f"findings:{f.id}" for f in unresolved),
                findings=[f.id for f in unresolved],
            )

    def _derive_nodes(self) -> list[tuple[RowRef, str, dict]]:
        """decisions:63 — one sub-task per live contract row.

        The row's content travels with the spec because finalization also freezes the
        obligation surface the session declared on it (D12).
        """
        rows = self.storage.query(
            "SELECT table_name, ordinal, content FROM plan_rows "
            "WHERE table_name = 'contracts' AND superseded_by IS NULL "
            "AND retired_at IS NULL ORDER BY ordinal"
        )
        specs = []
        for r in rows:
            content = json.loads(r["content"])
            ref = RowRef("contracts", r["ordinal"])
            title = content.get("title") or content.get("name") or str(ref)
            specs.append((ref, title, content))
        return specs

    def _owning_task_id(self, contract: RowRef) -> int | None:
        """The id of the task this contract belongs to, via its `belongs_to` link.

        DEFECTS.md F24: v1 carried this as `contracts.component_id`, a real foreign key.
        The package-6 flattening into generic `plan_rows`/`links` kept the rows and dropped
        the relation, leaving membership expressed only as markdown nesting in the exported
        plan. D13 restores it as a typed link, mirroring D11's treatment of `depends_on` —
        member -> owner, so the edge is owned by the row that knows it.

        Returns None when the contract declares no owner, or when the owning row has not
        been made a task (which requires a package — see `tasks.package_id NOT NULL`). That
        is reported, never guessed: choosing an owner or a package would be the tool
        exercising judgment (`decisions:12`).
        """
        found = self.storage.query(
            "SELECT t.id FROM links l JOIN tasks t ON t.source_ref = l.target_ref "
            "WHERE l.source_ref = ? AND l.edge_type = 'belongs_to' ORDER BY l.id LIMIT 1",
            (str(contract),),
        )
        return found[0]["id"] if found else None

    def _derive_edges(self, specs) -> list[tuple[str, str]]:
        """D11 — consumer -> provider, from `depends_on` links between contract rows only.

        Untyped links are traceability: a contract cites its requirements, decisions and
        findings with the same edge, and walking those as build dependencies would make
        every citation a dependency and fire CycleDetected on traceability loops that mean
        nothing.
        """
        known = {str(ref) for ref, _, _ in specs}
        return [
            (r["source_ref"], r["target_ref"])
            for r in self.storage.query(
                "SELECT source_ref, target_ref FROM links WHERE edge_type = ? ORDER BY id",
                (DEPENDS_ON,),
            )
            if r["source_ref"] in known and r["target_ref"] in known
        ]

    @staticmethod
    def _toposort(specs, edges) -> list[RowRef]:
        """requirements:34 — no sub-task precedes its dependencies. Kahn's algorithm,
        ties broken by ref so the order is deterministic across runs."""
        nodes = [ref for ref, _, _ in specs]
        incoming = {str(ref): set() for ref in nodes}
        outgoing = {str(ref): set() for ref in nodes}
        for consumer, provider in edges:
            incoming[consumer].add(provider)
            outgoing[provider].add(consumer)

        order, ready = [], sorted(
            (n for n in nodes if not incoming[str(n)]), key=str
        )
        while ready:
            node = ready.pop(0)
            order.append(node)
            for consumer in sorted(outgoing[str(node)]):
                incoming[consumer].discard(str(node))
                if not incoming[consumer]:
                    ready.append(RowRef.parse(consumer))
                    ready.sort(key=str)
        if len(order) != len(nodes):
            stuck = sorted(str(n) for n in nodes if str(n) not in {str(o) for o in order})
            raise CycleDetected(
                "the derived graph contains a dependency cycle; resolve it as a design "
                "conflict before implementation starts: " + ", ".join(stuck),
                nodes=stuck,
            )
        return order

    # --- readiness: DEFECTS.md F18's missing `deps_satisfied`, as D10's predicate ---

    def readiness_of(self, subtask: SubTask) -> str:
        """The presented state of a sub-task, with `ready` derived rather than stored.

        D10. A sub-task is `ready` exactly when its own state admits work and every
        dependency is `done`. Because this is evaluated on demand rather than fired once,
        a `rework_flagged` sub-task whose dependencies are all long since `done` becomes
        ready immediately — which under the edge-triggered reading it never could, its
        `deps_satisfied` edge having already fired for the last time (F19a).
        """
        if subtask.state not in (PENDING, REWORK_FLAGGED):
            return subtask.state
        return READY if self._deps_satisfied(subtask) else subtask.state

    def _deps_satisfied(self, subtask: SubTask) -> bool:
        if not subtask.deps:
            return True
        states = {
            r["id"]: r["state"]
            for r in self.storage.query(
                "SELECT id, state FROM subtasks WHERE id IN ("
                + ",".join("?" * len(subtask.deps)) + ")",
                tuple(subtask.deps),
            )
        }
        return all(states.get(d) == DONE for d in subtask.deps)

    def blocking_deps(self, subtask: SubTask) -> tuple[int, ...]:
        """uc_extensions:34 — name the blocking dependencies rather than serve
        unbuildable work."""
        if not subtask.deps:
            return ()
        states = {
            r["id"]: r["state"]
            for r in self.storage.query(
                "SELECT id, state FROM subtasks WHERE id IN ("
                + ",".join("?" * len(subtask.deps)) + ")",
                tuple(subtask.deps),
            )
        }
        return tuple(d for d in subtask.deps if states.get(d) != DONE)

    # --- contracts:38 ---

    def graph_status(self) -> GraphStatus:
        """Computed on read, never cached — the same D10 reasoning. A stored readiness
        flag would be a second source of truth for a fact the dependency states already
        determine, and the two would drift exactly when the graph is revised."""
        buckets: dict[str, list[int]] = {
            DONE: [], IN_PROGRESS: [], BLOCKED: [], READY: [],
            PENDING: [], REWORK_FLAGGED: [],
        }
        stale = []
        for subtask in self._all():
            buckets[self.readiness_of(subtask)].append(subtask.id)
            if subtask.state == IN_PROGRESS and age_seconds(subtask.updated_at) > STALENESS_SECONDS:
                stale.append(subtask.id)
        return GraphStatus(
            built=tuple(buckets[DONE]),
            in_flight=tuple(buckets[IN_PROGRESS]),
            blocked=tuple(buckets[BLOCKED]),
            ready=tuple(buckets[READY]),
            pending=tuple(buckets[PENDING]),
            rework=tuple(buckets[REWORK_FLAGGED]),
            stale=tuple(stale),
        )

    # --- contracts:55 ---

    def next_subtask(
        self, allow_draft: bool = False, consent: str = ""
    ) -> SubTaskCandidates | AllBlockedReport:
        """The ready sub-task plus its candidate closure — *not* a composed brief.

        findings:3: the closure goes to the planning session's LLM, which makes the
        BriefSelection; `compose_brief` is the separate second call. This contract has no
        LLM and must not pick.

        Note it does **not** fire `serve_brief`. A candidate may be offered and never
        briefed, and marking it in-progress here would put sub-tasks into `in_progress`
        that nobody is working on. `serve_brief` fires at handover — see `serve_brief`.
        """
        if not self.is_finalized():
            if not allow_draft:
                raise PlanNotFinalized(
                    "the plan is not finalized; pass allow_draft with recorded owner "
                    "consent to serve a watermarked draft brief (requirements:40)"
                )
            if not consent.strip():
                raise PlanNotFinalized(
                    "allow_draft requires recorded owner consent (requirements:40)"
                )
            if not self._all():
                raise PlanNotFinalized(
                    "there is no task graph to serve from: sub-tasks are derived at "
                    "finalization (crud_grid:33), so a plan that has never been "
                    "finalized has no sub-tasks for allow_draft to serve. See "
                    "DEFECTS.md F21 — allow_draft is only reachable for a plan that "
                    "left `finalized` afterwards, such as one under revision."
                )

        candidates = [s for s in self._all() if self.readiness_of(s) == READY]
        if not candidates:
            unfinished = [
                s for s in self._all()
                if self.readiness_of(s) in (PENDING, BLOCKED, REWORK_FLAGGED)
            ]
            return AllBlockedReport(
                blocking={s.id: self.blocking_deps(s) for s in unfinished}
            )

        chosen = candidates[0]
        return SubTaskCandidates(
            subtask=chosen,
            closure=self.closure_for(chosen),
            is_draft=not self.is_finalized(),
        )

    def closure_for(self, subtask: SubTask) -> tuple[RowRef, ...]:
        """requirements:36 — every row reachable from the sub-task's contract."""
        if self.graph is None:
            return (subtask.contract_ref,)
        from engine.models import TraversalSpec

        closure = self.graph.closure(
            [subtask.contract_ref], TraversalSpec(direction="out")
        )
        return closure.reached

    # --- DEFECTS.md F18's missing `serve_brief` ---

    def serve_brief(self, subtask_id: int) -> SubTask:
        """Fire `serve_brief` (sm_cells:137) at the moment a brief is handed over.

        Separate from `next_subtask` because candidacy is not delivery: a sub-task may be
        offered, considered and left alone. The transition belongs at handover, which is
        also what makes `serve_epoch` mean something — it counts deliveries, and a
        verification verdict is scoped to the epoch it was earned under (F19b).

        On task-graph rather than reachable from `report_status` because serving is the
        system's act, not the engine's claim (crud_grid:35).
        """
        subtask = self.get(subtask_id)
        self.guard_live(subtask)
        presented = self.readiness_of(subtask)
        self._check_transition(presented, "serve_brief", subtask)
        stamp = now()
        self.storage.write_atomic([
            Op("update", "subtasks",
               {"state": IN_PROGRESS,
                "serve_epoch": subtask.serve_epoch + 1,
                "updated_at": stamp},
               where={"id": subtask_id}),
        ], key("serve", subtask_id, subtask.serve_epoch + 1))
        self._capture_fingerprint("brief_issue", subtask_id=subtask_id)
        return self.get(subtask_id)

    # --- contracts:62 ---

    def verify_completion(
        self, subtask_id: int, evidence: dict[str, str]
    ) -> VerificationVerdict:
        """Check delivered evidence against every contract in the sub-task's scope.

        A pass is the sole enabler of `in_progress -> done`. The state precondition is a
        deviation from contracts:62, which declares none — without it a pass can be banked
        against a `pending` sub-task and satisfy contracts:60's guard later, verifying work
        that was never served (F19b). The verdict is additionally stamped with the current
        `serve_epoch`, so a pass earned before a rework cannot certify the rework.
        """
        subtask = self.get(subtask_id)
        self.guard_live(subtask)
        if subtask.state != IN_PROGRESS:
            raise NotInProgress(
                f"sub-task {subtask_id} is {subtask.state}; evidence can only be verified "
                "for work that has actually been served",
                subtask_id=subtask_id,
                state=subtask.state,
            )

        scope = self._scope_obligations(subtask)
        unaccounted = tuple(sorted(o for o in scope if not evidence.get(o)))
        verdict = "fail" if unaccounted else "pass"

        self.storage.write_atomic([
            Op("insert", "subtask_verifications", {
                "subtask_id": subtask_id,
                "serve_epoch": subtask.serve_epoch,
                "verdict": verdict,
                "evidence": json.dumps(evidence, sort_keys=True),
                "unaccounted": json.dumps(list(unaccounted)) if unaccounted else None,
                "created_at": now(),
            }),
        ], key("verify", subtask_id, subtask.serve_epoch))

        if unaccounted:
            raise EvidenceIncomplete(
                "verification refused; no evidence for: " + ", ".join(unaccounted),
                subtask_id=subtask_id,
                unaccounted=list(unaccounted),
            )
        return VerificationVerdict(
            subtask_id=subtask_id,
            serve_epoch=subtask.serve_epoch,
            verdict=verdict,
            evidence=dict(evidence),
        )

    def _scope_obligations(self, subtask: SubTask) -> tuple[str, ...]:
        """What this sub-task must produce evidence for: the obligations it owns (D12).

        This replaces M5a's placeholder, which returned the sub-task's single contract ref.
        The placeholder was correct for an unsplit graph and wrong the moment `split_subtask`
        existed: a split's sub-tasks all carry the *same* contract ref, so evidence for one
        sub-task's slice would discharge the parent's whole contract. `contracts:62`'s "each
        contract in the sub-task's scope" is read as each *obligation* in it, which is the
        only reading under which a sub-task cannot claim its siblings' work.

        A sub-task with no enumerated surface raises rather than returning an empty scope.
        An empty denominator makes `all(...)` true and reports a pass over nothing — F23
        exactly, and the one outcome this whole surface exists to prevent.
        """
        return tuple(
            o.ref for o in self.obligations.require_enumerated(subtask.id, "evidence")
        )

    def passing_verdict(self, subtask: SubTask) -> VerificationVerdict | None:
        """The passing verdict for the *current* serving episode, if any."""
        found = self.storage.query(
            "SELECT * FROM subtask_verifications WHERE subtask_id = ? AND serve_epoch = ? "
            "AND verdict = 'pass' ORDER BY id DESC LIMIT 1",
            (subtask.id, subtask.serve_epoch),
        )
        if not found:
            return None
        r = found[0]
        return VerificationVerdict(
            subtask_id=r["subtask_id"],
            serve_epoch=r["serve_epoch"],
            verdict=r["verdict"],
            evidence=json.loads(r["evidence"]),
        )

    # --- contracts:60 ---

    def report_status(
        self, subtask_id: int, status: str, detail: str = ""
    ) -> SubTask:
        """The code engine's half of crud_grid:35: what it observed, not what it is owed.

        `detail` is explicitly NOT completion evidence — contracts:60 demotes it to notes
        and gates `done` on a passing `verify_completion` verdict instead, which is
        findings:9's fix. Accepting a free string as proof is what made 'done' mean 'the
        engine said so'.
        """
        if status not in ENGINE_EVENTS:
            raise MalformedReport(
                f"'{status}' is not a status a code engine reports; expected one of "
                + ", ".join(ENGINE_EVENTS)
                + (". Readiness and brief service are the system's to determine "
                   "(crud_grid:35), not the engine's to assert."
                   if status in ("deps_satisfied", "serve_brief") else ""),
                status=status,
            )
        if status == "block" and not detail.strip():
            raise MalformedReport(
                "a block report must say what is blocking; sub-task state unchanged",
                status=status,
            )

        subtask = self.get(subtask_id)
        self.guard_live(subtask)
        presented = self.readiness_of(subtask)
        target = self._check_transition(presented, status, subtask)

        if status == "complete" and self.passing_verdict(subtask) is None:
            raise VerificationMissing(
                f"sub-task {subtask_id} reported done without a passing verify_completion "
                f"verdict for serving episode {subtask.serve_epoch}; transition refused, "
                "state unchanged",
                subtask_id=subtask_id,
                serve_epoch=subtask.serve_epoch,
            )

        values = {"state": target, "updated_at": now()}
        if detail:
            values["detail"] = detail
        values["block_reason"] = detail if status == "block" else None
        self.storage.write_atomic(
            [Op("update", "subtasks", values, where={"id": subtask_id})],
            key("report", subtask_id, status, subtask.state),
        )
        return self.get(subtask_id)

    def guard_live(self, subtask: SubTask) -> None:
        """A superseded node is out of the build entirely (DEFECTS.md F25)."""
        if not subtask.is_live:
            raise SubTaskSuperseded(
                f"sub-task {subtask.id} was split and superseded by sub-task "
                f"{subtask.superseded_by}; its obligations are owned by the sub-tasks that "
                "replaced it",
                subtask_id=subtask.id,
                superseded_by=subtask.superseded_by,
            )

    def _check_transition(self, presented: str, event: str, subtask: SubTask) -> str:
        target = _TRANSITIONS.get((presented, event))
        if target is None:
            raise InvalidTransition(
                f"cannot {event} a sub-task that is {presented}: "
                f"{_IMPOSSIBLE.get((presented, event), 'not a legal transition')}; "
                "state unchanged",
                subtask_id=subtask.id,
                state=presented,
                event=event,
            )
        return target

    # --- requirements:73 ---

    def _capture_fingerprint(
        self, occasion: str, subtask_id: int | None = None
    ) -> None:
        """The drift baseline. Captured at finalization and at each brief issue, which is
        what makes plan_status's drift flags computable at all — before this contract
        existed nothing ever wrote one (M5_PLAN.md 1.2)."""
        stamp = now()
        handle = self.storage.plan_handle()
        fingerprint = {
            "workspace": str(self.storage.workspace),
            "plan_version": handle.get("version"),
            "schema_version": handle.get("schema_version"),
        }
        self.storage.write_atomic([
            Op("insert", "workspace_fingerprints", {
                "occasion": occasion,
                "plan_version": handle.get("version") or 1,
                "subtask_id": subtask_id,
                "fingerprint": json.dumps(fingerprint, sort_keys=True),
                "created_at": stamp,
            }),
        ], key("fingerprint", occasion, subtask_id, handle.get("version") or 1))

    def _resurfaced_warnings(self) -> list[str]:
        """requirements:23 — finalization is a critical point, so suppressed warnings
        come back rather than staying quiet."""
        return [
            r["message"]
            for r in self.storage.query(
                "SELECT message FROM warnings WHERE state IN ('active','suppressed') "
                "ORDER BY id"
            )
        ]

    # --- reads ---

    def get(self, subtask_id: int) -> SubTask:
        found = self.storage.query("SELECT * FROM subtasks WHERE id = ?", (subtask_id,))
        if not found:
            raise SubTaskNotFound("no such sub-task", subtask_id=subtask_id)
        return self._hydrate(found[0])

    def _all(self, include_superseded: bool = False) -> list[SubTask]:
        """The live graph. DEFECTS.md F25: `contracts:40` returns sub-tasks "superseding the
        original in the graph" and never says what that does to the node, so M5a had no
        liveness filter here at all. A split original left in the graph stays `in_progress`
        forever, trips the 24h staleness flag, and can be served again by `next_subtask`.

        Superseded nodes are still readable through `get`, because the brief they drove is
        retained for forensics (`entities:13`) and a lineage you cannot read is not a
        lineage.
        """
        sql = "SELECT * FROM subtasks {} ORDER BY id".format(
            "" if include_superseded else "WHERE superseded_by IS NULL"
        )
        return [self._hydrate(r) for r in self.storage.query(sql)]

    def _hydrate(self, r) -> SubTask:
        deps = tuple(
            row["depends_on"]
            for row in self.storage.query(
                "SELECT depends_on FROM subtask_deps WHERE subtask_id = ? "
                "ORDER BY depends_on",
                (r["id"],),
            )
        )
        return SubTask(
            id=r["id"],
            contract_ref=RowRef.parse(r["contract_ref"]),
            title=r["title"],
            task_id=r["task_id"],
            state=r["state"],
            serve_epoch=r["serve_epoch"],
            deps=deps,
            detail=r["detail"],
            block_reason=r["block_reason"],
            superseded_by=r["superseded_by"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )

    def is_finalized(self) -> bool:
        return self.storage.plan_handle().get("state") == "finalized"

