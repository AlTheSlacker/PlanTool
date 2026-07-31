"""task-graph (components:11).

Derives the dependency-ordered implementation task graph at finalization and maintains
build-state truth: readiness, engine status reports, staleness flags, and draft-serving
policy.

Contracts: contracts:35 finalize_plan, contracts:38 graph_status, contracts:55
next_task, contracts:60 report_status, contracts:62 verify_completion.

**A task is what a builder is handed** — one externally-callable function plus the private
helpers serving only it (v3 D5), derived one per live contract row. The level above it, the
declared build grouping, is gone with D7, and so is the level below: there is nothing to
split a task into, because it is already the unit of work.

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
  therefore never written to `tasks.state`; it is computed from dependency state every
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
from engine.fingerprint import capture as fingerprint_capture
from engine.models import RowRef
from engine.behaviours import BehaviourService
from engine.clock import now
from engine.idempotency import key
from engine.storage import FromOp, Op, Storage

# --- state_machines:9, the Task lifecycle ---

PENDING = "pending"
READY = "ready"
IN_PROGRESS = "in_progress"
BLOCKED = "blocked"
DONE = "done"
REWORK_FLAGGED = "rework_flagged"

#: The states actually written to `tasks.state`. `ready` is absent by design (D10):
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

#: D11 — the typed edge task-graph derivation reads. Untyped links are traceability.
DEPENDS_ON = "depends_on"


class GatesIncomplete(PlanToolError):
    """contracts:35 — the terminal stage gate has not passed; names it."""


class CycleDetected(PlanToolError):
    """contracts:35 — the derived graph contains a dependency cycle, surfaced as a design
    conflict before implementation starts (requirements:35)."""


class UnresolvedFindings(PlanToolError):
    """contracts:35 — findings neither addressed nor explicitly accepted block
    finalization (requirements:32)."""


class PlanNotFinalized(PlanToolError):
    """contracts:55 — refused unless allow_draft with recorded owner consent."""


class TaskNotFound(PlanToolError):
    """contracts:60/62 — names the missing id."""


class InvalidTransition(PlanToolError):
    """contracts:60 — not a legal transition in state_machines:9; state unchanged."""


class VerificationMissing(PlanToolError):
    """contracts:60 — status 'done' reported without a passing verify_completion verdict
    for the task; transition refused, state unchanged."""


class MalformedReport(PlanToolError):
    """contracts:60 — report fails validation; rejected naming the specific problem;
    task state unchanged, engine resubmits (dep_failure_modes:8)."""


class EvidenceIncomplete(PlanToolError):
    """contracts:62 — a contract in the task's scope has no mapped evidence item;
    verification refused naming the unaccounted contracts, state unchanged."""


class NotInProgress(PlanToolError):
    """Not in the frozen plan. contracts:62 declares no state precondition, so a passing
    verdict could be banked against a `pending` task and later satisfy contracts:60's
    guard — verification of work that was never served. DEFECTS.md F19(b)."""


@dataclass(frozen=True, slots=True)
class Task:
    """One node of the implementation graph: what a builder is handed.

    No owning group and no supersession pointer. The group went with D7, and the pointer
    with splitting — a task is one contract, so there is nothing to divide it into and
    nothing that can replace it in the graph.
    """

    id: int
    contract_ref: RowRef
    title: str
    state: str
    serve_epoch: int
    deps: tuple[int, ...] = ()
    detail: str | None = None
    block_reason: str | None = None
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True, slots=True)
class GraphStatus:
    """contracts:38 — built, in-flight, blocked and ready tasks, so any fresh session
    resumes the build exactly.

    `dep_failure_modes:6` also asked for a `stale` list — in-flight tasks nobody had
    touched for a day. Removed 2026-07-22: it judged abandonment from elapsed time, which
    is a guess, and `in_flight` already names every task it would have drawn from. The
    planner is better placed than the tool to say which of those they have walked away
    from.
    """

    built: tuple[int, ...]
    in_flight: tuple[int, ...]
    blocked: tuple[int, ...]
    ready: tuple[int, ...]
    pending: tuple[int, ...]
    rework: tuple[int, ...]

    @property
    def complete(self) -> bool:
        return not (self.in_flight or self.blocked or self.ready
                    or self.pending or self.rework)


@dataclass(frozen=True, slots=True)
class TaskGraph:
    """contracts:35 — ordered so no task precedes its dependencies (requirements:34)."""

    order: tuple[int, ...]
    tasks: tuple[Task, ...]
    edge_count: int
    #: requirements:23 — finalization is a critical point, so suppressed warnings
    #: resurface here rather than staying quiet.
    resurfaced_warnings: tuple[str, ...] = ()
    #: Contracts whose behaviour surface the planning session never declared (D12).
    #: Reported rather than invented: the tool will not guess a denominator. These
    #: tasks cannot be verified until the enumeration exists, and saying so at
    #: finalization is the loud failure F23's silent one has to become.
    unenumerated: tuple[RowRef, ...] = ()

    @property
    def all_roots(self) -> bool:
        """No dependency edges at all. Legitimate on a plan that declares none, but
        worth surfacing rather than assuming — see DEVIATIONS.md D11's accepted cost."""
        return self.edge_count == 0 and len(self.tasks) > 1


@dataclass(frozen=True, slots=True)
class VerificationVerdict:
    """contracts:62 — recorded durably with the evidence."""

    task_id: int
    serve_epoch: int
    verdict: str
    evidence: dict[str, str]
    unaccounted: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return self.verdict == "pass"


@dataclass(frozen=True, slots=True)
class TaskCandidates:
    """contracts:55 — the ready task plus its full candidate closure, for the planning
    session's LLM to make the BriefSelection from. Composing the brief is a separate
    second call (findings:3)."""

    task: Task
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
        behaviours=None,
    ):
        self.storage = storage
        self.rows = rows
        self.graph = graph
        self.gates = gates
        self.findings = findings
        self.behaviours = behaviours or BehaviourService(storage)

    # The build grouping stood here until v3 change 1: `declare_package`, `assign_task`
    # and `packaging`, with their models, their two errors and the finalization refusal
    # that made membership mandatory. D7 removed the level, so the calls that declare,
    # assign and show it are gone rather than left with nothing to address.

    # --- contracts:35 ---

    def finalize_plan(self) -> TaskGraph:
        """Derive the task graph and move the plan out of `draft`.

        This is the sole contract firing `state_machines:1`'s `finalize` event
        (`sm_cells:1`). Until it existed nothing wrote `finalized`, which left the
        revision loop unreachable and the drift baseline never captured
        (M5_PLAN.md 1.2).

        It no longer refuses a plan whose tasks are in no group; that refusal died with
        the level in v3 change 1, and with it the `required_packages` parameter that told
        the guard which gates to insist on.

        **Two transactions, deliberately**, overriding the register's one-per-call
        default: the nodes must exist before the edges can reference them by id, and the
        plan-state flip rides with the edges so that a plan is never `finalized` with no
        graph behind it. Everything that can refuse has refused before the first write.
        """
        self._guard_gates()
        self._guard_findings()

        specs = self._derive_nodes()
        edges = self._derive_edges(specs)
        order = self._toposort(specs, edges)

        ops: list[Op] = []
        unenumerated: list[RowRef] = []
        stamp = now()
        for ref, title, content in specs:
            node = len(ops)
            ops.append(Op("insert", "tasks", {
                "contract_ref": str(ref),
                "title": title,
                "state": PENDING,
                "serve_epoch": 0,
                "created_at": stamp,
                "updated_at": stamp,
            }))
            # D12 — the behaviour surface is frozen here, in the same transaction that
            # creates the task, and before anything is measured against it. Freezing later
            # would let the party being audited pick its own denominator (DEFECTS.md F23);
            # freezing in a second batch would leave a window in which a task exists with no
            # accounting at all.
            behaviour_specs = (
                self.behaviours.enumerate_from_row(content)
                if self.behaviours is not None else []
            )
            if behaviour_specs:
                ops.extend(self.behaviours.freeze_ops(
                    str(ref), behaviour_specs, FromOp(node, "id"), base_index=len(ops)
                ))
            else:
                unenumerated.append(ref)
        self.storage.write_atomic(ops, key("finalize", "nodes"))

        by_ref = {str(s.contract_ref): s.id for s in self._all()}
        dep_ops = [
            Op("insert", "task_deps", {
                "task_id": by_ref[consumer],
                "depends_on": by_ref[provider],
            })
            for consumer, provider in edges
        ]
        dep_ops.append(Op("update", "plan", {"state": "finalized"}, where={"guard": 1}))
        self.storage.write_atomic(dep_ops, key("finalize", "edges"))

        self._capture_fingerprint("finalization")

        tasks = self._all()
        ordered = [by_ref[str(ref)] for ref in order]
        return TaskGraph(
            order=tuple(ordered),
            tasks=tuple(tasks),
            edge_count=len(edges),
            resurfaced_warnings=tuple(self._resurfaced_warnings()),
            unenumerated=tuple(unenumerated),
        )

    def _guard_gates(self) -> None:
        """Finalization requires the terminal stage gate, and nothing else.

        Which gates must have passed used to be the caller's list, and passing none — the
        default — checked **zero**. With the build grouping gone there is no list to pass,
        and the honest replacement is the gate that already folds in every earlier one:
        `gate_criteria.yaml` gives the terminal stage a `prior_gates_green` criterion, and
        `_c_prior_gates_green` re-runs every earlier stage's *criteria* rather than calling
        `run_gate`. Requiring the terminal gate therefore requires all of them, through the
        mechanism that already exists, with one stage number in the error instead of eight.

        Requiring the whole list here instead would re-implement `prior_gates_green` in
        this module and give two answers to "did the plan pass its gates".
        """
        if self.gates is None:
            return
        terminal = self.gates.methodology.stage_range[1]
        result = self.gates.run_gate(terminal)
        if not result.clean:
            raise GatesIncomplete(
                f"stage {terminal}'s gate has not passed; "
                f"{len(result.holes)} outstanding. It folds in every earlier stage gate, "
                "so this is the one that says the plan is ready to freeze",
                stage=terminal,
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
        """decisions:63 — one task per live contract row.

        The row's content travels with the spec because finalization also freezes the
        behaviour surface the session declared on it (D12).
        """
        rows = self.storage.query(
            "SELECT table_name, ordinal, name, content FROM plan_rows "
            "WHERE table_name = 'contracts' AND superseded_by IS NULL "
            "AND retired_at IS NULL ORDER BY ordinal"
        )
        specs = []
        for r in rows:
            content = json.loads(r["content"])
            ref = RowRef("contracts", r["ordinal"])
            specs.append((ref, r["name"], content))
        return specs

    # `_owning_task_id` stood here, resolving a contract's `belongs_to` link to the middle
    # level's owning row. Both ends of that lookup are gone: the level, and the column it
    # filled. A `belongs_to` link between plan rows is still a link like any other and is
    # still traversed by the closure — what it no longer does is decide a build grouping.

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
        """requirements:34 — no task precedes its dependencies. Kahn's algorithm,
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

    def readiness_of(self, task: Task) -> str:
        """The presented state of a task, with `ready` derived rather than stored.

        D10. A task is `ready` exactly when its own state admits work and every
        dependency is `done`. Because this is evaluated on demand rather than fired once,
        a `rework_flagged` task whose dependencies are all long since `done` becomes
        ready immediately — which under the edge-triggered reading it never could, its
        `deps_satisfied` edge having already fired for the last time (F19a).
        """
        if task.state not in (PENDING, REWORK_FLAGGED):
            return task.state
        return READY if self._deps_satisfied(task) else task.state

    def _deps_satisfied(self, task: Task) -> bool:
        if not task.deps:
            return True
        states = {
            r["id"]: r["state"]
            for r in self.storage.query(
                "SELECT id, state FROM tasks WHERE id IN ("
                + ",".join("?" * len(task.deps)) + ")",
                tuple(task.deps),
            )
        }
        return all(states.get(d) == DONE for d in task.deps)

    def blocking_deps(self, task: Task) -> tuple[int, ...]:
        """uc_extensions:34 — name the blocking dependencies rather than serve
        unbuildable work."""
        if not task.deps:
            return ()
        states = {
            r["id"]: r["state"]
            for r in self.storage.query(
                "SELECT id, state FROM tasks WHERE id IN ("
                + ",".join("?" * len(task.deps)) + ")",
                tuple(task.deps),
            )
        }
        return tuple(d for d in task.deps if states.get(d) != DONE)

    # --- contracts:38 ---

    def graph_status(self) -> GraphStatus:
        """Computed on read, never cached — the same D10 reasoning. A stored readiness
        flag would be a second source of truth for a fact the dependency states already
        determine, and the two would drift exactly when the graph is revised."""
        buckets: dict[str, list[int]] = {
            DONE: [], IN_PROGRESS: [], BLOCKED: [], READY: [],
            PENDING: [], REWORK_FLAGGED: [],
        }
        for task in self._all():
            buckets[self.readiness_of(task)].append(task.id)
        return GraphStatus(
            built=tuple(buckets[DONE]),
            in_flight=tuple(buckets[IN_PROGRESS]),
            blocked=tuple(buckets[BLOCKED]),
            ready=tuple(buckets[READY]),
            pending=tuple(buckets[PENDING]),
            rework=tuple(buckets[REWORK_FLAGGED]),
        )

    # --- contracts:55 ---

    def next_task(
        self, allow_draft: bool = False, consent: str = ""
    ) -> TaskCandidates | AllBlockedReport:
        """The ready task plus its candidate closure — *not* a composed brief.

        findings:3: the closure goes to the planning session's LLM, which makes the
        BriefSelection; `compose_brief` is the separate second call. This contract has no
        LLM and must not pick.

        Note it does **not** fire `serve_brief`. A candidate may be offered and never
        briefed, and marking it in-progress here would put tasks into `in_progress`
        that nobody is working on. `serve_brief` fires at handover — see `serve_brief`.
        """
        state = self.storage.plan_handle()["state"]
        finalized = state == "finalized"
        revising = state == "revising"

        if not finalized and not revising:
            # A draft plan — one that never finalized — has no task graph at all, because
            # tasks are derived at finalization (crud_grid:33). The allow_draft escape
            # hatch is genuinely unreachable here, so it fails with the real reason rather
            # than an empty result (F21, resolved: the flag's only live meaning is below).
            if not allow_draft:
                raise PlanNotFinalized(
                    "the plan is not finalized; pass allow_draft with recorded owner "
                    "consent to serve a watermarked draft brief (requirements:40)"
                )
            if not consent.strip():
                raise PlanNotFinalized(
                    "allow_draft requires recorded owner consent (requirements:40)"
                )
            raise PlanNotFinalized(
                "there is no task graph to serve from: tasks are derived at "
                "finalization (crud_grid:33), so a plan that has never been finalized has "
                "no tasks. allow_draft is reachable only for a plan that left "
                "`finalized`, i.e. one under revision — where it serves an affected "
                "task, watermarked, past the freeze."
            )

        # F21 / decisions:62 — the affected-only freeze. While a revision is open the plan
        # sits in `revising`; tasks whose contract the revision touches are frozen, and
        # every other task keeps flowing. allow_draft + recorded consent is the override
        # that serves a frozen task anyway, watermarked as a draft of the coming change —
        # the one reading under which the flag is reachable, and what F21 was waiting for.
        frozen = self._revision_frozen_refs() if revising else frozenset()
        serve_frozen = bool(allow_draft and consent.strip())

        ready = [s for s in self._all() if self.readiness_of(s) == READY]
        if revising and not serve_frozen:
            candidates = [s for s in ready if str(s.contract_ref) not in frozen]
        else:
            candidates = ready

        if not candidates:
            unfinished = [
                s for s in self._all()
                if self.readiness_of(s) in (PENDING, BLOCKED, REWORK_FLAGGED)
            ]
            return AllBlockedReport(
                blocking={s.id: self.blocking_deps(s) for s in unfinished}
            )

        chosen = candidates[0]
        return TaskCandidates(
            task=chosen,
            closure=self.closure_for(chosen),
            is_draft=revising and str(chosen.contract_ref) in frozen,
        )

    def _revision_frozen_refs(self) -> frozenset[str]:
        """The plan-row refs an open revision has frozen — its repercussion targets and
        affected rows (F21 / decisions:62).

        Read straight from the revision store rather than passed in, so what the freeze
        checks and what the revision service enumerated cannot drift apart. Empty when no
        revision is open.
        """
        rows = self.storage.query(
            "SELECT r.row_ref FROM repercussions r JOIN revisions v "
            "ON r.revision_id = v.id "
            "WHERE v.state = 'walkthrough' AND r.row_ref IS NOT NULL"
        )
        return frozenset(row["row_ref"] for row in rows)

    def closure_for(self, task: Task) -> tuple[RowRef, ...]:
        """requirements:36 — every row reachable from the task's contract."""
        if self.graph is None:
            return (task.contract_ref,)
        from engine.models import TraversalSpec

        closure = self.graph.closure(
            [task.contract_ref], TraversalSpec(direction="out")
        )
        return closure.reached

    # --- DEFECTS.md F18's missing `serve_brief` ---

    def serve_brief(self, task_id: int) -> Task:
        """Fire `serve_brief` (sm_cells:137) at the moment a brief is handed over.

        Separate from `next_task` because candidacy is not delivery: a task may be
        offered, considered and left alone. The transition belongs at handover, which is
        also what makes `serve_epoch` mean something — it counts deliveries, and a
        verification verdict is scoped to the epoch it was earned under (F19b).

        On task-graph rather than reachable from `report_status` because serving is the
        system's act, not the engine's claim (crud_grid:35).
        """
        task = self.get(task_id)
        presented = self.readiness_of(task)
        self._check_transition(presented, "serve_brief", task)
        stamp = now()
        self.storage.write_atomic([
            Op("update", "tasks",
               {"state": IN_PROGRESS,
                "serve_epoch": task.serve_epoch + 1,
                "updated_at": stamp},
               where={"id": task_id}),
        ], key("serve", task_id, task.serve_epoch + 1))
        self._capture_fingerprint("brief_issue", task_id=task_id)
        return self.get(task_id)

    # --- contracts:62 ---

    def verify_completion(
        self, task_id: int, evidence: dict[str, str]
    ) -> VerificationVerdict:
        """Check delivered evidence against every contract in the task's scope.

        A pass is the sole enabler of `in_progress -> done`. The state precondition is a
        deviation from contracts:62, which declares none — without it a pass can be banked
        against a `pending` task and satisfy contracts:60's guard later, verifying work
        that was never served (F19b). The verdict is additionally stamped with the current
        `serve_epoch`, so a pass earned before a rework cannot certify the rework.
        """
        task = self.get(task_id)
        if task.state != IN_PROGRESS:
            raise NotInProgress(
                f"task {task_id} is {task.state}; evidence can only be verified "
                "for work that has actually been served",
                task_id=task_id,
                state=task.state,
            )

        scope = self._scope_behaviours(task)
        unaccounted = tuple(sorted(o for o in scope if not evidence.get(o)))
        verdict = "fail" if unaccounted else "pass"

        self.storage.write_atomic([
            Op("insert", "task_verifications", {
                "task_id": task_id,
                "serve_epoch": task.serve_epoch,
                "verdict": verdict,
                "evidence": json.dumps(evidence, sort_keys=True),
                "unaccounted": json.dumps(list(unaccounted)) if unaccounted else None,
                "created_at": now(),
            }),
        ], key("verify", task_id, task.serve_epoch))

        if unaccounted:
            raise EvidenceIncomplete(
                "verification refused; no evidence for: " + ", ".join(unaccounted),
                task_id=task_id,
                unaccounted=list(unaccounted),
            )
        return VerificationVerdict(
            task_id=task_id,
            serve_epoch=task.serve_epoch,
            verdict=verdict,
            evidence=dict(evidence),
        )

    def _scope_behaviours(self, task: Task) -> tuple[str, ...]:
        """What this task must produce evidence for: the behaviours it owns (D12).

        `contracts:62`'s "each contract in the task's scope" is read as each *behaviour* in
        it, and the reading survives the level surgery: it is what makes evidence a
        per-commitment account rather than one artifact standing in for a whole contract.

        A task with no enumerated surface raises rather than returning an empty scope.
        An empty denominator makes `all(...)` true and reports a pass over nothing — F23
        exactly, and the one outcome this whole surface exists to prevent.
        """
        return tuple(
            b.ref for b in self.behaviours.require_enumerated(task.id, "evidence")
        )

    def passing_verdict(self, task: Task) -> VerificationVerdict | None:
        """The passing verdict for the *current* serving episode, if any."""
        found = self.storage.query(
            "SELECT * FROM task_verifications WHERE task_id = ? AND serve_epoch = ? "
            "AND verdict = 'pass' ORDER BY id DESC LIMIT 1",
            (task.id, task.serve_epoch),
        )
        if not found:
            return None
        r = found[0]
        return VerificationVerdict(
            task_id=r["task_id"],
            serve_epoch=r["serve_epoch"],
            verdict=r["verdict"],
            evidence=json.loads(r["evidence"]),
        )

    # --- contracts:60 ---

    def report_status(
        self, task_id: int, status: str, detail: str = ""
    ) -> Task:
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
                "a block report must say what is blocking; task state unchanged",
                status=status,
            )

        task = self.get(task_id)
        presented = self.readiness_of(task)
        target = self._check_transition(presented, status, task)

        if status == "complete" and self.passing_verdict(task) is None:
            raise VerificationMissing(
                f"task {task_id} reported done without a passing verify_completion "
                f"verdict for serving episode {task.serve_epoch}; transition refused, "
                "state unchanged",
                task_id=task_id,
                serve_epoch=task.serve_epoch,
            )

        values = {"state": target, "updated_at": now()}
        if detail:
            values["detail"] = detail
        values["block_reason"] = detail if status == "block" else None
        self.storage.write_atomic(
            [Op("update", "tasks", values, where={"id": task_id})],
            key("report", task_id, status, task.state),
        )
        return self.get(task_id)

    # `guard_live` stood here, refusing to serve, report on or verify a node a split had
    # superseded (DEFECTS.md F25). Nothing can supersede a task now that splitting is gone,
    # so the guard could never fire, and a check that cannot fire is the disease this change
    # is about. Its three call sites lose a branch each.

    def _check_transition(self, presented: str, event: str, task: Task) -> str:
        target = _TRANSITIONS.get((presented, event))
        if target is None:
            raise InvalidTransition(
                f"cannot {event} a task that is {presented}: "
                f"{_IMPOSSIBLE.get((presented, event), 'not a legal transition')}; "
                "state unchanged",
                task_id=task.id,
                state=presented,
                event=event,
            )
        return target

    # --- requirements:73 ---

    def _capture_fingerprint(
        self, occasion: str, task_id: int | None = None
    ) -> None:
        """The drift baseline. Captured at finalization and at each brief issue, which is
        what makes plan_status's drift flags computable at all — before this contract
        existed nothing ever wrote one (M5_PLAN.md 1.2).

        What goes *in* the fingerprint lives in `engine/fingerprint.py`, which also owns the
        comparison. Keeping the field list here would put capture and comparison in two files
        with nothing binding them to the same fields."""
        stamp = now()
        handle = self.storage.plan_handle()
        fingerprint = fingerprint_capture(self.storage)
        self.storage.write_atomic([
            Op("insert", "workspace_fingerprints", {
                "occasion": occasion,
                "plan_version": handle.get("version") or 1,
                "task_id": task_id,
                "fingerprint": json.dumps(fingerprint, sort_keys=True),
                "created_at": stamp,
            }),
        ], key("fingerprint", occasion, task_id, handle.get("version") or 1))

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

    def get(self, task_id: int) -> Task:
        found = self.storage.query("SELECT * FROM tasks WHERE id = ?", (task_id,))
        if not found:
            raise TaskNotFound("no such task", task_id=task_id)
        return self._hydrate(found[0])

    def _all(self) -> list[Task]:
        """The graph. Every task is live: the only thing that could ever supersede one was
        a split, and a task is one contract now, so the liveness filter this read used to
        carry has nothing left to exclude."""
        return [
            self._hydrate(r)
            for r in self.storage.query("SELECT * FROM tasks ORDER BY id")
        ]

    def _hydrate(self, r) -> Task:
        deps = tuple(
            row["depends_on"]
            for row in self.storage.query(
                "SELECT depends_on FROM task_deps WHERE task_id = ? "
                "ORDER BY depends_on",
                (r["id"],),
            )
        )
        return Task(
            id=r["id"],
            contract_ref=RowRef.parse(r["contract_ref"]),
            title=r["title"],
            state=r["state"],
            serve_epoch=r["serve_epoch"],
            deps=deps,
            detail=r["detail"],
            block_reason=r["block_reason"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )

    def is_finalized(self) -> bool:
        return self.storage.plan_handle().get("state") == "finalized"

