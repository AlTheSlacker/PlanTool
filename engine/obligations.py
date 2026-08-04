"""The obligation surface (DEVIATIONS.md D12, fixing DEFECTS.md F23).

Not in the frozen plan. An **obligation** is one dischargeable commitment of a contract:
the primary behaviour of its signature, or one of its enumerated error conditions. It is
the accounting denominator that `contracts:40` and `contracts:62` both assume and the plan
never defines.

F23 is what makes this necessary. `contracts:40` rejects a split when its products "do not
jointly cover the original sub-task's contracts" — but `decisions:63` gives every sub-task
exactly one contract, and every sub-task a split produces names that same contract, so joint
coverage is vacuous. `requirements:37`'s "silent trimming of relevant content is not a remedy" has no
enforcement at all. A check that runs, passes, and means nothing is worse than a missing one,
because it reports success.

**Where the set comes from is what carries the design.** It is enumerated by the *planning
session* and frozen at finalization — before, and independently of, any split later measured
against it. Two alternatives were rejected (D12):

- *The tool derives it by parsing the contract row.* Rejected on the design spine — the tool
  records judgment, it never exercises it (`decisions:12`) — and on fact: `plan_rows.content`
  is free-form JSON with no per-table schema, so a contract's enumerated errors are a
  methodology convention rather than a storage guarantee.
- *The splitting session declares it at split time.* Rejected: it hands the denominator to the
  party being audited, which is precisely how `findings:18` was gamed.

`enumerate_from_row` below reads an explicit `obligations` array off the contract row. That is
**not** the rejected first option: the array is a declaration the planning session wrote, not
an inference the tool drew from prose. The distinction is exactly whether the tool is reading
a judgment or making one — and it is why a contract row with no `obligations` array yields an
empty set rather than a guess. An empty set means *not yet enumerated*, and every consumer
refuses loudly rather than passing vacuously. That is the whole lesson of F23.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.errors import PlanToolError
from engine.clock import now
from engine.idempotency import key
from engine.storage import FromOp, Op, Storage

BEHAVIOUR = "behaviour"
ERROR = "error"
KINDS = (BEHAVIOUR, ERROR)

#: The key of the obligation every contract has: doing what its signature says.
PRIMARY = "behaviour"


class NotEnumerated(PlanToolError):
    """The sub-task has no frozen obligation surface, so there is no denominator to account
    against. Refused rather than passed vacuously — DEFECTS.md F23."""


class AmendmentNeedsReason(PlanToolError):
    """D12 — a frozen enumeration can be corrected, but never silently. Same friction shape
    as requirements:79's waiver log and D8's promotion reason."""


class UnknownObligation(PlanToolError):
    """An obligation id that is not live, or not owned by the sub-task in question."""


@dataclass(frozen=True, slots=True)
class Obligation:
    id: int
    contract_ref: str
    key: str
    kind: str
    statement: str
    created_at: str = ""
    retired_at: str | None = None

    @property
    def ref(self) -> str:
        """How an obligation is named in evidence maps and coverage errors."""
        return f"{self.contract_ref}#{self.key}"


@dataclass(frozen=True, slots=True)
class ObligationSpec:
    """What a planning session enumerates. Deliberately dumb: a key, a kind, a statement."""

    key: str
    kind: str
    statement: str


class ObligationService:
    def __init__(self, storage: Storage):
        self.storage = storage

    # --- enumeration, at finalization ---

    def enumerate_from_row(self, content: dict) -> list[ObligationSpec]:
        """Read the obligation surface a planning session declared on a contract row.

        Accepts either a list of strings (each becomes a behaviour obligation keyed by its
        position) or a list of objects with `key`/`kind`/`statement`. Anything else is
        ignored rather than interpreted: a malformed declaration is *not enumerated*, which
        every consumer then refuses on, and that is the safe direction.
        """
        declared = content.get("obligations")
        if not isinstance(declared, list):
            return []
        specs: list[ObligationSpec] = []
        for i, item in enumerate(declared):
            if isinstance(item, str):
                specs.append(ObligationSpec(
                    key=PRIMARY if i == 0 else f"o{i}", kind=BEHAVIOUR, statement=item
                ))
            elif isinstance(item, dict) and item.get("statement"):
                kind = item.get("kind", BEHAVIOUR)
                specs.append(ObligationSpec(
                    key=str(item.get("key") or f"o{i}"),
                    kind=kind if kind in KINDS else BEHAVIOUR,
                    statement=str(item["statement"]),
                ))
        return specs

    def freeze_ops(
        self,
        contract_ref: str,
        specs: list[ObligationSpec],
        subtask_id: int | FromOp,
        base_index: int = 0,
    ) -> list[Op]:
        """Ops that freeze `specs` against `contract_ref` and vest them in `subtask_id`.

        Returned as ops rather than written directly so finalization stays one atomic act: a
        plan half-enumerated is a plan whose accounting is silently partial.

        `base_index` is where these ops will sit in the caller's final batch. `FromOp`
        indexes are absolute within the batch storage applies, so a helper that emits a
        *fragment* has to be told its offset — there is no way to borrow an id relatively.
        """
        stamp = now()
        ops: list[Op] = []
        for spec in specs:
            ops.append(Op("insert", "obligations", {
                "contract_ref": contract_ref,
                "key": spec.key,
                "kind": spec.kind,
                "statement": spec.statement,
                "created_at": stamp,
            }))
            ops.append(Op("insert", "obligation_ownership", {
                "obligation_id": FromOp(base_index + len(ops) - 1, "id"),
                "subtask_id": subtask_id,
                "created_at": stamp,
            }))
        return ops

    # --- reads ---

    def for_subtask(self, subtask_id: int) -> tuple[Obligation, ...]:
        """The obligations this sub-task currently owes. Live ownership of live
        obligations — the set `verify_completion` must account for in full."""
        return tuple(
            self._hydrate(r)
            for r in self.storage.query(
                "SELECT o.* FROM obligations o "
                "JOIN obligation_ownership w ON w.obligation_id = o.id "
                "WHERE w.subtask_id = ? AND w.superseded_at IS NULL "
                "AND o.retired_at IS NULL ORDER BY o.id",
                (subtask_id,),
            )
        )

    def of_contract(self, contract_ref: str) -> tuple[Obligation, ...]:
        return tuple(
            self._hydrate(r)
            for r in self.storage.query(
                "SELECT * FROM obligations WHERE contract_ref = ? AND retired_at IS NULL "
                "ORDER BY id",
                (contract_ref,),
            )
        )

    def require_enumerated(self, subtask_id: int, action: str) -> tuple[Obligation, ...]:
        """Fetch the surface, refusing loudly when there is none.

        D12's accepted cost: sub-tasks derived before the obligation surface existed have no
        obligations recorded. The graph refuses to split or verify such a node rather than
        silently permitting an unaccountable one. A missing denominator must fail, not pass.
        """
        obligations = self.for_subtask(subtask_id)
        if not obligations:
            raise NotEnumerated(
                f"sub-task {subtask_id} has no frozen obligation surface, so there is "
                f"nothing to account {action} against. Enumerate the contract's "
                "obligations (its primary behaviour and each error condition) and "
                "re-finalize, or amend the enumeration with a recorded reason.",
                subtask_id=subtask_id,
                action=action,
            )
        return obligations

    # --- redistribution, by split_subtask ---

    def uncovered(
        self, subtask_id: int, assignment: dict[int, list[int]]
    ) -> tuple[str, ...]:
        """Which of the sub-task's obligations no new sub-task would own. `contracts:40`'s
        `PartsDontCover`, with the denominator F23 found missing.

        A split *redistributes*; it never invents or discards. Obligations assigned to no
        sub-task are named here; obligations assigned to more than one are a separate error,
        caught by the live-ownership unique index rather than by a check that could be
        forgotten.
        """
        owned = {o.id: o for o in self.for_subtask(subtask_id)}
        claimed = {oid for ids in assignment.values() for oid in ids}
        return tuple(sorted(o.ref for oid, o in owned.items() if oid not in claimed))

    def foreign(
        self, subtask_id: int, assignment: dict[int, list[int]]
    ) -> tuple[int, ...]:
        """Obligation ids a split tried to assign that the original does not own.

        The mirror of `uncovered`, and the reason the pair exists: coverage alone would let a
        split satisfy its accounting by *adding* obligations it never owed — the denominator
        being enlarged by the party being measured, which is F23's disease in the other
        direction.
        """
        owned = {o.id for o in self.for_subtask(subtask_id)}
        claimed = {oid for ids in assignment.values() for oid in ids}
        return tuple(sorted(claimed - owned))

    def redistribute_ops(
        self, subtask_id: int, assignment: dict[int, list[int]]
    ) -> list[Op]:
        """Ops moving live ownership from the original to the sub-tasks replacing it.

        Supersede-then-insert rather than update, because the redistribution history is the
        audit trail of the act being audited. The partial unique index on live ownership is
        what makes double-assignment impossible rather than merely checked.
        """
        stamp = now()
        # Superseded by id rather than by `WHERE superseded_at IS NULL`: storage's where
        # clause is an equality map, and `= NULL` matches nothing in SQL — a filter that
        # silently updates zero rows would leave the original still owning everything and
        # and each new insert would then collide with the live-ownership index.
        live = self.storage.query(
            "SELECT id FROM obligation_ownership WHERE subtask_id = ? "
            "AND superseded_at IS NULL",
            (subtask_id,),
        )
        ops: list[Op] = [
            Op("update", "obligation_ownership", {"superseded_at": stamp},
               where={"id": r["id"]})
            for r in live
        ]
        for new_subtask_id, obligation_ids in assignment.items():
            for obligation_id in obligation_ids:
                ops.append(Op("insert", "obligation_ownership", {
                    "obligation_id": obligation_id,
                    "subtask_id": new_subtask_id,
                    "created_at": stamp,
                }))
        return ops

    # --- amendment, the recorded escape hatch ---

    def amend(
        self,
        contract_ref: str,
        action: str,
        reason: str,
        obligation_id: int | None = None,
        spec: ObligationSpec | None = None,
        subtask_id: int | None = None,
    ) -> None:
        """Correct a frozen enumeration, on the record.

        D12: the accounting can be changed, but not silently. The reason is mandatory and
        the amendment log is the owner's review surface — gaming the accounting should
        require lying in a log the owner reads (`requirements:79`'s shape).
        """
        if not reason.strip():
            raise AmendmentNeedsReason(
                f"amending the frozen obligation surface of {contract_ref} changes the "
                "denominator a completion is measured against; record why",
                contract_ref=contract_ref,
                action=action,
            )
        stamp = now()
        ops: list[Op] = []
        if action == "retired":
            ops.append(Op("update", "obligations", {"retired_at": stamp},
                          where={"id": obligation_id}))
        elif action == "added":
            if spec is None or subtask_id is None:
                raise AmendmentNeedsReason(
                    "adding an obligation needs both the obligation and the sub-task that "
                    "will owe it; an unowned obligation is one nothing can discharge",
                    contract_ref=contract_ref,
                )
            ops.extend(self.freeze_ops(contract_ref, [spec], subtask_id))
        ops.append(Op("insert", "obligation_amendments", {
            "obligation_id": obligation_id,
            "contract_ref": contract_ref,
            "action": action,
            "reason": reason,
            "created_at": stamp,
        }))
        self.storage.write_atomic(ops, key("amend", contract_ref, action, obligation_id or 0))

    def amendments(self) -> list[dict]:
        """Every change ever made to a frozen enumeration, with its reason."""
        return [
            dict(r)
            for r in self.storage.query(
                "SELECT * FROM obligation_amendments ORDER BY id"
            )
        ]

    @staticmethod
    def _hydrate(r) -> Obligation:
        return Obligation(
            id=r["id"],
            contract_ref=r["contract_ref"],
            key=r["key"],
            kind=r["kind"],
            statement=r["statement"],
            created_at=r["created_at"],
            retired_at=r["retired_at"],
        )
