"""The catalogue's invariants, asserted **at the store** and not through the service.

That distinction is the whole reason this file exists, and it is not fussiness. Driven
through `CatalogueService`, the central one of these tests passes on the *wrong* index: a
second entry with an identical name ranks first in `_rank`, so `NearMatchesUnadjudicated`
refuses the call before the index is ever reached. The test would be green, the refusal would
be the wrong one, and the defect the `COALESCE` index exists to prevent would ship — a check
running green while measuring something narrower than its name, which is the failure this
project has now recorded three times.

**And the parity check cannot cover it either**, for a better and more general reason than
the one first given. `PRAGMA index_list` does report the naive and the `COALESCE` forms
identically, but `index_info` distinguishes them — an expression column reports `cid = -2`
and a NULL name — so it is not true that the pragmas cannot tell them apart. Parity is blind
because **both sides are built from the same DDL text**: it catches a migration that *omits*
the block and can never catch an index that is wrong-but-consistent, because it would compare
that index happily with itself.

So the assertion has to be the behaviour, and these are the assertions that would catch a
builder writing the obvious thing.
"""

from __future__ import annotations

import sqlite3

import pytest

from engine import schema
from engine.storage import Storage
from tests.fixtures.schema_v9 import DDL_V9


@pytest.fixture
def raw(tmp_path):
    """A store at schema 10, written to directly. No service in the way."""
    with Storage(tmp_path) as store:
        store.init_plan("catalogue", "standard")
        store.conn.execute(
            "INSERT INTO tasks (contract_ref, title, state, created_at, updated_at) "
            "VALUES ('contracts:1', 'a task', 'pending', 'then', 'then')"
        )
        store.conn.execute(
            "INSERT INTO tasks (contract_ref, title, state, created_at, updated_at) "
            "VALUES ('contracts:2', 'another', 'pending', 'then', 'then')"
        )
        store.conn.commit()
        yield store.conn


def insert(conn, **values):
    values.setdefault("created_at", "then")
    values.setdefault("updated_at", "then")
    cols = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    conn.execute(
        f"INSERT INTO catalogue ({cols}) VALUES ({marks})",  # noqa: S608
        tuple(values.values()),
    )
    conn.commit()


def an_object(conn, name, **over):
    insert(conn, **{"name": name, "kind": "object", "visibility": "public",
                    "purpose": "p", "component_ref": "components:1", **over})


def a_function(conn, name, **over):
    insert(conn, **{"name": name, "kind": "function", "visibility": "private",
                    "purpose": "p", "task_id": 1, **over})


class TestTheLiveNameIndex:
    """§3.3. Every collision this catalogue would catch in a codebase the size of v2's is a
    collision between two entries whose `container_id` is NULL — measured: the identity
    collides eleven times over v2's engine and all eleven are module-level objects. So the
    NULL case is not a corner, it is the whole of it."""

    def test_two_live_module_level_entries_cannot_share_a_name(self, raw):
        an_object(raw, "PlanUnreadable")
        with pytest.raises(sqlite3.IntegrityError):
            an_object(raw, "PlanUnreadable")

    def test_the_naive_index_would_have_accepted_it(self, tmp_path):
        """The guard on the guard: break it and watch it fail, or you do not know it works.

        This builds the index the specification calls the single most likely build-time
        defect in the change — `(name, container_id)` without the `COALESCE` — and shows it
        admitting the exact collision. Without this, a builder who writes the obvious form
        gets a green suite and an index that catches nothing.
        """
        conn = sqlite3.connect(tmp_path / "naive.db")
        conn.executescript(
            "CREATE TABLE catalogue (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "name TEXT NOT NULL, container_id INTEGER, retired_at TEXT);"
            "CREATE UNIQUE INDEX ix ON catalogue (name, container_id) "
            "WHERE retired_at IS NULL;"
        )
        conn.execute("INSERT INTO catalogue (name) VALUES ('PlanUnreadable')")
        conn.execute("INSERT INTO catalogue (name) VALUES ('PlanUnreadable')")
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM catalogue").fetchone()[0] == 2, (
            "SQLite has started comparing NULLs as equal in a unique index; the COALESCE "
            "form is then unnecessary rather than load-bearing, and §3.3 needs re-reading"
        )
        conn.close()

    def test_the_same_name_in_two_different_containers_is_accepted(self, raw):
        """`_hydrate` is a legitimate method name on five service classes in this engine,
        and that is the case the whole table's identity is designed around."""
        an_object(raw, "RowService")
        an_object(raw, "GapService")
        rows = raw.execute("SELECT id FROM catalogue ORDER BY id").fetchall()
        a_function(raw, "_hydrate", container_id=rows[0][0])
        a_function(raw, "_hydrate", container_id=rows[1][0], task_id=2)
        assert raw.execute(
            "SELECT COUNT(*) FROM catalogue WHERE name = '_hydrate'"
        ).fetchone()[0] == 2

    def test_a_retired_name_is_free_again_and_the_new_entry_is_a_new_row(self, raw):
        an_object(raw, "Widget")
        raw.execute("UPDATE catalogue SET retired_at = 'later' WHERE name = 'Widget'")
        raw.commit()
        an_object(raw, "Widget")
        ids = [r[0] for r in raw.execute(
            "SELECT id FROM catalogue WHERE name = 'Widget' ORDER BY id"
        )]
        assert len(ids) == 2 and ids[0] != ids[1], (
            "retirement is never undone: the reintroduction is a second row, because "
            "nulling the retirement would erase the history at the moment it gets "
            "interesting"
        )


class TestTheTaskEntryPointIndex:
    def test_a_task_cannot_hold_two_live_public_function_entries(self, raw):
        a_function(raw, "compose", visibility="public")
        with pytest.raises(sqlite3.IntegrityError):
            a_function(raw, "assemble", visibility="public")

    def test_private_entries_and_objects_are_unaffected(self, raw):
        a_function(raw, "compose", visibility="public")
        a_function(raw, "_gather")
        a_function(raw, "_sort")
        an_object(raw, "Composer")
        an_object(raw, "Sorter")
        assert raw.execute("SELECT COUNT(*) FROM catalogue").fetchone()[0] == 5

    def test_a_retired_public_entry_frees_the_task(self, raw):
        a_function(raw, "compose", visibility="public")
        raw.execute("UPDATE catalogue SET retired_at = 'later' WHERE name = 'compose'")
        raw.commit()
        a_function(raw, "assemble", visibility="public")


class TestTheOwnershipChecks:
    """A value that appears in an index predicate must be constrained, because a typo there
    does not fail — it removes the row from the invariant. `idx_catalogue_task_entry` is
    predicated on `kind` and `visibility`; write `'Public'` and the task quietly acquires a
    second entry point with nothing red."""

    def test_two_owners_is_refused(self, raw):
        with pytest.raises(sqlite3.IntegrityError):
            insert(raw, name="X", kind="function", visibility="public", purpose="p",
                   task_id=1, component_ref="components:1")

    def test_no_owner_is_refused(self, raw):
        with pytest.raises(sqlite3.IntegrityError):
            insert(raw, name="X", kind="function", visibility="public", purpose="p")

    def test_a_function_owned_by_a_component_is_refused(self, raw):
        """The draft's `CHECK ((task_id IS NULL) != (component_ref IS NULL))` alone lets
        this through, and such a row escapes `idx_catalogue_task_entry` entirely — the same
        NULL escape as §3.3, through the same door, one index later."""
        with pytest.raises(sqlite3.IntegrityError):
            insert(raw, name="X", kind="function", visibility="public", purpose="p",
                   component_ref="components:1")

    def test_an_object_owned_by_a_task_is_refused(self, raw):
        with pytest.raises(sqlite3.IntegrityError):
            insert(raw, name="X", kind="object", visibility="public", purpose="p",
                   task_id=1)

    @pytest.mark.parametrize("column,bad", [
        ("kind", "Function"), ("kind", "class"),
        ("visibility", "Public"), ("visibility", "internal"),
    ])
    def test_a_value_outside_the_set_is_refused(self, raw, column, bad):
        values = dict(name="X", kind="function", visibility="public", purpose="p",
                      task_id=1)
        values[column] = bad
        if column == "kind":
            values = dict(values, task_id=None, component_ref="components:1")
        with pytest.raises(sqlite3.IntegrityError):
            insert(raw, **values)

    def test_a_bad_relationship_is_refused(self, raw):
        an_object(raw, "Widget")
        with pytest.raises(sqlite3.IntegrityError):
            raw.execute(
                "INSERT INTO catalogue_comparisons (proposed, matched_id, relationship, "
                "reason, created_at) VALUES ('X', 1, 'Same', 'r', 'then')"
            )

    @pytest.mark.parametrize("relationship", [
        "same", "contains", "contained_by", "partially_overlaps", "unrelated",
    ])
    def test_each_of_the_five_relationships_is_accepted(self, raw, relationship):
        an_object(raw, "Widget")
        raw.execute(
            "INSERT INTO catalogue_comparisons (proposed, matched_id, relationship, "
            "reason, created_at) VALUES ('X', 1, ?, 'r', 'then')",
            (relationship,),
        )
        raw.commit()


class TestTheDDLAndTheMigration:
    def test_the_block_is_five_statements(self):
        """Measured rather than reasoned. `schema.statements` splits on semicolons and the
        split is only safe because comments are stripped first — comment lines in this block
        contain them. A builder who drops one statement gets a failure here rather than a
        quietly smaller schema."""
        assert len(schema.statements(schema.CATALOGUE_DDL)) == 5

    def test_the_migration_writes_no_catalogue_row(self, tmp_path):
        """3A.2 behaviour 2 is a claim a builder could quietly break with a helpful
        backfill, and nothing else would fail. There is no truth in the old store from which
        a set of function names could be derived — the one place such a truth exists is the
        tree, and deriving the catalogue from a tree is the rejected design."""
        old = tmp_path / "v9"
        old.mkdir()
        conn = sqlite3.connect(old / "plan.db")
        conn.executescript(DDL_V9)
        conn.execute(
            "INSERT INTO plan (guard, name, tier, state, version, schema_version, "
            "created_at) VALUES (1, 'old', 'standard', 'draft', 1, 9, 'then')"
        )
        conn.commit()
        conn.close()
        with Storage(old) as store:
            report = store.migrate(10)
            assert report.to_version == 10
            assert store.query("SELECT * FROM catalogue") == []
            assert store.query("SELECT * FROM catalogue_comparisons") == []

    def test_the_catalogue_stays_out_of_the_snapshot_table_set(self, tmp_path):
        """3A.2 behaviour 3 reverses the instinct, and the reason is mechanical: `tasks` is
        not in the snapshot set — the whole execution layer sits outside it — so a
        `catalogue` inside it would be rewound while the `tasks` rows its `task_id`
        references were not, leaving entries and tasks describing two different plans with
        nothing complaining. Both stay out, together."""
        import inspect

        from engine.storage import Storage as S

        source = inspect.getsource(S.snapshot_version)
        assert "catalogue" not in source, (
            "the catalogue joined the snapshot set; `tasks` is not in it, so its task_id "
            "references would survive a rewind that removed the tasks"
        )
        with Storage(tmp_path) as store:
            store.init_plan("p", "standard")
            snapshot = store.snapshot_version("check")
            payload = store.query(
                "SELECT payload FROM plan_versions WHERE id = ?", (snapshot,)
            )[0]["payload"]
            import json

            assert len(json.loads(payload)) == 9
            assert "catalogue" not in json.loads(payload)


class TestTheVocabularyParserSeesThisChange:
    """The guard on the guard. `_columns()` parses `engine/schema.py` with a regex, so if
    the new tables are declared in a shape it does not match, every vocabulary check passes
    while seeing nothing of this change — and `test_the_check_can_actually_fail`'s `> 100`
    floor is far too loose to notice."""

    def test_the_parser_finds_both_new_tables(self):
        from tests.test_schema_vocabulary import _columns

        found = {table for table, _, _ in _columns()}
        assert {"catalogue", "catalogue_comparisons"} <= found

    def test_it_finds_the_two_justification_columns_and_no_third(self):
        from tests.test_schema_vocabulary import JUSTIFICATION_ROLES, _columns

        ours = {
            f"{table}.{column}"
            for table, column, _ in _columns()
            if table.startswith("catalogue")
            and (column in ("reason", "grounds", "alternatives")
                 or column.endswith("_reason"))
        }
        assert ours == {"catalogue.retire_reason", "catalogue_comparisons.reason"}
        assert ours <= set(JUSTIFICATION_ROLES)

    def test_the_retained_v9_fixture_is_invisible_to_the_parser(self):
        """§11.4's cross-change hole. If a retained DDL lived in `engine/schema.py`, every
        one of these five vocabulary checks would read it as live schema — declaring columns
        that no longer exist and, in change 1's case, resurrecting the very names that change
        renamed. This is the assertion that proves it lives outside."""
        from tests.test_schema_vocabulary import SCHEMA

        source = SCHEMA.read_text(encoding="utf-8")
        assert "DDL_V9" not in source and "DDL_V8" not in source
        assert source.count("CREATE TABLE IF NOT EXISTS plan_rows") == 1
