"""Export and rendering (spec sections 4, 5, 8).

plan.yaml: a dumb, FK-ordered table dump — the schema-churn escape hatch.
Reimport creates a fresh DB on the *current* schema and inserts every
exported row keeping its id, silently-but-reportedly dropping columns the
new schema no longer has — so export -> recreate -> reimport is the poor
man's migration protecting a live plan across schema churn.
roundtrip_check() proves losslessness in memory (the stage-8 gate calls it).

plan.md / get_plan_pack: the same rows rendered as readable markdown —
scoped to a stage, a component, or the full plan. Every rendered row carries
its "table:id" ref so a red-team session can file findings with links.
Active rows only: superseded/retired rows are audit trail, not plan.

Also runnable directly:
    python -m engine.render export <plan.db> <plan.yaml>
    python -m engine.render import <plan.yaml> <new-plan.db>
"""
from __future__ import annotations

import json
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


def roundtrip_check(conn: db.Connection) -> list[str]:
    """Export -> fresh in-memory DB -> reimport -> re-export, compared table
    by table. Returns the problems (empty = lossless). The stage-8 gate runs
    this so a freeze never rests on an escape hatch that silently drops data."""
    data = export_data(conn)
    tmp = db.create_db(":memory:")
    try:
        result = import_data(tmp, data)
        problems = [
            f"reimport dropped column(s) {cols} from {table}"
            for table, cols in sorted(result.get("dropped_columns", {}).items())]
        back = export_data(tmp)
        problems += [
            f"table '{t}' did not survive export -> reimport intact"
            for t in TABLE_ORDER if data["tables"][t] != back["tables"][t]]
        return problems
    except Exception as exc:  # a crash is itself the finding, not a test failure
        return [f"reimport failed outright: {exc!r}"]
    finally:
        tmp.close()


# --- plan.md / plan packs ------------------------------------------------------

PACK_SCOPES = "\"full\", \"stage:N\" (N = 1-7), or \"component:<id or name>\""


def _jload(value, default):
    return json.loads(value) if value else default


def _active(conn, table: str, where: str = "1=1", params: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(
        f"SELECT * FROM {table} WHERE {db.ACTIVE} AND {where} ORDER BY id", params)]


def _tag(table: str, row: dict) -> str:
    """The row's ref plus its epistemic status — every rendered fact shows both."""
    prov = row["provenance"]
    if prov == "assumed":
        prov += f"/{row['assumption_kind']}"
    if prov == "verified":
        prov += f" by spikes:{row['spike_id']}"
    return f"`{table}:{row['id']}` · {prov}"


def _links_suffix(row: dict) -> str:
    links = _jload(row.get("links"), [])
    return f" · links: {', '.join(links)}" if links else ""


def ears_sentence(row: dict) -> str:
    """The canonical EARS sentence, assembled from the typed slots — the slots
    are the record; this prose is derived, never parsed back."""
    sr = row["system_response"]
    return {
        "ubiquitous": f"The system shall {sr}.",
        "event": f"WHEN {row['trigger_text']}, the system shall {sr}.",
        "state": f"WHILE {row['precondition']}, the system shall {sr}.",
        "unwanted": f"IF {row['trigger_text']}, THEN the system shall {sr}.",
        "optional": f"WHERE {row['feature']}, the system shall {sr}.",
    }[row["ears_type"]]


def _section(title: str, lines: list[str]) -> list[str]:
    return [f"## {title}", ""] + lines + [""] if lines else []


def _stage1_lines(conn) -> list[str]:
    from .gates import GOAL_WHERE, NON_GOAL_WHERE, STACK_WHERE  # lazy: gates imports render
    lines = []
    for heading, where in (("Goals", GOAL_WHERE), ("Non-goals", NON_GOAL_WHERE),
                           ("Target stack", STACK_WHERE)):
        rows = _active(conn, "decisions", where)
        if rows:
            lines.append(f"**{heading}**")
            for r in rows:
                line = f"- {r['text']} ({_tag('decisions', r)})"
                if r["rationale"]:
                    line += f" — {r['rationale']}"
                lines.append(line)
            lines.append("")
    return lines[:-1] if lines else []


def _stage2_lines(conn) -> list[str]:
    lines = []
    for uc in _active(conn, "use_cases"):
        lines.append(f"### {uc['title']} — actor: {uc['actor']} ({_tag('use_cases', uc)})")
        for s in _active(conn, "uc_steps", "use_case_id = ?", (uc["id"],)):
            lines.append(f"{s['step_no']}. {s['text']} (`uc_steps:{s['id']}`)")
            if s["no_extension_reason"]:
                lines.append(f"   - no extensions: {s['no_extension_reason']}")
            for e in _active(conn, "uc_extensions", "step_id = ?", (s["id"],)):
                handling = e["handling"] if e["in_scope"] else "OUT OF SCOPE"
                lines.append(f"   - if {e['description']} -> {handling} "
                             f"(`uc_extensions:{e['id']}`)")
        lines.append("")
    return lines[:-1] if lines else []


def _stage3_lines(conn) -> list[str]:
    lines = []
    for r in _active(conn, "requirements"):
        lines.append(f"- {ears_sentence(r)} ({_tag('requirements', r)}{_links_suffix(r)})")
        if r["is_nfr"]:
            lines.append(f"  - Planguage — scale: {r['planguage_scale']}; "
                         f"meter: {r['planguage_meter']}; target: {r['planguage_target']}")
    return lines


def _stage4_lines(conn) -> list[str]:
    lines = []
    for e in _active(conn, "entities"):
        lifecycle = ("has lifecycle" if e["has_lifecycle"]
                     else f"no lifecycle — {e['lifecycle_reason']}")
        lines.append(f"### {e['name']} ({_tag('entities', e)}) — {lifecycle}")
        if e["description"]:
            lines.append(e["description"])
        cells = _active(conn, "crud_grid", "entity_id = ?", (e["id"],))
        if cells:
            lines += ["", "| op | responsible | ref |", "|---|---|---|"]
            for c in sorted(cells, key=lambda c: "CRUD".index(c["op"])):
                who = f"n/a — {c['na_reason']}" if c["na"] else c["actor"]
                if c["children_on_delete"]:
                    who += f" (children: {c['children_on_delete']})"
                lines.append(f"| {c['op']} | {who} | `crud_grid:{c['id']}` |")
        for m in _active(conn, "state_machines", "entity_id = ?", (e["id"],)):
            lines += ["", f"State machine (`state_machines:{m['id']}`) — states: "
                          f"{', '.join(_jload(m['states'], []))}; events: "
                          f"{', '.join(_jload(m['events'], []))}",
                      "", "| state | event | -> | ref |", "|---|---|---|---|"]
            for c in _active(conn, "sm_cells", "machine_id = ?", (m["id"],)):
                to = f"impossible — {c['impossible_reason']}" if c["impossible"] \
                    else c["transition_to"]
                lines.append(f"| {c['state']} | {c['event']} | {to} | `sm_cells:{c['id']}` |")
        lines.append("")
    return lines[:-1] if lines else []


def _stage5_lines(conn) -> list[str]:
    lines = []
    for d in _active(conn, "dependencies"):
        lines.append(f"### {d['name']} ({d['kind']}) ({_tag('dependencies', d)})")
        if d["notes"]:
            lines.append(d["notes"])
        modes = _active(conn, "dep_failure_modes", "dep_id = ?", (d["id"],))
        if modes:
            lines += ["", "| failure mode | handling | ref |", "|---|---|---|"]
            lines += [f"| {m['mode']} | {m['handling']} | `dep_failure_modes:{m['id']}` |"
                      for m in modes]
        lines.append("")
    return lines[:-1] if lines else []


def _contract_lines(conn, k: dict) -> list[str]:
    params = ", ".join(
        f"{p['name']}: {p['type_expr']}" + ("" if p.get("required", True) else "?")
        for p in _jload(k["params"], []))
    lines = [f"- **{k['name']}** ({k['kind']}): ({params}) -> {k['returns']} "
             f"({_tag('contracts', k)}{_links_suffix(k)})"
             + (" · external" if k["is_external"] else "")]
    if k["cannot_fail"]:
        lines.append(f"  - cannot fail: {k['cannot_fail_reason']}")
    else:
        lines += [f"  - error {e['name']}: {e['semantics']}"
                  for e in _jload(k["errors"], [])]
    consumers = [dict(r) for r in conn.execute(f"""
        SELECT d.id, d.consumer_contract_id, d.consumer_component_id FROM contract_deps d
        WHERE d.provider_contract_id = ? AND {db.active('d')} ORDER BY d.id""", (k["id"],))]
    if consumers:
        lines.append("  - consumed by: " + ", ".join(
            (f"contracts:{c['consumer_contract_id']}" if c["consumer_contract_id"]
             else f"components:{c['consumer_component_id']}") for c in consumers))
    return lines


def _stage6_lines(conn, component_id: int | None = None) -> list[str]:
    where, params = ("id = ?", (component_id,)) if component_id else ("1=1", ())
    lines = []
    for c in _active(conn, "components", where, params):
        lines.append(f"### {c['name']} ({_tag('components', c)})")
        lines.append(f"Responsibility: {c['responsibility']}")
        for k in _active(conn, "contracts", "component_id = ?", (c["id"],)):
            lines += _contract_lines(conn, k)
        lines.append("")
    return lines[:-1] if lines else []


def _decision_lines(conn, like: str | None = None) -> list[str]:
    where, params = ("links LIKE ?", (like,)) if like else ("1=1", ())
    lines = []
    for d in _active(conn, "decisions", where, params):
        mark = " **[significant]**" if d["significant"] else ""
        lines.append(f"- {d['text']}{mark} ({_tag('decisions', d)}{_links_suffix(d)})")
        if d["rationale"]:
            lines.append(f"  - rationale: {d['rationale']}")
        lines += [f"  - rejected: {a['alternative']} — {a['rejected_because']}"
                  for a in _jload(d["alternatives"], [])]
        challenge = _jload(d["challenge"], None)
        if challenge:
            lines.append(f"  - challenged ({challenge['outcome']}): {challenge['text']}")
    return lines


def _spike_lines(conn) -> list[str]:
    lines = []
    for s in conn.execute("SELECT * FROM spikes ORDER BY id"):
        lines.append(f"- {s['question']} (`spikes:{s['id']}`) — "
                     f"verdict: {s['verdict'] or 'PENDING'}")
        if s["hypothesis"]:
            lines.append(f"  - hypothesis: {s['hypothesis']}; method: {s['method']}; "
                         f"budget: {s['budget']}")
        if s["evidence_summary"]:
            lines.append(f"  - evidence: {s['evidence_summary']}")
    return lines


def _question_lines(conn) -> list[str]:
    return [f"- [{q['state']}] {q['text']} (`open_questions:{q['id']}`)"
            + (f" — {q['resolution']}" if q["resolution"] else "")
            for q in conn.execute("SELECT * FROM open_questions ORDER BY id")]


def _conflict_lines(conn) -> list[str]:
    return [f"- [{c['state']}] {c['description']} (`conflicts:{c['id']}`, "
            f"{c['source']}-filed, refs: {', '.join(_jload(c['refs'], []))})"
            + (f" — {c['resolution']}" if c["resolution"] else "")
            for c in conn.execute("SELECT * FROM conflicts ORDER BY id")]


def _finding_lines(conn) -> list[str]:
    lines = []
    for f in conn.execute("SELECT * FROM findings ORDER BY id"):
        disp = (f"{f['disposition']} — {f['disposition_rationale']}"
                if f["disposition"] else "UNDISPOSITIONED")
        lines.append(f"- [{f['source']}] {f['text']} (`findings:{f['id']}`"
                     f"{_links_suffix(dict(f))}) — {disp}")
    return lines


STAGE_SECTIONS = {
    1: ("Stage 1 — Context & goals", _stage1_lines),
    2: ("Stage 2 — Use cases", _stage2_lines),
    3: ("Stage 3 — Requirements", _stage3_lines),
    4: ("Stage 4 — Domain model", _stage4_lines),
    5: ("Stage 5 — External dependencies & failure modes", _stage5_lines),
    6: ("Stage 6 — Architecture", _stage6_lines),
    7: ("Stage 7 — Adversarial findings", _finding_lines),
}


def _header_lines(conn) -> list[str]:
    # No render timestamp: plan.md is committed alongside the project, and a
    # timestamp would make every regeneration a diff. plan.yaml carries exported_at.
    plan = db.get_plan(conn)
    return [f"# Plan: {plan['name']}", "",
            f"State: {plan['state']} · version {plan['version']} · "
            f"stage {plan['current_stage']}", ""]


def render_markdown(conn: db.Connection) -> str:
    """The full plan as one readable document — plan.md and the red team's
    get_plan_pack(\"full\")."""
    lines = _header_lines(conn)
    for stage in sorted(STAGE_SECTIONS):
        title, build = STAGE_SECTIONS[stage]
        lines += _section(title, build(conn))
    lines += _section("Decisions", _decision_lines(conn))
    lines += _section("Spikes", _spike_lines(conn))
    lines += _section("Questions", _question_lines(conn))
    lines += _section("Conflicts", _conflict_lines(conn))
    return "\n".join(lines).rstrip() + "\n"


def _component_pack(conn, key: str) -> dict:
    if key.isdigit():
        row = conn.execute(f"SELECT * FROM components WHERE id = ? AND {db.ACTIVE}",
                           (int(key),)).fetchone()
    else:
        row = conn.execute(
            f"SELECT * FROM components WHERE lower(name) = ? AND {db.ACTIVE}",
            (key.lower(),)).fetchone()
    if row is None:
        known = {r["id"]: r["name"] for r in conn.execute(
            f"SELECT id, name FROM components WHERE {db.ACTIVE} ORDER BY id")}
        return {"error": (
            f"Rule: component scope names an active component by id or name — "
            f"{key!r} matches none. Known components (id: name): "
            f"{json.dumps(known, ensure_ascii=False)}.")}
    lines = _header_lines(conn)
    lines += _section(f"Component pack — {row['name']}", _stage6_lines(conn, row["id"]))
    # The decisions the significance heuristic tied to this component and its
    # contracts — a component pack without its ADRs invites re-litigating them.
    decisions = _decision_lines(conn, f'%"components:{row["id"]}"%')
    for k in _active(conn, "contracts", "component_id = ?", (row["id"],)):
        decisions += _decision_lines(conn, f'%"contracts:{k["id"]}"%')
    lines += _section("Linked decisions", decisions)
    return {"scope": f"component:{row['name']}", "markdown": "\n".join(lines).rstrip() + "\n"}


def plan_pack(conn: db.Connection, scope: str = "full") -> dict:
    """A scoped markdown slice of the plan — full (red team, deep rehydration),
    one stage, or one component with its contracts and linked decisions."""
    scope = scope.strip().lower() if isinstance(scope, str) else ""
    if scope in ("", "full"):
        return {"scope": "full", "markdown": render_markdown(conn)}
    kind, sep, key = scope.partition(":")
    if sep and kind == "stage" and key.strip().isdigit():
        stage = int(key)
        if stage in STAGE_SECTIONS:
            title, build = STAGE_SECTIONS[stage]
            lines = _header_lines(conn) + _section(title, build(conn))
            return {"scope": f"stage:{stage}", "markdown": "\n".join(lines).rstrip() + "\n"}
        return {"error": (
            f"Rule: stage packs cover stages {sorted(STAGE_SECTIONS)} — stage 8 is the "
            f"freeze procedure, not content. Offending input: scope={scope!r}.")}
    if sep and kind == "component" and key.strip():
        return _component_pack(conn, key.strip())
    return {"error": (
        f"Rule: scope is {PACK_SCOPES}. Offending input: scope={scope!r}.")}


PLAN_MD = "plan.md"
PLAN_YAML = "plan.yaml"


def export_plan(conn: db.Connection, workspace: str | Path) -> dict:
    """Write plan.md (human-readable) and plan.yaml (round-trippable bundle)
    into the workspace, overwriting previous exports — the exports are derived
    views of the DB, never sources."""
    workspace = Path(workspace)
    md_path = workspace / PLAN_MD
    markdown = render_markdown(conn)
    md_path.write_text(markdown, encoding="utf-8")
    yaml_result = export_yaml(conn, workspace / PLAN_YAML)
    return {
        "plan_md": {"path": str(md_path), "chars": len(markdown)},
        "plan_yaml": yaml_result,
        "note": ("Derived views of the DB — regenerate after any change; edits to these "
                 "files never flow back. plan.yaml reimports with "
                 "`python -m engine.render import <plan.yaml> <new-plan.db>`."),
    }


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
