"""Supersede/retire/confirm — the correction path for wrong or outdated claim
rows (Session D, dogfood finding F1: no amend path existed and duplicates +
gate dead-ends resulted).

Claim rows are never mutated in place. supersede_row creates a successor row
carrying `supersedes`; the original gains `superseded_by` + reason
(bidirectional, machine-checkable lineage). retire_row marks a row wrong with
no replacement (cascading to dependent child rows). Both leave the audit
trail intact: gates, sweeps, next_gap, and duplicate checks see active rows
only (engine/db.ACTIVE).

The one sanctioned in-place mutation is confirm_assumption: an
assumed(intent) row the user has now answered upgrades to decided, with the
user's answer quoted in provenance_note — the actual dogfood blocker
(three record_decision retries left duplicate rows). assumed(world) rows
still upgrade only through spikes.

Mechanics of a supersede: the successor is validated by the same rules as a
fresh submit (original temporarily inactive so natural-key checks pass),
child rows are re-pointed to the successor, and `links` in active rows are
rewritten old-ref -> new-ref so traceability never dangles. Resolved
questions linked to the superseded row get a staleness conflict, exactly as
if a spike had changed it.
"""
from __future__ import annotations

import json

from . import conflicts as conflict_detect
from . import db, submits
from .submits import (
    _all_links, _clean, _dangling_refs_error, _envelope, _envelope_error, _fmt,
    _text,
)

ENVELOPE_KEYS = ("provenance", "assumption_kind", "links")

# Child rows that structurally hang off a parent row (FK columns). On
# supersede the active children re-point to the successor; on retire they
# retire with the parent (a cut parent cuts what only exists because of it).
CHILD_FKS = {
    "use_cases": (("uc_steps", "use_case_id"),),
    "uc_steps": (("uc_extensions", "step_id"),),
    "entities": (("crud_grid", "entity_id"), ("state_machines", "entity_id")),
    "state_machines": (("sm_cells", "machine_id"),),
    "components": (("contracts", "component_id"),
                   ("contract_deps", "consumer_component_id")),
    "contracts": (("contract_deps", "consumer_contract_id"),
                  ("contract_deps", "provider_contract_id")),
    "dependencies": (("dep_failure_modes", "dep_id"),),
}

# Tables whose corrections can create/clear a CRUD contradiction — re-run the
# engine sweep after the write, like their submit surfaces do.
CRUD_SWEEP_TABLES = frozenset(
    {"use_cases", "uc_steps", "uc_extensions", "entities", "crud_grid"})

# Flat tables reuse their submit surface's validate/insert pair — one source
# of truth for the rules a successor row must satisfy.
FLAT_HANDLERS = {
    "requirements": submits._requirement_handlers,
    "entities": submits._entity_handlers,
    "uc_extensions": submits._uc_extension_handlers,
    "crud_grid": submits._crud_handlers,
    "sm_cells": submits._state_cell_handlers,
    "components": submits._component_handlers,
    "contracts": submits._contract_handlers,
    "contract_deps": submits._contract_dep_handlers,
    "dependencies": submits._dependency_handlers,
    "dep_failure_modes": submits._dep_fm_handlers,
}

REJECTED_CHILD_FIELDS = {
    "use_cases": ("steps",),
    "state_machines": ("states", "events", "cells", "entity_id"),
    "uc_steps": ("extensions", "use_case_id", "step_no"),
}


def _jload(value):
    return json.loads(value) if value else None


def _envelope_shape(row) -> dict:
    return {"provenance": row["provenance"], "assumption_kind": row["assumption_kind"],
            "links": _jload(row["links"])}


def _shape_requirements(conn, row) -> dict:
    return {"ears_type": row["ears_type"], "trigger": row["trigger_text"],
            "precondition": row["precondition"], "feature": row["feature"],
            "system_response": row["system_response"], "is_nfr": bool(row["is_nfr"]),
            "planguage_scale": row["planguage_scale"],
            "planguage_meter": row["planguage_meter"],
            "planguage_target": row["planguage_target"], **_envelope_shape(row)}


def _shape_entities(conn, row) -> dict:
    return {"name": row["name"], "description": row["description"],
            "has_lifecycle": bool(row["has_lifecycle"]),
            "lifecycle_reason": row["lifecycle_reason"], **_envelope_shape(row)}


def _shape_uc_extensions(conn, row) -> dict:
    return {"step_id": row["step_id"], "description": row["description"],
            "in_scope": bool(row["in_scope"]), "handling": row["handling"],
            **_envelope_shape(row)}


def _shape_crud_grid(conn, row) -> dict:
    return {"entity_id": row["entity_id"], "op": row["op"], "actor": row["actor"],
            "na": bool(row["na"]), "na_reason": row["na_reason"],
            "children_on_delete": row["children_on_delete"], **_envelope_shape(row)}


def _shape_sm_cells(conn, row) -> dict:
    machine = conn.execute("SELECT entity_id FROM state_machines WHERE id = ?",
                           (row["machine_id"],)).fetchone()
    return {"entity_id": machine["entity_id"], "state": row["state"],
            "event": row["event"], "transition_to": row["transition_to"],
            "impossible": bool(row["impossible"]),
            "impossible_reason": row["impossible_reason"], **_envelope_shape(row)}


def _shape_components(conn, row) -> dict:
    return {"name": row["name"], "responsibility": row["responsibility"],
            **_envelope_shape(row)}


def _shape_contracts(conn, row) -> dict:
    return {"component_id": row["component_id"], "name": row["name"],
            "kind": row["kind"], "params": _jload(row["params"]) or [],
            "returns": row["returns"], "errors": _jload(row["errors"]),
            "cannot_fail": bool(row["cannot_fail"]),
            "cannot_fail_reason": row["cannot_fail_reason"],
            "is_external": bool(row["is_external"]), **_envelope_shape(row)}


def _shape_contract_deps(conn, row) -> dict:
    return {"consumer_contract_id": row["consumer_contract_id"],
            "consumer_component_id": row["consumer_component_id"],
            "provider_contract_id": row["provider_contract_id"], **_envelope_shape(row)}


def _shape_dependencies(conn, row) -> dict:
    return {"name": row["name"], "kind": row["kind"], "notes": row["notes"],
            **_envelope_shape(row)}


def _shape_dep_failure_modes(conn, row) -> dict:
    return {"dep_id": row["dep_id"], "mode": row["mode"], "handling": row["handling"],
            **_envelope_shape(row)}


def _shape_use_cases(conn, row) -> dict:
    return {"title": row["title"], "actor": row["actor"], **_envelope_shape(row)}


def _shape_uc_steps(conn, row) -> dict:
    return {"text": row["text"], "no_extension_reason": row["no_extension_reason"],
            **_envelope_shape(row)}


def _shape_state_machines(conn, row) -> dict:
    return dict(_envelope_shape(row))


def _shape_decisions(conn, row) -> dict:
    return {"text": row["text"], "rationale": row["rationale"],
            "alternatives": _jload(row["alternatives"]),
            "challenge": _jload(row["challenge"]), **_envelope_shape(row)}


SHAPES = {
    "requirements": _shape_requirements, "entities": _shape_entities,
    "uc_extensions": _shape_uc_extensions, "crud_grid": _shape_crud_grid,
    "sm_cells": _shape_sm_cells, "components": _shape_components,
    "contracts": _shape_contracts, "contract_deps": _shape_contract_deps,
    "dependencies": _shape_dependencies, "dep_failure_modes": _shape_dep_failure_modes,
    "use_cases": _shape_use_cases, "uc_steps": _shape_uc_steps,
    "state_machines": _shape_state_machines, "decisions": _shape_decisions,
}

BOOKKEEPING_REMEDIES = (
    "open_questions have resolve_question, conflicts have resolve_conflict, spikes are "
    "one-question-one-row (register a new spike), and gate_results/findings are history"
)


def _table_error(table) -> str | None:
    if table not in db.CLAIM_TABLES:
        return (
            f"Rule: lineage tools work on claim tables {sorted(db.CLAIM_TABLES)} only — "
            f"bookkeeping rows have their own flows ({BOOKKEEPING_REMEDIES}). "
            f"Offending input: table={_fmt(table)}."
        )
    return None


def _fetch_active(conn, table: str, row_id) -> tuple[str, None] | tuple[None, db.Row]:
    if isinstance(row_id, bool) or not isinstance(row_id, int):
        return f"Rule: row_id is an integer. Offending input: row_id={_fmt(row_id)}.", None
    row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
    if row is None:
        return f"Rule: {table}:{row_id} matches nothing in this plan.", None
    if row["superseded_by"]:
        return (
            f"Rule: {table}:{row_id} was already superseded by {table}:{row['superseded_by']} "
            f"(\"{row['superseded_reason']}\") — correct the successor, not the history."), None
    if row["retired"]:
        return (
            f"Rule: {table}:{row_id} was retired (\"{row['superseded_reason']}\") — a retired "
            "row has no successor to correct; submit a fresh row if the fact returned."), None
    return None, row


def _merge(shape: dict, replacement: dict) -> dict:
    """Original's tool-shape + replacements. An explicit null clears a field;
    an absent field keeps the original's value."""
    merged = {k: v for k, v in _clean(shape).items()}
    for key, value in replacement.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    # Changing provenance away from 'assumed' drops a stale assumption_kind
    # unless the replacement addressed it explicitly.
    if ("provenance" in replacement and "assumption_kind" not in replacement
            and merged.get("provenance") != "assumed"):
        merged.pop("assumption_kind", None)
    return merged


def _mark_inactive(conn, table: str, row_id: int, reason: str) -> None:
    conn.execute(
        f"UPDATE {table} SET retired = 1, superseded_reason = ? WHERE id = ?",
        (reason, row_id))


def _repoint_children(conn, table: str, old_id: int, new_id: int) -> dict[str, int]:
    repointed = {}
    for child, fk in CHILD_FKS.get(table, ()):
        cur = conn.execute(
            f"UPDATE {child} SET {fk} = ? WHERE {fk} = ? AND {db.ACTIVE}",
            (new_id, old_id))
        if cur.rowcount:
            repointed[child] = repointed.get(child, 0) + cur.rowcount
    return repointed


def _rewrite_links(conn, old_ref: str, new_ref: str) -> int:
    """Point active rows' links at the successor; history keeps the old ref."""
    old_q, new_q, like = f'"{old_ref}"', f'"{new_ref}"', f'%"{old_ref}"%'
    rewritten = 0
    for table in db.CLAIM_TABLES:
        rewritten += conn.execute(
            f"UPDATE {table} SET links = replace(links, ?, ?) "
            f"WHERE links LIKE ? AND {db.ACTIVE}", (old_q, new_q, like)).rowcount
    rewritten += conn.execute(
        "UPDATE open_questions SET links = replace(links, ?, ?) "
        "WHERE links LIKE ? AND state = 'open'", (old_q, new_q, like)).rowcount
    rewritten += conn.execute(
        "UPDATE spikes SET links = replace(links, ?, ?) "
        "WHERE links LIKE ? AND verdict IS NULL", (old_q, new_q, like)).rowcount
    return rewritten


def _validate_special(conn, table: str, original, merged: dict) -> str | None:
    err = _envelope_error(merged)
    if err:
        return err
    if table == "use_cases":
        if _text(merged, "title") is None or _text(merged, "actor") is None:
            return (f"Rule: a use case keeps a non-empty title and actor. "
                    f"Offending replacement result: {_fmt(merged)}.")
        dup = conn.execute(
            f"SELECT id FROM use_cases WHERE lower(title) = ? AND {db.ACTIVE}",
            (merged["title"].strip().lower(),)).fetchone()
        if dup:
            return (f"Rule: one row per use case — '{merged['title']}' already exists "
                    f"(use_cases:{dup['id']}). Offending replacement result: {_fmt(merged)}.")
    elif table == "uc_steps":
        if _text(merged, "text") is None:
            return (f"Rule: every step needs text. Offending replacement result: "
                    f"{_fmt(merged)}.")
        if _text(merged, "no_extension_reason"):
            exts = conn.execute(
                f"SELECT count(*) FROM uc_extensions WHERE step_id = ? AND {db.ACTIVE}",
                (original["id"],)).fetchone()[0]
            if exts:
                return (
                    f"Rule: a step carries extensions or a no_extension_reason, never both — "
                    f"this step has {exts} active extension(s) that would move to the "
                    "successor. Retire them first (retire_row) if they are wrong, or drop "
                    f"the no_extension_reason. Offending replacement result: {_fmt(merged)}."
                )
    return None


def _insert_special(conn, table: str, original, merged: dict, plan) -> int:
    env = _envelope(plan, merged)
    if table == "use_cases":
        return db.insert_row(conn, "use_cases", {
            "title": _text(merged, "title"), "actor": _text(merged, "actor"), **env})
    if table == "uc_steps":
        return db.insert_row(conn, "uc_steps", {
            "use_case_id": original["use_case_id"], "step_no": original["step_no"],
            "text": _text(merged, "text"),
            "no_extension_reason": _text(merged, "no_extension_reason"), **env})
    # state_machines: only the envelope is replaceable; structure is copied.
    return db.insert_row(conn, "state_machines", {
        "entity_id": original["entity_id"], "states": original["states"],
        "events": original["events"], **env})


def supersede_row(conn: db.Connection, table: str, row_id: int,
                  replacement_fields: dict, reason: str) -> dict:
    err = _table_error(table)
    if err:
        return {"error": err}
    err, original = _fetch_active(conn, table, row_id)
    if err:
        return {"error": err}
    if not isinstance(replacement_fields, dict) or not replacement_fields:
        return {"error": (
            "Rule: replacement_fields is a non-empty object of the fields that change on the "
            "successor (explicit null clears a field; everything else carries over). To mark "
            f"a row wrong with no replacement, use retire_row. Offending input: "
            f"{_fmt(replacement_fields)}.")}
    reason = (reason or "").strip() if isinstance(reason, str) else None
    if not reason:
        return {"error": (
            "Rule: superseding records why the original was wrong or outdated (reason) — "
            "that is the audit trail's whole point.")}
    rejected = [f for f in REJECTED_CHILD_FIELDS.get(table, ()) if f in replacement_fields]
    if rejected:
        return {"error": (
            f"Rule: {rejected} cannot change through supersede_row on {table} — child rows "
            "supersede individually (uc_steps/uc_extensions/sm_cells), and restructuring a "
            "state machine's states/events is retire_row + a fresh submit_states. "
            f"Offending input: {_fmt(replacement_fields)}.")}
    shape = SHAPES[table](conn, original)
    allowed = set(shape) | set(ENVELOPE_KEYS)
    unknown = sorted(set(replacement_fields) - allowed)
    if unknown:
        return {"error": (
            f"Rule: unknown replacement field(s) {unknown} for {table}. Replaceable fields: "
            f"{sorted(allowed)}. Offending input: {_fmt(replacement_fields)}.")}
    if original["provenance"] == "verified" and "provenance" not in replacement_fields:
        return {"error": (
            f"Rule: {table}:{row_id} is verified (spike {original['spike_id']}) — its "
            "successor asserts something the spike did not test, so supply the successor's "
            "own provenance ('assumed' + assumption_kind to re-spike it, or 'decided' with "
            "the user's call). Offending input: " + _fmt(replacement_fields) + ".")}
    merged = _merge(shape, replacement_fields)

    plan = db.get_plan(conn)
    old_ref, savepoint = f"{table}:{row_id}", "supersede_row"
    conn.execute(f"SAVEPOINT {savepoint}")
    try:
        # Original goes inactive first so the successor passes the natural-key
        # checks (name/title/cell uniqueness live on active rows only).
        _mark_inactive(conn, table, row_id, reason)
        if table in FLAT_HANDLERS:
            validate, insert = FLAT_HANDLERS[table](conn)
            err = validate(merged) or _dangling_refs_error(conn, _all_links(merged), merged)
            if err is None:
                result = insert(merged, plan)
                new_id = result if isinstance(result, int) else result["id"]
        elif table == "decisions":
            err, values = submits._decision_values(conn, merged)
            if err is None:
                new_id = db.insert_row(conn, "decisions",
                                       {**values, **_envelope(plan, merged)})
        else:
            err = (_validate_special(conn, table, original, merged)
                   or _dangling_refs_error(conn, _all_links(merged), merged))
            if err is None:
                new_id = _insert_special(conn, table, original, merged, plan)
        if err:
            conn.execute(f"ROLLBACK TO {savepoint}")
            conn.execute(f"RELEASE {savepoint}")
            return {"error": err}
        conn.execute(f"UPDATE {table} SET supersedes = ? WHERE id = ?", (row_id, new_id))
        conn.execute(
            f"UPDATE {table} SET retired = 0, superseded_by = ? WHERE id = ?",
            (new_id, row_id))
        repointed = _repoint_children(conn, table, row_id, new_id)
        links_rewritten = _rewrite_links(conn, old_ref, f"{table}:{new_id}")
        conn.execute(f"RELEASE {savepoint}")
    except db.IntegrityError as exc:
        conn.execute(f"ROLLBACK TO {savepoint}")
        conn.execute(f"RELEASE {savepoint}")
        return {"error": (
            f"Rule: database constraint '{exc}'. Offending replacement result: "
            f"{_fmt(merged)}.")}
    conn.commit()

    out = {"id": new_id, "ref": f"{table}:{new_id}", "supersedes": old_ref,
           "reason": reason}
    if repointed:
        out["children_repointed"] = repointed
    if links_rewritten:
        out["links_rewritten"] = links_rewritten
    stale = conflict_detect.check_resolved_question_staleness(conn, [old_ref])
    filed = list(stale)
    if table in CRUD_SWEEP_TABLES:
        filed += conflict_detect.sweep_crud_contradictions(conn)
    if filed:
        out["conflicts_filed"] = filed
        out["guidance"] = ("Engine-detected conflict(s) were filed — they sit at next_gap() "
                           "priority 1 until resolved with the user.")
    return out


def _retire_cascade(conn, table: str, row_id: int, reason: str,
                    cascaded: list[str]) -> None:
    for child, fk in CHILD_FKS.get(table, ()):
        ids = [r["id"] for r in conn.execute(
            f"SELECT id FROM {child} WHERE {fk} = ? AND {db.ACTIVE}", (row_id,))]
        for cid in ids:
            _mark_inactive(conn, child, cid,
                           f"parent {table}:{row_id} retired: {reason}")
            cascaded.append(f"{child}:{cid}")
            _retire_cascade(conn, child, cid, reason, cascaded)


def retire_row(conn: db.Connection, table: str, row_id: int, reason: str) -> dict:
    err = _table_error(table)
    if err:
        return {"error": err}
    err, original = _fetch_active(conn, table, row_id)
    if err:
        return {"error": err}
    reason = (reason or "").strip() if isinstance(reason, str) else None
    if not reason:
        return {"error": (
            "Rule: retiring records why the row no longer stands (reason) — 'cut it' still "
            "leaves an audit trail.")}
    ref = f"{table}:{row_id}"
    cascaded: list[str] = []
    _mark_inactive(conn, table, row_id, reason)
    _retire_cascade(conn, table, row_id, reason, cascaded)
    conn.commit()
    out = {"retired": ref, "reason": reason}
    if cascaded:
        out["cascaded"] = cascaded
    filed = conflict_detect.check_resolved_question_staleness(conn, [ref])
    if table in CRUD_SWEEP_TABLES:
        filed += conflict_detect.sweep_crud_contradictions(conn)
    if filed:
        out["conflicts_filed"] = filed
    return out


def confirm_assumption(conn: db.Connection, table: str, row_id: int, evidence: str) -> dict:
    err = _table_error(table)
    if err:
        return {"error": err}
    err, row = _fetch_active(conn, table, row_id)
    if err:
        return {"error": err}
    ref = f"{table}:{row_id}"
    if row["provenance"] != "assumed":
        return {"error": (
            f"Rule: confirm_assumption upgrades assumed rows only — {ref} is "
            f"'{row['provenance']}'. If its content is wrong, supersede_row is the remedy.")}
    if row["assumption_kind"] == "world":
        return {"error": (
            f"Rule: {ref} is a world-assumption — a fact about external reality is resolved "
            "by experiment (register_spike -> record_spike_result), never by asking the user. "
            "If the user chooses to accept it unverified, record_decision the accepted risk "
            "and link this row.")}
    evidence = (evidence or "").strip() if isinstance(evidence, str) else None
    if not evidence:
        return {"error": (
            "Rule: the upgrade records the user's actual answer (evidence, quoted) — "
            "that is what turns an assumption into a decision.")}
    note = f"assumed(intent) -> decided: {evidence}"
    conn.execute(
        f"UPDATE {table} SET provenance = 'decided', assumption_kind = NULL, "
        "provenance_note = ? WHERE id = ?", (note, row_id))
    conn.commit()
    out = {"ref": ref, "provenance": "decided", "provenance_note": note}
    stale = conflict_detect.check_resolved_question_staleness(conn, [ref])
    if stale:
        out["conflicts_filed"] = stale
    return out
