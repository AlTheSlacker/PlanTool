"""next_gap() — the priority walker (spec section 6). Naive Session-A version;
Session D rewrites internals, but the contract below is stable:

Priority order:
  1 open conflicts (engine- or model-filed)
  2 holes in the current stage
  3 assumed + world  -> spike now
  4 assumed + intent -> ask the user
  5 open questions
  6 advance stage

Cluster contract: return 3-5 *related* gaps per call so the model asks the
user a coherent batch. Grouping key, in order: same entity -> same table ->
same stage. Each gap carries its surrounding rows as context so a cold
session needs no other warm-up. Submits for any stage are always accepted;
next_gap prefers stage order but follows the conversation.
"""
from __future__ import annotations

import json
import sqlite3

from . import db

CLUSTER_MIN = 3
CLUSTER_MAX = 5

GUIDANCE = (
    "Address these as one coherent exchange with the user: form proposals with rationale "
    "wherever you can (proposal-first — ask for objection, not an open question), reserve "
    "blank questions for genuine intent-unknowns, then submit the accepted facts as batched "
    "rows with provenance."
)


def _gap(priority: int, kind: str, table: str, stage: int | None, ask: str,
         *, row_id: int | None = None, entity: str | None = None, context: dict | None = None) -> dict:
    return {
        "priority": priority, "kind": kind, "table": table, "stage": stage,
        "row_id": row_id, "entity": entity, "ask": ask, "context": context or {},
    }


def _rows(conn, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params)]


def _conflict_gaps(conn):
    for r in _rows(conn, "SELECT * FROM conflicts WHERE state = 'open' ORDER BY id"):
        yield _gap(
            1, "conflict", "conflicts", None,
            f"Resolve conflict #{r['id']} ({r['source']}-filed): {r['description']} "
            "Present it to the user with the linked rows; record the resolution.",
            row_id=r["id"],
            context={"conflict": r, "refs": json.loads(r["refs"] or "[]")},
        )


def _stage_holes(conn, stage: int):
    if stage == 1:
        counts = db.table_counts(conn)
        if counts["requirements"] + counts["entities"] + counts["decisions"] == 0:
            yield _gap(
                2, "hole:stage1_not_started", "plans", 1,
                "Nothing recorded yet. Open the stage-1 interview: problem, users, goals with "
                "success criteria, non-goals, constraints, and target stack (see the stage-1 "
                "script from plan_status).",
            )
    elif stage == 2:
        steps = _rows(conn, """
            SELECT s.id, s.step_no, s.text, u.id AS uc_id, u.title
            FROM uc_steps s JOIN use_cases u ON u.id = s.use_case_id
            WHERE s.no_extension_reason IS NULL
              AND NOT EXISTS (SELECT 1 FROM uc_extensions e WHERE e.step_id = s.id)
            ORDER BY u.id, s.step_no""")
        for s in steps:
            yield _gap(
                2, "hole:step_without_extensions", "uc_steps", 2,
                f"Step {s['step_no']} of use case '{s['title']}' — \"{s['text']}\" — has no "
                "extensions and no no_extension_reason. What can fail or vary at this step? "
                "If genuinely nothing, record why.",
                row_id=s["id"], entity=s["title"],
                context={"step": s},
            )
        if not _rows(conn, "SELECT id FROM use_cases LIMIT 1"):
            yield _gap(2, "hole:no_use_cases", "use_cases", 2,
                       "No use cases yet. Elicit them Cockburn-style: primary actor, trigger, "
                       "numbered main scenario, extensions per step.")
    elif stage == 3:
        if not _rows(conn, "SELECT id FROM requirements LIMIT 1"):
            yield _gap(2, "hole:no_requirements", "requirements", 3,
                       "No requirements yet. Derive EARS-typed requirements from the use cases; "
                       "quantify NFRs with Planguage (scale/meter/target).")
        for u in _rows(conn, """
            SELECT u.id, u.title FROM use_cases u
            WHERE NOT EXISTS (SELECT 1 FROM requirements r
                              WHERE r.links LIKE '%"use_cases:' || u.id || '"%')"""):
            yield _gap(
                2, "hole:use_case_untraced", "use_cases", 3,
                f"Use case '{u['title']}' (use_cases:{u['id']}) traces to no requirement. Derive "
                "its requirements and link them (links: [\"use_cases:" + str(u["id"]) + "\"]).",
                row_id=u["id"], entity=u["title"], context={"use_case": u},
            )
        for r in _rows(conn, """
            SELECT * FROM requirements WHERE is_nfr = 1 AND (planguage_scale IS NULL
                OR planguage_meter IS NULL OR planguage_target IS NULL)"""):
            yield _gap(2, "hole:nfr_unquantified", "requirements", 3,
                       f"NFR requirements:{r['id']} lacks a full Planguage triad.",
                       row_id=r["id"], context={"requirement": r})
    elif stage == 4:
        entities = _rows(conn, "SELECT * FROM entities ORDER BY id")
        if not entities:
            yield _gap(2, "hole:no_entities", "entities", 4,
                       "No domain entities yet. Synthesize mode: propose the domain model "
                       "(entities with lifecycle judgments) and let the user adjudicate.")
        for e in entities:
            ops = {r["op"] for r in _rows(conn, "SELECT op FROM crud_grid WHERE entity_id = ?", (e["id"],))}
            missing = [op for op in "CRUD" if op not in ops]
            if missing:
                yield _gap(
                    2, "hole:crud_incomplete", "crud_grid", 4,
                    f"Entity '{e['name']}' has empty CRUD cell(s) {missing}: propose the "
                    "responsible actor/component per op, or an explicit n/a with reason "
                    "(note children-on-delete for D).",
                    row_id=e["id"], entity=e["name"], context={"entity": e, "missing_ops": missing},
                )
            if e["has_lifecycle"]:
                machine = _rows(conn, "SELECT * FROM state_machines WHERE entity_id = ?", (e["id"],))
                if not machine:
                    yield _gap(
                        2, "hole:missing_state_machine", "state_machines", 4,
                        f"Entity '{e['name']}' has a lifecycle but no state machine. Propose "
                        "states and events; every state x event cell must be a transition or an "
                        "explicit impossible + reason.",
                        row_id=e["id"], entity=e["name"], context={"entity": e},
                    )
                else:
                    m = machine[0]
                    states = json.loads(m["states"])
                    events = json.loads(m["events"])
                    have = {(c["state"], c["event"]) for c in
                            _rows(conn, "SELECT state, event FROM sm_cells WHERE machine_id = ?", (m["id"],))}
                    undefined = [[s, ev] for s in states for ev in events if (s, ev) not in have]
                    if undefined:
                        yield _gap(
                            2, "hole:sm_cells_undefined", "sm_cells", 4,
                            f"State machine for '{e['name']}' has {len(undefined)} undefined "
                            f"state x event cell(s), e.g. {undefined[:3]}. Each is a transition "
                            "or an explicit impossible + reason.",
                            row_id=m["id"], entity=e["name"],
                            context={"entity": e, "machine": m, "undefined_cells": undefined},
                        )
    elif stage == 5:
        deps = _rows(conn, "SELECT * FROM dependencies ORDER BY id")
        if not deps:
            yield _gap(2, "hole:no_dependencies", "dependencies", 5,
                       "No external dependencies registered. Register each (service, library, "
                       "api, filesystem, ...) — or record an explicit 'no external dependencies' "
                       "decision.")
        for d in deps:
            modes = {r["mode"] for r in _rows(conn, "SELECT mode FROM dep_failure_modes WHERE dep_id = ?", (d["id"],))}
            missing = [m for m in ("unavailable", "slow", "malformed", "auth", "partial") if m not in modes]
            if missing:
                yield _gap(
                    2, "hole:failure_modes_missing", "dep_failure_modes", 5,
                    f"Dependency '{d['name']}' is missing failure-mode handling for {missing}. "
                    "Propose handling for each (proposal-first).",
                    row_id=d["id"], entity=d["name"], context={"dependency": d, "missing_modes": missing},
                )
    elif stage == 6:
        if not _rows(conn, "SELECT id FROM components LIMIT 1"):
            yield _gap(2, "hole:no_components", "components", 6,
                       "No components yet. Synthesize mode: design the component cut and "
                       "contracts to structured-signature level; the user adjudicates.")
        for c in _rows(conn, """
            SELECT c.* FROM components c
            WHERE NOT EXISTS (SELECT 1 FROM contracts k WHERE k.component_id = c.id)"""):
            yield _gap(2, "hole:component_without_contract", "contracts", 6,
                       f"Component '{c['name']}' has no contract. Every deliverable component "
                       "needs one (params typed or explicit none, return, >=1 named error or "
                       "cannot_fail + reason).",
                       row_id=c["id"], entity=c["name"], context={"component": c})
        for k in _rows(conn, """
            SELECT k.*, c.name AS component_name FROM contracts k
            JOIN components c ON c.id = k.component_id
            WHERE k.is_external = 0
              AND NOT EXISTS (SELECT 1 FROM contract_deps d WHERE d.provider_contract_id = k.id)"""):
            yield _gap(2, "hole:contract_without_consumer", "contract_deps", 6,
                       f"Contract '{k['name']}' on component '{k['component_name']}' has no "
                       "consumer and is not marked external — untraceable contracts are "
                       "invented scope. Record its consumer edge or mark it external.",
                       row_id=k["id"], entity=k["component_name"], context={"contract": k})


# (table, alias, stage, sql) -> rows with id, label, entity for the assumed scans.
_ASSUMED_SCANS = [
    ("use_cases", "use_cases", 2, "SELECT id, title AS label, title AS entity FROM use_cases"),
    ("uc_steps", "s", 2, """SELECT s.id, s.text AS label, u.title AS entity
                       FROM uc_steps s JOIN use_cases u ON u.id = s.use_case_id"""),
    ("uc_extensions", "e", 2, """SELECT e.id, e.description AS label, u.title AS entity
                            FROM uc_extensions e JOIN uc_steps s ON s.id = e.step_id
                            JOIN use_cases u ON u.id = s.use_case_id"""),
    ("requirements", "requirements", 3, "SELECT id, coalesce(system_response, feature) AS label, NULL AS entity FROM requirements"),
    ("entities", "entities", 4, "SELECT id, name AS label, name AS entity FROM entities"),
    ("crud_grid", "g", 4, """SELECT g.id, g.op AS label, e.name AS entity
                        FROM crud_grid g JOIN entities e ON e.id = g.entity_id"""),
    ("state_machines", "m", 4, """SELECT m.id, 'state machine' AS label, e.name AS entity
                             FROM state_machines m JOIN entities e ON e.id = m.entity_id"""),
    ("sm_cells", "c", 4, """SELECT c.id, c.state || ' x ' || c.event AS label, e.name AS entity
                       FROM sm_cells c JOIN state_machines m ON m.id = c.machine_id
                       JOIN entities e ON e.id = m.entity_id"""),
    ("dependencies", "dependencies", 5, "SELECT id, name AS label, name AS entity FROM dependencies"),
    ("dep_failure_modes", "m", 5, """SELECT m.id, m.mode AS label, d.name AS entity
                                FROM dep_failure_modes m JOIN dependencies d ON d.id = m.dep_id"""),
    ("components", "components", 6, "SELECT id, name AS label, name AS entity FROM components"),
    ("contracts", "k", 6, """SELECT k.id, k.name AS label, c.name AS entity
                        FROM contracts k JOIN components c ON c.id = k.component_id"""),
    ("contract_deps", "d", 6, """SELECT d.id, 'edge -> ' || k.name AS label, NULL AS entity
                            FROM contract_deps d JOIN contracts k ON k.id = d.provider_contract_id"""),
    ("decisions", "decisions", None, "SELECT id, text AS label, NULL AS entity FROM decisions"),
]


def _assumed_gaps(conn, kind: str, priority: int, current_stage: int):
    for table, alias, stage, sql in _ASSUMED_SCANS:
        filtered = f"{sql} WHERE {alias}.provenance = 'assumed' AND {alias}.assumption_kind = ?"
        for r in _rows(conn, filtered, (kind,)):
            full = _rows(conn, f"SELECT * FROM {table} WHERE id = ?", (r["id"],))[0]
            if kind == "world":
                ask = (
                    f"World-assumption pending verification — {table}:{r['id']} \"{r['label']}\". "
                    "Resolve by experiment against the real dependency, never by asking the user. "
                    "(Spike tools arrive in a later build session; until then, flag it to the "
                    "user as an unverified risk.)"
                )
            else:
                ask = (
                    f"Intent-assumption awaiting the user — {table}:{r['id']} \"{r['label']}\". "
                    "Only the user can upgrade this: present it (proposal-first, with your "
                    "rationale) and record their answer."
                )
            yield _gap(priority, f"assumed_{kind}", table, stage or current_stage, ask,
                       row_id=r["id"], entity=r["entity"], context={"row": full})


def _question_gaps(conn):
    for q in _rows(conn, "SELECT * FROM open_questions WHERE state = 'open' ORDER BY id"):
        yield _gap(5, "open_question", "open_questions", None,
                   f"Open question #{q['id']} (owner: {q['owner'] or 'unassigned'}): {q['text']}",
                   row_id=q["id"], context={"question": q})


def _cluster(candidates: list[dict]) -> list[dict]:
    """Pick 3-5 related gaps: grouping key entity -> table -> stage (spec section 6)."""
    def order(g):
        return (g["priority"], g["stage"] is None, g["stage"] or 0,
                g["table"], g["entity"] or "", g["row_id"] or 0)

    candidates = sorted(candidates, key=order)
    anchor = candidates[0]
    pool = [g for g in candidates if g["priority"] == anchor["priority"]]
    picked = [anchor]
    picked_ids = {id(anchor)}

    def extend(pred, limit):
        for g in pool:
            if len(picked) >= limit:
                return
            if id(g) not in picked_ids and pred(g):
                picked.append(g)
                picked_ids.add(id(g))

    if anchor["entity"]:
        extend(lambda g: g["entity"] == anchor["entity"], CLUSTER_MAX)
    if len(picked) < CLUSTER_MIN:
        extend(lambda g: g["table"] == anchor["table"], CLUSTER_MAX)
    if len(picked) < CLUSTER_MIN:
        extend(lambda g: g["stage"] == anchor["stage"], CLUSTER_MAX)
    if len(picked) < CLUSTER_MIN:
        # Anchor's priority tier is thin: pad with the next candidates in
        # priority order so the exchange still carries a worthwhile batch.
        for g in candidates:
            if len(picked) >= CLUSTER_MIN:
                break
            if id(g) not in picked_ids:
                picked.append(g)
                picked_ids.add(id(g))
    return picked


def next_gap(conn: sqlite3.Connection) -> dict:
    plan = db.get_plan(conn)
    stage = plan["current_stage"]
    candidates = [
        *(_conflict_gaps(conn)),
        *(_stage_holes(conn, stage)),
        *(_assumed_gaps(conn, "world", 3, stage)),
        *(_assumed_gaps(conn, "intent", 4, stage)),
        *(_question_gaps(conn)),
    ]
    if not candidates:
        return {
            "status": "stage_clear",
            "current_stage": stage,
            "message": (
                f"No open gaps detected for stage {stage}. Run the stage script's self-review "
                f"checklist, then advance via run_gate({stage}) — which verifies completeness "
                "and delivers the next stage's script. (run_gate arrives in a later build "
                "session; until then continue enriching the plan or start the next stage's "
                "topics — submits for any stage are always accepted.)"
            ),
        }
    cluster = _cluster(candidates)
    return {
        "status": "gaps",
        "current_stage": stage,
        "plan_state": plan["state"],
        "cluster": cluster,
        "open_gap_total": len(candidates),
        "guidance": GUIDANCE,
    }
