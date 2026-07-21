"""finding-service (components:10) — contracts:33/34."""

import pytest

from engine.findings import (
    ACCEPTED_RISK,
    ADDRESSED,
    DISPUTED,
    FILED,
    FindingNotFound,
    InvalidTransition,
    RefNotFound,
)
from engine.models import RowSubmission


def _row(rows, text="the gate criteria are too weak", key=None):
    receipt = rows.submit_rows(
        [RowSubmission(table="requirements", content={"text": text})],
        key or f"row:{text}",
    )
    return receipt.verdicts[0].ref


# --- contracts:33 file_finding ---


def test_file_finding_links_the_attacked_rows(rows, findings):
    ref = _row(rows)
    finding = findings.file_finding([ref], "package 4 gate passes with zero tests", "high")

    assert finding.state == FILED
    assert finding.refs == (ref,)
    assert finding.severity == "high"
    assert finding.is_open is True


def test_file_finding_rejects_unknown_ref(findings):
    with pytest.raises(RefNotFound) as exc:
        findings.file_finding(["requirements:99"], "a problem", "low")
    assert "requirements:99" in str(exc.value)


def test_file_finding_requires_refs(findings):
    """requirements:31 — findings attack specific rows."""
    with pytest.raises(RefNotFound):
        findings.file_finding([], "the plan feels wrong", "low")


def test_file_finding_requires_description_and_severity(rows, findings):
    ref = _row(rows)
    with pytest.raises(RefNotFound):
        findings.file_finding([ref], "  ", "high")
    with pytest.raises(RefNotFound):
        findings.file_finding([ref], "a real problem", "")


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
    finding = findings.file_finding([_row(rows)], "a problem", "high")
    resolved = findings.resolve_finding(finding.id, "addressed", "fixed in requirements:12")

    assert resolved.state == ADDRESSED
    assert resolved.is_open is False
    with pytest.raises(InvalidTransition) as exc:
        findings.resolve_finding(finding.id, "accepted_risk", "actually, no")
    assert "terminal" in str(exc.value)


def test_accepted_risk_stays_visible_at_handoff(rows, findings):
    """requirements:33 — an accepted risk is a known issue, not a closed one."""
    finding = findings.file_finding([_row(rows)], "no rollback path", "medium")
    resolved = findings.resolve_finding(
        finding.id, "accepted_risk", "owner accepts: manual restore is acceptable"
    )

    assert resolved.state == ACCEPTED_RISK
    assert resolved.visible_at_handoff is True
    assert resolved.is_open is False          # requirements:32 — explicitly accepted
    assert [f.id for f in findings.accepted_risks()] == [finding.id]


def test_open_findings_fail_the_verification_gate(rows, findings):
    """requirements:32 — neither addressed nor explicitly accepted means still open."""
    kept = findings.file_finding([_row(rows, "a", key="a")], "unresolved", "high")
    done = findings.file_finding([_row(rows, "b", key="b")], "resolved", "high")
    findings.resolve_finding(done.id, "addressed", "fixed")

    assert [f.id for f in findings.open_findings()] == [kept.id]


def test_resolve_requires_a_rationale(rows, findings):
    finding = findings.file_finding([_row(rows)], "a problem", "high")
    with pytest.raises(InvalidTransition):
        findings.resolve_finding(finding.id, "accepted_risk", "   ")


def test_unknown_finding_is_named(findings):
    with pytest.raises(FindingNotFound) as exc:
        findings.get(404)
    assert "404" in str(exc.value)


# --- state_machines:7 dispute path (DEFECTS.md F13) ---


def test_withdraw_requires_a_dispute_first(rows, findings):
    """sm_cells:92 — a finding nobody disputed cannot be withdrawn."""
    finding = findings.file_finding([_row(rows)], "a problem", "high")
    with pytest.raises(InvalidTransition) as exc:
        findings.resolve_finding(finding.id, "withdrawn", "never mind")
    assert "no dispute open" in str(exc.value)
    assert findings.get(finding.id).state == FILED


def test_dispute_then_withdraw(rows, findings):
    finding = findings.file_finding([_row(rows)], "a problem", "high")
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
    finding = findings.file_finding([_row(rows)], "a problem", "high")
    findings.dispute_finding(finding.id, "this is out of scope")
    upheld = findings.uphold_finding(finding.id, "scope includes it; the finding stands")

    assert upheld.state == FILED
    assert upheld.dispute is None
    # Having been disputed once, it can now take any of the three outcomes.
    assert findings.resolve_finding(finding.id, "addressed", "fixed").state == ADDRESSED


def test_disputed_finding_cannot_be_addressed_directly(rows, findings):
    """sm_cells:98 — settle the dispute first."""
    finding = findings.file_finding([_row(rows)], "a problem", "high")
    findings.dispute_finding(finding.id, "disagree")
    with pytest.raises(InvalidTransition) as exc:
        findings.resolve_finding(finding.id, "addressed", "fixed anyway")
    assert "settle the dispute first" in str(exc.value)
    assert findings.get(finding.id).state == DISPUTED


def test_accepted_risk_can_be_reopened_by_dispute(rows, findings):
    """sm_cells:105 — accepted_risk is visible, not settled."""
    finding = findings.file_finding([_row(rows)], "a problem", "high")
    findings.resolve_finding(finding.id, "accepted_risk", "owner accepts")
    assert findings.dispute_finding(finding.id, "this risk is not acceptable").state == DISPUTED


def test_findings_for_a_row(rows, findings):
    ref = _row(rows)
    finding = findings.file_finding([ref], "a problem", "high")
    assert [f.id for f in findings.findings_for(ref)] == [finding.id]
