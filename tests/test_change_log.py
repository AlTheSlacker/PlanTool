"""change_log — the GUI's polling feed (DEVIATIONS.md D28).

The feed is fed at storage's single write choke point and the op-type is inferred from the
columns each write touches. These tests pin both halves: that every mutation kind lands the
right row, and that the boundaries hold — a replay or a rolled-back batch records nothing, and
a wholesale rewrite records one `resync` rather than a per-row flood.
"""

import pytest

from engine.errors import StorageUnavailable
from engine.models import RowSubmission
from engine.rows import RowService
from engine.storage import Op, Storage


def _log(store):
    return store.query("SELECT * FROM change_log ORDER BY seq")


def _submit(rows, table="requirements", text="x", name="a requirement"):
    receipt = rows.submit_rows(
        [RowSubmission(table, {"text": text}, name=name)], f"submit-{name}"
    )
    return receipt.verdicts[0].ref


# --- create ---

def test_insert_row_records_create(store, rows):
    ref = _submit(rows)
    entry = _log(store)[-1]
    assert entry["op_type"] == "create"
    assert entry["ref"] == str(ref)
    assert entry["replaced_by"] is None


def test_plain_insert_records_create_with_table_id_ref(store):
    store.write_atomic(
        [Op("insert", "links", {
            "source_ref": "a:1", "target_ref": "b:1", "edge_type": "links",
            "created_at": "now",
        })],
        "link-1",
    )
    entry = _log(store)[-1]
    assert entry["op_type"] == "create"
    assert entry["ref"] == "links:1"


# --- supersede ---

def test_supersede_records_create_and_supersede_with_pointer(store, rows):
    old = _submit(rows, name="original")
    result = rows.supersede_row(
        old, RowSubmission("requirements", {"text": "v2"}, name="sharper"),
        "the first wording was ambiguous", "sup-1"
    )
    new = result["new"]

    log = _log(store)
    creates = [e for e in log if e["op_type"] == "create" and e["ref"] == str(new)]
    supersedes = [e for e in log if e["op_type"] == "supersede" and e["ref"] == str(old)]

    assert len(creates) == 1, "the replacement is announced as a create"
    assert len(supersedes) == 1, "the old row's two stamps are one supersede, not two"
    assert supersedes[0]["replaced_by"] == str(new), "the pointer op's ref is kept"


def test_supersede_by_superseded_at_only_has_no_pointer(store):
    """scope_attachments supersedes by stamping superseded_at alone — no back-pointer to a
    replacement, so replaced_by is null and the GUI re-queries the live row."""
    store.write_atomic(
        [Op("insert", "scope_attachments", {
            "scope_level": "plan", "scope_key": "", "target_root": "requirements:1",
            "reason": "seed", "created_at": "now",
        })],
        "attach-1",
    )
    store.write_atomic(
        [Op("update", "scope_attachments", {"superseded_at": "now"}, where={"id": 1})],
        "attach-supersede",
    )
    entry = _log(store)[-1]
    assert entry["op_type"] == "supersede"
    assert entry["ref"] == "scope_attachments:1"
    assert entry["replaced_by"] is None


# --- retire ---

def test_retire_records_retire(store, rows):
    ref = _submit(rows, name="doomed")
    rows.retire_row(ref, "no longer true", "ret-1")
    entry = _log(store)[-1]
    assert entry["op_type"] == "retire"
    assert entry["ref"] == str(ref)


# --- state_change vs plain update ---

def test_state_change_is_recorded(store, rows):
    ref = _submit(rows, name="mover")
    store.write_atomic(
        [Op("update", "plan_rows", {"state": "active"},
            where={"table_name": ref.table, "ordinal": ref.ordinal})],
        "state-1",
    )
    entry = _log(store)[-1]
    assert entry["op_type"] == "state_change"
    assert entry["ref"] == str(ref)


def test_plain_in_place_edit_records_update(store, rows):
    ref = _submit(rows, name="editable")
    store.write_atomic(
        [Op("update", "plan_rows", {"name": "renamed", "named_for": "abc"},
            where={"table_name": ref.table, "ordinal": ref.ordinal})],
        "edit-1",
    )
    entry = _log(store)[-1]
    assert entry["op_type"] == "update"
    assert entry["ref"] == str(ref)


def test_supersede_column_beats_state_in_the_same_write(store, rows):
    """rows.py stamps state and superseded_at in one op; the supersession is the story."""
    ref = _submit(rows, name="both")
    store.write_atomic(
        [Op("update", "plan_rows", {"state": "superseded", "superseded_at": "now"},
            where={"table_name": ref.table, "ordinal": ref.ordinal})],
        "both-1",
    )
    assert _log(store)[-1]["op_type"] == "supersede"


# --- boundaries ---

def test_update_matching_no_row_records_nothing(store):
    before = len(_log(store))
    store.write_atomic(
        [Op("update", "plan_rows", {"state": "active"},
            where={"table_name": "requirements", "ordinal": 999})],
        "phantom",
    )
    assert len(_log(store)) == before, "an update that changed no row announces nothing"


def test_idempotent_replay_records_nothing_extra(store):
    op = Op("insert", "links", {
        "source_ref": "a:1", "target_ref": "b:1", "edge_type": "links", "created_at": "now",
    })
    store.write_atomic([op], "replay-key")
    after_first = len(_log(store))
    store.write_atomic(
        [Op("insert", "links", {
            "source_ref": "a:1", "target_ref": "b:1", "edge_type": "links",
            "created_at": "now",
        })],
        "replay-key",
    )
    assert len(_log(store)) == after_first, "a replay re-runs no op, so it records no change"


def test_rolled_back_batch_records_nothing(store):
    before = len(_log(store))
    good = Op("insert", "links", {
        "source_ref": "a:1", "target_ref": "b:1", "edge_type": "links", "created_at": "now",
    })
    bad = Op("insert", "links", {"nonexistent_column": "boom"})
    with pytest.raises(StorageUnavailable):
        store.write_atomic([good, bad], "doomed-batch")
    assert len(_log(store)) == before, "the whole batch rolled back, feed included"


# --- polling ---

def test_poll_returns_only_changes_after_the_cursor(store, rows):
    _submit(rows, name="first")
    cursor = store.query("SELECT MAX(seq) AS s FROM change_log")[0]["s"]
    _submit(rows, name="second")
    _submit(rows, name="third")
    fresh = store.query(
        "SELECT * FROM change_log WHERE seq > ? ORDER BY seq", (cursor,)
    )
    refs = [e["ref"] for e in fresh]
    assert refs == ["requirements:2", "requirements:3"]


# --- resync on wholesale rewrite ---

def test_restore_emits_resync_and_preserves_the_feed(store, rows):
    _submit(rows, name="pre-snapshot")
    snapshot = store.snapshot_version("test")
    _submit(rows, name="after-snapshot")
    history_before = len(_log(store))

    store.restore_snapshot(snapshot)

    log = _log(store)
    assert log[-1]["op_type"] == "resync", "a rewind tells the GUI to full-reload"
    assert log[-1]["ref"] is None
    assert len(log) == history_before + 1, "the feed's own history survives the rewind"


def test_recover_restart_emits_resync(store, rows):
    _submit(rows, name="soon-gone")
    store.recover("restart")
    assert _log(store)[-1]["op_type"] == "resync"


# --- migration ---

def test_migration_6_to_7_creates_an_empty_change_log(store):
    """A plan written before the feed existed has no change history; the 6 -> 7 step creates
    the table empty rather than backfilling a past it never had."""
    store.conn.execute("DROP TABLE change_log")
    store.conn.execute("UPDATE plan SET schema_version = 6 WHERE guard = 1")
    store.conn.commit()

    report = store.migrate(7)
    assert (report.from_version, report.to_version) == (6, 7)
    assert store.query("SELECT COUNT(*) AS n FROM change_log")[0]["n"] == 0
