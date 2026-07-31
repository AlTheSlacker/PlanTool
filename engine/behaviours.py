"""The behaviour surface (DEVIATIONS.md D12, fixing DEFECTS.md F23).

Not in the frozen plan. A **behaviour** is one dischargeable commitment of a contract: the
main effect of its signature, or one of its enumerated error conditions. It is the accounting
denominator that `contracts:62` assumes and the plan never defines. It was called an
*obligation* until v3 change 1 — same machinery, plainer word (D16).

F23 is what makes this necessary. A check that runs, passes, and means nothing is worse than
a missing one, because it reports success, and `requirements:37`'s "silent trimming of
relevant content is not a remedy" had no enforcement at all without a denominator.

**Where the set comes from is what carries the design.** It is enumerated by the *planning
session* and frozen at finalization. Two alternatives were rejected (D12):

- *The tool derives it by parsing the contract row.* Rejected on the design spine — the tool
  records judgment, it never exercises it (`decisions:12`) — and on fact: `plan_rows.content`
  is free-form JSON with no per-table schema, so a contract's enumerated errors are a
  methodology convention rather than a storage guarantee.
- *The session declares it at the moment it is measured.* Rejected: it hands the denominator
  to the party being audited, which is precisely how `findings:18` was gamed.

`enumerate_from_row` below reads an explicit `behaviours` array off the contract row. That is
**not** the rejected first option: the array is a declaration the planning session wrote, not
an inference the tool drew from prose. The distinction is exactly whether the tool is reading
a judgment or making one — and it is why a contract row with no `behaviours` array yields an
empty set rather than a guess. An empty set means *not yet enumerated*, and every consumer
refuses loudly rather than passing vacuously. That is the whole lesson of F23.

**`kind` is `effect | error` and the main one is keyed `effect`**, not `behaviour`. A
`Behaviour` row of kind "behaviour" whose ref reads `contracts:40#behaviour` is one word doing
two jobs, which is the same disease as two words doing one; `effect`/`error` is the pair
`INTERVIEW.md` §4 already uses to say what a behaviour list contains.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.errors import PlanToolError
from engine.clock import now
from engine.idempotency import key
from engine.storage import FromOp, Op, Storage

EFFECT = "effect"
ERROR = "error"
KINDS = (EFFECT, ERROR)

#: The key of the behaviour every contract has: doing what its signature says.
PRIMARY = "effect"


class NotEnumerated(PlanToolError):
    """The task has no frozen behaviour surface, so there is no denominator to account
    against. Refused rather than passed vacuously — DEFECTS.md F23."""


class AmendmentNeedsReason(PlanToolError):
    """D12 — a frozen enumeration can be corrected, but never silently. Same friction shape
    as requirements:79's waiver log and D8's promotion reason."""


@dataclass(frozen=True, slots=True)
class Behaviour:
    id: int
    contract_ref: str
    key: str
    kind: str
    statement: str
    created_at: str = ""
    retired_at: str | None = None

    @property
    def ref(self) -> str:
        """How a behaviour is named in evidence maps and coverage errors."""
        return f"{self.contract_ref}#{self.key}"


@dataclass(frozen=True, slots=True)
class BehaviourSpec:
    """What a planning session enumerates. Deliberately dumb: a key, a kind, a statement."""

    key: str
    kind: str
    statement: str


class BehaviourService:
    def __init__(self, storage: Storage):
        self.storage = storage

    # --- enumeration, at finalization ---

    def enumerate_from_row(self, content: dict) -> list[BehaviourSpec]:
        """Read the behaviour surface a planning session declared on a contract row.

        Accepts either a list of strings (each becomes an effect behaviour keyed by its
        position) or a list of objects with `key`/`kind`/`statement`. Anything else is
        ignored rather than interpreted: a malformed declaration is *not enumerated*, which
        every consumer then refuses on, and that is the safe direction.
        """
        declared = content.get("behaviours")
        if not isinstance(declared, list):
            return []
        specs: list[BehaviourSpec] = []
        for i, item in enumerate(declared):
            if isinstance(item, str):
                specs.append(BehaviourSpec(
                    key=PRIMARY if i == 0 else f"b{i}", kind=EFFECT, statement=item
                ))
            elif isinstance(item, dict) and item.get("statement"):
                kind = item.get("kind", EFFECT)
                specs.append(BehaviourSpec(
                    key=str(item.get("key") or f"b{i}"),
                    kind=kind if kind in KINDS else EFFECT,
                    statement=str(item["statement"]),
                ))
        return specs

    def freeze_ops(
        self,
        contract_ref: str,
        specs: list[BehaviourSpec],
        task_id: int | FromOp,
        base_index: int = 0,
    ) -> list[Op]:
        """Ops that freeze `specs` against `contract_ref` and vest them in `task_id`.

        Returned as ops rather than written directly so finalization stays one atomic act: a
        plan half-enumerated is a plan whose accounting is silently partial.

        `base_index` is where these ops will sit in the caller's final batch. `FromOp`
        indexes are absolute within the batch storage applies, so a helper that emits a
        *fragment* has to be told its offset — there is no way to borrow an id relatively.
        """
        stamp = now()
        ops: list[Op] = []
        for spec in specs:
            ops.append(Op("insert", "behaviours", {
                "contract_ref": contract_ref,
                "key": spec.key,
                "kind": spec.kind,
                "statement": spec.statement,
                "created_at": stamp,
            }))
            ops.append(Op("insert", "behaviour_ownership", {
                "behaviour_id": FromOp(base_index + len(ops) - 1, "id"),
                "task_id": task_id,
                "created_at": stamp,
            }))
        return ops

    # --- reads ---

    def for_task(self, task_id: int) -> tuple[Behaviour, ...]:
        """The behaviours this task currently owes. Live ownership of live behaviours —
        the set `verify_completion` must account for in full."""
        return tuple(
            self._hydrate(r)
            for r in self.storage.query(
                "SELECT b.* FROM behaviours b "
                "JOIN behaviour_ownership w ON w.behaviour_id = b.id "
                "WHERE w.task_id = ? AND w.superseded_at IS NULL "
                "AND b.retired_at IS NULL ORDER BY b.id",
                (task_id,),
            )
        )

    def of_contract(self, contract_ref: str) -> tuple[Behaviour, ...]:
        return tuple(
            self._hydrate(r)
            for r in self.storage.query(
                "SELECT * FROM behaviours WHERE contract_ref = ? AND retired_at IS NULL "
                "ORDER BY id",
                (contract_ref,),
            )
        )

    def require_enumerated(self, task_id: int, action: str) -> tuple[Behaviour, ...]:
        """Fetch the surface, refusing loudly when there is none.

        D12's accepted cost: tasks derived before the behaviour surface existed have none
        recorded. The graph refuses to verify such a node rather than silently permitting an
        unaccountable one. A missing denominator must fail, not pass.
        """
        behaviours = self.for_task(task_id)
        if not behaviours:
            raise NotEnumerated(
                f"task {task_id} has no frozen behaviour surface, so there is "
                f"nothing to account {action} against. Enumerate the contract's "
                "behaviours (its main effect and each error condition) and "
                "re-finalize, or amend the enumeration with a recorded reason.",
                task_id=task_id,
                action=action,
            )
        return behaviours

    # --- amendment, the recorded escape hatch ---

    def amend(
        self,
        contract_ref: str,
        action: str,
        reason: str,
        behaviour_id: int | None = None,
        spec: BehaviourSpec | None = None,
        task_id: int | None = None,
    ) -> None:
        """Correct a frozen enumeration, on the record.

        D12: the accounting can be changed, but not silently. The reason is mandatory and
        the amendment log is the owner's review surface — gaming the accounting should
        require lying in a log the owner reads (`requirements:79`'s shape).
        """
        if not reason.strip():
            raise AmendmentNeedsReason(
                f"amending the frozen behaviour surface of {contract_ref} changes the "
                "denominator a completion is measured against; record why",
                contract_ref=contract_ref,
                action=action,
            )
        stamp = now()
        ops: list[Op] = []
        if action == "retired":
            ops.append(Op("update", "behaviours", {"retired_at": stamp},
                          where={"id": behaviour_id}))
        elif action == "added":
            if spec is None or task_id is None:
                raise AmendmentNeedsReason(
                    "adding a behaviour needs both the behaviour and the task that "
                    "will owe it; an unowned behaviour is one nothing can discharge",
                    contract_ref=contract_ref,
                )
            ops.extend(self.freeze_ops(contract_ref, [spec], task_id))
        ops.append(Op("insert", "behaviour_amendments", {
            "behaviour_id": behaviour_id,
            "contract_ref": contract_ref,
            "action": action,
            "reason": reason,
            "created_at": stamp,
        }))
        self.storage.write_atomic(ops, key("amend", contract_ref, action, behaviour_id or 0))

    def amendments(self) -> list[dict]:
        """Every change ever made to a frozen enumeration, with its reason."""
        return [
            dict(r)
            for r in self.storage.query(
                "SELECT * FROM behaviour_amendments ORDER BY id"
            )
        ]

    @staticmethod
    def _hydrate(r) -> Behaviour:
        return Behaviour(
            id=r["id"],
            contract_ref=r["contract_ref"],
            key=r["key"],
            kind=r["kind"],
            statement=r["statement"],
            created_at=r["created_at"],
            retired_at=r["retired_at"],
        )
