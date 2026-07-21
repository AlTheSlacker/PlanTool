"""finding-service (components:10).

Owns the red-team finding lifecycle from filing against specific rows through addressed,
accepted-risk, or withdrawn outcomes.

Contracts: contracts:33 file_finding, contracts:34 resolve_finding.

`dispute_finding` is not in the frozen plan. state_machines:7 needs `dispute` and
`uphold` events that no planned contract fires, which makes contracts:34's `withdrawn`
outcome unreachable — sm_cells:92 refuses to withdraw a finding that was never disputed.
See DEFECTS.md F13.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.errors import PlanToolError
from engine.models import RowRef
from engine.clock import now
from engine.idempotency import key
from engine.storage import FromOp, Op, Storage

# --- state_machines:7, the Finding lifecycle ---

FILED = "filed"
DISPUTED = "disputed"
ADDRESSED = "addressed"
ACCEPTED_RISK = "accepted_risk"

#: (state, event) -> next state, from sm_cells:90-109. Absent pairs are the
#: "impossible" cells.
_TRANSITIONS = {
    (FILED, "dispute"): DISPUTED,
    (FILED, "address"): ADDRESSED,
    (FILED, "accept_risk"): ACCEPTED_RISK,
    (DISPUTED, "uphold"): FILED,
    (DISPUTED, "withdraw"): ADDRESSED,
    (ACCEPTED_RISK, "dispute"): DISPUTED,
    (ACCEPTED_RISK, "address"): ADDRESSED,
}

_IMPOSSIBLE = {
    (FILED, "uphold"): "no dispute open",
    (FILED, "withdraw"): "no dispute open",
    (DISPUTED, "dispute"): "already disputed",
    (DISPUTED, "address"): "settle the dispute first",
    (DISPUTED, "accept_risk"): "settle the dispute first",
    (ACCEPTED_RISK, "uphold"): "no dispute open",
    (ACCEPTED_RISK, "withdraw"): "no dispute open",
    (ACCEPTED_RISK, "accept_risk"): "already accepted",
}

#: contracts:34 outcome -> the state_machines:7 event it fires.
_OUTCOME_EVENT = {
    "addressed": "address",
    "accepted_risk": "accept_risk",
    "withdrawn": "withdraw",
}

#: addressed is the only genuinely terminal state (sm_cells:100-104). accepted_risk can
#: still be disputed or addressed later, which is what keeps requirements:33's
#: "visible at handoff" from meaning "settled".
TERMINAL = (ADDRESSED,)

#: contracts:33 — unreadable plan state is itself filed as a finding.
INTEGRITY_KIND = "plan_unreadable"


class RefNotFound(PlanToolError):
    """contracts:33 — names the missing ref; findings must attack specific rows."""


class FindingNotFound(PlanToolError):
    """contracts:34 — names the missing id."""


class InvalidTransition(PlanToolError):
    """contracts:34 — outcome not reachable from the finding's state; state
    unchanged."""


@dataclass(frozen=True, slots=True)
class Finding:
    id: int
    refs: tuple[RowRef, ...]
    description: str
    severity: str
    state: str
    created_at: str
    outcome: str | None = None
    rationale: str | None = None
    dispute: str | None = None
    resolved_at: str | None = None

    @property
    def is_open(self) -> bool:
        """requirements:32 — anything not addressed and not explicitly accepted still
        counts against the verification gate."""
        return self.state not in (ADDRESSED, ACCEPTED_RISK)

    @property
    def visible_at_handoff(self) -> bool:
        """requirements:33 — an accepted risk is not a closed issue; it is a known one
        that the implementer has to be told about."""
        return self.state == ACCEPTED_RISK


class FindingService:
    def __init__(self, storage: Storage, rows=None):
        self.storage = storage
        self.rows = rows

    # --- contracts:33 ---

    def file_finding(
        self,
        refs: list[RowRef | str],
        description: str,
        severity: str,
        lease=None,
    ) -> Finding:
        """File a finding against the specific rows it attacks (requirements:31).

        The refs are mandatory and validated. A finding with no target is an opinion
        about the plan; a finding with a target is a claim that can be adjudicated,
        which is the only kind the verification gate can act on.
        """
        parsed = [RowRef.coerce(r) for r in refs]
        if not parsed:
            raise RefNotFound(
                "findings must attack specific rows; nothing filed"
            )
        if not description.strip():
            raise RefNotFound("a finding needs its description; nothing filed")
        if not severity.strip():
            raise RefNotFound("a finding needs a severity; nothing filed")
        for ref in parsed:
            if not self._row_exists(ref):
                raise RefNotFound("no such row; nothing filed", ref=str(ref))

        return self._insert(parsed, description, severity, lease)

    def file_integrity_finding(
        self, report, refs: list[RowRef | str] | None = None, lease=None
    ) -> Finding:
        """contracts:33 — unreadable plan state is itself filed as a finding.

        Separate from file_finding because it is the one case where ref validation
        cannot be the gate: the rows in question are precisely the ones that failed to
        read. Refusing to file would lose the only durable record that certification was
        refused, so the unreadable refs are recorded as given.
        """
        unreadable = [RowRef.coerce(r) for r in (refs or getattr(report, "unreadable", []))]
        description = (
            "plan state is unreadable, so certification is refused (requirements:30). "
            f"Unreadable: {', '.join(str(r) for r in unreadable) or 'unnamed rows'}."
        )
        return self._insert(unreadable, description, "blocking", lease)

    def _insert(
        self, refs: list[RowRef], description: str, severity: str, lease
    ) -> Finding:
        stamp = now()
        ops = [
            Op("insert", "findings", {
                "description": description,
                "severity": severity,
                "state": FILED,
                "created_at": stamp,
            }),
            *[
                Op("insert", "finding_refs",
                   {"finding_id": FromOp(0, "id"), "ref": str(ref)})
                for ref in refs
            ],
        ]
        receipt = self.storage.write_atomic(
            ops, key("file_finding", ",".join(str(r) for r in refs)), lease=lease
        )
        return self.get(receipt["results"][0]["id"])

    # --- contracts:34 ---

    def resolve_finding(
        self, finding_id: int, outcome: str, rationale: str, lease=None
    ) -> Finding:
        """Move a finding to a terminal outcome.

        requirements:33 — accepted_risk stays visible at implementation handoff, which
        is why `rationale` carries the owner's explicit acceptance rather than being
        optional. An accepted risk with no recorded acceptance is indistinguishable at
        handoff from an issue somebody forgot about.
        """
        if outcome not in _OUTCOME_EVENT:
            raise InvalidTransition(
                "outcome must be addressed|accepted_risk|withdrawn",
                finding_id=finding_id,
                outcome=outcome,
            )
        if not rationale.strip():
            raise InvalidTransition(
                "resolving a finding records why; for accepted_risk, the owner's "
                "explicit acceptance (requirements:33)",
                finding_id=finding_id,
                outcome=outcome,
            )
        return self._transition(
            finding_id,
            _OUTCOME_EVENT[outcome],
            {"outcome": outcome, "rationale": rationale, "resolved_at": now()},
            lease,
        )

    # --- DEFECTS.md F13: the contracts that fire state_machines:7's missing events ---

    def dispute_finding(self, finding_id: int, argument: str, lease=None) -> Finding:
        """Fire `dispute` (sm_cells:90): the finding's target argues it is wrong.

        Not in the frozen plan. Without it `withdraw` is unreachable, because sm_cells:92
        refuses to withdraw a finding that was never disputed — so contracts:34's
        `withdrawn` outcome could never be used.
        """
        if not argument.strip():
            raise InvalidTransition(
                "a dispute records the argument against the finding",
                finding_id=finding_id,
            )
        return self._transition(finding_id, "dispute", {"dispute": argument}, lease)

    def uphold_finding(self, finding_id: int, rationale: str, lease=None) -> Finding:
        """Fire `uphold` (sm_cells:96): the dispute failed; the finding stands.

        Not in the frozen plan — see dispute_finding. Returns the finding to `filed`,
        where it can be addressed, accepted or (having now been disputed once) withdrawn.
        """
        if not rationale.strip():
            raise InvalidTransition(
                "upholding a finding records why the dispute failed",
                finding_id=finding_id,
            )
        return self._transition(
            finding_id, "uphold", {"dispute": None, "rationale": rationale}, lease
        )

    def _transition(
        self, finding_id: int, event: str, values: dict, lease
    ) -> Finding:
        finding = self.get(finding_id)
        target = _TRANSITIONS.get((finding.state, event))
        if target is None:
            raise InvalidTransition(
                f"cannot {event} a finding in state {finding.state}: "
                f"{_IMPOSSIBLE.get((finding.state, event), 'terminal')}; "
                "state unchanged",
                finding_id=finding_id,
                state=finding.state,
                event=event,
            )
        self.storage.write_atomic(
            [Op("update", "findings", {"state": target, **values},
                where={"id": finding_id})],
            key("finding", finding_id, event),
            lease=lease,
        )
        return self.get(finding_id)

    # --- reads ---

    def get(self, finding_id: int) -> Finding:
        found = self.storage.query("SELECT * FROM findings WHERE id = ?", (finding_id,))
        if not found:
            raise FindingNotFound("no such finding", finding_id=finding_id)
        r = dict(found[0])
        refs = tuple(
            RowRef.parse(x["ref"])
            for x in self.storage.query(
                "SELECT ref FROM finding_refs WHERE finding_id = ? ORDER BY ref",
                (finding_id,),
            )
        )
        return Finding(
            id=r["id"],
            refs=refs,
            description=r["description"],
            severity=r["severity"],
            state=r["state"],
            created_at=r["created_at"],
            outcome=r["outcome"],
            rationale=r["rationale"],
            dispute=r["dispute"],
            resolved_at=r["resolved_at"],
        )

    def open_findings(self) -> list[Finding]:
        """requirements:32 — these fail the verification gate."""
        rows = self.storage.query(
            "SELECT id FROM findings WHERE state NOT IN (?, ?) ORDER BY id",
            (ADDRESSED, ACCEPTED_RISK),
        )
        return [self.get(r["id"]) for r in rows]

    def accepted_risks(self) -> list[Finding]:
        """requirements:33 — visible at implementation handoff."""
        rows = self.storage.query(
            "SELECT id FROM findings WHERE state = ? ORDER BY id", (ACCEPTED_RISK,)
        )
        return [self.get(r["id"]) for r in rows]

    def findings_for(self, ref: RowRef | str) -> list[Finding]:
        rows = self.storage.query(
            "SELECT finding_id FROM finding_refs WHERE ref = ?",
            (str(RowRef.coerce(ref)),),
        )
        return [self.get(r["finding_id"]) for r in rows]

    def _row_exists(self, ref: RowRef) -> bool:
        return bool(self.storage.query(
            "SELECT 1 FROM plan_rows WHERE table_name = ? AND ordinal = ?",
            (ref.table, ref.ordinal),
        ))
