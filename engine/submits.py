"""Write-time validation and batched/single-row inserts (spec section 5).

Contract: every submitted row gets its own accept/reject verdict — one bad
row never bounces the batch. Rejections are pedagogic: they name the rule,
show the offending input, and show what compliance looks like.

Nested rows (use cases with steps/extensions, state machines with cells)
are all-or-nothing per row: a bad child rejects its whole row, and a
savepoint guarantees no partial insert survives.
"""
from __future__ import annotations

import json
import sqlite3

from . import conflicts as conflict_detect
from . import db

PROVENANCE_VALUES = ("decided", "derived", "assumed", "verified")
ASSUMPTION_KINDS = ("world", "intent")
CRUD_OPS = ("C", "R", "U", "D")
FAILURE_MODES = ("unavailable", "slow", "malformed", "auth", "partial")
CONTRACT_KINDS = ("api", "function", "schema", "file", "event")
CHALLENGE_OUTCOMES = ("overridden", "revised")
# Spec section 4: any decision whose links touch a component or contract is
# significant — set by this heuristic (coarse but ungameable), never by the model.
SIGNIFICANT_LINK_TABLES = frozenset({"components", "contracts"})
KNOWN_REF_TABLES = frozenset(db.COUNTED_TABLES) | {"plans"}

EARS_SLOTS = {
    "ubiquitous": ("system_response",),
    "event": ("trigger", "system_response"),
    "state": ("precondition", "system_response"),
    "unwanted": ("trigger", "system_response"),
    "optional": ("feature", "system_response"),
}
SLOT_FIELDS = ("trigger", "precondition", "feature", "system_response")
EARS_TEMPLATES = {
    "ubiquitous": "The <system> shall <system_response>.",
    "event": "WHEN <trigger>, the <system> shall <system_response>.",
    "state": "WHILE <precondition>, the <system> shall <system_response>.",
    "unwanted": "IF <trigger (the unwanted condition)>, THEN the <system> shall <system_response>.",
    "optional": "WHERE <feature>, the <system> shall <system_response>.",
}
EARS_EXAMPLES = {
    "ubiquitous": {"ears_type": "ubiquitous", "system_response": "record every submitted row with provenance and a timestamp", "provenance": "decided"},
    "event": {"ears_type": "event", "trigger": "the user submits a valid order", "system_response": "persist the order and emit an OrderPlaced event", "provenance": "decided"},
    "state": {"ears_type": "state", "precondition": "the plan is frozen", "system_response": "reject all submit calls with a frozen-plan error", "provenance": "decided"},
    "unwanted": {"ears_type": "unwanted", "trigger": "the payment gateway does not respond within 5 seconds", "system_response": "queue the charge for retry and notify the user", "provenance": "decided"},
    "optional": {"ears_type": "optional", "feature": "the audit-log feature is enabled", "system_response": "append every state change to the audit log", "provenance": "decided"},
}
PLANGUAGE_FIELDS = ("planguage_scale", "planguage_meter", "planguage_target")
NFR_EXAMPLE = {
    "ears_type": "ubiquitous",
    "system_response": "serve plan_status within the latency target",
    "is_nfr": True,
    "planguage_scale": "p95 response latency in milliseconds",
    "planguage_meter": "load test: 100 sequential plan_status calls on a 500-row plan",
    "planguage_target": "<= 200 ms",
    "provenance": "decided",
}

ENVELOPE_FIELDS = ("provenance", "assumption_kind", "links")
REQUIREMENT_FIELDS = frozenset(
    ("ears_type", "is_nfr", *SLOT_FIELDS, *PLANGUAGE_FIELDS, *ENVELOPE_FIELDS)
)
ENTITY_FIELDS = frozenset(
    ("name", "description", "has_lifecycle", "lifecycle_reason", *ENVELOPE_FIELDS)
)
UC_FIELDS = frozenset(("title", "actor", "steps", *ENVELOPE_FIELDS))
STEP_FIELDS = frozenset(("text", "no_extension_reason", "extensions", *ENVELOPE_FIELDS))
EXT_FIELDS = frozenset(("description", "in_scope", "handling", *ENVELOPE_FIELDS))
UC_EXT_FIELDS = EXT_FIELDS | {"step_id"}
CRUD_FIELDS = frozenset(
    ("entity_id", "op", "actor", "na", "na_reason", "children_on_delete", *ENVELOPE_FIELDS)
)
SM_FIELDS = frozenset(("entity_id", "states", "events", "cells", *ENVELOPE_FIELDS))
CELL_FIELDS = frozenset(
    ("state", "event", "transition_to", "impossible", "impossible_reason", *ENVELOPE_FIELDS)
)
SM_CELL_FIELDS = CELL_FIELDS | {"entity_id"}
COMPONENT_FIELDS = frozenset(("name", "responsibility", *ENVELOPE_FIELDS))
CONTRACT_FIELDS = frozenset(
    ("component_id", "name", "kind", "params", "returns", "errors",
     "cannot_fail", "cannot_fail_reason", "is_external", *ENVELOPE_FIELDS)
)
PARAM_FIELDS = frozenset(("name", "type_expr", "required"))
ERROR_ITEM_FIELDS = frozenset(("name", "semantics"))
CONTRACT_DEP_FIELDS = frozenset(
    ("consumer_contract_id", "consumer_component_id", "provider_contract_id", *ENVELOPE_FIELDS)
)
DEPENDENCY_FIELDS = frozenset(("name", "kind", "notes", *ENVELOPE_FIELDS))
DEP_FM_FIELDS = frozenset(("dep_id", "mode", "handling", *ENVELOPE_FIELDS))
ALTERNATIVE_FIELDS = frozenset(("alternative", "rejected_because"))
CHALLENGE_FIELDS = frozenset(("text", "outcome"))

UC_EXAMPLE = {
    "title": "Place an order",
    "actor": "Customer",
    "steps": [
        {"text": "Customer submits the completed order form",
         "extensions": [{"description": "form fails validation",
                         "handling": "return field-level errors; order not created"}]},
        {"text": "System assigns the next order number",
         "no_extension_reason": "monotonic counter inside one transaction; no external input"},
    ],
    "provenance": "decided",
}
EXT_EXAMPLE = {
    "description": "payment gateway times out",
    "in_scope": True,
    "handling": "queue the charge for retry; order stays pending_payment",
}
CRUD_EXAMPLE = {
    "entity_id": 1, "op": "D", "actor": "OrderService",
    "children_on_delete": "order lines are cascade-deleted", "provenance": "decided",
}
CRUD_NA_EXAMPLE = {
    "entity_id": 1, "op": "U", "na": True,
    "na_reason": "orders are immutable once placed; corrections are new orders",
    "provenance": "decided",
}
SM_EXAMPLE = {
    "entity_id": 1,
    "states": ["draft", "placed", "shipped", "cancelled"],
    "events": ["place", "ship", "cancel"],
    "cells": [
        {"state": "draft", "event": "place", "transition_to": "placed"},
        {"state": "shipped", "event": "cancel", "impossible": True,
         "impossible_reason": "goods already dispatched; use the returns flow instead"},
    ],
    "provenance": "decided",
}
COMPONENT_EXAMPLE = {
    "name": "OrderService",
    "responsibility": "owns order lifecycle state and enforces order invariants",
    "provenance": "decided",
}
CONTRACT_EXAMPLE = {
    "component_id": 1, "name": "place_order", "kind": "function",
    "params": [{"name": "draft", "type_expr": "OrderDraft", "required": True}],
    "returns": "OrderId",
    "errors": [{"name": "ValidationError",
                "semantics": "draft violates an order invariant; nothing persisted"}],
    "provenance": "decided",
}
CONTRACT_CANNOT_FAIL_EXAMPLE = {
    "component_id": 1, "name": "order_total", "kind": "function",
    "params": [{"name": "order", "type_expr": "Order", "required": True}],
    "returns": "Money",
    "cannot_fail": True,
    "cannot_fail_reason": "pure in-memory computation over an already-validated order",
    "provenance": "decided",
}
CONTRACT_DEP_EXAMPLE = {
    "consumer_component_id": 2, "provider_contract_id": 5, "provenance": "decided",
}
DEPENDENCY_EXAMPLE = {
    "name": "Stripe API", "kind": "api",
    "notes": "card payments; REST, versioned", "provenance": "decided",
}
DEP_FM_EXAMPLE = {
    "dep_id": 1, "mode": "slow",
    "handling": "2s client timeout; degrade to cached quote and flag it stale",
    "provenance": "decided",
}
DECISION_EXAMPLE = {
    "text": "Orders are soft-deleted (status=cancelled), never removed",
    "provenance": "decided",
    "rationale": "user chose auditability over storage: \"keep everything, we get disputes\"",
    "links": ["entities:1", "contracts:5"],
    "alternatives": [{"alternative": "hard delete plus a separate audit table",
                      "rejected_because": "two sources of truth for order history"}],
}


# --- generic helpers ---------------------------------------------------------

def _fmt(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def _strip(v) -> str | None:
    """Value as a stripped non-empty string, else None."""
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return None


def _text(row: dict, field: str) -> str | None:
    return _strip(row.get(field))


def _clean(value):
    """Drop None values recursively so optional-field defaults never mask intent."""
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    return value


def _unknown_fields_error(row: dict, allowed: frozenset[str]) -> str | None:
    unknown = sorted(set(row) - allowed)
    if unknown:
        return (
            f"Rule: unknown field(s) {unknown} — likely a typo or a fact that belongs in "
            f"another table. Valid fields: {sorted(allowed)}. Offending row: {_fmt(row)}."
        )
    return None


def _parse_ref(ref: str) -> tuple[str, int] | None:
    table, sep, rid = ref.partition(":")
    if sep and table in KNOWN_REF_TABLES and rid.isdigit():
        return table, int(rid)
    return None


def _links_error(row: dict) -> str | None:
    links = row.get("links")
    if links is None:
        return None
    if not isinstance(links, list) or any(
        not isinstance(x, str) or _parse_ref(x) is None for x in links
    ):
        return (
            "Rule: links is a JSON array of row refs shaped \"table:id\" where table is one of "
            f"the plan tables {sorted(KNOWN_REF_TABLES)}, e.g. [\"requirements:12\", "
            f"\"decisions:3\"]. Offending row: {_fmt(row)}."
        )
    return None


def _dangling_refs_error(conn, refs, offending) -> str | None:
    """Refs (already format-validated) must point at existing rows."""
    missing = []
    for ref in refs or []:
        table, rid = _parse_ref(ref)
        if not conn.execute(f"SELECT 1 FROM {table} WHERE id = ?", (rid,)).fetchone():
            missing.append(ref)
    if missing:
        return (
            f"Rule: refs must point at existing rows — {missing} match nothing in this plan. "
            f"Offending input: {_fmt(offending)}."
        )
    return None


def _envelope_error(row: dict) -> str | None:
    """Validate the provenance envelope every submit carries (spec section 4)."""
    prov = _text(row, "provenance")
    if prov not in PROVENANCE_VALUES:
        return (
            f"Rule: every row carries provenance, one of {list(PROVENANCE_VALUES)}. "
            f"Offending row: {_fmt(row)}. Compliant: add \"provenance\": \"decided\" if the user "
            "chose this, \"derived\" if it follows from a recorded row (link it), or \"assumed\" "
            "(plus assumption_kind) if you filled a gap pending confirmation."
        )
    kind = _text(row, "assumption_kind")
    if prov == "assumed" and kind not in ASSUMPTION_KINDS:
        return (
            "Rule: every assumed row carries assumption_kind — 'world' (a fact about external "
            "reality, resolvable by a spike) or 'intent' (a fact about what the user wants, "
            f"resolvable only by the user). Offending row: {_fmt(row)}. Compliant: add "
            "\"assumption_kind\": \"world\" or \"intent\"."
        )
    if prov != "assumed" and kind is not None:
        return (
            "Rule: assumption_kind accompanies provenance='assumed' only. "
            f"Offending row: {_fmt(row)}. Compliant: drop assumption_kind, or set "
            "provenance='assumed' if this really is an unconfirmed assumption."
        )
    if prov == "verified":
        return (
            "Rule: 'verified' is never set at submit time — only recording a spike result "
            "upgrades an assumed(world) row to verified. Offending row: " + _fmt(row) + ". "
            "Compliant: submit with provenance='assumed', assumption_kind='world', then "
            "register_spike (linking this row), run it against the real dependency, and "
            "record_spike_result — a confirmed verdict performs the upgrade."
        )
    return _links_error(row)


def _child_envelope_error(child: dict) -> str | None:
    """Children may omit provenance (they inherit the parent's); if they carry
    any of it, the full envelope rules apply."""
    if _text(child, "provenance") is None and _text(child, "assumption_kind") is None:
        return _links_error(child)
    return _envelope_error(child)


def _envelope(plan, row: dict) -> dict:
    return {
        "plan_id": plan["id"],
        "plan_version_added": plan["version"],
        "provenance": _text(row, "provenance"),
        "assumption_kind": _text(row, "assumption_kind"),
        "links": json.dumps(row["links"]) if row.get("links") else None,
    }


def _child_envelope(plan, child: dict, parent_env: dict) -> dict:
    """Children inherit the parent's provenance unless they carry their own;
    links are always the child's own."""
    env = dict(parent_env)
    if _text(child, "provenance"):
        env["provenance"] = _text(child, "provenance")
        env["assumption_kind"] = _text(child, "assumption_kind")
    env["links"] = json.dumps(child["links"]) if child.get("links") else None
    return env


def _id_lookup_error(conn, row: dict, field: str, table: str,
                     label_expr: str = "name") -> str | None:
    rid = row.get(field)
    if isinstance(rid, bool) or not isinstance(rid, int) or not conn.execute(
            f"SELECT 1 FROM {table} WHERE id = ?", (rid,)).fetchone():
        known = {r["id"]: r["label"] for r in conn.execute(
            f"SELECT id, {label_expr} AS label FROM {table} ORDER BY id")}
        return (
            f"Rule: {field} is the integer id of an existing {table} row. "
            f"Known {table} (id: label): {_fmt(known)}. Offending row: {_fmt(row)}."
        )
    return None


def _fetch(conn, table: str, rid: int) -> sqlite3.Row:
    return conn.execute(f"SELECT * FROM {table} WHERE id = ?", (rid,)).fetchone()


def _bookkeeping_values(plan) -> dict:
    return {"plan_id": plan["id"], "plan_version_added": plan["version"]}


def _submit_batch(conn, rows, validate, insert) -> dict:
    """Shared batch driver: per-row verdicts, partial acceptance, one commit.

    insert(row, plan) may write child rows and may return either a row id or
    a dict of verdict extras; each row runs inside a savepoint so a mid-children
    integrity failure never leaves a partial row behind.
    """
    plan = db.get_plan(conn)
    verdicts = []
    for i, raw in enumerate(rows):
        row = _clean(dict(raw))
        err = validate(row)
        if err is None:
            conn.execute("SAVEPOINT submit_row")
            try:
                result = insert(row, plan)
                conn.execute("RELEASE submit_row")
                verdict = {"index": i, "accepted": True}
                verdict.update(result if isinstance(result, dict) else {"id": result})
                verdicts.append(verdict)
                continue
            except sqlite3.IntegrityError as exc:
                conn.execute("ROLLBACK TO submit_row")
                conn.execute("RELEASE submit_row")
                err = f"Rule: database constraint '{exc}'. Offending row: {_fmt(row)}."
        verdicts.append({"index": i, "accepted": False, "error": err})
    conn.commit()
    return {
        "results": verdicts,
        "accepted": sum(1 for v in verdicts if v["accepted"]),
        "rejected": sum(1 for v in verdicts if not v["accepted"]),
    }


def _with_crud_sweep(conn, result: dict) -> dict:
    """After a write that can create an n/a-cell-vs-step contradiction, run the
    engine conflict sweep (spec section 6) and surface anything it filed."""
    if result["accepted"]:
        filed = conflict_detect.sweep_crud_contradictions(conn)
        if filed:
            result["conflicts_filed"] = filed
            result.setdefault("guidance", "")
            result["guidance"] = (result["guidance"] + " Engine-detected conflict(s) were "
                                  "filed — they sit at next_gap() priority 1 until resolved "
                                  "with the user.").strip()
    return result


# --- requirements (stage 3) --------------------------------------------------

def _validate_requirement(row: dict) -> str | None:
    err = _unknown_fields_error(row, REQUIREMENT_FIELDS) or _envelope_error(row)
    if err:
        return err
    ears_type = _text(row, "ears_type")
    if ears_type not in EARS_SLOTS:
        sigs = "; ".join(f"{t}({' + '.join(s)})" for t, s in EARS_SLOTS.items())
        return (
            f"Rule: ears_type must be one of {list(EARS_SLOTS)}, each with typed slots: {sigs}. "
            f"Offending row: {_fmt(row)}. Example: {_fmt(EARS_EXAMPLES['event'])}."
        )
    required = EARS_SLOTS[ears_type]
    missing = [s for s in required if _text(row, s) is None]
    if missing:
        return (
            f"Rule: ears_type '{ears_type}' requires slot(s) {list(required)}; missing {missing}. "
            f"Template: {EARS_TEMPLATES[ears_type]} Offending row: {_fmt(row)}. "
            f"Compliant example: {_fmt(EARS_EXAMPLES[ears_type])}."
        )
    stray = [s for s in SLOT_FIELDS if s not in required and _text(row, s) is not None]
    if stray:
        return (
            f"Rule: ears_type '{ears_type}' takes only slot(s) {list(required)} — {stray} does "
            f"not belong. Template: {EARS_TEMPLATES[ears_type]} Offending row: {_fmt(row)}. "
            "Compliant: pick the ears_type whose template matches what you mean, or drop the "
            "stray slot."
        )
    is_nfr = bool(row.get("is_nfr"))
    planguage_missing = [f for f in PLANGUAGE_FIELDS if _text(row, f) is None]
    if is_nfr and planguage_missing:
        return (
            f"Rule: every NFR is quantified with the Planguage triad {list(PLANGUAGE_FIELDS)}; "
            f"missing {planguage_missing}. Offending row: {_fmt(row)}. "
            f"Compliant example: {_fmt(NFR_EXAMPLE)}."
        )
    if not is_nfr and len(planguage_missing) < len(PLANGUAGE_FIELDS):
        return (
            "Rule: planguage fields quantify NFRs; this row has planguage values but "
            f"is_nfr is not true. Offending row: {_fmt(row)}. Compliant: set \"is_nfr\": true "
            "(and supply all three planguage fields), or drop the planguage values."
        )
    return None


def submit_requirements(conn: sqlite3.Connection, rows: list[dict]) -> dict:
    def insert(row, plan):
        return db.insert_row(conn, "requirements", {
            "ears_type": _text(row, "ears_type"),
            "trigger_text": _text(row, "trigger"),
            "precondition": _text(row, "precondition"),
            "feature": _text(row, "feature"),
            "system_response": _text(row, "system_response"),
            "is_nfr": 1 if row.get("is_nfr") else 0,
            "planguage_scale": _text(row, "planguage_scale"),
            "planguage_meter": _text(row, "planguage_meter"),
            "planguage_target": _text(row, "planguage_target"),
            **_envelope(plan, row),
        })

    return _submit_batch(conn, rows, _validate_requirement, insert)


# --- entities (stage 4) ------------------------------------------------------

def submit_entities(conn: sqlite3.Connection, rows: list[dict]) -> dict:
    seen_names: set[str] = set()

    def validate(row: dict) -> str | None:
        err = _unknown_fields_error(row, ENTITY_FIELDS) or _envelope_error(row)
        if err:
            return err
        name = _text(row, "name")
        if name is None:
            return f"Rule: every entity needs a non-empty name. Offending row: {_fmt(row)}."
        key = name.lower()
        exists = key in seen_names or conn.execute(
            "SELECT 1 FROM entities WHERE lower(name) = ?", (key,)
        ).fetchone()
        if exists:
            return (
                f"Rule: one row per entity — '{name}' already exists in this plan (or earlier "
                f"in this batch). Offending row: {_fmt(row)}. If this adds detail, it belongs "
                "on the existing row's grid/state machine, not a duplicate entity."
            )
        if row.get("has_lifecycle") not in (True, False, 0, 1):
            return (
                "Rule: has_lifecycle is a judgment you must make, true or false — true iff the "
                "entity moves through states worth modelling (a state machine is then required). "
                f"Offending row: {_fmt(row)}."
            )
        if not row.get("has_lifecycle") and _text(row, "lifecycle_reason") is None:
            return (
                "Rule: has_lifecycle=false needs a recorded justification (lifecycle_reason), "
                "adjudicated like any synthesize-mode proposal. Offending row: " + _fmt(row) + ". "
                "Compliant example: {\"name\": \"AuditEntry\", \"has_lifecycle\": false, "
                "\"lifecycle_reason\": \"append-only record; created once, never mutated\", "
                "\"provenance\": \"decided\"}."
            )
        seen_names.add(key)
        return None

    def insert(row, plan):
        return db.insert_row(conn, "entities", {
            "name": _text(row, "name"),
            "description": _text(row, "description"),
            "has_lifecycle": 1 if row.get("has_lifecycle") else 0,
            "lifecycle_reason": _text(row, "lifecycle_reason"),
            **_envelope(plan, row),
        })

    return _submit_batch(conn, rows, validate, insert)


# --- use cases (stage 2) -----------------------------------------------------

def _extension_body_error(ext: dict) -> str | None:
    if _text(ext, "description") is None:
        return (
            "Rule: every extension describes its failure/variant (description). "
            f"Offending extension: {_fmt(ext)}. Compliant example: {_fmt(EXT_EXAMPLE)}."
        )
    in_scope = ext.get("in_scope", True)
    if in_scope not in (True, False, 0, 1):
        return f"Rule: in_scope is a boolean (default true). Offending extension: {_fmt(ext)}."
    if in_scope and _text(ext, "handling") is None:
        return (
            "Rule: an in-scope extension records its handling; only out-of-scope "
            f"(in_scope=false) extensions may omit it. Offending extension: {_fmt(ext)}. "
            f"Compliant example: {_fmt(EXT_EXAMPLE)}."
        )
    return None


def _extension_error(ext) -> str | None:
    if not isinstance(ext, dict):
        return (
            "Rule: each extension is an object (description, in_scope, handling). "
            f"Offending extension: {_fmt(ext)}."
        )
    return (_unknown_fields_error(ext, EXT_FIELDS) or _child_envelope_error(ext)
            or _extension_body_error(ext))


def _step_error(step, step_no: int) -> str | None:
    if not isinstance(step, dict):
        return f"Rule: each step is an object with at least text. Offending step {step_no}: {_fmt(step)}."
    err = _unknown_fields_error(step, STEP_FIELDS) or _child_envelope_error(step)
    if err:
        return f"Step {step_no}: {err}"
    if _text(step, "text") is None:
        return f"Rule: every step needs text. Offending step {step_no}: {_fmt(step)}."
    exts = step.get("extensions")
    if exts is not None and not isinstance(exts, list):
        return f"Rule: extensions is an array of extension objects. Offending step {step_no}: {_fmt(step)}."
    if _text(step, "no_extension_reason") and exts:
        return (
            "Rule: a step carries extensions or a no_extension_reason, never both — the reason "
            f"asserts nothing can fail or vary here. Offending step {step_no}: {_fmt(step)}. "
            "Drop one of the two."
        )
    for ext in exts or []:
        err = _extension_error(ext)
        if err:
            return f"Step {step_no}: {err}"
    return None


def submit_use_cases(conn: sqlite3.Connection, rows: list[dict]) -> dict:
    seen_titles: set[str] = set()

    def validate(row: dict) -> str | None:
        err = _unknown_fields_error(row, UC_FIELDS) or _envelope_error(row)
        if err:
            return err
        title = _text(row, "title")
        if title is None:
            return (
                f"Rule: every use case needs a title. Offending row: {_fmt(row)}. "
                f"Compliant example: {_fmt(UC_EXAMPLE)}."
            )
        if _text(row, "actor") is None:
            return (
                "Rule: every use case names its primary actor (Cockburn coverage). "
                f"Offending row: {_fmt(row)}. Compliant example: {_fmt(UC_EXAMPLE)}."
            )
        key = title.lower()
        if key in seen_titles or conn.execute(
                "SELECT 1 FROM use_cases WHERE lower(title) = ?", (key,)).fetchone():
            return (
                f"Rule: one row per use case — '{title}' already exists in this plan (or earlier "
                f"in this batch). Offending row: {_fmt(row)}."
            )
        steps = row.get("steps")
        if not isinstance(steps, list) or not steps:
            return (
                "Rule: a use case is its numbered main scenario — steps is a non-empty array, "
                f"and array order is the step number. Offending row: {_fmt(row)}. "
                f"Compliant example: {_fmt(UC_EXAMPLE)}."
            )
        for step_no, step in enumerate(steps, start=1):
            err = _step_error(step, step_no)
            if err:
                return err
        seen_titles.add(key)
        return None

    def insert(row, plan):
        env = _envelope(plan, row)
        uc_id = db.insert_row(conn, "use_cases", {
            "title": _text(row, "title"), "actor": _text(row, "actor"), **env})
        step_ids = []
        for step_no, step in enumerate(row["steps"], start=1):
            step_env = _child_envelope(plan, step, env)
            step_id = db.insert_row(conn, "uc_steps", {
                "use_case_id": uc_id, "step_no": step_no, "text": _text(step, "text"),
                "no_extension_reason": _text(step, "no_extension_reason"), **step_env})
            step_ids.append(step_id)
            for ext in step.get("extensions") or []:
                db.insert_row(conn, "uc_extensions", {
                    "step_id": step_id,
                    "description": _text(ext, "description"),
                    "in_scope": 1 if ext.get("in_scope", True) else 0,
                    "handling": _text(ext, "handling"),
                    **_child_envelope(plan, ext, step_env)})
        return {"id": uc_id, "step_ids": step_ids}

    return _with_crud_sweep(conn, _submit_batch(conn, rows, validate, insert))


def submit_uc_extensions(conn: sqlite3.Connection, rows: list[dict]) -> dict:
    def validate(row: dict) -> str | None:
        err = (_unknown_fields_error(row, UC_EXT_FIELDS) or _envelope_error(row)
               or _id_lookup_error(conn, row, "step_id", "uc_steps", "substr(text, 1, 60)"))
        if err:
            return err
        step = _fetch(conn, "uc_steps", row["step_id"])
        if step["no_extension_reason"]:
            return (
                f"Rule: step uc_steps:{step['id']} is recorded as unable to fail "
                f"(no_extension_reason: \"{step['no_extension_reason']}\") — adding an extension "
                "contradicts that. If the recorded reason is now wrong, file_conflict "
                f"referencing uc_steps:{step['id']} so the user can adjudicate. "
                f"Offending row: {_fmt(row)}."
            )
        return _extension_body_error(row)

    def insert(row, plan):
        return db.insert_row(conn, "uc_extensions", {
            "step_id": row["step_id"],
            "description": _text(row, "description"),
            "in_scope": 1 if row.get("in_scope", True) else 0,
            "handling": _text(row, "handling"),
            **_envelope(plan, row)})

    return _with_crud_sweep(conn, _submit_batch(conn, rows, validate, insert))


# --- CRUD grid (stage 4) -----------------------------------------------------

def submit_crud(conn: sqlite3.Connection, rows: list[dict]) -> dict:
    seen: set[tuple] = set()

    def validate(row: dict) -> str | None:
        err = (_unknown_fields_error(row, CRUD_FIELDS) or _envelope_error(row)
               or _id_lookup_error(conn, row, "entity_id", "entities"))
        if err:
            return err
        op = row.get("op")
        op = op.strip().upper() if isinstance(op, str) else op
        if op not in CRUD_OPS:
            return (
                f"Rule: op is one of {list(CRUD_OPS)} (one row per entity x op). "
                f"Offending row: {_fmt(row)}. Examples — assigned: {_fmt(CRUD_EXAMPLE)}; "
                f"explicit n/a: {_fmt(CRUD_NA_EXAMPLE)}."
            )
        row["op"] = op
        na = row.get("na", False)
        if na not in (True, False, 0, 1):
            return f"Rule: na is a boolean. Offending row: {_fmt(row)}."
        actor = _text(row, "actor")
        if na:
            if actor:
                return (
                    "Rule: a cell is either assigned to an actor/component or explicitly n/a — "
                    f"never both. Offending row: {_fmt(row)}."
                )
            if _text(row, "na_reason") is None:
                return (
                    "Rule: an n/a cell records why the operation never happens (na_reason). "
                    f"Offending row: {_fmt(row)}. Compliant example: {_fmt(CRUD_NA_EXAMPLE)}."
                )
        else:
            if _text(row, "na_reason"):
                return (
                    f"Rule: na_reason accompanies na=true only. Offending row: {_fmt(row)}. "
                    "Set na=true if the operation genuinely never happens."
                )
            if actor is None:
                return (
                    "Rule: every CRUD cell names the responsible actor/component, or is an "
                    f"explicit n/a + reason. Offending row: {_fmt(row)}. Examples — assigned: "
                    f"{_fmt(CRUD_EXAMPLE)}; n/a: {_fmt(CRUD_NA_EXAMPLE)}."
                )
        if _text(row, "children_on_delete") and op != "D":
            return (
                "Rule: children_on_delete belongs on the D cell only. "
                f"Offending row: {_fmt(row)}."
            )
        key = (row["entity_id"], op)
        if key in seen or conn.execute(
                "SELECT 1 FROM crud_grid WHERE entity_id = ? AND op = ?", key).fetchone():
            return (
                f"Rule: one row per entity x op — cell (entity {row['entity_id']}, {op}) is "
                f"already recorded in this plan (or earlier in this batch). Offending row: "
                f"{_fmt(row)}. If the recorded cell is wrong, file_conflict referencing it so "
                "the user can adjudicate."
            )
        seen.add(key)
        return None

    def insert(row, plan):
        return db.insert_row(conn, "crud_grid", {
            "entity_id": row["entity_id"], "op": row["op"], "actor": _text(row, "actor"),
            "na": 1 if row.get("na") else 0, "na_reason": _text(row, "na_reason"),
            "children_on_delete": _text(row, "children_on_delete"),
            **_envelope(plan, row)})

    return _with_crud_sweep(conn, _submit_batch(conn, rows, validate, insert))


# --- state machines (stage 4) ------------------------------------------------

def _name_list_error(row: dict, field: str, what: str) -> str | None:
    v = row.get(field)
    if not isinstance(v, list) or not v or any(
            not isinstance(x, str) or not x.strip() for x in v):
        return (
            f"Rule: {field} is a non-empty array of {what} names. Offending row: {_fmt(row)}. "
            f"Compliant example: {_fmt(SM_EXAMPLE)}."
        )
    if len({x.strip() for x in v}) != len(v):
        return f"Rule: {field} must not contain duplicates. Offending row: {_fmt(row)}."
    return None


def _cell_body_error(cell: dict, states: list[str], events: list[str]) -> str | None:
    if _text(cell, "state") not in states:
        return (
            f"Rule: cell state must be one of the machine's states {states}. "
            f"Offending cell: {_fmt(cell)}."
        )
    if _text(cell, "event") not in events:
        return (
            f"Rule: cell event must be one of the machine's events {events}. "
            f"Offending cell: {_fmt(cell)}."
        )
    impossible = cell.get("impossible", False)
    if impossible not in (True, False, 0, 1):
        return f"Rule: impossible is a boolean. Offending cell: {_fmt(cell)}."
    transition = _text(cell, "transition_to")
    if impossible:
        if transition:
            return (
                "Rule: a cell is a transition or explicitly impossible — never both. "
                f"Offending cell: {_fmt(cell)}."
            )
        if _text(cell, "impossible_reason") is None:
            return (
                "Rule: an impossible cell records why (impossible_reason). Offending cell: "
                f"{_fmt(cell)}. Compliant example: {_fmt(SM_EXAMPLE['cells'][1])}."
            )
    else:
        if _text(cell, "impossible_reason"):
            return (
                "Rule: impossible_reason accompanies impossible=true only. "
                f"Offending cell: {_fmt(cell)}."
            )
        if transition is None:
            return (
                "Rule: every state x event cell is a transition (transition_to) or an explicit "
                f"impossible + reason. Offending cell: {_fmt(cell)}. Compliant examples: "
                f"{_fmt(SM_EXAMPLE['cells'])}."
            )
        if transition not in states:
            return (
                f"Rule: transition_to must be one of the machine's states {states}. "
                f"Offending cell: {_fmt(cell)}."
            )
    return None


def _cell_values(cell: dict) -> dict:
    return {
        "state": _text(cell, "state"), "event": _text(cell, "event"),
        "transition_to": _text(cell, "transition_to"),
        "impossible": 1 if cell.get("impossible") else 0,
        "impossible_reason": _text(cell, "impossible_reason"),
    }


def submit_states(conn: sqlite3.Connection, rows: list[dict]) -> dict:
    seen_entities: set[int] = set()

    def validate(row: dict) -> str | None:
        err = (_unknown_fields_error(row, SM_FIELDS) or _envelope_error(row)
               or _id_lookup_error(conn, row, "entity_id", "entities"))
        if err:
            return err
        entity = _fetch(conn, "entities", row["entity_id"])
        if not entity["has_lifecycle"]:
            return (
                f"Rule: state machines belong to lifecycle entities only — '{entity['name']}' "
                f"has has_lifecycle=false (reason: \"{entity['lifecycle_reason']}\"). If that "
                f"judgment is now wrong, file_conflict referencing entities:{entity['id']} so "
                f"the user can adjudicate. Offending row: {_fmt(row)}."
            )
        if row["entity_id"] in seen_entities or conn.execute(
                "SELECT 1 FROM state_machines WHERE entity_id = ?",
                (row["entity_id"],)).fetchone():
            return (
                f"Rule: one state machine per entity — '{entity['name']}' already has one. "
                f"Add cells to it with submit_state_cells instead. Offending row: {_fmt(row)}."
            )
        err = _name_list_error(row, "states", "state") or _name_list_error(row, "events", "event")
        if err:
            return err
        cells = row.get("cells")
        if cells is not None and not isinstance(cells, list):
            return f"Rule: cells is an array of cell objects. Offending row: {_fmt(row)}."
        seen_cells: set[tuple] = set()
        for cell in cells or []:
            if not isinstance(cell, dict):
                return (
                    "Rule: each cell is an object (state, event, transition_to | impossible + "
                    f"reason). Offending cell: {_fmt(cell)}."
                )
            err = (_unknown_fields_error(cell, CELL_FIELDS) or _child_envelope_error(cell)
                   or _cell_body_error(cell, row["states"], row["events"]))
            if err:
                return err
            key = (_text(cell, "state"), _text(cell, "event"))
            if key in seen_cells:
                return (
                    f"Rule: one cell per state x event — duplicate {list(key)} in this machine. "
                    f"Offending row: {_fmt(row)}."
                )
            seen_cells.add(key)
        seen_entities.add(row["entity_id"])
        return None

    def insert(row, plan):
        env = _envelope(plan, row)
        machine_id = db.insert_row(conn, "state_machines", {
            "entity_id": row["entity_id"],
            "states": json.dumps(row["states"]), "events": json.dumps(row["events"]), **env})
        for cell in row.get("cells") or []:
            db.insert_row(conn, "sm_cells", {
                "machine_id": machine_id, **_cell_values(cell),
                **_child_envelope(plan, cell, env)})
        return {"id": machine_id, "cells": len(row.get("cells") or [])}

    return _submit_batch(conn, rows, validate, insert)


def submit_state_cells(conn: sqlite3.Connection, rows: list[dict]) -> dict:
    seen: set[tuple] = set()

    def validate(row: dict) -> str | None:
        err = (_unknown_fields_error(row, SM_CELL_FIELDS) or _envelope_error(row)
               or _id_lookup_error(conn, row, "entity_id", "entities"))
        if err:
            return err
        machine = conn.execute(
            "SELECT * FROM state_machines WHERE entity_id = ?", (row["entity_id"],)).fetchone()
        if machine is None:
            return (
                f"Rule: entity entities:{row['entity_id']} has no state machine yet — create it "
                f"first with submit_states (states, events, then cells). Offending row: {_fmt(row)}."
            )
        err = _cell_body_error(row, json.loads(machine["states"]), json.loads(machine["events"]))
        if err:
            return err
        key = (machine["id"], _text(row, "state"), _text(row, "event"))
        if key in seen or conn.execute(
                "SELECT 1 FROM sm_cells WHERE machine_id = ? AND state = ? AND event = ?",
                key).fetchone():
            return (
                f"Rule: one cell per state x event — ({key[1]}, {key[2]}) is already recorded "
                f"for this machine (or earlier in this batch). Offending row: {_fmt(row)}. If "
                "the recorded cell is wrong, file_conflict referencing it so the user can "
                "adjudicate."
            )
        seen.add(key)
        return None

    def insert(row, plan):
        machine = conn.execute(
            "SELECT id FROM state_machines WHERE entity_id = ?", (row["entity_id"],)).fetchone()
        return db.insert_row(conn, "sm_cells", {
            "machine_id": machine["id"], **_cell_values(row), **_envelope(plan, row)})

    return _submit_batch(conn, rows, validate, insert)


# --- components & contracts (stage 6) ----------------------------------------

def submit_components(conn: sqlite3.Connection, rows: list[dict]) -> dict:
    seen: set[str] = set()

    def validate(row: dict) -> str | None:
        err = _unknown_fields_error(row, COMPONENT_FIELDS) or _envelope_error(row)
        if err:
            return err
        name = _text(row, "name")
        if name is None:
            return f"Rule: every component needs a non-empty name. Offending row: {_fmt(row)}."
        if _text(row, "responsibility") is None:
            return (
                "Rule: every component records its responsibility — the single reason it exists "
                "and changes. If you cannot state it in one sentence, the component cut is wrong "
                f"(merge or re-cut). Offending row: {_fmt(row)}. Compliant example: "
                f"{_fmt(COMPONENT_EXAMPLE)}."
            )
        key = name.lower()
        if key in seen or conn.execute(
                "SELECT 1 FROM components WHERE lower(name) = ?", (key,)).fetchone():
            return (
                f"Rule: one row per component — '{name}' already exists in this plan (or earlier "
                f"in this batch). Offending row: {_fmt(row)}."
            )
        seen.add(key)
        return None

    def insert(row, plan):
        return db.insert_row(conn, "components", {
            "name": _text(row, "name"), "responsibility": _text(row, "responsibility"),
            **_envelope(plan, row)})

    return _submit_batch(conn, rows, validate, insert)


def _param_error(p) -> str | None:
    if not isinstance(p, dict):
        return f"Rule: each param is an object {{name, type_expr, required?}}. Offending param: {_fmt(p)}."
    unknown = sorted(set(p) - PARAM_FIELDS)
    if unknown:
        return (
            f"Rule: unknown param field(s) {unknown} — valid: {sorted(PARAM_FIELDS)}. "
            f"Offending param: {_fmt(p)}."
        )
    if _text(p, "name") is None or _text(p, "type_expr") is None:
        return (
            "Rule: every param carries name and type_expr (type notation of the target stack — "
            f"recorded, never compiled). Offending param: {_fmt(p)}."
        )
    if "required" in p and p["required"] not in (True, False, 0, 1):
        return f"Rule: param required is a boolean (default true). Offending param: {_fmt(p)}."
    return None


def _error_item_error(e) -> str | None:
    if not isinstance(e, dict) or set(e) - ERROR_ITEM_FIELDS \
            or _strip(e.get("name")) is None or _strip(e.get("semantics")) is None:
        return (
            "Rule: each error is an object {name, semantics} — the name callers match on and "
            f"what it means/guarantees. Offending error: {_fmt(e)}. Compliant example: "
            f"{_fmt(CONTRACT_EXAMPLE['errors'])}."
        )
    return None


def submit_contracts(conn: sqlite3.Connection, rows: list[dict]) -> dict:
    seen: set[tuple] = set()

    def validate(row: dict) -> str | None:
        err = (_unknown_fields_error(row, CONTRACT_FIELDS) or _envelope_error(row)
               or _id_lookup_error(conn, row, "component_id", "components"))
        if err:
            return err
        name = _text(row, "name")
        if name is None:
            return (
                f"Rule: every contract needs a non-empty name. Offending row: {_fmt(row)}. "
                f"Compliant example: {_fmt(CONTRACT_EXAMPLE)}."
            )
        kind = _text(row, "kind")
        if kind not in CONTRACT_KINDS:
            return f"Rule: kind is one of {list(CONTRACT_KINDS)}. Offending row: {_fmt(row)}."
        key = (row["component_id"], name.lower())
        if key in seen or conn.execute(
                "SELECT 1 FROM contracts WHERE component_id = ? AND lower(name) = ?",
                key).fetchone():
            return (
                f"Rule: one row per contract — '{name}' already exists on component "
                f"components:{row['component_id']} (or earlier in this batch). "
                f"Offending row: {_fmt(row)}."
            )
        params = row.get("params")
        if not isinstance(params, list):
            return (
                "Rule: params is required — an array of {name, type_expr, required?}; pass [] "
                "to record explicitly that the contract takes none. Offending row: "
                f"{_fmt(row)}. Compliant example: {_fmt(CONTRACT_EXAMPLE)}."
            )
        seen_params: set[str] = set()
        for p in params:
            err = _param_error(p)
            if err:
                return f"{err} In row: {_fmt(row)}."
            pkey = _text(p, "name").lower()
            if pkey in seen_params:
                return f"Rule: param names must be unique within a contract. Offending row: {_fmt(row)}."
            seen_params.add(pkey)
        if _text(row, "returns") is None:
            return (
                "Rule: every contract records its return type_expr in the target stack's "
                "notation — use the stack's 'nothing' form (None, void, unit, 204, ...) when it "
                f"returns nothing. Offending row: {_fmt(row)}."
            )
        errors = row.get("errors")
        cannot_fail = row.get("cannot_fail", False)
        if cannot_fail not in (True, False, 0, 1):
            return f"Rule: cannot_fail is a boolean. Offending row: {_fmt(row)}."
        if cannot_fail:
            if errors:
                return (
                    "Rule: a contract declares named errors or cannot_fail — never both. "
                    f"Offending row: {_fmt(row)}."
                )
            if _text(row, "cannot_fail_reason") is None:
                return (
                    "Rule: cannot_fail needs a recorded reason. Offending row: "
                    f"{_fmt(row)}. Compliant example: {_fmt(CONTRACT_CANNOT_FAIL_EXAMPLE)}."
                )
        else:
            if _text(row, "cannot_fail_reason"):
                return (
                    "Rule: cannot_fail_reason accompanies cannot_fail=true only. "
                    f"Offending row: {_fmt(row)}."
                )
            if not isinstance(errors, list) or not errors:
                return (
                    "Rule: every contract declares >=1 named error with semantics, or "
                    "cannot_fail=true + reason — error behaviour is part of the signature. "
                    f"Offending row: {_fmt(row)}. Compliant examples: {_fmt(CONTRACT_EXAMPLE)} "
                    f"or {_fmt(CONTRACT_CANNOT_FAIL_EXAMPLE)}."
                )
            seen_errors: set[str] = set()
            for e in errors:
                err = _error_item_error(e)
                if err:
                    return f"{err} In row: {_fmt(row)}."
                ekey = _strip(e["name"]).lower()
                if ekey in seen_errors:
                    return f"Rule: error names must be unique within a contract. Offending row: {_fmt(row)}."
                seen_errors.add(ekey)
        if "is_external" in row and row["is_external"] not in (True, False, 0, 1):
            return (
                "Rule: is_external is a boolean — true iff the contract is consumed from "
                f"outside the system. Offending row: {_fmt(row)}."
            )
        seen.add(key)
        return None

    def insert(row, plan):
        params = [{"name": _text(p, "name"), "type_expr": _text(p, "type_expr"),
                   "required": bool(p.get("required", True))} for p in row["params"]]
        errors = [{"name": _strip(e["name"]), "semantics": _strip(e["semantics"])}
                  for e in row.get("errors") or []]
        return db.insert_row(conn, "contracts", {
            "component_id": row["component_id"], "name": _text(row, "name"),
            "kind": _text(row, "kind"), "params": json.dumps(params),
            "returns": _text(row, "returns"),
            "errors": json.dumps(errors) if errors else None,
            "cannot_fail": 1 if row.get("cannot_fail") else 0,
            "cannot_fail_reason": _text(row, "cannot_fail_reason"),
            "is_external": 1 if row.get("is_external") else 0,
            **_envelope(plan, row)})

    return _submit_batch(conn, rows, validate, insert)


def submit_contract_deps(conn: sqlite3.Connection, rows: list[dict]) -> dict:
    def validate(row: dict) -> str | None:
        err = _unknown_fields_error(row, CONTRACT_DEP_FIELDS) or _envelope_error(row)
        if err:
            return err
        has_contract = row.get("consumer_contract_id") is not None
        has_component = row.get("consumer_component_id") is not None
        if has_contract == has_component:
            return (
                "Rule: exactly one consumer per edge — consumer_contract_id or "
                f"consumer_component_id, not both and not neither. Offending row: {_fmt(row)}. "
                f"Compliant example: {_fmt(CONTRACT_DEP_EXAMPLE)}."
            )
        err = _id_lookup_error(conn, row, "provider_contract_id", "contracts")
        if err:
            return err
        if has_contract:
            err = _id_lookup_error(conn, row, "consumer_contract_id", "contracts")
            if err:
                return err
            if row["consumer_contract_id"] == row["provider_contract_id"]:
                return f"Rule: a contract cannot consume itself. Offending row: {_fmt(row)}."
        else:
            err = _id_lookup_error(conn, row, "consumer_component_id", "components")
            if err:
                return err
        return None

    def insert(row, plan):
        return db.insert_row(conn, "contract_deps", {
            "consumer_contract_id": row.get("consumer_contract_id"),
            "consumer_component_id": row.get("consumer_component_id"),
            "provider_contract_id": row["provider_contract_id"],
            **_envelope(plan, row)})

    return _submit_batch(conn, rows, validate, insert)


# --- dependencies & failure modes (stage 5) -----------------------------------

def submit_dependencies(conn: sqlite3.Connection, rows: list[dict]) -> dict:
    seen: set[str] = set()

    def validate(row: dict) -> str | None:
        err = _unknown_fields_error(row, DEPENDENCY_FIELDS) or _envelope_error(row)
        if err:
            return err
        name = _text(row, "name")
        if name is None:
            return (
                f"Rule: every dependency needs a non-empty name. Offending row: {_fmt(row)}. "
                f"Compliant example: {_fmt(DEPENDENCY_EXAMPLE)}."
            )
        if _text(row, "kind") is None:
            return (
                "Rule: every dependency records its kind — service, library, api, filesystem, "
                f"... (free text). Offending row: {_fmt(row)}. Compliant example: "
                f"{_fmt(DEPENDENCY_EXAMPLE)}."
            )
        key = name.lower()
        if key in seen or conn.execute(
                "SELECT 1 FROM dependencies WHERE lower(name) = ?", (key,)).fetchone():
            return (
                f"Rule: one row per dependency — '{name}' already exists in this plan (or "
                f"earlier in this batch). Offending row: {_fmt(row)}."
            )
        seen.add(key)
        return None

    def insert(row, plan):
        return db.insert_row(conn, "dependencies", {
            "name": _text(row, "name"), "kind": _text(row, "kind"),
            "notes": _text(row, "notes"), **_envelope(plan, row)})

    return _submit_batch(conn, rows, validate, insert)


def submit_dep_failure_modes(conn: sqlite3.Connection, rows: list[dict]) -> dict:
    seen: set[tuple] = set()

    def validate(row: dict) -> str | None:
        err = (_unknown_fields_error(row, DEP_FM_FIELDS) or _envelope_error(row)
               or _id_lookup_error(conn, row, "dep_id", "dependencies"))
        if err:
            return err
        mode = _text(row, "mode")
        if mode not in FAILURE_MODES:
            return (
                f"Rule: mode is one of {list(FAILURE_MODES)} — the stage-5 gate requires all "
                f"five per dependency. Offending row: {_fmt(row)}. Compliant example: "
                f"{_fmt(DEP_FM_EXAMPLE)}."
            )
        if _text(row, "handling") is None:
            return (
                "Rule: every failure mode records its handling (what the system does when the "
                f"dependency behaves this way). Offending row: {_fmt(row)}. Compliant example: "
                f"{_fmt(DEP_FM_EXAMPLE)}."
            )
        key = (row["dep_id"], mode)
        if key in seen or conn.execute(
                "SELECT 1 FROM dep_failure_modes WHERE dep_id = ? AND mode = ?", key).fetchone():
            return (
                f"Rule: one row per dependency x mode — (dep {row['dep_id']}, {mode}) is already "
                f"recorded (or earlier in this batch). Offending row: {_fmt(row)}. If the "
                "recorded handling is wrong, file_conflict referencing it so the user can "
                "adjudicate."
            )
        seen.add(key)
        return None

    def insert(row, plan):
        return db.insert_row(conn, "dep_failure_modes", {
            "dep_id": row["dep_id"], "mode": _text(row, "mode"),
            "handling": _text(row, "handling"), **_envelope(plan, row)})

    return _submit_batch(conn, rows, validate, insert)


# --- questions, conflicts, decisions (bookkeeping + ADRs) ---------------------

def file_question(conn: sqlite3.Connection, text: str, owner: str | None = None,
                  links: list[str] | None = None) -> dict:
    args = _clean({"text": text, "owner": owner, "links": links})
    if _text(args, "text") is None:
        return {"error": f"Rule: a question needs non-empty text. Offending input: {_fmt(args)}."}
    err = _links_error(args) or _dangling_refs_error(conn, args.get("links"), args)
    if err:
        return {"error": err}
    plan = db.get_plan(conn)
    qid = db.insert_row(conn, "open_questions", {
        **_bookkeeping_values(plan),
        "text": _text(args, "text"), "owner": _text(args, "owner"),
        "links": json.dumps(args["links"]) if args.get("links") else None})
    conn.commit()
    return {"id": qid, "state": "open"}


def resolve_question(conn: sqlite3.Connection, question_id: int,
                     resolution: str | None = None, defer: bool = False) -> dict:
    question = None
    if isinstance(question_id, int) and not isinstance(question_id, bool):
        question = _fetch(conn, "open_questions", question_id)
    if question is None:
        open_qs = {r["id"]: r["text"] for r in conn.execute(
            "SELECT id, text FROM open_questions WHERE state = 'open' ORDER BY id")}
        return {"error": (
            "Rule: question_id must match an existing question. Open questions (id: text): "
            f"{_fmt(open_qs)}. Offending input: question_id={_fmt(question_id)}.")}
    if question["state"] == "resolved":
        return {"error": (
            f"Rule: question #{question['id']} is already resolved "
            f"(\"{question['resolution']}\"). File a new question if it has reopened.")}
    if defer:
        state, res = "deferred", _strip(resolution)
    else:
        res = _strip(resolution)
        if res is None:
            return {"error": (
                "Rule: resolving a question records its resolution (or pass defer=true to park "
                "it deliberately). Offending input: "
                f"{_fmt({'question_id': question_id, 'resolution': resolution})}.")}
        state = "resolved"
    conn.execute("UPDATE open_questions SET state = ?, resolution = ? WHERE id = ?",
                 (state, res, question["id"]))
    conn.commit()
    return {"id": question["id"], "state": state, "resolution": res}


def file_conflict(conn: sqlite3.Connection, description: str, refs: list[str]) -> dict:
    args = _clean({"description": description, "refs": refs})
    if _text(args, "description") is None:
        return {"error": (
            "Rule: a conflict needs a non-empty description of what disagrees with what. "
            f"Offending input: {_fmt(args)}.")}
    refs = args.get("refs")
    if not isinstance(refs, list) or not refs or any(
            not isinstance(x, str) or _parse_ref(x) is None for x in refs):
        return {"error": (
            "Rule: refs is a non-empty array of row refs \"table:id\" naming the disagreeing "
            f"rows, e.g. [\"requirements:12\", \"decisions:3\"]. Offending input: {_fmt(args)}.")}
    err = _dangling_refs_error(conn, refs, args)
    if err:
        return {"error": err}
    plan = db.get_plan(conn)
    cid = db.insert_row(conn, "conflicts", {
        **_bookkeeping_values(plan),
        "description": _text(args, "description"), "refs": json.dumps(refs),
        "source": "model"})
    conn.commit()
    return {"id": cid, "state": "open",
            "note": "Filed. It sits at next_gap() priority 1 until resolved with the user."}


def resolve_conflict(conn: sqlite3.Connection, conflict_id: int, resolution: str) -> dict:
    conflict = None
    if isinstance(conflict_id, int) and not isinstance(conflict_id, bool):
        conflict = _fetch(conn, "conflicts", conflict_id)
    if conflict is None:
        open_cs = {r["id"]: r["description"] for r in conn.execute(
            "SELECT id, description FROM conflicts WHERE state = 'open' ORDER BY id")}
        return {"error": (
            "Rule: conflict_id must match an existing conflict. Open conflicts (id: "
            f"description): {_fmt(open_cs)}. Offending input: conflict_id={_fmt(conflict_id)}.")}
    if conflict["state"] == "resolved":
        return {"error": (
            f"Rule: conflict #{conflict['id']} is already resolved "
            f"(\"{conflict['resolution']}\"). File a new conflict if it has reopened.")}
    res = _strip(resolution)
    if res is None:
        return {"error": (
            "Rule: resolving a conflict records how it was resolved — the user's adjudication "
            "or the correcting rows. Offending input: "
            f"{_fmt({'conflict_id': conflict_id, 'resolution': resolution})}.")}
    conn.execute("UPDATE conflicts SET state = 'resolved', resolution = ? WHERE id = ?",
                 (res, conflict["id"]))
    conn.commit()
    return {"id": conflict["id"], "state": "resolved", "resolution": res}


def record_decision(conn: sqlite3.Connection, text: str, provenance: str,
                    rationale: str | None = None, links: list[str] | None = None,
                    alternatives: list[dict] | None = None, challenge: dict | None = None,
                    assumption_kind: str | None = None) -> dict:
    args = _clean({"text": text, "provenance": provenance, "assumption_kind": assumption_kind,
                   "rationale": rationale, "links": links,
                   "alternatives": alternatives, "challenge": challenge})
    if _text(args, "text") is None:
        return {"error": f"Rule: a decision needs non-empty text. Offending input: {_fmt(args)}."}
    err = _envelope_error(args) or _dangling_refs_error(conn, args.get("links"), args)
    if err:
        return {"error": err}
    alternatives = args.get("alternatives") or []
    if not isinstance(alternatives, list):
        return {"error": (
            "Rule: alternatives is an array of {alternative, rejected_because}. Offending "
            f"input: {_fmt(args)}. Compliant example: {_fmt(DECISION_EXAMPLE['alternatives'])}.")}
    for alt in alternatives:
        if not isinstance(alt, dict) or set(alt) - ALTERNATIVE_FIELDS \
                or _strip(alt.get("alternative")) is None \
                or _strip(alt.get("rejected_because")) is None:
            return {"error": (
                "Rule: each alternative carries 'alternative' and a one-line 'rejected_because'. "
                f"Offending alternative: {_fmt(alt)}. Compliant example: "
                f"{_fmt(DECISION_EXAMPLE['alternatives'])}.")}
    challenge = args.get("challenge")
    if challenge is not None:
        if not isinstance(challenge, dict) or set(challenge) - CHALLENGE_FIELDS \
                or _strip(challenge.get("text")) is None \
                or challenge.get("outcome") not in CHALLENGE_OUTCOMES:
            return {"error": (
                "Rule: challenge is null or {text, outcome} with outcome 'overridden' (the user "
                "heard the challenge and kept their call) or 'revised' (the decision changed). "
                f"Offending challenge: {_fmt(challenge)}.")}
    linked_tables = {_parse_ref(ref)[0] for ref in args.get("links") or []}
    significant = bool(linked_tables & SIGNIFICANT_LINK_TABLES)
    if significant and not alternatives:
        return {"error": (
            "Rule: this decision links to a component or contract, so the significance "
            "heuristic (code-enforced — coarse but ungameable) marks it significant, and "
            "significant decisions record the alternatives considered, each with a one-line "
            f"rejection reason. Offending input: {_fmt(args)}. Compliant example: "
            f"{_fmt(DECISION_EXAMPLE)}.")}
    alternatives = [{"alternative": _strip(a["alternative"]),
                     "rejected_because": _strip(a["rejected_because"])} for a in alternatives]
    plan = db.get_plan(conn)
    did = db.insert_row(conn, "decisions", {
        "text": _text(args, "text"), "rationale": _text(args, "rationale"),
        "alternatives": json.dumps(alternatives) if alternatives else None,
        "challenge": json.dumps({"text": _strip(challenge["text"]),
                                 "outcome": challenge["outcome"]}) if challenge else None,
        "significant": 1 if significant else 0,
        **_envelope(plan, args)})
    conn.commit()
    return {"id": did, "significant": significant}
