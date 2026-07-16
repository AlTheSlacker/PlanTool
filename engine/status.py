"""plan_status digest + targeted row reads (Session D, dogfood finding F2:
counts-only status forced a 4k+-token full-DB dump on cold resume).

digest() is everything a cold session needs to know *about* the plan in well
under ~1k tokens: stage, per-stage gate verdicts with the latest holes, active
row counts, the open conflict/question queue, and a small working set of the
most recent rows. Row *content* is then pulled on demand with get_rows —
never by dumping the DB.
"""
from __future__ import annotations

import json

from . import db, gaps

READABLE_TABLES = db.COUNTED_TABLES + ("plans", "gap_dismissals")
MAX_ROWS = 200
DEFAULT_ROWS = 50
RECENT_ROWS = 10
MAX_HOLES_IN_DIGEST = 10

# One-line label per claim table for the digest's working set.
LABELS = {
    "use_cases": "title",
    "uc_steps": "substr(text, 1, 60)",
    "uc_extensions": "substr(description, 1, 60)",
    "requirements": "coalesce(system_response, feature)",
    "entities": "name",
    "crud_grid": "op",
    "state_machines": "'state machine'",
    "sm_cells": "state || ' x ' || event",
    "components": "name",
    "contracts": "name",
    "contract_deps": "'edge -> contract ' || provider_contract_id",
    "dependencies": "name",
    "dep_failure_modes": "mode",
    "decisions": "substr(text, 1, 80)",
}


def _fmt(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def _latest_gate_runs(conn) -> list[dict]:
    runs = []
    for stage in range(1, 9):
        r = conn.execute(
            "SELECT stage, passed, holes, run_at FROM gate_results "
            "WHERE stage = ? ORDER BY id DESC LIMIT 1", (stage,)).fetchone()
        if r is None:
            continue
        run = {"stage": r["stage"], "passed": bool(r["passed"]), "run_at": r["run_at"]}
        holes = json.loads(r["holes"] or "[]")
        if holes:
            run["holes"] = holes[:MAX_HOLES_IN_DIGEST]
            if len(holes) > MAX_HOLES_IN_DIGEST:
                run["holes_truncated"] = len(holes) - MAX_HOLES_IN_DIGEST
        runs.append(run)
    return runs


def _recent_rows(conn) -> list[dict]:
    recent = []
    for table, label in LABELS.items():
        for r in conn.execute(
                f"SELECT id, {label} AS label, created_at FROM {table} "
                f"WHERE {db.ACTIVE} ORDER BY id DESC LIMIT {RECENT_ROWS}"):
            recent.append({"ref": f"{table}:{r['id']}", "label": r["label"],
                           "created_at": r["created_at"]})
    recent.sort(key=lambda r: (r["created_at"], r["ref"]), reverse=True)
    return recent[:RECENT_ROWS]


def digest(conn) -> dict:
    plan = db.get_plan(conn)
    gap_result = gaps.next_gap(conn)
    open_gaps = gap_result.get("open_gap_total", 0)
    return {
        "plan": dict(plan),
        "counts": {t: n for t, n in db.table_counts(conn).items() if n},
        "gates": _latest_gate_runs(conn),
        "open_conflicts": [
            {"id": r["id"], "description": r["description"]} for r in conn.execute(
                "SELECT id, description FROM conflicts WHERE state = 'open' ORDER BY id")],
        "open_questions": [
            {"id": r["id"], "text": r["text"], "owner": r["owner"]} for r in conn.execute(
                "SELECT id, text, owner FROM open_questions WHERE state = 'open' ORDER BY id")],
        "pending_spikes": [
            {"id": r["id"], "question": r["question"]} for r in conn.execute(
                "SELECT id, question FROM spikes WHERE verdict IS NULL ORDER BY id")],
        "open_gap_total": open_gaps,
        "recent_rows": _recent_rows(conn),
        "reading": ("Row content is fetched on demand: get_rows(table, ids=[...]) or "
                    "get_rows(table, filters={col: value}) — never reconstruct the plan by "
                    "dumping the DB."),
    }


def get_rows(conn, table: str, ids: list[int] | None = None,
             filters: dict | None = None, include_inactive: bool = False,
             limit: int = DEFAULT_ROWS) -> dict:
    """Targeted row reads. Equality filters only — this is a lookup tool, not
    a query language; anything richer belongs in a purpose-built view."""
    if table not in READABLE_TABLES:
        return {"error": (
            f"Rule: table is one of {sorted(READABLE_TABLES)}. "
            f"Offending input: table={_fmt(table)}.")}
    columns = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    where, params = [], []
    if ids is not None:
        if (not isinstance(ids, list) or not ids or any(
                isinstance(i, bool) or not isinstance(i, int) for i in ids)):
            return {"error": (
                f"Rule: ids is a non-empty array of integers. Offending input: {_fmt(ids)}.")}
        where.append(f"id IN ({', '.join('?' * len(ids))})")
        params += ids
    if filters:
        if not isinstance(filters, dict):
            return {"error": (
                f"Rule: filters is an object of column: value equality matches. "
                f"Offending input: {_fmt(filters)}.")}
        unknown = sorted(set(filters) - columns)
        if unknown:
            return {"error": (
                f"Rule: unknown filter column(s) {unknown} — {table} has "
                f"{sorted(columns)}. Offending input: {_fmt(filters)}.")}
        for col, value in filters.items():
            if value is None:
                where.append(f"{col} IS NULL")
            else:
                where.append(f"{col} = ?")
                params.append(value)
    if table in db.CLAIM_TABLES and not include_inactive:
        where.append(db.ACTIVE)
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        limit = DEFAULT_ROWS
    limit = min(limit, MAX_ROWS)
    sql = f"SELECT * FROM {table}"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY id LIMIT {limit + 1}"
    rows = [dict(r) for r in conn.execute(sql, params)]
    truncated = len(rows) > limit
    out = {"table": table, "rows": rows[:limit], "count": min(len(rows), limit)}
    if truncated:
        out["truncated"] = True
        out["note"] = f"More rows match — narrow with ids/filters or raise limit (max {MAX_ROWS})."
    return out
