"""Thin sqlite3 wrapper. One DB file per plan, living in the planning
workspace so the plan travels with the project folder (spec section 3).

Every connection opens with journal_mode=WAL and a busy_timeout so two
concurrent sessions on one workspace degrade gracefully instead of
corrupting or hard-failing.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
BUSY_TIMEOUT_MS = 5000

# The one sqlite3 seam (spec: backend-neutral storage is a later shape; keep
# this thin). Other engine modules take these from here, never from sqlite3.
Connection = sqlite3.Connection
Row = sqlite3.Row
IntegrityError = sqlite3.IntegrityError

# Tables whose rows assert planning facts (carry provenance).
CLAIM_TABLES = (
    "use_cases", "uc_steps", "uc_extensions", "requirements", "entities",
    "crud_grid", "state_machines", "sm_cells", "components", "contracts",
    "contract_deps", "dependencies", "dep_failure_modes", "decisions",
)
# Process bookkeeping (no provenance).
BOOKKEEPING_TABLES = ("open_questions", "conflicts", "spikes", "findings", "gate_results")
COUNTED_TABLES = CLAIM_TABLES + BOOKKEEPING_TABLES

# A claim row is active until superseded or retired; everything that reasons
# about the plan (gates, sweeps, next_gap, duplicate checks) sees active rows
# only. Superseded/retired rows stay as the audit trail.
ACTIVE = "superseded_by IS NULL AND retired = 0"


def active(alias: str) -> str:
    """The ACTIVE predicate qualified for a table alias in a join."""
    return f"{alias}.superseded_by IS NULL AND {alias}.retired = 0"


def is_active(row: sqlite3.Row | dict) -> bool:
    return row["superseded_by"] is None and not row["retired"]


def connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_db(db_path: str | Path) -> sqlite3.Connection:
    """Create a fresh, empty database on the current schema (no plan row) —
    the reimport target of the plan.yaml escape hatch."""
    conn = connect(db_path)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.execute("PRAGMA foreign_keys = ON")  # executescript may run outside our pragma
    return conn


def create_plan_db(db_path: str | Path, name: str) -> sqlite3.Connection:
    """Create a fresh plan database and its single plan row."""
    conn = create_db(db_path)
    conn.execute("INSERT INTO plans (name) VALUES (?)", (name,))
    conn.commit()
    return conn


def get_plan(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM plans ORDER BY id LIMIT 1").fetchone()


def frozen_error(conn: sqlite3.Connection) -> str | None:
    """A frozen plan is read-only — every write surface checks this first.
    Freezing that doesn't freeze would make plans.state decorative."""
    plan = get_plan(conn)
    if plan is not None and plan["state"] == "frozen":
        return (
            f"Rule: this plan is frozen (version {plan['version']}) — planning is complete "
            "and the record is read-only. Reads still work: plan_status, get_rows, "
            "get_plan_pack, get_stage_prompt, run_gate, and export_plan."
        )
    return None


def insert_row(conn: sqlite3.Connection, table: str, values: dict) -> int:
    """Insert one row; caller supplies validated column->value mapping."""
    cols = ", ".join(values)
    marks = ", ".join("?" * len(values))
    cur = conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(values.values()))
    return cur.lastrowid


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Active-row counts for claim tables (superseded/retired rows are audit
    trail, not plan size); raw counts for bookkeeping."""
    return {
        t: conn.execute(
            f"SELECT count(*) FROM {t} WHERE {ACTIVE}" if t in CLAIM_TABLES
            else f"SELECT count(*) FROM {t}").fetchone()[0]
        for t in COUNTED_TABLES
    }
