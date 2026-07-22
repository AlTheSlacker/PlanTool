"""storage-engine (components:1)."""

import pytest

from engine.errors import (
    MigrationFailed,
    NoGoodVersion,
    PlanAlreadyExists,
    StorageUnavailable,
)
from engine.storage import Op, Storage


def test_init_plan_records_name_and_tier(tmp_path):
    with Storage(tmp_path) as store:
        handle = store.init_plan("widget planner", "deep")
        assert handle["name"] == "widget planner"
        assert handle["tier"] == "deep"
        assert handle["state"] == "draft"


def test_init_refuses_to_overwrite(store):
    """requirements:9 — refuse and offer resume, never overwrite."""
    with pytest.raises(PlanAlreadyExists) as exc:
        store.init_plan("another", "standard")
    assert exc.value.detail["name"] == "test plan"


def test_init_never_creates_the_workspace(tmp_path):
    """requirements:8 — the workspace itself is never created or managed by us."""
    with pytest.raises(StorageUnavailable):
        Storage(tmp_path / "does-not-exist").init_plan("p", "standard")


def test_write_atomic_is_idempotent(store):
    """decisions:43 — a replayed key returns the original receipt, never duplicates."""
    op = Op("insert", "links", {
        "source_ref": "a:1", "target_ref": "b:1", "edge_type": "links",
        "created_at": "now",
    })
    first = store.write_atomic([op], "key-1")
    second = store.write_atomic(
        [Op("insert", "links", {
            "source_ref": "a:1", "target_ref": "b:1", "edge_type": "links",
            "created_at": "now",
        })],
        "key-1",
    )
    assert second["replayed"] is True
    assert first["written_at"] == second["written_at"]
    assert len(store.query("SELECT * FROM links")) == 1


def test_failed_batch_leaves_no_partial_state(store):
    """requirements:6 — a failed write leaves no partial state."""
    good = Op("insert", "links", {
        "source_ref": "a:1", "target_ref": "b:1", "edge_type": "links",
        "created_at": "now",
    })
    bad = Op("insert", "links", {"nonexistent_column": "boom"})
    with pytest.raises(StorageUnavailable):
        store.write_atomic([good, bad], "key-2")
    assert store.query("SELECT * FROM links") == []


def test_no_writer_lock_surface_exists(store):
    """The writer lock was removed on 2026-07-22 — planning is one session, so there is
    nothing to lock against, and the lease's ten-minute takeover rule was the last place
    elapsed time decided who owned the data. This test fails if it comes back."""
    for gone in ("acquire_writer_lock", "renew_lease", "release_writer_lock"):
        assert not hasattr(store, gone), f"{gone} was deliberately removed"
    tables = {r["name"] for r in store.query(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    )}
    assert "writer_lease" not in tables


def test_integrity_check_names_unreadable_rows(store, rows):
    from engine.models import RowSubmission

    rows.submit_rows([RowSubmission("requirements", {"text": "fine"})], "k")
    store.conn.execute("UPDATE plan_rows SET content = '{not json' WHERE ordinal = 1")
    store.conn.commit()

    report = store.integrity_check()
    assert report.unreadable == ("requirements:1",)
    assert not report.ok


def test_snapshot_and_restore_round_trip(store, rows):
    from engine.models import RowSubmission

    rows.submit_rows([RowSubmission("requirements", {"text": "original"})], "k")
    store.snapshot_version("before damage")
    store.conn.execute("DELETE FROM plan_rows")
    store.conn.commit()

    report = store.recover("restore")
    assert report.strategy == "restore"
    assert len(store.query("SELECT * FROM plan_rows")) == 1


def test_restore_without_a_snapshot_is_refused(store):
    with pytest.raises(NoGoodVersion):
        store.recover("restore")


def test_salvage_drops_only_the_unreadable(store, rows):
    from engine.models import RowSubmission

    rows.submit_rows(
        [RowSubmission("requirements", {"text": "keep"}),
         RowSubmission("requirements", {"text": "lose"})],
        "k",
    )
    store.conn.execute("UPDATE plan_rows SET content = 'broken' WHERE ordinal = 2")
    store.conn.commit()

    report = store.recover("salvage")
    assert report.salvaged == ("requirements:1",)
    assert report.lost == ("requirements:2",)
    assert report.regapped == ("requirements:2",)


def test_migration_with_no_path_fails_loudly_and_restores(store, rows):
    """decisions:45 — silent migration is forbidden; failure restores the snapshot."""
    from engine.models import RowSubmission

    rows.submit_rows([RowSubmission("requirements", {"text": "survives"})], "k")
    with pytest.raises(MigrationFailed):
        store.migrate(99)
    assert len(store.query("SELECT * FROM plan_rows")) == 1
