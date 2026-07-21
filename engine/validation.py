"""validation-service (components:9).

Resolves uncertainty against external reality: spike registration and resolution for
world-assumptions, and classification, routing and outcomes for technical claims.

Contracts: contracts:29 register_spike, contracts:30 record_spike_result, contracts:31
file_claim, contracts:32 record_claim_outcome.

Two contracts here are *not* in the frozen plan — `start_spike` and `unblock_spike`.
state_machines:5 needs a `start` and an `unblock` event that no planned contract fires,
which strands every spike in `registered` where `conclude` is impossible (sm_cells:65).
See DEFECTS.md F12.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from engine.errors import PlanToolError
from engine.models import Provenance, RowRef
from engine.clock import now
from engine.storage import FromOp, Op, Storage

# --- state_machines:5, the Spike lifecycle ---

REGISTERED = "registered"
EXECUTING = "executing"
BLOCKED = "blocked"
CONCLUDED = "concluded"

#: (state, event) -> next state. Every pair absent from this table is one of the
#: "impossible" cells in sm_cells:62-77, and raises InvalidTransition naming the reason.
_SPIKE_TRANSITIONS = {
    (REGISTERED, "start"): EXECUTING,
    (REGISTERED, "block"): BLOCKED,
    (EXECUTING, "block"): BLOCKED,
    (EXECUTING, "conclude"): CONCLUDED,
    (BLOCKED, "unblock"): EXECUTING,
    (BLOCKED, "conclude"): CONCLUDED,
}

#: The sm_cells reason text for each impossible pair, so InvalidTransition can explain
#: itself rather than merely refusing.
_SPIKE_IMPOSSIBLE = {
    (REGISTERED, "unblock"): "not blocked",
    (REGISTERED, "conclude"): "no result without execution",
    (EXECUTING, "start"): "already executing",
    (EXECUTING, "unblock"): "not blocked",
    (BLOCKED, "start"): "unblock first",
    (BLOCKED, "block"): "already blocked",
    (CONCLUDED, "start"): "terminal; the outcome is recorded on the row",
    (CONCLUDED, "block"): "terminal; the outcome is recorded on the row",
    (CONCLUDED, "unblock"): "terminal; the outcome is recorded on the row",
    (CONCLUDED, "conclude"): "terminal; the outcome is recorded on the row",
}

#: contracts:30 outcome -> the state_machines:5 event it fires.
_OUTCOME_EVENT = {
    "confirmed": "conclude",
    "refuted": "conclude",
    "inconclusive": "conclude",
    "blocked": "block",
}

# --- state_machines:8, the TechnicalClaim lifecycle ---

IDENTIFIED = "identified"
VALIDATING = "validating"
VALIDATED = "validated"
FAILED = "failed"
RISK_ACCEPTED = "risk_accepted"

_CLAIM_TRANSITIONS = {
    (IDENTIFIED, "route"): VALIDATING,
    (IDENTIFIED, "accept_risk"): RISK_ACCEPTED,
    (VALIDATING, "pass"): VALIDATED,
    (VALIDATING, "fail"): FAILED,
    (VALIDATING, "accept_risk"): RISK_ACCEPTED,
}

_CLAIM_IMPOSSIBLE = {
    (IDENTIFIED, "pass"): "not yet validating",
    (IDENTIFIED, "fail"): "not yet validating",
    (VALIDATING, "route"): "already routed",
}

_CLAIM_OUTCOME_EVENT = {"validated": "pass", "failed": "fail", "risk_accepted": "accept_risk"}

#: requirements:41 — kind -> the tracks it routes to. `both` opens two, and neither
#: alone closes the claim.
_KIND_TRACKS = {
    "software": ("spike",),
    "scientific": ("research",),
    "both": ("spike", "research"),
}

TRACK_OPEN = "open"
TRACK_SATISFIED = "satisfied"


class AssumptionNotFound(PlanToolError):
    """contracts:29 — names the missing ref; registration rejected without a linked
    assumption (requirements:24)."""


class NotWorldAssumption(PlanToolError):
    """contracts:29 — spikes resolve world-assumptions only.

    Intent-assumptions go to the owner: no experiment against the real world can tell
    you what someone meant.
    """


class SpikeNotFound(PlanToolError):
    """contracts:30 — names the missing id."""


class ClaimNotFound(PlanToolError):
    """contracts:32 — names the missing id."""


class RefNotFound(PlanToolError):
    """contracts:31 — names the missing ref; nothing filed."""


class InvalidTransition(PlanToolError):
    """contracts:30 / contracts:32 — outcome not reachable from the current state;
    state unchanged."""


@dataclass(frozen=True, slots=True)
class SpikeSpec:
    """contracts:29 — question, hypothesis, method against the real dependency, budget.

    All four are mandatory. A spike with no hypothesis cannot be refuted, and one with
    no budget is the open-ended investigation the spike mechanism exists to bound.
    """

    question: str
    hypothesis: str
    method: str
    budget: str


@dataclass(frozen=True, slots=True)
class Spike:
    id: int
    assumption: RowRef
    spec: SpikeSpec
    slug: str
    state: str
    created_at: str
    outcome: str | None = None
    evidence: str | None = None
    block_reason: str | None = None
    concluded_at: str | None = None

    @property
    def directory(self) -> str:
        """requirements:3 — the quarantine directory, relative to the workspace.

        Derived rather than stored so the path can never drift out of step with the
        record it belongs to.
        """
        return f"spikes/{self.id:03d}_{self.slug}"


@dataclass(frozen=True, slots=True)
class SpikeResolution:
    """contracts:30 — the spike plus what its outcome did to the linked assumption."""

    spike: Spike
    outcome: str
    assumption_closed: bool
    assumption_state: str
    conflicts_raised: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class ClaimTrack:
    """One validation route a claim was sent down (requirements:41)."""

    track: str
    state: str
    detail: str
    spike_id: int | None = None


@dataclass(frozen=True, slots=True)
class TechnicalClaim:
    id: int
    text: str
    kind: str
    refs: tuple[RowRef, ...]
    state: str
    tracks: tuple[ClaimTrack, ...]
    created_at: str
    red_flag: bool = False
    fenced: bool = False
    outcome: str | None = None
    evidence: str | None = None
    resolved_at: str | None = None

    @property
    def blocks_dependent_planning(self) -> bool:
        """requirements:4 — research red flags block dependent planning until resolved
        or fenced."""
        return self.red_flag and not self.fenced and self.state in (IDENTIFIED, VALIDATING)


@dataclass(frozen=True, slots=True)
class ClaimResolution:
    """contracts:32 — the resolved claim and the conflicts a failure raised."""

    claim: TechnicalClaim
    outcome: str
    conflicts_raised: tuple[int, ...] = ()


def _slugify(text: str) -> str:
    """Mirror the naming the v1 spikes already on disk use: lowercased, underscored,
    truncated. Collisions are harmless — the id prefix disambiguates."""
    cleaned = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return cleaned[:40].rstrip("_") or "spike"


class ValidationService:
    def __init__(self, storage: Storage, rows=None, graph=None, conflicts=None):
        self.storage = storage
        self.rows = rows
        self.graph = graph
        self.conflicts = conflicts

    # --- contracts:29 ---

    def register_spike(
        self, assumption: RowRef | str, spec: SpikeSpec, lease=None
    ) -> Spike:
        """Register a spike against a world-assumption, with its quarantine directory.

        requirements:24 — registration without a linked assumption is rejected. The
        spike exists to close a specific piece of uncertainty; an unlinked one is an
        experiment with no consumer for its result.
        """
        ref = RowRef.coerce(assumption)
        row = self._row(ref)
        if row is None:
            raise AssumptionNotFound(
                "no such row; registration rejected without a linked assumption "
                "(requirements:24)",
                ref=str(ref),
            )
        if row["provenance"] != Provenance.ASSUMED:
            raise NotWorldAssumption(
                "spikes resolve open assumptions; this row is not one",
                ref=str(ref),
                provenance=row["provenance"],
            )
        if (row["assumption_kind"] or "").strip().lower() != "world":
            raise NotWorldAssumption(
                "spikes resolve world-assumptions only; intent-assumptions go to the "
                "owner, because no experiment can tell you what someone meant",
                ref=str(ref),
                assumption_kind=row["assumption_kind"],
            )
        for field_name in ("question", "hypothesis", "method", "budget"):
            if not getattr(spec, field_name).strip():
                raise AssumptionNotFound(
                    f"a spike spec needs a {field_name}; nothing registered",
                    ref=str(ref),
                )

        stamp = now()
        receipt = self.storage.write_atomic(
            [Op("insert", "spikes", {
                "assumption": str(ref),
                "question": spec.question,
                "hypothesis": spec.hypothesis,
                "method": spec.method,
                "budget": spec.budget,
                "slug": _slugify(spec.question),
                "state": REGISTERED,
                "created_at": stamp,
            })],
            f"register_spike:{ref}:{stamp}",
            lease=lease,
        )
        spike = self.get_spike(receipt["results"][0]["id"])
        # requirements:3 — the quarantine directory is created now, so probe code has
        # exactly one legitimate place to live from the moment the spike exists.
        (self.storage.workspace / spike.directory).mkdir(parents=True, exist_ok=True)
        return spike

    # --- DEFECTS.md F12: the contracts that fire state_machines:5's missing events ---

    def start_spike(self, spike_id: int, lease=None) -> Spike:
        """Fire `start` (sm_cells:62): the probe is now running.

        Not in the frozen plan. Without it `conclude` is unreachable, because
        sm_cells:65 refuses to conclude a spike that never executed.
        """
        return self._transition_spike(spike_id, "start", {}, lease)

    def unblock_spike(self, spike_id: int, note: str = "", lease=None) -> Spike:
        """Fire `unblock` (sm_cells:72): the dependency is reachable again.

        Not in the frozen plan — see start_spike. The block reason is cleared, since it
        no longer describes the spike's situation; the note explaining what changed is
        appended to the evidence trail instead, where it survives the conclusion.
        """
        spike = self.get_spike(spike_id)
        values: dict = {"block_reason": None}
        if note.strip():
            prior = spike.evidence or ""
            values["evidence"] = f"{prior}\nunblocked: {note}".strip()
        return self._transition_spike(spike_id, "unblock", values, lease)

    # --- contracts:30 ---

    def record_spike_result(
        self, spike_id: int, outcome: str, evidence: str, lease=None
    ) -> SpikeResolution:
        """Record the outcome and resolve the linked assumption accordingly.

        requirements:25 — confirmed or refuted closes the assumption; inconclusive keeps
        it open with the findings attached. requirements:26 — blocked parks the spike
        with the assumption visibly open, so an unreachable dependency never reads as a
        settled question.

        requirements:43 — a refutation raises a conflict on every row that depended on
        the assumption. That is the whole point of linking them: the rows built on a
        false premise have to be re-examined, and nothing else in the system knows to
        look.
        """
        if outcome not in _OUTCOME_EVENT:
            raise InvalidTransition(
                "outcome must be confirmed|refuted|inconclusive|blocked",
                spike_id=spike_id,
                outcome=outcome,
            )
        if not evidence.strip():
            raise InvalidTransition(
                "a spike result records what was observed; for 'blocked', the "
                "unreachable-dependency reason (requirements:26)",
                spike_id=spike_id,
                outcome=outcome,
            )

        stamp = now()
        values: dict = {"outcome": outcome, "evidence": evidence}
        if outcome == "blocked":
            values["block_reason"] = evidence
        else:
            values["concluded_at"] = stamp
        spike = self._transition_spike(spike_id, _OUTCOME_EVENT[outcome], values, lease)

        closed, assumption_state = self._resolve_assumption(spike, outcome, evidence, lease)
        raised: tuple[int, ...] = ()
        if outcome == "refuted":
            raised = self._raise_dependent_conflicts(
                [spike.assumption],
                f"spike #{spike.id} refuted the assumption {spike.assumption}",
                evidence,
                lease,
            )
        return SpikeResolution(
            spike=self.get_spike(spike_id),
            outcome=outcome,
            assumption_closed=closed,
            assumption_state=assumption_state,
            conflicts_raised=raised,
        )

    def _resolve_assumption(
        self, spike: Spike, outcome: str, evidence: str, lease
    ) -> tuple[bool, str]:
        """requirements:25/26 — the linked assumption auto-resolves per outcome."""
        if outcome not in ("confirmed", "refuted") or self.rows is None:
            # inconclusive and blocked both leave the assumption visibly open; the
            # evidence stays attached to the spike, which is linked to it.
            row = self._row(spike.assumption)
            return False, (row["state"] if row else "unknown")

        # The spike's evidence takes the place of the owner's quote here. That is the
        # design working as intended: a world-assumption is settled by what the world
        # did, not by what the owner says about it (requirements:25).
        resolution = "confirm" if outcome == "confirmed" else "reject"
        row = self.rows.resolve_assumption(
            spike.assumption,
            quote=f"spike #{spike.id} {outcome}: {evidence}",
            resolution=resolution,
            idempotency_key=f"spike_resolves:{spike.id}",
            lease=lease,
            retire_reason=f"refuted by spike #{spike.id}",
        )
        return True, str(row.state)

    # --- contracts:31 ---

    def file_claim(
        self,
        text: str,
        kind: str,
        refs: list[RowRef | str],
        red_flag: bool = False,
        lease=None,
    ) -> TechnicalClaim:
        """File a load-bearing technical claim, routed per kind (requirements:41).

        Filing routes immediately: state_machines:8's `route` event has no other
        contract that fires it, and a claim sitting unrouted in `identified` is the
        thing requirements:41 exists to prevent.

        `red_flag` marks a research claim that blocks dependent planning until resolved
        or fenced (requirements:4). It is a caller-supplied judgment, not something the
        tool infers: the design spine is that the tool records judgment, never exercises
        it.
        """
        if kind not in _KIND_TRACKS:
            raise RefNotFound(
                "kind must be software|scientific|both (requirements:41); nothing filed",
                kind=kind,
            )
        if not text.strip():
            raise RefNotFound("a claim needs its text; nothing filed")
        parsed = [RowRef.coerce(r) for r in refs]
        if not parsed:
            raise RefNotFound(
                "a claim must name the rows resting on it; nothing filed"
            )
        for ref in parsed:
            if self._row(ref) is None:
                raise RefNotFound("no such row; nothing filed", ref=str(ref))

        stamp = now()
        ops = [
            Op("insert", "technical_claims", {
                "text": text,
                "kind": kind,
                "state": VALIDATING,          # filing fires `route` (sm_cells:110)
                "red_flag": int(red_flag),
                "fenced": 0,
                "created_at": stamp,
            }),
            *[
                Op("insert", "claim_refs",
                   {"claim_id": FromOp(0, "id"), "ref": str(ref)})
                for ref in parsed
            ],
            *[
                Op("insert", "claim_tracks", {
                    "claim_id": FromOp(0, "id"),
                    "track": track,
                    "state": TRACK_OPEN,
                    "detail": _TRACK_DETAIL[track],
                    "created_at": stamp,
                    "updated_at": stamp,
                })
                for track in _KIND_TRACKS[kind]
            ],
        ]
        receipt = self.storage.write_atomic(
            ops, f"file_claim:{stamp}:{','.join(str(r) for r in parsed)}", lease=lease
        )
        return self.get_claim(receipt["results"][0]["id"])

    def fence_claim(self, claim_id: int, rationale: str, lease=None) -> TechnicalClaim:
        """requirements:4 — fence a red flag so dependent planning may proceed.

        The requirement offers "resolved or fenced" as the two ways to clear the block
        but names no contract for fencing. Recorded in DEFECTS.md F12.
        """
        if not rationale.strip():
            raise ClaimNotFound(
                "fencing a red flag records why the risk is bounded", claim_id=claim_id
            )
        claim = self.get_claim(claim_id)
        self.storage.write_atomic(
            [Op("update", "technical_claims",
                {"fenced": 1, "evidence": rationale}, where={"id": claim.id})],
            f"fence_claim:{claim_id}",
            lease=lease,
        )
        return self.get_claim(claim_id)

    # --- contracts:32 ---

    def record_claim_outcome(
        self, claim_id: int, outcome: str, evidence: str, lease=None
    ) -> ClaimResolution:
        """Record a claim's validation outcome.

        requirements:43 — failed validation raises conflicts on every dependent row.
        requirements:42 — risk_accepted is the unvalidatable-at-acceptable-cost path,
        and stays visible at handoff.
        """
        if outcome not in _CLAIM_OUTCOME_EVENT:
            raise InvalidTransition(
                "outcome must be validated|failed|risk_accepted",
                claim_id=claim_id,
                outcome=outcome,
            )
        if not evidence.strip():
            raise InvalidTransition(
                "a claim outcome records its evidence; for risk_accepted, the owner's "
                "sign-off (requirements:42)",
                claim_id=claim_id,
                outcome=outcome,
            )
        claim = self.get_claim(claim_id)
        event = _CLAIM_OUTCOME_EVENT[outcome]
        target = _CLAIM_TRANSITIONS.get((claim.state, event))
        if target is None:
            raise InvalidTransition(
                f"cannot {event} a claim in state {claim.state}: "
                f"{_CLAIM_IMPOSSIBLE.get((claim.state, event), 'terminal')}; "
                "state unchanged",
                claim_id=claim_id,
                state=claim.state,
                outcome=outcome,
            )
        # requirements:41 — for kind 'both', neither track alone closes the claim.
        if outcome == "validated":
            unsatisfied = [t.track for t in claim.tracks if t.state != TRACK_SATISFIED]
            if unsatisfied:
                raise InvalidTransition(
                    "every routed validation track must be satisfied before the claim "
                    "validates; neither track alone closes it (requirements:41)",
                    claim_id=claim_id,
                    unsatisfied=unsatisfied,
                )

        stamp = now()
        self.storage.write_atomic(
            [Op("update", "technical_claims", {
                "state": target,
                "outcome": outcome,
                "evidence": evidence,
                "resolved_at": stamp,
            }, where={"id": claim_id})],
            f"record_claim_outcome:{claim_id}:{outcome}",
            lease=lease,
        )
        raised: tuple[int, ...] = ()
        if outcome == "failed":
            raised = self._raise_dependent_conflicts(
                list(claim.refs),
                f"technical claim #{claim.id} failed validation: {claim.text}",
                evidence,
                lease,
                include_roots=True,
            )
        return ClaimResolution(
            claim=self.get_claim(claim_id), outcome=outcome, conflicts_raised=raised
        )

    def satisfy_track(
        self, claim_id: int, track: str, detail: str, spike_id: int | None = None,
        lease=None,
    ) -> TechnicalClaim:
        """Mark one of a claim's validation tracks satisfied.

        requirements:41 routes a 'both' claim down two tracks and says neither alone
        closes it, but names no contract that records a track's completion. DEFECTS.md
        F12.
        """
        claim = self.get_claim(claim_id)
        if track not in {t.track for t in claim.tracks}:
            raise ClaimNotFound(
                "this claim was not routed down that track",
                claim_id=claim_id,
                track=track,
                routed=[t.track for t in claim.tracks],
            )
        self.storage.write_atomic(
            [Op("update", "claim_tracks", {
                "state": TRACK_SATISFIED,
                "detail": detail,
                "spike_id": spike_id,
                "updated_at": now(),
            }, where={"claim_id": claim_id, "track": track})],
            f"satisfy_track:{claim_id}:{track}",
            lease=lease,
        )
        return self.get_claim(claim_id)

    # --- requirements:43, the shared dependent-conflict walk ---

    def _raise_dependent_conflicts(
        self, roots: list[RowRef], description: str, evidence: str, lease,
        include_roots: bool = False,
    ) -> tuple[int, ...]:
        """Raise a conflict on every row that depends on a refuted/failed root.

        One conflict per dependent row rather than one naming them all: conflicts block
        gates by the rows they contest (contracts:28), and the dependents are
        adjudicated separately — one may be revised while another is overridden.

        `include_roots` distinguishes the two callers, and getting it wrong silently
        under-contests the plan (DEFECTS.md F14). A refuted *spike* roots at the
        assumption, which is itself resolved rather than contested — only what rests on
        it is in question. A failed *claim* roots at the rows that rest on the claim, so
        those rows are exactly the ones requirements:43 means, and excluding them would
        contest their dependents while leaving the directly-affected row untouched.
        """
        if self.graph is None or self.conflicts is None:
            return ()
        impact = self.graph.impact(roots)
        affected = (*impact.changed, *impact.affected) if include_roots else impact.affected
        raised = []
        for ref in affected:
            conflict = self.conflicts.raise_conflict(
                [ref],
                description=f"{description}. This row rests on it. Evidence: {evidence}",
                recommendation=(
                    "re-examine this row against the evidence: revise it to match what "
                    "was observed, or override with the reasoning for keeping it as it "
                    "stands"
                ),
                lease=lease,
            )
            raised.append(conflict.id)
        return tuple(raised)

    # --- transitions ---

    def _transition_spike(
        self, spike_id: int, event: str, values: dict, lease
    ) -> Spike:
        spike = self.get_spike(spike_id)
        target = _SPIKE_TRANSITIONS.get((spike.state, event))
        if target is None:
            raise InvalidTransition(
                f"cannot {event} a spike in state {spike.state}: "
                f"{_SPIKE_IMPOSSIBLE.get((spike.state, event), 'terminal')}; "
                "state unchanged",
                spike_id=spike_id,
                state=spike.state,
                event=event,
            )
        self.storage.write_atomic(
            [Op("update", "spikes", {"state": target, **values},
                where={"id": spike_id})],
            f"spike:{spike_id}:{event}:{now()}",
            lease=lease,
        )
        return self.get_spike(spike_id)

    # --- reads ---

    def get_spike(self, spike_id: int) -> Spike:
        found = self.storage.query("SELECT * FROM spikes WHERE id = ?", (spike_id,))
        if not found:
            raise SpikeNotFound("no such spike", spike_id=spike_id)
        r = dict(found[0])
        return Spike(
            id=r["id"],
            assumption=RowRef.parse(r["assumption"]),
            spec=SpikeSpec(r["question"], r["hypothesis"], r["method"], r["budget"]),
            slug=r["slug"],
            state=r["state"],
            created_at=r["created_at"],
            outcome=r["outcome"],
            evidence=r["evidence"],
            block_reason=r["block_reason"],
            concluded_at=r["concluded_at"],
        )

    def spikes_for(self, assumption: RowRef | str) -> list[Spike]:
        rows = self.storage.query(
            "SELECT id FROM spikes WHERE assumption = ? ORDER BY id",
            (str(RowRef.coerce(assumption)),),
        )
        return [self.get_spike(r["id"]) for r in rows]

    def open_spikes(self) -> list[Spike]:
        rows = self.storage.query(
            "SELECT id FROM spikes WHERE state != ? ORDER BY id", (CONCLUDED,)
        )
        return [self.get_spike(r["id"]) for r in rows]

    def get_claim(self, claim_id: int) -> TechnicalClaim:
        found = self.storage.query(
            "SELECT * FROM technical_claims WHERE id = ?", (claim_id,)
        )
        if not found:
            raise ClaimNotFound("no such claim", claim_id=claim_id)
        r = dict(found[0])
        refs = tuple(
            RowRef.parse(x["ref"])
            for x in self.storage.query(
                "SELECT ref FROM claim_refs WHERE claim_id = ? ORDER BY ref", (claim_id,)
            )
        )
        tracks = tuple(
            ClaimTrack(t["track"], t["state"], t["detail"], t["spike_id"])
            for t in self.storage.query(
                "SELECT * FROM claim_tracks WHERE claim_id = ? ORDER BY track",
                (claim_id,),
            )
        )
        return TechnicalClaim(
            id=r["id"],
            text=r["text"],
            kind=r["kind"],
            refs=refs,
            state=r["state"],
            tracks=tracks,
            created_at=r["created_at"],
            red_flag=bool(r["red_flag"]),
            fenced=bool(r["fenced"]),
            outcome=r["outcome"],
            evidence=r["evidence"],
            resolved_at=r["resolved_at"],
        )

    def claims_for(self, ref: RowRef | str) -> list[TechnicalClaim]:
        rows = self.storage.query(
            "SELECT claim_id FROM claim_refs WHERE ref = ?",
            (str(RowRef.coerce(ref)),),
        )
        return [self.get_claim(r["claim_id"]) for r in rows]

    def blocking_claims(self) -> list[TechnicalClaim]:
        """requirements:4 — unfenced, unresolved research red flags block dependent
        planning."""
        rows = self.storage.query(
            "SELECT id FROM technical_claims WHERE red_flag = 1 AND fenced = 0 "
            "ORDER BY id"
        )
        claims = [self.get_claim(r["id"]) for r in rows]
        return [c for c in claims if c.blocks_dependent_planning]

    def accepted_risks(self) -> list[TechnicalClaim]:
        """requirements:42 — accepted risks stay visible at handoff."""
        rows = self.storage.query(
            "SELECT id FROM technical_claims WHERE state = ? ORDER BY id",
            (RISK_ACCEPTED,),
        )
        return [self.get_claim(r["id"]) for r in rows]

    def _row(self, ref: RowRef):
        found = self.storage.query(
            "SELECT * FROM plan_rows WHERE table_name = ? AND ordinal = ?",
            (ref.table, ref.ordinal),
        )
        return found[0] if found else None


#: What each track means, recorded on the claim so the routing is legible without
#: re-deriving it from `kind` (requirements:41).
_TRACK_DETAIL = {
    "spike": "software feasibility: routed to an executable spike against the real "
             "dependency",
    "research": "scientific appropriateness: routed to research plus owner or "
                "domain-expert adjudication",
}
