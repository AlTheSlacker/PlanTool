"""Scope-attachment framework (DEVIATIONS.md D8, M5_PLAN.md section 2).

Not in the frozen plan. Plan-time context allocation: when the master plan is built, the
planning session decides the base reference set for every part of the plan, and execution
serves what was allocated. The tool records that judgment and serves it; it never computes
relevance at read time.

This matters more than it looks. The rejected alternative — computing a "current working
set" from whatever is open across gaps, warnings, findings and conflicts — is *the tool
exercising judgment about relevance*, which is the one thing the design spine forbids
(`decisions:12`). A relevance heuristic is the seed from which "the tool has opinions"
grows.

It also dissolves the unbounded-journal problem rather than answering it. `requirements:58`
requires resume to present "accumulated learnings" and nothing bounds the accumulation, so
as specified resume cost eventually scales with total session history — worse than the
plan-size scaling `requirements:62` exists to kill. Every candidate bound (last N,
since-last-gate) is arbitrary invention. Under scope levels, resume serves
plan ∪ current-package ∪ current-task ∪ current-subtask, and the bound is structural. See
DEFECTS.md F16.

M5a builds the framework only. The allocation surface — deciding *what* to attach *where*
during planning — is M5b. The schema has to come first because nothing may write an
attachment before the scope column exists: retrofitting one means back-filling a level for
every attachment ever made, a judgment nobody would be positioned to make retroactively.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.errors import PlanToolError
from engine.models import RowRef
from engine.clock import now
from engine.storage import Op, Storage

PLAN = "plan"
PACKAGE = "package"
TASK = "task"
SUBTASK = "subtask"

#: Broad to narrow. A sub-task's context is the union of its own attachments and those of
#: every enclosing scope (M5_PLAN.md 2.3). See `GLOSSARY.md` — these four levels are the
#: whole structural vocabulary, and DEVIATIONS.md D13 for why there are four.
#:
#: A `session` level was in the owner's original phrasing and was dropped on review: these
#: are plan structure, whereas a session is an episode of work — and session-scoped
#: attachment is what the journal already is. Settled 2026-07-20.
LEVELS = (PLAN, PACKAGE, TASK, SUBTASK)

#: How broad each level is, for detecting promotion (M5_PLAN.md 2.5).
_BREADTH = {PLAN: 3, PACKAGE: 2, TASK: 1, SUBTASK: 0}


class UnknownScopeLevel(PlanToolError):
    """The level is not one of plan | package | task | subtask."""


class PromotionNeedsReason(PlanToolError):
    """M5_PLAN.md 2.5 — asymmetric friction. Broadening an attachment's scope requires a
    recorded reason the owner sees; narrowing is free."""


@dataclass(frozen=True, slots=True)
class Attachment:
    id: int
    scope_level: str
    scope_key: str
    target_root: RowRef
    reason: str
    promoted_from: str | None = None
    superseded_at: str | None = None
    created_at: str = ""

    @property
    def is_live(self) -> bool:
        return self.superseded_at is None


class AttachmentService:
    def __init__(self, storage: Storage, rows):
        self.storage = storage
        self.rows = rows

    def attach(
        self,
        target: RowRef | str,
        scope_level: str,
        scope_key: str = "",
        reason: str = "",
        lease=None,
    ) -> Attachment:
        """Attach a row to a scope, keyed on its lineage root.

        M5_PLAN.md 2.4: keyed on the lineage root rather than the row ref, because
        `decisions:3` makes the plan a living source of truth — rows are superseded and
        revisions rewrite them, and an allocation keyed on a row id silently detaches the
        moment its target is superseded. This is exactly `findings:16` / `requirements:78`,
        where gap dismissals had the identical problem and the answer was the same. Second
        application of the primitive, which is mild evidence it is the right one.
        """
        self._guard_level(scope_level)
        root = self.rows.lineage_root(target)

        existing = self._find(root)
        promoted_from = None
        if existing is not None:
            if _BREADTH[scope_level] > _BREADTH[existing.scope_level]:
                if not reason.strip():
                    raise PromotionNeedsReason(
                        f"promoting {root} from {existing.scope_level} to {scope_level} "
                        "broadens its reach; record why. A plan-level attachment is in "
                        "every sub-task forever, and nobody notices a cost spread evenly.",
                        target=str(root),
                        from_level=existing.scope_level,
                        to_level=scope_level,
                    )
                promoted_from = existing.scope_level

        stamp = now()
        ops = []
        if existing is not None:
            # One live placement per target. Without this, narrowing is a no-op: the
            # broader row stays live and the target is in every sub-task forever — the
            # "too low"/"too high" asymmetry collapses because only one direction works.
            ops.append(Op("update", "scope_attachments", {"superseded_at": stamp},
                          where={"id": existing.id}))
        op = Op("insert", "scope_attachments", {
            "scope_level": scope_level,
            "scope_key": scope_key,
            "target_root": str(root),
            "reason": reason,
            "promoted_from": promoted_from,
            "created_at": stamp,
        })
        ops.append(op)
        self.storage.write_atomic(
            ops, f"attach:{root}:{scope_level}:{scope_key}:{stamp}", lease=lease
        )
        return self.get(op.result["id"])

    def context_for(
        self, subtask_key: str = "", task_key: str = "", package_key: str = ""
    ) -> tuple[RowRef, ...]:
        """M5_PLAN.md 2.3 — a sub-task's context is the union of its own attachments and
        those of every enclosing scope: plan ∪ package ∪ task ∪ subtask.

        This is the structural bound that replaces "last N" or "since last gate". Note it
        is a union of *recorded* allocations, not a computed relevance ranking: every row
        here is here because a planning session put it here.

        Keys are row ids, never names (`GLOSSARY.md`): a name-keyed scope silently returns
        an empty set on a typo, and a sub-task quietly missing its mid-level context is the
        failure `decisions:14` measures.
        """
        wanted = [(PLAN, "")]
        if package_key:
            wanted.append((PACKAGE, package_key))
        if task_key:
            wanted.append((TASK, task_key))
        if subtask_key:
            wanted.append((SUBTASK, subtask_key))

        refs: list[str] = []
        for level, key in wanted:
            refs.extend(
                r["target_root"]
                for r in self.storage.query(
                    "SELECT target_root FROM scope_attachments "
                    "WHERE scope_level = ? AND scope_key = ? AND superseded_at IS NULL "
                    "ORDER BY id",
                    (level, key),
                )
            )
        seen, ordered = set(), []
        for ref in refs:
            if ref not in seen:
                seen.add(ref)
                ordered.append(RowRef.parse(ref))
        return tuple(ordered)

    def promotions(self) -> list[Attachment]:
        """The review surface's input (M5_PLAN.md 2.5): every broadening, with the reason
        its author had to write down. Gaming the accounting should require lying in a log
        the owner reads — the same shape as `requirements:79`."""
        return [
            self._hydrate(r)
            for r in self.storage.query(
                "SELECT * FROM scope_attachments WHERE promoted_from IS NOT NULL "
                "ORDER BY id"
            )
        ]

    def get(self, attachment_id: int) -> Attachment:
        found = self.storage.query(
            "SELECT * FROM scope_attachments WHERE id = ?", (attachment_id,)
        )
        if not found:
            raise PlanToolError("no such attachment", attachment_id=attachment_id)
        return self._hydrate(found[0])

    def _find(self, root: RowRef) -> Attachment | None:
        """The live placement, if the target has one."""
        found = self.storage.query(
            "SELECT * FROM scope_attachments WHERE target_root = ? "
            "AND superseded_at IS NULL ORDER BY id DESC LIMIT 1",
            (str(root),),
        )
        return self._hydrate(found[0]) if found else None

    @staticmethod
    def _guard_level(level: str) -> None:
        if level not in LEVELS:
            raise UnknownScopeLevel(
                f"{level!r} is not a scope level; expected one of " + ", ".join(LEVELS),
                level=level,
            )

    @staticmethod
    def _hydrate(r) -> Attachment:
        return Attachment(
            id=r["id"],
            scope_level=r["scope_level"],
            scope_key=r["scope_key"],
            target_root=RowRef.parse(r["target_root"]),
            reason=r["reason"],
            promoted_from=r["promoted_from"],
            superseded_at=r["superseded_at"],
            created_at=r["created_at"],
        )
