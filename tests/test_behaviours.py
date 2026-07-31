"""The behaviour surface (DEVIATIONS.md D12, fixing DEFECTS.md F23).

The point of every test here is the same one: an accounting check with no denominator
reports success over an empty question. F23 is the sixth instance of the plan naming a
mechanism it never built, and the first where the missing piece is the *set being counted*
rather than the trigger — so these tests are as much about what refuses as what passes.
"""

import pytest

from engine.models import RowSubmission
from engine.behaviours import (
    AmendmentNeedsReason,
    BehaviourSpec,
    NotEnumerated,
)


def _contract(rows, key, declared, title="a contract"):
    return rows.submit_rows(
        [RowSubmission(
            table="contracts",
            content={"title": title, "behaviours": declared},
            name=title,
        )],
        key,
    ).verdicts[0].ref


# --- enumeration ---


def test_finalization_freezes_the_declared_surface(tasks, rows, behaviours):
    """D12 — enumerated by the planning session, frozen at finalization."""
    _contract(rows, "c1", [
        {"key": "effect", "kind": "effect", "statement": "does the thing"},
        {"key": "NotFound", "kind": "error", "statement": "names the missing id"},
    ])
    graph = tasks.finalize_plan()

    frozen = behaviours.for_task(graph.tasks[0].id)
    assert [b.ref for b in frozen] == ["contracts:1#effect", "contracts:1#NotFound"]
    assert [b.kind for b in frozen] == ["effect", "error"]
    assert graph.unenumerated == ()


def test_the_kind_and_the_key_do_not_both_say_behaviour(rows, behaviours):
    """One word for two things is the disease this change exists to remove. A `Behaviour`
    of kind "behaviour" whose ref reads `contracts:40#behaviour` says nothing twice; the
    main one is an *effect*, which is the word INTERVIEW.md §4 already uses."""
    specs = behaviours.enumerate_from_row({"behaviours": ["does the thing", "and this"]})
    assert [(s.key, s.kind) for s in specs] == [("effect", "effect"), ("b1", "effect")]


def test_an_undeclared_surface_is_reported_never_invented(tasks, rows, behaviours):
    """The tool records judgment, it never exercises it (`decisions:12`). A contract whose
    behaviours nobody declared yields an empty set and a named report — not a guess
    parsed out of the contract's prose, which is the source D12 rejected."""
    rows.submit_rows(
        [RowSubmission(table="contracts", content={"title": "undeclared"}, name="undeclared")], "c1"
    )
    graph = tasks.finalize_plan()

    assert [str(r) for r in graph.unenumerated] == ["contracts:1"]
    assert behaviours.for_task(graph.tasks[0].id) == ()


def test_a_malformed_declaration_is_not_enumerated(rows, behaviours):
    """Not interpreted, not repaired: not enumerated. Every consumer then refuses loudly,
    which is the safe direction — a half-read declaration is a denominator nobody chose."""
    assert behaviours.enumerate_from_row({"behaviours": "effect, errors"}) == []
    assert behaviours.enumerate_from_row({}) == []
    assert behaviours.enumerate_from_row({"behaviours": [{"kind": "error"}]}) == []


def test_the_old_key_is_not_read(rows, behaviours):
    """The array is `behaviours`. A contract row still carrying `obligations` is not
    silently accepted: the 7 -> 8 migration moves the key, and a store where it was not
    moved is unenumerated — loudly — rather than half-read under two spellings."""
    assert behaviours.enumerate_from_row({"obligations": ["does the thing"]}) == []


# --- the refusals that make F23 loud instead of silent ---


def test_verification_refuses_a_task_with_no_surface(tasks, rows):
    """F23's core failure, inverted. With no behaviours the evidence loop iterates over
    nothing, `all()` is vacuously true and a pass is recorded for an empty question. It
    must fail instead."""
    rows.submit_rows(
        [RowSubmission(table="contracts", content={"title": "undeclared"}, name="undeclared")], "c1"
    )
    tasks.finalize_plan()
    tasks.serve_brief(1)

    with pytest.raises(NotEnumerated):
        tasks.verify_completion(1, {})


def test_verification_accounts_per_behaviour_not_per_contract(tasks, rows):
    """Evidence maps per behaviour, so a task cannot discharge its whole contract by
    producing evidence for one slice of it. M5a's `_scope_contracts` 1-tuple was the
    placeholder for exactly this."""
    from engine.tasks import EvidenceIncomplete

    _contract(rows, "c1", [
        {"key": "effect", "kind": "effect", "statement": "does the thing"},
        {"key": "NotFound", "kind": "error", "statement": "names the missing id"},
    ])
    tasks.finalize_plan()
    tasks.serve_brief(1)

    with pytest.raises(EvidenceIncomplete) as exc:
        tasks.verify_completion(1, {"contracts:1#effect": "tests pass"})
    assert "contracts:1#NotFound" in str(exc.value)
    assert "contracts:1#effect" not in str(exc.value)


# --- amendment: the recorded escape hatch ---


def test_amending_a_frozen_surface_demands_a_reason(tasks, rows, behaviours):
    """D12 — the accounting can be changed, but not silently. Gaming it should require
    lying in a log the owner reads (requirements:79's shape)."""
    _contract(rows, "c1", [{"key": "effect", "statement": "does the thing"}])
    tasks.finalize_plan()

    with pytest.raises(AmendmentNeedsReason):
        behaviours.amend("contracts:1", "retired", "", behaviour_id=1)


def test_an_amendment_is_recorded_where_the_owner_sees_it(tasks, rows, behaviours):
    _contract(rows, "c1", [{"key": "effect", "statement": "does the thing"}])
    tasks.finalize_plan()

    behaviours.amend(
        "contracts:1", "added", "the error path was missed at enumeration",
        spec=BehaviourSpec("Timeout", "error", "gives up and says so"),
        task_id=1,
    )
    assert [b.key for b in behaviours.for_task(1)] == ["effect", "Timeout"]
    log = behaviours.amendments()
    assert log[0]["action"] == "added"
    assert "missed at enumeration" in log[0]["reason"]


def test_a_retired_behaviour_leaves_the_denominator(tasks, rows, behaviours):
    _contract(rows, "c1", [
        {"key": "effect", "statement": "does the thing"},
        {"key": "NotFound", "kind": "error", "statement": "names the missing id"},
    ])
    tasks.finalize_plan()

    behaviours.amend(
        "contracts:1", "retired", "folded into the main effect", behaviour_id=2
    )
    assert [b.key for b in behaviours.for_task(1)] == ["effect"]
