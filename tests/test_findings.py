"""finding-service (components:10) — contracts:33/34."""

import pytest

from engine.findings import (
    ACCEPTED_RISK,
    ADDRESSED,
    DISPUTED,
    FILED,
    FindingNotFound,
    InvalidAllocation,
    InvalidTransition,
    RefNotFound,
)
from engine.models import RowSubmission


def _row(rows, text="the gate criteria are too weak", key=None):
    receipt = rows.submit_rows(
        [RowSubmission(table="requirements", content={"text": text}, name=text)],
        key or f"row:{text}",
    )
    return receipt.verdicts[0].ref


# --- contracts:33 file_finding ---


def test_file_finding_links_the_attacked_rows(rows, findings):
    ref = _row(rows)
    finding = findings.file_finding(
        [ref], "package 4 gate passes with zero tests", "high",
        name="gate 4 passes with no tests", resolve_by=8,
    )

    assert finding.state == FILED
    assert finding.refs == (ref,)
    assert finding.severity == "high"
    assert finding.is_open is True


# --- D22: a finding is addressable, named, and not a plan row ---


def test_a_finding_has_an_address_of_its_own(rows, findings):
    """`table:ordinal` was never a property of `plan_rows` — it is a naming scheme, and
    what it needs is somebody able to resolve it. That is what lets a finding keep its own
    store and still be cited."""
    finding = findings.file_finding(
        [_row(rows)], "no rollback path", "high", name="no rollback path", resolve_by=8,
    )
    assert str(finding.ref) == f"findings:{finding.id}"
    assert findings.find(finding.ref).name == "no rollback path"


def test_an_address_reaching_no_finding_resolves_to_nothing(findings):
    assert findings.find("findings:99") is None


def test_a_finding_needs_a_name(rows, findings):
    """D19: `findings:3` reaches readers, so it may not travel alone. The tool cannot
    supply the name — deriving one from the description is the guess the rule removes."""
    with pytest.raises(RefNotFound) as exc:
        findings.file_finding([_row(rows)], "a real problem", "high", name="  ", resolve_by=8)
    assert "name" in str(exc.value)


def test_findings_is_not_a_plan_row_table(rows):
    """Deciding which store owns the word is half a fix. Without this the collision comes
    back as data the first time somebody submits the obvious-looking row (F38)."""
    receipt = rows.submit_rows(
        [RowSubmission(table="findings", content={"text": "a red-team finding"},
                       name="a red-team finding")],
        "reserved",
    )
    verdict = receipt.verdicts[0]
    assert not verdict.accepted
    assert "file_finding" in verdict.problem


def test_file_finding_rejects_unknown_ref(findings):
    with pytest.raises(RefNotFound) as exc:
        findings.file_finding(["requirements:99"], "a problem", "low", name="a problem", resolve_by=8)
    assert "requirements:99" in str(exc.value)


def test_file_finding_requires_refs(findings):
    """requirements:31 — findings attack specific rows."""
    with pytest.raises(RefNotFound):
        findings.file_finding([], "the plan feels wrong", "low", name="the plan feels wrong", resolve_by=8)


def test_file_finding_requires_description_and_severity(rows, findings):
    ref = _row(rows)
    with pytest.raises(RefNotFound):
        findings.file_finding([ref], "  ", "high", name="a real problem", resolve_by=8)
    with pytest.raises(RefNotFound):
        findings.file_finding([ref], "a real problem", "", name="a real problem", resolve_by=8)


def test_integrity_finding_files_without_readable_rows(store, findings):
    """contracts:33 — unreadable plan state is itself filed, and certification refused.

    Ref validation cannot gate this one: the rows in question are exactly the ones that
    failed to read.
    """
    report = store.integrity_check()
    finding = findings.file_integrity_finding(report, refs=["requirements:7"])
    assert finding.state == FILED
    assert "certification is refused" in finding.description
    assert finding.severity == "blocking"


# --- contracts:34 resolve_finding ---


def test_addressed_is_terminal(rows, findings):
    finding = findings.file_finding([_row(rows)], "a problem", "high", name="a problem", resolve_by=8)
    resolved = findings.resolve_finding(finding.id, "addressed", "fixed in requirements:12")

    assert resolved.state == ADDRESSED
    assert resolved.is_open is False
    with pytest.raises(InvalidTransition) as exc:
        findings.resolve_finding(finding.id, "accepted_risk", "actually, no")
    assert "terminal" in str(exc.value)


def test_accepted_risk_stays_visible_at_handoff(rows, findings):
    """requirements:33 — an accepted risk is a known issue, not a closed one."""
    finding = findings.file_finding([_row(rows)], "no rollback path", "medium", name="no rollback path", resolve_by=8)
    resolved = findings.resolve_finding(
        finding.id, "accepted_risk", "owner accepts: manual restore is acceptable"
    )

    assert resolved.state == ACCEPTED_RISK
    assert resolved.visible_at_handoff is True
    assert resolved.is_open is False          # requirements:32 — explicitly accepted
    assert [f.id for f in findings.accepted_risks()] == [finding.id]


def test_open_findings_fail_the_verification_gate(rows, findings):
    """requirements:32 — neither addressed nor explicitly accepted means still open."""
    kept = findings.file_finding([_row(rows, "a", key="a")], "unresolved", "high", name="unresolved", resolve_by=8)
    done = findings.file_finding([_row(rows, "b", key="b")], "resolved", "high", name="resolved", resolve_by=8)
    findings.resolve_finding(done.id, "addressed", "fixed")

    assert [f.id for f in findings.open_findings()] == [kept.id]


def test_resolve_requires_a_rationale(rows, findings):
    finding = findings.file_finding([_row(rows)], "a problem", "high", name="a problem", resolve_by=8)
    with pytest.raises(InvalidTransition):
        findings.resolve_finding(finding.id, "accepted_risk", "   ")


def test_unknown_finding_is_named(findings):
    with pytest.raises(FindingNotFound) as exc:
        findings.get(404)
    assert "404" in str(exc.value)


# --- state_machines:7 dispute path (DEFECTS.md F13) ---


def test_withdraw_requires_a_dispute_first(rows, findings):
    """sm_cells:92 — a finding nobody disputed cannot be withdrawn."""
    finding = findings.file_finding([_row(rows)], "a problem", "high", name="a problem", resolve_by=8)
    with pytest.raises(InvalidTransition) as exc:
        findings.resolve_finding(finding.id, "withdrawn", "never mind")
    assert "no dispute open" in str(exc.value)
    assert findings.get(finding.id).state == FILED


def test_dispute_then_withdraw(rows, findings):
    finding = findings.file_finding([_row(rows)], "a problem", "high", name="a problem", resolve_by=8)
    disputed = findings.dispute_finding(finding.id, "the row already covers this case")

    assert disputed.state == DISPUTED
    assert disputed.dispute == "the row already covers this case"

    withdrawn = findings.resolve_finding(
        finding.id, "withdrawn", "the dispute is correct; the finding was mistaken"
    )
    # sm_cells:97 — withdrawal resolves to addressed, not to a separate state.
    assert withdrawn.state == ADDRESSED
    assert withdrawn.outcome == "withdrawn"


def test_dispute_then_uphold_returns_to_filed(rows, findings):
    finding = findings.file_finding([_row(rows)], "a problem", "high", name="a problem", resolve_by=8)
    findings.dispute_finding(finding.id, "this is out of scope")
    upheld = findings.uphold_finding(finding.id, "scope includes it; the finding stands")

    assert upheld.state == FILED
    assert upheld.dispute is None
    # Having been disputed once, it can now take any of the three outcomes.
    assert findings.resolve_finding(finding.id, "addressed", "fixed").state == ADDRESSED


def test_disputed_finding_cannot_be_addressed_directly(rows, findings):
    """sm_cells:98 — settle the dispute first."""
    finding = findings.file_finding([_row(rows)], "a problem", "high", name="a problem", resolve_by=8)
    findings.dispute_finding(finding.id, "disagree")
    with pytest.raises(InvalidTransition) as exc:
        findings.resolve_finding(finding.id, "addressed", "fixed anyway")
    assert "settle the dispute first" in str(exc.value)
    assert findings.get(finding.id).state == DISPUTED


def test_accepted_risk_can_be_reopened_by_dispute(rows, findings):
    """sm_cells:105 — accepted_risk is visible, not settled."""
    finding = findings.file_finding([_row(rows)], "a problem", "high", name="a problem", resolve_by=8)
    findings.resolve_finding(finding.id, "accepted_risk", "owner accepts")
    assert findings.dispute_finding(finding.id, "this risk is not acceptable").state == DISPUTED


def test_findings_for_a_row(rows, findings):
    ref = _row(rows)
    finding = findings.file_finding([ref], "a problem", "high", name="a problem", resolve_by=8)
    assert [f.id for f in findings.findings_for(ref)] == [finding.id]


# --- D15: the gate allocation (M6_PLAN.md §2.6) ---


def test_a_finding_carries_the_gate_it_must_be_resolved_by(rows, findings):
    """The deadline is a gate, not a date: `resolve_by` is the package whose gate must not
    pass while this finding is open."""
    finding = findings.file_finding(
        [_row(rows)], "a problem", "high", name="a problem", resolve_by=5
    )
    assert finding.resolve_by == 5
    assert [f.id for f in findings.open_allocated_to(5)] == [finding.id]
    assert findings.open_allocated_to(4) == []


def test_resolve_by_must_be_a_real_gate(rows, findings):
    """An allocation to a package that does not exist is one no gate can ever discharge."""
    ref = _row(rows)
    for bad in (0, 9, True, "8"):
        with pytest.raises(InvalidAllocation):
            findings.file_finding(
                [ref], "a problem", "high", name=f"a problem {bad}", resolve_by=bad,
            )


def test_a_resolved_finding_is_no_longer_allocated_to_its_gate(rows, findings):
    """Resolving is the first exit: the finding leaves the scheme, so its gate is free."""
    finding = findings.file_finding(
        [_row(rows)], "a problem", "high", name="a problem", resolve_by=5
    )
    findings.resolve_finding(finding.id, "addressed", "fixed")
    assert findings.open_allocated_to(5) == []


def test_an_accepted_risk_stops_locking_its_gate(rows, findings):
    """requirements:33 — an accepted risk is a decision the owner made, not an open item;
    it stays visible at handoff but locks nothing."""
    finding = findings.file_finding(
        [_row(rows)], "a problem", "high", name="a problem", resolve_by=5
    )
    findings.resolve_finding(finding.id, "accepted_risk", "the owner will live with it")
    assert findings.open_allocated_to(5) == []


def test_reallocation_defers_to_a_later_gate_on_the_record(rows, findings):
    """The second exit: a finding that genuinely belongs later moves forward, with a reason
    the owner reads, and the move is logged rather than an in-place edit that leaves no trace."""
    finding = findings.file_finding(
        [_row(rows)], "a problem", "high", name="a problem", resolve_by=5
    )
    moved = findings.reallocate_finding(finding.id, 7, "the fix depends on the red-team pass")
    assert moved.resolve_by == 7
    assert findings.open_allocated_to(5) == []
    assert [f.id for f in findings.open_allocated_to(7)] == [finding.id]
    history = findings.reallocations_of(finding.id)
    assert len(history) == 1
    assert history[0]["from_package"] == 5 and history[0]["to_package"] == 7
    assert "red-team" in history[0]["reason"]


def test_reallocation_must_move_forward(rows, findings):
    """An earlier gate has passed or is where the finding should have been answered, so
    moving backward is not a deferral at all."""
    finding = findings.file_finding(
        [_row(rows)], "a problem", "high", name="a problem", resolve_by=5
    )
    for same_or_earlier in (5, 4):
        with pytest.raises(InvalidAllocation):
            findings.reallocate_finding(finding.id, same_or_earlier, "trying to go back")
    assert findings.get(finding.id).resolve_by == 5


def test_reallocation_needs_a_reason(rows, findings):
    finding = findings.file_finding(
        [_row(rows)], "a problem", "high", name="a problem", resolve_by=5
    )
    with pytest.raises(InvalidAllocation):
        findings.reallocate_finding(finding.id, 7, "   ")
    assert findings.get(finding.id).resolve_by == 5


def test_a_closed_finding_cannot_be_reallocated(rows, findings):
    """Moving the deadline of something already done is recording a deadline for nothing."""
    finding = findings.file_finding(
        [_row(rows)], "a problem", "high", name="a problem", resolve_by=5
    )
    findings.resolve_finding(finding.id, "addressed", "fixed")
    with pytest.raises(InvalidAllocation) as exc:
        findings.reallocate_finding(finding.id, 7, "too late")
    assert "left the scheme" in str(exc.value)
