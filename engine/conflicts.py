"""Engine-side conflict detection (spec section 6, next_gap priority 1).

The mechanically detectable list is exactly three; add none until dogfood
demands:
  1. Duplicate state x event transitions — made unrepresentable at write time
     (UNIQUE(machine_id, state, event) + submit validation + the reimport
     target carrying the same schema), so there is nothing left to sweep;
     the stronger write-time enforcement subsumes the detector.
  2. n/a CRUD cells contradicted by a use-case step — swept after any
     crud/use-case write (sweep_crud_contradictions). Detection is a coarse
     word match: the step text names the entity and a verb of the n/a'd op.
     Coarse but mechanical; the user adjudicates, dogfood tunes.
  3. Resolved questions whose resolution links to a since-changed row — rows
     only change when a spike upgrades them, so the check runs from
     record_spike_result (check_resolved_question_staleness).

Engine-filed conflicts dedupe on (source='engine', refs): once filed — open
or resolved — the same row pair is never refiled.
"""
from __future__ import annotations

import json
import re
import sqlite3

from . import db

VERB_STEMS = {
    "C": ("creat", "add", "regist", "insert"),
    "R": ("read", "view", "list", "display", "show", "fetch"),
    "U": ("updat", "edit", "modif", "chang", "renam"),
    "D": ("delet", "remov", "purg", "destroy"),
}
OP_WORDS = {"C": "create", "R": "read", "U": "update", "D": "delete"}


def _mentions_entity(text: str, name: str) -> bool:
    return re.search(rf"\b{re.escape(name)}s?\b", text, re.IGNORECASE) is not None


def _mentions_op(text: str, op: str) -> bool:
    return any(re.search(rf"\b{stem}\w*", text, re.IGNORECASE) for stem in VERB_STEMS[op])


def file_engine_conflict(conn: sqlite3.Connection, description: str,
                         refs: list[str]) -> dict | None:
    """Insert an engine-filed conflict unless one with these refs exists."""
    refs_json = json.dumps(refs)
    if conn.execute("SELECT 1 FROM conflicts WHERE source = 'engine' AND refs = ?",
                    (refs_json,)).fetchone():
        return None
    plan = db.get_plan(conn)
    cid = db.insert_row(conn, "conflicts", {
        "plan_id": plan["id"], "plan_version_added": plan["version"],
        "description": description, "refs": refs_json, "source": "engine"})
    return {"id": cid, "description": description, "refs": refs}


def sweep_crud_contradictions(conn: sqlite3.Connection) -> list[dict]:
    """File a conflict for every n/a CRUD cell a use-case step appears to
    contradict. Idempotent: already-filed pairs are skipped."""
    cells = [dict(r) for r in conn.execute("""
        SELECT g.id, g.op, g.na_reason, e.name AS entity
        FROM crud_grid g JOIN entities e ON e.id = g.entity_id
        WHERE g.na = 1 ORDER BY g.id""")]
    if not cells:
        return []
    steps = [dict(r) for r in conn.execute("""
        SELECT s.id, s.text, u.title
        FROM uc_steps s JOIN use_cases u ON u.id = s.use_case_id ORDER BY s.id""")]
    filed = []
    for cell in cells:
        for step in steps:
            if (_mentions_entity(step["text"], cell["entity"])
                    and _mentions_op(step["text"], cell["op"])):
                conflict = file_engine_conflict(
                    conn,
                    f"CRUD cell crud_grid:{cell['id']} records {cell['op']} on entity "
                    f"'{cell['entity']}' as n/a (\"{cell['na_reason']}\"), but use-case step "
                    f"uc_steps:{step['id']} in '{step['title']}' (\"{step['text']}\") appears "
                    f"to {OP_WORDS[cell['op']]} it. One of the two is wrong — present both to "
                    "the user and record the adjudication.",
                    [f"crud_grid:{cell['id']}", f"uc_steps:{step['id']}"])
                if conflict:
                    filed.append(conflict)
    if filed:
        conn.commit()
    return filed


def check_resolved_question_staleness(conn: sqlite3.Connection,
                                      changed_refs: list[str]) -> list[dict]:
    """File a conflict for every resolved question linked to a row that just
    changed — its resolution may no longer hold."""
    filed = []
    for ref in changed_refs:
        for q in conn.execute(
                "SELECT * FROM open_questions WHERE state = 'resolved' AND links LIKE ? "
                "ORDER BY id", (f'%"{ref}"%',)):
            conflict = file_engine_conflict(
                conn,
                f"Question #{q['id']} (\"{q['text']}\") was resolved "
                f"(\"{q['resolution']}\") while linked to {ref}, which has since changed — "
                "re-check with the user that the resolution still holds.",
                [f"open_questions:{q['id']}", ref])
            if conflict:
                filed.append(conflict)
    if filed:
        conn.commit()
    return filed
