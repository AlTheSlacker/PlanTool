"""conflict-service (components:8)."""

import pytest

from engine.conflicts import (
    AlreadyResolved,
    ConflictNotFound,
    ConflictService,
    GateScope,
    RefNotFound,
)
from engine.errors import ConflictRequired
from engine.models import LinkSpec, RowRef, RowSelector, RowSubmission
from engine.rows import RowService


@pytest.fixture
def two_rows(rows):
    rows.submit_rows(
        [
            RowSubmission("decisions", {"text": "store plans in SQLite"}),
            RowSubmission("decisions", {"text": "store plans in Postgres"}),
        ],
        "k",
    )
    return RowRef("decisions", 1), RowRef("decisions", 2)


def raise_one(conflicts, refs):
    return conflicts.raise_conflict(
        list(refs),
        description="two rows name different stores for the same data",
        recommendation="keep SQLite; the no-server constraint rules Postgres out",
    )


# --- contracts:26 -----------------------------------------------------------------


def test_a_conflict_records_both_sides_and_the_recommendation(conflicts, two_rows):
    conflict = raise_one(conflicts, two_rows)
    assert conflict.is_open
    assert conflict.refs == two_rows
    assert "SQLite" in conflict.recommendation


def test_a_contested_ref_that_does_not_exist_is_named_and_nothing_is_filed(conflicts):
    with pytest.raises(RefNotFound) as exc:
        raise_one(conflicts, [RowRef("decisions", 99)])
    assert "decisions:99" in str(exc.value)
    assert conflicts.open_conflicts() == []


def test_a_conflict_without_a_recommendation_is_refused(conflicts, two_rows):
    """use_cases:7 — both sides AND the engineering recommendation are presented."""
    with pytest.raises(RefNotFound):
        conflicts.raise_conflict(list(two_rows), "they disagree", "   ")


def test_conflict_and_its_refs_land_in_one_transaction(conflicts, store, two_rows):
    """A conflict whose refs failed to land would block nothing, silently."""
    raise_one(conflicts, two_rows)
    stored = store.query("SELECT COUNT(*) AS n FROM conflict_refs")[0]["n"]
    assert stored == 2


# --- contracts:28 -----------------------------------------------------------------


def test_a_restart_clears_the_conflict_ledger(conflicts, store, two_rows):
    """A conflict contesting a row that no longer exists would block gates forever."""
    raise_one(conflicts, two_rows)
    store.recover("restart")
    assert conflicts.open_conflicts() == []
    assert store.query("SELECT COUNT(*) AS n FROM conflict_refs")[0]["n"] == 0


def test_a_snapshot_round_trip_preserves_open_conflicts(conflicts, store, two_rows):
    """Restoring a snapshot that dropped them would silently unblock the gates."""
    conflict = raise_one(conflicts, two_rows)
    store.snapshot_version("before")
    conflicts.resolve_conflict(conflict.id, "revised", "settled")
    store.recover("restore")
    assert [c.id for c in conflicts.open_conflicts()] == [conflict.id]


def test_an_open_conflict_blocks_a_gate_whose_scope_it_contests(conflicts, two_rows):
    raise_one(conflicts, two_rows)
    blocking = conflicts.blocking_conflicts(GateScope(tables=("decisions",)))
    assert len(blocking) == 1
    assert "decisions:1" in blocking[0].blockage_reason()


def test_a_conflict_outside_the_scope_does_not_block(conflicts, two_rows):
    raise_one(conflicts, two_rows)
    assert conflicts.blocking_conflicts(GateScope(tables=("components",))) == []


def test_a_resolved_conflict_stops_blocking(conflicts, two_rows):
    conflict = raise_one(conflicts, two_rows)
    conflicts.resolve_conflict(conflict.id, "revised", "we drop Postgres")
    assert conflicts.blocking_conflicts(GateScope(tables=("decisions",))) == []


# --- contracts:27 -----------------------------------------------------------------


def test_resolution_records_outcome_and_adjudication_permanently(conflicts, two_rows):
    conflict = raise_one(conflicts, two_rows)
    resolution = conflicts.resolve_conflict(
        conflict.id, "overridden", "I want Postgres anyway; I'll run a server."
    )
    assert resolution.outcome == "overridden"
    stored = conflicts.get(conflict.id)
    assert stored.state == "resolved_overridden"
    assert "run a server" in stored.adjudication


def test_re_adjudication_requires_a_new_conflict(conflicts, two_rows):
    """requirements:29 — the record is permanent; an override stays visible."""
    conflict = raise_one(conflicts, two_rows)
    conflicts.resolve_conflict(conflict.id, "revised", "drop Postgres")
    with pytest.raises(AlreadyResolved):
        conflicts.resolve_conflict(conflict.id, "overridden", "changed my mind")
    assert conflicts.get(conflict.id).outcome == "revised"


def test_an_unknown_conflict_is_named(conflicts):
    with pytest.raises(ConflictNotFound):
        conflicts.resolve_conflict(404, "revised", "...")


def test_an_unquoted_adjudication_is_refused(conflicts, two_rows):
    conflict = raise_one(conflicts, two_rows)
    with pytest.raises(ConflictNotFound):
        conflicts.resolve_conflict(conflict.id, "revised", "  ")


def test_an_unknown_outcome_is_refused(conflicts, two_rows):
    conflict = raise_one(conflicts, two_rows)
    with pytest.raises(ConflictNotFound):
        conflicts.resolve_conflict(conflict.id, "ignored", "whatever")


# --- the contradiction detector (requirements:27, DEFECTS.md F4/F8) ----------------


def test_a_declared_contradiction_is_refused_until_a_conflict_is_raised(store):
    """requirements:27 — the conflict is raised and presented BEFORE the row is
    filed."""
    conflicts = ConflictService(store)
    rows = RowService(store, detector=conflicts.detector())
    rows.submit_rows([RowSubmission("decisions", {"text": "SQLite"})], "k1")

    with pytest.raises(ConflictRequired) as exc:
        rows.submit_rows(
            [
                RowSubmission(
                    "decisions",
                    {"text": "Postgres"},
                    links=[LinkSpec(RowRef("decisions", 1), edge_type="contradicts")],
                )
            ],
            "k2",
        )
    assert "decisions:1" in str(exc.value)
    assert len(rows.read_rows(RowSelector(limit=100)).rows) == 1  # nothing filed


def test_the_row_files_once_the_conflict_exists(store):
    conflicts = ConflictService(store)
    rows = RowService(store, detector=conflicts.detector())
    rows.submit_rows([RowSubmission("decisions", {"text": "SQLite"})], "k1")
    conflicts.raise_conflict(
        [RowRef("decisions", 1)],
        "the new row says Postgres",
        "keep SQLite; no-server constraint",
    )
    receipt = rows.submit_rows(
        [
            RowSubmission(
                "decisions",
                {"text": "Postgres"},
                links=[LinkSpec(RowRef("decisions", 1), edge_type="contradicts")],
            )
        ],
        "k2",
    )
    assert all(v.accepted for v in receipt.verdicts)


def test_an_ordinary_link_is_not_a_contradiction(store):
    """The detector is mechanical: only a `contradicts` edge triggers it."""
    conflicts = ConflictService(store)
    rows = RowService(store, detector=conflicts.detector())
    rows.submit_rows([RowSubmission("use_cases", {"title": "Order"})], "k1")
    receipt = rows.submit_rows(
        [RowSubmission("requirements", {"title": "Orders persist"},
                       links=[LinkSpec(RowRef("use_cases", 1))])],
        "k2",
    )
    assert all(v.accepted for v in receipt.verdicts)
