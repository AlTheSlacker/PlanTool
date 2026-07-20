import sqlite3

import pytest

from engine import db


def test_wal_and_busy_timeout(conn):
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == db.BUSY_TIMEOUT_MS


def test_plan_row_defaults(conn):
    plan = db.get_plan(conn)
    assert plan["name"] == "test-plan"
    assert plan["tier"] == "standard"
    assert plan["current_stage"] == 1
    assert plan["version"] == 1
    assert plan["state"] == "open"


def test_all_spec_tables_exist(conn):
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}
    expected = set(db.COUNTED_TABLES) | {"plans", "pack_manifests"}
    assert expected <= tables


def test_foreign_keys_enforced(conn):
    plan = db.get_plan(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO uc_steps (plan_id, plan_version_added, use_case_id, step_no, text, provenance)"
            " VALUES (?, 1, 999, 1, 'orphan', 'decided')", (plan["id"],))


def test_schema_rejects_assumed_without_kind(conn):
    plan = db.get_plan(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO entities (plan_id, plan_version_added, name, has_lifecycle, lifecycle_reason, provenance)"
            " VALUES (?, 1, 'X', 0, 'r', 'assumed')", (plan["id"],))


def test_schema_rejects_verified_without_spike(conn):
    plan = db.get_plan(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO requirements (plan_id, plan_version_added, ears_type, system_response, provenance)"
            " VALUES (?, 1, 'ubiquitous', 'x', 'verified')", (plan["id"],))
