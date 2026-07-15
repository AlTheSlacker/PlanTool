"""Write-time validation and batched inserts (spec section 5).

Contract: every submitted row gets its own accept/reject verdict — one bad
row never bounces the batch. Rejections are pedagogic: they name the rule,
show the offending input, and show what compliance looks like.
"""
from __future__ import annotations

import json
import sqlite3

from . import db

PROVENANCE_VALUES = ("decided", "derived", "assumed", "verified")
ASSUMPTION_KINDS = ("world", "intent")

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

REQUIREMENT_FIELDS = frozenset(
    ("ears_type", "is_nfr", *SLOT_FIELDS, *PLANGUAGE_FIELDS, "provenance", "assumption_kind", "links")
)
ENTITY_FIELDS = frozenset(
    ("name", "description", "has_lifecycle", "lifecycle_reason", "provenance", "assumption_kind", "links")
)


def _fmt(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def _text(row: dict, field: str) -> str | None:
    """Field value as a stripped non-empty string, else None."""
    v = row.get(field)
    if isinstance(v, str):
        v = v.strip()
    return v if v else None


def _unknown_fields_error(row: dict, allowed: frozenset[str]) -> str | None:
    unknown = sorted(set(row) - allowed)
    if unknown:
        return (
            f"Rule: unknown field(s) {unknown} — likely a typo or a fact that belongs in "
            f"another table. Valid fields: {sorted(allowed)}. Offending row: {_fmt(row)}."
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
            "Compliant: submit with provenance='assumed', assumption_kind='world', then run a "
            "spike against the real dependency (spike tools arrive in a later build session)."
        )
    links = row.get("links")
    if links is not None and (
        not isinstance(links, list) or not all(isinstance(x, str) and ":" in x for x in links)
    ):
        return (
            "Rule: links is a JSON array of row refs shaped \"table:id\", e.g. "
            f"[\"requirements:12\", \"decisions:3\"]. Offending row: {_fmt(row)}."
        )
    return None


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


def _requirement_values(row: dict) -> dict:
    return {
        "ears_type": _text(row, "ears_type"),
        "trigger_text": _text(row, "trigger"),
        "precondition": _text(row, "precondition"),
        "feature": _text(row, "feature"),
        "system_response": _text(row, "system_response"),
        "is_nfr": 1 if row.get("is_nfr") else 0,
        "planguage_scale": _text(row, "planguage_scale"),
        "planguage_meter": _text(row, "planguage_meter"),
        "planguage_target": _text(row, "planguage_target"),
    }


def _entity_values(row: dict) -> dict:
    return {
        "name": _text(row, "name"),
        "description": _text(row, "description"),
        "has_lifecycle": 1 if row.get("has_lifecycle") else 0,
        "lifecycle_reason": _text(row, "lifecycle_reason"),
    }


def _submit_batch(conn, rows, validate, to_values, table) -> dict:
    """Shared batch driver: per-row verdicts, partial acceptance, one commit."""
    plan = db.get_plan(conn)
    verdicts = []
    for i, raw in enumerate(rows):
        row = {k: v for k, v in dict(raw).items() if v is not None}
        err = validate(row)
        if err is None:
            values = to_values(row)
            values.update(
                plan_id=plan["id"],
                plan_version_added=plan["version"],
                provenance=_text(row, "provenance"),
                assumption_kind=_text(row, "assumption_kind"),
                links=json.dumps(row["links"]) if row.get("links") else None,
            )
            try:
                row_id = db.insert_row(conn, table, values)
                verdicts.append({"index": i, "accepted": True, "id": row_id})
                continue
            except sqlite3.IntegrityError as exc:
                err = f"Rule: database constraint '{exc}'. Offending row: {_fmt(row)}."
        verdicts.append({"index": i, "accepted": False, "error": err})
    conn.commit()
    return {
        "results": verdicts,
        "accepted": sum(1 for v in verdicts if v["accepted"]),
        "rejected": sum(1 for v in verdicts if not v["accepted"]),
    }


def submit_requirements(conn: sqlite3.Connection, rows: list[dict]) -> dict:
    return _submit_batch(conn, rows, _validate_requirement, _requirement_values, "requirements")


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

    return _submit_batch(conn, rows, validate, _entity_values, "entities")
