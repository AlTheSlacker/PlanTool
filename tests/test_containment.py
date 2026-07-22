"""Every child row declares its owning parent, and the edge vocabulary is closed.

**DEFECTS.md F28.** v1 carried eight mandatory (NOT NULL) relations that were not
`plan_id`. The package-6 flattening into generic `plan_rows`/`links` preserved every row
and dropped every relation. Two were found by accident and repaired one at a time — F20
(`contract_deps`) and F24 (`contracts.component_id`). Sweeping `archive/v1`'s schema
found the other six, which is what the M6 gate item existed to stop us discovering the
third-through-eighth time by accident.

The loss is invisible by construction: an orphan `uc_steps` row is writable, readable and
gate-clean, and nothing anywhere asks what use case it belongs to. In v1 the database
refused it.

**Why submission-time rejection rather than a gate warning.** This is well-formedness,
not judgment — a step with no use case makes no claim, the same way a row with no
provenance makes none, and `_validate` has always rejected that outright. D7's
warn-don't-block stance governs *advisory* gate findings (open gaps, coverage) and is
untouched here.

**Why the map lives in the methodology.** `uc_steps` is this methodology's row type, not
the engine's. An engine that knows the name has begun to contain a methodology of its
own, which is `findings:4`. These tests therefore assert the *mechanism*, and read the
row-type names from the loaded revision rather than restating them.
"""

import sqlite3

import pytest

from engine.errors import StorageUnavailable
from engine.methodology import load
from engine.models import EDGE_TYPES, LinkSpec, RowRef, RowSubmission
from engine.rows import RowService


CONTAINMENT = load().containment


def _row(table, **kwargs):
    return RowSubmission(table=table, content={"title": f"a {table}"}, **kwargs)


def test_the_v1_relations_are_all_declared():
    """The sweep's result, pinned. If one is ever dropped from the manifest the loss
    returns silently, which is the whole failure mode.

    `contracts` -> `components` is v1's eighth mandatory relation and is deliberately
    **not** here. It is F24, already repaired, and enforced at *finalization* — a
    contract with no owner is reported there, never guessed. Declaring it a second time
    here would not restore a lost constraint, it would move an existing one earlier, and
    that is a change to when the tool interrupts the planner rather than a defect fix.
    See F28's note; the inconsistency is real and is the owner's call, not a side effect
    of this repair.
    """
    assert CONTAINMENT == {
        "uc_steps": "use_cases",
        "uc_extensions": "uc_steps",
        "crud_grid": "entities",
        "state_machines": "entities",
        "sm_cells": "state_machines",
        "dep_failure_modes": "dependencies",
    }


def test_an_orphan_child_is_rejected(rows):
    """The regression itself: v1's NOT NULL, restored."""
    receipt = rows.submit_rows([_row("uc_steps")], "orphan-step")
    verdict = receipt.verdicts[0]
    assert not verdict.accepted
    assert "belongs_to" in verdict.problem
    assert "use_cases" in verdict.problem


def test_a_child_with_its_parent_is_accepted(rows):
    """Parent and child in one batch — the normal interview shape, since a use case and
    its steps are elicited together."""
    receipt = rows.submit_rows(
        [_row("use_cases"), _row("uc_steps", links=[LinkSpec(0, "belongs_to")])],
        "step-with-parent",
    )
    assert [v.accepted for v in receipt.verdicts] == [True, True]


def test_a_child_pointing_at_the_wrong_row_type_is_rejected(rows):
    """The typo that a plain "has some belongs_to edge" check would wave through: the
    link exists, is well-formed, and points at the wrong kind of thing."""
    receipt = rows.submit_rows(
        [_row("entities"), _row("uc_steps", links=[LinkSpec(0, "belongs_to")])],
        "step-wrong-parent",
    )
    assert not receipt.verdicts[1].accepted
    assert "entities" in receipt.verdicts[1].problem


def test_two_parents_are_rejected(rows):
    """`belongs_to` is containment and containment is single. Two owners is v1's
    NOT NULL column holding two values."""
    receipt = rows.submit_rows(
        [
            _row("use_cases"),
            _row("use_cases"),
            _row("uc_steps", links=[LinkSpec(0, "belongs_to"), LinkSpec(1, "belongs_to")]),
        ],
        "step-two-parents",
    )
    assert not receipt.verdicts[2].accepted
    assert "exactly one" in receipt.verdicts[2].problem


def test_a_row_type_with_no_declared_parent_is_unaffected(rows):
    """Most row types are not contained by anything. The check must not invent a parent
    requirement for `decisions` because it happens to be adjacent in the manifest."""
    receipt = rows.submit_rows([_row("decisions")], "free-standing")
    assert receipt.verdicts[0].accepted


def test_an_unknown_edge_type_is_rejected(rows):
    """`links.edge_type` defaults to `'links'` and accepts any string, so a typo does not
    fail — it produces an edge no traversal looks for. That is F20's invisible-relation
    failure arriving by typo rather than by omission."""
    receipt = rows.submit_rows(
        [_row("decisions", links=[LinkSpec(RowRef("decisions", 1), "belogns_to")])],
        "typo-edge",
    )
    assert not receipt.verdicts[0].accepted
    assert "closed" in receipt.verdicts[0].problem


def test_every_edge_type_in_use_is_declared():
    """The vocabulary is only closed if it covers what the engine actually writes."""
    assert {"belongs_to", "depends_on", "cites", "contradicts", "links"} <= set(EDGE_TYPES)


def test_the_checks_can_actually_fail(store):
    """F23's disease: a check that cannot fail runs, passes and means nothing. If the
    containment map ever loads empty — a renamed manifest key, a YAML slip — every
    assertion above still passes while enforcing nothing."""
    assert CONTAINMENT, "containment map loaded empty; the checks above enforce nothing"
    disabled = RowService(store, containment={})
    receipt = disabled.submit_rows([_row("uc_steps")], "no-map")
    assert receipt.verdicts[0].accepted, (
        "with the map disabled an orphan must be accepted — otherwise the rejection "
        "above proves something other than the map"
    )


def test_a_row_and_its_links_commit_together(store):
    """The orphan this file refuses on the way in must not be creatable on the way out.

    Links used to be written in a *second* transaction, because a link needs its source
    row's ref and refs are assigned inside the first one. Harmless while links were
    optional; not harmless once `belongs_to` became mandatory — a successful row write
    followed by a failed link write left precisely the orphan state submission rejects.
    """
    rows = RowService(store)
    original = store._apply

    def fail_on_links(op, batch=None):
        if op.table == "links":
            raise sqlite3.OperationalError("simulated failure writing links")
        return original(op, batch)

    store._apply = fail_on_links
    try:
        with pytest.raises(StorageUnavailable):
            rows.submit_rows(
                [_row("use_cases"), _row("uc_steps", links=[LinkSpec(0, "belongs_to")])],
                "atomic",
            )
    finally:
        store._apply = original

    assert store.query("SELECT * FROM plan_rows") == [], (
        "the use case was committed while its step's link failed — rows and their "
        "edges must land in one transaction or neither"
    )
