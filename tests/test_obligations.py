"""The obligation surface (DEVIATIONS.md D12, fixing DEFECTS.md F23).

The point of every test here is the same one: an accounting check with no denominator
reports success over an empty question. F23 is the sixth instance of the plan naming a
mechanism it never built, and the first where the missing piece is the *set being counted*
rather than the trigger — so these tests are as much about what refuses as what passes.
"""

import pytest

from engine.models import RowSubmission
from engine.obligations import (
    AmendmentNeedsReason,
    NotEnumerated,
    ObligationSpec,
)


def _contract(rows, key, declared, title="a contract"):
    return rows.submit_rows(
        [RowSubmission(
            table="contracts",
            content={"title": title, "obligations": declared},
            name=title,
        )],
        key,
    ).verdicts[0].ref


# --- enumeration ---


def test_finalization_freezes_the_declared_surface(tasks, rows, obligations):
    """D12 — enumerated by the planning session, frozen at finalization, before and
    independently of any split later measured against it."""
    _contract(rows, "c1", [
        {"key": "behaviour", "kind": "behaviour", "statement": "does the thing"},
        {"key": "NotFound", "kind": "error", "statement": "names the missing id"},
    ])
    graph = tasks.finalize_plan()

    frozen = obligations.for_subtask(graph.subtasks[0].id)
    assert [o.ref for o in frozen] == ["contracts:1#behaviour", "contracts:1#NotFound"]
    assert [o.kind for o in frozen] == ["behaviour", "error"]
    assert graph.unenumerated == ()


def test_an_undeclared_surface_is_reported_never_invented(tasks, rows, obligations):
    """The tool records judgment, it never exercises it (`decisions:12`). A contract whose
    obligations nobody declared yields an empty set and a named report — not a guess
    parsed out of the contract's prose, which is the source D12 rejected."""
    rows.submit_rows(
        [RowSubmission(table="contracts", content={"title": "undeclared"}, name="undeclared")], "c1"
    )
    graph = tasks.finalize_plan()

    assert graph.unenumerated == ("contracts:1",)
    assert obligations.for_subtask(graph.subtasks[0].id) == ()


def test_a_malformed_declaration_is_not_enumerated(rows, obligations):
    """Not interpreted, not repaired: not enumerated. Every consumer then refuses loudly,
    which is the safe direction — a half-read declaration is a denominator nobody chose."""
    assert obligations.enumerate_from_row({"obligations": "behaviour, errors"}) == []
    assert obligations.enumerate_from_row({}) == []
    assert obligations.enumerate_from_row({"obligations": [{"kind": "error"}]}) == []


# --- the refusals that make F23 loud instead of silent ---


def test_verification_refuses_a_subtask_with_no_surface(tasks, rows):
    """F23's core failure, inverted. With no obligations the evidence loop iterates over
    nothing, `all()` is vacuously true and a pass is recorded for an empty question. It
    must fail instead."""
    rows.submit_rows(
        [RowSubmission(table="contracts", content={"title": "undeclared"}, name="undeclared")], "c1"
    )
    tasks.finalize_plan()
    tasks.serve_brief(1)

    with pytest.raises(NotEnumerated):
        tasks.verify_completion(1, {})


def test_verification_accounts_per_obligation_not_per_contract(tasks, rows):
    """Evidence maps per obligation, so a sub-task produced by a split cannot discharge its
    parent's whole contract by producing evidence for its own slice. M5a's
    `_scope_contracts` 1-tuple was the placeholder for exactly this."""
    from engine.tasks import EvidenceIncomplete

    _contract(rows, "c1", [
        {"key": "behaviour", "kind": "behaviour", "statement": "does the thing"},
        {"key": "NotFound", "kind": "error", "statement": "names the missing id"},
    ])
    tasks.finalize_plan()
    tasks.serve_brief(1)

    with pytest.raises(EvidenceIncomplete) as exc:
        tasks.verify_completion(1, {"contracts:1#behaviour": "tests pass"})
    assert "contracts:1#NotFound" in str(exc.value)
    assert "contracts:1#behaviour" not in str(exc.value)


# --- amendment: the recorded escape hatch ---


def test_amending_a_frozen_surface_demands_a_reason(tasks, rows, obligations):
    """D12 — the accounting can be changed, but not silently. Gaming it should require
    lying in a log the owner reads (requirements:79's shape)."""
    _contract(rows, "c1", [{"key": "behaviour", "statement": "does the thing"}])
    tasks.finalize_plan()

    with pytest.raises(AmendmentNeedsReason):
        obligations.amend("contracts:1", "retired", "", obligation_id=1)


def test_an_amendment_is_recorded_where_the_owner_sees_it(tasks, rows, obligations):
    _contract(rows, "c1", [{"key": "behaviour", "statement": "does the thing"}])
    tasks.finalize_plan()

    obligations.amend(
        "contracts:1", "added", "the error path was missed at enumeration",
        spec=ObligationSpec("Timeout", "error", "gives up and says so"),
        subtask_id=1,
    )
    assert [o.key for o in obligations.for_subtask(1)] == ["behaviour", "Timeout"]
    log = obligations.amendments()
    assert log[0]["action"] == "added"
    assert "missed at enumeration" in log[0]["reason"]


def test_a_retired_obligation_leaves_the_denominator(tasks, rows, obligations):
    _contract(rows, "c1", [
        {"key": "behaviour", "statement": "does the thing"},
        {"key": "NotFound", "kind": "error", "statement": "names the missing id"},
    ])
    tasks.finalize_plan()

    obligations.amend(
        "contracts:1", "retired", "folded into the primary behaviour", obligation_id=2
    )
    assert [o.key for o in obligations.for_subtask(1)] == ["behaviour"]
