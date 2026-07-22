"""brief-composer (components:12).

Composes immutable, scoped sub-task briefs from link-graph candidate closures with 100%
candidate accounting, and splits sub-tasks when a brief proves too large.

Contracts: contracts:68 compose_brief, contracts:41 audit_brief, contracts:40 split_subtask.

Three things here are not in the frozen plan, all logged:

- **D12** — a split redistributes the original's *obligations*. The frozen plan's check
  compares the new sub-tasks' contracts against the original's, and under `decisions:63`
  those are the same single contract for each of them, so it is vacuous (DEFECTS.md F23).
  Obligations are the denominator it was missing.
- **DEFECTS.md F25** — "superseding the original in the graph" is given a meaning: the
  original leaves the graph, and its dependants are rewired to the new sub-tasks. Without
  that a split silently deadlocks every consumer behind a node that can never complete.

**A renamed error, owner's decision 2026-07-21 (DEFECTS.md F27).** `contracts:40` declares
this error as `PartsDontCover`, and `errors.py`'s convention is that a contract's error name
is the class name. `GLOSSARY.md` wins: `part` is retired — what a split produces is a
**sub-task**, distinguished by which obligations it owns, not a different kind of thing — so
the class is `ObligationsNotCovered`, paired with its mirror `ObligationsNotOwned`. The
convention is internal and has no consumer outside this repo, so keeping the plan's spelling
would have bought nothing and cost a live retired word in the codebase. `contracts:40`'s own
name is recorded on the class so a reader grepping the frozen plan still lands here.
- **DEFECTS.md F26** — the candidate closure is frozen into the brief. `contracts:41` audits
  against a closure recomputed at audit time, but `decisions:3` makes the plan a living
  source of truth, so requirements:44's 100% accounting meter would drift on its own and
  "the composer skipped a row" would be indistinguishable from "the plan grew".

The actor split is `decisions:60` and is load-bearing: `next_subtask` returns candidates,
**the planning session's LLM** makes the selection, `compose_brief` is a separate second
call. This module never selects. It computes the denominator, checks the accounting, and
records what it was told — which is the whole of `decisions:52`'s division of labour.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.errors import PlanToolError
from engine.models import RowRef
from engine.obligations import ObligationService
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


class ObligationsNotCovered(PlanToolError):
    """contracts:40 — the new sub-tasks do not jointly cover the original's obligations;
    names what is uncovered; nothing written.

    **Spelled `PartsDontCover` in the frozen plan** (`contracts:40`), renamed here because
    `part` is retired — see the module docstring and DEFECTS.md F27."""


class ObligationsNotOwned(PlanToolError):
    """Not in the frozen plan. `ObligationsNotCovered`'s mirror: a split that assigns obligations
    the original never owed enlarges the denominator it is measured by, which is F23's
    disease pointing the other way."""


class NothingToSplit(PlanToolError):
    """contracts:40 — a split needs at least two sub-tasks. One is a rename, and zero is a
    deletion wearing a split's name."""


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
    subtask_id: int
    serve_epoch: int
    goal: str
    rows: tuple[BriefRow, ...]
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
    subtask_id: int
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
                 obligations=None):
        self.storage = storage
        self.tasks = tasks
        self.graph = graph
        self.attachments = attachments
        self.obligations = obligations or ObligationService(storage)

    # --- contracts:68 ---

    def compose_brief(
        self, subtask_id: int, selection: BriefSelection
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
        subtask = self.tasks.get(subtask_id)
        self.tasks.guard_live(subtask)

        candidates = self._candidates(subtask)
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
                subtask_id=subtask_id,
                unaccounted=list(unaccounted),
            )

        unreasoned = tuple(sorted(
            ref for ref in selection.omitted if not selection.omitted[ref].strip()
        ))
        if unreasoned:
            raise OmissionNeedsReason(
                "omitting a candidate requires a recorded reason the owner sees; these "
                "have none: " + ", ".join(unreasoned) + " (requirements:79)",
                subtask_id=subtask_id,
                rows=list(unreasoned),
            )

        previous = self.live_brief(subtask_id)
        stamp = now()
        ops: list[Op] = [Op("insert", "briefs", {
            "subtask_id": subtask_id,
            "serve_epoch": subtask.serve_epoch,
            "goal": subtask.title,
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
                subtask_id,
                subtask.serve_epoch,
                previous.id if previous else 0,
            ),
        )
        # Read the id off the receipt, not off `ops[0].result`. On a replayed key the ops
        # were never executed and carry no result — decisions:43, and the same reason
        # submit_rows has always read its refs from the receipt. This path was
        # unreachable while the key carried a timestamp, because no key ever repeated;
        # now that the key identifies the operation, a genuine repeat replays.
        return self.get(receipt["results"][0]["id"])

    def _candidates(self, subtask) -> list[tuple[str, str]]:
        """The denominator, computed by the tool and never supplied by the caller.

        Two sources, both recorded judgments rather than computed relevance:

        - **closure** — `requirements:36`, every row reachable from the sub-task's contract
          by the defined traversal. Deterministic and structural.
        - **allocation** — the rows a planning session attached to this sub-task or to an
          enclosing scope (D8). Plan-time context allocation: allocation happens once, at
          plan time, as a recorded judgment, and execution serves what was allocated.

        Allocated rows are candidates, not automatic inclusions, and they are subject to the
        same 100% accounting. That is deliberate: an over-broad attachment is D8 §2.5's
        "too high" failure — context bloat arriving through the ceiling, spread evenly so
        nobody notices — and making the composer omit it *with a reason* is how it becomes
        visible in a log the owner reads.
        """
        seen: dict[str, str] = {}
        for ref in self.tasks.closure_for(subtask):
            seen.setdefault(str(ref), CLOSURE)
        if self.attachments is not None:
            allocated = self.attachments.context_for(
                subtask_key=str(subtask.id),
                task_key=str(subtask.task_id) if subtask.task_id else "",
                package_key=self._package_of(subtask),
            )
            for ref in allocated:
                seen.setdefault(str(ref), ALLOCATION)
        return sorted(seen.items())

    def _package_of(self, subtask) -> str:
        """The package enclosing this sub-task, via its task. Empty when the contract has
        no owning task (DEFECTS.md F24) — reported by its absence, never guessed."""
        if not subtask.task_id:
            return ""
        found = self.storage.query(
            "SELECT package_id FROM tasks WHERE id = ?", (subtask.task_id,)
        )
        return str(found[0]["package_id"]) if found else ""

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
        subtask = self.tasks.get(brief.subtask_id)

        frozen = {r.target_ref for r in brief.rows}
        current = {RowRef.parse(ref) for ref, _ in self._candidates(subtask)}

        loud = tuple(sorted(
            str(r.target_ref) for r in brief.omitted
            if r.target_ref.table in LOUD_OMISSIONS
        ))
        return BriefAudit(
            brief_id=brief.id,
            subtask_id=brief.subtask_id,
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

    # --- contracts:40 ---

    def split_subtask(
        self, subtask_id: int, into: list[tuple[str, list[int]]]
    ) -> list:
        """Divide a sub-task whose brief proved too large; silent trimming is never a
        remedy (`requirements:37`).

        `into` is the sub-tasks to split it into, each `(title, [obligation ids])`. They
        are **sub-tasks**, not a different kind of thing (`GLOSSARY.md`) — what distinguishes
        them is which obligations they own. They jointly redistribute the original's
        obligations; a split never invents or discards one. `decisions:63` says a split
        "divides along the contract's param/error surface", and the obligation surface (D12)
        *is* that surface, enumerated by the planning session at finalization rather than by
        the splitter at split time.

        The original is superseded and leaves the graph, its dependants rewired to every new
        sub-task (DEFECTS.md F25). Rewiring to all of them rather than guessing which one a
        dependant actually needs is the only choice that preserves `requirements:34` without
        the tool exercising judgment: waiting for all of them is never wrong, only sometimes
        conservative.
        """
        subtask = self.tasks.get(subtask_id)
        self.tasks.guard_live(subtask)
        if len(into) < 2:
            raise NothingToSplit(
                "a split needs at least two sub-tasks; one is a rename and zero is a "
                "deletion wearing a split's name",
                subtask_id=subtask_id,
                into=len(into),
            )

        # Raises when the surface was never enumerated: a split measured against an empty
        # denominator passes vacuously, which is F23 itself.
        self.obligations.require_enumerated(subtask_id, "a split")

        assignment = {i: ids for i, (_, ids) in enumerate(into)}
        uncovered = self.obligations.uncovered(subtask_id, assignment)
        if uncovered:
            raise ObligationsNotCovered(
                "the new sub-tasks do not jointly cover the original's obligations; "
                "uncovered: "
                + ", ".join(uncovered)
                + ". Nothing written — splitting is how an over-large brief is made "
                  "tractable, not how work is dropped (requirements:37).",
                subtask_id=subtask_id,
                uncovered=list(uncovered),
            )
        foreign = self.obligations.foreign(subtask_id, assignment)
        if foreign:
            raise ObligationsNotOwned(
                "the new sub-tasks claim obligations the original does not own: "
                + ", ".join(str(f) for f in foreign) + "; nothing written",
                subtask_id=subtask_id,
                foreign=list(foreign),
            )

        stamp = now()
        ops: list[Op] = []
        node_indexes: list[int] = []
        for title, _ in into:
            node_indexes.append(len(ops))
            ops.append(Op("insert", "subtasks", {
                # A split's sub-tasks share the original's contract ref, which is why M5a's UNIQUE
                # constraint on it had to go: uniqueness was never really about the
                # contract, it was expressing "nothing is owed twice" — which live
                # obligation ownership states directly (D12).
                "contract_ref": str(subtask.contract_ref),
                "title": title,
                "task_id": subtask.task_id,
                "state": PENDING,
                "serve_epoch": 0,
                "created_at": stamp,
                "updated_at": stamp,
            }))
        self.storage.write_atomic(ops, key("split", subtask_id, "nodes"))

        new_ids = [ops[i].result["id"] for i in node_indexes]
        by_subtask = {new_ids[i]: ids for i, (_, ids) in enumerate(into)}

        wiring: list[Op] = [
            Op("update", "subtasks",
               {"superseded_by": new_ids[0], "updated_at": stamp},
               where={"id": subtask_id}),
        ]
        # The original's own dependencies become every new sub-task's dependencies: each is
        # still downstream of whatever the whole was.
        for new_id in new_ids:
            for dep in subtask.deps:
                wiring.append(Op("insert", "subtask_deps", {
                    "subtask_id": new_id, "depends_on": dep,
                }))
        # And its dependants wait for all the new sub-tasks instead of a node that can never
        # complete. This is the deadlock F25 describes, so the *stale* edge has to go: an
        # edge onto a superseded node is never satisfied, and leaving it while adding the
        # new ones would keep the consumer blocked forever with the fix apparently applied.
        # The existing edge is repointed at the first of them rather than deleted, because
        # storage's op vocabulary is insert/update by design (no delete: plan history is
        # append-only) and repointing is one op either way.
        for consumer in self._dependants(subtask_id):
            wiring.append(Op("update", "subtask_deps", {"depends_on": new_ids[0]},
                             where={"subtask_id": consumer, "depends_on": subtask_id}))
            for new_id in new_ids[1:]:
                wiring.append(Op("insert", "subtask_deps", {
                    "subtask_id": consumer, "depends_on": new_id,
                }))
        wiring.extend(self.obligations.redistribute_ops(subtask_id, by_subtask))
        self.storage.write_atomic(wiring, key("split", subtask_id, "wiring"))

        return [self.tasks.get(new_id) for new_id in new_ids]

    def _dependants(self, subtask_id: int) -> tuple[int, ...]:
        return tuple(
            r["subtask_id"]
            for r in self.storage.query(
                "SELECT subtask_id FROM subtask_deps WHERE depends_on = ? "
                "ORDER BY subtask_id", (subtask_id,),
            )
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
            subtask_id=r["subtask_id"],
            serve_epoch=r["serve_epoch"],
            goal=r["goal"],
            rows=rows,
            is_draft=bool(r["is_draft"]),
            supersedes=r["supersedes"],
            superseded_by=r["superseded_by"],
            created_at=r["created_at"],
        )

    def live_brief(self, subtask_id: int) -> Brief | None:
        found = self.storage.query(
            "SELECT id FROM briefs WHERE subtask_id = ? AND superseded_by IS NULL "
            "ORDER BY id DESC LIMIT 1",
            (subtask_id,),
        )
        return self.get(found[0]["id"]) if found else None

    def history(self, subtask_id: int) -> list[Brief]:
        """Every brief ever composed for this sub-task, oldest first. `entities:13`: old
        briefs stay frozen for defect forensics — 'what exactly did the engine see'."""
        return [
            self.get(r["id"])
            for r in self.storage.query(
                "SELECT id FROM briefs WHERE subtask_id = ? ORDER BY id", (subtask_id,)
            )
        ]
