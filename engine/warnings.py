"""warning-service (components:7).

Owns the warning lifecycle under decisions:31's keep-pushing policy: re-present until
resolved or suppressed, and resurface suppressed warnings at critical points.

Contracts: contracts:23 active_warnings, contracts:24 suppress_warning, contracts:25
resolve_warning.

The plan specifies the whole lifecycle but names no contract that *raises* a warning
(DEFECTS.md F9 — the fourth instance of "behaviour named in prose without the mechanism
that produces it"). `raise_warning` is invented here. It is idempotent on a stable
warning key, which is what makes re-presentation work: the same open gap seen at three
successive gates is one warning re-presented, not three warnings accumulating.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from engine.door import Verbatim
from engine.errors import PlanToolError
from engine.models import RowRef
from engine.clock import now
from engine.idempotency import key
from engine.storage import Op, Storage

ACTIVE = "active"
SUPPRESSED = "suppressed"
RESOLVED = "resolved"

OPEN_GAP = "open_gap"
UNRESOLVED_ASSUMPTION = "unresolved_assumption"
#: A live row using a retired word. Its own kind, not folded into open_gap: it settles when
#: the glossary changes or the row is superseded — a different lifecycle — and a shared kind
#: would leave one settling rule guessing at two conditions.
RETIRED_TERM = "retired_term"

#: The warning kinds whose active/settled state mirrors a condition the gap-engine computes,
#: rather than being owned here: an open gap, an unresolved assumption, a retired-word use.
#: Their state must never be read stale, so `active_warnings` reconciles them against the
#: live derivation (`GapEngine.live_warning_keys`) before returning, and the gate settles
#: them for real from the *same* derivation, so read and gate cannot disagree (DEFECTS.md
#: F50). Every other kind owns its own lifecycle and is passed through untouched.
SETTLEABLE_KINDS = frozenset({OPEN_GAP, UNRESOLVED_ASSUMPTION, RETIRED_TERM})


class CriticalPoint(StrEnum):
    """contracts:23 / requirements:23 — where a suppressed warning still resurfaces.

    REVISION is requirements:55's re-adjudication point: a revision touching a
    suppressed warning must put it back in front of the owner.
    """

    FINALIZATION = "finalization"
    RED_TEAM_ENTRY = "red_team_entry"
    HANDOFF = "handoff"
    REVISION = "revision"


class WarningNotFound(PlanToolError):
    """contracts:24/25 — names the missing id."""


class AlreadyResolved(PlanToolError):
    """contracts:24 — resolved warnings need no suppression; nothing written."""


class PlanUnreadable(PlanToolError):
    """contracts:23 — integrity path."""


@dataclass(frozen=True, slots=True)
class Warning:
    id: int
    warning_key: str
    kind: str
    message: str
    state: str
    created_at: str
    source_ref: RowRef | None = None
    reason: str | None = None
    resolved_by: RowRef | None = None
    #: True when this warning is only being shown because a critical point was reached.
    resurfaced: bool = False

    def present(self) -> str:
        """The line the agent re-presents. A suppressed warning surfacing at a critical
        point says so, or it reads as the tool having forgotten the suppression."""
        if self.resurfaced:
            return (
                f"[suppressed, resurfaced] {self.message} "
                f"(suppressed because: {self.reason})"
            )
        return self.message

    def present_lines(self, display=str) -> list:
        # The message is re-presented stored prose — most warnings carry a gap ask that
        # quotes a row or a definition — so it is Verbatim, annotated rather than rejected
        # when it names an address (DEFECTS.md F49). No composed ref of its own to display.
        return [Verbatim(self.present())]


class WarningService:
    def __init__(self, storage: Storage, live_warning_keys=None):
        self.storage = storage
        #: Optional callable returning the set of warning keys whose mirrored condition is
        #: still live — the gap-engine owns that derivation and this is bound to its
        #: `live_warning_keys`. When set, `active_warnings` reconciles the settleable kinds
        #: against it so a reader never sees a warning whose condition cleared between gates
        #: (DEFECTS.md F50). Left None in isolation (the unit tests), where there is no plan
        #: state to mirror and the raw ledger is exactly what is under test. Late-bound in
        #: the surface, because the gap-engine is built after this service; matches
        #: `terms.rows = rows` there.
        self.live_warning_keys = live_warning_keys

    # --- raising (invented; DEFECTS.md F9) ---

    def raise_warning(
        self,
        warning_key: str,
        kind: str,
        message: str,
        source_ref: RowRef | str | None = None,
    ) -> Warning:
        """Ensure a warning exists for this key, and refresh its wording.

        Idempotent by key. A warning the owner has already suppressed is *not* dragged
        back to active by being re-raised — that would make suppression meaningless, and
        decisions:31 gives suppressed warnings a defined resurfacing rule instead.
        Likewise a resolved warning stays resolved unless the condition is re-raised
        after the resolving row itself changed, which shows up as a new key.
        """
        existing = self._by_key(warning_key)
        stamp = now()
        if existing is None:
            self.storage.write_atomic(
                [Op("insert", "warnings", {
                    "warning_key": warning_key,
                    "kind": kind,
                    "message": message,
                    "source_ref": str(source_ref) if source_ref else None,
                    "state": ACTIVE,
                    "created_at": stamp,
                    "updated_at": stamp,
                })],
                key("raise_warning", warning_key),
            )
            return self._require_key(warning_key)

        if existing.message != message and existing.state == ACTIVE:
            self.storage.write_atomic(
                [Op("update", "warnings", {"message": message, "updated_at": stamp},
                    where={"id": existing.id})],
                key("reword_warning", existing.id, message),
            )
            return self._require_key(warning_key)
        return existing

    # --- contracts:23 ---

    def active_warnings(
        self, context: CriticalPoint | str | None = None
    ) -> list[Warning]:
        """Unresolved warnings; at a critical point, suppressed ones come too.

        requirements:22 — this is the call a package open and every gate invocation makes,
        which is what "re-present until resolved or suppressed" amounts to mechanically.
        """
        integrity = self.storage.integrity_check()
        if integrity.unreadable:
            raise PlanUnreadable(
                "underlying rows failed integrity; recover before warning",
                unreadable=list(integrity.unreadable),
            )
        warnings = [
            self._build(dict(r))
            for r in self.storage.query(
                "SELECT * FROM warnings WHERE state = ? ORDER BY id", (ACTIVE,)
            )
        ]
        if context is None:
            return self._reconcile(warnings)

        CriticalPoint(context)  # rejects an unknown point rather than silently
        resurfaced = [
            self._build(dict(r), resurfaced=True)
            for r in self.storage.query(
                "SELECT * FROM warnings WHERE state = ? ORDER BY id", (SUPPRESSED,)
            )
        ]
        return self._reconcile(warnings + resurfaced)

    def _reconcile(self, warnings: list[Warning]) -> list[Warning]:
        """Drop any settleable warning whose mirrored condition no longer holds.

        The gate settles these for real (writing the audit note and retiring the row); this
        keeps a reader between gates from seeing one the condition has already cleared —
        the F50 defect, where `plan_status` still nagged about terms the owner had just
        settled while its own gap count had dropped them. Read-only: it filters what is
        returned, never writes, so a status read stays a read. A warning of any other kind,
        or one whose condition is still live, passes straight through. With no provider
        wired (the unit tests) nothing is filtered — there is no plan state to mirror.
        """
        if self.live_warning_keys is None:
            return warnings
        live = self.live_warning_keys()
        return [
            w for w in warnings
            if w.kind not in SETTLEABLE_KINDS or w.warning_key in live
        ]

    # --- contracts:24 ---

    def suppress_warning(self, warning_id: int, reason: str) -> Warning:
        """Record the owner's explicit suppression. Still resurfaces at critical
        points (requirements:23)."""
        if not reason.strip():
            raise WarningNotFound(
                "suppression is the owner's explicit act and records why",
                warning_id=warning_id,
            )
        warning = self.get(warning_id)
        if warning.state == RESOLVED:
            raise AlreadyResolved(
                "resolved warnings need no suppression; nothing written",
                warning_id=warning_id,
            )
        self.storage.write_atomic(
            [Op("update", "warnings",
                {"state": SUPPRESSED, "reason": reason, "updated_at": now()},
                where={"id": warning_id})],
            key("suppress_warning", warning_id),
        )
        return self.get(warning_id)

    # --- contracts:25 ---

    def resolve_warning(
        self, warning_id: int, cause: RowRef | str
    ) -> Warning:
        """Resolve the warning, linked to the row whose fix resolved it.

        The link is mandatory (contracts:25 types `cause` as a RowRef, not an optional
        note): a warning that simply stopped being mentioned is the silent pass-over
        requirements:21 exists to prevent.
        """
        cause_ref = RowRef.coerce(cause)
        warning = self.get(warning_id)
        if warning.state == RESOLVED:
            return warning
        self.storage.write_atomic(
            [Op("update", "warnings",
                {"state": RESOLVED, "resolved_by": str(cause_ref),
                 "updated_at": now()},
                where={"id": warning_id})],
            key("resolve_warning", warning_id),
        )
        return self.get(warning_id)

    def settle_warning(self, warning_id: int, note: str) -> Warning:
        """Retire a warning whose *condition* cleared, rather than whose row was fixed.

        Distinct from resolve_warning, which contracts:25 types as taking the RowRef
        that fixed it. A gap that stopped being derived has no single such row — the
        plan simply moved on — and inventing one would put a false cause in the audit
        trail. So this records the reason in `reason` and leaves resolved_by null,
        which is honest and still distinguishable from an owner suppression by state.
        """
        warning = self.get(warning_id)
        if warning.state == RESOLVED:
            return warning
        self.storage.write_atomic(
            [Op("update", "warnings",
                {"state": RESOLVED, "reason": note, "updated_at": now()},
                where={"id": warning_id})],
            key("settle_warning", warning_id),
        )
        return self.get(warning_id)

    # --- reads ---

    def get(self, warning_id: int) -> Warning:
        found = self.storage.query(
            "SELECT * FROM warnings WHERE id = ?", (warning_id,)
        )
        if not found:
            raise WarningNotFound("no such warning", warning_id=warning_id)
        return self._build(dict(found[0]))

    def all_warnings(self) -> list[Warning]:
        return [
            self._build(dict(r))
            for r in self.storage.query("SELECT * FROM warnings ORDER BY id")
        ]

    def _by_key(self, warning_key: str) -> Warning | None:
        found = self.storage.query(
            "SELECT * FROM warnings WHERE warning_key = ?", (warning_key,)
        )
        return self._build(dict(found[0])) if found else None

    def _require_key(self, warning_key: str) -> Warning:
        warning = self._by_key(warning_key)
        if warning is None:  # pragma: no cover — the write just landed
            raise WarningNotFound("warning vanished after write", key=warning_key)
        return warning

    @staticmethod
    def _build(record: dict, resurfaced: bool = False) -> Warning:
        return Warning(
            id=record["id"],
            warning_key=record["warning_key"],
            kind=record["kind"],
            message=record["message"],
            state=record["state"],
            created_at=record["created_at"],
            source_ref=(
                RowRef.parse(record["source_ref"]) if record["source_ref"] else None
            ),
            reason=record["reason"],
            resolved_by=(
                RowRef.parse(record["resolved_by"]) if record["resolved_by"] else None
            ),
            resurfaced=resurfaced,
        )
