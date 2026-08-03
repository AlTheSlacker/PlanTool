"""brief-composer (components:12).

Composes immutable, scoped task briefs from link-graph candidate closures with 100%
candidate accounting.

Contracts: contracts:68 compose_brief, contracts:41 audit_brief.

**The split is gone** — `contracts:40`, with its three errors, its supersession machinery
and its payload parser. It existed because the unit a builder was handed was one contract,
which was not a servable size; a task is one function now (v3 D5), so there is nothing to
divide. Keeping the entry point alone would have left machinery whose reason for existing
had been removed: the two coverage checks, the refusal of a one-way "split", and the
rewiring of dependants onto the products all existed to make that one act safe.

One thing here is not in the frozen plan:

- **DEFECTS.md F26** — the candidate closure is frozen into the brief. `contracts:41` audits
  against a closure recomputed at audit time, but `decisions:3` makes the plan a living
  source of truth, so requirements:44's 100% accounting meter would drift on its own and
  "the composer skipped a row" would be indistinguishable from "the plan grew".

The actor split is `decisions:60` and is load-bearing: `next_task` returns candidates,
**the planning session's LLM** makes the selection, `compose_brief` is a separate second
call. This module never selects. It computes the denominator, checks the accounting, and
records what it was told — which is the whole of `decisions:52`'s division of labour.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.errors import PlanToolError
from engine.models import RowRef
from engine.behaviours import BehaviourService
from engine.clock import now
from engine.idempotency import key
from engine.storage import FromOp, Op, Storage
from engine.tasks import PENDING

INCLUDED = "included"
OMITTED = "omitted"

CLOSURE = "closure"
ALLOCATION = "allocation"

#: requirements:79 — omissions of these row types are surfaced to the owner by name, not
#: merely counted. Dropping a decision or a failure mode is the omission that costs.
LOUD_OMISSIONS = ("decisions", "requirements", "dep_failure_modes")


class BriefNotFound(PlanToolError):
    """contracts:41 — names the missing id."""


class IncompleteAccounting(PlanToolError):
    """contracts:68 — a candidate row from the link-graph closure is neither included nor
    recorded-omitted; composition rejected naming the unaccounted rows (requirements:44,
    decisions:52)."""


class ClosureUnreadable(PlanToolError):
    """contracts:68 — candidate rows failed integrity; refuses to compose from partial
    state. A brief composed from a closure that is missing rows nobody knows are missing is
    the silent failure the whole accounting exists to prevent."""


class OmissionNeedsReason(PlanToolError):
    """requirements:79 — every omitted candidate is "explicitly waived with a recorded
    reason". An unreasoned omission is the silent deprioritization the requirement names."""


@dataclass(frozen=True, slots=True)
class BriefRow:
    target_ref: RowRef
    origin: str
    disposition: str
    reason: str = ""


@dataclass(frozen=True, slots=True)
class Brief:
    """entities:13 — immutable, including its omission log. No lifecycle: regeneration
    creates a superseding brief and the old one stays frozen for defect forensics."""

    id: int
    task_id: int
    serve_epoch: int
    goal: str
    rows: tuple[BriefRow, ...]
    # A live `glossary` section stood here until v3 change 4, attached at read time as a
    # constraint on the output rather than as accounted context. The owner's reason for
    # removing it is better than the one this module carried: "the brief idea is dumb, you
    # don't build it until the plan is finished, but you need the glossary context during
    # the plan." A brief is served after finalization, and naming drift happens while the
    # rows are being written — so the glossary arrived after the damage. This module's own
    # comment had reached half of that ("serving last week's glossary would enforce a rule
    # the plan has since retired") and drew the wrong conclusion from it.
    is_draft: bool = False
    supersedes: int | None = None
    superseded_by: int | None = None
    created_at: str = ""

    @property
    def included(self) -> tuple[RowRef, ...]:
        return tuple(r.target_ref for r in self.rows if r.disposition == INCLUDED)

    @property
    def omitted(self) -> tuple[BriefRow, ...]:
        return tuple(r for r in self.rows if r.disposition == OMITTED)

    @property
    def is_live(self) -> bool:
        return self.superseded_by is None


@dataclass(frozen=True, slots=True)
class BriefSelection:
    """decisions:60 — the planning-session LLM's picks. Included rows, and omitted rows
    each with a reason. The tool never fills either in."""

    included: tuple[str, ...] = ()
    omitted: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BriefAudit:
    """contracts:41 — the automated meter for requirements:44's 100% accounting target.

    Two separate numbers, which is DEFECTS.md F26's fix. `accounted` measures the brief
    against the closure frozen with it — that is what requirements:44 is about, and it is
    stable forever. `drifted_in`/`drifted_out` measure the plan's movement since, which is
    real and worth seeing but is not a composition defect and never fails the audit.
    """

    brief_id: int
    task_id: int
    candidates: int
    included: int
    omitted: int
    unaccounted: tuple[str, ...] = ()
    loud_omissions: tuple[str, ...] = ()
    drifted_in: tuple[str, ...] = ()
    drifted_out: tuple[str, ...] = ()

    @property
    def accounted(self) -> bool:
        """requirements:44's target: every frozen candidate has a disposition."""
        return not self.unaccounted

    @property
    def drifted(self) -> bool:
        return bool(self.drifted_in or self.drifted_out)


class BriefComposer:
    def __init__(self, storage: Storage, tasks, graph=None, attachments=None,
                 behaviours=None):
        self.storage = storage
        self.tasks = tasks
        self.graph = graph
        self.attachments = attachments
        self.behaviours = behaviours or BehaviourService(storage)

    # --- contracts:68 ---

    def compose_brief(
        self, task_id: int, selection: BriefSelection
    ) -> Brief:
        """Record the planning session's selection as an immutable brief.

        `decisions:52` splits the work: the tool computes the deterministic candidate
        closure, the composing LLM makes the task-specific selection, and the contract
        mechanically rejects any composition that fails 100% candidate accounting. All three
        halves are here, and the middle one is the caller's.

        Note what is *not* here: no relevance ranking, no size budget, no trimming.
        `decisions:34` puts brief sizing beyond token quotas deliberately — relevance is
        structural (the link graph) and the selection is made auditable rather than caged by
        numbers. A tool that trimmed would be exercising the judgment it exists to record.
        """
        task = self.tasks.get(task_id)

        candidates = self._candidates(task)
        self._guard_integrity(candidates)

        included = [c for c in candidates if c[0] in set(selection.included)]
        omitted = [c for c in candidates if c[0] in selection.omitted]
        accounted = {c[0] for c in included} | {c[0] for c in omitted}

        unaccounted = tuple(sorted(ref for ref, _ in candidates if ref not in accounted))
        if unaccounted:
            raise IncompleteAccounting(
                "composition rejected; these candidate rows are neither included nor "
                "recorded-omitted: " + ", ".join(unaccounted)
                + ". Every candidate is accounted for, so omission is a visible recorded "
                  "act and never a silent deprioritization (requirements:44).",
                task_id=task_id,
                unaccounted=list(unaccounted),
            )

        unreasoned = tuple(sorted(
            ref for ref in selection.omitted if not selection.omitted[ref].strip()
        ))
        if unreasoned:
            raise OmissionNeedsReason(
                "omitting a candidate requires a recorded reason the owner sees; these "
                "have none: " + ", ".join(unreasoned) + " (requirements:79)",
                task_id=task_id,
                rows=list(unreasoned),
            )

        previous = self.live_brief(task_id)
        stamp = now()
        ops: list[Op] = [Op("insert", "briefs", {
            "task_id": task_id,
            "serve_epoch": task.serve_epoch,
            "goal": task.title,
            "is_draft": 0 if self.tasks.is_finalized() else 1,
            "supersedes": previous.id if previous else None,
            "created_at": stamp,
        })]
        for ref, origin in candidates:
            ops.append(Op("insert", "brief_rows", {
                "brief_id": FromOp(0, "id"),
                "target_ref": ref,
                "origin": origin,
                "disposition": INCLUDED if ref in {c[0] for c in included} else OMITTED,
                "reason": selection.omitted.get(ref, ""),
            }))
        if previous is not None:
            # requirements:61's bidirectional lineage, applied to a non-row entity: the
            # replacement points back at creation and the old one is stamped once. The old
            # brief's *content* is untouched — entities:13 is immutable so forensics can
            # always answer what the engine saw.
            ops.append(Op("update", "briefs", {"superseded_by": FromOp(0, "id")},
                          where={"id": previous.id}))
        receipt = self.storage.write_atomic(
            ops,
            key(
                "compose",
                task_id,
                task.serve_epoch,
                previous.id if previous else 0,
            ),
        )
        # Read the id off the receipt, not off `ops[0].result`. On a replayed key the ops
        # were never executed and carry no result — decisions:43, and the same reason
        # submit_rows has always read its refs from the receipt. This path was
        # unreachable while the key carried a timestamp, because no key ever repeated;
        # now that the key identifies the operation, a genuine repeat replays.
        return self.get(receipt["results"][0]["id"])

    def _candidates(self, task) -> list[tuple[str, str]]:
        """The denominator, computed by the tool and never supplied by the caller.

        Two sources, both recorded judgments rather than computed relevance:

        - **closure** — `requirements:36`, every row reachable from the task's contract
          by the defined traversal. Deterministic and structural.
        - **allocation** — the rows a planning session attached to this task or to an
          enclosing scope (D8). Plan-time context allocation: allocation happens once, at
          plan time, as a recorded judgment, and execution serves what was allocated.

        Allocated rows are candidates, not automatic inclusions, and they are subject to the
        same 100% accounting. That is deliberate: an over-broad attachment is D8 §2.5's
        "too high" failure — context bloat arriving through the ceiling, spread evenly so
        nobody notices — and making the composer omit it *with a reason* is how it becomes
        visible in a log the owner reads.
        """
        seen: dict[str, str] = {}
        for ref in self.tasks.closure_for(task):
            seen.setdefault(str(ref), CLOSURE)
        if self.attachments is not None:
            # One key, because there are two scope levels now and one of them is the plan.
            # `_package_of` walked the served node up to its owning task and on to its
            # package, through two columns schema 8 drops. The level it resolved is gone,
            # and what used to sit at it now sits at plan scope and reaches every task —
            # the price of D7, recorded in 1D.3 rather than discovered later.
            allocated = self.attachments.context_for(task_key=str(task.id))
            for ref in allocated:
                seen.setdefault(str(ref), ALLOCATION)
        return sorted(seen.items())

    def _guard_integrity(self, candidates: list[tuple[str, str]]) -> None:
        """contracts:68's `ClosureUnreadable`. The mechanism already exists —
        `storage.integrity_check()` names unreadable rows — and had no consumer until now.
        Refusing here is the point: a brief composed from partial state is one whose
        accounting is complete over the wrong set."""
        report = self.storage.integrity_check()
        if not report.unreadable:
            return
        broken = sorted(set(report.unreadable) & {ref for ref, _ in candidates})
        if broken:
            raise ClosureUnreadable(
                "refusing to compose from partial state; these candidate rows failed "
                "integrity: " + ", ".join(broken),
                rows=broken,
            )

    # --- contracts:41 ---

    def audit_brief(self, brief_id: int) -> BriefAudit:
        """The automated meter for `requirements:44`'s 100% accounting target.

        Accounting is measured against the closure **frozen with the brief**, which is
        DEFECTS.md F26's fix. Auditing against a recomputed closure would conflate a real
        composition defect with the plan simply having moved on, and `requirements:44`'s
        metric would degrade with plan age rather than with composition quality.

        Drift is reported alongside, because "the plan changed under this brief" is a real
        and useful fact — it is what `requirements:73`'s drift flags are for at the workspace
        level. It never fails the audit.
        """
        brief = self.get(brief_id)
        task = self.tasks.get(brief.task_id)

        frozen = {r.target_ref for r in brief.rows}
        current = {RowRef.parse(ref) for ref, _ in self._candidates(task)}

        loud = tuple(sorted(
            str(r.target_ref) for r in brief.omitted
            if r.target_ref.table in LOUD_OMISSIONS
        ))
        return BriefAudit(
            brief_id=brief.id,
            task_id=brief.task_id,
            candidates=len(brief.rows),
            included=len(brief.included),
            omitted=len(brief.omitted),
            unaccounted=(),  # a stored brief cannot be unaccounted: compose_brief refuses
            loud_omissions=loud,
            drifted_in=tuple(sorted(str(r) for r in current - frozen)),
            drifted_out=tuple(sorted(str(r) for r in frozen - current)),
        )

    def waivers(self) -> tuple[str, ...]:
        """requirements:79 — every waiver of a decision, requirement or failure-mode row,
        for the finalization and brief-review summaries. Surfaced by name: gaming the
        accounting should require lying in a log the owner reads."""
        return tuple(
            f"brief {r['brief_id']}: {r['target_ref']} — {r['reason']}"
            for r in self.storage.query(
                "SELECT brief_id, target_ref, reason FROM brief_rows "
                "WHERE disposition = ? ORDER BY brief_id, id", (OMITTED,)
            )
            if r["target_ref"].split(":")[0] in LOUD_OMISSIONS
        )

    # --- reads ---

    def get(self, brief_id: int) -> Brief:
        found = self.storage.query("SELECT * FROM briefs WHERE id = ?", (brief_id,))
        if not found:
            raise BriefNotFound("no such brief", brief_id=brief_id)
        r = found[0]
        rows = tuple(
            BriefRow(
                target_ref=RowRef.parse(b["target_ref"]),
                origin=b["origin"],
                disposition=b["disposition"],
                reason=b["reason"],
            )
            for b in self.storage.query(
                "SELECT * FROM brief_rows WHERE brief_id = ? ORDER BY id", (brief_id,)
            )
        )
        return Brief(
            id=r["id"],
            task_id=r["task_id"],
            serve_epoch=r["serve_epoch"],
            goal=r["goal"],
            rows=rows,
            is_draft=bool(r["is_draft"]),
            supersedes=r["supersedes"],
            superseded_by=r["superseded_by"],
            created_at=r["created_at"],
        )

    def live_brief(self, task_id: int) -> Brief | None:
        found = self.storage.query(
            "SELECT id FROM briefs WHERE task_id = ? AND superseded_by IS NULL "
            "ORDER BY id DESC LIMIT 1",
            (task_id,),
        )
        return self.get(found[0]["id"]) if found else None

    def history(self, task_id: int) -> list[Brief]:
        """Every brief ever composed for this task, oldest first. `entities:13`: old
        briefs stay frozen for defect forensics — 'what exactly did the engine see'."""
        return [
            self.get(r["id"])
            for r in self.storage.query(
                "SELECT id FROM briefs WHERE task_id = ? ORDER BY id", (task_id,)
            )
        ]
