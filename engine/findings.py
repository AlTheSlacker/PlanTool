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
from engine.methodology import Methodology, load
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


class InvalidAllocation(PlanToolError):
    """D15 — `resolve_by` is not a package gate, or a reallocation does not move the
    finding to a strictly later one; the allocation is unchanged."""


@dataclass(frozen=True, slots=True)
class Finding:
    id: int
    refs: tuple[RowRef, ...]
    #: What the finding says, in a few words. Required, because `findings:N` is an address
    #: and D19 forbids an address travelling without the name of what it addresses.
    name: str
    description: str
    severity: str
    state: str
    #: D15 — the package gate that must not pass while this finding is open. NOT NULL, set
    #: at filing. It is the answer to "by when", made mechanical: the gate is the deadline.
    resolve_by: int
    created_at: str
    outcome: str | None = None
    rationale: str | None = None
    dispute: str | None = None
    resolved_at: str | None = None

    #: The table a finding is addressed under. One constant rather than the string spelled
    #: in four places, because this is exactly the word F38 found in two stores at once.
    TABLE = "findings"

    @property
    def ref(self) -> RowRef:
        """`findings:N` — a finding is addressable, and its id is the ordinal.

        Addressing was never the property that made something a plan row; `table:ordinal`
        is a naming scheme, and what it needs is somebody able to resolve it. That is the
        whole of why findings can stay in their own store and still be cited (D22).
        """
        return RowRef(self.TABLE, self.id)

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
    #: The table findings are addressed under, read by the door's resolver. Held here, and
    #: nowhere else, so the address space has one owner (D22).
    TABLE = Finding.TABLE

    def __init__(self, storage: Storage, rows=None, methodology: Methodology | None = None):
        self.storage = storage
        self.rows = rows
        #: The package set, so `resolve_by` can be validated against gates that exist and
        #: an integrity finding can be allocated to the terminal one. Loaded, not hard-coded:
        #: the range is the methodology's to declare, not this module's to assume.
        self.methodology = methodology or load()

    # --- contracts:33 ---

    def file_finding(
        self,
        refs: list[RowRef | str],
        description: str,
        severity: str,
        name: str,
        resolve_by: int,
    ) -> Finding:
        """File a finding against the specific rows it attacks (requirements:31).

        The refs are mandatory and validated. A finding with no target is an opinion
        about the plan; a finding with a target is a claim that can be adjudicated,
        which is the only kind the verification gate can act on.

        `name` is not in `contracts:33` and is a deviation (D22). The contract predates the
        rule that an address never travels without a name, and `findings:N` is an address:
        it appears in gate holes, in the resume digest, and in the owner's own prose. A
        session that already wrote the description can write the six-word version of it, and
        the tool cannot — deriving the name from the description is the guess D19 exists to
        remove.

        `resolve_by` is D15 (M6_PLAN.md §2.6), also a deviation from `contracts:33`. It is
        the package gate that must not pass while the finding is open, required here because
        an item with no gate to answer to is one only finalization catches — the pile-up the
        allocation scheme exists to break up. Which gate is a judgement (`decisions:12`): the
        tool checks the gate exists and records the choice; it does not choose it.
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
        if not name or not name.strip():
            raise RefNotFound(
                "every finding needs a name: what it says, in a few words. The finding is "
                "addressed as findings:N, and an address on its own makes the reader go "
                "and look it up — so the name is what gets shown and the address rides "
                "alongside it"
            )
        self._check_package(resolve_by, "resolve_by")
        for ref in parsed:
            if not self._row_exists(ref):
                raise RefNotFound("no such row; nothing filed", ref=str(ref))

        return self._insert(parsed, description, severity, name, resolve_by)

    def _check_package(self, package: int, field: str) -> None:
        low, high = self.methodology.package_range
        if isinstance(package, bool) or not isinstance(package, int) or not low <= package <= high:
            raise InvalidAllocation(
                f"{field} must be a package gate in {low}-{high}; nothing filed",
                **{field: repr(package)},
            )

    def file_integrity_finding(
        self, report, refs: list[RowRef | str] | None = None
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
        # The one finding the tool names itself, because the tool is the one filing it.
        # Allocated to the terminal gate: an unreadable plan already refuses every gate
        # (run_gate raises PlanUnreadable before evaluating), so the allocation is a formality
        # — the terminal package is the honest home for "must be gone before freeze".
        return self._insert(
            unreadable, description, "blocking", "plan state is unreadable",
            self.methodology.package_range[1],
        )

    def _insert(
        self, refs: list[RowRef], description: str, severity: str, name: str,
        resolve_by: int,
    ) -> Finding:
        stamp = now()
        ops = [
            Op("insert", "findings", {
                "name": name,
                "description": description,
                "severity": severity,
                "state": FILED,
                "resolve_by": resolve_by,
                "created_at": stamp,
            }),
            *[
                Op("insert", "finding_refs",
                   {"finding_id": FromOp(0, "id"), "ref": str(ref)})
                for ref in refs
            ],
        ]
        receipt = self.storage.write_atomic(
            ops, key("file_finding", ",".join(str(r) for r in refs))
        )
        return self.get(receipt["results"][0]["id"])

    # --- contracts:34 ---

    def resolve_finding(
        self, finding_id: int, outcome: str, rationale: str
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
        )

    # --- D15's second exit: defer to a later gate, on the record ---

    def reallocate_finding(
        self, finding_id: int, resolve_by: int, reason: str
    ) -> Finding:
        """Move an open finding's gate allocation to a strictly later package, with a reason.

        The one legitimate alternative to resolving a finding at its gate: it genuinely
        belongs to a later package sometimes. But deferral is exactly where "we'll get to
        it" quietly becomes "we never did", so it costs a reason the owner reads and leaves
        a row in `finding_reallocations` — the accounting can move, never silently.

        Only an *open* finding can be re-allocated: a resolved one has left the scheme, and
        moving its deadline forward would be recording a deadline for something already done.
        And only *forward*: an earlier gate has either passed or is where the finding should
        have been answered, so re-allocating backward is not a deferral at all.
        """
        finding = self.get(finding_id)
        if not finding.is_open:
            raise InvalidAllocation(
                "only an open finding is allocated to a gate; this one is "
                f"{finding.state} and has left the scheme",
                finding_id=finding_id,
                state=finding.state,
            )
        self._check_package(resolve_by, "resolve_by")
        if resolve_by <= finding.resolve_by:
            raise InvalidAllocation(
                "a reallocation defers to a *later* gate; this finding is already "
                f"allocated to package {finding.resolve_by}",
                finding_id=finding_id,
                current=finding.resolve_by,
                requested=resolve_by,
            )
        if not reason.strip():
            raise InvalidAllocation(
                "deferring a finding to a later gate records why; nothing changed",
                finding_id=finding_id,
            )
        stamp = now()
        self.storage.write_atomic(
            [
                Op("update", "findings", {"resolve_by": resolve_by},
                   where={"id": finding_id}),
                Op("insert", "finding_reallocations", {
                    "finding_id": finding_id,
                    "from_package": finding.resolve_by,
                    "to_package": resolve_by,
                    "reason": reason,
                    "created_at": stamp,
                }),
            ],
            key("reallocate_finding", finding_id, resolve_by),
        )
        return self.get(finding_id)

    # --- DEFECTS.md F13: the contracts that fire state_machines:7's missing events ---

    def dispute_finding(self, finding_id: int, argument: str) -> Finding:
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
        return self._transition(finding_id, "dispute", {"dispute": argument})

    def uphold_finding(self, finding_id: int, rationale: str) -> Finding:
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
            finding_id, "uphold", {"dispute": None, "rationale": rationale}
        )

    def _transition(
        self, finding_id: int, event: str, values: dict
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
            name=r["name"],
            description=r["description"],
            severity=r["severity"],
            state=r["state"],
            resolve_by=r["resolve_by"],
            created_at=r["created_at"],
            outcome=r["outcome"],
            rationale=r["rationale"],
            dispute=r["dispute"],
            resolved_at=r["resolved_at"],
        )

    def all_findings(self) -> list[Finding]:
        """Every finding, oldest first. What the package-7 gate counts and checks."""
        return [
            self.get(r["id"])
            for r in self.storage.query("SELECT id FROM findings ORDER BY id")
        ]

    def find(self, ref: RowRef | str) -> Finding | None:
        """The finding an address names, or None. The door's lookup for `findings:N`."""
        ref = RowRef.coerce(ref)
        if ref.table != Finding.TABLE:
            return None
        try:
            return self.get(ref.ordinal)
        except FindingNotFound:
            return None

    def open_findings(self) -> list[Finding]:
        """requirements:32 — these fail the verification gate."""
        rows = self.storage.query(
            "SELECT id FROM findings WHERE state NOT IN (?, ?) ORDER BY id",
            (ADDRESSED, ACCEPTED_RISK),
        )
        return [self.get(r["id"]) for r in rows]

    def open_allocated_to(self, package: int) -> list[Finding]:
        """D15 — open findings whose gate is `package`. What locks that gate.

        `is_open` is `state NOT IN (addressed, accepted_risk)`: an accepted risk is a
        settled decision the owner made and does not lock anything, which is what keeps
        `requirements:33`'s "visible at handoff" from meaning "still blocking".
        """
        rows = self.storage.query(
            "SELECT id FROM findings "
            "WHERE resolve_by = ? AND state NOT IN (?, ?) ORDER BY id",
            (package, ADDRESSED, ACCEPTED_RISK),
        )
        return [self.get(r["id"]) for r in rows]

    def reallocations_of(self, finding_id: int) -> list[dict]:
        """The deferral history of a finding, oldest first — the owner's review surface."""
        return [
            dict(r)
            for r in self.storage.query(
                "SELECT from_package, to_package, reason, created_at "
                "FROM finding_reallocations WHERE finding_id = ? ORDER BY id",
                (finding_id,),
            )
        ]

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
