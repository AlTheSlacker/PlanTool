"""Spike tools (spec sections 5 and 8). register_spike is called BEFORE any
spike code runs and hands back a quarantine directory; record_spike_result
closes the loop. Only a confirmed spike upgrades linked assumed(world) rows
to verified — the engine performs the upgrade so 'verified' is never
model-settable. A refuted spike files engine conflicts on the linked rows it
disproved; budget expiry means inconclusive and escalates to the user as a
risk decision (prompt-enforced, spec section 5.1).
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from . import conflicts, db
from .submits import _clean, _dangling_refs_error, _fmt, _links_error, _parse_ref, _strip

VERDICTS = ("confirmed", "refuted", "inconclusive")

REGISTER_REQUIRED = (
    ("question", "one spike answers exactly one question about external reality"),
    ("hypothesis", "what you expect to observe — a spike that cannot be falsified is not "
                   "an experiment"),
    ("method", "how the probe touches the REAL dependency; a mocked stand-in yields "
               "inconclusive at best"),
    ("budget", "the timebox; expiry means 'inconclusive', never 'keep digging'"),
)


def _slug(question: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", question.lower()).strip("_")[:40] or "spike"


def register_spike(conn: sqlite3.Connection, spikes_root: str | Path, question: str,
                   hypothesis: str | None = None, method: str | None = None,
                   budget: str | None = None, links: list[str] | None = None) -> dict:
    args = _clean({"question": question, "hypothesis": hypothesis, "method": method,
                   "budget": budget, "links": links})
    for field, why in REGISTER_REQUIRED:
        if _strip(args.get(field)) is None:
            return {"error": (
                f"Rule: register_spike requires {field} — {why}. "
                f"Offending input: {_fmt(args)}.")}
    err = _links_error(args) or _dangling_refs_error(conn, args.get("links"), args)
    if err:
        return {"error": err}
    plan = db.get_plan(conn)
    sid = db.insert_row(conn, "spikes", {
        "plan_id": plan["id"], "plan_version_added": plan["version"],
        "question": _strip(args["question"]), "hypothesis": _strip(args["hypothesis"]),
        "method": _strip(args["method"]), "budget": _strip(args["budget"]),
        "links": json.dumps(args["links"]) if args.get("links") else None})
    conn.commit()
    quarantine = Path(spikes_root) / f"{sid:03d}_{_slug(args['question'])}"
    quarantine.mkdir(parents=True, exist_ok=True)
    return {
        "id": sid,
        "quarantine_path": str(quarantine),
        "next": (
            "Write throwaway probe code inside the quarantine dir (any language — whatever "
            "probes the real dependency fastest), run it against the REAL dependency, then "
            "call record_spike_result. Spike code never migrates to any codebase; "
            "implementations rewrite from contracts."),
    }


def record_spike_result(conn: sqlite3.Connection, spike_id, verdict: str,
                        evidence_summary: str, evidence_path: str | None = None) -> dict:
    spike = None
    if isinstance(spike_id, int) and not isinstance(spike_id, bool):
        spike = conn.execute("SELECT * FROM spikes WHERE id = ?", (spike_id,)).fetchone()
    if spike is None:
        open_spikes = {r["id"]: r["question"] for r in conn.execute(
            "SELECT id, question FROM spikes WHERE verdict IS NULL ORDER BY id")}
        return {"error": (
            "Rule: spike_id must match a registered spike. Spikes awaiting a result "
            f"(id: question): {_fmt(open_spikes)}. Offending input: spike_id={_fmt(spike_id)}.")}
    if spike["verdict"] is not None:
        return {"error": (
            f"Rule: spike #{spike['id']} already has verdict '{spike['verdict']}'. One spike = "
            "one question — register a new spike if a new question emerged.")}
    if verdict not in VERDICTS:
        return {"error": (
            f"Rule: verdict is one of {list(VERDICTS)}. 'confirmed'/'refuted' require the "
            "method to have touched the real dependency; budget expiry or a mocked stand-in "
            f"is 'inconclusive'. Offending input: verdict={_fmt(verdict)}.")}
    summary = _strip(evidence_summary)
    if summary is None:
        return {"error": (
            "Rule: evidence_summary records what the experiment actually showed — the "
            "observation, not the conclusion. Offending input: "
            f"{_fmt({'spike_id': spike_id, 'verdict': verdict, 'evidence_summary': evidence_summary})}.")}
    conn.execute(
        "UPDATE spikes SET verdict = ?, evidence_summary = ?, evidence_path = ? WHERE id = ?",
        (verdict, summary, _strip(evidence_path), spike["id"]))
    result: dict = {"id": spike["id"], "verdict": verdict}
    linked = json.loads(spike["links"] or "[]")

    if verdict == "confirmed":
        upgraded, skipped = [], []
        for ref in linked:
            table, rid = _parse_ref(ref)
            if table not in db.CLAIM_TABLES:
                skipped.append({"ref": ref, "reason": "not a claim table — nothing to upgrade"})
                continue
            row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (rid,)).fetchone()
            if row is None:
                skipped.append({"ref": ref, "reason": "row no longer exists"})
            elif row["provenance"] == "assumed" and row["assumption_kind"] == "world":
                conn.execute(
                    f"UPDATE {table} SET provenance = 'verified', spike_id = ?, "
                    "assumption_kind = NULL WHERE id = ?", (spike["id"], rid))
                upgraded.append(ref)
            else:
                skipped.append({"ref": ref, "reason": (
                    f"provenance '{row['provenance']}' — only assumed(world) rows upgrade "
                    "to verified")})
        result["upgraded_to_verified"] = upgraded
        if skipped:
            result["skipped"] = skipped
        stale = conflicts.check_resolved_question_staleness(conn, upgraded)
        if stale:
            result["conflicts_filed"] = stale
    elif verdict == "refuted":
        filed = []
        for ref in linked:
            table, rid = _parse_ref(ref)
            if table not in db.CLAIM_TABLES:
                continue
            row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (rid,)).fetchone()
            if row is not None and row["provenance"] == "assumed":
                conflict = conflicts.file_engine_conflict(
                    conn,
                    f"Spike #{spike['id']} refuted its hypothesis "
                    f"(\"{spike['hypothesis']}\") — linked row {ref} records the disproved "
                    "assumption and needs correcting.",
                    [ref, f"spikes:{spike['id']}"])
                if conflict:
                    filed.append(conflict)
        if filed:
            result["conflicts_filed"] = filed
        result["note"] = (
            "A refuted hypothesis is a spike success — update the linked rows to match "
            "reality and record the correction.")
    else:
        result["note"] = (
            "Inconclusive — escalate to the user as a risk decision (record_decision with "
            "the unresolved risk and how the plan absorbs it).")
    conn.commit()
    return result
