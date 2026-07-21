"""conflict-service (components:8).

Records contradictions between rows or against new input, blocks dependent gates while
open, and captures the owner's adjudication permanently.

Contracts: contracts:26 raise_conflict, contracts:27 resolve_conflict, contracts:28
blocking_conflicts.

This module also supplies the contradiction detector that row-service takes as a
pluggable argument (DEFECTS.md F4). The detector is deliberately *mechanical*: the
frozen plan never says how contradiction is determined, and the design spine says the
tool records judgment rather than exercising it. So the driving session declares a
contradiction by giving the submitted row a `contradicts` edge, and the tool enforces
the accounting requirements:27 demands — that a conflict naming the contested row was
raised and presented before the offending row could be filed. See DEFECTS.md F8.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.errors import PlanToolError
from engine.models import RowRef, RowSubmission
from engine.clock import now
from engine.storage import FromOp, Op, Storage

#: The edge type by which a submitted row declares what it contradicts.
CONTRADICTS = "contradicts"

OPEN = "open"
RESOLVED_OVERRIDDEN = "resolved_overridden"
RESOLVED_REVISED = "resolved_revised"

#: state_machines:4 — outcome -> resting state.
_OUTCOME_STATE = {"overridden": RESOLVED_OVERRIDDEN, "revised": RESOLVED_REVISED}


class RefNotFound(PlanToolError):
    """contracts:26 — a contested ref does not exist; names it; nothing filed."""


class ConflictNotFound(PlanToolError):
    """contracts:27 — names the missing id."""


class AlreadyResolved(PlanToolError):
    """contracts:27 — resolved conflicts are permanent audit records.

    Re-adjudication requires a new conflict: overwriting the outcome would erase the
    override that requirements:29 keeps permanently visible.
    """


class PlanUnreadable(PlanToolError):
    """contracts:28 — integrity path."""


@dataclass(frozen=True, slots=True)
class Conflict:
    id: int
    refs: tuple[RowRef, ...]
    description: str
    recommendation: str
    state: str
    created_at: str
    outcome: str | None = None
    adjudication: str | None = None
    resolved_at: str | None = None

    @property
    def is_open(self) -> bool:
        return self.state == OPEN

    def blockage_reason(self) -> str:
        """contracts:28 — the reason a gate is blocked, displayable as-is."""
        contested = ", ".join(str(r) for r in self.refs)
        return (
            f"conflict #{self.id} is open and contests {contested}: {self.description} "
            f"— recommendation: {self.recommendation}"
        )


@dataclass(frozen=True, slots=True)
class ConflictResolution:
    """contracts:27 — outcome and challenge text recorded permanently."""

    conflict: Conflict
    outcome: str
    adjudication: str
    resolved_at: str


@dataclass(frozen=True, slots=True)
class GateScope:
    """contracts:28 — the rows a gate depends on.

    Expressed as tables plus explicit refs rather than a materialized ref list: a gate's
    dependency is "every live row in these tables", and that set changes between the
    moment the scope is built and the moment the gate reads it.
    """

    tables: tuple[str, ...] = ()
    refs: tuple[RowRef, ...] = ()

    def covers(self, ref: RowRef) -> bool:
        return ref.table in self.tables or ref in self.refs


class ConflictService:
    def __init__(self, storage: Storage, rows=None):
        self.storage = storage
        self.rows = rows

    # --- contracts:26 ---

    def raise_conflict(
        self,
        refs: list[RowRef | str],
        description: str,
        recommendation: str,
        lease=None,
    ) -> Conflict:
        """File a conflict in the open state; dependent gates block while it is open.

        use_cases:7 step 1 — raised *before* the offending row is filed, presenting both
        sides with the engineering recommendation. Both are required: a conflict with no
        recommendation is an unanswerable question put to the owner.
        """
        parsed = [RowRef.coerce(r) for r in refs]
        if not parsed:
            raise RefNotFound("a conflict must contest at least one row")
        if not description.strip() or not recommendation.strip():
            raise RefNotFound(
                "a conflict presents both sides and an engineering recommendation "
                "(use_cases:7); neither may be empty"
            )
        for ref in parsed:
            if not self._row_exists(ref):
                raise RefNotFound(
                    "a contested row does not exist; nothing filed", ref=str(ref)
                )

        stamp = now()
        # One transaction: a conflict whose contested refs failed to land would be an
        # open conflict that silently blocks nothing. FromOp borrows the id the insert
        # assigns mid-transaction.
        ops = [
            Op("insert", "conflicts", {
                "description": description,
                "recommendation": recommendation,
                "state": OPEN,
                "created_at": stamp,
            }),
            *[
                Op("insert", "conflict_refs",
                   {"conflict_id": FromOp(0, "id"), "ref": str(ref)})
                for ref in parsed
            ],
        ]
        receipt = self.storage.write_atomic(
            ops, f"conflict:{stamp}:{','.join(str(r) for r in parsed)}", lease=lease
        )
        return self.get(receipt["results"][0]["id"])

    # --- contracts:27 ---

    def resolve_conflict(
        self, conflict_id: int, outcome: str, adjudication: str, lease=None
    ) -> ConflictResolution:
        """Record the owner's adjudication permanently.

        uc_extensions:26 — the owner may override the engineering recommendation; that
        is allowed, and the override stays permanently visible on the record. Which is
        why `adjudication` is mandatory rather than optional: an override with no quoted
        reasoning is exactly the thing a future reader needs and cannot reconstruct.
        """
        if outcome not in _OUTCOME_STATE:
            raise ConflictNotFound(
                "outcome must be 'overridden' or 'revised'",
                conflict_id=conflict_id,
                outcome=outcome,
            )
        if not adjudication.strip():
            raise ConflictNotFound(
                "a resolution records the owner's decision verbatim (requirements:29)",
                conflict_id=conflict_id,
            )
        conflict = self.get(conflict_id)
        if not conflict.is_open:
            raise AlreadyResolved(
                "resolved conflicts are permanent audit records; re-adjudication "
                "requires a new conflict",
                conflict_id=conflict_id,
                state=conflict.state,
            )

        stamp = now()
        self.storage.write_atomic(
            [Op("update", "conflicts", {
                "state": _OUTCOME_STATE[outcome],
                "outcome": outcome,
                "adjudication": adjudication,
                "resolved_at": stamp,
            }, where={"id": conflict_id})],
            f"resolve_conflict:{conflict_id}",
            lease=lease,
        )
        return ConflictResolution(
            conflict=self.get(conflict_id),
            outcome=outcome,
            adjudication=adjudication,
            resolved_at=stamp,
        )

    # --- contracts:28 ---

    def blocking_conflicts(self, scope: GateScope) -> list[Conflict]:
        """Open conflicts contesting rows in scope, with the blockage reason
        displayable (requirements:28)."""
        integrity = self.storage.integrity_check()
        if integrity.unreadable:
            raise PlanUnreadable(
                "underlying rows failed integrity; recover before gating",
                unreadable=list(integrity.unreadable),
            )
        return [
            conflict
            for conflict in self.open_conflicts()
            if any(scope.covers(ref) for ref in conflict.refs)
        ]

    # --- reads ---

    def get(self, conflict_id: int) -> Conflict:
        found = self.storage.query(
            "SELECT * FROM conflicts WHERE id = ?", (conflict_id,)
        )
        if not found:
            raise ConflictNotFound("no such conflict", conflict_id=conflict_id)
        return self._build(dict(found[0]))

    def open_conflicts(self) -> list[Conflict]:
        return [
            self._build(dict(r))
            for r in self.storage.query(
                "SELECT * FROM conflicts WHERE state = ? ORDER BY id", (OPEN,)
            )
        ]

    def conflicts_for(self, ref: RowRef | str) -> list[Conflict]:
        rows = self.storage.query(
            "SELECT conflict_id FROM conflict_refs WHERE ref = ?",
            (str(RowRef.coerce(ref)),),
        )
        return [self.get(r["conflict_id"]) for r in rows]

    def _build(self, record: dict) -> Conflict:
        refs = tuple(
            RowRef.parse(r["ref"])
            for r in self.storage.query(
                "SELECT ref FROM conflict_refs WHERE conflict_id = ? ORDER BY ref",
                (record["id"],),
            )
        )
        return Conflict(
            id=record["id"],
            refs=refs,
            description=record["description"],
            recommendation=record["recommendation"],
            state=record["state"],
            created_at=record["created_at"],
            outcome=record["outcome"],
            adjudication=record["adjudication"],
            resolved_at=record["resolved_at"],
        )

    def _row_exists(self, ref: RowRef) -> bool:
        return bool(self.storage.query(
            "SELECT 1 FROM plan_rows WHERE table_name = ? AND ordinal = ?",
            (ref.table, ref.ordinal),
        ))

    # --- the contradiction detector row-service plugs in (DEFECTS.md F4/F8) ---

    def detector(self):
        """A ContradictionDetector enforcing requirements:27 mechanically.

        The submitted row declares what it contradicts with a `contradicts` edge. Filing
        is refused until a conflict naming that contested row has been raised — open or
        resolved, since the requirement is that the conflict was *raised and presented*,
        not that it was settled first (uc_extensions:25 keeps deferred conflicts open
        precisely so work can continue around them).

        A `contradicts` edge to an unknown row is not the detector's business: link
        validation is row-service's, and it rejects the row on its own terms.
        """

        def detect(submission: RowSubmission, service) -> str | None:
            for link in submission.links:
                if link.edge_type != CONTRADICTS or link.is_intra_batch:
                    continue
                target = RowRef.coerce(link.target)
                if not self._row_exists(target):
                    continue
                if not self.conflicts_for(target):
                    return (
                        f"this row declares that it contradicts {target}, but no "
                        f"conflict contesting {target} has been raised. Raise it with "
                        "both sides and your engineering recommendation, present it to "
                        "the owner, then re-submit."
                    )
            return None

        return detect
