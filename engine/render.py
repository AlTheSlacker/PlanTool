"""plan.yaml export/reimport — the schema-churn escape hatch (spec section 4).

Session-C minimal form: a dumb, FK-ordered table dump. No plan.md rendering
yet (session E). Reimport creates a fresh DB on the *current* schema and
inserts every exported row keeping its id, silently-but-reportedly dropping
columns the new schema no longer has — so export -> recreate -> reimport is
the poor man's migration protecting a live plan across schema churn.

Also runnable directly:
    python -m engine.render export <plan.db> <plan.yaml>
    python -m engine.render import <plan.yaml> <new-plan.db>
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

from . import db

EXPORT_FORMAT = 1

# Insert order respects foreign keys (spikes before the claim tables that
# reference it; parents before children).
TABLE_ORDER = (
    "plans", "spikes", "use_cases", "uc_steps", "uc_extensions", "requirements",
    "entities", "crud_grid", "state_machines", "sm_cells", "components", "contracts",
    "contract_deps", "dependencies", "dep_failure_modes", "decisions",
    "open_questions", "conflicts", "findings", "gate_results", "gap_dismissals",
    "pack_manifests",
)


def export_data(conn: db.Connection) -> dict:
    plan = db.get_plan(conn)
    return {
        "plantool_export": EXPORT_FORMAT,
        "plan_name": plan["name"] if plan else None,
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tables": {
            t: [dict(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY id")]
            for t in TABLE_ORDER
        },
    }


def export_yaml(conn: db.Connection, yaml_path: str | Path) -> dict:
    data = export_data(conn)
    Path(yaml_path).write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return {
        "path": str(yaml_path),
        "rows": {t: len(rows) for t, rows in data["tables"].items() if rows},
    }


def import_data(conn: db.Connection, data: dict) -> dict:
    """Insert exported rows into a freshly created (empty) DB. Rows keep their
    ids; columns unknown to the current schema are dropped and reported."""
    if data.get("plantool_export") != EXPORT_FORMAT:
        raise ValueError(
            f"not a plantool export (or unknown format {data.get('plantool_export')!r})")
    counts: dict[str, int] = {}
    dropped: dict[str, list[str]] = {}
    for table in TABLE_ORDER:
        rows = data.get("tables", {}).get(table) or []
        if not rows:
            continue
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for row in rows:
            unknown = sorted(set(row) - cols)
            if unknown:
                dropped[table] = sorted(set(dropped.get(table, [])) | set(unknown))
            db.insert_row(conn, table, {k: v for k, v in row.items() if k in cols})
        counts[table] = len(rows)
    conn.commit()
    result = {"rows": counts}
    if dropped:
        result["dropped_columns"] = dropped
    return result


def import_yaml(yaml_path: str | Path, db_path: str | Path) -> dict:
    db_path = Path(db_path)
    if db_path.exists():
        raise FileExistsError(
            f"{db_path} already exists — reimport only targets a fresh DB; move or delete "
            "the old one deliberately first")
    data = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8"))
    conn = db.create_db(db_path)
    try:
        return import_data(conn, data)
    finally:
        conn.close()


def _cli(argv: list[str]) -> int:
    usage = ("usage: python -m engine.render export <plan.db> <plan.yaml>\n"
             "       python -m engine.render import <plan.yaml> <new-plan.db>")
    if len(argv) != 3 or argv[0] not in ("export", "import"):
        print(usage)
        return 2
    if argv[0] == "export":
        conn = db.connect(argv[1])
        try:
            print(export_yaml(conn, argv[2]))
        finally:
            conn.close()
    else:
        print(import_yaml(argv[1], argv[2]))
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(_cli(sys.argv[1:]))
