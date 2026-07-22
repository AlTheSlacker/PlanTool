"""validation-service (components:9) — contracts:29/30/31/32."""

import pytest

from engine.models import LinkSpec, Provenance, RowRef, RowSubmission
from engine.validation import (
    BLOCKED,
    CONCLUDED,
    EXECUTING,
    FAILED,
    IDENTIFIED,
    REGISTERED,
    RISK_ACCEPTED,
    VALIDATED,
    VALIDATING,
    AssumptionNotFound,
    ClaimNotFound,
    InvalidTransition,
    NotWorldAssumption,
    RefNotFound,
    SpikeNotFound,
    SpikeSpec,
)

SPEC = SpikeSpec(
    question="Does SQLite commit atomically over SMB?",
    hypothesis="It does not, under concurrent writers",
    method="Two processes writing the same DB on the share, checked for torn commits",
    budget="2 hours",
)


def _assumption(rows, kind="world", text="SMB honours fsync"):
    receipt = rows.submit_rows(
        [RowSubmission(
            table="assumptions",
            content={"text": text},
            name=text,
            provenance=Provenance.ASSUMED,
            assumption_kind=kind,
        )],
        f"assume:{kind}:{text}",
    )
    return receipt.verdicts[0].ref


def _dependent(rows, on, text="store the plan on the share", key=None):
    """A row that rests on `on` — the thing requirements:43 walks to."""
    receipt = rows.submit_rows(
        [RowSubmission(
            table="decisions",
            content={"text": text},
            name=text,
            links=[LinkSpec(target=RowRef.coerce(on))],
        )],
        key or f"dep:{text}",
    )
    return receipt.verdicts[0].ref


# --- contracts:29 register_spike ---


def test_register_spike_creates_quarantine_directory(store, rows, validation):
    ref = _assumption(rows)
    spike = validation.register_spike(ref, SPEC)

    assert spike.state == REGISTERED
    assert spike.assumption == ref
    # requirements:3 — probe code is confined to spikes/ and never shipped.
    assert spike.directory.startswith("spikes/")
    assert (store.workspace / spike.directory).is_dir()


def test_register_spike_rejects_missing_assumption(rows, validation):
    with pytest.raises(AssumptionNotFound) as exc:
        validation.register_spike("assumptions:99", SPEC)
    assert "assumptions:99" in str(exc.value)


def test_register_spike_rejects_intent_assumption(rows, validation):
    ref = _assumption(rows, kind="intent", text="the owner wants a web UI")
    with pytest.raises(NotWorldAssumption):
        validation.register_spike(ref, SPEC)


def test_register_spike_rejects_decided_row(rows, validation):
    ref = _dependent(rows, on=_assumption(rows), text="a settled decision")
    with pytest.raises(NotWorldAssumption):
        validation.register_spike(ref, SPEC)


def test_register_spike_requires_a_complete_spec(rows, validation):
    ref = _assumption(rows)
    with pytest.raises(AssumptionNotFound):
        validation.register_spike(ref, SpikeSpec("q", "h", "m", "  "))


# --- state_machines:5 (DEFECTS.md F12) ---


def test_spike_cannot_conclude_without_executing(rows, validation):
    """sm_cells:65 — no result without execution."""
    spike = validation.register_spike(_assumption(rows), SPEC)
    with pytest.raises(InvalidTransition) as exc:
        validation.record_spike_result(spike.id, "confirmed", "it held")
    assert "no result without execution" in str(exc.value)
    assert validation.get_spike(spike.id).state == REGISTERED


def test_start_then_conclude(rows, validation):
    spike = validation.register_spike(_assumption(rows), SPEC)
    assert validation.start_spike(spike.id).state == EXECUTING
    resolution = validation.record_spike_result(spike.id, "confirmed", "no torn commits")
    assert resolution.spike.state == CONCLUDED


def test_blocked_spike_unblocks_and_concludes(rows, validation):
    """requirements:26 — a blocked spike parks; unblocking resumes it."""
    ref = _assumption(rows)
    spike = validation.register_spike(ref, SPEC)
    validation.start_spike(spike.id)

    parked = validation.record_spike_result(spike.id, "blocked", "the share is offline")
    assert parked.spike.state == BLOCKED
    assert parked.spike.block_reason == "the share is offline"
    # The assumption stays visibly open: a blocked spike settles nothing.
    assert parked.assumption_closed is False
    assert parked.assumption_state == "assumed"

    resumed = validation.unblock_spike(spike.id, "share is back")
    assert resumed.state == EXECUTING
    assert resumed.block_reason is None
    assert validation.record_spike_result(
        spike.id, "refuted", "torn commits observed"
    ).spike.state == CONCLUDED


def test_concluded_spike_is_terminal(rows, validation):
    spike = validation.register_spike(_assumption(rows), SPEC)
    validation.start_spike(spike.id)
    validation.record_spike_result(spike.id, "confirmed", "held")
    with pytest.raises(InvalidTransition) as exc:
        validation.record_spike_result(spike.id, "refuted", "changed my mind")
    assert "terminal" in str(exc.value)


def test_unknown_spike_is_named(validation):
    with pytest.raises(SpikeNotFound) as exc:
        validation.get_spike(404)
    assert "404" in str(exc.value)


# --- contracts:30 assumption resolution (requirements:25/26) ---


def test_confirmed_spike_closes_the_assumption(rows, validation):
    ref = _assumption(rows)
    spike = validation.register_spike(ref, SPEC)
    validation.start_spike(spike.id)

    resolution = validation.record_spike_result(spike.id, "confirmed", "fsync honoured")
    assert resolution.assumption_closed is True
    row = rows.get(ref)
    assert row.provenance is Provenance.DECIDED
    assert "fsync honoured" in row.content["owner_answer"]["quote"]


def test_inconclusive_spike_keeps_the_assumption_open(rows, validation):
    ref = _assumption(rows)
    spike = validation.register_spike(ref, SPEC)
    validation.start_spike(spike.id)

    resolution = validation.record_spike_result(spike.id, "inconclusive", "ran out of budget")
    assert resolution.assumption_closed is False
    assert rows.get(ref).provenance is Provenance.ASSUMED
    # The evidence stays attached to the spike, which is linked to the assumption.
    assert validation.get_spike(spike.id).evidence == "ran out of budget"


def test_refuted_spike_raises_conflicts_on_every_dependent_row(rows, validation, conflicts):
    """requirements:43 — the rows built on a false premise all get contested."""
    ref = _assumption(rows)
    first = _dependent(rows, on=ref, text="store the plan on the share", key="d1")
    second = _dependent(rows, on=ref, text="skip the write-lock", key="d2")

    spike = validation.register_spike(ref, SPEC)
    validation.start_spike(spike.id)
    resolution = validation.record_spike_result(spike.id, "refuted", "torn commits seen")

    assert resolution.assumption_closed is True
    assert len(resolution.conflicts_raised) == 2
    contested = {str(r) for c in conflicts.open_conflicts() for r in c.refs}
    assert contested == {str(first), str(second)}
    # One conflict per dependent, so each can be adjudicated on its own terms.
    assert all(len(c.refs) == 1 for c in conflicts.open_conflicts())


def test_confirmed_spike_raises_no_conflicts(rows, validation, conflicts):
    ref = _assumption(rows)
    _dependent(rows, on=ref)
    spike = validation.register_spike(ref, SPEC)
    validation.start_spike(spike.id)
    validation.record_spike_result(spike.id, "confirmed", "held")
    assert conflicts.open_conflicts() == []


def test_spike_result_requires_evidence(rows, validation):
    spike = validation.register_spike(_assumption(rows), SPEC)
    validation.start_spike(spike.id)
    with pytest.raises(InvalidTransition):
        validation.record_spike_result(spike.id, "confirmed", "   ")


def test_unknown_outcome_is_rejected(rows, validation):
    spike = validation.register_spike(_assumption(rows), SPEC)
    with pytest.raises(InvalidTransition):
        validation.record_spike_result(spike.id, "probably", "hmm")


# --- contracts:31 file_claim ---


def test_file_claim_routes_software_to_a_spike_track(rows, validation):
    ref = _dependent(rows, on=_assumption(rows), text="use FTS5")
    claim = validation.file_claim("FTS5 is compiled into the runtime", "software", [ref])

    assert claim.state == VALIDATING          # filing fires `route`
    assert [t.track for t in claim.tracks] == ["spike"]
    assert claim.refs == (ref,)


def test_file_claim_both_opens_two_tracks(rows, validation):
    ref = _dependent(rows, on=_assumption(rows), text="use a Kalman filter")
    claim = validation.file_claim("A Kalman filter suits this noise", "both", [ref])
    assert sorted(t.track for t in claim.tracks) == ["research", "spike"]


def test_file_claim_rejects_unknown_ref(validation):
    with pytest.raises(RefNotFound) as exc:
        validation.file_claim("something", "software", ["decisions:99"])
    assert "decisions:99" in str(exc.value)


def test_file_claim_rejects_unknown_kind(rows, validation):
    ref = _dependent(rows, on=_assumption(rows))
    with pytest.raises(RefNotFound):
        validation.file_claim("something", "vibes", [ref])


def test_file_claim_requires_refs(validation):
    with pytest.raises(RefNotFound):
        validation.file_claim("a free-floating claim", "software", [])


# --- requirements:4 research red flags ---


def test_red_flag_blocks_dependent_planning_until_fenced(rows, validation):
    ref = _dependent(rows, on=_assumption(rows), text="assume linear response")
    claim = validation.file_claim(
        "the system is linear in this range", "scientific", [ref], red_flag=True
    )
    assert claim.blocks_dependent_planning is True
    assert [c.id for c in validation.blocking_claims()] == [claim.id]

    fenced = validation.fence_claim(claim.id, "bounded to the 0-5 V range by design")
    assert fenced.blocks_dependent_planning is False
    assert validation.blocking_claims() == []


# --- contracts:32 record_claim_outcome ---


def test_both_tracks_must_be_satisfied_before_validating(rows, validation):
    """requirements:41 — neither track alone closes a 'both' claim."""
    ref = _dependent(rows, on=_assumption(rows))
    claim = validation.file_claim("a dual claim", "both", [ref])

    validation.satisfy_track(claim.id, "spike", "spike 3 confirmed it")
    with pytest.raises(InvalidTransition) as exc:
        validation.record_claim_outcome(claim.id, "validated", "looks fine")
    assert "research" in str(exc.value)
    assert validation.get_claim(claim.id).state == VALIDATING

    validation.satisfy_track(claim.id, "research", "domain expert signed off")
    resolved = validation.record_claim_outcome(claim.id, "validated", "both tracks agree")
    assert resolved.claim.state == VALIDATED


def test_failed_claim_raises_conflicts_on_every_dependent_row(rows, validation, conflicts):
    """requirements:43 — same walk as a refuted spike, from the claim's own refs."""
    base = _dependent(rows, on=_assumption(rows), text="use FTS5", key="base")
    downstream = _dependent(rows, on=base, text="expose lexical search", key="down")

    claim = validation.file_claim("FTS5 is available", "software", [base])
    resolution = validation.record_claim_outcome(claim.id, "failed", "not compiled in")

    assert resolution.claim.state == FAILED
    contested = {str(r) for c in conflicts.open_conflicts() for r in c.refs}
    # DEFECTS.md F14 — the row resting *directly* on the claim is the one most obviously
    # invalidated by its failure, and it was exactly the one being missed.
    assert str(base) in contested
    assert str(downstream) in contested
    assert len(resolution.conflicts_raised) == 2


def test_refuted_spike_does_not_contest_the_assumption_itself(rows, validation, conflicts):
    """The mirror of F14: the assumption is *resolved* by the spike, not contested.

    Contesting it too would put the owner in front of a question the evidence has
    already answered.
    """
    ref = _assumption(rows)
    dep = _dependent(rows, on=ref)
    spike = validation.register_spike(ref, SPEC)
    validation.start_spike(spike.id)
    validation.record_spike_result(spike.id, "refuted", "torn commits seen")

    contested = {str(r) for c in conflicts.open_conflicts() for r in c.refs}
    assert contested == {str(dep)}


def test_refuted_assumption_records_the_spike_as_the_reason(rows, validation):
    """DEFECTS.md F14 — not 'rejected by the owner'; no owner was involved."""
    ref = _assumption(rows)
    spike = validation.register_spike(ref, SPEC)
    validation.start_spike(spike.id)
    validation.record_spike_result(spike.id, "refuted", "torn commits seen")

    assert rows.get(ref).retire_reason == f"refuted by spike #{spike.id}"


def test_risk_accepted_claim_is_visible_at_handoff(rows, validation):
    """requirements:42 — unvalidatable at acceptable cost, owner-signed."""
    ref = _dependent(rows, on=_assumption(rows))
    claim = validation.file_claim("the vendor firmware is correct", "software", [ref])
    resolved = validation.record_claim_outcome(
        claim.id, "risk_accepted", "owner accepts: source unavailable, cost prohibitive"
    )
    assert resolved.claim.state == RISK_ACCEPTED
    assert [c.id for c in validation.accepted_risks()] == [claim.id]


def test_claim_outcome_requires_evidence(rows, validation):
    ref = _dependent(rows, on=_assumption(rows))
    claim = validation.file_claim("a claim", "software", [ref])
    with pytest.raises(InvalidTransition):
        validation.record_claim_outcome(claim.id, "failed", "")


def test_resolved_claim_cannot_be_re_resolved(rows, validation):
    ref = _dependent(rows, on=_assumption(rows))
    claim = validation.file_claim("a claim", "software", [ref])
    validation.record_claim_outcome(claim.id, "failed", "did not work")
    with pytest.raises(InvalidTransition) as exc:
        validation.record_claim_outcome(claim.id, "validated", "actually it did")
    assert "state unchanged" in str(exc.value)


def test_unknown_claim_is_named(validation):
    with pytest.raises(ClaimNotFound) as exc:
        validation.get_claim(404)
    assert "404" in str(exc.value)


def test_satisfy_unrouted_track_is_refused(rows, validation):
    ref = _dependent(rows, on=_assumption(rows))
    claim = validation.file_claim("a software claim", "software", [ref])
    with pytest.raises(ClaimNotFound) as exc:
        validation.satisfy_track(claim.id, "research", "not routed here")
    assert "research" in str(exc.value)
