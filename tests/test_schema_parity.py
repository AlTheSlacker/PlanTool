"""A migrated store and a fresh one end structurally identical.

The schema comment at the terms table records the rule this enforces: a migration and a
fresh init must create a table from one text, or the stores that were born and the stores
that were migrated drift apart. Every rename in a migration therefore edits `schema.DDL`
*and* emits a step, and this is what holds the two together.

**It compares through the pragmas and never through `sqlite_master.sql`**, and the obvious
implementation is the wrong one. `RENAME COLUMN` substitutes the new name into the stored
`CREATE TABLE` text and keeps the original column padding, so a re-aligned `DDL` — which any
editor produces — gives `'stage             INTEGER'` fresh against `'stage           INTEGER'`
migrated: identical structure, different text. Probed at SQLite 3.49.1 under Python 3.12.10
(`spec/v3/builds/01-vocabulary-and-levels.md` §4.5). A parity check that fails on whitespace
gets disabled within a week, which is how a check becomes theatre.
"""

from __future__ import annotations

import sqlite3

from engine import schema
from engine.storage import Storage
from tests.fixtures.schema_v7 import DDL_V7
from tests.fixtures.schema_v8 import DDL_V8

#: Each retained DDL, with the version it created and the version it migrates to. One entry
#: joins this per schema change; the parametrisation is what stops the check from silently
#: covering one hop forever while the schema moves on. The 7 entry now crosses *two* hops,
#: which is what `Storage._chained_steps` exists for.
RETAINED = {7: DDL_V7, 8: DDL_V8}


def _structure(conn: sqlite3.Connection) -> dict:
    """Tables, columns, indexes and foreign keys, read through the pragmas."""
    conn.row_factory = sqlite3.Row
    out: dict[str, dict] = {}
    tables = sorted(
        r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%'"
        )
    )
    for table in tables:
        out[table] = {
            "columns": [
                (r["name"], r["type"], r["notnull"], r["dflt_value"], r["pk"])
                for r in conn.execute(f"PRAGMA table_info({table})")  # noqa: S608
            ],
            "indexes": sorted(
                (
                    r["name"],
                    r["unique"],
                    r["partial"],
                    tuple(
                        c["name"]
                        for c in conn.execute(f"PRAGMA index_info({r['name']})")  # noqa: S608
                    ),
                )
                for r in conn.execute(f"PRAGMA index_list({table})")  # noqa: S608
            ),
            "foreign_keys": sorted(
                (r["table"], r["from"], r["to"])
                for r in conn.execute(f"PRAGMA foreign_key_list({table})")  # noqa: S608
            ),
        }
    return out


def _built_at(path, ddl: str, version: int) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(ddl)
    try:
        conn.executescript(schema.FTS_DDL)
    except sqlite3.OperationalError:
        pass  # FTS5 unavailable here too; a fresh init degrades the same way
    conn.execute(
        "INSERT INTO plan (guard, name, tier, state, version, schema_version, created_at) "
        "VALUES (1, 'migrated', 'standard', 'draft', 1, ?, '2026-07-31T00:00:00+00:00')",
        (version,),
    )
    conn.commit()
    conn.close()


def test_a_migrated_store_matches_a_fresh_one(tmp_path):
    for version, ddl in RETAINED.items():
        old = tmp_path / f"from{version}"
        old.mkdir()
        _built_at(old / "plan.db", ddl, version)
        with Storage(old) as store:
            store.migrate(schema.SCHEMA_VERSION)
            migrated = _structure(store.conn)

        new = tmp_path / f"fresh{version}"
        new.mkdir()
        with Storage(new) as store:
            store.init_plan("fresh", "standard")
            fresh = _structure(store.conn)

        assert set(migrated) == set(fresh), (
            "tables differ between a store migrated from schema "
            f"{version} and a fresh {schema.SCHEMA_VERSION}: "
            f"{sorted(set(migrated) ^ set(fresh))}"
        )
        for table in sorted(fresh):
            for part in ("columns", "indexes", "foreign_keys"):
                assert migrated[table][part] == fresh[table][part], (
                    f"{table}.{part} differs between a store migrated from schema "
                    f"{version} and a fresh {schema.SCHEMA_VERSION}:\n"
                    f"  migrated: {migrated[table][part]}\n"
                    f"  fresh:    {fresh[table][part]}"
                )


def test_the_retained_ddl_is_the_version_it_claims(tmp_path):
    """A fixture that has quietly been edited to the current shape would make the check
    above pass by comparing schema 9 against schema 9. So each fixture is asserted to still
    hold what the version it names actually had."""
    old = tmp_path / "v7"
    old.mkdir()
    _built_at(old / "plan.db", DDL_V7, 7)
    conn = sqlite3.connect(old / "plan.db")
    tables = {
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    conn.close()
    assert {"subtasks", "packages", "obligations"} <= tables
    assert "behaviours" not in tables

    new = tmp_path / "v8"
    new.mkdir()
    _built_at(new / "plan.db", DDL_V8, 8)
    conn = sqlite3.connect(new / "plan.db")
    rows = {r[1] for r in conn.execute("PRAGMA table_info(plan_rows)")}
    findings = {r[1] for r in conn.execute("PRAGMA table_info(findings)")}
    conn.close()
    # Schema 8 is after change 1 and before change 2: `stage` has landed, the decision
    # context has not, and `findings` still carries the retired spelling.
    assert "stage" in rows
    assert not {"grounds", "alternatives", "supersede_reason"} & rows
    assert "rationale" in findings and "reason" not in findings


def test_the_8_to_9_step_backfills_nothing_and_renames_in_place(tmp_path):
    """The migrated columns arrive NULL. No truth in the old store says what any row's
    argument was, and a manufactured one would read as though somebody had checked — the
    112 gaps that follow are the instrument's first reading, not a defect."""
    old = tmp_path / "v8"
    old.mkdir()
    _built_at(old / "plan.db", DDL_V8, 8)
    conn = sqlite3.connect(old / "plan.db")
    conn.execute(
        "INSERT INTO plan_rows (table_name, ordinal, name, named_for, content, "
        "provenance, state, created_at) VALUES "
        "('entities', 1, 'Order', 'fp', '{}', 'decided', 'active', 'then')"
    )
    conn.execute(
        "INSERT INTO findings (name, description, severity, state, rationale, "
        "resolve_by, created_at) VALUES ('f', 'd', 'high', 'addressed', "
        "'the owner accepted it', 8, 'then')"
    )
    conn.commit()
    conn.close()

    with Storage(old) as store:
        report = store.migrate(9)
        assert report.to_version == 9
        row = store.query("SELECT * FROM plan_rows WHERE ordinal = 1")[0]
        assert row["grounds"] is None
        assert row["alternatives"] is None
        assert row["supersede_reason"] is None
        # The rename carries the value across; it is the same column under its own word.
        assert store.query("SELECT reason FROM findings")[0]["reason"] == (
            "the owner accepted it"
        )


def test_the_migration_refuses_what_it_cannot_migrate_honestly(tmp_path):
    """The two refusals, and that they leave the store where it was.

    A migrated value must be a truth the old store already implied. Collapsing several
    declared groupings into nothing invents the claim that the owner's grouping meant
    nothing, and a store still holding a split would have its second task silently rejected
    by the new unique index — so both are named and refused instead.
    """
    from engine.errors import MigrationFailed

    for label, extra in (
        (
            "two live packages",
            "INSERT INTO packages (name, intent, created_at, updated_at) "
            "VALUES ('the GUI', '', 'now', 'now'), ('the engine', '', 'now', 'now')",
        ),
        (
            "a split",
            "INSERT INTO subtasks (contract_ref, title, state, serve_epoch, created_at, "
            "updated_at) VALUES ('contracts:1', 'a', 'pending', 0, 'now', 'now'), "
            "('contracts:1', 'b', 'pending', 0, 'now', 'now')",
        ),
    ):
        workspace = tmp_path / label.replace(" ", "_")
        workspace.mkdir()
        _built_at(workspace / "plan.db", DDL_V7, 7)
        conn = sqlite3.connect(workspace / "plan.db")
        conn.execute(extra)
        conn.commit()
        conn.close()

        with Storage(workspace) as store:
            try:
                store.migrate(8)
            except MigrationFailed as exc:
                assert "contracts:1" in str(exc) or "packages:1" in str(exc), exc
            else:
                raise AssertionError(f"{label} was migrated rather than refused")
            assert store.plan_handle()["schema_version"] == 7
            assert store.query(
                "SELECT name FROM sqlite_master WHERE name = 'subtasks'"
            ), "the pre-migration snapshot was not restored"
