"""What `label_attachments` guarantees at the store, asserted in raw SQL.

**These cannot be written through the service, and that is the whole reason this file
exists.** `attach_label` treats a duplicate as a no-op, so a service-driven test passes
against a completely inert index — and the *natural* spelling of that index is completely
inert. Probed at SQLite 3.49.1: every row here has exactly one NULL among the two target
columns, and SQL compares NULLs as distinct, so `(word, target_root, task_id)` accepts
**every** duplicate for the whole life of the table. `PRAGMA index_list` reports the two
forms identically, so `test_schema_parity.py` cannot tell them apart either.

The same reasoning covers the `CHECK`s: both `COALESCE` sentinels are reachable, and only a
test that inserts them directly says so.
"""

import sqlite3

import pytest

from engine import schema
from engine.storage import Storage
from tests.fixtures.schema_v10 import DDL_V10


def _attach(store, word, root=None, task_id=None, detached_at=None):
    store.conn.execute(
        "INSERT INTO label_attachments (word, target_root, task_id, detached_at, "
        "created_at) VALUES (?, ?, ?, ?, '2026-08-03T00:00:00+00:00')",
        (word, root, task_id, detached_at),
    )
    store.conn.commit()


def test_the_live_index_refuses_a_duplicate_on_a_row(store):
    _attach(store, "engine", root="requirements:1")
    with pytest.raises(sqlite3.IntegrityError):
        _attach(store, "engine", root="requirements:1")


def test_the_live_index_refuses_a_duplicate_on_a_task(store):
    """The half the naive index misses most obviously: for a task attachment `target_root`
    is NULL on both rows, so the natural form compares them as distinct."""
    store.conn.execute(
        "INSERT INTO tasks (id, contract_ref, title, state, serve_epoch, created_at, "
        "updated_at) VALUES (1, 'contracts:1', 't', 'pending', 0, 'now', 'now')"
    )
    _attach(store, "engine", task_id=1)
    with pytest.raises(sqlite3.IntegrityError):
        _attach(store, "engine", task_id=1)


def test_a_detached_attachment_leaves_the_word_free_again(store):
    """The index is partial on `detached_at IS NULL`, which is what lets a label be put
    back on a target it was taken off."""
    _attach(store, "engine", root="requirements:1", detached_at="2026-08-03T00:00:00Z")
    _attach(store, "engine", root="requirements:1")
    rows = store.query("SELECT * FROM label_attachments")
    assert len(rows) == 2


def test_two_words_on_one_target_are_permitted(store):
    """A reference carries as many labels as are attached to it — the live index is unique
    on *(word, target)*, so a second word on the same target is a different key. There is no
    cap, and deliberately no warning above some number: a rule saying five is fine and six
    is not is a threshold."""
    _attach(store, "engine", root="requirements:1")
    _attach(store, "schema", root="requirements:1")
    assert len(store.query("SELECT * FROM label_attachments")) == 2


def test_both_coalesce_sentinels_are_refused(store):
    """Both are reachable without the `CHECK`s, and each collides with the other kind of
    target under the index key `(word, '', 0)`.

    The draft asserted that `INSERT INTO tasks (id) VALUES (0)` is *refused* — but nothing
    in this change touches `tasks`, and the DDL comment says the opposite, that such a row
    is accepted once its NOT NULL columns are supplied. Written literally that test fails,
    and the tempting repair is to constrain `tasks`, which nobody specified. What this
    change constrains is `label_attachments`, and that is what is asserted.
    """
    with pytest.raises(sqlite3.IntegrityError):
        _attach(store, "engine", root="")
    with pytest.raises(sqlite3.IntegrityError):
        _attach(store, "engine", task_id=0)


def test_exactly_one_target_is_set(store):
    with pytest.raises(sqlite3.IntegrityError):
        _attach(store, "engine", root="requirements:1", task_id=1)
    with pytest.raises(sqlite3.IntegrityError):
        _attach(store, "engine")


def test_a_task_id_of_zero_is_reachable_and_that_is_why_the_check_exists(store):
    """The probe this change inherited and re-ran, because it was false as recorded.

    The old note claimed `INSERT INTO tasks (id) VALUES (0)` is accepted despite
    AUTOINCREMENT; `tasks` has four NOT NULL columns and it fails on the first. Re-probed
    properly — with them supplied — task id 0 *is* reachable, so the conclusion survived and
    the evidence did not.
    """
    store.conn.execute(
        "INSERT INTO tasks (id, contract_ref, title, state, serve_epoch, created_at, "
        "updated_at) VALUES (0, 'contracts:1', 't', 'pending', 0, 'now', 'now')"
    )
    store.conn.commit()
    assert store.query("SELECT id FROM tasks")[0]["id"] == 0


def test_the_and_filter_needs_count_distinct(store, rows):
    """A duplicate live attachment makes `COUNT(*)` return a row carrying only one of two
    requested labels. It **cannot be created through the service** — `attach_label` no-ops a
    duplicate — and it cannot be created in raw SQL either while the index is correct, so
    the index is dropped first: this asserts that the query is right *independently of the
    constraint*, which is what a query should be when the constraint protecting it has
    already been observed to fail in its natural spelling.

    The draft put this in the service tests against a three-row fixture, where the two
    spellings return the same rows and the test catches OR and nothing else.
    """
    from engine.models import RowSelector, RowSubmission

    rows.submit_rows(
        [RowSubmission(table="requirements", content={"t": "a"}, name="one"),
         RowSubmission(table="requirements", content={"t": "b"}, name="two")],
        "k",
    )
    store.conn.execute("DROP INDEX idx_label_attachments_live")
    _attach(store, "engine", root="requirements:1")
    _attach(store, "engine", root="requirements:1")  # the duplicate, now insertable
    _attach(store, "schema", root="requirements:2")
    _attach(store, "engine", root="requirements:2")

    found = {str(r.ref) for r in rows.read_rows(
        RowSelector(labels=("engine", "schema"))
    ).rows}
    assert found == {"requirements:2"}, (
        "requirements:1 carries `engine` twice and `schema` never; COUNT(*) would return it"
    )


def test_the_snapshot_carries_attachments_and_a_restore_brings_them_back(store, rows):
    """`label_attachments` is in the snapshot table set, which reverses the draft. It is an
    overlay keyed on lineage roots — the same primitive as `gap_overlay` — holding judgments
    that cannot be recomputed from the rows. Left out, `restore_snapshot` on an abandoned
    revision would strand attachments on roots that no longer exist and
    `recover('restart')` would orphan every one of them, neither column carrying a foreign
    key to catch it.

    The round trip is what proves it, since the table list is a tuple in `storage.py` that
    no test reads.
    """
    from engine.models import RowSubmission

    rows.submit_rows(
        [RowSubmission(table="requirements", content={"t": "a"}, name="one")], "k"
    )
    _attach(store, "engine", root="requirements:1")
    snapshot = store.snapshot_version("before")
    store.conn.execute("DELETE FROM label_attachments")
    store.conn.commit()
    assert store.query("SELECT * FROM label_attachments") == []

    store.restore_snapshot(snapshot)
    restored = store.query("SELECT word, target_root FROM label_attachments")
    assert [(r["word"], r["target_root"]) for r in restored] == [
        ("engine", "requirements:1")
    ]


def test_the_attachment_table_is_not_a_junction(store):
    """A new table with no `updated_at` looks like a junction, and this is not one: it has
    independent existence and its own lifecycle stamp in `detached_at`."""
    columns = {r["name"] for r in store.conn.execute(
        "PRAGMA table_info(label_attachments)"
    )}
    assert {"id", "created_at", "detached_at"} <= columns
    assert "updated_at" not in columns


# --- the 10 -> 11 migration ---------------------------------------------------------


def _v10(path, redefined=True):
    """A schema-10 store, optionally holding a word that has been redefined twice — which
    under the old schema means three rows and one live."""
    conn = sqlite3.connect(path)
    conn.executescript(DDL_V10)
    conn.execute(
        "INSERT INTO plan (guard, name, tier, state, version, schema_version, created_at) "
        "VALUES (1, 'old', 'standard', 'draft', 1, 10, '2026-08-01T00:00:00+00:00')"
    )
    conn.execute(
        "INSERT INTO terms (term, definition, ban_scope, ban_reason, use_instead, "
        "created_at, updated_at) VALUES ('component', 'the old word', 'prose', "
        "'one thing, two spellings', 'task', 'then', 'then')"
    )
    if redefined:
        conn.execute(
            "INSERT INTO terms (term, definition, superseded_at, created_at, updated_at) "
            "VALUES ('stage', 'a first go', 'then', 'first', 'first')"
        )
        conn.execute(
            "INSERT INTO terms (term, definition, superseded_at, created_at, updated_at) "
            "VALUES ('stage', 'a second go', 'later', 'second', 'second')"
        )
    conn.execute(
        "INSERT INTO terms (term, definition, created_at, updated_at) "
        "VALUES ('stage', 'an ordered step of the interview', 'third', 'third')"
    )
    conn.execute(
        "INSERT INTO warnings (warning_key, kind, message, state, created_at, updated_at) "
        "VALUES ('term:requirements:1:component', 'retired_term', 'uses a retired word', "
        "'active', 'then', 'then')"
    )
    conn.commit()
    conn.close()


def test_the_migration_drops_six_columns_and_keeps_the_live_words(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _v10(workspace / "plan.db")
    with Storage(workspace) as store:
        store.migrate(schema.SCHEMA_VERSION)
        columns = [r[1] for r in store.conn.execute("PRAGMA table_info(terms)")]
        assert columns == ["id", "term", "definition", "created_at", "updated_at"]
        words = {
            r["term"]: r["definition"]
            for r in store.query("SELECT term, definition FROM terms")
        }
        assert words == {
            "component": "the old word",
            "stage": "an ordered step of the interview",
        }


def test_a_redefined_word_migrates_to_exactly_one_row(tmp_path):
    """The one place this migration could silently corrupt the table. Under the old schema a
    redefinition wrote a new row and stamped the old, so a word that has ever been redefined
    has several rows and one live. The new `UNIQUE (term)` is total, so keeping them all
    makes the index creation fail — and a copy written to tolerate that would keep an
    arbitrary definition."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _v10(workspace / "plan.db")
    with Storage(workspace) as store:
        store.migrate(schema.SCHEMA_VERSION)
        stage = store.query("SELECT * FROM terms WHERE term = 'stage'")
        assert len(stage) == 1
        assert stage[0]["definition"] == "an ordered step of the interview"
        assert stage[0]["created_at"] == "third", "the live row is the one that survives"


def test_the_migration_settles_the_retired_word_warnings(tmp_path):
    """Once `RETIRED_TERM` leaves `SETTLEABLE_KINDS`, neither `_reconcile` nor the gate's
    settling pass would ever touch such a row again — so it would sit `active` forever, with
    nothing able to produce it and nothing able to settle it. A permanent nag, in the digest
    that exists to de-noise, about a rule that no longer exists."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _v10(workspace / "plan.db")
    with Storage(workspace) as store:
        store.migrate(schema.SCHEMA_VERSION)
        warning = store.query("SELECT * FROM warnings")[0]
        assert warning["state"] == "resolved"
        assert "schema 11" in warning["reason"]


def test_sqlite_sequence_survives_the_migration(tmp_path):
    """Register entry 7: an id is never reused. A table rebuild would have reset the
    high-water mark; the in-place `ALTER` route keeps it, which is one of the reasons the
    rebuild the draft asserted was necessary is not."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _v10(workspace / "plan.db")
    with Storage(workspace) as store:
        before = store.query("SELECT MAX(id) AS n FROM terms")[0]["n"]
        store.migrate(schema.SCHEMA_VERSION)
        new = store.query(
            "INSERT INTO terms (term, definition, created_at, updated_at) "
            "VALUES ('label', 'a glossary word attached to rows', 'now', 'now') "
            "RETURNING id"
        )[0]["id"]
        assert new > before


def test_the_migration_order_is_load_bearing(tmp_path):
    """Two of the three order dependencies were probed and both bite, and they bite inside
    the step that is discarding data. Broken deliberately here rather than trusted."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _v10(workspace / "plan.db")
    conn = sqlite3.connect(workspace / "plan.db")

    with pytest.raises(sqlite3.OperationalError) as exc:
        conn.execute("ALTER TABLE terms DROP COLUMN superseded_at")
    assert "idx_terms_live" in str(exc.value)

    conn.execute("DROP INDEX idx_terms_live")
    conn.execute("ALTER TABLE terms DROP COLUMN superseded_at")
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("DELETE FROM terms WHERE superseded_at IS NOT NULL")
    conn.close()


def test_a_failed_migration_rolls_back_to_the_full_table(tmp_path):
    """DDL is transactional here — probed. The store comes back with all eleven columns and
    every row, which matters more in this step than in any before it."""
    from engine.errors import MigrationFailed

    workspace = tmp_path / "ws"
    workspace.mkdir()
    _v10(workspace / "plan.db")
    with Storage(workspace) as store:
        # The failure is forced on the **last** step, which is what makes this worth
        # asserting: by then the superseded rows are deleted and all six columns are
        # dropped, so a non-transactional DDL path would leave the store reduced and
        # stamped 10. An index of that name already existing is the cheapest way to make
        # `CREATE UNIQUE INDEX idx_terms_word` fail; two live rows for one word cannot be
        # arranged, because the *old* partial index already forbids them.
        store.conn.execute("CREATE INDEX idx_terms_word ON terms (definition)")
        store.conn.commit()
        with pytest.raises(MigrationFailed):
            store.migrate(schema.SCHEMA_VERSION)
        columns = [r[1] for r in store.conn.execute("PRAGMA table_info(terms)")]
        assert len(columns) == 11
        assert store.plan_handle()["schema_version"] == 10
        assert len(store.query("SELECT * FROM terms")) == 4
